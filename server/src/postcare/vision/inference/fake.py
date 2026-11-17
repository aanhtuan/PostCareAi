"""`FakePoseAdapter` cho test tích hợp worker/replay, không cần model (F11 R8; testing.md §1)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from postcare.schemas.observation import FrameObservation, PersonPose
from postcare.vision.camera import Frame


class FakePoseAdapter:
    """Trả `FrameObservation` với `persons` dựng sẵn theo `frame_index` (không có → không ai)."""

    def __init__(self, persons_by_index: Mapping[int, Sequence[PersonPose]]) -> None:
        self._persons = {i: list(p) for i, p in persons_by_index.items()}
        self.calls: list[int] = []
        self.closed = False

    def observe(self, frame: Frame, camera_id: int) -> FrameObservation:
        self.calls.append(frame.frame_index)
        return FrameObservation(
            camera_id=camera_id,
            frame_index=frame.frame_index,
            ts_ms=frame.ts_ms,
            image_size=(frame.width, frame.height),
            persons=self._persons.get(frame.frame_index, []),
            source_ok=True,
        )

    def close(self) -> None:
        self.closed = True
