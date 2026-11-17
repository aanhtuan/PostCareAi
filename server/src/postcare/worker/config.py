"""Cấu hình camera worker nhận từ `GET /internal/v1/cameras/{id}/config` (F06 R2, R6)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from postcare.schemas.enums import CameraSourceType, DisplayMode


class WorkerConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    camera_id: int
    bed_id: int | None
    source_type: CameraSourceType
    source: str
    roi_polygon: list[list[float]] | None
    thresholds: dict[str, Any] = Field(default_factory=dict)
    display_mode: DisplayMode
    config_version: int
    active_session_id: int | None
    capture_paused: bool = False

    @property
    def source_key(self) -> tuple[str, str]:
        """Đổi khóa này → đóng nguồn cũ, mở nguồn mới (F06 R6)."""
        return (self.source_type.value, self.source)

    @property
    def engine_key(self) -> tuple[Any, ...]:
        """Đổi khóa này → tạo `Engine` mới: cấu hình mới (R6) hoặc đổi phiên (F17 R7)."""
        roi = json.dumps(self.roi_polygon)
        thresholds = json.dumps(self.thresholds, sort_keys=True)
        return (self.config_version, self.active_session_id, self.bed_id, roi, thresholds)
