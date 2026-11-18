"""F22 AC1, AC3, R1–R6: timeline gộp sự kiện + thao tác cảnh báo + thao tác phiên.

Dữ liệu seed: giường A01/A02 (id 1–2) có camera 1–2; bệnh nhân BN-001 (id 1).
Đồng hồ Windows thô (~15 ms) nên các mốc audit được đặt lại bằng SQL khi test cần thứ tự chặt.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog, Camera, MonitoringSession, User
from postcare.domain.events import create_camera_event
from postcare.domain.security import hash_password
from postcare.schemas.enums import UserRole
from postcare.schemas.events import EventCode
from tests.conftest import PASSWORD

Login = Callable[[str], dict[str, str]]
SESSIONS = "/api/v1/sessions"


@pytest.fixture
def old_session(open_session: dict[str, Any], db: Session) -> dict[str, Any]:
    """Lùi giờ bắt đầu phiên A01 về 3 giờ trước để gửi được sự kiện trong quá khứ."""
    s = db.get(MonitoringSession, open_session["id"])
    assert s is not None
    s.started_at = datetime.now(UTC) - timedelta(hours=3)
    db.commit()
    return open_session


def _event(
    post_event: Callable[..., Any], code: str, priority: str, at: datetime, **kw: Any
) -> int:
    r = post_event(code, priority, occurred_at=at, **kw)
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def _alert_of(client: TestClient, headers: dict[str, str], event_id: int) -> int:
    items = client.get("/api/v1/alerts", headers=headers).json()["items"]
    return next(a["id"] for a in items if a["event"]["id"] == event_id)


def _set_audit_times(db: Session, actions: list[str], times: list[datetime]) -> None:
    """Đặt `created_at` cho các audit theo thứ tự ghi (id tăng dần) của từng action."""
    db.expire_all()
    logs = list(
        db.scalars(select(AuditLog).where(AuditLog.action.in_(actions)).order_by(AuditLog.id))
    )
    assert len(logs) == len(times), [log.action for log in logs]
    for log, t in zip(logs, times, strict=True):
        db.execute(update(AuditLog).where(AuditLog.id == log.id).values(created_at=t))
    db.commit()


def _summary(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(i["kind"], i["action"] or i["code"]) for i in items]


def _session_tl(client: TestClient, headers: dict[str, str], sid: int, **params: Any) -> Any:
    r = client.get(f"{SESSIONS}/{sid}/timeline", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------------------------ AC1


def test_session_timeline_merges_events_and_alert_actions_sorted(
    client: TestClient, login: Login, old_session: dict[str, Any], post_event, db: Session
) -> None:
    nurse = login("nurse")
    t0 = datetime.now(UTC) - timedelta(minutes=10)
    # Gửi lệch thứ tự: API phải sắp theo thời gian, không theo thứ tự nhận.
    exit_id = _event(post_event, "BED_EXIT", "HIGH", t0 + timedelta(seconds=22))
    _event(post_event, "SIT_UP", "INFO", t0)
    _event(post_event, "BED_EDGE", "MEDIUM", t0 + timedelta(seconds=14))
    alert = _alert_of(client, nurse, exit_id)
    client.post(f"/api/v1/alerts/{alert}/acknowledge", headers=nurse)
    client.post(f"/api/v1/alerts/{alert}/outcome", json={"outcome": "PATIENT_SAFE"}, headers=nurse)
    client.post(f"/api/v1/alerts/{alert}/resolve", headers=nurse)
    _set_audit_times(
        db,
        ["alert.acknowledge", "alert.outcome", "alert.resolve"],
        [t0 + timedelta(seconds=s) for s in (29, 60, 90)],
    )
    _event(post_event, "RETURN_TO_BED", "INFO", t0 + timedelta(seconds=40))

    body = _session_tl(client, nurse, old_session["id"])
    items = body["items"]
    assert _summary(items) == [
        ("event", "SIT_UP"),
        ("event", "BED_EDGE"),
        ("event", "BED_EXIT"),
        ("alert_action", "alert.acknowledge"),
        ("event", "RETURN_TO_BED"),
        ("alert_action", "alert.outcome"),
        ("alert_action", "alert.resolve"),
    ]
    assert body["total"] == 7
    assert [i["time"] for i in items] == sorted(i["time"] for i in items)
    ack = items[3]
    assert ack["actor"] == {"id": ack["actor"]["id"], "full_name": "Nguyễn Thị Hoa"}
    assert (ack["alert_id"], ack["event_code"]) == (alert, "BED_EXIT")
    assert items[5]["outcome"] == "PATIENT_SAFE"
    exit_item = items[2]
    assert exit_item["alert"]["status"] == "RESOLVED"
    assert exit_item["alert"]["outcome"] == "PATIENT_SAFE"
    assert exit_item["alert"]["acknowledged_by"]["full_name"] == "Nguyễn Thị Hoa"


def test_outcome_rewrite_shows_two_actions(
    client: TestClient, login: Login, old_session: dict[str, Any], post_event
) -> None:
    nurse = login("nurse")
    ev = _event(post_event, "BED_EXIT", "HIGH", datetime.now(UTC) - timedelta(minutes=5))
    alert = _alert_of(client, nurse, ev)
    client.post(f"/api/v1/alerts/{alert}/acknowledge", headers=nurse)
    for outcome, note in (("PATIENT_SAFE", None), ("CONFIRMED", "Theo dõi thêm")):
        r = client.post(
            f"/api/v1/alerts/{alert}/outcome",
            json={"outcome": outcome, "note": note},
            headers=nurse,
        )
        assert r.status_code == 200, r.text
    items = _session_tl(client, nurse, old_session["id"])["items"]
    outcomes = [(i["outcome"], i["note"]) for i in items if i["action"] == "alert.outcome"]
    assert outcomes == [("PATIENT_SAFE", None), ("CONFIRMED", "Theo dõi thêm")]


def test_alert_create_not_listed(
    client: TestClient, login: Login, old_session: dict[str, Any], post_event, db: Session
) -> None:
    nurse = login("nurse")
    _event(post_event, "BED_EXIT", "HIGH", datetime.now(UTC) - timedelta(minutes=5))
    db.expire_all()
    assert db.scalar(select(AuditLog).where(AuditLog.action == "alert.create")) is not None
    items = _session_tl(client, nurse, old_session["id"])["items"]
    assert _summary(items) == [("event", "BED_EXIT")]


def test_other_session_not_listed(
    client: TestClient, login: Login, old_session: dict[str, Any], post_event
) -> None:
    nurse = login("nurse")
    other = client.post(SESSIONS, json={"bed_id": 2, "patient_id": 2}, headers=nurse).json()
    _event(post_event, "SIT_UP", "INFO", datetime.now(UTC), camera_id=2)
    assert _session_tl(client, nurse, old_session["id"])["items"] == []
    assert [i["code"] for i in _session_tl(client, nurse, other["id"])["items"]] == ["SIT_UP"]


def test_same_time_ties_are_deterministic(
    client: TestClient, login: Login, old_session: dict[str, Any], post_event, db: Session
) -> None:
    """R3: trùng thời điểm → sự kiện trước, rồi theo id; gọi lại cho cùng kết quả."""
    nurse = login("nurse")
    t = datetime.now(UTC).replace(microsecond=123000) - timedelta(minutes=5)
    first = _event(post_event, "BED_EXIT", "HIGH", t)
    second = _event(post_event, "POSTURE_CHANGE", "LOG", t)
    alert = _alert_of(client, nurse, first)
    client.post(f"/api/v1/alerts/{alert}/acknowledge", headers=nurse)
    client.post(f"/api/v1/alerts/{alert}/outcome", json={"outcome": "PATIENT_SAFE"}, headers=nurse)
    _set_audit_times(db, ["alert.acknowledge", "alert.outcome"], [t, t])

    runs = [_session_tl(client, nurse, old_session["id"])["items"] for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert [(i["kind"], i["event_id"], i["action"]) for i in runs[0]] == [
        ("event", first, None),
        ("event", second, None),
        ("alert_action", first, "alert.acknowledge"),
        ("alert_action", first, "alert.outcome"),
    ]
    # Phân trang cắt đúng giữa các mục trùng giờ.
    paged = [
        i["action"] or i["code"]
        for off in range(4)
        for i in _session_tl(client, nurse, old_session["id"], limit=1, offset=off)["items"]
    ]
    assert paged == ["BED_EXIT", "POSTURE_CHANGE", "alert.acknowledge", "alert.outcome"]


# ------------------------------------------------------------------------------------ AC3


def test_bed_timeline_filters_by_time_range(
    client: TestClient, login: Login, old_session: dict[str, Any], post_event, db: Session
) -> None:
    nurse = login("nurse")
    t0 = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=1)
    _event(post_event, "SIT_UP", "INFO", t0 - timedelta(seconds=1))  # trước from → loại
    _event(post_event, "BED_EDGE", "MEDIUM", t0)  # đúng from → giữ
    _event(post_event, "BED_EXIT", "HIGH", t0 + timedelta(seconds=30))
    _event(post_event, "RETURN_TO_BED", "INFO", t0 + timedelta(seconds=60))  # đúng to → loại
    other = client.post(SESSIONS, json={"bed_id": 2, "patient_id": 2}, headers=nurse).json()
    s2 = db.get(MonitoringSession, other["id"])
    assert s2 is not None
    s2.started_at = t0 - timedelta(hours=1)
    db.commit()
    _event(post_event, "SIT_UP", "INFO", t0 + timedelta(seconds=10), camera_id=2)  # giường khác
    params = {
        "bed_id": 1,
        "from": t0.isoformat(),
        "to": (t0 + timedelta(seconds=60)).isoformat(),
    }
    r = client.get("/api/v1/timeline", params=params, headers=nurse)
    assert r.status_code == 200, r.text
    assert [i["code"] for i in r.json()["items"]] == ["BED_EDGE", "BED_EXIT"]
    assert all(i["bed_code"] == "A01" for i in r.json()["items"])
    bad = {**params, "from": params["to"], "to": params["from"]}
    assert client.get("/api/v1/timeline", params=bad, headers=nurse).status_code == 400
    assert client.get("/api/v1/timeline", headers=nurse).status_code == 422  # thiếu bed_id


def test_bed_timeline_defaults_to_last_24h(
    client: TestClient, login: Login, open_session: dict[str, Any], post_event, db: Session
) -> None:
    s = db.get(MonitoringSession, open_session["id"])
    assert s is not None
    s.started_at = datetime.now(UTC) - timedelta(hours=30)
    db.commit()
    _event(post_event, "SIT_UP", "INFO", datetime.now(UTC) - timedelta(hours=25))
    _event(post_event, "BED_EDGE", "MEDIUM", datetime.now(UTC) - timedelta(hours=23))
    r = client.get("/api/v1/timeline", params={"bed_id": 1}, headers=login("nurse"))
    assert [i["code"] for i in r.json()["items"]] == ["BED_EDGE"]


def test_filter_by_priority_keeps_related_actions(
    client: TestClient, login: Login, old_session: dict[str, Any], post_event, db: Session
) -> None:
    nurse = login("nurse")
    t0 = datetime.now(UTC) - timedelta(minutes=10)
    edge = _event(post_event, "BED_EDGE", "MEDIUM", t0)
    exit_ = _event(post_event, "BED_EXIT", "HIGH", t0 + timedelta(seconds=5))
    _event(post_event, "SIT_UP", "INFO", t0 + timedelta(seconds=1))
    for ev in (edge, exit_):
        client.post(f"/api/v1/alerts/{_alert_of(client, nurse, ev)}/acknowledge", headers=nurse)
    _set_audit_times(
        db, ["alert.acknowledge"], [t0 + timedelta(seconds=20), t0 + timedelta(seconds=30)]
    )

    items = _session_tl(client, nurse, old_session["id"], priority="HIGH")["items"]
    assert [(i["kind"], i["event_id"]) for i in items] == [
        ("event", exit_),
        ("alert_action", exit_),
    ]
    both = _session_tl(client, nurse, old_session["id"], priority=["HIGH", "MEDIUM"])
    assert [i["priority"] for i in both["items"]] == ["MEDIUM", "HIGH", "MEDIUM", "HIGH"]
    r = client.get(
        "/api/v1/timeline",
        params={"bed_id": 1, "priority": "INFO", "from": (t0 - timedelta(minutes=1)).isoformat()},
        headers=nurse,
    )
    assert [i["code"] for i in r.json()["items"]] == ["SIT_UP"]


def test_bed_timeline_includes_camera_events_without_session(
    client: TestClient, login: Login, db: Session
) -> None:
    """Không có phiên mở: sự kiện camera vẫn gắn giường (session_id null) và hiện theo giường."""
    nurse = login("nurse")
    camera = db.get(Camera, 1)
    assert camera is not None
    created = create_camera_event(
        db,
        camera,
        code=EventCode.CAMERA_OFFLINE,
        occurred_at=datetime.now(UTC) - timedelta(minutes=2),
        reason="test",
    )
    assert created is not None and created[0].session_id is None
    db.commit()
    r = client.get("/api/v1/timeline", params={"bed_id": 1}, headers=nurse)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [(i["code"], i["session_id"]) for i in items] == [("CAMERA_OFFLINE", None)]


def test_pagination(
    client: TestClient, login: Login, old_session: dict[str, Any], post_event
) -> None:
    nurse = login("nurse")
    t0 = datetime.now(UTC) - timedelta(minutes=30)
    ids = [_event(post_event, "POSTURE_CHANGE", "LOG", t0 + timedelta(seconds=s)) for s in range(5)]
    p1 = _session_tl(client, nurse, old_session["id"], limit=2, offset=0)
    p3 = _session_tl(client, nurse, old_session["id"], limit=2, offset=4)
    assert (p1["total"], [i["event_id"] for i in p1["items"]]) == (5, ids[:2])
    assert [i["event_id"] for i in p3["items"]] == ids[4:]
    too_big = client.get(f"{SESSIONS}/{old_session['id']}/timeline?limit=201", headers=nurse)
    assert too_big.status_code == 422


# ------------------------------------------------------- chuỗi phiên, tạm dừng (F04 R16, R19)


def test_pause_resume_and_transfer_entries(
    client: TestClient, login: Login, post_event, db: Session
) -> None:
    nurse, charge = login("nurse"), login("charge")
    old = client.post(SESSIONS, json={"bed_id": 1, "patient_id": 1}, headers=nurse).json()
    t0 = datetime.now(UTC)
    sit = _event(post_event, "SIT_UP", "INFO", t0)
    assert client.post(
        f"{SESSIONS}/{old['id']}/pause", json={"reason": "Vệ sinh"}, headers=nurse
    ).is_success
    assert client.post(f"{SESSIONS}/{old['id']}/resume", headers=charge).is_success
    r = client.post(
        f"{SESSIONS}/{old['id']}/transfer",
        json={"target_bed_id": 2, "reason": "Đổi phòng"},
        headers=charge,
    )
    assert r.status_code == 201, r.text
    new = r.json()
    _set_audit_times(
        db,
        ["session.pause", "session.resume", "session.transfer"],
        [t0 + timedelta(seconds=s) for s in (1, 2, 3)],
    )
    edge = _event(post_event, "BED_EDGE", "MEDIUM", t0 + timedelta(seconds=10), camera_id=2)

    old_items = _session_tl(client, nurse, old["id"])["items"]
    assert _summary(old_items) == [
        ("event", "SIT_UP"),
        ("session_action", "session.pause"),
        ("session_action", "session.resume"),
        ("session_action", "session.transfer"),
    ]
    pause, resume, transfer = old_items[1:]
    assert (pause["actor"]["full_name"], pause["note"]) == ("Nguyễn Thị Hoa", "Vệ sinh")
    assert resume["actor"]["full_name"] == "Trần Văn Minh"
    assert (transfer["from_bed_code"], transfer["bed_code"], transfer["note"]) == (
        "A01",
        "A02",
        "Đổi phòng",
    )
    assert (transfer["session_id"], pause["session_id"]) == (new["id"], old["id"])
    assert all(i["code"] is None and i["event_id"] is None for i in old_items[1:])

    # Không xem chuỗi: phiên mới chỉ có mục chuyển giường và sự kiện của chính nó.
    new_items = _session_tl(client, nurse, new["id"])["items"]
    assert [(i["kind"], i["event_id"]) for i in new_items] == [
        ("session_action", None),
        ("event", edge),
    ]
    # Theo giường: mục chuyển giường hiện ở cả giường cũ lẫn giường mới.
    frm = (t0 - timedelta(minutes=1)).isoformat()
    for bed_id in (1, 2):
        r = client.get("/api/v1/timeline", params={"bed_id": bed_id, "from": frm}, headers=nurse)
        assert "session.transfer" in [i["action"] for i in r.json()["items"]], bed_id
    # Lọc mức ưu tiên vẫn giữ mục thao tác phiên (không có mức ưu tiên).
    hi = _session_tl(client, nurse, old["id"], priority="HIGH")["items"]
    assert [i["action"] for i in hi] == ["session.pause", "session.resume", "session.transfer"]
    assert sit in [i["event_id"] for i in old_items]


def test_session_timeline_chain_after_transfer(
    client: TestClient, login: Login, post_event, db: Session
) -> None:
    nurse = login("nurse")
    first = client.post(SESSIONS, json={"bed_id": 1, "patient_id": 1}, headers=nurse).json()
    t0 = datetime.now(UTC)
    sit = _event(post_event, "SIT_UP", "INFO", t0)
    second = client.post(
        f"{SESSIONS}/{first['id']}/transfer",
        json={"target_bed_id": 2, "reason": "Đổi phòng"},
        headers=nurse,
    ).json()
    _set_audit_times(db, ["session.transfer"], [t0 + timedelta(seconds=1)])
    edge = _event(post_event, "BED_EDGE", "MEDIUM", t0 + timedelta(seconds=5), camera_id=2)
    # Phiên không liên quan ở giường A01 sau khi chuyển: không thuộc chuỗi.
    client.post(SESSIONS, json={"bed_id": 1, "patient_id": 2}, headers=nurse)
    _event(post_event, "POSTURE_CHANGE", "LOG", t0 + timedelta(seconds=6))

    expected = [("event", sit), ("session_action", None), ("event", edge)]
    for sid in (first["id"], second["id"]):
        items = _session_tl(client, nurse, sid, chain="true")["items"]
        assert [(i["kind"], i["event_id"]) for i in items] == expected, sid
        assert [i["session_id"] for i in items] == [first["id"], second["id"], second["id"]]
        assert [i["bed_code"] for i in items] == ["A01", "A02", "A02"]


# ------------------------------------------------------------------------------------ R6


def test_doctor_can_read_timeline(
    client: TestClient, login: Login, old_session: dict[str, Any], post_event
) -> None:
    doctor = login("doctor")
    _event(post_event, "SIT_UP", "INFO", datetime.now(UTC) - timedelta(minutes=1))
    assert len(_session_tl(client, doctor, old_session["id"])["items"]) == 1
    r = client.get("/api/v1/timeline", params={"bed_id": 1}, headers=doctor)
    assert r.status_code == 200


def test_family_forbidden_timeline(
    client: TestClient, login: Login, old_session: dict[str, Any], db: Session
) -> None:
    db.add(
        User(
            username="family",
            full_name="Người nhà thử nghiệm",
            password_hash=hash_password(PASSWORD),
            role=UserRole.FAMILY,
        )
    )
    db.commit()
    family = login("family")
    for url in (f"{SESSIONS}/{old_session['id']}/timeline", "/api/v1/timeline?bed_id=1"):
        r = client.get(url, headers=family)
        assert r.status_code == 403, url
        assert r.json()["error"]["code"] == "FORBIDDEN"


def test_unknown_session_404(client: TestClient, login: Login) -> None:
    r = client.get(f"{SESSIONS}/999/timeline", params={"chain": "true"}, headers=login("nurse"))
    assert r.status_code == 404
