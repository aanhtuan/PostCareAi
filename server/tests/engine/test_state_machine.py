"""F14 AC1–AC5 và ca âm tính: state machine 7 trạng thái (event-engine.md mục 4).

Phần đầu kiểm `BodyStateMachine` trực tiếp bằng `BodyFeatures` tổng hợp để đo min_duration chính
xác từng frame. Phần sau chạy cả `Engine` trên chuỗi `PoseSequence` (có làm mượt, cổng chất lượng).
"""

import math
from collections.abc import Iterable
from itertools import pairwise

import pytest

from postcare.engine import Engine
from postcare.engine.features import BodyFeatures
from postcare.engine.pipeline import FrameAssessment
from postcare.engine.state_machine import BodyStateMachine
from postcare.schemas.events import EngineOutput
from postcare.schemas.observation import FrameObservation
from postcare.schemas.state import BodyState as S
from postcare.schemas.state import ObservationQuality as Q
from tests.engine.builders import (
    AT_EDGE,
    LYING,
    SITTING,
    STANDING,
    TORSO_PX,
    Body,
    PoseSequence,
    context,
    default_config,
    run_engine,
)
from tests.engine.test_posture import feat

CONFIG = default_config()
MIN = CONFIG.min_duration_s
STEP_MS = 100
FPS = 15


def ms(seconds: float) -> int:
    return round(seconds * 1000)


def good(f: BodyFeatures) -> FrameAssessment:
    return FrameAssessment(
        quality=Q.GOOD, target=None, features=f, observable=True, persons_in_roi=1
    )


class Feeder:
    """Đưa `BodyFeatures` vào state machine, mỗi frame cách nhau `STEP_MS`."""

    def __init__(self) -> None:
        self.sm = BodyStateMachine(CONFIG)
        self.ts = 0
        self.states: list[tuple[int, S]] = []

    def feed(self, f: BodyFeatures, seconds: float) -> "Feeder":
        for _ in range(ms(seconds) // STEP_MS):
            self.states.append((self.ts, self.sm.update(good(f), self.ts)))
            self.ts += STEP_MS
        return self

    def state_at(self, ts: int) -> S:
        return dict(self.states)[ts]


LYING_F = feat(0)
RAISING_F = feat((CONFIG.posture.lying_exit_deg + CONFIG.posture.sitting_exit_deg) / 2)
SITTING_F = feat(90)


def established(outs: Iterable[EngineOutput]) -> list[S]:
    """Chuỗi trạng thái ổn định (bỏ lặp), bắt đầu từ trạng thái khởi tạo."""
    result: list[S] = []
    for o in outs:
        if not result or result[-1] != o.state.body_state:
            result.append(o.state.body_state)
    return result


def body_changes(outs: list[EngineOutput]) -> int:
    return sum(1 for a, b in pairwise(outs) if a.state.body_state != b.state.body_state)


def trunk_at(angle_deg: float, base: Body = LYING) -> Body:
    """Thân nghiêng `angle_deg` so với trục giường (ngang), giữ chiều dài thân."""
    rad = math.radians(angle_deg)
    return Body(
        hip=base.hip,
        shoulder=(-TORSO_PX * math.cos(rad), -TORSO_PX * math.sin(rad)),
        knee=base.knee,
        ankle=base.ankle,
        half_width=base.half_width,
    )


def lying_established() -> PoseSequence:
    """Khởi động: qua cổng phục hồi (1 s) rồi giữ LYING đủ min_duration (2 s), dư 1 s."""
    return PoseSequence(fps=FPS).lying(seconds=CONFIG.quality.restore_duration_s + MIN.LYING + 1)


def at_edge_established() -> PoseSequence:
    return (
        lying_established()
        .raise_to_sitting(seconds=1.5)
        .sitting(seconds=MIN.SITTING + 1)
        .move_to_edge(seconds=1)
        .pose(AT_EDGE, seconds=MIN.AT_EDGE + 1)
    )


# ---- AC1 ----


def full_sequence() -> list[FrameObservation]:
    return (
        at_edge_established()
        .move_to(STANDING, seconds=0.5)
        .standing(seconds=MIN.STANDING + 1)
        .walk_out(seconds=2)
        .hold(seconds=MIN.OUT_OF_BED + 1)
        .drop_landmarks(seconds=CONFIG.quality.low_quality_to_no_observation_s + 1)
        .build()
    )


def test_full_sequence_reaches_all_seven_states() -> None:
    outs = run_engine(full_sequence())
    assert established(outs) == [
        S.NO_OBSERVATION,
        S.LYING,
        S.RAISING,
        S.SITTING,
        S.AT_EDGE,
        S.STANDING,
        S.OUT_OF_BED,
        S.NO_OBSERVATION,
    ]
    # Ra ngoài qua mép giường: chuỗi hợp lệ, không có anomaly
    out_of_bed = next(o for o in outs if o.state.body_state == S.OUT_OF_BED)
    assert out_of_bed.state.explanation is not None
    assert "anomaly" not in out_of_bed.state.explanation


def test_state_history_records_established_states() -> None:
    engine = Engine(CONFIG, context())
    for obs in full_sequence():
        engine.process(obs)
    states = [r.state for r in engine.state_history]
    assert states == [
        S.LYING,
        S.RAISING,
        S.SITTING,
        S.AT_EDGE,
        S.STANDING,
        S.OUT_OF_BED,
        S.NO_OBSERVATION,
    ]
    since = [r.since_ms for r in engine.state_history]
    assert since == sorted(since)
    assert all(r.explanation["to_state"] == r.state.value for r in engine.state_history)


# ---- AC2 ----


def test_initial_state_needs_min_duration() -> None:
    fd = Feeder().feed(LYING_F, MIN.LYING + 1)
    assert fd.state_at(ms(MIN.LYING) - STEP_MS) == S.NO_OBSERVATION
    assert fd.state_at(ms(MIN.LYING)) == S.LYING


@pytest.mark.parametrize(
    ("target", "f"),
    [(S.RAISING, RAISING_F), (S.SITTING, SITTING_F)],
)
def test_transition_only_after_min_duration(target: S, f: BodyFeatures) -> None:
    fd = Feeder().feed(LYING_F, MIN.LYING + 1)
    if target == S.SITTING:
        fd.feed(RAISING_F, MIN.RAISING + 1)
    t0 = fd.ts
    hold = ms(getattr(MIN, target.value))
    fd.feed(f, hold / 1000 + 1)
    previous = S.LYING if target == S.RAISING else S.RAISING
    # Ngắn hơn min_duration 1 frame: chưa đổi; đúng min_duration: đổi
    assert fd.state_at(t0 + hold - STEP_MS) == previous
    assert fd.state_at(t0 + hold) == target


def test_candidate_change_restarts_hold() -> None:
    fd = Feeder().feed(LYING_F, MIN.LYING + 1).feed(RAISING_F, MIN.RAISING + 1)
    t0 = fd.ts
    # SITTING gần đủ lâu, xen 1 frame LYING (ứng viên khác), rồi SITTING lại
    fd.feed(SITTING_F, MIN.SITTING - 0.2).feed(feat(10), 0.1)
    t1 = fd.ts
    fd.feed(SITTING_F, MIN.SITTING + 0.5)
    assert all(s == S.RAISING for ts, s in fd.states if t0 <= ts < t1 + ms(MIN.SITTING))
    assert fd.state_at(t1 + ms(MIN.SITTING)) == S.SITTING


@pytest.mark.parametrize("frames", [1, 2, 3])
def test_noise_1_to_3_frames_no_transition(frames: int) -> None:
    builder = lying_established()
    t0 = builder.ts_ms
    seq = builder.pose(SITTING, seconds=frames / FPS).lying(seconds=4).build()
    outs = run_engine(seq)
    after = [o.state.body_state for obs, o in zip(seq, outs, strict=True) if obs.ts_ms >= t0]
    assert set(after) == {S.LYING}


@pytest.mark.parametrize("frames", [1, 2, 3])
def test_noise_1_to_3_frames_unit(frames: int) -> None:
    fd = Feeder().feed(LYING_F, MIN.LYING + 1)
    t0 = fd.ts
    fd.feed(SITTING_F, frames * STEP_MS / 1000).feed(LYING_F, 3)
    assert {s for ts, s in fd.states if ts >= t0} == {S.LYING}


# ---- AC3 ----


@pytest.mark.parametrize(
    ("start", "threshold"),
    [
        ("lying", CONFIG.posture.lying_exit_deg),
        ("raising", CONFIG.posture.sitting_enter_deg),
        ("sitting", CONFIG.posture.sitting_exit_deg),
        ("lying_enter", CONFIG.posture.lying_enter_deg),
    ],
)
def test_trunk_angle_oscillating_near_threshold_no_flapping(start: str, threshold: float) -> None:
    builder = lying_established()
    if start in ("raising", "sitting", "lying_enter"):
        builder.move_to(trunk_at(45), seconds=0.5).pose(trunk_at(45), seconds=MIN.RAISING + 1)
    if start == "sitting":
        builder.move_to(trunk_at(90), seconds=0.5).pose(trunk_at(90), seconds=MIN.SITTING + 1)
    t0 = builder.ts_ms
    # ±4° quanh ngưỡng, chu kỳ 1.6 s, trong 12 s
    bodies = [
        trunk_at(threshold + 4 * math.sin(2 * math.pi * i / (1.6 * FPS))) for i in range(12 * FPS)
    ]
    seq = builder.frames(bodies).build()
    outs = run_engine(seq)
    window = [o for obs, o in zip(seq, outs, strict=True) if obs.ts_ms >= t0]
    assert body_changes(window) <= 1


# ---- AC4 ----


REQUIRED_KEYS = {
    "rule_id",
    "from_state",
    "to_state",
    "held_ms",
    "trunk_angle_deg",
    "dist_to_roi_edge",
    "ankles_outside_roi",
    "observation_quality",
}


def test_every_transition_has_explanation() -> None:
    outs = run_engine(full_sequence())
    transitions = 0
    for prev, cur in pairwise(outs):
        if prev.state.body_state == cur.state.body_state:
            # Giữa hai lần chuyển, explanation không đổi
            assert cur.state.explanation == prev.state.explanation
            continue
        transitions += 1
        assert cur.state_changed
        exp = cur.state.explanation
        assert exp is not None
        if cur.state.body_state == S.NO_OBSERVATION:
            assert {"rule_id", "from_state", "to_state", "held_ms", "observation_quality"} <= set(
                exp
            )
        else:
            assert set(exp) >= REQUIRED_KEYS
            held = exp["held_ms"]
            assert isinstance(held, int)
            assert held >= ms(getattr(MIN, cur.state.body_state.value))
        assert isinstance(exp["rule_id"], str) and exp["rule_id"]
        assert exp["from_state"] == prev.state.body_state.value
        assert exp["to_state"] == cur.state.body_state.value
    assert transitions == 7
    assert outs[0].state.explanation is None


# ---- AC5 ----


@pytest.mark.parametrize("mode", ["low_visibility", "missing"])
def test_landmark_loss_at_edge_goes_no_observation_not_out_of_bed(mode: str) -> None:
    builder = at_edge_established()
    t0 = builder.ts_ms
    # Bị che ở mép giường: vị trí đoán trượt ra ngoài ROI
    builder.body = AT_EDGE.moved_to((640, 640))
    seq = builder.drop_landmarks(seconds=5, mode=mode).build()
    outs = run_engine(seq)
    states = [o.state.body_state for obs, o in zip(seq, outs, strict=True) if obs.ts_ms >= t0]
    assert states[0] == S.AT_EDGE
    assert S.OUT_OF_BED not in states
    assert states[-1] == S.NO_OBSERVATION
    exp = outs[-1].state.explanation
    assert exp is not None and exp["from_state"] == S.AT_EDGE.value


def test_occlusion_mid_transition_restarts_min_duration() -> None:
    builder = at_edge_established().move_to(STANDING, seconds=0.5).standing(seconds=2)
    out_pose = STANDING.moved_to((1150, 590))
    builder.move_to(out_pose, seconds=0.8).pose(out_pose, seconds=0.5)
    # Bị che ngắn (chưa tới mức NO_OBSERVATION) giữa lúc đang thành ứng viên OUT_OF_BED
    builder.drop_landmarks(seconds=0.4)
    t_back = builder.ts_ms
    seq = builder.pose(out_pose, seconds=MIN.OUT_OF_BED + 1).build()
    outs = run_engine(seq)
    by_ts = {obs.ts_ms: o.state.body_state for obs, o in zip(seq, outs, strict=True)}
    # Sau khi thấy lại, phải giữ OUT trọn min_duration mới xác lập
    assert all(
        s != S.OUT_OF_BED for ts, s in by_ts.items() if ts < t_back + ms(MIN.OUT_OF_BED) - 70
    )
    assert outs[-1].state.body_state == S.OUT_OF_BED
    assert S.NO_OBSERVATION not in {s for ts, s in by_ts.items() if ts >= t_back - 500}


def test_lying_to_out_of_bed_marks_skipped_edge() -> None:
    off_bed = LYING.moved_to((640, 700))
    seq = (
        lying_established()
        .move_to(off_bed, seconds=0.5)
        .pose(off_bed, seconds=MIN.OUT_OF_BED + 1)
        .build()
    )
    outs = run_engine(seq)
    assert established(outs) == [S.NO_OBSERVATION, S.LYING, S.OUT_OF_BED]
    exp = outs[-1].state.explanation
    assert exp is not None
    assert exp["anomaly"] == "skipped_edge"
    assert exp["from_state"] == S.LYING.value


def test_lying_to_out_skipped_edge_ignores_no_observation_gap() -> None:
    off_bed = LYING.moved_to((640, 700))
    # Mất quan sát khi đang nằm, thấy lại (chưa đủ lâu để xác lập LYING) rồi ra thẳng ngoài ROI
    seq = (
        lying_established()
        .drop_landmarks(seconds=3)
        .lying(seconds=CONFIG.quality.restore_duration_s + 0.5)
        .move_to(off_bed, seconds=0.5)
        .pose(off_bed, seconds=MIN.OUT_OF_BED + 1)
        .build()
    )
    outs = run_engine(seq)
    assert established(outs) == [S.NO_OBSERVATION, S.LYING, S.NO_OBSERVATION, S.OUT_OF_BED]
    exp = outs[-1].state.explanation
    assert exp is not None and exp["anomaly"] == "skipped_edge"


# ---- Ca âm tính bắt buộc (mục 6) ----


def test_sit_up_then_lie_back_never_edge_or_out() -> None:
    seq = (
        lying_established()
        .raise_to_sitting(seconds=1.5)
        .sitting(seconds=MIN.SITTING + 1)
        .move_to(LYING, seconds=1.5)
        .lying(seconds=MIN.LYING + 1)
        .build()
    )
    states = established(run_engine(seq))
    assert states[:4] == [S.NO_OBSERVATION, S.LYING, S.RAISING, S.SITTING]
    assert states[-1] == S.LYING
    assert S.AT_EDGE not in states and S.OUT_OF_BED not in states


def test_brief_sit_up_spike_shorter_than_min_duration() -> None:
    builder = lying_established()
    t0 = builder.ts_ms
    seq = (
        builder.raise_to_sitting(seconds=0.5)
        .sitting(seconds=MIN.SITTING / 2)
        .move_to(LYING, seconds=0.3)
        .lying(seconds=3)
        .build()
    )
    outs = run_engine(seq)
    after = {o.state.body_state for obs, o in zip(seq, outs, strict=True) if obs.ts_ms >= t0}
    assert S.SITTING not in after
    assert outs[-1].state.body_state in (S.LYING, S.RAISING)


def test_nurse_outside_roi_does_not_change_state() -> None:
    builder = lying_established()
    t0 = builder.ts_ms
    seq = builder.add_person_outside_roi().lying(seconds=5).build()
    outs = run_engine(seq)
    assert {o.state.body_state for obs, o in zip(seq, outs, strict=True) if obs.ts_ms >= t0} == {
        S.LYING
    }


def test_two_people_in_roi_state_no_observation() -> None:
    seq = lying_established().add_second_person_in_roi().lying(seconds=4).build()
    outs = run_engine(seq)
    assert outs[-1].state.body_state == S.NO_OBSERVATION
    assert outs[-1].state.observation_quality == Q.MULTIPLE_PEOPLE
    assert S.OUT_OF_BED not in established(outs)


def test_standing_at_edge_is_standing_not_at_edge() -> None:
    # Đứng sát mép giường (hông vẫn trong ROI để nhận mục tiêu)
    seq = PoseSequence(fps=FPS, start=STANDING.moved_to((640, 560))).hold(seconds=4).build()
    states = established(run_engine(seq))
    assert states == [S.NO_OBSERVATION, S.STANDING]


def test_sitting_at_edge_is_at_edge() -> None:
    seq = PoseSequence(fps=FPS).pose(AT_EDGE, seconds=4).build()
    assert established(run_engine(seq)) == [S.NO_OBSERVATION, S.AT_EDGE]


def test_hip_dithering_at_roi_margin_no_edge_out_flapping() -> None:
    margin_px = CONFIG.location.out_of_roi_margin_torso * TORSO_PX
    bottom = 576  # mép dưới ROI theo pixel (BED_ROI)

    def dither(seconds: float) -> list[Body]:
        # Hông dao động ±0.1 torso quanh biên out_of_roi_margin, chu kỳ 1.2 s
        n = round(seconds * FPS)
        amp = 0.1 * TORSO_PX
        return [
            AT_EDGE.moved_to(
                (640, bottom + margin_px + amp * math.sin(2 * math.pi * i / (1.2 * FPS)))
            )
            for i in range(n)
        ]

    builder = at_edge_established()
    t0 = builder.ts_ms
    seq = builder.frames(dither(10)).build()
    outs = run_engine(seq)
    window = [o for obs, o in zip(seq, outs, strict=True) if obs.ts_ms >= t0]
    assert {o.state.body_state for o in window} == {S.AT_EDGE}

    # Đã ra ngoài hẳn: dao động ở biên không làm quay về (cần hông vào trong ROI)
    far = AT_EDGE.moved_to((640, bottom + 2 * margin_px))
    builder = at_edge_established().move_to(far, seconds=0.5).pose(far, seconds=MIN.OUT_OF_BED + 1)
    t1 = builder.ts_ms
    seq = builder.frames(dither(10)).build()
    outs = run_engine(seq)
    window = [o for obs, o in zip(seq, outs, strict=True) if obs.ts_ms >= t1]
    assert {o.state.body_state for o in window} == {S.OUT_OF_BED}


def test_return_into_roi_leaves_out_of_bed() -> None:
    seq = (
        at_edge_established()
        .move_to(STANDING, seconds=0.5)
        .standing(seconds=MIN.STANDING + 1)
        .walk_out(seconds=2)
        .hold(seconds=MIN.OUT_OF_BED + 1)
        .move_to(SITTING, seconds=2)
        .sitting(seconds=MIN.SITTING + 1)
        .build()
    )
    states = established(run_engine(seq))
    assert S.OUT_OF_BED in states
    assert states[-1] == S.SITTING


def test_state_machine_is_deterministic() -> None:
    seq = full_sequence()
    a = run_engine(seq)
    b = run_engine(seq)
    assert [o.model_dump_json() for o in a] == [o.model_dump_json() for o in b]
