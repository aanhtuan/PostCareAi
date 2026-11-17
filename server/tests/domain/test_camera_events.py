"""F17 AC4 (R17–R19): `CAMERA_OFFLINE` / `CAMERA_ONLINE` do API sinh khi trạng thái camera đổi."""

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from postcare.db.models import Alert, AuditLog, Camera, Event
from postcare.db.types import utcnow
from postcare.domain.cameras import mark_offline_cameras
from postcare.domain.notifications import InMemoryPublisher
from postcare.schemas.enums import AlertStatus, CameraStatus, ObservationQuality, Priority
from postcare.schemas.events import EventCode


def _heartbeat(client: TestClient, headers: dict[str, str], **body: Any) -> None:
    r = client.post("/internal/v1/cameras/1/heartbeat", headers=headers, json=body)
    assert r.status_code == 200, r.text


def _camera_events(db: Session) -> list[Event]:
    db.expire_all()
    return list(
        db.scalars(
            select(Event)
            .where(Event.code.in_([EventCode.CAMERA_OFFLINE, EventCode.CAMERA_ONLINE]))
            .order_by(Event.id)
        )
    )


def _go_offline(app: Any, db: Session, publisher: InMemoryPublisher) -> Camera:
    cam = db.get(Camera, 1)
    assert cam is not None and cam.last_seen_at is not None
    changed = mark_offline_cameras(
        db,
        app.state.store,
        publisher,
        offline_after_s=5,
        now=cam.last_seen_at + timedelta(seconds=6),
    )
    assert changed == [1]
    return cam


def test_first_online_no_event(
    client: TestClient, open_session: Any, worker_headers: dict[str, str], db: Session
) -> None:
    cam = db.get(Camera, 1)
    assert cam is not None and cam.status == CameraStatus.UNKNOWN
    _heartbeat(client, worker_headers, fps=15)
    db.expire_all()
    assert db.get(Camera, 1).status == CameraStatus.ONLINE  # type: ignore[union-attr]
    assert _camera_events(db) == []


def test_online_to_offline_creates_camera_offline_alert(
    app: Any,
    client: TestClient,
    open_session: dict[str, Any],
    worker_headers: dict[str, str],
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    db.execute(update(Camera).where(Camera.id == 1).values(last_config_hash="hash-worker"))
    db.commit()
    _heartbeat(client, worker_headers, fps=15)
    publisher.messages.clear()
    cam = _go_offline(app, db, publisher)
    last_seen = cam.last_seen_at
    events = _camera_events(db)
    assert len(events) == 1
    ev = events[0]
    assert ev.code == EventCode.CAMERA_OFFLINE and ev.priority == Priority.MEDIUM
    assert ev.session_id == open_session["id"] and ev.bed_id == 1 and ev.camera_id == 1
    # R18: trường do API sinh
    assert ev.occurred_at == last_seen
    assert ev.confidence == 1.0
    assert ev.observation_quality == ObservationQuality.CAMERA_ISSUE
    assert ev.explanation["reason"] == "heartbeat_timeout"
    assert ev.explanation["rule_id"]
    assert ev.explanation["last_seen_at"] == last_seen.isoformat()  # type: ignore[union-attr]
    assert ev.config_hash == "hash-worker"
    assert ev.alert is not None and ev.alert.status == AlertStatus.PENDING
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "alert.create"))
    assert audit is not None and audit.actor_user_id is None
    assert "event.created" in publisher.types() and "alert.created" in publisher.types()


def test_offline_to_online_creates_camera_online_log(
    app: Any,
    client: TestClient,
    open_session: Any,
    worker_headers: dict[str, str],
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    _heartbeat(client, worker_headers, fps=15)
    _go_offline(app, db, publisher)
    before = utcnow()
    _heartbeat(client, worker_headers, fps=15)
    events = _camera_events(db)
    assert [e.code for e in events] == [EventCode.CAMERA_OFFLINE, EventCode.CAMERA_ONLINE]
    online = events[1]
    assert online.priority == Priority.LOG and online.alert is None
    assert online.observation_quality == ObservationQuality.GOOD
    assert online.occurred_at >= before
    assert online.config_hash == ""  # worker chưa gửi hash nào
    # Heartbeat tiếp theo khi đã ONLINE: không sinh thêm.
    _heartbeat(client, worker_headers, fps=15)
    assert len(_camera_events(db)) == 2


def test_camera_offline_without_session_still_alerts(
    app: Any,
    client: TestClient,
    worker_headers: dict[str, str],
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    """R19: giường không có phiên mở → `session_id` null nhưng vẫn có cảnh báo."""
    _heartbeat(client, worker_headers, fps=15)
    _go_offline(app, db, publisher)
    ev = _camera_events(db)[0]
    assert ev.session_id is None and ev.bed_id == 1
    assert ev.alert is not None


def test_camera_without_bed_no_event(
    app: Any,
    client: TestClient,
    worker_headers: dict[str, str],
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    db.execute(update(Camera).where(Camera.id == 1).values(bed_id=None))
    db.commit()
    _heartbeat(client, worker_headers, fps=15)
    _go_offline(app, db, publisher)
    assert _camera_events(db) == []
    assert db.scalar(select(func.count()).select_from(Alert)) == 0
