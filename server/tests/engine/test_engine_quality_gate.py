"""F13 AC4, AC5 + ca âm tính: cổng chất lượng trong `Engine.process`.

Chưa có F14 nên `StateMachine` của F10 luôn trả `NO_OBSERVATION`. Để kiểm cổng chất lượng, các
test thay nó bằng `FakeStateMachine`: trả `LYING` khi hông trong ROI, `OUT_OF_BED` khi ngoài ROI.
Nhờ đó mọi frame kém lọt tới bước phân loại (vi phạm R7/R8) sẽ lộ ra.
"""

from collections.abc import Iterator
from typing import ClassVar

import pytest
from postcare.engine.features import BodyFeatures

from postcare.engine import engine as engine_module
from postcare.engine.pipeline import FrameAssessment
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.observation import FrameObservation
from postcare.schemas.state import BodyState as S
from postcare.schemas.state import ObservationQuality as Q
from tests.engine.builders import AT_EDGE, PoseSequence, default_config, run_engine

CONFIG = default_config()
LOW_MS = round(CONFIG.quality.low_quality_to_no_observation_s * 1000)
RESTORE_MS = round(CONFIG.quality.restore_duration_s * 1000)


class FakeStateMachine:
    """Thay cho F14: ghi lại mọi assessment nhận được."""

    instances: ClassVar[list["FakeStateMachine"]] = []

    def __init__(self, config: EngineConfig) -> None:
        self.received: list[FrameAssessment] = []
        FakeStateMachine.instances.append(self)

    def update(self, assessment: FrameAssessment, ts_ms: int) -> S:
        self.received.append(assessment)
        assert assessment.features is not None
        return S.LYING if assessment.features.inside_roi else S.OUT_OF_BED


@pytest.fixture
def fake_sm(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[FakeStateMachine]]:
    FakeStateMachine.instances = []
    monkeypatch.setattr(engine_module, "StateMachine", FakeStateMachine)
    yield FakeStateMachine


def _states(seq: list[FrameObservation]) -> list[S]:
    return [o.state.body_state for o in run_engine(seq)]


def _received_features(fake: type[FakeStateMachine]) -> list[BodyFeatures]:
    (sm,) = fake.instances
    return [a.features for a in sm.received if a.features is not None]


def test_startup_requires_restore_duration(fake_sm: type[FakeStateMachine]) -> None:
    seq = PoseSequence().lying(seconds=2).build()
    for obs, state in zip(seq, _states(seq), strict=True):
        expected = S.LYING if obs.ts_ms - seq[0].ts_ms >= RESTORE_MS else S.NO_OBSERVATION
        assert state == expected, obs.ts_ms


@pytest.mark.parametrize("mode", ["low_visibility", "missing"])
def test_prolonged_low_quality_goes_no_observation(
    fake_sm: type[FakeStateMachine], mode: str
) -> None:
    builder = PoseSequence().lying(seconds=2)
    t0 = builder.ts_ms
    seq = builder.drop_landmarks(seconds=3, mode=mode).build()
    outs = run_engine(seq)
    expected_quality = Q.LOW_CONFIDENCE if mode == "low_visibility" else Q.NO_PERSON
    for obs, out in zip(seq, outs, strict=True):
        if obs.ts_ms < t0:
            continue
        assert out.state.observation_quality == expected_quality
        expected = S.NO_OBSERVATION if obs.ts_ms - t0 >= LOW_MS else S.LYING
        assert out.state.body_state == expected, obs.ts_ms


def test_short_low_quality_keeps_state(fake_sm: type[FakeStateMachine]) -> None:
    builder = PoseSequence().lying(seconds=2)
    t_open = RESTORE_MS
    seq = builder.drop_landmarks(seconds=1.5).lying(seconds=1).build()
    states = _states(seq)
    after_open = [s for obs, s in zip(seq, states, strict=True) if obs.ts_ms >= t_open]
    assert set(after_open) == {S.LYING}
    # Frame kém không được đưa sang bước phân loại (R7)
    (sm,) = fake_sm.instances
    assert all(a.quality == Q.GOOD for a in sm.received)


def test_restore_requires_restore_duration(fake_sm: type[FakeStateMachine]) -> None:
    builder = PoseSequence().lying(seconds=2).drop_landmarks(seconds=3)
    g0 = builder.ts_ms
    seq = builder.lying(seconds=2).build()
    for obs, state in zip(seq, _states(seq), strict=True):
        if obs.ts_ms < g0:
            continue
        expected = S.LYING if obs.ts_ms - g0 >= RESTORE_MS else S.NO_OBSERVATION
        assert state == expected, obs.ts_ms


@pytest.mark.parametrize("frames", [1, 2, 3])
@pytest.mark.parametrize("kind", ["visibility", "jump"])
def test_noise_1_to_3_frames_no_quality_transition(
    fake_sm: type[FakeStateMachine], frames: int, kind: str
) -> None:
    builder = PoseSequence().lying(seconds=2)
    seq = builder.noise(frames=frames, kind=kind).lying(seconds=1).build()
    states = _states(seq)
    after_open = [s for obs, s in zip(seq, states, strict=True) if obs.ts_ms >= RESTORE_MS]
    assert set(after_open) == {S.LYING}
    # Đặc trưng đã làm mượt không nhảy: hông vẫn ở chỗ cũ
    for f in _received_features(fake_sm):
        assert f.hip_center == pytest.approx((640, 400))


def test_landmark_loss_at_edge_is_not_out_of_roi(fake_sm: type[FakeStateMachine]) -> None:
    builder = PoseSequence().pose(AT_EDGE, seconds=2)
    t0 = builder.ts_ms
    # Bị che ở mép giường: keypoint visibility thấp, vị trí đoán trượt ra ngoài ROI
    builder.body = AT_EDGE.moved_to((640, 620))
    seq = builder.drop_landmarks(seconds=4).build()
    outs = run_engine(seq)
    states = [o.state.body_state for o in outs]
    assert S.OUT_OF_BED not in states
    assert states[-1] == S.NO_OBSERVATION
    for obs, out in zip(seq, outs, strict=True):
        if obs.ts_ms >= t0:
            assert out.state.observation_quality == Q.LOW_CONFIDENCE
    assert all(f.inside_roi for f in _received_features(fake_sm))


def test_nurse_outside_roi_ignored(fake_sm: type[FakeStateMachine]) -> None:
    alone = PoseSequence().lying(seconds=3).build()
    run_engine(alone)
    baseline = _received_features(fake_sm)
    FakeStateMachine.instances = []

    with_nurse = PoseSequence().add_person_outside_roi().lying(seconds=3).build()
    outs = run_engine(with_nurse)
    assert _received_features(fake_sm) == baseline
    assert {o.state.observation_quality for o in outs} == {Q.GOOD}


def test_two_people_in_roi_goes_no_observation(fake_sm: type[FakeStateMachine]) -> None:
    builder = PoseSequence().lying(seconds=2)
    t0 = builder.ts_ms
    seq = builder.add_second_person_in_roi().lying(seconds=3).build()
    outs = run_engine(seq)
    for obs, out in zip(seq, outs, strict=True):
        if obs.ts_ms >= t0:
            assert out.state.observation_quality == Q.MULTIPLE_PEOPLE
    assert outs[-1].state.body_state == S.NO_OBSERVATION


def test_camera_issue_goes_no_observation(fake_sm: type[FakeStateMachine]) -> None:
    seq = PoseSequence().lying(seconds=2).camera_issue(seconds=3).build()
    outs = run_engine(seq)
    assert outs[-1].state.observation_quality == Q.CAMERA_ISSUE
    assert outs[-1].state.body_state == S.NO_OBSERVATION


def test_patient_walking_out_tracked_until_quality_drops(fake_sm: type[FakeStateMachine]) -> None:
    seq = (
        PoseSequence()
        .lying(seconds=2)
        .raise_to_sitting(seconds=1)
        .move_to_edge(seconds=1)
        .standing(seconds=1)
        .walk_out(seconds=2)
        .hold(seconds=1)
        .build()
    )
    outs = run_engine(seq)
    # Bệnh nhân được bám cả khi ra ngoài ROI (giả định R5), chất lượng vẫn GOOD
    assert {o.state.observation_quality for o in outs} == {Q.GOOD}
    assert outs[-1].state.body_state == S.OUT_OF_BED


def _full_sequence() -> list[FrameObservation]:
    return (
        PoseSequence()
        .lying(seconds=2)
        .noise(frames=2, kind="jump")
        .raise_to_sitting(seconds=1)
        .add_person_outside_roi()
        .sitting(seconds=1)
        .drop_landmarks(seconds=2.5)
        .move_to_edge(seconds=1)
        .add_second_person_in_roi()
        .standing(seconds=1)
        .remove_extra_people()
        .walk_out(seconds=2)
        .build()
    )


def test_engine_deterministic_same_sequence_same_output() -> None:
    seq = _full_sequence()
    first = run_engine(seq)
    second = run_engine(seq)
    assert [o.model_dump_json() for o in first] == [o.model_dump_json() for o in second]


def test_engine_deterministic_with_fake_state_machine(fake_sm: type[FakeStateMachine]) -> None:
    seq = _full_sequence()
    first = run_engine(seq)
    second = run_engine(seq)
    assert first == second
    a, b = fake_sm.instances
    assert [x.features for x in a.received] == [x.features for x in b.received]
