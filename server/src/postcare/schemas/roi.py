"""Polygon vùng giường (Bed ROI), toạ độ chuẩn hóa 0–1 (PDF §7.2; QA#15).

F10 chỉ kiểm tra số điểm và miền toạ độ. Kiểm tra tự cắt (`validate_roi_polygon`) do F08 thêm.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from postcare.schemas.observation import UnitFloat

RoiPoint = tuple[UnitFloat, UnitFloat]


class RoiPolygon(BaseModel):
    """Đa giác ROI: ≥3 đỉnh (x, y) theo thứ tự vẽ."""

    model_config = ConfigDict(frozen=True)

    points: Annotated[list[RoiPoint], Field(min_length=3)]
