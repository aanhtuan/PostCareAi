"""F37 AC1, AC2, AC4: khu vực (CRUD, xóa mềm, khôi phục, ràng buộc giường, quyền, audit).

Dữ liệu nền (fixture `client`): khu vực "Khu hậu phẫu" (id 1, mã KV01) chứa giường A01–A03.
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog, User
from postcare.domain.security import hash_password
from postcare.schemas.enums import UserRole
from tests.conftest import PASSWORD

Login = Callable[[str], dict[str, str]]

AREAS = "/api/v1/areas"
SHIFTS = "/api/v1/shifts"
BEDS = "/api/v1/beds"


def _audits(db: Session, entity_type: str, entity_id: int | None = None) -> list[AuditLog]:
    db.expire_all()
    q = select(AuditLog).where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.where(AuditLog.entity_id == entity_id)
    return list(db.scalars(q.order_by(AuditLog.id)))


def _new_area(client: TestClient, admin: dict[str, str], code: str = "HP-2") -> dict[str, Any]:
    r = client.post(AREAS, json={"code": code, "name": "Hậu phẫu 2"}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def family(client: TestClient, db: Session, login: Login) -> dict[str, str]:
    db.add(
        User(
            username="family",
            full_name="Người nhà thử nghiệm",
            password_hash=hash_password(PASSWORD),
            role=UserRole.FAMILY,
        )
    )
    db.commit()
    return login("family")


def test_seed_area_and_list(client: TestClient, login: Login) -> None:
    r = client.get(AREAS, headers=login("nurse"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    area = body["items"][0]
    assert area["code"] == "KV01" and area["name"] == "Khu hậu phẫu"
    assert area["is_active"] is True and area["bed_count"] == 3


def test_beds_list_shows_area_name(client: TestClient, login: Login) -> None:
    r = client.get(BEDS, headers=login("doctor"))
    assert r.status_code == 200
    for bed in r.json()["items"]:
        assert bed["area"] == {"id": 1, "code": "KV01", "name": "Khu hậu phẫu"}
    r = client.get("/api/v1/overview", headers=login("nurse"))
    assert {b["area"] for b in r.json()["beds"]} == {"Khu hậu phẫu"}


def test_admin_crud_areas(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    r = client.post(AREAS, json={"code": " HP-2 ", "name": " Hậu phẫu 2 "}, headers=admin)
    assert r.status_code == 201, r.text
    area = r.json()
    assert area["code"] == "HP-2" and area["name"] == "Hậu phẫu 2" and area["bed_count"] == 0
    url = f"{AREAS}/{area['id']}"

    r = client.patch(url, json={"name": "Hồi sức"}, headers=admin)
    assert r.status_code == 200 and r.json()["name"] == "Hồi sức" and r.json()["code"] == "HP-2"

    r = client.delete(url, headers=admin)
    assert r.status_code == 200 and r.json()["is_active"] is False
    r = client.get(AREAS, headers=admin)
    assert [a["code"] for a in r.json()["items"]] == ["KV01"]
    r = client.get(AREAS, params={"include_inactive": True}, headers=admin)
    assert {a["code"] for a in r.json()["items"]} == {"KV01", "HP-2"}

    r = client.post(f"{url}/restore", headers=admin)
    assert r.status_code == 200 and r.json()["is_active"] is True

    logs = _audits(db, "area", area["id"])
    assert [log.action for log in logs] == [
        "area.create",
        "area.update",
        "area.delete",
        "area.restore",
    ]
    assert logs[1].before is not None and logs[1].before["name"] == "Hậu phẫu 2"
    assert logs[1].after is not None and logs[1].after["name"] == "Hồi sức"
    assert all(log.actor_user_id is not None for log in logs)


def test_duplicate_area_code_409(client: TestClient, login: Login) -> None:
    admin = login("admin")
    r = client.post(AREAS, json={"code": "KV01", "name": "Khác"}, headers=admin)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "DUPLICATE_CODE" and err["details"]["field"] == "code"
    # Trùng mã của khu vực đã xóa cũng bị chặn (mã duy nhất kể cả đã xóa).
    area = _new_area(client, admin)
    client.delete(f"{AREAS}/{area['id']}", headers=admin)
    r = client.post(AREAS, json={"code": "HP-2", "name": "Khác"}, headers=admin)
    assert r.status_code == 409 and r.json()["error"]["details"]["inactive"] is True
    # Sửa mã trùng mã khác.
    other = _new_area(client, admin, "HP-3")
    r = client.patch(f"{AREAS}/{other['id']}", json={"code": "KV01"}, headers=admin)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_CODE"


@pytest.mark.parametrize("body", [{"code": "", "name": "X"}, {"code": "X"}, {"name": "X"}])
def test_area_create_validation(client: TestClient, login: Login, body: dict[str, Any]) -> None:
    r = client.post(AREAS, json=body, headers=login("admin"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_delete_area_with_active_beds_409(client: TestClient, login: Login, db: Session) -> None:
    r = client.delete(f"{AREAS}/1", headers=login("admin"))
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "AREA_IN_USE"
    assert sorted(err["details"]["bed_ids"]) == [1, 2, 3]
    assert "Khu hậu phẫu" in err["message"]
    assert _audits(db, "area") == []


def test_delete_area_only_deleted_beds_ok(client: TestClient, login: Login) -> None:
    """Ca âm tính: khu vực chỉ còn giường đã xóa thì xóa được; giường đã xóa vẫn hiện tên."""
    admin = login("admin")
    area = _new_area(client, admin)
    r = client.post(BEDS, json={"code": "Z01", "area_id": area["id"]}, headers=admin)
    assert r.status_code == 201, r.text
    bed = r.json()
    assert client.delete(f"{BEDS}/{bed['id']}", headers=admin).status_code == 200
    r = client.delete(f"{AREAS}/{area['id']}", headers=admin)
    assert r.status_code == 200, r.text
    r = client.get(f"{BEDS}/{bed['id']}", headers=admin)
    assert r.json()["area"]["name"] == "Hậu phẫu 2"
    # Khôi phục giường vào khu vực đã xóa: chặn để không có giường đang dùng ở khu vực đã xóa.
    r = client.post(f"{BEDS}/{bed['id']}/restore", headers=admin)
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_bed_cannot_use_deleted_area(client: TestClient, login: Login) -> None:
    admin = login("admin")
    area = _new_area(client, admin)
    client.delete(f"{AREAS}/{area['id']}", headers=admin)
    r = client.post(BEDS, json={"code": "Z02", "area_id": area["id"]}, headers=admin)
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_ERROR" and err["details"]["field"] == "area_id"
    r = client.patch(f"{BEDS}/1", json={"area_id": area["id"]}, headers=admin)
    assert r.status_code == 400 and r.json()["error"]["details"]["field"] == "area_id"
    r = client.post(BEDS, json={"code": "Z03", "area_id": 999}, headers=admin)
    assert r.status_code == 400 and r.json()["error"]["details"]["field"] == "area_id"


def test_bed_moves_to_other_area(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    area = _new_area(client, admin)
    r = client.patch(f"{BEDS}/1", json={"area_id": area["id"]}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["area"] == {"id": area["id"], "code": "HP-2", "name": "Hậu phẫu 2"}
    log = _audits(db, "bed", 1)[-1]
    assert log.action == "bed.update"
    assert log.before is not None and log.before["area_id"] == 1
    assert log.after is not None and log.after["area_id"] == area["id"]


def test_repeat_delete_restore_no_audit(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    area = _new_area(client, admin)
    url = f"{AREAS}/{area['id']}"
    assert client.post(f"{url}/restore", headers=admin).status_code == 200
    assert client.delete(url, headers=admin).status_code == 200
    assert client.delete(url, headers=admin).status_code == 200
    actions = [log.action for log in _audits(db, "area", area["id"])]
    assert actions == ["area.create", "area.delete"]


def test_area_not_found_404(client: TestClient, login: Login) -> None:
    admin = login("admin")
    assert client.patch(f"{AREAS}/999", json={"name": "X"}, headers=admin).status_code == 404
    assert client.delete(f"{AREAS}/999", headers=admin).status_code == 404


WRITES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("post", AREAS, {"code": "Z", "name": "Z"}),
    ("patch", f"{AREAS}/1", {"name": "Z"}),
    ("delete", f"{AREAS}/1", None),
    ("post", f"{AREAS}/1/restore", None),
    ("post", SHIFTS, {"name": "Ca thử", "start_time": "01:00", "end_time": "02:00"}),
    ("patch", f"{SHIFTS}/1", {"name": "Z"}),
    ("delete", f"{SHIFTS}/1", None),
    ("post", f"{SHIFTS}/1/restore", None),
]


@pytest.mark.parametrize("username", ["nurse", "charge", "doctor", "family"])
@pytest.mark.parametrize(("method", "path", "body"), WRITES)
def test_area_shift_writes_admin_only(
    client: TestClient,
    login: Login,
    db: Session,
    request: pytest.FixtureRequest,
    username: str,
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    headers = request.getfixturevalue("family") if username == "family" else login(username)
    kwargs: dict[str, Any] = {"headers": headers}
    if body is not None:
        kwargs["json"] = body
    r = client.request(method.upper(), path, **kwargs)
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "FORBIDDEN"
    assert _audits(db, "area") == [] and _audits(db, "shift") == []


@pytest.mark.parametrize("path", [AREAS, SHIFTS])
def test_family_cannot_read_areas_shifts(
    client: TestClient, family: dict[str, str], path: str
) -> None:
    r = client.get(path, headers=family)
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize("path", [AREAS, SHIFTS])
def test_areas_shifts_require_login(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401
