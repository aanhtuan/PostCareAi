"""Interface chung của adapter pose (F11 R3) và adapter mặt (F25) (ADR-0003).

Worker (F17) và replay (F12) chỉ dùng `PoseAdapter` / `FaceDetector`; đổi model thì viết adapter
mới.
"""

from __future__ import annotations

from typing import Protocol

from postcare.schemas.observation import FrameObservation
from postcare.vision.camera import Frame, Image

MAKE_MODELS_HINT = "Chạy `make models` (hoặc `scripts\\dev.ps1 models`) để tải model."


class ModelNotFoundError(FileNotFoundError):
    """Không có hoặc không mở được file model (R7)."""


class PoseAdapter(Protocol):
    """Chạy model pose trên một khung, trả quan sát theo schema chung."""

    def observe(self, frame: Frame, camera_id: int) -> FrameObservation:
        """`frame.ts_ms` phải tăng ngặt giữa các lần gọi (chế độ VIDEO)."""
        ...

    def close(self) -> None: ...


class FaceDetector(Protocol):
    """Chạy model mặt trên ảnh cắt vùng đầu (F25 R1, R6). Kiểu MediaPipe không lộ ra ngoài."""

    def detect(self, crop: Image, ts_ms: int) -> dict[str, float] | None:
        """Ảnh BGR đã cắt, `ts_ms` tăng ngặt → điểm blendshape đã lọc; `None` khi không thấy mặt.

        Lỗi (model hỏng, ảnh sai…) được phép raise: `FaceGate` bắt và quy về `NOT_VISIBLE` (R8).
        """
        ...

    def close(self) -> None: ...
