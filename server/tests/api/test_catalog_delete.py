"""F03 AC5, AC6: xóa mềm, khôi phục, chặn xóa khi đang dùng trong phiên mở (QA#36)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, event, select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog, Camera

RESOURCES = {
    "beds": ("bed", {"code": "Z01", "area": "Khu"}),
    "patients": ("patient", {"code": "BN-900"}),
    "cameras": ("camera", {"name": "Cam Z", "source_type": "WEBCAM", "source": "5"}),
}


def _create(client: TestClient, admin: dict[str, str], resource: str) -> dict[str, Any]:
    r = client.post(f"/api/v1/{resource}", json=RESOURCES[resource][1], headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


def _actions(db: Session, entity_type: str, entity_id: int) -> list[str]:
    db.expire_all()
    q = (
        select(AuditLog.action)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.id)
    )
    return list(db.scalars(q))


@pytest.mark.parametrize("resource", list(RESOURCES))
def test_soft_delete_and_restore(client: TestClient, login, db: Session, resource: str) -> None:
    admin = login("admin")
    item = _create(client, admin, resource)
    url = f"/api/v1/{resource}/{item['id']}"

    r = client.delete(url, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False
    # Chi tiết vẫn xem được.
    r = client.get(url, headers=login("nurse"))
    assert r.status_code == 200 and r.json()["is_active"] is False

    r = client.post(f"{url}/restore", headers=admin)
    assert r.status_code == 200 and r.json()["is_active"] is True

    entity = RESOURCES[resource][0]
    assert _actions(db, entity, item["id"]) == [
        f"{entity}.create",
        f"{entity}.delete",
        f"{entity}.restore",
    ]


@pytest.mark.parametrize("resource", list(RESOURCES))
def test_delete_restore_audited(client: TestClient, login, db: Session, resource: str) -> None:
    """Xóa lặp lại / khôi phục bản ghi đang dùng: 200, không đổi gì, không thêm audit."""
    admin = login("admin")
    item = _create(client, admin, resource)
    url = f"/api/v1/{resource}/{item['id']}"
    assert client.post(f"{url}/restore", headers=admin).status_code == 200
    assert client.delete(url, headers=admin).status_code == 200
    r = client.delete(url, headers=admin)
    assert r.status_code == 200 and r.json()["is_active"] is False
    entity = RESOURCES[resource][0]
    assert _actions(db, entity, item["id"]) == [f"{entity}.create", f"{entity}.delete"]
    db.expire_all()
    log = db.scalars(select(AuditLog).where(AuditLog.action == f"{entity}.delete")).one()
    assert log.before is not None and log.before["is_active"] is True
    assert log.after is not None and log.after["is_active"] is False


@pytest.mark.parametrize("resource", list(RESOURCES))
def test_deleted_hidden_from_default_list(client: TestClient, login, resource: str) -> None:
    admin = login("admin")
    item = _create(client, admin, resource)
    assert client.delete(f"/api/v1/{resource}/{item['id']}", headers=admin).status_code == 200
    nurse = login("nurse")
    body = client.get(f"/api/v1/{resource}", params={"limit": 200}, headers=nurse).json()
    assert item["id"] not in [i["id"] for i in body["items"]]
    body = client.get(
        f"/api/v1/{resource}", params={"limit": 200, "include_inactive": True}, headers=nurse
    ).json()
    found = [i for i in body["items"] if i["id"] == item["id"]]
    assert len(found) == 1 and found[0]["is_active"] is False
    assert body["total"] == len(body["items"])


@pytest.mark.parametrize("username", ["nurse", "charge", "doctor"])
@pytest.mark.parametrize("resource", list(RESOURCES))
def test_delete_requires_admin(
    client: TestClient, login, db: Session, resource: str, username: str
) -> None:
    h = login(username)
    for r in (
        client.delete(f"/api/v1/{resource}/1", headers=h),
        client.post(f"/api/v1/{resource}/1/restore", headers=h),
    ):
        assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"
    assert _actions(db, RESOURCES[resource][0], 1) == []


@pytest.mark.parametrize("resource", list(RESOURCES))
def test_patch_rejects_is_active(client: TestClient, login, resource: str) -> None:
    r = client.patch(f"/api/v1/{resource}/1", json={"is_active": False}, headers=login("admin"))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_no_hard_delete_and_unknown_404(client: TestClient, login) -> None:
    admin = login("admin")
    for resource in RESOURCES:
        assert client.delete(f"/api/v1/{resource}/999", headers=admin).status_code == 404
        assert client.post(f"/api/v1/{resource}/999/restore", headers=admin).status_code == 404
        assert client.delete(f"/api/v1/{resource}", headers=admin).status_code == 405


def test_create_with_code_of_deleted_record_409(client: TestClient, login) -> None:
    admin = login("admin")
    for resource in ("beds", "patients"):
        item = _create(client, admin, resource)
        client.delete(f"/api/v1/{resource}/{item['id']}", headers=admin)
        r = client.post(f"/api/v1/{resource}", json=RESOURCES[resource][1], headers=admin)
        assert r.status_code == 409
        err = r.json()["error"]
        assert err["code"] == "DUPLICATE_CODE" and err["details"]["inactive"] is True
        assert "Khôi phục" in err["message"]


def test_delete_bed_with_open_session_409(
    client: TestClient, login, open_session: dict[str, Any]
) -> None:
    r = client.delete("/api/v1/beds/1", headers=login("admin"))
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "BED_HAS_OPEN_SESSION"
    assert err["details"]["session_id"] == open_session["id"]
    assert client.get("/api/v1/beds/1", headers=login("admin")).json()["is_active"] is True


def test_delete_patient_with_open_session_409(
    client: TestClient, login, open_session: dict[str, Any]
) -> None:
    r = client.delete("/api/v1/patients/1", headers=login("admin"))
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "PATIENT_HAS_OPEN_SESSION"
    assert err["details"]["session_id"] == open_session["id"]


def test_delete_camera_in_active_session_409(
    client: TestClient, login, open_session: dict[str, Any]
) -> None:
    r = client.delete("/api/v1/cameras/1", headers=login("admin"))
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "CAMERA_IN_ACTIVE_SESSION"
    assert err["details"]["session_id"] == open_session["id"]
    # Camera gắn giường nhưng không có phiên mở → xóa được.
    assert client.delete("/api/v1/cameras/2", headers=login("admin")).status_code == 200


def test_delete_allowed_after_session_end(
    client: TestClient, login, open_session: dict[str, Any]
) -> None:
    r = client.post(f"/api/v1/sessions/{open_session['id']}/end", headers=login("nurse"))
    assert r.status_code == 200
    admin = login("admin")
    for path in ("/api/v1/cameras/1", "/api/v1/beds/1", "/api/v1/patients/1"):
        assert client.delete(path, headers=admin).status_code == 200, path


def test_delete_camera_frees_bed(client: TestClient, login, db: Session) -> None:
    admin = login("admin")
    before = client.get("/api/v1/cameras/1", headers=admin).json()["config_version"]
    r = client.delete("/api/v1/cameras/1", headers=admin)
    assert r.status_code == 200
    assert r.json()["bed_id"] is None
    assert r.json()["config_version"] == before + 1
    db.expire_all()
    log = db.scalars(select(AuditLog).where(AuditLog.action == "camera.delete")).one()
    assert log.before is not None and log.before["bed_id"] == 1
    # Giường A01 gắn được camera khác.
    r = client.post(
        "/api/v1/cameras",
        json={"name": "Cam mới", "source_type": "WEBCAM", "source": "1", "bed_id": 1},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    # Khôi phục camera cũ không tự gắn lại giường.
    r = client.post("/api/v1/cameras/1/restore", headers=admin)
    assert r.status_code == 200 and r.json()["bed_id"] is None
    assert db.get(Camera, 1) is not None


def test_delete_bed_keeps_camera_link(client: TestClient, login) -> None:
    admin = login("admin")
    r = client.delete("/api/v1/beds/2", headers=admin)
    assert r.status_code == 200 and r.json()["camera"]["id"] == 2
    r = client.post("/api/v1/beds/2/restore", headers=admin)
    assert r.status_code == 200 and r.json()["camera"]["id"] == 2


def test_deleted_bed_cannot_start_session(client: TestClient, login) -> None:
    assert client.delete("/api/v1/beds/2", headers=login("admin")).status_code == 200
    r = client.post("/api/v1/sessions", json={"bed_id": 2, "patient_id": 2}, headers=login("nurse"))
    assert r.status_code == 400
    assert client.delete("/api/v1/patients/3", headers=login("admin")).status_code == 200
    r = client.post("/api/v1/sessions", json={"bed_id": 3, "patient_id": 3}, headers=login("nurse"))
    assert r.status_code == 400


def test_deleted_bed_history_still_accessible(
    client: TestClient, login, open_session: dict[str, Any], post_event
) -> None:
    r = post_event("SIT_UP", "INFO")
    assert r.status_code == 201, r.text
    nurse = login("nurse")
    sid = open_session["id"]
    assert client.post(f"/api/v1/sessions/{sid}/end", headers=nurse).status_code == 200
    admin = login("admin")
    assert client.delete("/api/v1/beds/1", headers=admin).status_code == 200
    assert client.delete("/api/v1/patients/1", headers=admin).status_code == 200

    r = client.get(f"/api/v1/sessions/{sid}", headers=nurse)
    assert r.status_code == 200 and r.json()["bed_code"] == "A01"
    r = client.get(f"/api/v1/sessions/{sid}/timeline", headers=nurse)
    assert r.status_code == 200
    assert [i["code"] for i in r.json()["items"]] == ["SIT_UP"]
    r = client.get("/api/v1/beds/1", headers=nurse)
    assert r.status_code == 200 and r.json()["is_active"] is False


def test_start_session_locks_bed_and_patient_rows(
    client: TestClient, login, connection: Connection
) -> None:
    """Review F03 #2: mở phiên khóa hàng giường và bệnh nhân để không tranh chấp với xóa mềm."""
    statements: list[str] = []

    def capture(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        statements.append(" ".join(statement.split()))

    nurse = login("nurse")
    event.listen(connection, "before_cursor_execute", capture)
    try:
        r = client.post("/api/v1/sessions", json={"bed_id": 2, "patient_id": 2}, headers=nurse)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert r.status_code == 201, r.text
    locked = [s for s in statements if s.endswith("FOR UPDATE")]
    assert any("FROM beds" in s for s in locked), statements
    assert any("FROM patients" in s for s in locked), statements


@pytest.mark.parametrize(
    "patch",
    [
        {"bed_id": None},
        {"bed_id": "NEW_BED"},
        {"source": "1"},
        {"source_type": "FILE", "source": "a.mp4"},
    ],
)
def test_update_camera_in_active_session_409(
    client: TestClient, login, open_session: dict[str, Any], patch: dict[str, Any]
) -> None:
    """Review F03 #4: không đổi giường hoặc nguồn của camera đang dùng cho phiên mở."""
    admin = login("admin")
    if patch.get("bed_id") == "NEW_BED":
        r = client.post("/api/v1/beds", json={"code": "Z09", "area": "Khu"}, headers=admin)
        patch = {"bed_id": r.json()["id"]}
    before = client.get("/api/v1/cameras/1", headers=admin).json()
    r = client.patch("/api/v1/cameras/1", json=patch, headers=admin)
    assert r.status_code == 409, r.text
    err = r.json()["error"]
    assert err["code"] == "CAMERA_IN_ACTIVE_SESSION"
    assert err["details"]["session_id"] == open_session["id"]
    assert client.get("/api/v1/cameras/1", headers=admin).json() == before


def test_update_camera_in_active_session_allows_name_and_same_values(
    client: TestClient, login, open_session: dict[str, Any]
) -> None:
    admin = login("admin")
    r = client.patch(
        "/api/v1/cameras/1",
        json={"name": "Camera giường A01", "source_type": "WEBCAM", "source": "0", "bed_id": 1},
        headers=admin,
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Camera giường A01"
