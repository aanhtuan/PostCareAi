"""F17 R16, AC4: `OBSERVATION_LOST` (INFO) / `OBSERVATION_RESTORED` (LOG) do engine phát.

Thời lượng lấy từ `engine.default.yaml` (không viết cứng ngưỡng). Chuỗi chạy cả `Engine` (cổng
chất lượng F13, state machine F14, debounce F15).
"""

from postcare.engine import Engine
from postcare.schemas.enums import Priority
from postcare.schemas.events import EngineEvent, EngineOutput, EventCode, default_priority
from postcare.schemas.state import BodyState as S
from tests.engine.builders import (
    AT_EDGE,
    PoseSequence,
    context,
    default_config,
    run_engine,
)
from tests.engine.builders import codes as all_codes
from tests.engine.builders import events as all_events

CONFIG = default_config()
LOST_EVENT_S = CONFIG.quality.observation_lost_event_s
TO_NO_OBS_S = CONFIG.quality.low_quality_to_no_observation_s
RESTORE_S = CONFIG.quality.restore_duration_s
DEBOUNCE_S = CONFIG.debounce.same_code_same_session_s
# Quan sát lại: cổng mở sau `restore_duration_s`, rồi LYING cần giữ `min_duration_s.LYING`.
BACK_S = RESTORE_S + CONFIG.min_duration_s.LYING + 2
FPS = 15
OBS_CODES = {EventCode.OBSERVATION_LOST, EventCode.OBSERVATION_RESTORED}


def obs_events(outs: list[EngineOutput]) -> list[EngineEvent]:
    return [e for e in all_events(outs) if e.code in OBS_CODES]


def obs_codes(outs: list[EngineOutput]) -> list[str]:
    return [e.code.value for e in obs_events(outs)]


def lying_observed() -> PoseSequence:
    """Đã quan sát ổn định (cổng mở) trước khi bị che."""
    return PoseSequence(fps=FPS).lying(seconds=RESTORE_S + 3)


def test_prolonged_no_observation_emits_observation_lost_info() -> None:
    seq = lying_observed().drop_landmarks(seconds=TO_NO_OBS_S + LOST_EVENT_S + 2).build()
    outs = run_engine(seq)
    evs = obs_events(outs)
    assert [e.code for e in evs] == [EventCode.OBSERVATION_LOST]
    ev = evs[0]
    assert ev.priority == Priority.INFO == default_priority(EventCode.OBSERVATION_LOST)
    # Phát đúng một lần khi NO_OBSERVATION giữ đủ ngưỡng; occurred_at = đầu chuỗi NO_OBSERVATION.
    i = next(i for i, o in enumerate(outs) if ev in o.events)
    first_no_obs = next(
        k
        for k in range(i, -1, -1)
        if outs[k].state.body_state == S.NO_OBSERVATION
        and (k == 0 or outs[k - 1].state.body_state != S.NO_OBSERVATION)
    )
    assert ev.occurred_at_ms == seq[first_no_obs].ts_ms
    assert ev.detected_at_ms == seq[i].ts_ms
    assert ev.detected_at_ms - ev.occurred_at_ms >= LOST_EVENT_S * 1000
    assert ev.detected_at_ms - seq[i - 1].ts_ms > 0
    assert seq[i - 1].ts_ms - ev.occurred_at_ms < LOST_EVENT_S * 1000
    assert ev.explanation["rule_id"] == "observation.observation_lost"
    assert ev.explanation["held_ms"] == ev.detected_at_ms - ev.occurred_at_ms
    assert ev.config_hash == CONFIG.config_hash()
    assert 0.0 <= ev.confidence <= 1.0


def test_restored_only_after_lost() -> None:
    seq = (
        lying_observed()
        .drop_landmarks(seconds=TO_NO_OBS_S + LOST_EVENT_S + 1)
        .lying(seconds=BACK_S)
        .build()
    )
    outs = run_engine(seq)
    assert obs_codes(outs) == ["OBSERVATION_LOST", "OBSERVATION_RESTORED"]
    restored = obs_events(outs)[1]
    assert restored.priority == Priority.LOG == default_priority(EventCode.OBSERVATION_RESTORED)
    i = next(i for i, o in enumerate(outs) if restored in o.events)
    # Phát ở frame đầu tiên thoát NO_OBSERVATION.
    assert outs[i - 1].state.body_state == S.NO_OBSERVATION
    assert outs[i].state.body_state != S.NO_OBSERVATION
    assert restored.explanation["rule_id"] == "observation.observation_restored"
    lost = obs_events(outs)[0]
    assert restored.explanation["lost_ms"] == restored.detected_at_ms - lost.occurred_at_ms


def test_short_occlusion_no_observation_lost() -> None:
    """Bị che ở mép giường, ngắn hơn ngưỡng: NO_OBSERVATION nhưng không LOST/RESTORED/BED_EXIT."""
    seq = (
        PoseSequence(fps=FPS, start=AT_EDGE)
        .pose(AT_EDGE, seconds=RESTORE_S + 3)
        .drop_landmarks(seconds=TO_NO_OBS_S + LOST_EVENT_S / 2)
        .pose(AT_EDGE, seconds=RESTORE_S + 2)
        .build()
    )
    outs = run_engine(seq)
    assert any(o.state.body_state == S.NO_OBSERVATION for o in outs[FPS * 5 :])
    codes = all_codes(outs)
    assert "OBSERVATION_LOST" not in codes
    assert "OBSERVATION_RESTORED" not in codes
    assert "BED_EXIT" not in codes


def test_missing_person_prolonged_never_bed_exit() -> None:
    seq = (
        PoseSequence(fps=FPS, start=AT_EDGE)
        .pose(AT_EDGE, seconds=RESTORE_S + 3)
        .drop_landmarks(seconds=TO_NO_OBS_S + LOST_EVENT_S + 1, mode="missing")
        .build()
    )
    codes = all_codes(run_engine(seq))
    assert "OBSERVATION_LOST" in codes
    assert "BED_EXIT" not in codes


def test_observation_lost_debounced() -> None:
    """Hai lần mất quan sát dài trong cửa sổ debounce: một LOST; RESTORED chỉ sau LOST đã phát."""
    gap = TO_NO_OBS_S + LOST_EVENT_S + 1
    assert 2 * (gap + BACK_S) < DEBOUNCE_S  # cả hai lần nằm trong cửa sổ debounce
    seq = (
        lying_observed()
        .drop_landmarks(seconds=gap)
        .lying(seconds=BACK_S)
        .drop_landmarks(seconds=gap)
        .lying(seconds=BACK_S)
        .build()
    )
    assert obs_codes(run_engine(seq)) == ["OBSERVATION_LOST", "OBSERVATION_RESTORED"]


def test_startup_without_observation_counts_as_lost() -> None:
    """Engine khởi động khi không thấy ai (cổng đóng): giữ đủ ngưỡng → một LOST (giả định)."""
    seq = PoseSequence(fps=FPS).drop_landmarks(seconds=LOST_EVENT_S + 1, mode="missing").build()
    outs = run_engine(seq)
    evs = obs_events(outs)
    assert [e.code for e in evs] == [EventCode.OBSERVATION_LOST]
    assert evs[0].occurred_at_ms == seq[0].ts_ms


def test_no_restored_without_lost_at_startup() -> None:
    """Khởi động bình thường (cổng mở sau `restore_duration_s`) không phát RESTORED."""
    outs = run_engine(lying_observed().build())
    assert obs_codes(outs) == []


def test_new_engine_starts_fresh() -> None:
    """Mỗi `Engine` (một phiên) có trạng thái riêng: không phát RESTORED của engine cũ."""
    seq = lying_observed().drop_landmarks(seconds=TO_NO_OBS_S + LOST_EVENT_S + 1).build()
    first = Engine(CONFIG, context())
    assert "OBSERVATION_LOST" in [e.code.value for obs in seq for e in first.process(obs).events]
    second = Engine(CONFIG, context())
    outs = [second.process(o) for o in lying_observed().build()]
    assert obs_codes(outs) == []


def test_restored_not_debounced_when_its_lost_was_emitted() -> None:
    """Mất 0 s → LOST 10 s → quan sát lại ~55 s; mất lại ~60 s → LOST ~70 s (đã qua cửa sổ
    debounce của LOST đầu) → quan sát lại ~75 s: RESTORED thứ hai vẫn phát dù cách RESTORED đầu
    < `same_code_same_session_s` (review F17: RESTORED đi cặp với LOST đã phát)."""
    first_missing = DEBOUNCE_S - BACK_S + 2  # chuỗi 1: 0 → ~55 s (khởi động không thấy ai)
    seq = (
        PoseSequence(fps=FPS)
        .drop_landmarks(seconds=first_missing, mode="missing")
        .lying(seconds=BACK_S)
        .drop_landmarks(seconds=TO_NO_OBS_S + LOST_EVENT_S + 1, mode="missing")
        .lying(seconds=BACK_S)
        .build()
    )
    evs = obs_events(run_engine(seq))
    assert [e.code.value for e in evs] == [
        "OBSERVATION_LOST",
        "OBSERVATION_RESTORED",
        "OBSERVATION_LOST",
        "OBSERVATION_RESTORED",
    ]
    lost1, restored1, lost2, restored2 = evs
    assert lost2.detected_at_ms - lost1.detected_at_ms >= DEBOUNCE_S * 1000
    assert restored2.detected_at_ms - restored1.detected_at_ms < DEBOUNCE_S * 1000
