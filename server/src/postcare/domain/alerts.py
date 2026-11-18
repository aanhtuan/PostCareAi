"""Vòng đời cảnh báo (ADR-0007): PENDING → ACKNOWLEDGED → RESOLVED; outcome tách riêng."""

from datetime import datetime
from typing import Any

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session, selectinload

from postcare.db.models import Alert, Event, MonitoringSession, User
from postcare.db.types import utcnow
from postcare.domain.audit import record_audit
from postcare.domain.dto import AlertOut, Page, alert_out
from postcare.domain.errors import DomainError, not_found
from postcare.domain.notifications import Publisher, safe_publish
from postcare.schemas.enums import PRIORITY_RANK, AlertOutcome, AlertStatus, Priority

_STATUS_ORDER = case(
    (Alert.status == AlertStatus.PENDING, 0),
    (Alert.status == AlertStatus.ACKNOWLEDGED, 1),
    else_=2,
)

PRIORITY_RANK_SQL = case(
    *[(Event.priority == p, rank) for p, rank in PRIORITY_RANK.items()],
    else_=0,
)


def _load_options() -> list[Any]:
    return [
        selectinload(Alert.event).selectinload(Event.bed),
        selectinload(Alert.event)
        .selectinload(Event.session)
        .selectinload(MonitoringSession.patient),
        selectinload(Alert.acknowledger),
        selectinload(Alert.outcome_user),
        selectinload(Alert.resolver),
    ]


def _get(db: Session, alert_id: int, *, lock: bool = False) -> Alert:
    """`lock=True`: `SELECT … FOR UPDATE` để kiểm tra trạng thái rồi ghi không bị tranh chấp."""
    q = select(Alert).where(Alert.id == alert_id).options(*_load_options())
    if lock:
        # populate_existing: nạp lại từ DB, không dùng bản cũ trong identity map.
        q = q.with_for_update(of=Alert).execution_options(populate_existing=True)
    alert = db.scalar(q)
    if alert is None:
        raise not_found("Không tìm thấy cảnh báo")
    return alert


def _snapshot(a: Alert) -> dict[str, Any]:
    return {
        "status": a.status.value,
        "outcome": a.outcome.value if a.outcome else None,
        "note": a.note,
    }


def _invalid(message: str) -> DomainError:
    return DomainError("INVALID_ALERT_TRANSITION", message, 409)


def _finish(db: Session, alert_id: int, publisher: Publisher) -> AlertOut:
    db.commit()
    db.expire_all()
    out = alert_out(_get(db, alert_id))
    safe_publish(publisher, "alert.updated", out)
    return out


def get_alert(db: Session, alert_id: int) -> AlertOut:
    return alert_out(_get(db, alert_id))


def acknowledge(db: Session, alert_id: int, user: User, publisher: Publisher) -> AlertOut:
    alert = _get(db, alert_id)
    if alert.status == AlertStatus.RESOLVED:
        raise _invalid("Cảnh báo đã xử lý, không thể tiếp nhận")
    before = _snapshot(alert)
    now = utcnow()
    # Chỉ một người tiếp nhận: UPDATE có điều kiện, không ai khác ghi đè được.
    result = db.execute(
        update(Alert)
        .where(Alert.id == alert_id, Alert.status == AlertStatus.PENDING)
        .values(status=AlertStatus.ACKNOWLEDGED, acknowledged_by=user.id, acknowledged_at=now)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        db.rollback()
        db.expire_all()
        current = _get(db, alert_id)
        if current.status == AlertStatus.ACKNOWLEDGED and current.acknowledger:
            raise DomainError(
                "ALERT_ALREADY_ACKNOWLEDGED",
                f"Cảnh báo đã được tiếp nhận bởi {current.acknowledger.full_name}",
                409,
                {
                    "acknowledged_by": {
                        "id": current.acknowledger.id,
                        "full_name": current.acknowledger.full_name,
                    },
                    "acknowledged_at": current.acknowledged_at.isoformat()
                    if current.acknowledged_at
                    else None,
                },
            )
        raise _invalid("Không thể tiếp nhận cảnh báo ở trạng thái hiện tại")
    record_audit(
        db,
        actor_user_id=user.id,
        action="alert.acknowledge",
        entity_type="alert",
        entity_id=alert_id,
        before=before,
        after={**before, "status": AlertStatus.ACKNOWLEDGED.value},
    )
    return _finish(db, alert_id, publisher)


def set_outcome(
    db: Session,
    alert_id: int,
    outcome: AlertOutcome,
    note: str | None,
    user: User,
    publisher: Publisher,
) -> AlertOut:
    alert = _get(db, alert_id, lock=True)
    if alert.status != AlertStatus.ACKNOWLEDGED:
        raise _invalid("Chỉ ghi kết quả sau khi đã tiếp nhận và trước khi xử lý xong")
    before = _snapshot(alert)
    alert.outcome = outcome
    alert.outcome_by = user.id
    alert.outcome_at = utcnow()
    if note is not None:
        alert.note = note
    record_audit(
        db,
        actor_user_id=user.id,
        action="alert.outcome",
        entity_type="alert",
        entity_id=alert_id,
        before=before,
        after=_snapshot(alert),
    )
    return _finish(db, alert_id, publisher)


def resolve(
    db: Session, alert_id: int, note: str | None, user: User, publisher: Publisher
) -> AlertOut:
    alert = _get(db, alert_id, lock=True)
    if alert.status != AlertStatus.ACKNOWLEDGED:
        raise _invalid("Chỉ xử lý xong cảnh báo đã được tiếp nhận")
    before = _snapshot(alert)
    alert.status = AlertStatus.RESOLVED
    alert.resolved_by = user.id
    alert.resolved_at = utcnow()
    if note is not None:
        alert.note = note
    record_audit(
        db,
        actor_user_id=user.id,
        action="alert.resolve",
        entity_type="alert",
        entity_id=alert_id,
        before=before,
        after=_snapshot(alert),
    )
    return _finish(db, alert_id, publisher)


def list_alerts(
    db: Session,
    *,
    statuses: list[AlertStatus] | None,
    bed_id: int | None,
    priorities: list[Priority] | None,
    from_: datetime | None,
    to: datetime | None,
    limit: int,
    offset: int,
) -> Page[AlertOut]:
    """Chưa xử lý trước (PENDING, ACKNOWLEDGED, RESOLVED); trong nhóm mới nhất trước."""
    q = select(Alert).join(Alert.event)
    if statuses:
        q = q.where(Alert.status.in_(statuses))
    if bed_id is not None:
        q = q.where(Event.bed_id == bed_id)
    if priorities:
        q = q.where(Event.priority.in_(priorities))
    if from_ is not None:
        q = q.where(Event.occurred_at >= from_)
    if to is not None:
        q = q.where(Event.occurred_at < to)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.options(*_load_options())
        .order_by(_STATUS_ORDER, Event.occurred_at.desc(), Alert.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return Page[AlertOut](items=[alert_out(a) for a in rows], total=total)


def load_alerts(db: Session, ids: list[int]) -> dict[int, Alert]:
    if not ids:
        return {}
    rows = db.scalars(select(Alert).where(Alert.id.in_(ids)).options(*_load_options()))
    return {a.id: a for a in rows}
