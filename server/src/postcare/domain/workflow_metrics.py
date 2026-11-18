"""Chỉ số workflow từ bảng `alerts` (F29 R5, R6; HS §8.2; PDF §11; evaluation.md §5).

Trong khoảng `[start, end)` theo `alerts.created_at`:
- thời gian chờ tiếp nhận `acknowledged_at − created_at` (cảnh báo đã tiếp nhận);
- thời gian xử lý `resolved_at − acknowledged_at` (cảnh báo đã xử lý);
- tỷ lệ cảnh báo đã xử lý có `outcome`; tỷ lệ `FALSE_ALARM` trên cảnh báo có `outcome`;
- số cảnh báo còn Chờ / Đã tiếp nhận tại thời điểm `end` (theo mốc thời gian, không theo
  trạng thái hiện tại).

Đặt ở `domain` vì `eval` không được import `db` (overview.md §3).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from postcare.db.models import Alert
from postcare.schemas.enums import AlertOutcome


def _percentile(values: Sequence[float], q: float) -> float | None:
    """Nội suy tuyến tính như `postcare.eval.metrics.percentile` (numpy mặc định)."""
    if not values:
        return None
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _ratio(a: int, b: int) -> float | None:
    return a / b if b > 0 else None


@dataclass(frozen=True)
class WorkflowMetrics:
    start: datetime
    end: datetime
    alerts: int
    ack_samples: int
    ack_wait_median_s: float | None
    ack_wait_p90_s: float | None
    resolve_samples: int
    resolve_median_s: float | None
    resolve_p90_s: float | None
    resolved: int
    resolved_with_outcome: int
    with_outcome: int
    false_alarm: int
    pending_at_end: int
    acknowledged_at_end: int

    @property
    def outcome_rate(self) -> float | None:
        return _ratio(self.resolved_with_outcome, self.resolved)

    @property
    def false_alarm_rate(self) -> float | None:
        return _ratio(self.false_alarm, self.with_outcome)

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.start.isoformat(),
            "to": self.end.isoformat(),
            "alerts": self.alerts,
            "ack_samples": self.ack_samples,
            "ack_wait_median_s": self.ack_wait_median_s,
            "ack_wait_p90_s": self.ack_wait_p90_s,
            "resolve_samples": self.resolve_samples,
            "resolve_median_s": self.resolve_median_s,
            "resolve_p90_s": self.resolve_p90_s,
            "resolved": self.resolved,
            "resolved_with_outcome": self.resolved_with_outcome,
            "outcome_rate": self.outcome_rate,
            "with_outcome": self.with_outcome,
            "false_alarm": self.false_alarm,
            "false_alarm_rate": self.false_alarm_rate,
            "pending_at_end": self.pending_at_end,
            "acknowledged_at_end": self.acknowledged_at_end,
        }


def _count(db: Session, *conds: Any) -> int:
    return int(db.scalar(select(func.count()).select_from(Alert).where(*conds)) or 0)


def workflow_metrics(db: Session, start: datetime, end: datetime) -> WorkflowMetrics:
    if end <= start:
        raise ValueError("Khoảng thời gian không hợp lệ: cần from < to.")
    in_range = and_(Alert.created_at >= start, Alert.created_at < end)
    times = db.execute(
        select(Alert.created_at, Alert.acknowledged_at, Alert.resolved_at).where(in_range)
    ).all()
    ack = [(a - c).total_seconds() for c, a, _ in times if a is not None]
    res = [(r - a).total_seconds() for _, a, r in times if a is not None and r is not None]
    resolved_cond = Alert.resolved_at.is_not(None)
    outcome_cond = Alert.outcome.is_not(None)
    not_acked_at_end = or_(Alert.acknowledged_at.is_(None), Alert.acknowledged_at >= end)
    acked_at_end = and_(
        Alert.acknowledged_at < end,
        or_(Alert.resolved_at.is_(None), Alert.resolved_at >= end),
    )
    return WorkflowMetrics(
        start=start,
        end=end,
        alerts=len(times),
        ack_samples=len(ack),
        ack_wait_median_s=_percentile(ack, 0.5),
        ack_wait_p90_s=_percentile(ack, 0.9),
        resolve_samples=len(res),
        resolve_median_s=_percentile(res, 0.5),
        resolve_p90_s=_percentile(res, 0.9),
        resolved=_count(db, in_range, resolved_cond),
        resolved_with_outcome=_count(db, in_range, resolved_cond, outcome_cond),
        with_outcome=_count(db, in_range, outcome_cond),
        false_alarm=_count(db, in_range, Alert.outcome == AlertOutcome.FALSE_ALARM),
        pending_at_end=_count(db, in_range, not_acked_at_end),
        acknowledged_at_end=_count(db, in_range, acked_at_end),
    )
