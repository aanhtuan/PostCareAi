"""Adapter MediaPipe Face Landmarker → điểm blendshape đã lọc (F25 R1, R6, R8, R10; ADR-0003).

- Tasks API, `running_mode = VIDEO`, `output_face_blendshapes = True`, `num_faces = 1` (chỉ ảnh cắt
  vùng đầu của người mục tiêu), `detect_for_video(image, ts_ms)` với `ts_ms` của khung.
- Chỉ giữ các blendshape có tên trong `face.signals.*.keys` (config là nguồn duy nhất, R6).
- Kiểu dữ liệu MediaPipe không ra khỏi module này. Không lưu ảnh (QA#29).
- Không nhận diện danh tính, không suy ra cảm giác hay ý thức: chỉ trả điểm blendshape (PRD).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Protocol

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision as mp_vision

from postcare.schemas.engine_config import EngineConfig
from postcare.vision.camera import Image
from postcare.vision.inference.base import MAKE_MODELS_HINT, ModelNotFoundError
from postcare.vision.inference.face_gate import blendshape_keys_from_config

__all__ = [
    "MediaPipeFaceAdapter",
    "blendshape_keys_from_config",
    "create_mediapipe_face_landmarker",
    "open_face_adapter",
]

logger = logging.getLogger(__name__)


class FaceLandmarkerLike(Protocol):
    """Phần tối thiểu của `FaceLandmarker` mà adapter dùng (test inject bản giả)."""

    def detect_for_video(self, image: Any, timestamp_ms: int) -> Any: ...

    def close(self) -> None: ...


FaceLandmarkerFactory = Callable[[Path], FaceLandmarkerLike]


def create_mediapipe_face_landmarker(model_path: Path) -> FaceLandmarkerLike:
    """`FaceLandmarker` chế độ VIDEO, có blendshapes, một mặt, chạy CPU (QA#23)."""
    options = mp_vision.FaceLandmarkerOptions(
        # Đọc bytes: tránh lỗi đường dẫn có ký tự ngoài ASCII trên Windows (như adapter pose).
        base_options=BaseOptions(model_asset_buffer=model_path.read_bytes()),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=False,
    )
    landmarker: FaceLandmarkerLike = mp_vision.FaceLandmarker.create_from_options(options)
    return landmarker


class MediaPipeFaceAdapter:
    """`FaceDetector` dùng MediaPipe Face Landmarker trên ảnh cắt vùng đầu."""

    def __init__(
        self,
        model_path: Path | str,
        keys: Iterable[str],
        *,
        landmarker_factory: FaceLandmarkerFactory | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.keys = frozenset(keys)
        if not self.model_path.is_file():
            raise ModelNotFoundError(
                f"Không tìm thấy model face {self.model_path}. {MAKE_MODELS_HINT}"
            )
        factory = landmarker_factory or create_mediapipe_face_landmarker
        try:
            self._landmarker: FaceLandmarkerLike | None = factory(self.model_path)
        except (RuntimeError, ValueError, OSError) as exc:
            raise ModelNotFoundError(
                f"Không mở được model face {self.model_path} ({exc}). {MAKE_MODELS_HINT}"
            ) from exc
        self._last_ts: int | None = None

    def detect(self, crop: Image, ts_ms: int) -> dict[str, float] | None:
        if self._landmarker is None:
            raise RuntimeError("Adapter face đã đóng")
        if self._last_ts is not None and ts_ms <= self._last_ts:
            raise ValueError(f"ts_ms phải tăng ngặt cho MediaPipe VIDEO: {ts_ms} ≤ {self._last_ts}")
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._last_ts = ts_ms
        result = self._landmarker.detect_for_video(image, ts_ms)
        if not result.face_landmarks:
            return None
        categories = result.face_blendshapes[0] if result.face_blendshapes else []
        return {
            str(c.category_name): float(c.score) for c in categories if c.category_name in self.keys
        }

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None


def open_face_adapter(
    model_path: Path | str,
    config: EngineConfig,
    *,
    landmarker_factory: FaceLandmarkerFactory | None = None,
) -> MediaPipeFaceAdapter | None:
    """Mở adapter face; thiếu hoặc hỏng model → WARNING và `None` (R8: pose vẫn chạy)."""
    try:
        return MediaPipeFaceAdapter(
            model_path,
            blendshape_keys_from_config(config),
            landmarker_factory=landmarker_factory,
        )
    except ModelNotFoundError as exc:
        logger.warning("Tắt nhánh face: %s", exc)
        return None
