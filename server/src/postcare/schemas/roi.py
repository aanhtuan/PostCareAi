"""Polygon vùng giường (Bed ROI), toạ độ chuẩn hóa 0–1 (PDF §7.2; QA#15).

`RoiPolygon` (F10) chỉ kiểm tra số điểm và miền toạ độ. `validate_roi_polygon` kiểm tra thêm
polygon đơn (không tự cắt, không trùng đỉnh, diện tích > 0); F12 tạo cho file cấu hình camera,
F08 dùng lại khi lưu ROI vẽ trên web (giả định của spec F12: feature nào làm trước thì tạo).
Lỗi là `RoiPolygonError` (con của `ValueError`) có `reason` là mã máy để API trả `details.reason`
và web hiện câu tiếng Việt tương ứng (F08 R2). Web có bản tương đương: `web/src/utils/polygon.ts`.
"""

import math
from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from postcare.schemas.observation import UnitFloat

RoiPoint = tuple[UnitFloat, UnitFloat]

_EPS = 1e-9
MAX_ROI_POINTS = 20
"""Tối đa 20 đỉnh *(giả định F08 R2: đủ cho một giường, chặn dữ liệu bất thường)*."""

RoiReason = Literal[
    "TOO_FEW_POINTS",
    "TOO_MANY_POINTS",
    "INVALID_POINT",
    "OUT_OF_RANGE",
    "DUPLICATE_POINT",
    "SELF_INTERSECTION",
    "ZERO_AREA",
]


class RoiPolygonError(ValueError):
    """Polygon ROI không hợp lệ; `reason` là mã máy, thông điệp là tiếng Việt."""

    def __init__(self, reason: RoiReason, message: str) -> None:
        super().__init__(message)
        self.reason: RoiReason = reason


class RoiPolygon(BaseModel):
    """Đa giác ROI: ≥3 đỉnh (x, y) theo thứ tự vẽ."""

    model_config = ConfigDict(frozen=True)

    points: Annotated[list[RoiPoint], Field(min_length=3)]


def validate_roi_polygon(points: Sequence[Any]) -> RoiPolygon:
    """Kiểm tra polygon ROI rồi trả `RoiPolygon`; sai → `RoiPolygonError` nêu lý do (tiếng Việt).

    Điều kiện: 3–20 đỉnh; mỗi đỉnh 2 số hữu hạn (không phải bool) trong [0, 1]; không có hai đỉnh
    trùng nhau; các cạnh không cắt nhau (trừ hai cạnh kề chung đỉnh); diện tích > 0.
    """
    pts: list[tuple[float, float]] = []
    for i, p in enumerate(points):
        if not isinstance(p, list | tuple) or len(p) != 2 or not all(_is_number(v) for v in p):
            raise RoiPolygonError("INVALID_POINT", f"đỉnh {i} phải có đúng 2 toạ độ số (x, y)")
        x, y = float(p[0]), float(p[1])
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise RoiPolygonError("OUT_OF_RANGE", f"đỉnh {i} ({x}, {y}) nằm ngoài [0, 1]")
        pts.append((x, y))
    n = len(pts)
    if n < 3:
        raise RoiPolygonError("TOO_FEW_POINTS", f"polygon ROI cần ít nhất 3 đỉnh, nhận {n}")
    if n > MAX_ROI_POINTS:
        raise RoiPolygonError(
            "TOO_MANY_POINTS", f"polygon ROI có tối đa {MAX_ROI_POINTS} đỉnh, nhận {n}"
        )
    for i in range(n):
        for j in range(i + 1, n):
            if abs(pts[i][0] - pts[j][0]) < _EPS and abs(pts[i][1] - pts[j][1]) < _EPS:
                raise RoiPolygonError("DUPLICATE_POINT", f"đỉnh {i} và {j} trùng nhau")
    for i in range(n):
        a1, a2 = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            if (j + 1) % n == i or j == (i + 1) % n:
                continue  # cạnh kề chung một đỉnh
            b1, b2 = pts[j], pts[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                raise RoiPolygonError(
                    "SELF_INTERSECTION", f"polygon ROI tự cắt (cạnh {i} và cạnh {j})"
                )
    if abs(_area(pts)) < _EPS:
        raise RoiPolygonError("ZERO_AREA", "polygon ROI có diện tích bằng 0 (các đỉnh thẳng hàng)")
    return RoiPolygon(points=pts)


def _is_number(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)


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
