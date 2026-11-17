"""Bước 3b: chất lượng quan sát từng frame (F13 R6) và cổng chất lượng theo thời gian (R7).

Thời gian chỉ lấy từ `obs.ts_ms` (event-engine.md mục 1). Ngưỡng ở `quality.*` của `EngineConfig`.
"""

from postcare.engine.features import torso_length_px
from postcare.engine.target import TargetSelection
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.observation import FrameObservation
from postcare.schemas.state import ObservationQuality

MS_PER_S = 1000


def assess_quality(
    obs: FrameObservation, selection: TargetSelection, config: EngineConfig
) -> ObservationQuality:
    """Điều kiện đứng trước thắng khi nhiều điều kiện cùng đúng *(giả định R6)*."""
    if not obs.source_ok:
        return ObservationQuality.CAMERA_ISSUE
    if selection.persons_in_roi >= 2:  # QA#20: từ hai người trong ROI là không đủ căn cứ
        return ObservationQuality.MULTIPLE_PEOPLE
    target = selection.target
    if target is None:
        return ObservationQuality.NO_PERSON
    min_vis = config.pose.min_keypoint_visibility
    for name in config.pose.required_keypoints:
        kp = target.keypoints.get(name)
        # Keypoint bắt buộc bị thiếu coi như visibility = 0 (giả định)
        if kp is None or kp.visibility < min_vis:
            return ObservationQuality.LOW_CONFIDENCE
    torso = torso_length_px(target, obs.image_size)
    if torso is None or torso <= 0:
        return ObservationQuality.LOW_CONFIDENCE
    return ObservationQuality.GOOD


class QualityGate:
    """Cổng chất lượng có hysteresis theo thời gian (R7; PDF §4.3, §13.4).

    - Đang mở: chất lượng khác `GOOD` liên tục ≥ `low_quality_to_no_observation_s` → đóng.
    - Đang đóng: `GOOD` liên tục ≥ `restore_duration_s` → mở.
    - Khởi tạo ở trạng thái đóng (engine bắt đầu ở `NO_OBSERVATION`).

    "Liên tục" đo từ `ts_ms` của frame đầu tiên trong chuỗi tới frame hiện tại.
    """

    def __init__(self, config: EngineConfig) -> None:
        self._close_after_ms = config.quality.low_quality_to_no_observation_s * MS_PER_S
        self._open_after_ms = config.quality.restore_duration_s * MS_PER_S
        self._observable = False
        self._run_start_ms: int | None = None
        """Mốc đầu của chuỗi frame đang có thể làm đổi trạng thái cổng."""

    @property
    def observable(self) -> bool:
        return self._observable

    def update(self, quality: ObservationQuality, ts_ms: int) -> bool:
        good = quality == ObservationQuality.GOOD
        # Đang mở: chuỗi đáng quan tâm là frame kém; đang đóng: frame tốt.
        if good == self._observable:
            self._run_start_ms = None
            return self._observable
        if self._run_start_ms is None:
            self._run_start_ms = ts_ms
        limit = self._open_after_ms if good else self._close_after_ms
        if ts_ms - self._run_start_ms >= limit:
            self._observable = good
            self._run_start_ms = None
        return self._observable
