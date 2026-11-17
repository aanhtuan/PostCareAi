"""Interface chung của adapter pose (F11 R3; ADR-0003).

Worker (F17) và replay (F12) chỉ dùng `PoseAdapter`; đổi model thì viết adapter mới.
"""

from __future__ import annotations

from typing import Protocol

from postcare.schemas.observation import FrameObservation
from postcare.vision.camera import Frame

MAKE_MODELS_HINT = "Chạy `make models` (hoặc `scripts\\dev.ps1 models`) để tải model."


class ModelNotFoundError(FileNotFoundError):
    """Không có hoặc không mở được file model (R7)."""


class PoseAdapter(Protocol):
    """Chạy model pose trên một khung, trả quan sát theo schema chung."""

    def observe(self, frame: Frame, camera_id: int) -> FrameObservation:
        """`frame.ts_ms` phải tăng ngặt giữa các lần gọi (chế độ VIDEO)."""
        ...

    def close(self) -> None: ...
