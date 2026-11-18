"""F24 AC1, R1, R2, R6: `GET /api/v1/handover`, `GET /api/v1/shifts` qua HTTP.

Dữ liệu seed: giường A01/A02/A03 (id 1–3), camera 1–3, 3 ca mặc định. FAMILY → 403 đã có ở
`tests/api/test_family_role_default_deny.py`; ca đã xóa ở `tests/api/test_shifts_admin.py`.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import ShiftDefinition
from postcare.schemas.enums import AlertOutcome, Priority
from postcare.schemas.events import EventCode
from tests.handover_data import add_event, z

Login = Callable[[str], dict[str, str]]
URL = "/api/v1/handover"


def _shift_id(db: Session, name: str) -> int:
    return db.scalars(select(ShiftDefinition.id).where(ShiftDefinition.name == name)).one()


def _get(client: TestClient, headers: dict[str, str], **params: Any) -> Any:
    r = client.get(URL, params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _bed(body: Any, code: str) -> Any:
    return next(b for b in body["beds"] if b["code"] == code)


def test_shifts_list(client: TestClient, login: Login) -> None:
    r = client.get("/api/v1/shifts", headers=login("nurse"))
    assert r.status_code == 200
    assert [(s["name"], s["start_time"], s["end_time"]) for s in r.json()] == [
        ("Ca sáng", "06:00:00", "14:00:00"),
        ("Ca chiều", "14:00:00", "22:00:00"),
        ("Ca đêm", "22:00:00", "06:00:00"),
    ]


def test_handover_by_shift_and_date(client: TestClient, login: Login, db: Session) -> None:
    add_event(db, EventCode.SIT_UP, z(16))  # 23:00 VN 12/10
    add_event(
        db,
        EventCode.BED_EXIT,
        z(20),  # 03:00 VN 13/10
        priority=Priority.HIGH,
        alert=True,
        resolved_at=z(20, 5),
        outcome=AlertOutcome.CONFIRMED,
    )
    add_event(db, EventCode.BED_EDGE, z(22), bed_id=2, priority=Priority.MEDIUM, alert=True)
    add_event(db, EventCode.SIT_UP, z(23))  # 06:00 VN 13/10: ca sáng
    body = _get(client, login("charge"), shift_id=_shift_id(db, "Ca đêm"), date="2026-10-12")
    assert body["from"].startswith("2026-10-12T15:00:00")
    assert body["to"].startswith("2026-10-12T23:00:00")
    assert body["shift"]["name"] == "Ca đêm"
    a01, a02 = _bed(body, "A01"), _bed(body, "A02")
    assert a01["event_counts"] == {"BED_EXIT": 1, "SIT_UP": 1}
    assert (a01["alerts_resolved"], a01["alerts_unresolved"], a01["state_change_count"]) == (
        1,
        0,
        2,
    )
    assert a01["outcome_counts"] == {"CONFIRMED": 1}
    assert (a02["alerts_resolved"], a02["alerts_unresolved"]) == (0, 1)
    assert [(a["bed"]["code"], a["event"]["code"]) for a in body["outstanding_alerts"]] == [
        ("A02", "BED_EDGE")
    ]


def test_handover_by_custom_range(client: TestClient, login: Login, db: Session) -> None:
    add_event(db, EventCode.SIT_UP, z(10))
    add_event(db, EventCode.SIT_UP, z(12, 30))  # đúng `to`: loại
    body = _get(
        client,
        login("nurse"),
        **{"from": "2026-10-12T17:00:00+07:00", "to": "2026-10-12T19:30:00+07:00"},
    )
    assert body["shift"] is None
    assert datetime.fromisoformat(body["from"]) == z(10)
    assert datetime.fromisoformat(body["to"]) == z(12, 30)
    assert _bed(body, "A01")["event_counts"] == {"SIT_UP": 1}


def test_beds_without_events_show_zero(client: TestClient, login: Login) -> None:
    body = _get(client, login("nurse"), **{"from": z(10).isoformat(), "to": z(11).isoformat()})
    assert [b["code"] for b in body["beds"]] == ["A01", "A02", "A03"]
    for b in body["beds"]:
        assert b["event_counts"] == {} and b["outcome_counts"] == {}
        assert (b["alerts_resolved"], b["alerts_unresolved"], b["state_change_count"]) == (0, 0, 0)
        assert b["is_active"] is True
    assert body["outstanding_alerts"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"from": "2026-10-12T12:00:00Z", "to": "2026-10-12T10:00:00Z"},  # from > to
        {"from": "2026-10-12T10:00:00Z", "to": "2026-10-12T10:00:00Z"},  # from = to
        {"from": "2026-10-12T17:00:00+07:00", "to": "2026-10-12T10:00:00Z"},  # bằng nhau sau UTC
        {"from": "2026-10-12T10:00:00Z"},  # thiếu `to`
        {},  # thiếu cả ca lẫn khoảng
        {"shift_id": 1},  # thiếu `date`
    ],
)
def test_invalid_range_400(client: TestClient, login: Login, params: dict[str, Any]) -> None:
    r = client.get(URL, params=params, headers=login("nurse"))
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_naive_datetime_rejected(client: TestClient, login: Login) -> None:
    r = client.get(
        URL,
        params={"from": "2026-10-12T10:00:00", "to": "2026-10-12T12:00:00"},
        headers=login("nurse"),
    )
    assert r.status_code == 422


def test_unknown_shift_404(client: TestClient, login: Login) -> None:
    r = client.get(URL, params={"shift_id": 999, "date": "2026-10-12"}, headers=login("nurse"))
    assert r.status_code == 404


@pytest.mark.parametrize("username", ["nurse", "charge", "doctor", "admin"])
def test_staff_roles_can_read_handover(client: TestClient, login: Login, username: str) -> None:
    headers = login(username)
    assert client.get("/api/v1/shifts", headers=headers).status_code == 200
    r = client.get(URL, params={"shift_id": 1, "date": "2026-10-12"}, headers=headers)
    assert r.status_code == 200, r.text


def test_unauthenticated_401(client: TestClient) -> None:
    assert client.get(URL, params={"shift_id": 1, "date": "2026-10-12"}).status_code == 401


def test_transferred_patient_events_stay_on_old_bed(
    client: TestClient, login: Login, post_event: Callable[..., Any]
) -> None:
    """F04: sự kiện tính theo giường lúc xảy ra (`events.bed_id`), không theo giường hiện tại."""
    nurse = login("nurse")
    r = client.post("/api/v1/sessions", json={"bed_id": 1, "patient_id": 1}, headers=nurse)
    assert r.status_code == 201, r.text
    old = r.json()
    start = datetime.now(UTC)
    assert post_event("SIT_UP", "INFO", camera_id=1).status_code == 201
    r = client.post(
        f"/api/v1/sessions/{old['id']}/transfer",
        json={"target_bed_id": 2, "reason": "Đổi phòng"},
        headers=nurse,
    )
    assert r.status_code == 201, r.text
    assert post_event("STAND_UP", "INFO", camera_id=2).status_code == 201
    body = _get(
        client,
        nurse,
        **{
            "from": (start - timedelta(minutes=1)).isoformat(),
            "to": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
        },
    )
    assert _bed(body, "A01")["event_counts"] == {"SIT_UP": 1}
    assert _bed(body, "A02")["event_counts"] == {"STAND_UP": 1}
