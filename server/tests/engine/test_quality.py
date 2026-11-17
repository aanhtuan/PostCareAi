"""F13 AC3: chất lượng quan sát từng frame (R6) và cổng chất lượng theo thời gian (R7)."""

from postcare.engine.quality import QualityGate, assess_quality
from postcare.engine.target import TargetSelector

from postcare.schemas.observation import FrameObservation, KeypointName
from postcare.schemas.state import ObservationQuality as Q
from tests.engine.builders import (
    LOW_VISIBILITY,
    LYING,
    NURSE,
    SITTING,
    context,
    default_config,
    frame,
    person_from_px,
)

CONFIG = default_config()
K = KeypointName
SECOND_IN_ROI = SITTING.moved_to((420, 330))


def _quality(obs: FrameObservation) -> Q:
    selector = TargetSelector(CONFIG, context())
    return assess_quality(obs, selector.select(obs), CONFIG)


def test_good_single_patient() -> None:
    assert _quality(frame([LYING.person()], ts_ms=0)) == Q.GOOD


def test_two_people_in_roi_is_multiple_people() -> None:
    assert _quality(frame([LYING.person(), SECOND_IN_ROI.person()], ts_ms=0)) == Q.MULTIPLE_PEOPLE


def test_second_person_outside_roi_is_not_multiple_people() -> None:
    assert _quality(frame([NURSE.person(), LYING.person()], ts_ms=0)) == Q.GOOD


def test_low_visibility_required_keypoint_is_low_confidence() -> None:
    for name in CONFIG.pose.required_keypoints:
        p = person_from_px(LYING.points(), visibility={name: LOW_VISIBILITY})
        assert _quality(frame([p], ts_ms=0)) == Q.LOW_CONFIDENCE, name


def test_low_visibility_optional_keypoint_is_still_good() -> None:
    p = person_from_px(LYING.points(), visibility={K.LEFT_KNEE: LOW_VISIBILITY})
    assert _quality(frame([p], ts_ms=0)) == Q.GOOD


def test_missing_required_keypoint_is_low_confidence() -> None:
    pts = LYING.points()
    del pts[K.LEFT_SHOULDER]
    assert _quality(frame([person_from_px(pts)], ts_ms=0)) == Q.LOW_CONFIDENCE


def test_zero_torso_length_is_low_confidence() -> None:
    p = person_from_px({name: (640, 400) for name in LYING.points()})
    assert _quality(frame([p], ts_ms=0)) == Q.LOW_CONFIDENCE


def test_no_person_and_outside_only() -> None:
    assert _quality(frame([], ts_ms=0)) == Q.NO_PERSON
    assert _quality(frame([NURSE.person()], ts_ms=0)) == Q.NO_PERSON


def test_source_not_ok_is_camera_issue() -> None:
    # CAMERA_ISSUE đứng trước mọi điều kiện khác (R6)
    obs = frame([LYING.person(), SECOND_IN_ROI.person()], ts_ms=0, source_ok=False)
    assert _quality(obs) == Q.CAMERA_ISSUE


def test_priority_multiple_people_over_low_confidence() -> None:
    hidden = person_from_px(LYING.points(), visibility=LOW_VISIBILITY)
    assert _quality(frame([hidden, SECOND_IN_ROI.person()], ts_ms=0)) == Q.MULTIPLE_PEOPLE


# ---- cổng chất lượng ----


def _run_gate(samples: list[tuple[int, Q]]) -> list[bool]:
    gate = QualityGate(CONFIG)
    return [gate.update(q, ts) for ts, q in samples]


def test_gate_starts_closed_and_opens_after_restore_duration() -> None:
    restore_ms = round(CONFIG.quality.restore_duration_s * 1000)
    ts = [0, restore_ms - 1, restore_ms, restore_ms + 66]
    assert _run_gate([(t, Q.GOOD) for t in ts]) == [False, False, True, True]


def test_gate_closes_only_after_low_quality_duration() -> None:
    restore_ms = round(CONFIG.quality.restore_duration_s * 1000)
    low_ms = round(CONFIG.quality.low_quality_to_no_observation_s * 1000)
    t0 = restore_ms + 100
    samples = [(0, Q.GOOD), (restore_ms, Q.GOOD)]
    samples += [(t0, Q.LOW_CONFIDENCE), (t0 + low_ms - 1, Q.NO_PERSON), (t0 + low_ms, Q.NO_PERSON)]
    assert _run_gate(samples) == [False, True, True, True, False]


def test_gate_good_frame_resets_low_quality_run() -> None:
    restore_ms = round(CONFIG.quality.restore_duration_s * 1000)
    low_ms = round(CONFIG.quality.low_quality_to_no_observation_s * 1000)
    t0 = restore_ms + 100
    samples = [(0, Q.GOOD), (restore_ms, Q.GOOD), (t0, Q.LOW_CONFIDENCE)]
    samples += [(t0 + low_ms - 10, Q.GOOD), (t0 + low_ms + 10, Q.LOW_CONFIDENCE)]
    samples += [(t0 + 2 * low_ms - 20, Q.LOW_CONFIDENCE)]
    assert _run_gate(samples)[-3:] == [True, True, True]


def test_gate_bad_frame_resets_restore_run() -> None:
    restore_ms = round(CONFIG.quality.restore_duration_s * 1000)
    samples = [(0, Q.GOOD), (restore_ms - 10, Q.MULTIPLE_PEOPLE), (restore_ms + 10, Q.GOOD)]
    samples += [(2 * restore_ms, Q.GOOD), (2 * restore_ms + 10, Q.GOOD)]
    assert _run_gate(samples) == [False, False, False, False, True]
