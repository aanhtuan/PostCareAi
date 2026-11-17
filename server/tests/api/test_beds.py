"""F03 AC1–AC3: giường (thêm, sửa, danh sách kèm camera và bệnh nhân hiện tại, trùng mã, quyền).

Dữ liệu nền (fixture `client`): giường A01–A03 (id 1–3), camera 1–3 gắn A01–A03,
bệnh nhân BN-001…BN-005 (id 1–5), chưa có phiên mở.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog

BEDS = "/api/v1/beds"
NON_ADMIN = ("nurse", "charge", "doctor")


def _audits(db: Session, entity_type: str) -> list[AuditLog]:
    db.expire_all()
    return list(
        db.scalars(
            select(AuditLog).where(AuditLog.entity_type == entity_type).order_by(AuditLog.id)
        )
    )


def test_admin_crud_beds(client: TestClient, login, db: Session) -> None:
    admin = login("admin")
    r = client.post(BEDS, json={"code": " B01 ", "area": "Khu hậu phẫu 2"}, headers=admin)
    assert r.status_code == 201, r.text
    bed = r.json()
    assert bed["code"] == "B01" and bed["area"] == "Khu hậu phẫu 2"
    assert bed["is_active"] is True and bed["camera"] is None and bed["active_session"] is None

    r = client.get(f"{BEDS}/{bed['id']}", headers=login("nurse"))
    assert r.status_code == 200 and r.json()["code"] == "B01"

    r = client.patch(f"{BEDS}/{bed['id']}", json={"area": "Khu hồi sức"}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["area"] == "Khu hồi sức" and r.json()["code"] == "B01"

    logs = _audits(db, "bed")
    assert [log.action for log in logs] == ["bed.create", "bed.update"]
    assert logs[0].after is not None and logs[0].after["code"] == "B01"
    assert logs[1].before is not None and logs[1].before["area"] == "Khu hậu phẫu 2"
    assert logs[1].after is not None and logs[1].after["area"] == "Khu hồi sức"
    assert logs[1].actor_user_id is not None


def test_bed_list_is_paginated(client: TestClient, login) -> None:
    r = client.get(BEDS, params={"limit": 2, "offset": 1}, headers=login("doctor"))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert [b["code"] for b in body["items"]] == ["A02", "A03"]
    r = client.get(BEDS, params={"limit": 201}, headers=login("doctor"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "body",
    [{"code": "", "area": "Khu"}, {"code": "   ", "area": "Khu"}, {"code": "B09"}, {"area": "K"}],
)
def test_bed_create_validation(client: TestClient, login, body: dict[str, Any]) -> None:
    r = client.post(BEDS, json=body, headers=login("admin"))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_duplicate_bed_code_409(client: TestClient, login) -> None:
    admin = login("admin")
    r = client.post(BEDS, json={"code": "  A01", "area": "Khu"}, headers=admin)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "DUPLICATE_CODE" and err["details"]["field"] == "code"
    assert "A01" in err["message"]
    # Sửa mã của A02 thành A01 cũng trùng.
    r = client.patch(f"{BEDS}/2", json={"code": "A01"}, headers=admin)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_CODE"
    # Giữ nguyên mã của chính nó thì không trùng.
    r = client.patch(f"{BEDS}/1", json={"code": "A01"}, headers=admin)
    assert r.status_code == 200


@pytest.mark.parametrize("username", NON_ADMIN)
def test_write_requires_admin(client: TestClient, login, username: str) -> None:
    h = login(username)
    for method, path, body in [
        ("post", BEDS, {"code": "Z01", "area": "Khu"}),
        ("patch", f"{BEDS}/1", {"area": "Khu"}),
        ("post", "/api/v1/patients", {"code": "BN-900"}),
        ("patch", "/api/v1/patients/1", {"note": "x"}),
        ("post", "/api/v1/cameras", {"name": "C", "source_type": "WEBCAM", "source": "1"}),
        ("patch", "/api/v1/cameras/1", {"name": "C"}),
    ]:
        r = client.request(method, path, json=body, headers=h)
        assert r.status_code == 403, (method, path, r.text)
        assert r.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize("username", (*NON_ADMIN, "admin"))
def test_staff_can_read_catalog(client: TestClient, login, username: str) -> None:
    h = login(username)
    for path in (BEDS, f"{BEDS}/1", "/api/v1/patients", "/api/v1/patients/1"):
        assert client.get(path, headers=h).status_code == 200, path
    for path in ("/api/v1/cameras", "/api/v1/cameras/1"):
        assert client.get(path, headers=h).status_code == 200, path


def test_catalog_requires_login(client: TestClient) -> None:
    for path in (BEDS, "/api/v1/patients", "/api/v1/cameras"):
        r = client.get(path)
        assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED"
    r = client.post(BEDS, json={"code": "Z01", "area": "Khu"})
    assert r.status_code == 401


def test_unknown_bed_404(client: TestClient, login) -> None:
    assert client.get(f"{BEDS}/999", headers=login("nurse")).status_code == 404
    r = client.patch(f"{BEDS}/999", json={"area": "x"}, headers=login("admin"))
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_beds_list_includes_camera_and_current_patient(
    client: TestClient, login, open_session: dict[str, Any]
) -> None:
    items = client.get(BEDS, headers=login("doctor")).json()["items"]
    a01, a02 = items[0], items[1]
    assert a01["code"] == "A01"
    assert a01["camera"] == {"id": 1, "name": "Camera A01", "status": "UNKNOWN"}
    assert a01["active_session"]["id"] == open_session["id"]
    assert a01["active_session"]["patient_code"] == "BN-001"
    # Giường không có phiên mở: không có bệnh nhân hiện tại.
    assert a02["active_session"] is None
