"""F17 AC1, AC2 (R11, R13–R15): `ingest_event` gắn phiên, tạo alert, lưu trước phát sau."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from postcare.db.models import Alert, AuditLog, Event, MonitoringSession
from postcare.domain.dto import EventIn
from postcare.domain.errors import DomainError
from postcare.domain.events import ingest_event
from postcare.domain.notifications import InMemoryPublisher
from postcare.schemas.enums import AlertStatus, ObservationQuality, Priority
from postcare.schemas.events import EVENT_CATALOG, EventCode


def _event(
    code: EventCode = EventCode.BED_EXIT,
    priority: Priority | None = None,
    *,
    occurred_at: datetime | None = None,
    explanation: dict[str, Any] | None = None,
    config_hash: str = "cfg-hash-1",
) -> EventIn:
    t = occurred_at or datetime.now(UTC)
    return EventIn(
        event_uid=str(uuid.uuid4()),
        camera_id=1,
        code=code,
        priority=priority or EVENT_CATALOG[code].default_priority,
        occurred_at=t,
        detected_at=t + timedelta(milliseconds=1500),
        confidence=0.87,
        observation_quality=ObservationQuality.GOOD,
        explanation=explanation if explanation is not None else {"rule_id": "body.bed_exit"},
        config_hash=config_hash,
    )


def _count(db: Session, model: type) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_event_attached_to_open_session_at_occurred_at(
    client: TestClient, login: Any, open_session: dict[str, Any], db: Session
) -> None:
    """Sự kiện đến sau khi phiên đóng nhưng `occurred_at` nằm trong phiên → gắn phiên đó."""
    started = datetime.now(UTC) - timedelta(minutes=10)
    db.execute(
        update(MonitoringSession)
        .where(MonitoringSession.id == open_session["id"])
        .values(started_at=started)
    )
    db.commit()
    r = client.post(f"/api/v1/sessions/{open_session['id']}/end", headers=login("nurse"), json={})
    assert r.status_code == 200, r.text
    occurred = started + timedelta(minutes=5)
    out, created = ingest_event(db, _event(occurred_at=occurred), InMemoryPublisher())
    assert created
    ev = db.get(Event, out.id)
    assert ev is not None
    assert ev.session_id == open_session["id"]
    assert ev.bed_id == 1 and ev.camera_id == 1


def test_event_outside_session_window_rejected(
    client: TestClient, open_session: dict[str, Any], db: Session
) -> None:
    session = db.get(MonitoringSession, open_session["id"])
    assert session is not None
    before = session.started_at - timedelta(seconds=5)
    with pytest.raises(DomainError) as exc:
        ingest_event(db, _event(occurred_at=before), InMemoryPublisher())
    assert exc.value.code == "NO_ACTIVE_SESSION" and exc.value.http_status == 409
    assert _count(db, Event) == 0


def test_high_event_creates_pending_alert(open_session: dict[str, Any], db: Session) -> None:
    pub = InMemoryPublisher()
    out, _ = ingest_event(db, _event(EventCode.BED_EXIT, Priority.HIGH), pub)
    alert = db.scalar(select(Alert).where(Alert.event_id == out.id))
    assert alert is not None
    assert alert.status == AlertStatus.PENDING and alert.outcome is None
    assert pub.types() == ["event.created", "alert.created"]


def test_medium_event_creates_pending_alert(open_session: dict[str, Any], db: Session) -> None:
    out, _ = ingest_event(db, _event(EventCode.BED_EDGE, Priority.MEDIUM), InMemoryPublisher())
    alert = db.scalar(select(Alert).where(Alert.event_id == out.id))
    assert alert is not None and alert.status == AlertStatus.PENDING


@pytest.mark.parametrize(
    ("code", "priority"),
    [
        (EventCode.POSTURE_CHANGE, Priority.LOG),
        (EventCode.SIT_UP, Priority.INFO),
        (EventCode.OBSERVATION_LOST, Priority.INFO),
        (EventCode.OBSERVATION_RESTORED, Priority.LOG),
    ],
)
def test_log_info_event_no_alert(
    open_session: dict[str, Any], db: Session, code: EventCode, priority: Priority
) -> None:
    pub = InMemoryPublisher()
    ingest_event(db, _event(code, priority), pub)
    assert _count(db, Event) == 1
    assert _count(db, Alert) == 0
    assert pub.types() == ["event.created"]


def test_alert_creation_audited_as_system(open_session: dict[str, Any], db: Session) -> None:
    out, _ = ingest_event(db, _event(EventCode.BED_EXIT, Priority.HIGH), InMemoryPublisher())
    alert = db.scalar(select(Alert).where(Alert.event_id == out.id))
    assert alert is not None
    logs = list(db.scalars(select(AuditLog).where(AuditLog.action == "alert.create")))
    assert len(logs) == 1
    assert logs[0].actor_user_id is None
    assert logs[0].entity_type == "alert" and logs[0].entity_id == alert.id
    assert logs[0].after == {"status": "PENDING", "event_id": out.id}


def test_explanation_and_config_hash_stored(open_session: dict[str, Any], db: Session) -> None:
    explanation = {
        "rule_id": "body.bed_exit",
        "from_state": "STANDING",
        "to_state": "OUT_OF_BED",
        "held_ms": 1000,
        "state_chain": ["SITTING", "AT_EDGE", "STANDING", "OUT_OF_BED"],
    }
    data = _event(explanation=explanation, config_hash="209d60d22e16abcd")
    out, _ = ingest_event(db, data, InMemoryPublisher())
    db.expire_all()
    ev = db.get(Event, out.id)
    assert ev is not None
    assert ev.explanation == explanation
    assert ev.config_hash == "209d60d22e16abcd"
    assert ev.confidence == pytest.approx(0.87)
    assert ev.occurred_at == data.occurred_at and ev.detected_at == data.detected_at
    assert str(ev.event_uid) == data.event_uid


def test_priority_from_catalog_not_client(open_session: dict[str, Any], db: Session) -> None:
    """Mức khác catalog → 400; chỉ FACE_ATTENTION nhận hai mức (event-engine.md mục 5)."""
    for code, wrong in [
        (EventCode.BED_EXIT, Priority.MEDIUM),
        (EventCode.SIT_UP, Priority.HIGH),
        (EventCode.OBSERVATION_LOST, Priority.MEDIUM),
        (EventCode.FACE_ATTENTION, Priority.LOG),
    ]:
        with pytest.raises(DomainError) as exc:
            ingest_event(db, _event(code, wrong), InMemoryPublisher())
        assert exc.value.code == "VALIDATION_ERROR"
    assert _count(db, Event) == 0


@pytest.mark.real_commit
def test_publisher_called_after_commit(app: Any, client: TestClient, open_session: Any) -> None:
    """Lúc publisher chạy, dữ liệu đã thấy được từ kết nối DB khác (đã commit)."""
    order: list[str] = []

    class CheckingPublisher:
        def publish(self, type_: str, payload: dict[str, Any]) -> None:
            with app.state.session_factory() as other:
                if type_ == "event.created":
                    assert other.get(Event, payload["id"]) is not None
                if type_ == "alert.created":
                    assert other.get(Alert, payload["alert"]["id"]) is not None
            order.append(type_)

    with app.state.session_factory() as db:
        ingest_event(db, _event(EventCode.BED_EXIT, Priority.HIGH), CheckingPublisher())
    assert order == ["event.created", "alert.created"]


def test_db_error_publishes_nothing(
    open_session: dict[str, Any], db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    pub = InMemoryPublisher()

    def broken_commit() -> None:
        raise OperationalError("COMMIT", {}, Exception("mất kết nối DB"))

    monkeypatch.setattr(db, "commit", broken_commit)
    with pytest.raises(OperationalError):
        ingest_event(db, _event(EventCode.BED_EXIT, Priority.HIGH), pub)
    assert pub.messages == []


def test_publisher_failure_keeps_saved_data(open_session: dict[str, Any], db: Session) -> None:
    class BrokenPublisher:
        def publish(self, type_: str, payload: dict[str, Any]) -> None:
            raise RuntimeError("hub lỗi")

    out, created = ingest_event(db, _event(EventCode.BED_EXIT, Priority.HIGH), BrokenPublisher())
    assert created
    assert _count(db, Event) == 1 and _count(db, Alert) == 1
    assert db.get(Event, out.id) is not None


def test_integrity_error_branch_returns_existing(
    open_session: dict[str, Any], db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Request khác đã lưu cùng `event_uid` giữa lúc kiểm tra và lúc insert: nhánh IntegrityError
    rollback rồi trả bản đã có, `created = False`, không phát gì (R9)."""
    import postcare.domain.events as events_mod

    first = _event(EventCode.BED_EXIT, Priority.HIGH)
    saved, _ = ingest_event(db, first, InMemoryPublisher())
    real_existing = events_mod._existing
    calls: list[str] = []

    def stale_existing(session: Session, event_uid: str) -> Event | None:
        calls.append(event_uid)
        if len(calls) == 1:
            return None  # lần kiểm tra đầu chưa thấy bản của request kia
        return real_existing(session, event_uid)

    monkeypatch.setattr(events_mod, "_existing", stale_existing)
    pub = InMemoryPublisher()
    out, created = ingest_event(db, first, pub)
    assert len(calls) == 2
    assert created is False and out.id == saved.id
    assert pub.messages == []
    assert _count(db, Event) == 1 and _count(db, Alert) == 1
