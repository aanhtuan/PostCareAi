"""Bước 2: đặc trưng cơ thể của người mục tiêu (F13 R3; event-engine.md mục 3).

Mọi toạ độ theo pixel (R2). Đặc trưng suy ra từ vị trí keypoint **đã làm mượt** (R4), nên vận tốc
cũng tính trên vị trí đã làm mượt. Chỉ gọi `FeatureExtractor.update` với frame chất lượng `GOOD`
(engine bảo đảm): đặc trưng của frame kém không được đưa sang bước phân loại (R7, R8).
"""

from dataclasses import dataclass

from postcare.engine.geometry import (
    GeometryCache,
    Px,
    angle_to_axis_deg,
    direction_deg,
    distance,
    midpoint,
    to_px,
)
from postcare.engine.smoothing import PointSmoother
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.observation import FrameObservation, KeypointName, PersonPose
from postcare.schemas.roi import RoiPolygon

K = KeypointName
MS_PER_S = 1000

_REQUIRED_FOR_FEATURES = (K.LEFT_SHOULDER, K.RIGHT_SHOULDER, K.LEFT_HIP, K.RIGHT_HIP)
_OPTIONAL = (K.LEFT_KNEE, K.RIGHT_KNEE, K.LEFT_ANKLE, K.RIGHT_ANKLE)


@dataclass(frozen=True)
class BodyFeatures:
    """Đặc trưng đã làm mượt của người mục tiêu ở một frame. Toạ độ theo pixel."""

    ts_ms: int
    image_size: tuple[int, int]
    hip_center: Px
    shoulder_center: Px
    torso_length: float
    """Khoảng cách tâm vai – tâm hông (pixel)."""
    trunk_angle_deg: float
    """Góc giữa vector hông→vai và trục dài của giường, gập về [0°, 90°]."""
    inside_roi: bool
    dist_to_roi_edge: float
    """Khoảng cách có dấu từ tâm hông tới biên ROI (dương khi ở trong), đơn vị torso_length."""
    ankles_outside_roi: int
    """Số cổ chân nhìn thấy (visibility ≥ ngưỡng) nằm ngoài ROI."""
    knees: tuple[Px | None, Px | None]
    """(trái, phải); None khi không thấy (visibility < ngưỡng)."""
    ankles: tuple[Px | None, Px | None]
    shoulder_line_angle_deg: float
    """Hướng vector vai phải → vai trái trong hệ ảnh, độ trong (-180, 180]."""
    velocity: Px
    """Vận tốc tâm hông đã làm mượt (vx, vy), đơn vị torso_length/giây; 0 ở frame đầu sau reset."""


def _point(person: PersonPose, name: KeypointName, image_size: tuple[int, int]) -> Px | None:
    kp = person.keypoints.get(name)
    return None if kp is None else to_px((kp.x, kp.y), image_size)


def _center(
    person: PersonPose, left: KeypointName, right: KeypointName, image_size: tuple[int, int]
) -> Px | None:
    a = _point(person, left, image_size)
    b = _point(person, right, image_size)
    return None if a is None or b is None else midpoint(a, b)


def hip_center_px(person: PersonPose, image_size: tuple[int, int]) -> Px | None:
    """Tâm hông theo pixel; None khi thiếu một hông. Không xét visibility (dùng để định vị)."""
    return _center(person, K.LEFT_HIP, K.RIGHT_HIP, image_size)


def torso_length_px(person: PersonPose, image_size: tuple[int, int]) -> float | None:
    hip = hip_center_px(person, image_size)
    shoulder = _center(person, K.LEFT_SHOULDER, K.RIGHT_SHOULDER, image_size)
    return None if hip is None or shoulder is None else distance(hip, shoulder)


class FeatureExtractor:
    """Tính đặc trưng + làm mượt cho một người mục tiêu liên tục."""

    def __init__(self, config: EngineConfig, roi: RoiPolygon) -> None:
        self._min_vis = config.pose.min_keypoint_visibility
        self._geometry = GeometryCache(roi)
        self._smoother = PointSmoother(config.smoothing.ema_alpha)
        self._prev_hip: Px | None = None
        self._prev_ts_ms: int | None = None

    def reset(self) -> None:
        self._smoother.reset()
        self._prev_hip = None
        self._prev_ts_ms = None

    def update(self, person: PersonPose, obs: FrameObservation) -> BodyFeatures:
        size = obs.image_size
        raw: dict[str, Px | None] = {}
        for name in _REQUIRED_FOR_FEATURES:
            p = _point(person, name, size)
            if p is None:
                raise ValueError(f"thiếu keypoint {name} (chỉ gọi với frame chất lượng GOOD)")
            raw[name] = p
        for name in _OPTIONAL:
            kp = person.keypoints.get(name)
            visible = kp is not None and kp.visibility >= self._min_vis
            raw[name] = _point(person, name, size) if visible else None
        sm = self._smoother.update(raw)

        def req(name: KeypointName) -> Px:
            p = sm[name]
            assert p is not None
            return p

        l_sh, r_sh = req(K.LEFT_SHOULDER), req(K.RIGHT_SHOULDER)
        hip = midpoint(req(K.LEFT_HIP), req(K.RIGHT_HIP))
        shoulder = midpoint(l_sh, r_sh)
        torso = distance(hip, shoulder)
        geo = self._geometry.get(size)
        ankles = (sm[K.LEFT_ANKLE], sm[K.RIGHT_ANKLE])

        velocity: Px = (0.0, 0.0)
        if self._prev_hip is not None and self._prev_ts_ms is not None and torso > 0:
            dt_s = (obs.ts_ms - self._prev_ts_ms) / MS_PER_S
            if dt_s > 0:
                velocity = (
                    (hip[0] - self._prev_hip[0]) / torso / dt_s,
                    (hip[1] - self._prev_hip[1]) / torso / dt_s,
                )
        self._prev_hip = hip
        self._prev_ts_ms = obs.ts_ms

        trunk_vec = (shoulder[0] - hip[0], shoulder[1] - hip[1])
        return BodyFeatures(
            ts_ms=obs.ts_ms,
            image_size=size,
            hip_center=hip,
            shoulder_center=shoulder,
            torso_length=torso,
            trunk_angle_deg=angle_to_axis_deg(trunk_vec, geo.axis_angle_deg),
            inside_roi=geo.contains(hip),
            dist_to_roi_edge=geo.signed_distance(hip) / torso if torso > 0 else 0.0,
            ankles_outside_roi=sum(1 for a in ankles if a is not None and not geo.contains(a)),
            knees=(sm[K.LEFT_KNEE], sm[K.RIGHT_KNEE]),
            ankles=ankles,
            shoulder_line_angle_deg=direction_deg((l_sh[0] - r_sh[0], l_sh[1] - r_sh[1])),
            velocity=velocity,
        )
