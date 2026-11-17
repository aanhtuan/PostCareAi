"""Ghép sự kiện dự đoán với ground truth (F16 R4; evaluation.md mục 5; A06).

- Khớp khi cùng `code` và `occurred_s` ∈ `[start_s − tol_before_s, end_s + tol_after_s]`.
- Mỗi ground truth khớp tối đa một dự đoán và ngược lại. Ghép tham lam theo khoảng cách thời gian
  nhỏ nhất tới đoạn `[start_s, end_s]` *(giả định của spec)*; hòa thì ưu tiên dự đoán sớm hơn.
- Video có `eval_codes` (dữ liệu ngoài): dự đoán mã khác bị bỏ qua, không tính FP *(giả định)*.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from postcare.eval.manifest import TruthRow
from postcare.schemas.enums import Priority
from postcare.schemas.events import EventCode

DEFAULT_TOL_BEFORE_S = 1.0
DEFAULT_TOL_AFTER_S = 3.0
_EPS = 1e-9


@dataclass(frozen=True)
class Prediction:
    video_id: str
    code: EventCode
    priority: Priority
    occurred_s: float
    detected_s: float


@dataclass(frozen=True)
class Match:
    truth: TruthRow
    prediction: Prediction

    @property
    def latency_s(self) -> float:
        """Detection latency = `detected_at − start_s` (R5; QA#37: đã gồm `min_duration`)."""
        return self.prediction.detected_s - self.truth.start_s


@dataclass
class MatchResult:
    tp: list[Match] = field(default_factory=list)
    fp: list[Prediction] = field(default_factory=list)
    fn: list[TruthRow] = field(default_factory=list)
    ignored: list[Prediction] = field(default_factory=list)
    """Dự đoán mã không được chấm trên video này (không thuộc `eval_codes`)."""


def _distance(p: Prediction, t: TruthRow) -> float:
    if p.occurred_s < t.start_s:
        return t.start_s - p.occurred_s
    if p.occurred_s > t.end_s:
        return p.occurred_s - t.end_s
    return 0.0


def match_events(
    predictions: Iterable[Prediction],
    truths: Sequence[TruthRow],
    *,
    tol_before_s: float = DEFAULT_TOL_BEFORE_S,
    tol_after_s: float = DEFAULT_TOL_AFTER_S,
    eval_codes: frozenset[EventCode] | None = None,
) -> MatchResult:
    """Ghép dự đoán và ground truth của **một** video."""
    result = MatchResult()
    preds: list[Prediction] = []
    for p in predictions:
        if eval_codes is not None and p.code not in eval_codes:
            result.ignored.append(p)
        else:
            preds.append(p)
    candidates: list[tuple[float, float, float, int, int]] = []
    for i, p in enumerate(preds):
        for j, t in enumerate(truths):
            if p.code != t.event_code:
                continue
            lo, hi = t.start_s - tol_before_s, t.end_s + tol_after_s
            if lo - _EPS <= p.occurred_s <= hi + _EPS:
                candidates.append((_distance(p, t), p.occurred_s, t.start_s, i, j))
    candidates.sort()
    used_p: set[int] = set()
    used_t: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _, _, _, i, j in candidates:
        if i in used_p or j in used_t:
            continue
        used_p.add(i)
        used_t.add(j)
        pairs.append((i, j))
    pairs.sort(key=lambda ij: (truths[ij[1]].start_s, preds[ij[0]].occurred_s))
    result.tp = [Match(truths[j], preds[i]) for i, j in pairs]
    result.fp = [p for i, p in enumerate(preds) if i not in used_p]
    result.fn = [t for j, t in enumerate(truths) if j not in used_t]
    return result
