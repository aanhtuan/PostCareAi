"""Các bước pipeline của engine (event-engine.md mục 3). F10 chỉ dựng khung có chữ ký sẵn.

- Bước 1 chọn người mục tiêu: `TargetSelector` (F13, sau tách ra `engine/target.py`).
- Bước 2 tính đặc trưng: F13 thêm `engine/features.py`.
- Bước 3 làm mượt + chất lượng: `QualityAssessor` (F13, `engine/quality.py`, `smoothing.py`).
- Bước 4–5 tư thế thô + state machine: `StateMachine` (F14, `posture.py`, `state_machine.py`).
- Bước 6–9 rule, vận động, khuôn mặt, debounce: `RuleSet` (F15, F23, F26, F27; `engine/rules/`).

Mọi bước là thuần: chỉ nhận dữ liệu và `ts_ms`, không đọc đồng hồ hệ thống, không I/O.
"""

from dataclasses import dataclass

from postcare.schemas.context import EngineContext
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.events import EngineEvent
from postcare.schemas.observation import FrameObservation, PersonPose
from postcare.schemas.state import BodyState, BodyStateSnapshot, ObservationQuality


@dataclass(frozen=True)
class FrameAssessment:
    """Kết quả bước 1–3 cho một khung hình."""

    quality: ObservationQuality
    target: PersonPose | None


class TargetSelector:
    """Bước 1: chọn người mục tiêu trong ROI, liên tục với vị trí trước (F13)."""

    def __init__(self, config: EngineConfig, context: EngineContext) -> None:
        self._config = config
        self._context = context

    def select(self, obs: FrameObservation) -> PersonPose | None:
        # F10: chưa chọn người mục tiêu; F13 điền.
        return None


class QualityAssessor:
    """Bước 3: đánh giá chất lượng quan sát của khung hình (F13 điền phần còn lại)."""

    def __init__(self, config: EngineConfig) -> None:
        self._config = config

    def assess(self, obs: FrameObservation, target: PersonPose | None) -> ObservationQuality:
        if not obs.source_ok:
            return ObservationQuality.CAMERA_ISSUE
        if not obs.persons:
            return ObservationQuality.NO_PERSON
        if target is None:
            # F10 (giả định): có người nhưng chưa có bước chọn mục tiêu → chưa đủ căn cứ.
            return ObservationQuality.LOW_CONFIDENCE
        return ObservationQuality.GOOD


class StateMachine:
    """Bước 4–5: trạng thái cơ thể ổn định, hysteresis + min_duration (F14).

    Khởi tạo ở `NO_OBSERVATION`. F10 chưa có chuyển trạng thái nào.
    """

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self.state = BodyState.NO_OBSERVATION

    def update(self, assessment: FrameAssessment, ts_ms: int) -> BodyState:
        # F14 điền: chỉ chuyển khi giữ đủ min_duration; chất lượng kém → NO_OBSERVATION.
        return self.state


class RuleSet:
    """Bước 6–9: rule sự kiện, vận động, khuôn mặt, debounce, quan sát (F15, F23, F26, F27)."""

    def __init__(self, config: EngineConfig) -> None:
        self._config = config

    def evaluate(
        self,
        obs: FrameObservation,
        assessment: FrameAssessment,
        previous: BodyStateSnapshot | None,
        current: BodyStateSnapshot,
    ) -> list[EngineEvent]:
        # F10: chưa có rule nào.
        return []
