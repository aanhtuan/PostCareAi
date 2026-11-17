"""Bối cảnh cố định của một instance Engine (event-engine.md mục 2)."""

from pydantic import BaseModel, ConfigDict

from postcare.schemas.roi import RoiPolygon


class EngineContext(BaseModel):
    """Truyền khi tạo `Engine(config, context)`, không nằm trong từng frame.

    Đổi ROI hoặc ngưỡng thì worker tạo `Engine` mới *(giả định)*.
    """

    model_config = ConfigDict(frozen=True)

    camera_id: int
    roi_polygon: RoiPolygon
