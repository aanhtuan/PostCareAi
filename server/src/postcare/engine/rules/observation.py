"""Bước 9 (phần quan sát): `OBSERVATION_LOST` / `OBSERVATION_RESTORED` (F17 R16; QA#21; A11).

- Một "chuỗi mất quan sát" bắt đầu ở frame đầu có `body_state = NO_OBSERVATION`, kể cả lúc engine
  khởi động với cổng chất lượng đóng *(giả định)*, và kết thúc ở frame đầu không còn
  `NO_OBSERVATION`.
- `OBSERVATION_LOST`: chuỗi giữ ≥ `quality.observation_lost_event_s` → một bản nháp mỗi chuỗi;
  `occurred_at_ms` = đầu chuỗi, `detected_at_ms` = frame đạt ngưỡng.
- `OBSERVATION_RESTORED`: ở frame thoát chuỗi, **chỉ khi** `OBSERVATION_LOST` của chuỗi đó đã qua
  debounce (`RuleSet` gọi `confirm_lost`). Mất quan sát ngắn không sinh gì (giảm nhiễu timeline).
- `confidence = 1.0` *(giả định: hệ thống biết chắc là mình không quan sát được; không có keypoint
  để lấy trung bình visibility)*.

Thời gian chỉ lấy từ `ts_ms` (engine thuần).
"""

from postcare.engine.pipeline import FrameAssessment
from postcare.engine.rules.common import MS_PER_S, EventDraft
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.events import EventCode
from postcare.schemas.state import BodyState

CONFIDENCE = 1.0


class ObservationRules:
    """Một instance cho một `Engine` (trạng thái theo phiên)."""

    def __init__(self, config: EngineConfig) -> None:
        self._lost_after_ms = config.quality.observation_lost_event_s * MS_PER_S
        self._threshold_s = config.quality.observation_lost_event_s
        self._run_start_ms: int | None = None
        """Đầu chuỗi `NO_OBSERVATION` hiện tại; None khi đang quan sát được."""
        self._lost_drafted = False
        self._lost_emitted = False

    def confirm_lost(self) -> None:
        """`RuleSet` báo `OBSERVATION_LOST` của chuỗi hiện tại đã qua debounce và được phát."""
        self._lost_emitted = True

    def evaluate(
        self, ts_ms: int, assessment: FrameAssessment, body_state: BodyState
    ) -> list[EventDraft]:
        if body_state == BodyState.NO_OBSERVATION:
            if self._run_start_ms is None:
                self._run_start_ms = ts_ms
                self._lost_drafted = False
                self._lost_emitted = False
            held_ms = ts_ms - self._run_start_ms
            if self._lost_drafted or held_ms < self._lost_after_ms:
                return []
            self._lost_drafted = True
            return [
                EventDraft(
                    code=EventCode.OBSERVATION_LOST,
                    occurred_at_ms=self._run_start_ms,
                    detected_at_ms=ts_ms,
                    confidence=CONFIDENCE,
                    observation_quality=assessment.quality,
                    explanation={
                        "rule_id": "observation.observation_lost",
                        "held_ms": held_ms,
                        "threshold_s": self._threshold_s,
                        "observation_quality": assessment.quality.value,
                    },
                )
            ]
        if self._run_start_ms is None:
            return []
        start_ms, emitted = self._run_start_ms, self._lost_emitted
        self._run_start_ms = None
        self._lost_drafted = False
        self._lost_emitted = False
        if not emitted:
            return []
        return [
            EventDraft(
                code=EventCode.OBSERVATION_RESTORED,
                occurred_at_ms=ts_ms,
                detected_at_ms=ts_ms,
                confidence=CONFIDENCE,
                observation_quality=assessment.quality,
                explanation={
                    "rule_id": "observation.observation_restored",
                    "lost_ms": ts_ms - start_ms,
                    "body_state": body_state.value,
                },
            )
        ]
