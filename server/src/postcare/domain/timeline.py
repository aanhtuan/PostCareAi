"""Timeline (F22): gộp sự kiện + thao tác cảnh báo bằng SQL UNION ALL, sắp theo thời gian."""

from datetime import datetime, timedelta

from sqlalchemy import Integer, cast, func, literal, null, select, union_all
from sqlalchemy.orm import Session, selectinload

from postcare.db.models import Alert, AuditLog, Event, MonitoringSession
from postcare.db.types import utcnow
from postcare.domain.dto import Page, TimelineAlertRef, TimelineItemOut, user_ref
from postcare.domain.errors import not_found, validation_error
from postcare.schemas.enums import AlertOutcome, Priority

ALERT_ACTIONS = ("alert.acknowledge", "alert.outcome", "alert.resolve")
DEFAULT_WINDOW = timedelta(hours=24)


def _query(
    *,
    session_id: int | None,
    bed_id: int | None,
    from_: datetime | None,
    to: datetime | None,
    priorities: list[Priority] | None,
):
    ev = select(
        literal("event").label("kind"),
        Event.occurred_at.label("time"),
        literal(0).label("ord"),
        Event.id.label("event_id"),
        cast(null(), Integer).label("audit_id"),
    )
    act = (
        select(
            literal("alert_action").label("kind"),
            AuditLog.created_at.label("time"),
            literal(1).label("ord"),
            Event.id.label("event_id"),
            AuditLog.id.label("audit_id"),
        )
        .join(Alert, (AuditLog.entity_type == "alert") & (AuditLog.entity_id == Alert.id))
        .join(Event, Event.id == Alert.event_id)
        .where(AuditLog.action.in_(ALERT_ACTIONS))
    )
    if session_id is not None:
        ev = ev.where(Event.session_id == session_id)
        act = act.where(Event.session_id == session_id)
    if bed_id is not None:
        ev = ev.where(Event.bed_id == bed_id)
        act = act.where(Event.bed_id == bed_id)
    if from_ is not None:
        ev = ev.where(Event.occurred_at >= from_)
        act = act.where(AuditLog.created_at >= from_)
    if to is not None:
        ev = ev.where(Event.occurred_at < to)
        act = act.where(AuditLog.created_at < to)
    if priorities:
        ev = ev.where(Event.priority.in_(priorities))
        act = act.where(Event.priority.in_(priorities))
    return union_all(ev, act).subquery("timeline")


def _build(db: Session, rows: list[tuple[str, datetime, int, int | None]]) -> list[TimelineItemOut]:
    event_ids = {r[2] for r in rows}
    audit_ids = {r[3] for r in rows if r[3] is not None}
    events = {
        e.id: e
        for e in db.scalars(
            select(Event)
            .where(Event.id.in_(event_ids))
            .options(
                selectinload(Event.bed),
                selectinload(Event.alert).selectinload(Alert.acknowledger),
            )
        )
    }
    audits = {
        a.id: a
        for a in db.scalars(
            select(AuditLog).where(AuditLog.id.in_(audit_ids)).options(selectinload(AuditLog.actor))
        )
    }
    items: list[TimelineItemOut] = []
    for kind, time, event_id, audit_id in rows:
        e = events[event_id]
        base = {
            "time": time,
            "bed_code": e.bed.code if e.bed else None,
            "event_id": e.id,
            "code": e.code,
            "priority": e.priority,
        }
        if kind == "event":
            a = e.alert
            items.append(
                TimelineItemOut(
                    kind="event",
                    observation_quality=e.observation_quality,
                    alert=TimelineAlertRef(
                        id=a.id,
                        status=a.status,
                        outcome=a.outcome,
                        acknowledged_by=user_ref(a.acknowledger),
                    )
                    if a
                    else None,
                    alert_id=a.id if a else None,
                    **base,
                )
            )
        else:
            log = audits[audit_id]  # type: ignore[index]
            after = log.after or {}
            raw_outcome = after.get("outcome") if log.action == "alert.outcome" else None
            items.append(
                TimelineItemOut(
                    kind="alert_action",
                    action=log.action,  # type: ignore[arg-type]
                    actor=user_ref(log.actor),
                    outcome=AlertOutcome(raw_outcome) if raw_outcome else None,
                    note=after.get("note"),
                    alert_id=log.entity_id,
                    **base,
                )
            )
    return items


def _page(db: Session, sub, limit: int, offset: int) -> Page[TimelineItemOut]:
    total = db.scalar(select(func.count()).select_from(sub)) or 0
    rows = db.execute(
        select(sub.c.kind, sub.c.time, sub.c.event_id, sub.c.audit_id)
        .order_by(sub.c.time, sub.c.ord, sub.c.event_id, sub.c.audit_id)
        .limit(limit)
        .offset(offset)
    ).all()
    return Page[TimelineItemOut](
        items=_build(db, [(r[0], r[1], r[2], r[3]) for r in rows]), total=total
    )


def session_timeline(
    db: Session, session_id: int, priorities: list[Priority] | None, limit: int, offset: int
) -> Page[TimelineItemOut]:
    if db.get(MonitoringSession, session_id) is None:
        raise not_found("Không tìm thấy phiên theo dõi")
    sub = _query(session_id=session_id, bed_id=None, from_=None, to=None, priorities=priorities)
    return _page(db, sub, limit, offset)


def bed_timeline(
    db: Session,
    bed_id: int,
    from_: datetime | None,
    to: datetime | None,
    priorities: list[Priority] | None,
    limit: int,
    offset: int,
) -> Page[TimelineItemOut]:
    """Mọi phiên của giường trong khoảng, kể cả sự kiện camera không có phiên."""
    to = to or utcnow()
    from_ = from_ or (to - DEFAULT_WINDOW)
    if from_ >= to:
        raise validation_error("Thời điểm bắt đầu phải trước thời điểm kết thúc")
    sub = _query(session_id=None, bed_id=bed_id, from_=from_, to=to, priorities=priorities)
    return _page(db, sub, limit, offset)
