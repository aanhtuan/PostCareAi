"""Bàn giao ca (F24): tổng hợp bằng SQL aggregation theo giường trong khoảng `[from, to)`."""

from datetime import UTC, date, datetime

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from postcare.db.models import Alert, Bed, Event, ShiftDefinition
from postcare.db.types import utcnow
from postcare.domain.alerts import PRIORITY_RANK_SQL, load_alerts
from postcare.domain.dto import HandoverBedOut, HandoverOut, alert_out, shift_out
from postcare.domain.errors import not_found, validation_error
from postcare.domain.shifts import shift_window
from postcare.schemas.enums import AlertOutcome
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
    """Mọi số liệu là `COUNT … GROUP BY` trong SQL (F24 R5), không lặp bản ghi bằng Python.

    - Sự kiện thuộc khoảng: `occurred_at ∈ [start, end)`, tính theo `events.bed_id` (giường lúc
      xảy ra; bệnh nhân chuyển giường thì sự kiện cũ vẫn ở giường cũ, F04).
    - "Tại cuối khoảng" = `min(end, now)` (ca đang diễn ra, R2).
    - Giường: mọi giường đang dùng + giường đã xóa có sự kiện trong khoảng *(giả định)*.
    """
    in_range = (Event.occurred_at >= start) & (Event.occurred_at < end) & Event.bed_id.is_not(None)
    cutoff = min(end, utcnow())

    counts: dict[int, dict[EventCode, int]] = {}
    for bed_id, code, n in db.execute(
        select(Event.bed_id, Event.code, func.count())
        .where(in_range)
        .group_by(Event.bed_id, Event.code)
        .order_by(Event.bed_id, cast(Event.code, String))
    ):
        counts.setdefault(bed_id, {})[code] = int(n)

    resolved = Alert.resolved_at.is_not(None) & (Alert.resolved_at < cutoff)
    alert_stats: dict[int, tuple[int, int]] = {
        bed_id: (int(r), int(u))
        for bed_id, r, u in db.execute(
            select(
                Event.bed_id,
                func.count().filter(resolved),
                func.count().filter(~resolved),
            )
            .join(Alert, Alert.event_id == Event.id)
            .where(in_range)
            .group_by(Event.bed_id)
        )
    }

    outcomes: dict[int, dict[AlertOutcome, int]] = {}
    for bed_id, outcome, n in db.execute(
        select(Event.bed_id, Alert.outcome, func.count())
        .join(Alert, Alert.event_id == Event.id)
        .where(in_range, Alert.outcome.is_not(None), Alert.outcome_at < cutoff)
        .group_by(Event.bed_id, Alert.outcome)
        .order_by(Event.bed_id, cast(Alert.outcome, String))
    ):
        outcomes.setdefault(bed_id, {})[outcome] = int(n)

    state_changes: dict[int, int] = {
        bed_id: int(n)
        for bed_id, n in db.execute(
            select(Event.bed_id, func.count())
            .where(in_range, Event.code.in_(STATE_CHANGE_CODES))
            .group_by(Event.bed_id)
        )
    }

    beds_q = (
        select(Bed)
        .where(Bed.is_active.is_(True) | Bed.id.in_(select(Event.bed_id).where(in_range)))
        .order_by(Bed.code)
    )
    beds: list[HandoverBedOut] = []
    for bed in db.scalars(beds_q):
        n_resolved, n_unresolved = alert_stats.get(bed.id, (0, 0))
        beds.append(
            HandoverBedOut(
                bed_id=bed.id,
                code=bed.code,
                is_active=bed.is_active,
                event_counts=counts.get(bed.id, {}),
                alerts_resolved=n_resolved,
                alerts_unresolved=n_unresolved,
                state_change_count=state_changes.get(bed.id, 0),
                outcome_counts=outcomes.get(bed.id, {}),
            )
        )

    # Tồn đọng tại cuối khoảng (R4): sự kiện xảy ra trước cuối khoảng, chưa xử lý tại đó, kể cả
    # trước `from`. Dùng `occurred_at` (không phải `alerts.created_at`) để khớp bảng theo giường
    # khi cảnh báo được ghi trễ *(giả định)*. Sắp: ưu tiên cao trước, cũ trước, rồi id.
    outstanding_ids = list(
        db.scalars(
            select(Alert.id)
            .join(Event, Event.id == Alert.event_id)
            .where(Event.occurred_at < cutoff, ~resolved)
            .order_by(PRIORITY_RANK_SQL.desc(), Event.occurred_at.asc(), Alert.id.asc())
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
