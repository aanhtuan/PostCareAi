"""Bước 7a: chỉ số vận động và `activity_level` (F23 R2–R4; event-engine.md mục 3, 5).

Chỉ số vận động (đơn vị torso_length/giây) *(giả định F23 R2)*:

1. Tập keypoint: vai, khuỷu, cổ tay, hông, gối, cổ chân của người mục tiêu, chỉ lấy điểm có
   visibility ≥ `pose.min_keypoint_visibility`; làm mượt EMA (`smoothing.ema_alpha`).
2. Mỗi frame có đặc trưng (chất lượng `GOOD`): tốc độ mẫu = trung bình trên các keypoint thấy ở
   cả frame này và frame cách đó ≥ `activity.sample_interval_s` của
   `|Δp| / torso_length / Δt`. Đo trên bước ~1 s chứ không phải giữa hai frame liền nhau, vì nhiễu
   keypoint MediaPipe từng frame (1–2 px) cộng dồn theo quãng đường làm người ngồi yên đã vượt
   `activity.high_threshold` (đo trên GMDCSA24/URFD, F23 mục 10).
3. Chỉ số = **trung vị** các tốc độ mẫu trong `activity.window_s` gần nhất. Trung vị chứ không
   phải trung bình: keypoint lệch 1–3 frame (vẫn trong ngưỡng bám mục tiêu) làm hỏng vài mẫu, kéo
   trung bình vượt `high_threshold` suốt cả cửa sổ (đủ `increased_hold_s`), còn trung vị thì không
   đổi ("không tin một frame", AGENTS.md quy tắc 6). Cử động phải chiếm quá nửa cửa sổ mới đẩy
   được chỉ số lên.

`activity_level`: `LOW` khi chỉ số < `low_threshold`, `HIGH` khi > `high_threshold`, còn lại
`NORMAL`. `UNKNOWN` khi chưa đủ dữ liệu (mẫu chưa phủ đủ `window_s`), và reset khi cổng chất lượng
đóng (`NO_OBSERVATION`) hoặc đổi người mục tiêu: mất quan sát không bao giờ là "ít vận động"
(R4). Frame kém nhưng cổng còn mở: không thêm mẫu, giữ mức hiện tại.
"""

import math
import statistics
from collections import deque
from dataclasses import dataclass

from postcare.engine.features import BodyFeatures
from postcare.engine.geometry import Px, distance, to_px
from postcare.engine.smoothing import PointSmoother
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.observation import KeypointName, PersonPose
from postcare.schemas.state import ActivityLevel

K = KeypointName
MS_PER_S = 1000

ACTIVITY_KEYPOINTS = (
    K.LEFT_SHOULDER,
    K.RIGHT_SHOULDER,
    K.LEFT_ELBOW,
    K.RIGHT_ELBOW,
    K.LEFT_WRIST,
    K.RIGHT_WRIST,
    K.LEFT_HIP,
    K.RIGHT_HIP,
    K.LEFT_KNEE,
    K.RIGHT_KNEE,
    K.LEFT_ANKLE,
    K.RIGHT_ANKLE,
)


@dataclass(frozen=True)
class ActivityReading:
    """Kết quả bước vận động ở một frame."""

    level: ActivityLevel
    index: float | None
    """Chỉ số vận động trên cửa sổ (torso/s); None khi `UNKNOWN`."""
    sample_speed: float | None
    """Tốc độ mẫu của riêng frame này (torso/s); None khi frame không có mẫu."""


UNKNOWN_READING = ActivityReading(level=ActivityLevel.UNKNOWN, index=None, sample_speed=None)


class ActivityMeter:
    """Một instance cho một `Engine`. Gọi `reset()` khi `NO_OBSERVATION` hoặc đổi mục tiêu."""

    def __init__(self, config: EngineConfig) -> None:
        act = config.activity
        self._min_vis = config.pose.min_keypoint_visibility
        self._window_ms = act.window_s * MS_PER_S
        self._step_ms = act.sample_interval_s * MS_PER_S
        self._low = act.low_threshold
        self._high = act.high_threshold
        self._smoother = PointSmoother(config.smoothing.ema_alpha)
        self._points: deque[tuple[int, dict[str, Px]]] = deque()
        self._samples: deque[tuple[int, float]] = deque()
        self._first_sample_ms: int | None = None
        self._reading = UNKNOWN_READING

    @property
    def reading(self) -> ActivityReading:
        return self._reading

    def reset(self) -> None:
        self._smoother.reset()
        self._points.clear()
        self._samples.clear()
        self._first_sample_ms = None
        self._reading = UNKNOWN_READING

    def hold(self) -> ActivityReading:
        """Frame không có đặc trưng nhưng cổng còn mở: giữ mức, không có mẫu mới."""
        r = self._reading
        self._reading = ActivityReading(level=r.level, index=r.index, sample_speed=None)
        return self._reading

    def update(self, ts_ms: int, target: PersonPose, features: BodyFeatures) -> ActivityReading:
        size = features.image_size
        raw: dict[str, Px | None] = {}
        for name in ACTIVITY_KEYPOINTS:
            kp = target.keypoints.get(name)
            visible = kp is not None and kp.visibility >= self._min_vis
            raw[name] = to_px((kp.x, kp.y), size) if visible and kp is not None else None
        smoothed = {name: p for name, p in self._smoother.update(raw).items() if p is not None}
        self._points.append((ts_ms, smoothed))

        speed = self._sample_speed(ts_ms, smoothed, features.torso_length)
        if speed is not None:
            self._samples.append((ts_ms, speed))
            if self._first_sample_ms is None:
                self._first_sample_ms = ts_ms
        while self._samples and self._samples[0][0] <= ts_ms - self._window_ms:
            self._samples.popleft()

        index: float | None = None
        level = ActivityLevel.UNKNOWN
        filled = (
            self._first_sample_ms is not None and ts_ms - self._first_sample_ms >= self._window_ms
        )
        if filled and self._samples:
            index = statistics.median(s for _, s in self._samples)
            level = self._level(index)
        self._reading = ActivityReading(level=level, index=index, sample_speed=speed)
        return self._reading

    def _sample_speed(self, ts_ms: int, points: dict[str, Px], torso: float) -> float | None:
        # Mốc = frame mới nhất cách ≥ một bước; bỏ các mốc cũ hơn nó.
        ref: tuple[int, dict[str, Px]] | None = None
        while self._points and self._points[0][0] <= ts_ms - self._step_ms:
            ref = self._points.popleft()
        if ref is not None:
            self._points.appendleft(ref)
        if ref is None or torso <= 0:
            return None
        ref_ts, ref_points = ref
        dt_s = (ts_ms - ref_ts) / MS_PER_S
        moved = [distance(p, ref_points[name]) for name, p in points.items() if name in ref_points]
        if not moved or dt_s <= 0:
            return None
        speed = sum(moved) / len(moved) / torso / dt_s
        return speed if math.isfinite(speed) else None

    def _level(self, index: float) -> ActivityLevel:
        if index < self._low:
            return ActivityLevel.LOW
        if index > self._high:
            return ActivityLevel.HIGH
        return ActivityLevel.NORMAL
