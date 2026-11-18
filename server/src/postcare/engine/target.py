"""Bước 1: chọn người mục tiêu và đếm người trong Bed ROI (F13 R5; QA#20; event-engine.md mục 3).

- Đã có mục tiêu: chọn người có tâm hông gần vị trí cũ nhất, nếu quãng dịch chuyển
  ≤ `target.max_jump_torso_lengths × torso_length`. Mục tiêu vẫn được bám khi đã ra ngoài ROI.
- Chưa có mục tiêu: chỉ nhận người có tâm hông trong ROI. Người ngoài ROI không bao giờ thành
  mục tiêu mới (PDF §13.1; HS §8.1).
- Vị trí nhớ chỉ cập nhật khi hai hông có visibility ≥ `pose.min_keypoint_visibility`.
- Frame không khớp ai: vị trí cũ vẫn được nhớ, và trong lúc nhớ không nhận người mới *(giả định)*.
  Engine gọi `forget()` khi cổng chất lượng đã đóng (NO_OBSERVATION) mà frame không có mục tiêu.
"""

from dataclasses import dataclass

from postcare.engine.features import hip_center_px, torso_length_px
from postcare.engine.geometry import GeometryCache, Px, distance
from postcare.schemas.context import EngineContext
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.observation import FrameObservation, KeypointName, PersonPose


@dataclass(frozen=True)
class TargetSelection:
    target: PersonPose | None
    persons_in_roi: int
    """Số người (trong `pose.num_poses` người đầu) có tâm hông trong ROI."""
    is_new: bool
    """True khi vừa nhận mục tiêu mới (không nối tiếp mục tiêu trước)."""


@dataclass(frozen=True)
class _Candidate:
    index: int
    person: PersonPose
    hip: Px
    torso: float | None
    inside: bool
    depth: float


class TargetSelector:
    def __init__(self, config: EngineConfig, context: EngineContext) -> None:
        self._num_poses = config.pose.num_poses
        self._max_jump = config.target.max_jump_torso_lengths
        self._min_vis = config.pose.min_keypoint_visibility
        self._geometry = GeometryCache(context.roi_polygon)
        self._last_hip: Px | None = None
        self._last_torso: float | None = None

    @property
    def has_target(self) -> bool:
        return self._last_hip is not None

    def forget(self) -> None:
        self._last_hip = None
        self._last_torso = None

    def peek(self, obs: FrameObservation) -> PersonPose | None:
        """Người mà `select(obs)` sẽ chọn, nhưng không đổi trạng thái (nhánh face F25 chạy trước
        engine). Gọi ngay trước `select(obs)` thì luôn trùng `select(obs).target`."""
        chosen, _, _ = self._choose(obs)
        return None if chosen is None else chosen.person

    def select(self, obs: FrameObservation) -> TargetSelection:
        chosen, in_roi, is_new = self._choose(obs)
        if chosen is None:
            return TargetSelection(target=None, persons_in_roi=in_roi, is_new=False)
        # Chỉ cập nhật vị trí nhớ khi hai hông nhìn thấy rõ: vị trí đoán lúc bị che không được kéo
        # mục tiêu đi (review F13). Lúc nhận mới thì luôn ghi để có mốc bám.
        if is_new or self._hips_visible(chosen.person):
            self._last_hip = chosen.hip
            if chosen.torso:
                self._last_torso = chosen.torso
        return TargetSelection(target=chosen.person, persons_in_roi=in_roi, is_new=is_new)

    def _choose(self, obs: FrameObservation) -> tuple[_Candidate | None, int, bool]:
        """(người được chọn, số người trong ROI, có phải nhận mới). Không đổi trạng thái."""
        if not obs.source_ok:
            # Không tin khung hình lỗi nguồn: không đếm, không cập nhật vị trí nhớ.
            return None, 0, False
        geo = self._geometry.get(obs.image_size)
        candidates: list[_Candidate] = []
        for i, person in enumerate(obs.persons[: self._num_poses]):
            hip = hip_center_px(person, obs.image_size)
            if hip is None:
                continue
            depth = geo.signed_distance(hip)
            candidates.append(
                _Candidate(
                    index=i,
                    person=person,
                    hip=hip,
                    torso=torso_length_px(person, obs.image_size),
                    inside=geo.contains(hip),
                    depth=depth,
                )
            )
        in_roi = [c for c in candidates if c.inside]
        if self._last_hip is not None:
            return self._match_continuous(candidates, self._last_hip), len(in_roi), False
        if in_roi:
            # Nhận mới: người nằm sâu nhất trong ROI; hòa thì người đứng trước (xác định).
            return max(in_roi, key=lambda c: (c.depth, -c.index)), len(in_roi), True
        return None, len(in_roi), False

    def _hips_visible(self, person: PersonPose) -> bool:
        return all(
            (kp := person.keypoints.get(name)) is not None and kp.visibility >= self._min_vis
            for name in (KeypointName.LEFT_HIP, KeypointName.RIGHT_HIP)
        )

    def _match_continuous(self, candidates: list[_Candidate], last_hip: Px) -> _Candidate | None:
        if not candidates:
            return None
        nearest = min(candidates, key=lambda c: (distance(c.hip, last_hip), c.index))
        torso = self._last_torso or nearest.torso or 0.0
        if distance(nearest.hip, last_hip) <= self._max_jump * torso:
            return nearest
        return None
