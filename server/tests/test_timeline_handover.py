"""F22 timeline (thứ tự), F24 bàn giao ca (đếm), F09 ca hiện tại, F21 số liệu thẻ giường."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from postcare.db.models import MonitoringSession, ShiftDefinition
from postcare.domain.shifts import current_shift, shift_window


@pytest.fixture
def old_session(open_session: dict[str, Any], db: Session) -> dict[str, Any]:
    """Lùi giờ bắt đầu phiên A01 về 3 giờ trước để gửi được sự kiện trong quá khứ."""
    s = db.get(MonitoringSession, open_session["id"])
    assert s is not None
    s.started_at = datetime.now(UTC) - timedelta(hours=3)
    db.commit()
    return open_session


def test_session_timeline_order(
    client: TestClient,
    login,
    old_session,
    post_event,
) -> None:
    nurse = login("nurse")
    t0 = datetime.now(UTC) - timedelta(minutes=10)
    # Gửi lệch thứ tự để chắc chắn API sắp theo thời gian, không theo thứ tự nhận.
    post_event("BED_EXIT", "HIGH", occurred_at=t0 + timedelta(seconds=22))
    post_event("SIT_UP", "INFO", occurred_at=t0)
    post_event("BED_EDGE", "MEDIUM", occurred_at=t0 + timedelta(seconds=14))
    exit_alert = next(
        a["id"]
        for a in client.get("/api/v1/alerts", headers=nurse).json()["items"]
        if a["event"]["code"] == "BED_EXIT"
    )
    client.post(f"/api/v1/alerts/{exit_alert}/acknowledge", headers=nurse)
    client.post(
        f"/api/v1/alerts/{exit_alert}/outcome",
        json={"outcome": "PATIENT_SAFE", "note": "ok"},
        headers=nurse,
    )
    client.post(f"/api/v1/alerts/{exit_alert}/resolve", headers=nurse)
    # Mốc rõ ràng sau thao tác resolve: đồng hồ Windows có độ phân giải ~15 ms nên
    # "now" của sự kiện có thể trùng hoặc sớm hơn thời điểm ghi audit.
    post_event("RETURN_TO_BED", "INFO", occurred_at=datetime.now(UTC) + timedelta(seconds=1))

    r = client.get(f"/api/v1/sessions/{old_session['id']}/timeline", headers=login("doctor"))
    assert r.status_code == 200
    items = r.json()["items"]
    summary = [(i["kind"], i["action"] or i["code"]) for i in items]
    assert summary == [
        ("event", "SIT_UP"),
        ("event", "BED_EDGE"),
        ("event", "BED_EXIT"),
        ("alert_action", "alert.acknowledge"),
        ("alert_action", "alert.outcome"),
        ("alert_action", "alert.resolve"),
        ("event", "RETURN_TO_BED"),
    ]
    times = [i["time"] for i in items]
    assert times == sorted(times)
    assert items[3]["actor"]["full_name"] == "Nguyễn Thị Hoa"
    assert items[4]["outcome"] == "PATIENT_SAFE"
    assert items[2]["alert"]["status"] == "RESOLVED"
    # alert.create không xuất hiện (đã có mục sự kiện).
    assert all(i["action"] != "alert.create" for i in items)

    # Lọc theo giường + khoảng thời gian.
    frm = (t0 + timedelta(seconds=10)).isoformat()
    to = (t0 + timedelta(seconds=30)).isoformat()
    r = client.get("/api/v1/timeline", params={"bed_id": 1, "from": frm, "to": to}, headers=nurse)
    assert [i["code"] for i in r.json()["items"]] == ["BED_EDGE", "BED_EXIT"]


def test_timeline_unknown_session_404(client: TestClient, login) -> None:
    assert client.get("/api/v1/sessions/999/timeline", headers=login("nurse")).status_code == 404


def test_handover_counts(
    client: TestClient,
    login,
    old_session,
    post_event,
) -> None:
    nurse = login("nurse")
    now = datetime.now(UTC)
    frm, to = now - timedelta(hours=1), now + timedelta(hours=1)
    # Ngoài khoảng (2 giờ trước): không đếm, nhưng cảnh báo vẫn tồn đọng.
    post_event("BED_EDGE", "MEDIUM", occurred_at=now - timedelta(hours=2))
    post_event("SIT_UP", "INFO", occurred_at=now - timedelta(minutes=30))
    post_event("BED_EDGE", "MEDIUM", occurred_at=now - timedelta(minutes=29))
    post_event("BED_EXIT", "HIGH", occurred_at=now - timedelta(minutes=28))
    post_event("POSTURE_CHANGE", "LOG", occurred_at=now - timedelta(minutes=20))
    post_event("OBSERVATION_LOST", "INFO", occurred_at=now - timedelta(minutes=10))
    items = client.get("/api/v1/alerts", headers=nurse).json()["items"]
    edge_in_range = next(
        a["id"]
        for a in items
        if a["event"]["code"] == "BED_EDGE"
        and datetime.fromisoformat(a["event"]["occurred_at"]) > frm
    )
    client.post(f"/api/v1/alerts/{edge_in_range}/acknowledge", headers=nurse)
    client.post(f"/api/v1/alerts/{edge_in_range}/resolve", headers=nurse)

    r = client.get(
        "/api/v1/handover", params={"from": frm.isoformat(), "to": to.isoformat()}, headers=nurse
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"from", "to", "beds", "outstanding_alerts"}
    a01 = next(b for b in body["beds"] if b["code"] == "A01")
    assert a01["event_counts"] == {
        "SIT_UP": 1,
        "BED_EDGE": 1,
        "BED_EXIT": 1,
        "POSTURE_CHANGE": 1,
        "OBSERVATION_LOST": 1,
    }
    assert a01["alerts_resolved"] == 1
    assert a01["alerts_unresolved"] == 1
    assert a01["state_change_count"] == 4  # OBSERVATION_LOST không phải đổi tư thế/vị trí
    a02 = next(b for b in body["beds"] if b["code"] == "A02")
    assert a02["event_counts"] == {} and a02["alerts_unresolved"] == 0
    outstanding = [(a["event"]["code"], a["event"]["priority"]) for a in body["outstanding_alerts"]]
    assert outstanding == [("BED_EXIT", "HIGH"), ("BED_EDGE", "MEDIUM")]  # ưu tiên cao trước

    r = client.get(
        "/api/v1/handover", params={"from": to.isoformat(), "to": frm.isoformat()}, headers=nurse
    )
    assert r.status_code == 400


def test_handover_by_shift(client: TestClient, login, db: Session) -> None:
    night = next(s for s in db.query(ShiftDefinition) if s.name == "Ca đêm")
    r = client.get(
        "/api/v1/handover",
        params={"shift_id": night.id, "date": "2026-10-12"},
        headers=login("nurse"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["from"].startswith("2026-10-12T15:00:00")  # 22:00 giờ VN
    assert body["to"].startswith("2026-10-12T23:00:00")  # 06:00 hôm sau giờ VN
    assert (
        client.get(
            "/api/v1/handover",
            params={"shift_id": 999, "date": "2026-10-12"},
            headers=login("nurse"),
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    ("hhmm", "expected"),
    [
        ("06:00", "Ca sáng"),
        ("13:59", "Ca sáng"),
        ("14:00", "Ca chiều"),
        ("21:59", "Ca chiều"),
        ("23:30", "Ca đêm"),
        ("05:59", "Ca đêm"),
    ],
)
def test_current_shift(hhmm: str, expected: str) -> None:
    shifts = [
        ShiftDefinition(id=1, name="Ca sáng", start_time=time(6), end_time=time(14)),
        ShiftDefinition(id=2, name="Ca chiều", start_time=time(14), end_time=time(22)),
        ShiftDefinition(id=3, name="Ca đêm", start_time=time(22), end_time=time(6)),
    ]
    h, m = map(int, hhmm.split(":"))
    vn = datetime(2026, 10, 12, h, m, tzinfo=UTC) - timedelta(hours=7)  # giờ VN = UTC+7
    shift = current_shift(vn, shifts)
    assert shift is not None and shift.name == expected
    assert current_shift(vn, []) is None


def test_shift_window_crosses_midnight() -> None:
    night = ShiftDefinition(id=3, name="Ca đêm", start_time=time(22), end_time=time(6))
    start, end = shift_window(night, date(2026, 10, 12))
    assert (end - start) == timedelta(hours=8)
    assert end.date() == date(2026, 10, 13)


def test_overview_alert_counts_and_max_priority(
    client: TestClient,
    login,
    open_session,
    post_event,
) -> None:
    nurse = login("nurse")
    post_event("BED_EDGE", "MEDIUM")
    post_event("BED_EXIT", "HIGH")
    aid = client.get("/api/v1/alerts?priority=HIGH", headers=nurse).json()["items"][0]["id"]
    client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=nurse)
    body = client.get("/api/v1/overview", headers=nurse).json()
    a01 = body["beds"][0]
    assert a01["code"] == "A01"
    assert a01["session"]["patient_code"] == "BN-001"
    assert a01["pending_alert_count"] == 1
    assert a01["acknowledged_alert_count"] == 1
    assert a01["max_open_priority"] == "HIGH"
    a02 = body["beds"][1]
    assert a02["session"] is None and a02["pending_alert_count"] == 0
    assert a02["max_open_priority"] is None
    assert body["current_shift"] is not None  # 3 ca phủ kín 24 giờ
