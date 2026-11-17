"""F13 AC1: đặc trưng cơ thể tính trên toạ độ tổng hợp có đáp án tính tay."""

import math

import pytest

from postcare.engine.features import BodyFeatures, FeatureExtractor
from postcare.schemas.observation import FrameObservation, KeypointName, PersonPose
from postcare.schemas.roi import RoiPolygon
from tests.engine.builders import (
    AT_EDGE,
    BED_ROI,
    IMAGE_SIZE,
    LOW_VISIBILITY,
    LYING,
    SITTING,
    STANDING,
    Body,
    default_config,
    frame,
    person_from_px,
)
from tests.engine.test_geometry import _rotated_rect_roi

CONFIG = default_config()
K = KeypointName


def _extract(
    person: PersonPose, roi: RoiPolygon = BED_ROI, image_size: tuple[int, int] = IMAGE_SIZE
) -> BodyFeatures:
    fx = FeatureExtractor(CONFIG, roi)
    return fx.update(person, frame([person], ts_ms=0, image_size=image_size))


def test_centers_and_torso_length() -> None:
    f = _extract(LYING.person())
    assert f.hip_center == pytest.approx((640, 400))
    assert f.shoulder_center == pytest.approx((440, 400))
    assert f.torso_length == pytest.approx(200)
    assert f.inside_roi is True
    assert f.knees[0] == pytest.approx((820, 400 + 35 * 0.5))
    assert f.ankles[1] == pytest.approx((1000, 400 - 35 * 0.5))


def test_trunk_angle_relative_to_bed_axis() -> None:
    assert _extract(LYING.person()).trunk_angle_deg == pytest.approx(0.0, abs=1e-6)
    assert _extract(SITTING.person()).trunk_angle_deg == pytest.approx(90.0)

    # Giường xoay 30° trong khung (y hướng xuống). Thân dọc trục → 0°, vuông góc → 90°,
    # lệch 75° so với trục → 75°.
    roi = _rotated_rect_roi((640, 360), 700, 300, 30)
    hip = (640.0, 360.0)
    for rel, expected in ((180.0, 0.0), (-90.0, 90.0), (30.0 + 75.0 - 30.0, 75.0)):
        a = math.radians(30.0 + rel)
        vec = (200 * math.cos(a), 200 * math.sin(a))
        body = Body(hip=hip, shoulder=vec, knee=(0, 0), ankle=(0, 0), half_width=(0, 0))
        got = _extract(body.person(), roi=roi).trunk_angle_deg
        assert got == pytest.approx(expected, abs=1e-6)


def test_trunk_angle_uses_pixel_aspect_ratio() -> None:
    # Chênh (0.1, 0.1) theo toạ độ chuẩn hóa = (128, 72) px ở 1280×720 → 29.36°, không phải 45°.
    w, h = IMAGE_SIZE
    hip = (0.5 * w, 0.55 * h)
    shoulder = (hip[0] + 0.1 * w, hip[1] - 0.1 * h)
    person = person_from_px(
        {
            K.LEFT_HIP: hip,
            K.RIGHT_HIP: hip,
            K.LEFT_SHOULDER: shoulder,
            K.RIGHT_SHOULDER: shoulder,
        }
    )
    got = _extract(person).trunk_angle_deg
    assert got == pytest.approx(math.degrees(math.atan2(72, 128)), abs=0.01)
    assert abs(got - 45.0) > 10


def test_dist_to_roi_edge_sign() -> None:
    # BED_ROI: y 216–576, x 256–1024; torso 200 px
    assert _extract(LYING.person()).dist_to_roi_edge == pytest.approx(176 / 200)
    edge = _extract(AT_EDGE.person())
    assert edge.inside_roi is True
    assert edge.dist_to_roi_edge == pytest.approx(26 / 200)
    out = _extract(STANDING.person())  # hông ở y = 590
    assert out.inside_roi is False
    assert out.dist_to_roi_edge == pytest.approx(-14 / 200)


def test_ankles_outside_roi_ignores_low_visibility() -> None:
    assert _extract(LYING.person()).ankles_outside_roi == 0
    assert _extract(AT_EDGE.person()).ankles_outside_roi == 2
    # Âm tính: cổ chân visibility thấp không được tính là ngoài ROI
    one_hidden = person_from_px(AT_EDGE.points(), visibility={K.LEFT_ANKLE: LOW_VISIBILITY})
    f = _extract(one_hidden)
    assert f.ankles_outside_roi == 1
    assert f.ankles[0] is None
    both_hidden = person_from_px(
        AT_EDGE.points(), visibility={K.LEFT_ANKLE: LOW_VISIBILITY, K.RIGHT_ANKLE: LOW_VISIBILITY}
    )
    assert _extract(both_hidden).ankles_outside_roi == 0


def test_shoulder_line_angle() -> None:
    # LYING: vai trái ở dưới (y lớn hơn) vai phải → hướng phải→trái là (0, 70): 90°
    assert _extract(LYING.person()).shoulder_line_angle_deg == pytest.approx(90.0)
    assert _extract(SITTING.person()).shoulder_line_angle_deg == pytest.approx(0.0)


def _obs(person: PersonPose, ts_ms: int) -> FrameObservation:
    return frame([person], ts_ms=ts_ms)


def test_velocity_smoothed_from_ts_ms() -> None:
    alpha = CONFIG.smoothing.ema_alpha
    fx = FeatureExtractor(CONFIG, BED_ROI)
    p0 = LYING.person()
    first = fx.update(p0, _obs(p0, 1000))
    assert first.velocity == (0.0, 0.0)

    # Dịch 20 px sau 50 ms: hông đã làm mượt dịch alpha × 20 px
    p1 = LYING.moved_to((660, 400)).person()
    second = fx.update(p1, _obs(p1, 1050))
    assert second.hip_center[0] == pytest.approx(640 + alpha * 20)
    assert second.velocity[0] == pytest.approx(alpha * 20 / 200 / 0.050)
    assert second.velocity[1] == pytest.approx(0.0)

    # Đứng yên, khoảng cách 200 ms (không đều): vận tốc dùng chênh lệch ts_ms thật
    third = fx.update(p1, _obs(p1, 1250))
    moved = alpha * (20 - alpha * 20)
    assert third.velocity[0] == pytest.approx(moved / 200 / 0.200)


def test_static_pose_stable_and_reset() -> None:
    fx = FeatureExtractor(CONFIG, BED_ROI)
    p = LYING.person()
    outs = [fx.update(p, _obs(p, i * 66)) for i in range(10)]
    assert all(o.hip_center == pytest.approx((640, 400)) for o in outs)
    assert all(o.velocity == pytest.approx((0.0, 0.0)) for o in outs)

    # Sau reset không kéo giá trị cũ: vị trí mới dùng ngay, vận tốc = 0
    fx.reset()
    q = SITTING.moved_to((500, 300)).person()
    f = fx.update(q, _obs(q, 1000))
    assert f.hip_center == pytest.approx((500, 300))
    assert f.velocity == (0.0, 0.0)
