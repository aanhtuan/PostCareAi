"""Adapter MediaPipe Pose Landmarker → `FrameObservation` (F11 R4, R5, R7; ADR-0003; A04).

- Tasks API, `running_mode = VIDEO`, `detect_for_video(image, ts_ms)` với `ts_ms` của khung.
- Kiểu dữ liệu MediaPipe không ra khỏi module này: output chỉ gồm kiểu `postcare.schemas`.
- Không lưu khung hình (R11; QA#29).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, Self

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision as mp_vision

from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.observation import FrameObservation, PersonPose
from postcare.vision.camera import Frame
from postcare.vision.inference.base import MAKE_MODELS_HINT, ModelNotFoundError
from postcare.vision.inference.mapping import RawLandmark, landmarks_to_person


class Landmarker(Protocol):
    """Phần tối thiểu của `PoseLandmarker` mà adapter dùng (test inject bản giả)."""

    def detect_for_video(self, image: Any, timestamp_ms: int) -> Any: ...

    def close(self) -> None: ...


LandmarkerFactory = Callable[[Path, int], Landmarker]


def create_mediapipe_landmarker(model_path: Path, num_poses: int) -> Landmarker:
    """Tạo `PoseLandmarker` chế độ VIDEO trên CPU (QA#23, QA#35)."""
    options = mp_vision.PoseLandmarkerOptions(
        # Đọc bytes thay vì truyền đường dẫn: tránh lỗi đường dẫn có ký tự ngoài ASCII trên Windows.
        base_options=BaseOptions(model_asset_buffer=model_path.read_bytes()),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=num_poses,
        output_segmentation_masks=False,
    )
    landmarker: Landmarker = mp_vision.PoseLandmarker.create_from_options(options)
    return landmarker


class MediaPipePoseAdapter:
    """`PoseAdapter` dùng MediaPipe Pose Landmarker (lite / full / heavy, chọn bằng file model)."""

    def __init__(
        self,
        model_path: Path | str,
        *,
        num_poses: int,
        landmarker_factory: LandmarkerFactory | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.num_poses = num_poses
        if not self.model_path.is_file():
            raise ModelNotFoundError(
                f"Không tìm thấy model pose {self.model_path}. {MAKE_MODELS_HINT}"
            )
        factory = landmarker_factory or create_mediapipe_landmarker
        try:
            self._landmarker: Landmarker | None = factory(self.model_path, num_poses)
        except (RuntimeError, ValueError, OSError) as exc:
            raise ModelNotFoundError(
                f"Không mở được model pose {self.model_path} ({exc}). {MAKE_MODELS_HINT}"
            ) from exc
        self._last_ts: int | None = None

    @classmethod
    def from_config(
        cls,
        model_path: Path | str,
        config: EngineConfig,
        *,
        landmarker_factory: LandmarkerFactory | None = None,
    ) -> Self:
        """`num_poses` lấy từ `EngineConfig.pose.num_poses` (A04; QA#20)."""
        return cls(
            model_path, num_poses=config.pose.num_poses, landmarker_factory=landmarker_factory
        )

    def observe(self, frame: Frame, camera_id: int) -> FrameObservation:
        if self._landmarker is None:
            raise RuntimeError("Adapter pose đã đóng")
        if self._last_ts is not None and frame.ts_ms <= self._last_ts:
            raise ValueError(
                f"ts_ms phải tăng ngặt cho MediaPipe VIDEO: {frame.ts_ms} ≤ {self._last_ts} "
                f"(frame_index {frame.frame_index})"
            )
        rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, frame.ts_ms)
        self._last_ts = frame.ts_ms
        persons = [_to_person(pose) for pose in (result.pose_landmarks or [])]
        return FrameObservation(
            camera_id=camera_id,
            frame_index=frame.frame_index,
            ts_ms=frame.ts_ms,
            image_size=(frame.width, frame.height),
            persons=persons,
            face=None,
            source_ok=True,
        )

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None


def _to_person(pose: Any) -> PersonPose:
    raw: list[RawLandmark] = [(float(lm.x), float(lm.y), lm.visibility) for lm in pose]
    return landmarks_to_person(raw)
