"""Cấu hình camera worker nhận từ `GET /internal/v1/cameras/{id}/config` (F06 R2, R6)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from postcare.schemas.enums import CameraSourceType, DisplayMode, ObservationProfile
from postcare.vision.render import DEFAULT_DISPLAY_MODE, resolve_display_mode

logger = logging.getLogger(__name__)

_USERINFO = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*://)[^/@]+@")


def mask_source(source: str) -> str:
    """Che user:pass trong URL nguồn trước khi ghi log (`rtsp://u:p@host` → `rtsp://***@host`)."""
    return _USERINFO.sub(r"\1***@", source)


class WorkerConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    camera_id: int
    bed_id: int | None
    source_type: CameraSourceType
    source: str
    roi_polygon: list[list[float]] | None
    thresholds: dict[str, Any] = Field(default_factory=dict)
    display_mode: DisplayMode = DEFAULT_DISPLAY_MODE
    observation_profile: ObservationProfile = ObservationProfile.BED_MONITORING
    """Thiếu hoặc không hợp lệ → `BLUR` (F28 R1)."""
    config_version: int
    active_session_id: int | None
    capture_paused: bool = False

    @field_validator("display_mode", mode="before")
    @classmethod
    def _display_mode_or_blur(cls, value: Any) -> DisplayMode:
        mode = resolve_display_mode(value)
        if value is None or (not isinstance(value, DisplayMode) and value != mode.value):
            logger.warning("display_mode %r không hợp lệ: dùng %s", value, mode.value)
        return mode

    @property
    def source_key(self) -> tuple[str, str]:
        """Đổi khóa này → đóng nguồn cũ, mở nguồn mới (F06 R6)."""
        return (self.source_type.value, self.source)

    @property
    def engine_key(self) -> tuple[Any, ...]:
        """Đổi khóa này → tạo `Engine` mới: ROI/ngưỡng mới (R6) hoặc đổi phiên/giường (F17 R7).

        Không gồm `config_version` và `display_mode`: đổi chế độ hiển thị (cũng tăng
        `config_version`) không được làm đổi trạng thái engine (F28 R8).
        """
        roi = json.dumps(self.roi_polygon)
        thresholds = json.dumps(self.thresholds, sort_keys=True)
        return (self.active_session_id, self.bed_id, self.observation_profile, roi, thresholds)
