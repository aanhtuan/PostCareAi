"""Cổng chất lượng khuôn mặt: khi nào chạy Face Landmarker và gán `FaceStatus` (F25 R2, R5, R7, R8).

Nhánh face là nhánh **phụ**: mọi lỗi ở đây được bắt, đếm, ghi WARNING và quy về `NOT_VISIBLE`,
nên pose, engine, heartbeat không bao giờ bị gián đoạn vì face (HS §4.1; PDF §6.2, §17).

Ở frame chạy face, thứ tự kiểm tra:
1. không có người mục tiêu → `NOT_VISIBLE` (không gọi model);
2. không đủ keypoint đầu nhìn rõ để ước lượng vùng đầu → `LOW_CONFIDENCE` (không gọi model);
3. `head_box_px < face.min_head_box_px` → `TOO_SMALL` (không gọi model);
4. không có adapter (thiếu model), ảnh cắt rỗng, adapter raise → `NOT_VISIBLE`, `error_count += 1`;
5. model không thấy mặt trong ảnh cắt → `NOT_VISIBLE`;
6. thấy mặt → `OK` + blendshape đã lọc theo `face.signals.*.keys`.

Frame không chạy face (chu kỳ `face.run_every_n_frames`, đếm theo khung đã xử lý) → `None`.
Module này không import mediapipe.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.enums import FaceStatus
from postcare.schemas.observation import FaceObservation, PersonPose
from postcare.vision.camera import Frame
from postcare.vision.inference.base import FaceDetector
from postcare.vision.inference.head_region import crop_head, estimate_head_box

logger = logging.getLogger(__name__)

ERROR_LOG_EVERY = 100
"""Sau lỗi đầu tiên, chỉ ghi WARNING mỗi chừng này lỗi để không ngập log (giả định)."""


def blendshape_keys_from_config(config: EngineConfig) -> frozenset[str]:
    """Hợp các khóa `face.signals.*.keys`: nguồn duy nhất của tên blendshape (R6)."""
    signals = config.face.signals
    return frozenset(
        key for name in type(signals).model_fields for key in getattr(signals, name).keys
    )


class FaceGate:
    """Một instance cho một camera (một chuỗi khung có `ts_ms` tăng ngặt)."""

    def __init__(
        self,
        detector: FaceDetector | None,
        *,
        keys: Iterable[str],
        min_head_box_px: int,
        run_every_n_frames: int,
        head_crop_scale: float,
        min_keypoint_visibility: float,
    ) -> None:
        if run_every_n_frames < 1:
            raise ValueError("run_every_n_frames phải ≥ 1")
        self._detector = detector
        self._keys = frozenset(keys)
        self._min_head_box_px = min_head_box_px
        self._every = run_every_n_frames
        self._scale = head_crop_scale
        self._min_vis = min_keypoint_visibility
        self._frames = 0
        self.error_count = 0
        """Số lần nhánh face lỗi (thiếu model, ảnh cắt rỗng, adapter raise)."""

    @classmethod
    def from_config(cls, config: EngineConfig, detector: FaceDetector | None) -> FaceGate:
        face = config.face
        return cls(
            detector,
            keys=blendshape_keys_from_config(config),
            min_head_box_px=face.min_head_box_px,
            run_every_n_frames=face.run_every_n_frames,
            head_crop_scale=face.head_crop_scale,
            min_keypoint_visibility=config.pose.min_keypoint_visibility,
        )

    def observe(self, frame: Frame, target: PersonPose | None) -> FaceObservation | None:
        """Quan sát mặt của người mục tiêu ở khung này; `None` nếu khung này không chạy face."""
        index = self._frames
        self._frames += 1
        if index % self._every != 0:
            return None
        if target is None:
            return _obs(FaceStatus.NOT_VISIBLE)
        try:
            return self._observe_target(frame, target)
        except Exception as exc:  # R8: mọi lỗi face (kể cả keypoint NaN) bị cô lập
            self._error(frame, f"{type(exc).__name__}: {exc}")
            return _obs(FaceStatus.NOT_VISIBLE)

    def _observe_target(self, frame: Frame, target: PersonPose) -> FaceObservation:
        box = estimate_head_box(
            target, (frame.width, frame.height), min_visibility=self._min_vis, scale=self._scale
        )
        if box is None:
            return _obs(FaceStatus.LOW_CONFIDENCE)
        side = box.side_px
        if side < self._min_head_box_px:
            return _obs(FaceStatus.TOO_SMALL, side)
        if self._detector is None:
            self._error(frame, "không có adapter face (thiếu model?)")
            return _obs(FaceStatus.NOT_VISIBLE, side)
        crop = crop_head(frame.image, box)
        if crop.size == 0:
            self._error(frame, "ảnh cắt vùng đầu rỗng")
            return _obs(FaceStatus.NOT_VISIBLE, side)
        try:
            scores = self._detector.detect(crop, frame.ts_ms)
        except Exception as exc:  # R8: mọi lỗi face bị cô lập, không lan sang pose/engine
            self._error(frame, f"{type(exc).__name__}: {exc}")
            return _obs(FaceStatus.NOT_VISIBLE, side)
        if scores is None:
            return _obs(FaceStatus.NOT_VISIBLE, side)
        shapes = {k: min(1.0, max(0.0, float(v))) for k, v in scores.items() if k in self._keys}
        return _obs(FaceStatus.OK, side, shapes)

    def close(self) -> None:
        if self._detector is not None:
            self._detector.close()
            self._detector = None

    def _error(self, frame: Frame, reason: str) -> None:
        self.error_count += 1
        if self.error_count == 1 or self.error_count % ERROR_LOG_EVERY == 0:
            logger.warning(
                "Nhánh face lỗi ở frame %d (%s); lỗi thứ %d. Pose và engine vẫn chạy.",
                frame.frame_index,
                reason,
                self.error_count,
            )


def _obs(
    status: FaceStatus, head_box_px: int = 0, blendshapes: dict[str, float] | None = None
) -> FaceObservation:
    return FaceObservation(status=status, head_box_px=head_box_px, blendshapes=blendshapes or {})
