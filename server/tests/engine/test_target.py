"""F13 AC2: chọn người mục tiêu trong ROI, liên tục với vị trí trước (QA#20; HS §8.1)."""

import pytest
from postcare.engine.features import hip_center_px
from postcare.engine.target import TargetSelector

from postcare.schemas.observation import FrameObservation, PersonPose
from tests.engine.builders import (
    LYING,
    NURSE,
    OUTSIDE,
    STANDING,
    TORSO_PX,
    PoseSequence,
    context,
    default_config,
    frame,
)

CONFIG = default_config()


def _selector() -> TargetSelector:
    return TargetSelector(CONFIG, context())


def _hip(person: PersonPose | None, obs: FrameObservation) -> tuple[float, float] | None:
    return None if person is None else hip_center_px(person, obs.image_size)


def test_person_outside_roi_never_becomes_target() -> None:
    sel = _selector()
    for i in range(30):
        obs = frame([NURSE.person(), OUTSIDE.person()], ts_ms=i * 66)
        result = sel.select(obs)
        assert result.target is None
        assert result.persons_in_roi == 0


def test_nurse_outside_roi_does_not_replace_patient() -> None:
    sel = _selector()
    seq = PoseSequence().add_person_outside_roi().lying(seconds=2).build()
    for obs in seq:
        result = sel.select(obs)
        assert _hip(result.target, obs) == pytest.approx(LYING.hip)
        assert result.persons_in_roi == 1


def test_walker_passing_near_edge_does_not_steal_target() -> None:
    sel = _selector()
    for i in range(30):
        # Người đi ngang sát mép dưới giường (hông y = 620, ngoài ROI), cách bệnh nhân < ngưỡng nhảy
        walker = STANDING.moved_to((300 + i * 25, 620))
        obs = frame([walker.person(), LYING.person()], ts_ms=i * 66)
        result = sel.select(obs)
        assert _hip(result.target, obs) == pytest.approx(LYING.hip)


def test_target_tracked_by_continuity_outside_roi() -> None:
    sel = _selector()
    seq = (
        PoseSequence()
        .lying(seconds=1)
        .raise_to_sitting(seconds=1)
        .move_to_edge(seconds=1)
        .standing(seconds=1)
        .walk_out(seconds=2)
        .hold(seconds=1)
        .build()
    )
    for obs in seq:
        result = sel.select(obs)
        assert result.target is not None, obs.frame_index
    last = seq[-1]
    assert _hip(sel.select(last).target, last) == pytest.approx(OUTSIDE.hip)


def test_jump_over_threshold_is_new_person() -> None:
    sel = _selector()
    first = sel.select(frame([LYING.person()], ts_ms=0))
    assert first.target is not None
    assert first.is_new is True

    limit = CONFIG.target.max_jump_torso_lengths * TORSO_PX
    # Trong ngưỡng: vẫn là người cũ
    near = LYING.moved_to((640 - (limit - 10), 400))
    r = sel.select(frame([near.person()], ts_ms=66))
    assert r.target is not None
    assert r.is_new is False

    # Vượt ngưỡng (vẫn trong ROI): không nối tiếp với mục tiêu cũ
    far_x = near.hip[0] + limit + 10
    far = LYING.moved_to((far_x, 400))
    r = sel.select(frame([far.person()], ts_ms=132))
    assert r.target is None

    # Khi đã mất mục tiêu (forget, do cổng chất lượng đóng), người trong ROI được nhận mới
    sel.forget()
    r = sel.select(frame([far.person()], ts_ms=198))
    assert r.target is not None
    assert r.is_new is True


def test_nearest_person_wins_continuity() -> None:
    sel = _selector()
    sel.select(frame([LYING.person()], ts_ms=0))
    other = LYING.moved_to((640 + 120, 400))  # cũng trong ROI, trong ngưỡng nhảy
    moved = LYING.moved_to((640 + 20, 400))
    obs = frame([other.person(), moved.person()], ts_ms=66)
    r = sel.select(obs)
    assert _hip(r.target, obs) == pytest.approx(moved.hip)
    assert r.persons_in_roi == 2


def test_only_num_poses_persons_considered() -> None:
    sel = _selector()
    extra = [NURSE.person()] * CONFIG.pose.num_poses
    r = sel.select(frame([*extra, LYING.person()], ts_ms=0))
    assert r.target is None
    assert r.persons_in_roi == 0
