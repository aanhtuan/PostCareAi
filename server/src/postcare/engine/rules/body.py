"""Bước 6: rule sự kiện cơ thể và vị trí (F15; event-engine.md mục 4, 5).

Rule chỉ đọc chuỗi trạng thái ổn định của F14 (`Engine.state_history` + explanation) và đặc trưng
đã làm mượt của F13 (R1). Không phát gì khi đang `NO_OBSERVATION` (R10). Kết quả chưa qua debounce;
`RuleSet` lọc bằng `Debouncer` (R8). Thời gian chỉ lấy từ `ts_ms`.
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import JsonValue

from postcare.engine.pipeline import FrameAssessment
from postcare.engine.state_machine import StateRecord
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.events import EventCode
from postcare.schemas.observation import PersonPose
from postcare.schemas.state import BodyState, ObservationQuality

MS_PER_S = 1000
_BUFFER_SLACK_MS = 1000
"""Dư cho bộ đệm visibility (một vài frame sau mốc min_duration; không phải ngưỡng)."""

_IN_BED = frozenset({BodyState.LYING, BodyState.RAISING, BodyState.SITTING})
_EXIT_PATH = frozenset({BodyState.AT_EDGE, BodyState.STANDING})
_STAND_FROM = frozenset({BodyState.SITTING, BodyState.AT_EDGE})
_RETURNED = frozenset({BodyState.SITTING, BodyState.LYING})
_STATE_FEATURE_KEYS = (
    "posture",
    "location",
    "trunk_angle_deg",
    "dist_to_roi_edge",
    "ankles_outside_roi",
    "torso_length_ratio",
)

Explanation = dict[str, JsonValue]


@dataclass(frozen=True)
class BodyEventDraft:
    """Sự kiện cơ thể trước debounce. `RuleSet` gắn `priority` (catalog) và `config_hash`."""

    code: EventCode
    occurred_at_ms: int
    detected_at_ms: int
    confidence: float
    observation_quality: ObservationQuality
    explanation: Explanation


def _angle_diff_deg(a: float, b: float) -> float:
    """Độ lệch hướng, gập về [0°, 180°]."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _last_observed(records: Sequence[StateRecord]) -> BodyState | None:
    """Trạng thái ổn định gần nhất, bỏ qua `NO_OBSERVATION` (event-engine.md mục 4)."""
    for record in reversed(records):
        if record.state != BodyState.NO_OBSERVATION:
            return record.state
    return None


def _chain_since_last_exit(history: Sequence[StateRecord]) -> list[JsonValue]:
    """Chuỗi trạng thái từ sau lần `OUT_OF_BED` trước (hoặc đầu lịch sử) tới hiện tại."""
    chain: list[JsonValue] = []
    for record in reversed(history[:-1]):
        if record.state == BodyState.OUT_OF_BED:
            break
        chain.append(record.state.value)
    chain.reverse()
    chain.append(history[-1].state.value)
    return chain


class BodyRules:
    """`SIT_UP`, `STAND_UP`, `BED_EDGE`, `BED_EXIT`, `RETURN_TO_BED`, `POSTURE_CHANGE` (R2–R7)."""

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self._required = tuple(config.pose.required_keypoints)
        self._return_hold_ms = config.min_duration_s.RETURN_TO_BED * MS_PER_S
        self._turn_delta_deg = config.posture_change.shoulder_angle_delta_deg
        self._turn_stable_ms = config.posture_change.stable_s * MS_PER_S
        longest_s = max(
            *config.min_duration_s.model_dump().values(), config.posture_change.stable_s
        )
        self._buffer_ms = longest_s * MS_PER_S + _BUFFER_SLACK_MS
        self._visibility: deque[tuple[int, float]] = deque()
        self._last_record: StateRecord | None = None
        # RETURN_TO_BED (R6)
        self._awaiting_return = False
        self._return_since_ms: int | None = None
        # POSTURE_CHANGE (R7)
        self._ref_angle_deg: float | None = None
        self._turn_since_ms: int | None = None

    def evaluate(
        self,
        ts_ms: int,
        assessment: FrameAssessment,
        body_state: BodyState,
        history: Sequence[StateRecord],
    ) -> list[BodyEventDraft]:
        self._record_visibility(ts_ms, assessment.target)
        drafts: list[BodyEventDraft] = []
        latest = history[-1] if history else None
        if latest is not None and latest is not self._last_record:
            self._last_record = latest
            drafts.extend(self._on_transition(ts_ms, assessment.quality, history))
        drafts.extend(self._return_to_bed(ts_ms, assessment, body_state, latest))
        drafts.extend(self._posture_change(ts_ms, assessment, body_state))
        return drafts

    # ---- R2–R5: theo lần chuyển trạng thái ----

    def _on_transition(
        self, ts_ms: int, quality: ObservationQuality, history: Sequence[StateRecord]
    ) -> list[BodyEventDraft]:
        record = history[-1]
        previous = history[:-1]
        to = record.state
        if to == BodyState.NO_OBSERVATION:
            return []
        immediate = previous[-1].state if previous else None
        last_observed = _last_observed(previous)
        code: EventCode | None = None
        extra: Explanation = {}
        if to == BodyState.SITTING:
            if (
                len(previous) >= 2
                and previous[-1].state == BodyState.RAISING
                and previous[-2].state == BodyState.LYING
            ):
                code = EventCode.SIT_UP
        elif to == BodyState.STANDING:
            if immediate in _STAND_FROM:
                code = EventCode.STAND_UP
        elif to == BodyState.AT_EDGE:
            # Chỉ khi ra mép từ trong giường; quay về qua mép (từ STANDING/OUT_OF_BED) thì không
            # (R4)
            if last_observed in _IN_BED:
                code = EventCode.BED_EDGE
        elif to == BodyState.OUT_OF_BED:
            self._awaiting_return = True
            self._return_since_ms = None
            # Điều kiện trước: AT_EDGE hoặc STANDING ngay trước, bỏ qua NO_OBSERVATION (R5)
            if last_observed in _EXIT_PATH:
                code = EventCode.BED_EXIT
                extra["state_chain"] = _chain_since_last_exit(history)
        if code is None:
            return []
        held_ms = _as_int(record.explanation.get("held_ms"))
        occurred = max(0, record.since_ms - held_ms)
        explanation: Explanation = {
            "rule_id": _rule_id(code),
            "from_state": record.explanation.get("from_state"),
            "to_state": to.value,
            "held_ms": ts_ms - occurred,
        }
        for key in _STATE_FEATURE_KEYS:
            if key in record.explanation:
                explanation[key] = record.explanation[key]
        explanation.update(extra)
        return [self._draft(code, occurred, ts_ms, quality, explanation)]

    # ---- R6 ----

    def _return_to_bed(
        self,
        ts_ms: int,
        assessment: FrameAssessment,
        body_state: BodyState,
        latest: StateRecord | None,
    ) -> list[BodyEventDraft]:
        if not self._awaiting_return:
            return []
        if body_state not in _RETURNED or latest is None:
            self._return_since_ms = None
            return []
        if self._return_since_ms is None:
            # Mốc = đầu khoảng giữ của trạng thái trong giường vừa xác lập
            held = _as_int(latest.explanation.get("held_ms"))
            self._return_since_ms = max(0, latest.since_ms - held)
        held_ms = ts_ms - self._return_since_ms
        if assessment.features is None or held_ms < self._return_hold_ms:
            return []
        self._awaiting_return = False
        occurred = self._return_since_ms
        self._return_since_ms = None
        explanation: Explanation = {
            "rule_id": _rule_id(EventCode.RETURN_TO_BED),
            "from_state": BodyState.OUT_OF_BED.value,
            "to_state": body_state.value,
            "held_ms": held_ms,
            "trunk_angle_deg": round(assessment.features.trunk_angle_deg, 1),
            "dist_to_roi_edge": round(assessment.features.dist_to_roi_edge, 3),
        }
        return [
            self._draft(EventCode.RETURN_TO_BED, occurred, ts_ms, assessment.quality, explanation)
        ]

    # ---- R7 ----

    def _posture_change(
        self, ts_ms: int, assessment: FrameAssessment, body_state: BodyState
    ) -> list[BodyEventDraft]:
        if body_state != BodyState.LYING:
            self._ref_angle_deg = None
            self._turn_since_ms = None
            return []
        f = assessment.features
        if f is None:
            self._turn_since_ms = None
            return []
        angle = f.shoulder_line_angle_deg
        if self._ref_angle_deg is None:
            self._ref_angle_deg = angle
            return []
        delta = _angle_diff_deg(angle, self._ref_angle_deg)
        if delta <= self._turn_delta_deg:
            self._turn_since_ms = None
            return []
        if self._turn_since_ms is None:
            self._turn_since_ms = ts_ms
        held_ms = ts_ms - self._turn_since_ms
        if held_ms < self._turn_stable_ms:
            return []
        explanation: Explanation = {
            "rule_id": _rule_id(EventCode.POSTURE_CHANGE),
            "from_state": BodyState.LYING.value,
            "to_state": BodyState.LYING.value,
            "held_ms": held_ms,
            "reference_angle_deg": round(self._ref_angle_deg, 1),
            "shoulder_line_angle_deg": round(angle, 1),
            "shoulder_angle_delta_deg": round(delta, 1),
        }
        occurred = self._turn_since_ms
        self._ref_angle_deg = angle
        self._turn_since_ms = None
        return [
            self._draft(EventCode.POSTURE_CHANGE, occurred, ts_ms, assessment.quality, explanation)
        ]

    # ---- confidence (R9) ----

    def _record_visibility(self, ts_ms: int, target: PersonPose | None) -> None:
        if target is not None:
            values = [
                kp.visibility if (kp := target.keypoints.get(name)) is not None else 0.0
                for name in self._required
            ]
            self._visibility.append((ts_ms, sum(values) / len(values)))
        while self._visibility and self._visibility[0][0] < ts_ms - self._buffer_ms:
            self._visibility.popleft()

    def _confidence(self, start_ms: int, end_ms: int) -> float:
        """Trung bình visibility của `pose.required_keypoints` trong khoảng giữ (giả định R9)."""
        values = [v for ts, v in self._visibility if start_ms <= ts <= end_ms]
        if not values:
            return 0.0
        return round(min(1.0, max(0.0, sum(values) / len(values))), 3)

    def _draft(
        self,
        code: EventCode,
        occurred_ms: int,
        detected_ms: int,
        quality: ObservationQuality,
        explanation: Explanation,
    ) -> BodyEventDraft:
        return BodyEventDraft(
            code=code,
            occurred_at_ms=occurred_ms,
            detected_at_ms=detected_ms,
            confidence=self._confidence(occurred_ms, detected_ms),
            observation_quality=quality,
            explanation=explanation,
        )


def _rule_id(code: EventCode) -> str:
    return f"body.{code.value.lower()}"


def _as_int(value: JsonValue) -> int:
    return int(value) if isinstance(value, int | float) else 0
