"""Tiện ích test F25: người có keypoint đầu, khung giả, bộ phát hiện mặt giả. Không có media."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.observation import FrameObservation, Keypoint, KeypointName, PersonPose
from postcare.vision.camera import Frame
from tests.engine.builders import IMAGE_SIZE, LYING, default_config

K = KeypointName
HEAD = (K.NOSE, K.LEFT_EYE, K.RIGHT_EYE, K.LEFT_EAR, K.RIGHT_EAR)


def with_head(
    person: PersonPose,
    *,
    half_width_px: float,
    image_size: tuple[int, int] = IMAGE_SIZE,
    visibility: float = 0.95,
    center_px: tuple[float, float] | None = None,
) -> PersonPose:
    """Thêm mắt, tai quanh mũi: bbox đầu rộng `2 × half_width_px` (tai trái ↔ tai phải)."""
    w, h = image_size
    if center_px is None:
        nose = person.keypoints[K.NOSE]
        cx, cy = nose.x * w, nose.y * h
    else:
        cx, cy = center_px
    offsets = {
        K.NOSE: (0.0, 0.0),
        K.LEFT_EYE: (half_width_px * 0.4, -half_width_px * 0.3),
        K.RIGHT_EYE: (-half_width_px * 0.4, -half_width_px * 0.3),
        K.LEFT_EAR: (half_width_px, -half_width_px * 0.1),
        K.RIGHT_EAR: (-half_width_px, -half_width_px * 0.1),
    }
    kps = dict(person.keypoints)
    for name, (dx, dy) in offsets.items():
        x = min(1.0, max(0.0, (cx + dx) / w))
        y = min(1.0, max(0.0, (cy + dy) / h))
        kps[name] = Keypoint(x=x, y=y, visibility=visibility)
    return PersonPose(keypoints=kps)


def head_person(half_width_px: float, visibility: float = 0.95) -> PersonPose:
    """Người nằm (builder F13) có đủ keypoint đầu."""
    return with_head(LYING.person(), half_width_px=half_width_px, visibility=visibility)


def image_frame(index: int, ts_ms: int, size: tuple[int, int] = IMAGE_SIZE) -> Frame:
    w, h = size
    return Frame(image=np.full((h, w, 3), 90, dtype=np.uint8), ts_ms=ts_ms, frame_index=index)


def face_config(**face: object) -> EngineConfig:
    """Cấu hình mặc định, ghi đè một số khóa `face.*`."""
    return EngineConfig.from_mapping(
        {**default_config().model_dump(mode="json"), "face": {**_face_dump(), **face}}
    )


def _face_dump() -> dict[str, object]:
    data: dict[str, object] = default_config().model_dump(mode="json")["face"]
    return data


def config_keys(config: EngineConfig) -> set[str]:
    return {k for sig in config.face.signals.model_dump().values() for k in sig["keys"]}


class FakeFaceDetector:
    """Thay adapter MediaPipe: ghi lại ảnh cắt và ts, trả điểm blendshape dựng sẵn.

    `scores=None` → không thấy mặt. `error` → luôn raise.
    """

    def __init__(
        self,
        scores: Mapping[str, float] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.scores = dict(scores) if scores is not None else None
        self.error = error
        self.calls: list[tuple[tuple[int, ...], int]] = []
        self.closed = False

    def detect(self, crop: np.ndarray, ts_ms: int) -> dict[str, float] | None:
        self.calls.append((tuple(crop.shape), ts_ms))
        if self.error is not None:
            raise self.error
        return None if self.scores is None else dict(self.scores)

    def close(self) -> None:
        self.closed = True


def observation_of(frame: Frame, persons: Sequence[PersonPose]) -> FrameObservation:
    return FrameObservation(
        camera_id=1,
        frame_index=frame.frame_index,
        ts_ms=frame.ts_ms,
        image_size=(frame.width, frame.height),
        persons=list(persons),
        source_ok=True,
    )
