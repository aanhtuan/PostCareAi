"""Hình học phẳng cho engine, tính theo pixel (F13 R2, giả định: module phụ trợ).

Keypoint và ROI chuẩn hóa theo chiều rộng và chiều cao riêng, nên góc và khoảng cách phải tính
sau khi nhân với `image_size`, nếu không góc bị méo theo tỷ lệ khung hình.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

from postcare.schemas.roi import RoiPolygon

Px = tuple[float, float]
"""Điểm (x, y) theo pixel, y hướng xuống."""


def to_px(point: tuple[float, float], image_size: tuple[int, int]) -> Px:
    return (point[0] * image_size[0], point[1] * image_size[1])


def midpoint(a: Px, b: Px) -> Px:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def distance(a: Px, b: Px) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def direction_deg(vec: Px) -> float:
    """Hướng của vector trong hệ ảnh (y hướng xuống), độ trong (-180, 180]."""
    return math.degrees(math.atan2(vec[1], vec[0]))


def angle_to_axis_deg(vec: Px, axis_deg: float) -> float:
    """Góc giữa vector và một trục (đường thẳng), gập về [0°, 90°]: không phân biệt chiều."""
    diff = (direction_deg(vec) - axis_deg) % 180.0
    return min(diff, 180.0 - diff)


def _point_segment_distance(p: Px, a: Px, b: Px) -> float:
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return distance(p, a)
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / length_sq
    t = min(1.0, max(0.0, t))
    return distance(p, (ax + t * dx, ay + t * dy))


def point_in_polygon(p: Px, vertices: Sequence[Px]) -> bool:
    """Ray casting (even-odd). Điểm đúng trên biên có thể rơi vào trong hoặc ngoài."""
    x, y = p
    inside = False
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_cross:
                inside = not inside
    return inside


def principal_axis_deg(vertices: Sequence[Px]) -> float:
    """Hướng trục chính (PCA trên các đỉnh), độ trong (-90, 90] *(giả định F13 R3)*."""
    n = len(vertices)
    mx = sum(v[0] for v in vertices) / n
    my = sum(v[1] for v in vertices) / n
    sxx = sum((v[0] - mx) ** 2 for v in vertices)
    syy = sum((v[1] - my) ** 2 for v in vertices)
    sxy = sum((v[0] - mx) * (v[1] - my) for v in vertices)
    # Vector riêng ứng với trị riêng lớn nhất của ma trận hiệp phương sai 2×2
    return math.degrees(0.5 * math.atan2(2 * sxy, sxx - syy))


@dataclass(frozen=True)
class BedGeometry:
    """Polygon ROI theo pixel cho một kích thước khung hình, kèm trục dài của giường."""

    vertices: tuple[Px, ...]
    axis_angle_deg: float

    @classmethod
    def from_roi(cls, roi: RoiPolygon, image_size: tuple[int, int]) -> Self:
        vertices = tuple(to_px(p, image_size) for p in roi.points)
        return cls(vertices=vertices, axis_angle_deg=principal_axis_deg(vertices))

    def contains(self, p: Px) -> bool:
        return point_in_polygon(p, self.vertices)

    def signed_distance(self, p: Px) -> float:
        """Khoảng cách (pixel) tới biên gần nhất: dương khi ở trong, âm khi ở ngoài."""
        n = len(self.vertices)
        d = min(
            _point_segment_distance(p, self.vertices[i], self.vertices[(i + 1) % n])
            for i in range(n)
        )
        return d if self.contains(p) else -d


class GeometryCache:
    """Giữ `BedGeometry` theo `image_size` (thường chỉ có một kích thước mỗi camera)."""

    def __init__(self, roi: RoiPolygon) -> None:
        self._roi = roi
        self._cache: dict[tuple[int, int], BedGeometry] = {}

    def get(self, image_size: tuple[int, int]) -> BedGeometry:
        geo = self._cache.get(image_size)
        if geo is None:
            geo = BedGeometry.from_roi(self._roi, image_size)
            self._cache[image_size] = geo
        return geo
