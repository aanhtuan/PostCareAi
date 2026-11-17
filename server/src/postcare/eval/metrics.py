"""Metric thuần của F16 (R5; HS §8.2; PDF §13.2–13.3). Không đọc file, không đo máy."""

from __future__ import annotations

import itertools
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from postcare.eval.matching import MatchResult, Prediction
from postcare.schemas.enums import BodyState
from postcare.schemas.events import ALERT_PRIORITIES, EventCode


@dataclass(frozen=True)
class CodeStats:
    code: EventCode
    tp: int
    fp: int
    fn: int
    precision: float | None
    recall: float | None
    f1: float | None
    latency_median_s: float | None
    latency_p90_s: float | None


def prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    """Precision, Recall, F1; mẫu số 0 → `None` (báo cáo ghi "—", giả định của spec)."""
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def percentile(values: Sequence[float], q: float) -> float | None:
    """Phân vị `q` ∈ [0, 1], nội suy tuyến tính giữa hai phần tử (như numpy mặc định)."""
    if not values:
        return None
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def latency_stats(values: Sequence[float]) -> tuple[float | None, float | None]:
    """(trung vị, p90) của detection latency (giây)."""
    return percentile(values, 0.5), percentile(values, 0.9)


def code_stats(results: Iterable[MatchResult]) -> list[CodeStats]:
    """TP/FP/FN, P/R/F1, latency theo từng code (chỉ các code có xuất hiện), thứ tự `EventCode`."""
    tp: dict[EventCode, int] = {}
    fp: dict[EventCode, int] = {}
    fn: dict[EventCode, int] = {}
    lat: dict[EventCode, list[float]] = {}
    for r in results:
        for m in r.tp:
            tp[m.truth.event_code] = tp.get(m.truth.event_code, 0) + 1
            lat.setdefault(m.truth.event_code, []).append(m.latency_s)
        for p in r.fp:
            fp[p.code] = fp.get(p.code, 0) + 1
        for t in r.fn:
            fn[t.event_code] = fn.get(t.event_code, 0) + 1
    out: list[CodeStats] = []
    for code in EventCode:
        if code not in tp and code not in fp and code not in fn:
            continue
        a, b, c = tp.get(code, 0), fp.get(code, 0), fn.get(code, 0)
        median, p90 = latency_stats(lat.get(code, []))
        out.append(CodeStats(code, a, b, c, *prf(a, b, c), median, p90))
    return out


def false_alerts_per_hour(
    false_positives: Iterable[Prediction], total_hours: float
) -> float | None:
    """Số FP mức MEDIUM/HIGH chia tổng số giờ video; tổng giờ 0 → `None`."""
    if total_hours <= 0:
        return None
    n = sum(1 for p in false_positives if p.priority in ALERT_PRIORITIES)
    return n / total_hours


def coverage_seconds(frames: Sequence[tuple[int, BodyState]]) -> tuple[float, float]:
    """(giây có quan sát, tổng giây) theo thời gian: khung kéo dài tới khung sau.

    Khung cuối dùng trung vị bước giữa các khung (một khung duy nhất → 0 s). `frames` là
    `(ts_ms, body_state)` từ `frames.jsonl` (F12), đã sắp theo thời gian.
    """
    if not frames:
        return 0.0, 0.0
    steps = [(b[0] - a[0]) / 1000 for a, b in itertools.pairwise(frames)]
    last = statistics.median(steps) if steps else 0.0
    durations = [*steps, last]
    total = sum(durations)
    observed = sum(
        d
        for (_, state), d in zip(frames, durations, strict=True)
        if state != BodyState.NO_OBSERVATION
    )
    return observed, total
