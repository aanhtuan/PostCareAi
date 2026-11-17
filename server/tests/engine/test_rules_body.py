"""F15 AC1–AC5 và ca âm tính: sự kiện cơ thể và vị trí (event-engine.md mục 4, 5).

Mọi chuỗi chạy cả `Engine` trên `PoseSequence` (làm mượt, cổng chất lượng, state machine F14).
Thời lượng mỗi đoạn lấy từ `engine.default.yaml` (không viết cứng ngưỡng).
"""

from collections.abc import Callable

import pytest

from postcare.engine import Engine
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.events import EngineEvent, EngineOutput, EventCode, default_priority
from postcare.schemas.observation import FrameObservation
from postcare.schemas.state import BodyState as S
from postcare.schemas.state import ObservationQuality as Q
from tests.engine.builders import (
    AT_EDGE,
    LYING,
    OUTSIDE,
    ROOT,
    SITTING,
    STANDING,
    PoseSequence,
    context,
    default_config,
    run_engine,
)
from tests.engine.builders import codes as all_codes
from tests.engine.builders import events as all_events

BODY_CODES = frozenset(
    {
        EventCode.SIT_UP,
        EventCode.STAND_UP,
        EventCode.BED_EDGE,
        EventCode.BED_EXIT,
        EventCode.RETURN_TO_BED,
        EventCode.POSTURE_CHANGE,
    }
)
"""Mã của F15. Sự kiện vận động (F23, LOG) xuất hiện song song khi người bệnh cử động; test ở đây
chỉ xét rule cơ thể (vận động: `test_rules_movement.py`)."""


def events(outs: list[EngineOutput]) -> list[EngineEvent]:
    return [e for e in all_events(outs) if e.code in BODY_CODES]


def codes(outs: list[EngineOutput]) -> list[str]:
    return [c for c in all_codes(outs) if c in BODY_CODES]


CONFIG = default_config()
MIN = CONFIG.min_duration_s
RESTORE = CONFIG.quality.restore_duration_s
LOST = CONFIG.quality.low_quality_to_no_observation_s
STABLE = CONFIG.posture_change.stable_s
FPS = 15


def short_debounce() -> EngineConfig:
    """Cửa sổ debounce ngắn: để test rule (vào/ra trạng thái) độc lập với debounce."""
    return EngineConfig.load(
        ROOT / "config" / "engine.default.yaml",
        {"debounce": {"same_code_same_session_s": 1.0}},
    )


def lying_established() -> PoseSequence:
    """Qua cổng phục hồi rồi giữ LYING đủ min_duration, dư 1 s."""
    return PoseSequence(fps=FPS).lying(seconds=RESTORE + MIN.LYING + 1)


def sitting_established() -> PoseSequence:
    return lying_established().raise_to_sitting(seconds=1.5).sitting(seconds=MIN.SITTING + 1)


def at_edge_established() -> PoseSequence:
    return sitting_established().move_to_edge(seconds=1).pose(AT_EDGE, seconds=MIN.AT_EDGE + 1)


def exited() -> PoseSequence:
    return (
        at_edge_established()
        .move_to(STANDING, seconds=0.5)
        .standing(seconds=MIN.STANDING + 1)
        .walk_out(seconds=2)
        .hold(seconds=MIN.OUT_OF_BED + 1)
    )


def first(outs: list[EngineOutput], code: EventCode) -> tuple[int, EngineEvent]:
    """(chỉ số frame, sự kiện) của lần phát đầu tiên `code`."""
    for i, o in enumerate(outs):
        for e in o.events:
            if e.code == code:
                return i, e
    raise AssertionError(f"không có {code}")


# ---- AC1 ----


def test_sit_up_sequence_emits_sit_up() -> None:
    seq = sitting_established().build()
    outs = run_engine(seq)
    assert codes(outs) == ["SIT_UP"]
    i, ev = first(outs, EventCode.SIT_UP)
    # Phát đúng frame SITTING được xác lập, chuỗi LYING → RAISING → SITTING
    assert outs[i].state.body_state == S.SITTING
    assert outs[i - 1].state.body_state == S.RAISING
    assert ev.detected_at_ms == seq[i].ts_ms
    assert ev.detected_at_ms - ev.occurred_at_ms >= MIN.SITTING * 1000
    assert ev.explanation["from_state"] == S.RAISING.value
    assert ev.explanation["to_state"] == S.SITTING.value


def test_sit_up_then_lie_back_no_bed_exit() -> None:
    seq = (
        sitting_established()
        .move_to(LYING, seconds=1.5)
        .lying(seconds=MIN.LYING + STABLE + 1)
        .build()
    )
    outs = run_engine(seq)
    assert outs[-1].state.body_state == S.LYING
    assert codes(outs) == ["SIT_UP"]


@pytest.mark.parametrize("n", [1, 2, 3])
def test_noise_1_to_3_frames_no_sit_up(n: int) -> None:
    seq = lying_established().frames([SITTING] * n).lying(seconds=4).build()
    assert codes(run_engine(seq)) == []


def test_sit_up_requires_raising_after_lying() -> None:
    """Bắt đầu theo dõi khi đã ngồi: SITTING không đến từ LYING → RAISING, không SIT_UP."""
    seq = PoseSequence(fps=FPS, start=SITTING).sitting(seconds=RESTORE + MIN.SITTING + 2).build()
    outs = run_engine(seq)
    assert outs[-1].state.body_state == S.SITTING
    assert codes(outs) == []


# ---- AC2 ----


def test_full_exit_sequence_codes() -> None:
    # Ví dụ ở testing.md mục 2
    seq = (
        PoseSequence(fps=15)
        .lying(seconds=4)
        .raise_to_sitting(seconds=1.5)
        .sitting(seconds=3)
        .move_to_edge(seconds=1)
        .hold(seconds=2.5)
        .move_to(STANDING, seconds=0.5)
        .standing(seconds=2)
        .walk_out(seconds=2)
        .hold(seconds=2)
        .build()
    )
    outs = run_engine(seq, config=default_config())
    assert codes(outs) == ["SIT_UP", "BED_EDGE", "STAND_UP", "BED_EXIT"]
    i, ev = first(outs, EventCode.BED_EXIT)
    assert outs[i].state.body_state == S.OUT_OF_BED
    assert ev.priority.value == "HIGH"
    assert ev.explanation["state_chain"] == [
        S.LYING.value,
        S.RAISING.value,
        S.SITTING.value,
        S.AT_EDGE.value,
        S.STANDING.value,
        S.OUT_OF_BED.value,
    ]


def test_bed_edge_emitted_on_entering_at_edge() -> None:
    outs = run_engine(at_edge_established().build())
    assert codes(outs) == ["SIT_UP", "BED_EDGE"]
    i, ev = first(outs, EventCode.BED_EDGE)
    assert outs[i].state.body_state == S.AT_EDGE
    assert ev.explanation["from_state"] == S.SITTING.value
    assert ev.detected_at_ms - ev.occurred_at_ms >= MIN.AT_EDGE * 1000


def test_brief_edge_below_min_duration_no_bed_edge() -> None:
    seq = (
        sitting_established()
        .move_to_edge(seconds=0.3)
        .pose(AT_EDGE, seconds=MIN.AT_EDGE / 3)
        .move_to(SITTING, seconds=0.3)
        .sitting(seconds=MIN.SITTING + 1)
        .build()
    )
    outs = run_engine(seq)
    assert S.AT_EDGE not in {o.state.body_state for o in outs}
    assert codes(outs) == ["SIT_UP"]


def test_edge_at_monitoring_start_emits_bed_edge() -> None:
    """R4 (chốt 18/11/2026, hướng an toàn): AT_EDGE đầu tiên, chưa có trạng thái nào trước đó."""
    seq = PoseSequence(fps=FPS, start=AT_EDGE).pose(AT_EDGE, seconds=RESTORE + MIN.AT_EDGE + 1)
    outs = run_engine(seq.build())
    assert outs[-1].state.body_state == S.AT_EDGE
    assert codes(outs) == ["BED_EDGE"]
    _, ev = first(outs, EventCode.BED_EDGE)
    assert ev.explanation["from_state"] == S.NO_OBSERVATION.value


def test_edge_after_occlusion_at_edge_no_new_bed_edge() -> None:
    """Đang ở mép → bị che → thấy lại ở mép: không phải lần ra mép mới (debounce rút ngắn)."""
    seq = (
        at_edge_established()
        .drop_landmarks(seconds=LOST + 1)
        .pose(AT_EDGE, seconds=RESTORE + MIN.AT_EDGE + 1)
        .build()
    )
    outs = run_engine(seq, config=short_debounce())
    states = [o.state.body_state for o in outs]
    assert S.NO_OBSERVATION in states[states.index(S.AT_EDGE) :]
    assert outs[-1].state.body_state == S.AT_EDGE
    assert codes(outs) == ["SIT_UP", "BED_EDGE"]


def test_sitting_standing_out_of_bed_emits_bed_exit() -> None:
    """Ngồi mép < min_duration rồi đứng đi ra: qua STANDING là chuỗi hợp lệ (event-engine.md §4)."""
    seq = (
        sitting_established()
        .move_to(STANDING, seconds=0.8)
        .standing(seconds=MIN.STANDING + 1)
        .walk_out(seconds=2)
        .hold(seconds=MIN.OUT_OF_BED + 1)
        .build()
    )
    outs = run_engine(seq)
    assert codes(outs) == ["SIT_UP", "STAND_UP", "BED_EXIT"]
    _, ev = first(outs, EventCode.STAND_UP)
    assert ev.explanation["from_state"] == S.SITTING.value


def test_lying_straight_out_no_bed_exit() -> None:
    off_bed = LYING.moved_to((640, 700))
    seq = (
        lying_established()
        .move_to(off_bed, seconds=0.5)
        .pose(off_bed, seconds=MIN.OUT_OF_BED + 2)
        .build()
    )
    outs = run_engine(seq)
    assert outs[-1].state.body_state == S.OUT_OF_BED
    exp = outs[-1].state.explanation
    assert exp is not None and exp["anomaly"] == "skipped_edge"
    assert codes(outs) == []


@pytest.mark.parametrize("mode", ["low_visibility", "missing"])
def test_landmark_loss_at_edge_no_bed_exit(mode: str) -> None:
    builder = at_edge_established()
    # Bị che ở mép giường: vị trí đoán trượt ra ngoài ROI
    builder.body = AT_EDGE.moved_to((640, 640))
    seq = builder.drop_landmarks(seconds=LOST + 5, mode=mode).build()
    outs = run_engine(seq)
    assert outs[-1].state.body_state == S.NO_OBSERVATION
    assert codes(outs) == ["SIT_UP", "BED_EDGE"]


def test_occluded_at_edge_then_observed_outside_emits_bed_exit() -> None:
    """R5: mép → bị che (NO_OBSERVATION) → quan sát rõ ở ngoài ROI đủ lâu → BED_EXIT."""
    builder = at_edge_established().drop_landmarks(seconds=LOST + 1)
    out_pose = STANDING.moved_to((640, 680))
    builder.body = out_pose
    seq = builder.pose(out_pose, seconds=RESTORE + MIN.OUT_OF_BED + 1).build()
    outs = run_engine(seq)
    states = [o.state.body_state for o in outs]
    assert S.NO_OBSERVATION in states[states.index(S.AT_EDGE) :]
    assert outs[-1].state.body_state == S.OUT_OF_BED
    assert codes(outs) == ["SIT_UP", "BED_EDGE", "BED_EXIT"]
    _, ev = first(outs, EventCode.BED_EXIT)
    chain = ev.explanation["state_chain"]
    assert isinstance(chain, list)
    assert chain[-3:] == [S.AT_EDGE.value, S.NO_OBSERVATION.value, S.OUT_OF_BED.value]


def test_return_to_bed_after_exit() -> None:
    seq = (
        exited()
        .move_to(SITTING, seconds=2)
        .sitting(seconds=MIN.RETURN_TO_BED + 1)
        .move_to(LYING, seconds=1.5)
        .lying(seconds=MIN.LYING + 1)
        .build()
    )
    outs = run_engine(seq)
    assert codes(outs) == ["SIT_UP", "BED_EDGE", "STAND_UP", "BED_EXIT", "RETURN_TO_BED"]
    i, ev = first(outs, EventCode.RETURN_TO_BED)
    assert outs[i].state.body_state in (S.SITTING, S.LYING)
    assert ev.detected_at_ms - ev.occurred_at_ms >= MIN.RETURN_TO_BED * 1000
    assert ev.priority.value == "INFO"


def test_return_to_bed_needs_hold() -> None:
    """Về ngồi trong giường chưa đủ min_duration_s.RETURN_TO_BED → chưa có RETURN_TO_BED."""
    seq = exited().move_to(SITTING, seconds=0.5).sitting(seconds=MIN.RETURN_TO_BED - 0.5).build()
    outs = run_engine(seq)
    assert "RETURN_TO_BED" not in codes(outs)


def test_return_to_bed_after_skipped_edge_without_bed_exit() -> None:
    """R6: RETURN_TO_BED chỉ cần đã OUT_OF_BED, kể cả khi lần ra ngoài không sinh BED_EXIT."""
    off_bed = LYING.moved_to((640, 700))
    seq = (
        lying_established()
        .move_to(off_bed, seconds=0.5)
        .pose(off_bed, seconds=MIN.OUT_OF_BED + 1)
        .move_to(LYING, seconds=0.5)
        .lying(seconds=MIN.LYING + MIN.RETURN_TO_BED + 1)
        .build()
    )
    outs = run_engine(seq)
    assert S.OUT_OF_BED in {o.state.body_state for o in outs}
    assert codes(outs) == ["RETURN_TO_BED"]


def test_return_to_bed_only_after_out_of_bed() -> None:
    seq = sitting_established().move_to(LYING, seconds=1.5).lying(seconds=10).build()
    assert "RETURN_TO_BED" not in codes(run_engine(seq))


def test_return_via_edge_no_bed_edge() -> None:
    """R4: quay lại giường qua mép (từ STANDING) không sinh BED_EDGE."""
    seq = (
        exited()
        .move_to(STANDING, seconds=1.5)
        .standing(seconds=MIN.STANDING + 1)
        .move_to(AT_EDGE, seconds=0.5)
        .pose(AT_EDGE, seconds=MIN.AT_EDGE + 1)
        .move_to(LYING, seconds=1.5)
        .lying(seconds=MIN.LYING + MIN.RETURN_TO_BED + 1)
        .build()
    )
    outs = run_engine(seq, config=short_debounce())
    states = [o.state.body_state for o in outs]
    i_exit, _ = first(outs, EventCode.BED_EXIT)
    assert S.AT_EDGE in states[i_exit:]
    after = codes(outs[i_exit + 1 :])
    assert "BED_EDGE" not in after
    assert after[-1] == "RETURN_TO_BED"


# ---- AC3 ----


def test_turn_over_emits_posture_change_log() -> None:
    seq = lying_established().turn_over(seconds=1).hold(seconds=STABLE + 1).build()
    outs = run_engine(seq)
    assert {o.state.body_state for o in outs[-30:]} == {S.LYING}
    assert codes(outs) == ["POSTURE_CHANGE"]
    _, ev = first(outs, EventCode.POSTURE_CHANGE)
    assert ev.priority.value == "LOG"
    delta = ev.explanation["shoulder_angle_delta_deg"]
    assert isinstance(delta, float)
    assert delta > CONFIG.posture_change.shoulder_angle_delta_deg
    assert ev.detected_at_ms - ev.occurred_at_ms >= STABLE * 1000


def test_small_shoulder_rotation_no_posture_change() -> None:
    degrees = CONFIG.posture_change.shoulder_angle_delta_deg * 0.6
    seq = lying_established().turn_over(seconds=1, degrees=degrees).hold(seconds=STABLE + 2).build()
    assert codes(run_engine(seq)) == []


def test_brief_turn_shorter_than_stable_no_posture_change() -> None:
    seq = (
        lying_established()
        .turn_over(seconds=0.3)
        .hold(seconds=STABLE / 3)
        .turn_over(seconds=0.3, degrees=-60)
        .hold(seconds=STABLE + 1)
        .build()
    )
    assert codes(run_engine(seq)) == []


def test_posture_change_reference_resets_after_event() -> None:
    """Sau khi phát, hướng mới là tham chiếu: nằm yên ở hướng mới không phát lại."""
    seq = (
        lying_established()
        .turn_over(seconds=1)
        .hold(seconds=STABLE + 1)
        .hold(seconds=CONFIG.debounce.same_code_same_session_s + 5)
        .build()
    )
    assert codes(run_engine(seq)) == ["POSTURE_CHANGE"]


# ---- Ca âm tính mục 6 ----


def test_nurse_outside_roi_no_events() -> None:
    seq = (
        lying_established()
        .add_person_outside_roi()
        .lying(seconds=5)
        .remove_extra_people()
        .add_person_outside_roi(OUTSIDE)
        .lying(seconds=5)
        .build()
    )
    assert codes(run_engine(seq)) == []


def test_two_people_in_roi_no_body_events() -> None:
    seq = (
        lying_established()
        .add_second_person_in_roi()
        .raise_to_sitting(seconds=1.5)
        .sitting(seconds=MIN.SITTING + 1)
        .move_to_edge(seconds=1)
        .pose(AT_EDGE, seconds=MIN.AT_EDGE + 1)
        .build()
    )
    outs = run_engine(seq)
    assert outs[-1].state.body_state == S.NO_OBSERVATION
    assert codes(outs) == []


# ---- AC5 ----


SEQUENCES: dict[str, Callable[[], list[FrameObservation]]] = {
    "sit_up": lambda: sitting_established().build(),
    "exit_and_return": lambda: (
        exited().move_to(SITTING, seconds=2).sitting(seconds=MIN.RETURN_TO_BED + 1).build()
    ),
    "turn_over": lambda: lying_established().turn_over(seconds=1).hold(seconds=STABLE + 1).build(),
    "occluded_exit": lambda: (
        at_edge_established()
        .drop_landmarks(seconds=LOST + 1)
        .pose(STANDING.moved_to((640, 680)), seconds=RESTORE + MIN.OUT_OF_BED + 1)
        .build()
    ),
}


def test_every_body_event_has_required_fields() -> None:
    seen: set[EventCode] = set()
    for name, make in SEQUENCES.items():
        seq = make()
        engine = Engine(CONFIG, context())
        outs = [engine.process(obs) for obs in seq]
        for obs, out in zip(seq, outs, strict=True):
            for ev in out.events:
                if ev.code not in BODY_CODES:
                    continue
                seen.add(ev.code)
                assert ev.priority == default_priority(ev.code), name
                assert 0.0 <= ev.confidence <= 1.0, name
                assert ev.confidence > CONFIG.pose.min_keypoint_visibility, name
                assert ev.observation_quality == Q.GOOD, name
                assert ev.config_hash == engine.config_hash == CONFIG.config_hash(), name
                assert ev.detected_at_ms == obs.ts_ms, name
                assert ev.occurred_at_ms <= ev.detected_at_ms, name
                exp = ev.explanation
                assert exp["rule_id"] == f"body.{ev.code.value.lower()}", name
                for key in ("from_state", "to_state", "held_ms"):
                    assert key in exp, (name, key)
                assert exp["held_ms"] == ev.detected_at_ms - ev.occurred_at_ms, name
    assert seen == {
        EventCode.SIT_UP,
        EventCode.BED_EDGE,
        EventCode.STAND_UP,
        EventCode.BED_EXIT,
        EventCode.RETURN_TO_BED,
        EventCode.POSTURE_CHANGE,
    }


def test_body_events_deterministic() -> None:
    seq = SEQUENCES["exit_and_return"]()
    a = [e.model_dump_json() for e in events(run_engine(seq))]
    b = [e.model_dump_json() for e in events(run_engine(seq))]
    assert a == b and a
