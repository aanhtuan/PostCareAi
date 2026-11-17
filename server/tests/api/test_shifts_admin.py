"""F37 AC3, AC4: quản lý ca trực (CRUD, không chồng giờ, xóa mềm, khôi phục, audit, bàn giao).

Dữ liệu nền: Ca sáng 06–14 (id 1), Ca chiều 14–22 (id 2), Ca đêm 22–06 (id 3), phủ kín 24 giờ.
"""

from collections.abc import Callable
from datetime import UTC, datetime, time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog, ShiftDefinition
from postcare.domain.shifts import DISPLAY_TZ, current_shift, list_shifts

Login = Callable[[str], dict[str, str]]

SHIFTS = "/api/v1/shifts"
MORNING, AFTERNOON, NIGHT = 1, 2, 3


def _audits(db: Session, entity_id: int | None = None) -> list[AuditLog]:
    db.expire_all()
    q = select(AuditLog).where(AuditLog.entity_type == "shift")
    if entity_id is not None:
        q = q.where(AuditLog.entity_id == entity_id)
    return list(db.scalars(q.order_by(AuditLog.id)))


def _shift(name: str, start: str, end: str) -> dict[str, str]:
    return {"name": name, "start_time": start, "end_time": end}


def _delete(client: TestClient, admin: dict[str, str], *ids: int) -> None:
    for shift_id in ids:
        r = client.delete(f"{SHIFTS}/{shift_id}", headers=admin)
        assert r.status_code == 200, r.text


def test_list_shifts_sorted_with_status(client: TestClient, login: Login) -> None:
    r = client.get(SHIFTS, headers=login("nurse"))
    assert r.status_code == 200
    body = r.json()
    assert [s["name"] for s in body] == ["Ca sáng", "Ca chiều", "Ca đêm"]
    assert body[0]["start_time"] == "06:00:00" and body[2]["end_time"] == "06:00:00"
    assert all(s["is_active"] for s in body)


def test_admin_crud_shifts(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    _delete(client, admin, MORNING)
    r = client.post(SHIFTS, json=_shift(" Ca sớm ", "06:00", "10:00"), headers=admin)
    assert r.status_code == 201, r.text
    shift = r.json()
    assert shift["name"] == "Ca sớm" and shift["start_time"] == "06:00:00"
    url = f"{SHIFTS}/{shift['id']}"

    r = client.patch(url, json={"end_time": "14:00", "name": "Ca sáng mới"}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["end_time"] == "14:00:00" and r.json()["name"] == "Ca sáng mới"

    r = client.delete(url, headers=admin)
    assert r.status_code == 200 and r.json()["is_active"] is False
    r = client.get(SHIFTS, headers=admin)
    assert [s["name"] for s in r.json()] == ["Ca chiều", "Ca đêm"]
    r = client.get(SHIFTS, params={"include_inactive": True}, headers=admin)
    assert len(r.json()) == 4

    r = client.post(f"{url}/restore", headers=admin)
    assert r.status_code == 200 and r.json()["is_active"] is True

    logs = _audits(db, shift["id"])
    assert [log.action for log in logs] == [
        "shift.create",
        "shift.update",
        "shift.delete",
        "shift.restore",
    ]
    assert logs[1].before is not None and logs[1].before["end_time"] == "10:00"
    assert logs[1].after is not None and logs[1].after["end_time"] == "14:00"


def test_area_shift_writes_audited(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    _delete(client, admin, NIGHT)
    r = client.post(f"{SHIFTS}/{NIGHT}/restore", headers=admin)
    assert r.status_code == 200
    logs = _audits(db, NIGHT)
    assert [log.action for log in logs] == ["shift.delete", "shift.restore"]
    assert logs[0].before is not None and logs[0].before["is_active"] is True
    assert logs[0].after is not None and logs[0].after["is_active"] is False
    r = client.post("/api/v1/areas", json={"code": "HP-9", "name": "Khu 9"}, headers=admin)
    assert r.status_code == 201
    db.expire_all()
    area_logs = db.scalars(select(AuditLog).where(AuditLog.entity_type == "area")).all()
    assert [log.action for log in area_logs] == ["area.create"]


def test_shift_overlap_409(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    r = client.post(SHIFTS, json=_shift("Ca giữa", "12:00", "16:00"), headers=admin)
    assert r.status_code == 409, r.text
    err = r.json()["error"]
    assert err["code"] == "SHIFT_OVERLAP"
    assert sorted(err["details"]["conflicting_shift_ids"]) == [MORNING, AFTERNOON]
    assert "Ca sáng" in err["message"]
    # Sửa giờ ca làm chồng giờ ca khác.
    r = client.patch(f"{SHIFTS}/{MORNING}", json={"end_time": "15:00"}, headers=admin)
    assert r.status_code == 409
    assert r.json()["error"]["details"]["conflicting_shift_ids"] == [AFTERNOON]
    assert _audits(db) == []


def test_overnight_shift_overlap_detected(client: TestClient, login: Login) -> None:
    admin = login("admin")
    _delete(client, admin, MORNING)
    # Ca qua đêm mới 04:00–07:00 chồng phần sau nửa đêm của Ca đêm (22:00–06:00).
    r = client.post(SHIFTS, json=_shift("Ca rạng sáng", "04:00", "07:00"), headers=admin)
    assert r.status_code == 409
    assert r.json()["error"]["details"]["conflicting_shift_ids"] == [NIGHT]
    # Ca qua đêm mới 21:00–01:00 chồng Ca chiều và Ca đêm.
    r = client.post(SHIFTS, json=_shift("Ca muộn", "21:00", "01:00"), headers=admin)
    assert r.status_code == 409
    assert sorted(r.json()["error"]["details"]["conflicting_shift_ids"]) == [AFTERNOON, NIGHT]


def test_adjacent_shifts_do_not_overlap(client: TestClient, login: Login) -> None:
    admin = login("admin")
    _delete(client, admin, AFTERNOON, NIGHT)
    r = client.post(SHIFTS, json=_shift("Ca chiều 2", "14:00", "22:00"), headers=admin)
    assert r.status_code == 201, r.text
    r = client.post(SHIFTS, json=_shift("Ca đêm 2", "22:00", "06:00"), headers=admin)
    assert r.status_code == 201, r.text
    # Sửa ca mà không đổi giờ không bị coi là chồng với chính nó.
    r = client.patch(f"{SHIFTS}/{MORNING}", json={"start_time": "06:00"}, headers=admin)
    assert r.status_code == 200, r.text


def test_deleted_shift_does_not_block_new(client: TestClient, login: Login) -> None:
    admin = login("admin")
    _delete(client, admin, MORNING)
    r = client.post(SHIFTS, json=_shift("Ca sáng", "07:00", "13:00"), headers=admin)
    assert r.status_code == 201, r.text  # tên trùng ca đã xóa: được


def test_restore_overlapping_shift_409(client: TestClient, login: Login) -> None:
    admin = login("admin")
    _delete(client, admin, MORNING)
    r = client.post(SHIFTS, json=_shift("Ca sớm", "05:00", "06:00"), headers=admin)
    assert r.status_code == 409  # 05:00–06:00 nằm trong Ca đêm 22:00–06:00
    r = client.post(SHIFTS, json=_shift("Ca sớm", "07:00", "13:00"), headers=admin)
    assert r.status_code == 201
    new_id = r.json()["id"]
    r = client.post(f"{SHIFTS}/{MORNING}/restore", headers=admin)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "SHIFT_OVERLAP" and err["details"]["conflicting_shift_ids"] == [new_id]


def test_restore_duplicate_name_409(client: TestClient, login: Login) -> None:
    admin = login("admin")
    _delete(client, admin, MORNING)
    r = client.post(SHIFTS, json=_shift("Ca sáng", "07:00", "08:00"), headers=admin)
    assert r.status_code == 201
    _delete(client, admin, r.json()["id"])
    r = client.post(SHIFTS, json=_shift("Ca sáng", "08:00", "09:00"), headers=admin)
    assert r.status_code == 201
    r = client.post(f"{SHIFTS}/{MORNING}/restore", headers=admin)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_CODE"


def test_duplicate_active_shift_name_409(client: TestClient, login: Login) -> None:
    admin = login("admin")
    _delete(client, admin, NIGHT)
    r = client.post(SHIFTS, json=_shift(" Ca sáng", "23:00", "01:00"), headers=admin)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "DUPLICATE_CODE" and err["details"]["field"] == "name"
    r = client.patch(f"{SHIFTS}/{AFTERNOON}", json={"name": "Ca sáng"}, headers=admin)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_CODE"


def test_shift_equal_start_end_400(client: TestClient, login: Login) -> None:
    admin = login("admin")
    _delete(client, admin, MORNING)
    r = client.post(SHIFTS, json=_shift("Ca lỗi", "08:00", "08:00"), headers=admin)
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_ERROR" and err["details"]["field"] == "end_time"
    r = client.patch(f"{SHIFTS}/{AFTERNOON}", json={"end_time": "14:00"}, headers=admin)
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "body",
    [
        _shift("Ca", "08:00:30", "09:00"),
        _shift("Ca", "08:00", "09:00:00.5"),
        _shift("Ca", "25:00", "09:00"),
        _shift("", "08:00", "09:00"),
        {"name": "Ca", "start_time": "08:00"},
    ],
)
def test_shift_time_validation(client: TestClient, login: Login, body: dict[str, Any]) -> None:
    admin = login("admin")
    _delete(client, admin, MORNING)
    r = client.post(SHIFTS, json=body, headers=admin)
    assert r.status_code in (400, 422), r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_repeat_shift_delete_no_audit(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    assert client.post(f"{SHIFTS}/{MORNING}/restore", headers=admin).status_code == 200
    _delete(client, admin, MORNING, MORNING)
    assert [log.action for log in _audits(db, MORNING)] == ["shift.delete"]


def test_shift_not_found_404(client: TestClient, login: Login) -> None:
    admin = login("admin")
    assert client.delete(f"{SHIFTS}/999", headers=admin).status_code == 404
    assert client.patch(f"{SHIFTS}/999", json={"name": "x"}, headers=admin).status_code == 404


def test_handover_works_for_deleted_shift(client: TestClient, login: Login) -> None:
    admin = login("admin")
    _delete(client, admin, NIGHT)
    r = client.get(
        "/api/v1/handover", params={"shift_id": NIGHT, "date": "2026-10-12"}, headers=admin
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["shift"]["id"] == NIGHT and body["shift"]["is_active"] is False


def test_current_shift_ignores_deleted(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    _delete(client, admin, MORNING)
    db.expire_all()
    active = list_shifts(db)
    assert [s.name for s in active] == ["Ca chiều", "Ca đêm"]
    assert len(list_shifts(db, include_inactive=True)) == 3
    morning = datetime.combine(datetime(2026, 10, 12).date(), time(8, 0), DISPLAY_TZ)
    assert current_shift(morning.astimezone(UTC), active) is None
    evening = datetime.combine(datetime(2026, 10, 12).date(), time(15, 0), DISPLAY_TZ)
    shift = current_shift(evening, active)
    assert isinstance(shift, ShiftDefinition) and shift.name == "Ca chiều"
