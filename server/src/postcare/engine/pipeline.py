"""Các bước pipeline của engine (event-engine.md mục 3) chưa tách ra module riêng.

- Bước 1 chọn người mục tiêu: `engine/target.py` (F13).
- Bước 2 tính đặc trưng: `engine/features.py` (F13).
- Bước 3 làm mượt + chất lượng: `engine/smoothing.py`, `engine/quality.py` (F13).
- Bước 4–5 tư thế thô + state machine: `StateMachine` (F14, `posture.py`, `state_machine.py`).
- Bước 6–9 rule, vận động, khuôn mặt, debounce: `RuleSet` (F15, F23, F26, F27; `engine/rules/`).

Mọi bước là thuần: chỉ nhận dữ liệu và `ts_ms`, không đọc đồng hồ hệ thống, không I/O.
"""

from dataclasses import dataclass

from postcare.engine.features import BodyFeatures
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.events import EngineEvent
from postcare.schemas.observation import FrameObservation, PersonPose
from postcare.schemas.state import BodyState, BodyStateSnapshot, ObservationQuality


@dataclass(frozen=True)
class FrameAssessment:
    """Kết quả bước 1–3 cho một khung hình."""

    quality: ObservationQuality
    """Chất lượng của riêng frame này (R6)."""
    target: PersonPose | None
    features: BodyFeatures | None
    """Đặc trưng đã làm mượt; chỉ có khi `quality = GOOD` (R7, R8)."""
    observable: bool
    """Cổng chất lượng đang mở (R7). False → engine báo `NO_OBSERVATION`."""
    persons_in_roi: int


class StateMachine:
    """Bước 4–5: trạng thái cơ thể ổn định, hysteresis + min_duration (F14).

    Khởi tạo ở `NO_OBSERVATION`. F10 chưa có chuyển trạng thái nào. Engine chỉ gọi `update` khi
    cổng chất lượng mở và frame `GOOD` (có `features`); cổng chất lượng do Engine xử lý (F13).
    """

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self.state = BodyState.NO_OBSERVATION

    def update(self, assessment: FrameAssessment, ts_ms: int) -> BodyState:
        # F14 điền: phân loại tư thế từ assessment.features, chỉ chuyển khi giữ đủ min_duration.
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
