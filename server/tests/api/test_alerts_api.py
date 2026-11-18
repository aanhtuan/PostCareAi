"""F19 AC1–AC5, R1–R11: API vòng đời cảnh báo (ADR-0007; QA#16, QA#18).

Bổ sung cho `tests/test_alerts.py`: ma trận trạng thái × thao tác, audit `before`/`after`,
publish sau commit, phân quyền DOCTOR/không token, validation, lọc danh sách.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from postcare.db.models import Alert, AuditLog, User
from postcare.domain.notifications import InMemoryPublisher

Login = Callable[[str], dict[str, str]]
ACTIONS = ("acknowledge", "outcome", "resolve")


def _new_alert(client: TestClient, login: Login, post_event: Callable[..., Any], **kw: Any) -> int:
    r = post_event(kw.pop("code", "BED_EXIT"), kw.pop("priority", "HIGH"), **kw)
    assert r.status_code == 201, r.text
    items = client.get("/api/v1/alerts", headers=login("nurse")).json()["items"]
    return max(i["id"] for i in items)


def _call(client: TestClient, aid: int, action: str, headers: dict[str, str], **body: Any) -> Any:
    path = f"/api/v1/alerts/{aid}/{action}"
    if action == "outcome":
        return client.post(path, json={"outcome": "CONFIRMED", **body}, headers=headers)
    if action == "resolve":
        return client.post(path, json=body, headers=headers)
    return client.post(path, headers=headers)


def _to_state(client: TestClient, aid: int, state: str, headers: dict[str, str]) -> None:
    if state in ("ACKNOWLEDGED", "RESOLVED"):
        assert _call(client, aid, "acknowledge", headers).status_code == 200
    if state == "RESOLVED":
        assert _call(client, aid, "resolve", headers).status_code == 200


def _audits(db: Session, aid: int) -> list[AuditLog]:
    db.expire_all()
    return list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == "alert", AuditLog.entity_id == aid)
            .order_by(AuditLog.id)
        )
    )


def _uid(db: Session, username: str) -> int:
    uid = db.scalar(select(User.id).where(User.username == username))
    assert uid is not None
    return uid


# R1 / AC1: ma trận trạng thái × thao tác. None = được phép (200).
MATRIX: list[tuple[str, str, str | None]] = [
    ("PENDING", "acknowledge", None),
    ("PENDING", "outcome", "INVALID_ALERT_TRANSITION"),
    ("PENDING", "resolve", "INVALID_ALERT_TRANSITION"),
    ("ACKNOWLEDGED", "acknowledge", "ALERT_ALREADY_ACKNOWLEDGED"),
    ("ACKNOWLEDGED", "outcome", None),
    ("ACKNOWLEDGED", "resolve", None),
    ("RESOLVED", "acknowledge", "INVALID_ALERT_TRANSITION"),
    ("RESOLVED", "outcome", "INVALID_ALERT_TRANSITION"),
    ("RESOLVED", "resolve", "INVALID_ALERT_TRANSITION"),
]


@pytest.mark.parametrize(("state", "action", "error"), MATRIX)
def test_transition_matrix(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    post_event: Callable[..., Any],
    db: Session,
    publisher: InMemoryPublisher,
    state: str,
    action: str,
    error: str | None,
) -> None:
    nurse, charge = login("nurse"), login("charge")
    aid = _new_alert(client, login, post_event)
    _to_state(client, aid, state, nurse)
    audits_before = len(_audits(db, aid))
    publisher.messages.clear()

    r = _call(client, aid, action, charge)

    if error is None:
        assert r.status_code == 200, r.text
        assert len(_audits(db, aid)) == audits_before + 1
        assert publisher.types() == ["alert.updated"]
    else:
        assert r.status_code == 409, r.text
        assert r.json()["error"]["code"] == error
        # Thao tác bị từ chối: không ghi audit, không phát, không đổi trạng thái.
        assert len(_audits(db, aid)) == audits_before
        assert publisher.messages == []
        assert client.get(f"/api/v1/alerts/{aid}", headers=nurse).json()["status"] == state


@pytest.mark.parametrize("value", ["CONFIRMED", "FALSE_ALARM", "PATIENT_SAFE"])
def test_outcome_values_accepted(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    post_event: Callable[..., Any],
    value: str,
) -> None:
    nurse = login("nurse")
    aid = _new_alert(client, login, post_event)
    _to_state(client, aid, "ACKNOWLEDGED", nurse)
    r = client.post(f"/api/v1/alerts/{aid}/outcome", json={"outcome": value}, headers=nurse)
    assert r.status_code == 200 and r.json()["outcome"] == value


@pytest.mark.parametrize(
    ("action", "body"),
    [
        ("outcome", {"outcome": "PAIN"}),
        ("outcome", {}),
        ("outcome", {"outcome": "CONFIRMED", "note": "x" * 1001}),
        ("outcome", {"outcome": "CONFIRMED", "extra": 1}),
        ("resolve", {"note": "x" * 1001}),
        ("resolve", {"status": "PENDING"}),
    ],
)
def test_body_validation_422(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    post_event: Callable[..., Any],
    db: Session,
    action: str,
    body: dict[str, Any],
) -> None:
    nurse = login("nurse")
    aid = _new_alert(client, login, post_event)
    _to_state(client, aid, "ACKNOWLEDGED", nurse)
    n = len(_audits(db, aid))
    r = client.post(f"/api/v1/alerts/{aid}/{action}", json=body, headers=nurse)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert len(_audits(db, aid)) == n


def test_note_max_length_accepted(
    client: TestClient, login: Login, open_session: dict[str, Any], post_event: Callable[..., Any]
) -> None:
    nurse = login("nurse")
    aid = _new_alert(client, login, post_event)
    _to_state(client, aid, "ACKNOWLEDGED", nurse)
    r = client.post(
        f"/api/v1/alerts/{aid}/outcome",
        json={"outcome": "CONFIRMED", "note": "x" * 1000},
        headers=nurse,
    )
    assert r.status_code == 200 and len(r.json()["note"]) == 1000


def test_each_action_writes_alert_fields_and_audit(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    post_event: Callable[..., Any],
    db: Session,
) -> None:
    """AC3, R5, R7: người + thời điểm trong `alerts` và `audit_logs` (before/after)."""
    nurse, charge, admin = login("nurse"), login("charge"), login("admin")
    aid = _new_alert(client, login, post_event)
    start = datetime.now(UTC) - timedelta(seconds=5)

    a = _call(client, aid, "acknowledge", nurse).json()
    o = _call(client, aid, "outcome", charge, outcome="FALSE_ALARM", note="Gối rơi").json()
    r = _call(client, aid, "resolve", admin, note="Đã kiểm tra").json()

    assert a["acknowledged_by"]["full_name"] == "Nguyễn Thị Hoa"
    assert o["outcome_by"]["full_name"] == "Trần Văn Minh"
    assert r["resolved_by"]["full_name"] == "Phạm Thu Hà"
    assert r["acknowledged_by"]["full_name"] == "Nguyễn Thị Hoa"  # không bị ghi đè
    assert r["outcome"] == "FALSE_ALARM" and r["note"] == "Đã kiểm tra"
    for key in ("acknowledged_at", "outcome_at", "resolved_at"):
        assert datetime.fromisoformat(r[key]) >= start

    db.expire_all()
    row = db.get(Alert, aid)
    assert row is not None
    assert row.acknowledged_by == _uid(db, "nurse")
    assert row.outcome_by == _uid(db, "charge")
    assert row.resolved_by == _uid(db, "admin")

    logs = [log for log in _audits(db, aid) if log.action != "alert.create"]
    assert [(log.action, log.actor_user_id) for log in logs] == [
        ("alert.acknowledge", _uid(db, "nurse")),
        ("alert.outcome", _uid(db, "charge")),
        ("alert.resolve", _uid(db, "admin")),
    ]
    assert [(log.before, log.after) for log in logs] == [
        (
            {"status": "PENDING", "outcome": None, "note": None},
            {"status": "ACKNOWLEDGED", "outcome": None, "note": None},
        ),
        (
            {"status": "ACKNOWLEDGED", "outcome": None, "note": None},
            {"status": "ACKNOWLEDGED", "outcome": "FALSE_ALARM", "note": "Gối rơi"},
        ),
        (
            {"status": "ACKNOWLEDGED", "outcome": "FALSE_ALARM", "note": "Gối rơi"},
            {"status": "RESOLVED", "outcome": "FALSE_ALARM", "note": "Đã kiểm tra"},
        ),
    ]


def test_outcome_without_note_keeps_existing_note(
    client: TestClient, login: Login, open_session: dict[str, Any], post_event: Callable[..., Any]
) -> None:
    """R3 *(giả định)*: `note` chỉ ghi đè khi được gửi."""
    nurse = login("nurse")
    aid = _new_alert(client, login, post_event)
    _to_state(client, aid, "ACKNOWLEDGED", nurse)
    _call(client, aid, "outcome", nurse, note="Lần 1")
    r = _call(client, aid, "outcome", nurse, outcome="PATIENT_SAFE").json()
    assert r["outcome"] == "PATIENT_SAFE" and r["note"] == "Lần 1"


def test_resolve_without_outcome_keeps_null(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    post_event: Callable[..., Any],
    db: Session,
) -> None:
    """AC5: xử lý khi chưa ghi kết quả → RESOLVED, outcome null (cả không gửi body)."""
    nurse = login("nurse")
    aid = _new_alert(client, login, post_event)
    _to_state(client, aid, "ACKNOWLEDGED", nurse)
    r = client.post(f"/api/v1/alerts/{aid}/resolve", headers=nurse)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "RESOLVED"
    assert body["outcome"] is None and body["outcome_by"] is None and body["outcome_at"] is None
    assert _audits(db, aid)[-1].after == {"status": "RESOLVED", "outcome": None, "note": None}


def test_doctor_cannot_ack_outcome_resolve_403(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    post_event: Callable[..., Any],
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    """AC4, R6: DOCTOR chỉ xem; thử ở cả trạng thái PENDING và ACKNOWLEDGED."""
    doctor, nurse = login("doctor"), login("nurse")
    aid = _new_alert(client, login, post_event)
    for state in ("PENDING", "ACKNOWLEDGED"):
        if state == "ACKNOWLEDGED":
            _to_state(client, aid, state, nurse)
        n = len(_audits(db, aid))
        publisher.messages.clear()
        for action in ACTIONS:
            r = _call(client, aid, action, doctor)
            assert r.status_code == 403, (state, action, r.text)
            assert r.json()["error"]["code"] == "FORBIDDEN"
        assert len(_audits(db, aid)) == n
        assert publisher.messages == []
        assert client.get(f"/api/v1/alerts/{aid}", headers=nurse).json()["status"] == state


def test_doctor_can_list_and_get(
    client: TestClient, login: Login, open_session: dict[str, Any], post_event: Callable[..., Any]
) -> None:
    doctor = login("doctor")
    aid = _new_alert(client, login, post_event)
    r = client.get("/api/v1/alerts", headers=doctor)
    assert r.status_code == 200 and aid in [i["id"] for i in r.json()["items"]]
    r = client.get(f"/api/v1/alerts/{aid}", headers=doctor)
    assert r.status_code == 200 and r.json()["id"] == aid


def test_no_token_401(
    client: TestClient, login: Login, open_session: dict[str, Any], post_event: Callable[..., Any]
) -> None:
    aid = _new_alert(client, login, post_event)
    for action in ACTIONS:
        assert _call(client, aid, action, {}).status_code == 401
    assert client.get("/api/v1/alerts").status_code == 401
    assert client.get(f"/api/v1/alerts/{aid}").status_code == 401


def test_unknown_alert_404_no_publish(
    client: TestClient, login: Login, publisher: InMemoryPublisher
) -> None:
    nurse = login("nurse")
    publisher.messages.clear()
    for action in ACTIONS:
        r = _call(client, 9999, action, nurse)
        assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    assert client.get("/api/v1/alerts/9999", headers=nurse).status_code == 404
    assert publisher.messages == []


def test_alert_out_shape(
    client: TestClient, login: Login, open_session: dict[str, Any], post_event: Callable[..., Any]
) -> None:
    """R10: AlertOut có event (mã, không câu tiếng Việt), bed, session."""
    aid = _new_alert(client, login, post_event)
    a = client.get(f"/api/v1/alerts/{aid}", headers=login("nurse")).json()
    assert a["event"]["code"] == "BED_EXIT" and a["event"]["priority"] == "HIGH"
    assert a["event"]["observation_quality"] == "GOOD"
    assert a["bed"]["id"] == 1 and a["bed"]["code"]
    assert a["session"]["id"] == open_session["id"] and a["session"]["patient_code"]


def test_list_filters_and_limit(
    client: TestClient, login: Login, open_session: dict[str, Any], post_event: Callable[..., Any]
) -> None:
    """R9: lọc `bed_id`, `from`/`to` theo `events.occurred_at`; `limit > 200` → 422."""
    nurse = login("nurse")
    t0 = datetime.now(UTC) + timedelta(seconds=1)  # sau khi phiên mở
    old = _new_alert(client, login, post_event, occurred_at=t0)
    new = _new_alert(client, login, post_event, occurred_at=t0 + timedelta(hours=2))

    def ids(qs: dict[str, Any]) -> list[int]:
        r = client.get("/api/v1/alerts", params=qs, headers=nurse)
        assert r.status_code == 200, r.text
        return [i["id"] for i in r.json()["items"]]

    assert ids({"bed_id": 1}) == [new, old]
    assert ids({"bed_id": 2}) == []
    mid, end = (t0 + timedelta(hours=1)).isoformat(), (t0 + timedelta(hours=3)).isoformat()
    assert ids({"from": mid, "to": end}) == [new]
    assert ids({"to": (t0 + timedelta(hours=1)).isoformat()}) == [old]
    page = client.get("/api/v1/alerts", params={"limit": 1}, headers=nurse).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    r = client.get("/api/v1/alerts", params={"limit": 201}, headers=nurse)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.real_commit
def test_publisher_called_after_commit_only_on_success(
    app: Any,
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    post_event: Callable[..., Any],
    test_engine: Engine,
) -> None:
    """AC3, R8: lúc publisher chạy, kết nối DB khác đã thấy thay đổi (đã commit)."""
    nurse, charge = login("nurse"), login("charge")
    aid = _new_alert(client, login, post_event)
    seen: list[tuple[str, str, str | None]] = []

    class CheckingPublisher(InMemoryPublisher):
        def publish(self, type_: str, payload: dict[str, Any]) -> None:
            with test_engine.connect() as other:
                row = other.execute(
                    text("SELECT status, outcome FROM alerts WHERE id = :id"), {"id": aid}
                ).one()
            seen.append((type_, row.status, row.outcome))
            super().publish(type_, payload)

    app.state.hub = CheckingPublisher()
    assert _call(client, aid, "acknowledge", nurse).status_code == 200
    assert _call(client, aid, "acknowledge", charge).status_code == 409
    assert _call(client, aid, "outcome", charge, outcome="PATIENT_SAFE").status_code == 200
    assert _call(client, aid, "resolve", login("doctor")).status_code == 403
    assert _call(client, aid, "resolve", charge).status_code == 200
    assert _call(client, aid, "outcome", nurse).status_code == 409
    assert seen == [
        ("alert.updated", "ACKNOWLEDGED", None),
        ("alert.updated", "ACKNOWLEDGED", "PATIENT_SAFE"),
        ("alert.updated", "RESOLVED", "PATIENT_SAFE"),
    ]
    payload = app.state.hub.messages[-1][1]
    assert payload["id"] == aid and payload["status"] == "RESOLVED"
