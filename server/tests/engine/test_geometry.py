"""F13: hàm hình học phụ trợ (điểm trong polygon, khoảng cách có dấu, trục dài PCA)."""

import math

import pytest
from postcare.engine.geometry import BedGeometry, angle_to_axis_deg

from postcare.schemas.roi import RoiPolygon
from tests.engine.builders import BED_ROI, IMAGE_SIZE


def _rotated_rect_roi(
    center: tuple[float, float], length: float, width: float, angle_deg: float
) -> RoiPolygon:
    """Hình chữ nhật xoay theo pixel (y hướng xuống), trả về ROI chuẩn hóa theo IMAGE_SIZE."""
    w, h = IMAGE_SIZE
    a = math.radians(angle_deg)
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -uy, ux
    cx, cy = center
    pts = []
    for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x = cx + su * length / 2 * ux + sv * width / 2 * vx
        y = cy + su * length / 2 * uy + sv * width / 2 * vy
        pts.append((x / w, y / h))
    return RoiPolygon(points=pts)


def test_contains_and_signed_distance() -> None:
    geo = BedGeometry.from_roi(BED_ROI, IMAGE_SIZE)  # x 256–1024, y 216–576
    assert geo.contains((640, 400))
    assert not geo.contains((640, 600))
    assert not geo.contains((1100, 400))
    assert geo.signed_distance((640, 400)) == pytest.approx(176)
    assert geo.signed_distance((640, 550)) == pytest.approx(26)
    assert geo.signed_distance((640, 600)) == pytest.approx(-24)
    assert geo.signed_distance((1100, 650)) == pytest.approx(-math.hypot(76, 74))


@pytest.mark.parametrize("angle", [0.0, 30.0, 90.0, 135.0])
def test_long_axis_from_pca(angle: float) -> None:
    roi = _rotated_rect_roi((640, 360), 500, 200, angle)
    geo = BedGeometry.from_roi(roi, IMAGE_SIZE)
    # Trục là đường thẳng: so sánh theo modulo 180°
    diff = (geo.axis_angle_deg - angle) % 180.0
    assert min(diff, 180.0 - diff) == pytest.approx(0.0, abs=1e-6)


def test_long_axis_uses_pixels_not_normalized() -> None:
    # 0.4 × 1280 = 512 px rộng, 0.6 × 720 = 432 px cao → trục dài vẫn nằm ngang theo pixel,
    # dù trên toạ độ chuẩn hóa thì cạnh dọc (0.6) dài hơn cạnh ngang (0.4).
    roi = RoiPolygon(points=[(0.3, 0.2), (0.7, 0.2), (0.7, 0.8), (0.3, 0.8)])
    geo = BedGeometry.from_roi(roi, IMAGE_SIZE)
    assert geo.axis_angle_deg % 180.0 == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize(
    ("vec", "axis", "expected"),
    [
        ((1, 0), 0.0, 0.0),
        ((-1, 0), 0.0, 0.0),  # không phân biệt hướng đầu/chân
        ((0, -1), 0.0, 90.0),
        ((1, 1), 0.0, 45.0),
        ((-1, 1), 0.0, 45.0),
        ((math.cos(math.radians(30)), math.sin(math.radians(30))), 30.0, 0.0),
        ((math.cos(math.radians(100)), math.sin(math.radians(100))), 30.0, 70.0),
    ],
)
def test_angle_to_axis_folded(vec: tuple[float, float], axis: float, expected: float) -> None:
    assert angle_to_axis_deg(vec, axis) == pytest.approx(expected)
