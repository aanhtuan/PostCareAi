"""Độ đầy đủ landmark cho `postcare probe --pose` và benchmark (F11 R10; QA#35)."""

from __future__ import annotations

from collections.abc import Iterable

from postcare.schemas.observation import FrameObservation, KeypointName, PersonPose


class PoseCoverage:
    """Đếm khung có người và khung có ít nhất một người thấy đủ keypoint thân.

    "Đủ thân": mọi keypoint trong `required` (cấu hình `pose.required_keypoints`) có
    visibility ≥ `min_visibility` (`pose.min_keypoint_visibility`).
    """

    def __init__(self, required: Iterable[KeypointName], min_visibility: float) -> None:
        self.required = tuple(required)
        self.min_visibility = min_visibility
        self.frames = 0
        self.frames_with_person = 0
        self.frames_with_torso = 0

    def _torso_visible(self, person: PersonPose) -> bool:
        kps = person.keypoints
        return all(
            name in kps and kps[name].visibility >= self.min_visibility for name in self.required
        )

    def add(self, obs: FrameObservation) -> None:
        self.frames += 1
        if obs.persons:
            self.frames_with_person += 1
        if any(self._torso_visible(p) for p in obs.persons):
            self.frames_with_torso += 1

    @property
    def person_ratio(self) -> float:
        return self.frames_with_person / self.frames if self.frames else 0.0

    @property
    def torso_ratio(self) -> float:
        return self.frames_with_torso / self.frames if self.frames else 0.0
