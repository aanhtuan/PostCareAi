"""Lưu sự kiện (idempotent theo `event_uid`), tạo cảnh báo MEDIUM/HIGH, rồi mới phát thông báo."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from postcare.db.models import Alert, Camera, Event
from postcare.db.types import utcnow
from postcare.domain.audit import record_audit
from postcare.domain.dto import (
    AlertCreatedOut,
    EventIn,
    EventIngestOut,
    EventOut,
    Page,
    alert_out,
    event_out,
)
from postcare.domain.errors import DomainError, validation_error
from postcare.domain.notifications import Publisher, safe_publish
from postcare.domain.sessions import session_at
from postcare.schemas.enums import AlertStatus, ObservationQuality, Priority
from postcare.schemas.events import ALERT_PRIORITIES, EVENT_CATALOG, EventCode, default_priority


def _validate(db: Session, data: EventIn) -> Camera:
    spec = EVENT_CATALOG[data.code]
    if spec.api_generated:
        raise validation_error("Sự kiện camera chỉ do máy chủ tạo", {"code": data.code})
    if data.priority not in spec.allowed_priorities:
        raise validation_error(
            "Mức ưu tiên không hợp lệ với loại sự kiện",
            {"code": data.code, "priority": data.priority},
        )
    camera = db.get(Camera, data.camera_id)
    if camera is None or camera.bed_id is None:
        raise validation_error("Camera không tồn tại hoặc chưa gắn giường")
    try:
        uuid.UUID(data.event_uid)
    except ValueError as exc:
        raise validation_error("event_uid phải là UUID") from exc
    return camera


def _existing(db: Session, event_uid: str) -> Event | None:
    return db.scalar(select(Event).where(Event.event_uid == event_uid))


def _insert(
    db: Session,
    *,
    event_uid: str,
    camera: Camera,
    session_id: int | None,
    code: EventCode,
    priority: Priority,
    occurred_at: datetime,
    detected_at: datetime,
    confidence: float,
    quality: ObservationQuality,
    explanation: dict[str, Any],
    config_hash: str,
) -> tuple[Event, Alert | None]:
    """Insert event (+ alert PENDING nếu MEDIUM/HIGH) trong transaction hiện tại."""
    now = utcnow()
    event = Event(
        event_uid=event_uid,
        session_id=session_id,
        bed_id=camera.bed_id,
        camera_id=camera.id,
        code=code,
        priority=priority,
        occurred_at=occurred_at,
        detected_at=detected_at,
        created_at=now,
        confidence=confidence,
        observation_quality=quality,
        explanation=explanation,
        config_hash=config_hash,
    )
    db.add(event)
    db.flush()
    alert: Alert | None = None
    if priority in ALERT_PRIORITIES:
        alert = Alert(event_id=event.id, status=AlertStatus.PENDING, created_at=now)
        db.add(alert)
        db.flush()
        record_audit(
            db,
            actor_user_id=None,
            action="alert.create",
            entity_type="alert",
            entity_id=alert.id,
            after={"status": AlertStatus.PENDING.value, "event_id": event.id},
        )
    return event, alert


def publish_created(db: Session, publisher: Publisher, event: Event, alert: Alert | None) -> None:
    """Gọi sau commit: event.created, rồi alert.created nếu có."""
    db.refresh(event)
    ev = event_out(event)
    safe_publish(publisher, "event.created", ev)
    if alert is not None:
        db.refresh(alert)
        safe_publish(publisher, "alert.created", AlertCreatedOut(alert=alert_out(alert), event=ev))


def ingest_event(db: Session, data: EventIn, publisher: Publisher) -> tuple[EventIngestOut, bool]:
    """Trả `(kết quả, created)`. Gửi lại cùng `event_uid` không tạo gì mới (F17 R9)."""
    existing = _existing(db, data.event_uid)
    if existing is not None:
        return EventIngestOut(id=existing.id, created=False), False
    camera = _validate(db, data)
    assert camera.bed_id is not None
    session = session_at(db, camera.bed_id, data.occurred_at)
    if session is None:
        raise DomainError(
            "NO_ACTIVE_SESSION", "Giường không có phiên theo dõi tại thời điểm sự kiện", 409
        )
    if session.paused_at is not None and data.occurred_at >= session.paused_at:
        raise DomainError(
            "CAPTURE_PAUSED", "Phiên theo dõi đang tạm dừng thu hình tại thời điểm sự kiện", 409
        )
    try:
        event, alert = _insert(
            db,
            event_uid=data.event_uid,
            camera=camera,
            session_id=session.id,
            code=data.code,
            priority=data.priority,
            occurred_at=data.occurred_at,
            detected_at=data.detected_at,
            confidence=data.confidence,
            quality=data.observation_quality,
            explanation=data.explanation,
            config_hash=data.config_hash,
        )
        if data.config_hash:
            camera.last_config_hash = data.config_hash
        db.commit()
    except IntegrityError:
        # Hai request cùng event_uid đến cùng lúc: bản kia đã lưu.
        db.rollback()
        again = _existing(db, data.event_uid)
        if again is None:
            raise
        return EventIngestOut(id=again.id, created=False), False
    publish_created(db, publisher, event, alert)
    return EventIngestOut(id=event.id, created=True), True


def create_camera_event(
    db: Session,
    camera: Camera,
    *,
    code: EventCode,
    occurred_at: datetime,
    reason: str,
) -> tuple[Event, Alert | None] | None:
    """Sự kiện CAMERA_OFFLINE / CAMERA_ONLINE do API sinh (F17 R17–R18). Caller commit."""
    if camera.bed_id is None:
        return None
    session = session_at(db, camera.bed_id, occurred_at)
    offline = code == EventCode.CAMERA_OFFLINE
    return _insert(
        db,
        event_uid=str(uuid.uuid4()),
        camera=camera,
        session_id=session.id if session else None,
        code=code,
        priority=default_priority(code),
        occurred_at=occurred_at,
        detected_at=utcnow(),
        confidence=1.0,
        quality=ObservationQuality.CAMERA_ISSUE if offline else ObservationQuality.GOOD,
        explanation={
            "rule_id": "api.camera_heartbeat",
            "reason": reason,
            "last_seen_at": camera.last_seen_at.isoformat() if camera.last_seen_at else None,
        },
        config_hash=camera.last_config_hash,
    )


def list_events(
    db: Session,
    *,
    bed_id: int | None,
    session_id: int | None,
    from_: datetime | None,
    to: datetime | None,
    priorities: list[Priority] | None,
    code: EventCode | None,
    limit: int,
    offset: int,
) -> Page[EventOut]:
    q = select(Event)
    if bed_id is not None:
        q = q.where(Event.bed_id == bed_id)
    if session_id is not None:
        q = q.where(Event.session_id == session_id)
    if from_ is not None:
        q = q.where(Event.occurred_at >= from_)
    if to is not None:
        q = q.where(Event.occurred_at < to)
    if priorities:
        q = q.where(Event.priority.in_(priorities))
    if code is not None:
        q = q.where(Event.code == code)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.options(selectinload(Event.bed), selectinload(Event.alert))
        .order_by(Event.occurred_at.desc(), Event.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return Page[EventOut](items=[event_out(e) for e in rows], total=total)
