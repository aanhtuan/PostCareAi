"""Bàn giao ca (F24): tổng hợp bằng SQL aggregation theo giường trong khoảng `[from, to)`."""

from datetime import UTC, date, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from postcare.db.models import Alert, Bed, Event, ShiftDefinition
from postcare.db.types import utcnow
from postcare.domain.alerts import PRIORITY_RANK_SQL, load_alerts
from postcare.domain.dto import HandoverBedOut, HandoverOut, alert_out, shift_out
from postcare.domain.errors import not_found, validation_error
from postcare.domain.shifts import shift_window
from postcare.schemas.events import STATE_CHANGE_CODES, EventCode


def resolve_window(
    db: Session,
    *,
    shift_id: int | None,
    day: date | None,
    from_: datetime | None,
    to: datetime | None,
) -> tuple[datetime, datetime, ShiftDefinition | None]:
    if shift_id is not None:
        shift = db.get(ShiftDefinition, shift_id)
        if shift is None:
            raise not_found("Không tìm thấy ca trực")
        if day is None:
            raise validation_error("Cần chọn ngày của ca trực")
        start, end = shift_window(shift, day)
        return start.astimezone(UTC), end.astimezone(UTC), shift
    if from_ is None or to is None:
        raise validation_error("Cần chọn ca trực hoặc khoảng thời gian")
    if from_ >= to:
        raise validation_error("Thời điểm bắt đầu phải trước thời điểm kết thúc")
    return from_.astimezone(UTC), to.astimezone(UTC), None


def build_handover(
    db: Session, start: datetime, end: datetime, shift: ShiftDefinition | None
) -> HandoverOut:
    in_range = (Event.occurred_at >= start) & (Event.occurred_at < end)
    # Ca đang diễn ra: số liệu "tại cuối khoảng" tính tới hiện tại (F24 R2).
    cutoff = min(end, utcnow())

    counts: dict[int, dict[EventCode, int]] = {}
    for bed_id, code, n in db.execute(
        select(Event.bed_id, Event.code, func.count())
        .where(in_range, Event.bed_id.is_not(None))
        .group_by(Event.bed_id, Event.code)
    ):
        counts.setdefault(bed_id, {})[code] = int(n)

    resolved_before_end = Alert.resolved_at.is_not(None) & (Alert.resolved_at < end)
    alert_rows = db.execute(
        select(
            Event.bed_id,
            func.sum(case((resolved_before_end, 1), else_=0)),
            func.sum(case((resolved_before_end, 0), else_=1)),
        )
        .join(Alert, Alert.event_id == Event.id)
        .where(in_range, Event.bed_id.is_not(None))
        .group_by(Event.bed_id)
    ).all()
    alert_stats = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in alert_rows}

    state_changes = dict(
        db.execute(
            select(Event.bed_id, func.count())
            .where(in_range, Event.code.in_(STATE_CHANGE_CODES))
            .group_by(Event.bed_id)
        ).all()
    )

    beds: list[HandoverBedOut] = []
    for bed in db.scalars(select(Bed).where(Bed.is_active.is_(True)).order_by(Bed.code)):
        resolved, unresolved = alert_stats.get(bed.id, (0, 0))
        beds.append(
            HandoverBedOut(
                bed_id=bed.id,
                code=bed.code,
                event_counts=counts.get(bed.id, {}),
                alerts_resolved=resolved,
                alerts_unresolved=unresolved,
                state_change_count=int(state_changes.get(bed.id, 0)),
            )
        )

    # Tồn đọng tại cuối khoảng: tạo trước `to`, chưa xử lý tại `to` (kể cả tạo trước `from`).
    outstanding_ids = list(
        db.scalars(
            select(Alert.id)
            .join(Event, Event.id == Alert.event_id)
            .where(
                Alert.created_at < cutoff,
                Alert.resolved_at.is_(None) | (Alert.resolved_at >= cutoff),
            )
            .order_by(PRIORITY_RANK_SQL.desc(), Event.occurred_at.asc())
        )
    )
    loaded = load_alerts(db, outstanding_ids)
    return HandoverOut(
        from_=start,
        to=end,
        shift=shift_out(shift) if shift else None,
        beds=beds,
        outstanding_alerts=[alert_out(loaded[i]) for i in outstanding_ids],
    )
