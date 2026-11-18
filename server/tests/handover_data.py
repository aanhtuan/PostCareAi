"""Dữ liệu mẫu cho test bàn giao ca (F24): chèn sự kiện/cảnh báo trực tiếp theo mốc giờ."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from postcare.db.models import Alert, Event
from postcare.schemas.enums import AlertOutcome, AlertStatus, ObservationQuality, Priority
from postcare.schemas.events import EventCode


def z(h: int, m: int = 0, day: int = 12) -> datetime:
    """Mốc UTC trong tháng 10/2026."""
    return datetime(2026, 10, day, h, m, tzinfo=UTC)


def add_event(
    db: Session,
    code: EventCode,
    at: datetime,
    *,
    bed_id: int = 1,
    priority: Priority = Priority.INFO,
    alert: bool = False,
    resolved_at: datetime | None = None,
    outcome: AlertOutcome | None = None,
    outcome_at: datetime | None = None,
    alert_created_at: datetime | None = None,
) -> Alert | None:
    ev = Event(
        event_uid=str(uuid.uuid4()),
        session_id=None,
        bed_id=bed_id,
        camera_id=bed_id,
        code=code,
        priority=priority,
        occurred_at=at,
        detected_at=at,
        confidence=0.9,
        observation_quality=ObservationQuality.GOOD,
        explanation={"rule_id": "test"},
        config_hash="test",
    )
    db.add(ev)
    db.flush()
    if not alert:
        return None
    a = Alert(
        event_id=ev.id,
        status=AlertStatus.RESOLVED if resolved_at else AlertStatus.PENDING,
        outcome=outcome,
        outcome_at=outcome_at or (resolved_at if outcome else None),
        resolved_at=resolved_at,
    )
    db.add(a)
    db.flush()
    db.execute(update(Alert).where(Alert.id == a.id).values(created_at=alert_created_at or at))
    db.commit()
    return a
