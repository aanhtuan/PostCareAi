"""Polygon vùng giường (Bed ROI), toạ độ chuẩn hóa 0–1 (PDF §7.2; QA#15).

`RoiPolygon` (F10) chỉ kiểm tra số điểm và miền toạ độ. `validate_roi_polygon` kiểm tra thêm
polygon đơn (không tự cắt, không trùng đỉnh, diện tích > 0); F12 tạo cho file cấu hình camera,
F08 dùng lại khi lưu ROI vẽ trên web (giả định của spec F12: feature nào làm trước thì tạo).
"""

from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from postcare.schemas.observation import UnitFloat

RoiPoint = tuple[UnitFloat, UnitFloat]

_EPS = 1e-9


class RoiPolygon(BaseModel):
    """Đa giác ROI: ≥3 đỉnh (x, y) theo thứ tự vẽ."""

    model_config = ConfigDict(frozen=True)

    points: Annotated[list[RoiPoint], Field(min_length=3)]


def validate_roi_polygon(points: Sequence[Sequence[float]]) -> RoiPolygon:
    """Kiểm tra polygon ROI rồi trả `RoiPolygon`; sai → `ValueError` nêu lý do (tiếng Việt).

    Điều kiện: ≥ 3 đỉnh; mỗi đỉnh 2 số trong [0, 1]; không có hai đỉnh trùng nhau; các cạnh
    không cắt nhau (trừ hai cạnh kề chung đỉnh); diện tích > 0.
    """
    pts: list[tuple[float, float]] = []
    for i, p in enumerate(points):
        if len(p) != 2:
            raise ValueError(f"đỉnh {i} phải có đúng 2 toạ độ (x, y)")
        x, y = float(p[0]), float(p[1])
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError(f"đỉnh {i} ({x}, {y}) nằm ngoài [0, 1]")
        pts.append((x, y))
    n = len(pts)
    if n < 3:
        raise ValueError(f"polygon ROI cần ít nhất 3 đỉnh, nhận {n}")
    for i in range(n):
        for j in range(i + 1, n):
            if abs(pts[i][0] - pts[j][0]) < _EPS and abs(pts[i][1] - pts[j][1]) < _EPS:
                raise ValueError(f"đỉnh {i} và {j} trùng nhau")
    for i in range(n):
        a1, a2 = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or j == (i + 1) % n:
                continue  # cạnh kề chung một đỉnh
            b1, b2 = pts[j], pts[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                raise ValueError(f"polygon ROI tự cắt (cạnh {i} và cạnh {j})")
    if abs(_area(pts)) < _EPS:
        raise ValueError("polygon ROI có diện tích bằng 0 (các đỉnh thẳng hàng)")
    return RoiPolygon(points=pts)


def _area(pts: Sequence[tuple[float, float]]) -> float:
    n = len(pts)
    return 0.5 * sum(
        pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n)
    )


def _orient(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def _on_segment(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> bool:
    """r nằm trên đoạn pq (đã biết thẳng hàng)."""
    return (
        min(p[0], q[0]) - _EPS <= r[0] <= max(p[0], q[0]) + _EPS
        and min(p[1], q[1]) - _EPS <= r[1] <= max(p[1], q[1]) + _EPS
    )


def _segments_intersect(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    d1, d2 = _orient(b1, b2, a1), _orient(b1, b2, a2)
    d3, d4 = _orient(a1, a2, b1), _orient(a1, a2, b2)
    if ((d1 > _EPS and d2 < -_EPS) or (d1 < -_EPS and d2 > _EPS)) and (
        (d3 > _EPS and d4 < -_EPS) or (d3 < -_EPS and d4 > _EPS)
    ):
        return True
    return (
        (abs(d1) <= _EPS and _on_segment(b1, b2, a1))
        or (abs(d2) <= _EPS and _on_segment(b1, b2, a2))
        or (abs(d3) <= _EPS and _on_segment(a1, a2, b1))
        or (abs(d4) <= _EPS and _on_segment(a1, a2, b2))
    )
