"""Timeline (F22): gộp sự kiện + thao tác cảnh báo + thao tác phiên bằng SQL UNION ALL.

Sắp theo `time`, rồi `ord` (sự kiện trước khi trùng thời điểm, R3), rồi `event_id`, `audit_id`
để thứ tự luôn xác định (kể cả khi phân trang qua các mục trùng giờ).
"""

from datetime import datetime, timedelta

from sqlalchemy import BigInteger, cast, func, literal, null, or_, select, union_all
from sqlalchemy.orm import Session, aliased, selectinload

from postcare.db.models import Alert, AuditLog, Event, MonitoringSession
from postcare.db.types import utcnow
from postcare.domain.dto import Page, TimelineAlertRef, TimelineItemOut, user_ref
from postcare.domain.errors import not_found, validation_error
from postcare.domain.sessions import session_chain
from postcare.schemas.enums import AlertOutcome, Priority

ALERT_ACTIONS = ("alert.acknowledge", "alert.outcome", "alert.resolve")
# Thao tác phiên hiện trên timeline (F04 R16, R19–R22). `session.start`/`end` không đưa vào.
SESSION_ACTIONS = ("session.transfer", "session.pause", "session.resume")
DEFAULT_WINDOW = timedelta(hours=24)


def _query(
    *,
    session_ids: list[int] | None,
    bed_id: int | None,
    from_: datetime | None,
    to: datetime | None,
    priorities: list[Priority] | None,
):
    no_id = cast(null(), BigInteger)
    ev = select(
        literal("event").label("kind"),
        Event.occurred_at.label("time"),
        literal(0).label("ord"),
        cast(Event.id, BigInteger).label("event_id"),
        no_id.label("audit_id"),
    )
    act = (
        select(
            literal("alert_action").label("kind"),
            AuditLog.created_at.label("time"),
            literal(1).label("ord"),
            cast(Event.id, BigInteger).label("event_id"),
            cast(AuditLog.id, BigInteger).label("audit_id"),
        )
        .join(Alert, (AuditLog.entity_type == "alert") & (AuditLog.entity_id == Alert.id))
        .join(Event, Event.id == Alert.event_id)
        .where(AuditLog.action.in_(ALERT_ACTIONS))
    )
    # Chuyển giường: audit gắn với phiên mới; phiên cũ (giường cũ) lấy qua previous_session_id.
    sess, prev = MonitoringSession, aliased(MonitoringSession)
    sa = (
        select(
            literal("session_action").label("kind"),
            AuditLog.created_at.label("time"),
            literal(1).label("ord"),
            no_id.label("event_id"),
            cast(AuditLog.id, BigInteger).label("audit_id"),
        )
        .join(sess, (AuditLog.entity_type == "session") & (AuditLog.entity_id == sess.id))
        .outerjoin(
            prev,
            (AuditLog.action == "session.transfer") & (prev.id == sess.previous_session_id),
        )
        .where(AuditLog.action.in_(SESSION_ACTIONS))
    )
    if session_ids is not None:
        ev = ev.where(Event.session_id.in_(session_ids))
        act = act.where(Event.session_id.in_(session_ids))
        sa = sa.where(or_(sess.id.in_(session_ids), prev.id.in_(session_ids)))
    if bed_id is not None:
        ev = ev.where(Event.bed_id == bed_id)
        act = act.where(Event.bed_id == bed_id)
        sa = sa.where(or_(sess.bed_id == bed_id, prev.bed_id == bed_id))
    if from_ is not None:
        ev = ev.where(Event.occurred_at >= from_)
        act = act.where(AuditLog.created_at >= from_)
        sa = sa.where(AuditLog.created_at >= from_)
    if to is not None:
        ev = ev.where(Event.occurred_at < to)
        act = act.where(AuditLog.created_at < to)
        sa = sa.where(AuditLog.created_at < to)
    if priorities:
        # Thao tác cảnh báo theo mức của sự kiện gốc (R4); thao tác phiên không có mức → giữ.
        ev = ev.where(Event.priority.in_(priorities))
        act = act.where(Event.priority.in_(priorities))
    return union_all(ev, act, sa).subquery("timeline")


def _event_item(e: Event, time: datetime) -> TimelineItemOut:
    a = e.alert
    return TimelineItemOut(
        kind="event",
        time=time,
        session_id=e.session_id,
        bed_code=e.bed.code if e.bed else None,
        event_id=e.id,
        code=e.code,
        priority=e.priority,
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
    )


def _alert_action_item(e: Event, log: AuditLog, time: datetime) -> TimelineItemOut:
    after = log.after or {}
    raw_outcome = after.get("outcome") if log.action == "alert.outcome" else None
    return TimelineItemOut(
        kind="alert_action",
        time=time,
        session_id=e.session_id,
        bed_code=e.bed.code if e.bed else None,
        event_id=e.id,
        code=e.code,
        priority=e.priority,
        action=log.action,
        actor=user_ref(log.actor),
        outcome=AlertOutcome(raw_outcome) if raw_outcome else None,
        note=after.get("note"),
        alert_id=log.entity_id,
        event_code=e.code,
    )


def _session_action_item(s: MonitoringSession, log: AuditLog, time: datetime) -> TimelineItemOut:
    after = log.after or {}
    prev = s.previous_session if log.action == "session.transfer" else None
    return TimelineItemOut(
        kind="session_action",
        time=time,
        session_id=s.id,
        bed_code=s.bed.code,
        event_id=None,
        code=None,
        priority=None,
        action=log.action,
        actor=user_ref(log.actor),
        note=after.get("reason"),
        from_bed_code=prev.bed.code if prev else None,
    )


def _build(
    db: Session, rows: list[tuple[str, datetime, int | None, int | None]]
) -> list[TimelineItemOut]:
    event_ids = {r[2] for r in rows if r[2] is not None}
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
    session_ids = {a.entity_id for a in audits.values() if a.entity_type == "session"}
    sessions = {
        s.id: s
        for s in db.scalars(
            select(MonitoringSession)
            .where(MonitoringSession.id.in_(session_ids))
            .options(
                selectinload(MonitoringSession.bed),
                selectinload(MonitoringSession.previous_session).selectinload(
                    MonitoringSession.bed
                ),
            )
        )
    }
    items: list[TimelineItemOut] = []
    for kind, time, event_id, audit_id in rows:
        if kind == "event":
            items.append(_event_item(events[event_id], time))  # type: ignore[index]
        elif kind == "alert_action":
            log = audits[audit_id]  # type: ignore[index]
            items.append(_alert_action_item(events[event_id], log, time))  # type: ignore[index]
        else:
            log = audits[audit_id]  # type: ignore[index]
            items.append(_session_action_item(sessions[log.entity_id], log, time))
    return items


def _page(db: Session, sub, limit: int, offset: int) -> Page[TimelineItemOut]:
    total = db.scalar(select(func.count()).select_from(sub)) or 0
    rows = db.execute(
        select(sub.c.kind, sub.c.time, sub.c.event_id, sub.c.audit_id)
        .order_by(
            sub.c.time,
            sub.c.ord,
            sub.c.event_id.asc().nulls_last(),
            sub.c.audit_id.asc().nulls_first(),
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return Page[TimelineItemOut](
        items=_build(db, [(r[0], r[1], r[2], r[3]) for r in rows]), total=total
    )


def session_timeline(
    db: Session,
    session_id: int,
    priorities: list[Priority] | None,
    limit: int,
    offset: int,
    *,
    chain: bool = False,
) -> Page[TimelineItemOut]:
    """Timeline của một phiên; `chain=True` gộp cả chuỗi chuyển giường (F04 R16).

    F36 (người nhà) gọi với `chain=False` để chỉ thấy đúng phiên được cấp quyền.
    """
    if db.get(MonitoringSession, session_id) is None:
        raise not_found("Không tìm thấy phiên theo dõi")
    ids = [s.id for s in session_chain(db, session_id).items] if chain else [session_id]
    sub = _query(session_ids=ids, bed_id=None, from_=None, to=None, priorities=priorities)
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
    """Mọi phiên của giường trong khoảng `[from, to)`, kể cả sự kiện camera không có phiên."""
    to = to or utcnow()
    from_ = from_ or (to - DEFAULT_WINDOW)
    if from_ >= to:
        raise validation_error("Thời điểm bắt đầu phải trước thời điểm kết thúc")
    sub = _query(session_ids=None, bed_id=bed_id, from_=from_, to=to, priorities=priorities)
    return _page(db, sub, limit, offset)
