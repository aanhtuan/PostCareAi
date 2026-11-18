"""Bước 8b: sự kiện `FACE_ATTENTION` (F26 R4–R8; event-engine.md mục 5, 8).

- Đoạn giữ: số tín hiệu mặt đang bật (`FaceReading.attention_count`, nhóm mắt tính một) ≥
  `face.attention_min_signals`, `face_status = OK` và `body_state ≠ NO_OBSERVATION` liên tục.
  Đoạn bị cắt khi một điều kiện không còn đúng.
- Đoạn giữ ≥ `face.attention_hold_s` → phát **một lần** cho đoạn đó *(giả định F26)*. Debounce
  `debounce.same_code_same_session_s` do `RuleSet` lọc (R7).
- Mức ưu tiên `MEDIUM`; nâng `HIGH` khi trong `face.attention_hold_s` ngay trước lúc phát có
  `activity_level = HIGH` (`activity_high`) hoặc ≥ 2 trạng thái cơ thể ổn định khác nhau, không tính
  `NO_OBSERVATION` (`state_change`) (R5; conflicts C05). Mức chốt tại lúc phát (R7).

`occurred_at_ms` = đầu đoạn giữ, `detected_at_ms` = lúc phát. `confidence` = visibility trung bình
keypoint bắt buộc trong đoạn (như các rule khác, giả định F15 R9).
"""

from collections import deque

from postcare.engine.activity import ActivityReading
from postcare.engine.face import FaceReading
from postcare.engine.pipeline import FrameAssessment
from postcare.engine.rules.common import MS_PER_S, EventDraft, VisibilityBuffer
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.enums import Priority
from postcare.schemas.events import EventCode
from postcare.schemas.state import ActivityLevel, BodyState, FaceStatus

RULE_ID = "face_attention"
_BUFFER_SLACK_MS = 1000
"""Dư cho bộ đệm visibility (không phải ngưỡng)."""


class FaceRules:
    """Một instance cho một `Engine`; kết quả chưa debounce (`RuleSet` lọc)."""

    def __init__(self, config: EngineConfig) -> None:
        self._min_signals = config.face.attention_min_signals
        self._hold_ms = config.face.attention_hold_s * MS_PER_S
        self._visibility = VisibilityBuffer(
            config.pose.required_keypoints, self._hold_ms + _BUFFER_SLACK_MS
        )
        self._recent: deque[tuple[int, ActivityLevel, BodyState]] = deque()
        self._start_ms: int | None = None
        self._emitted = False

    def evaluate(
        self,
        ts_ms: int,
        assessment: FrameAssessment,
        body_state: BodyState,
        activity: ActivityReading,
        face: FaceReading,
    ) -> list[EventDraft]:
        self._visibility.record(ts_ms, assessment.target)
        self._recent.append((ts_ms, activity.level, body_state))
        while self._recent and self._recent[0][0] < ts_ms - self._hold_ms:
            self._recent.popleft()
        held = (
            face.status == FaceStatus.OK
            and body_state != BodyState.NO_OBSERVATION
            and face.attention_count >= self._min_signals
        )
        if not held:
            self._start_ms = None
            self._emitted = False
            return []
        if self._start_ms is None:
            self._start_ms = ts_ms
        held_ms = ts_ms - self._start_ms
        if self._emitted or held_ms < self._hold_ms:
            return []
        self._emitted = True
        escalated_by = self._escalation()
        explanation: dict[str, object] = {
            "rule_id": RULE_ID,
            "signals": list(face.active),
            "signal_values": dict(face.values),
            "held_ms": held_ms,
            "min_signals": self._min_signals,
            "activity_level": activity.level.value,
            "body_state": body_state.value,
        }
        if escalated_by:
            explanation["escalated_by"] = escalated_by
        return [
            EventDraft(
                code=EventCode.FACE_ATTENTION,
                occurred_at_ms=self._start_ms,
                detected_at_ms=ts_ms,
                confidence=self._visibility.confidence(self._start_ms, ts_ms),
                observation_quality=assessment.quality,
                explanation=explanation,  # type: ignore[arg-type]
                priority=Priority.HIGH if escalated_by else Priority.MEDIUM,
            )
        ]

    def _escalation(self) -> list[str]:
        reasons: list[str] = []
        if any(level == ActivityLevel.HIGH for _, level, _ in self._recent):
            reasons.append("activity_high")
        states = {s for _, _, s in self._recent if s != BodyState.NO_OBSERVATION}
        if len(states) >= 2:
            reasons.append("state_change")
        return reasons
