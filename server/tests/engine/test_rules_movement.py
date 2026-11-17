"""F23 AC2–AC4 và ca âm tính: `ACTIVITY_INCREASED`, `ACTIVITY_LOW_PROLONGED`, `ABNORMAL_MOVEMENT`.

Mọi chuỗi chạy qua `Engine` trên `PoseSequence` (event-engine.md mục 5, 6). Thời lượng các đoạn
lấy từ `engine.default.yaml`; khi cần rút ngắn (ví dụ `low_prolonged_s` = 300 s) thì override cấu
hình trong test, không viết cứng ngưỡng vào rule.
"""

from typing import Any

import pytest

from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.enums import Priority as EventPriority
from postcare.schemas.events import EngineEvent, EngineOutput, EventCode
from postcare.schemas.state import ActivityLevel as A
from tests.engine.builders import (
    BENT_FORWARD,
    CHAIR_SEATED,
    FLOOR,
    LYING,
    NURSE,
    ROOT,
    SITTING,
    UPRIGHT,
    PoseSequence,
    codes,
    default_config,
    events,
    run_engine,
)

CONFIG = default_config()
ACT = CONFIG.activity
AM = CONFIG.abnormal_movement
RESTORE = CONFIG.quality.restore_duration_s
LOST = CONFIG.quality.low_quality_to_no_observation_s
STABLE = CONFIG.posture_change.stable_s
FPS = 15
ABNORMAL = EventCode.ABNORMAL_MOVEMENT.value
INCREASED = EventCode.ACTIVITY_INCREASED.value
LOW_PROLONGED = EventCode.ACTIVITY_LOW_PROLONGED.value
MOVEMENT_CODES = {ABNORMAL, INCREASED, LOW_PROLONGED}
FILL_S = ACT.sample_interval_s + ACT.window_s
SETTLE_S = RESTORE + max(FILL_S, AM.window_s) + 1
AFTER_S = AM.window_s + AM.hold_after_s + 2
"""Sau chuyển động: đủ để cửa sổ trượt qua chuyển động rồi giữ `hold_after_s`."""
VIGOROUS = 3 * ACT.high_threshold
FLOOR_IN_ROI = FLOOR.moved_to((700, 560))
"""Nằm thấp nhưng tâm hông vẫn trong ROI (để người mục tiêu không rời ROI)."""


def cfg(overrides: dict[str, Any]) -> EngineConfig:
    return EngineConfig.load(ROOT / "config" / "engine.default.yaml", overrides)


def movement_codes(outs: list[EngineOutput]) -> list[str]:
    return [c for c in codes(outs) if c in MOVEMENT_CODES]


def only(outs: list[EngineOutput], code: str) -> EngineEvent:
    found = [e for e in events(outs) if e.code.value == code]
    assert len(found) == 1, f"cần đúng 1 {code}, có {codes(outs)}"
    return found[0]


def upright() -> PoseSequence:
    """Đứng yên đủ lâu để qua cổng phục hồi và lấp cửa sổ vận động."""
    return PoseSequence(fps=FPS, start=UPRIGHT).hold(seconds=SETTLE_S)


def fall() -> PoseSequence:
    return upright().fast_drop(seconds=0.6).hold(seconds=AFTER_S)


# ---- AC2: ACTIVITY_INCREASED, ACTIVITY_LOW_PROLONGED (LOG) ----


def test_activity_increased_after_hold() -> None:
    seq = PoseSequence(fps=FPS).lying(seconds=SETTLE_S)
    seq.limb_motion(
        seconds=ACT.increased_hold_s + FILL_S, speed_torso_per_s=VIGOROUS, whole_body=True
    )
    outs = run_engine(seq.build())
    ev = only(outs, INCREASED)
    assert ev.detected_at_ms - ev.occurred_at_ms >= ACT.increased_hold_s * 1000
    assert ev.explanation["rule_id"] == "movement.activity_increased"
    assert ev.explanation["activity_level"] == A.HIGH.value
    assert float(ev.explanation["activity_index"]) > ACT.high_threshold  # type: ignore[arg-type]
    i = next(i for i, o in enumerate(outs) if ev in o.events)
    assert outs[i].state.activity_level == A.HIGH


def test_brief_high_activity_no_activity_increased() -> None:
    """Vận động mạnh quá ngắn: mức HIGH không giữ đủ `increased_hold_s`."""
    seq = PoseSequence(fps=FPS).lying(seconds=SETTLE_S)
    seq.limb_motion(seconds=0.4, speed_torso_per_s=VIGOROUS, whole_body=True)
    seq.lying(seconds=FILL_S + 2)
    outs = run_engine(seq.build())
    assert INCREASED not in codes(outs)


def low_prolonged_config() -> EngineConfig:
    return cfg({"activity": {"low_prolonged_s": 20.0}})


def test_activity_low_prolonged_after_threshold() -> None:
    config = low_prolonged_config()
    lying_s = RESTORE + FILL_S + config.activity.low_prolonged_s + 2
    outs = run_engine(PoseSequence(fps=FPS).lying(seconds=lying_s).build(), config=config)
    ev = only(outs, LOW_PROLONGED)
    assert ev.detected_at_ms - ev.occurred_at_ms >= config.activity.low_prolonged_s * 1000
    assert ev.explanation["rule_id"] == "movement.activity_low_prolonged"
    assert ev.explanation["activity_level"] == A.LOW.value


def test_activity_low_prolonged_default_threshold() -> None:
    """Ngưỡng mặc định (300 s) ở fps thấp để test nhanh: phát đúng một lần, sau ngưỡng."""
    fps = 3
    seq = PoseSequence(fps=fps).lying(seconds=RESTORE + FILL_S + ACT.low_prolonged_s + 5)
    outs = run_engine(seq.build())
    ev = only(outs, LOW_PROLONGED)
    assert ev.detected_at_ms - ev.occurred_at_ms >= ACT.low_prolonged_s * 1000


def test_low_shorter_than_threshold_no_event() -> None:
    config = low_prolonged_config()
    lying_s = RESTORE + FILL_S + config.activity.low_prolonged_s - 2
    outs = run_engine(PoseSequence(fps=FPS).lying(seconds=lying_s).build(), config=config)
    assert LOW_PROLONGED not in codes(outs)


def test_low_prolonged_emitted_once_per_segment() -> None:
    config = cfg(
        {"activity": {"low_prolonged_s": 20.0}, "debounce": {"same_code_same_session_s": 1}}
    )
    lying_s = RESTORE + FILL_S + 3 * config.activity.low_prolonged_s
    outs = run_engine(PoseSequence(fps=FPS).lying(seconds=lying_s).build(), config=config)
    assert codes(outs).count(LOW_PROLONGED) == 1


@pytest.mark.parametrize("mode", ["low_visibility", "missing"])
def test_occlusion_resets_low_prolonged_counter(mode: str) -> None:
    """Nằm yên xen một đoạn mất quan sát: bộ đếm reset, mất quan sát không tính là ít vận động."""
    config = low_prolonged_config()
    half = config.activity.low_prolonged_s * 0.6
    seq = (
        PoseSequence(fps=FPS)
        .lying(seconds=RESTORE + FILL_S + half)
        .drop_landmarks(seconds=LOST + 2, mode=mode)
        .lying(seconds=RESTORE + FILL_S + half)
    )
    outs = run_engine(seq.build(), config=config)
    assert LOW_PROLONGED not in codes(outs)


def test_activity_events_are_log() -> None:
    config = cfg({"activity": {"low_prolonged_s": 20.0}})
    seq = PoseSequence(fps=FPS).lying(seconds=RESTORE + FILL_S + 22)
    seq.limb_motion(
        seconds=ACT.increased_hold_s + FILL_S, speed_torso_per_s=VIGOROUS, whole_body=True
    )
    outs = run_engine(seq.build(), config=config)
    found = {e.code.value: e for e in events(outs) if e.code.value in {INCREASED, LOW_PROLONGED}}
    assert set(found) == {INCREASED, LOW_PROLONGED}
    for e in found.values():
        assert e.priority == EventPriority.LOG
        assert 0.0 <= e.confidence <= 1.0
        assert e.config_hash == config.config_hash()
        assert e.occurred_at_ms <= e.detected_at_ms
        assert "held_ms" in e.explanation
        assert "window_s" in e.explanation


# ---- AC3: ABNORMAL_MOVEMENT (HIGH) ----


def test_fast_drop_emits_abnormal_movement_high() -> None:
    before = upright()
    drop_start = before.ts_ms
    seq = before.fast_drop(seconds=0.6)
    drop_end = seq.ts_ms
    seq.hold(seconds=AFTER_S)
    outs = run_engine(seq.build())
    ev = only(outs, ABNORMAL)
    assert ev.priority == EventPriority.HIGH
    # occurred = lúc bắt đầu chuyển động nhanh; detected = sau khi giữ nguyên `hold_after_s`
    assert drop_start <= ev.occurred_at_ms <= drop_end
    assert ev.detected_at_ms >= drop_end + AM.hold_after_s * 1000
    assert ev.config_hash == CONFIG.config_hash()
    assert 0.0 < ev.confidence <= 1.0
    assert ev.explanation["rule_id"] == "movement.abnormal_movement"


def test_explanation_lists_conditions() -> None:
    ev = only(run_engine(fall().build()), ABNORMAL)
    x = ev.explanation
    assert x["conditions_met"] == [
        "hip_drop_speed",
        "displacement",
        "trunk_angle_change",
        "final_low_position",
        "still_after",
    ]
    assert x["min_conditions"] == AM.min_conditions
    assert float(x["hip_drop_speed_torso_per_s"]) >= AM.hip_drop_speed_torso_per_s  # type: ignore[arg-type]
    assert float(x["displacement_torso"]) >= AM.displacement_torso  # type: ignore[arg-type]
    assert float(x["trunk_angle_change_deg"]) >= AM.trunk_angle_change_deg  # type: ignore[arg-type]
    assert float(x["final_position_ratio"]) >= AM.final_low_position_ratio  # type: ignore[arg-type]
    assert float(x["activity_index_after"]) < ACT.low_threshold  # type: ignore[arg-type]


# Ngưỡng không thể đạt cho từng điều kiện → điều kiện đó không thỏa
DISABLE = {
    "hip_drop_speed": {"abnormal_movement": {"hip_drop_speed_torso_per_s": 1000.0}},
    "displacement": {"abnormal_movement": {"displacement_torso": 1000.0}},
    "trunk_angle_change": {"abnormal_movement": {"trunk_angle_change_deg": 180.0}},
    "final_low_position": {"abnormal_movement": {"final_low_position_ratio": 1.0}},
    "still_after": {"activity": {"low_threshold": 0.0}},
}
ALL_CONDITIONS = list(DISABLE)


@pytest.mark.parametrize("missing", ALL_CONDITIONS)
def test_each_condition_counted(missing: str) -> None:
    """Tắt từng điều kiện C1–C5: còn 4 điều kiện → vẫn phát khi `min_conditions = 4`, và
    `conditions_met` không còn điều kiện đã tắt; `min_conditions = 5` → không phát."""
    overrides: dict[str, Any] = {k: dict(v) for k, v in DISABLE[missing].items()}
    overrides.setdefault("abnormal_movement", {})["min_conditions"] = 4
    ev = only(run_engine(fall().build(), config=cfg(overrides)), ABNORMAL)
    assert ev.explanation["conditions_met"] == [c for c in ALL_CONDITIONS if c != missing]

    overrides["abnormal_movement"]["min_conditions"] = 5
    assert ABNORMAL not in codes(run_engine(fall().build(), config=cfg(overrides)))


def test_below_min_conditions_no_event() -> None:
    """Hạ thấp nhanh xuống sàn rồi vẫn cử động mạnh (C5 sai), C4 tắt: chỉ còn 3 < 4 điều kiện."""
    config = cfg({"abnormal_movement": {"min_conditions": 4, "final_low_position_ratio": 1.0}})
    seq = upright().fast_drop(seconds=0.6)
    seq.limb_motion(seconds=AFTER_S, speed_torso_per_s=VIGOROUS)
    assert ABNORMAL not in codes(run_engine(seq.build(), config=config))


def test_abnormal_movement_outside_roi() -> None:
    """Hông cuối ở ngoài ROI (nằm trên sàn cạnh giường) vẫn được xét: mục tiêu còn được bám."""
    outs = run_engine(fall().build())
    assert ABNORMAL in codes(outs)
    assert outs[-1].state.observation_quality.value == "GOOD"


def test_abnormal_movement_debounced() -> None:
    seq = fall().move_to(UPRIGHT, seconds=1.5).hold(seconds=SETTLE_S).fast_drop(seconds=0.6)
    seq.hold(seconds=AFTER_S)
    assert movement_codes(run_engine(seq.build())).count(ABNORMAL) == 1


def test_abnormal_movement_after_debounce_window_emitted_again() -> None:
    config = cfg({"debounce": {"same_code_same_session_s": 1.0}})
    seq = fall().move_to(UPRIGHT, seconds=1.5).hold(seconds=SETTLE_S).fast_drop(seconds=0.6)
    seq.hold(seconds=AFTER_S)
    assert codes(run_engine(seq.build(), config=config)).count(ABNORMAL) == 2


def test_abnormal_movement_deterministic() -> None:
    seq = fall().build()
    first = run_engine(seq)
    second = run_engine(seq)
    assert [o.model_dump_json() for o in first] == [o.model_dump_json() for o in second]


# ---- AC4 và ca âm tính (testing.md mục 2; spec mục 6) ----


def test_turn_over_no_abnormal_movement() -> None:
    seq = (
        PoseSequence(fps=FPS)
        .lying(seconds=SETTLE_S + CONFIG.min_duration_s.LYING)
        .turn_over(seconds=1.0)
        .hold(seconds=STABLE + AFTER_S)
    )
    outs = run_engine(seq.build())
    assert EventCode.POSTURE_CHANGE.value in codes(outs)
    assert ABNORMAL not in codes(outs)


def test_sitting_down_quickly_on_chair_no_abnormal_movement() -> None:
    """Ngồi nhanh xuống ghế: hông hạ nhanh nhưng quãng ngắn, thân thẳng, vị trí cuối không thấp."""
    seq = upright().fast_drop(seconds=0.4, to=CHAIR_SEATED).hold(seconds=AFTER_S)
    assert ABNORMAL not in codes(run_engine(seq.build()))


def test_sitting_down_quickly_on_bed_edge_no_abnormal_movement() -> None:
    seq = upright().fast_drop(seconds=0.4, to=SITTING.moved_to((900, 470))).hold(seconds=AFTER_S)
    assert ABNORMAL not in codes(run_engine(seq.build()))


def test_bending_forward_no_abnormal_movement() -> None:
    seq = (
        upright()
        .move_to(BENT_FORWARD, seconds=0.8)
        .hold(seconds=AFTER_S)
        .move_to(UPRIGHT, seconds=0.8)
        .hold(seconds=AFTER_S)
    )
    assert ABNORMAL not in codes(run_engine(seq.build()))


def test_slow_lie_down_no_abnormal_movement() -> None:
    seq = (
        PoseSequence(fps=FPS, start=SITTING)
        .sitting(seconds=SETTLE_S)
        .move_to(LYING, seconds=2.0)
        .lying(seconds=AFTER_S)
    )
    assert ABNORMAL not in codes(run_engine(seq.build()))


@pytest.mark.parametrize("n", [1, 2, 3])
def test_keypoint_jump_1_to_3_frames_no_movement_event(n: int) -> None:
    """Nhiễu: keypoint nhảy xa 1–3 frame rồi quay về (bộ chọn mục tiêu không nhận bước nhảy)."""
    seq = upright().noise(frames=n, kind="jump").hold(seconds=AFTER_S + ACT.increased_hold_s)
    outs = run_engine(seq.build())
    assert ABNORMAL not in codes(outs)
    assert INCREASED not in codes(outs)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_spike_to_floor_1_to_3_frames_no_abnormal_movement(n: int) -> None:
    """Nhiễu gần: 1–3 frame keypoint lệch về tư thế nằm sàn (vẫn trong ngưỡng bám mục tiêu) rồi
    quay lại đứng. Vị trí cuối không đổi → không đủ điều kiện."""
    seq = upright().frames([FLOOR] * n).pose(UPRIGHT, seconds=AFTER_S + ACT.increased_hold_s)
    outs = run_engine(seq.build())
    assert ABNORMAL not in codes(outs)
    assert INCREASED not in codes(outs)


@pytest.mark.parametrize("mode", ["low_visibility", "missing"])
def test_occlusion_no_abnormal_movement_no_low_activity(mode: str) -> None:
    """Bị che ngay trong lúc hạ thấp: cửa sổ có frame không GOOD → không xét (R8); mất quan sát
    dài không tính là ít vận động."""
    config = low_prolonged_config()
    seq = (
        upright()
        .fast_drop(seconds=0.3)
        .drop_landmarks(seconds=0.5, mode=mode)
        .fast_drop(seconds=0.3)
        .hold(seconds=AFTER_S)
        .drop_landmarks(seconds=config.activity.low_prolonged_s + LOST + 5, mode=mode)
    )
    outs = run_engine(seq.build(), config=config)
    assert ABNORMAL not in codes(outs)
    assert LOW_PROLONGED not in codes(outs)


def test_fast_passerby_outside_roi_no_event() -> None:
    """Điều dưỡng ngoài ROI đi nhanh và cúi xuống sàn: không phải người mục tiêu."""
    seq = PoseSequence(fps=FPS).lying(seconds=SETTLE_S)
    nurse_path = [
        NURSE.moved_to((1150, 300 + 30 * i)) if i < 10 else FLOOR.moved_to((1100, 660))
        for i in range(20)
    ]
    for body in nurse_path:
        seq.add_person_outside_roi(body).lying(seconds=1 / FPS).remove_extra_people()
    seq.add_person_outside_roi(FLOOR.moved_to((1100, 660))).lying(seconds=AFTER_S)
    outs = run_engine(seq.build())
    assert movement_codes(outs) == []


def test_two_people_in_roi_no_movement_event() -> None:
    """Người thứ hai trong ROI suốt chuỗi: NO_OBSERVATION, không xét vận động của ai."""
    seq = (
        upright()
        .add_second_person_in_roi()
        .fast_drop(seconds=0.6, to=FLOOR_IN_ROI)
        .hold(seconds=AFTER_S)
        .limb_motion(
            seconds=ACT.increased_hold_s + FILL_S, speed_torso_per_s=VIGOROUS, whole_body=True
        )
    )
    outs = run_engine(seq.build())
    assert movement_codes(outs) == []


def test_target_switch_no_abnormal_movement() -> None:
    """Mục tiêu biến mất rồi người khác được nhận ở chỗ thấp: bước nhảy không phải chuyển động."""
    seq = upright().drop_landmarks(seconds=LOST + 1, mode="missing").pose(LYING, seconds=AFTER_S)
    assert ABNORMAL not in codes(run_engine(seq.build()))
