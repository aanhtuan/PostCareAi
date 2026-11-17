"""F25 (kế hoạch §9): xem trước người mục tiêu (chỉ đọc) để nhánh face chạy trước engine."""

from postcare.engine import Engine
from postcare.engine.target import TargetSelector
from postcare.schemas.observation import FrameObservation
from tests.engine.builders import NURSE, PoseSequence, context, default_config


def _sequence() -> list[FrameObservation]:
    return (
        PoseSequence(fps=15)
        .lying(seconds=2)
        .add_person_outside_roi(NURSE)
        .raise_to_sitting(seconds=1)
        .drop_landmarks(seconds=3, mode="missing")
        .lying(seconds=1)
        .build()
    )


def test_selector_peek_matches_select() -> None:
    selector = TargetSelector(default_config(), context())
    for obs in _sequence():
        peeked = selector.peek(obs)
        assert selector.peek(obs) == peeked  # không đổi trạng thái
        assert selector.select(obs).target == peeked


def test_engine_peek_target_does_not_change_outputs() -> None:
    peeking = Engine(default_config(), context())
    plain = Engine(default_config(), context())
    targets = 0
    for obs in _sequence():
        target = peeking.peek_target(obs)
        if target is not None:
            targets += 1
            assert target in obs.persons
        assert peeking.process(obs) == plain.process(obs)
    assert targets > 0


def test_peek_target_none_without_persons() -> None:
    seq = PoseSequence(fps=15).drop_landmarks(seconds=1, mode="missing").build()
    engine = Engine(default_config(), context())
    assert all(engine.peek_target(o) is None for o in seq)
