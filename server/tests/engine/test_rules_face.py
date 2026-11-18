"""F26 AC2, AC3, R7 và ca âm tính: sự kiện `FACE_ATTENTION` (event-engine.md mục 5, 8).

Chuỗi pose (`PoseSequence`) + kịch bản mặt tổng hợp (`face_builders`). Thời lượng lấy từ
`engine.default.yaml`.
"""

from typing import Any

from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.enums import FaceStatus, Priority
from postcare.schemas.events import EngineEvent, EventCode
from postcare.schemas.observation import FrameObservation
from tests.engine.builders import ROOT, PoseSequence, default_config, events, run_engine
from tests.engine.face_builders import ON, face, with_face

CONFIG = default_config()
FACE = CONFIG.face
HOLD = FACE.attention_hold_s
FPS = 15
LEAD_S = 6.0
"""Đoạn đầu mặt trung tính: đủ để cổng chất lượng mở và `LYING` ổn định."""
TWO = {"brow_down": ON, "eye_squint": ON}
VIGOROUS = 3 * CONFIG.activity.high_threshold


def cfg(overrides: dict[str, Any]) -> EngineConfig:
    return EngineConfig.load(ROOT / "config" / "engine.default.yaml", overrides)


def face_events(
    frames: list[FrameObservation], config: EngineConfig | None = None
) -> list[EngineEvent]:
    outs = run_engine(frames, config)
    return [e for e in events(outs) if e.code == EventCode.FACE_ATTENTION]


def body_codes(frames: list[FrameObservation]) -> list[str]:
    return [e.code.value for e in events(run_engine(frames)) if e.code != EventCode.FACE_ATTENTION]


def lying(seconds: float) -> list[FrameObservation]:
    return PoseSequence(fps=FPS).lying(seconds=seconds).build()


# ---- AC2 ----


def test_face_attention_two_signals_held() -> None:
    frames = with_face(lying(LEAD_S + HOLD + 3), [face(seconds=LEAD_S), face(TWO, HOLD + 3)])
    found = face_events(frames)
    assert len(found) == 1
    ev = found[0]
    assert ev.priority == Priority.MEDIUM
    ex = ev.explanation
    assert ex["rule_id"] == "face_attention"
    assert set(ex["signals"]) >= {"brow_down", "eye_squint"}  # type: ignore[arg-type]
    assert ex["held_ms"] >= HOLD * 1000  # type: ignore[operator]
    assert ex["activity_level"] is not None
    assert "escalated_by" not in ex
    assert ev.detected_at_ms - ev.occurred_at_ms >= HOLD * 1000
    assert ev.occurred_at_ms >= LEAD_S * 1000
    assert ev.detected_at_ms <= (LEAD_S + HOLD + 1) * 1000


def test_short_brow_down_while_lying_no_event() -> None:
    """Hạ lông mày + nheo ngắn hơn `attention_hold_s` khi nằm yên → không sự kiện (PDF §7.4)."""
    frames = with_face(
        lying(LEAD_S + 3 * HOLD),
        [
            face(seconds=LEAD_S),
            face(TWO, HOLD * 0.5),
            face(seconds=HOLD),
            face(TWO, HOLD * 0.5),
            face(seconds=HOLD),
        ],
    )
    assert face_events(frames) == []


def test_single_signal_long_no_event() -> None:
    """Một tín hiệu kéo dài (< `attention_min_signals`) → không sự kiện."""
    for name in ("brow_down", "eyes_closed", "mouth_change"):
        frames = with_face(
            lying(LEAD_S + 4 * HOLD), [face(seconds=LEAD_S), face({name: ON}, 4 * HOLD)]
        )
        assert face_events(frames) == [], name


def test_eyes_closed_and_prolonged_count_once() -> None:
    """Nhắm mắt kéo dài không được đếm thêm: chỉ nhóm mắt → không sự kiện (R2)."""
    long_s = FACE.eyes_closed_prolonged_s + 2 * HOLD
    frames = with_face(
        lying(LEAD_S + long_s), [face(seconds=LEAD_S), face({"eyes_closed": ON}, long_s)]
    )
    outs = run_engine(frames)
    assert outs[-1].state.face_signals.eyes_closed_prolonged
    assert [e for e in events(outs) if e.code == EventCode.FACE_ATTENTION] == []


def test_signals_interrupted_by_skipped_face_still_count() -> None:
    """Frame không chạy face giữa đoạn giữ không cắt đoạn (R3)."""
    frames = with_face(
        lying(LEAD_S + HOLD + 3),
        [face(seconds=LEAD_S), face(TWO, HOLD + 3)],
        every_n=FACE.run_every_n_frames,
    )
    assert len(face_events(frames)) == 1


def test_face_attention_requires_target() -> None:
    """Không có người mục tiêu (`NO_OBSERVATION`) → không sự kiện dù blendshape bật."""
    frames = PoseSequence(fps=FPS).drop_landmarks(LEAD_S + HOLD + 3, mode="missing").build()
    assert face_events(with_face(frames, [face(TWO, LEAD_S + HOLD + 3)])) == []


def test_min_signals_from_config() -> None:
    """`attention_min_signals` = 3 → hai tín hiệu không đủ, ba tín hiệu thì đủ."""
    config = cfg({"face": {"attention_min_signals": 3}})
    two = with_face(lying(LEAD_S + HOLD + 3), [face(seconds=LEAD_S), face(TWO, HOLD + 3)], config)
    assert face_events(two, config) == []
    three = with_face(
        lying(LEAD_S + HOLD + 3),
        [face(seconds=LEAD_S), face({**TWO, "nose_sneer": ON}, HOLD + 3)],
        config,
    )
    assert len(face_events(three, config)) == 1


# ---- AC4 ----


def test_face_not_ok_clears_signals_and_no_event() -> None:
    """Mặt quay đi giữa chừng → bộ đếm reset; tổng thời gian > hold nhưng không đoạn nào đủ."""
    part = HOLD * 0.7
    frames = with_face(
        lying(LEAD_S + 2 * part + 1),
        [
            face(seconds=LEAD_S),
            face(TWO, part),
            face(seconds=1, status=FaceStatus.NOT_VISIBLE),
            face(TWO, part),
        ],
    )
    assert face_events(frames) == []


def test_face_too_small_never_attention() -> None:
    frames = with_face(
        lying(LEAD_S + 3 * HOLD), [face(seconds=LEAD_S + 3 * HOLD, status=FaceStatus.TOO_SMALL)]
    )
    assert face_events(frames) == []


# ---- AC3 ----


def test_face_attention_medium_when_still() -> None:
    frames = with_face(lying(LEAD_S + HOLD + 2), [face(seconds=LEAD_S), face(TWO, HOLD + 2)])
    (ev,) = face_events(frames)
    assert ev.priority == Priority.MEDIUM
    assert "escalated_by" not in ev.explanation


def test_face_attention_escalates_with_high_activity() -> None:
    fill = CONFIG.activity.sample_interval_s + CONFIG.activity.window_s
    pre = LEAD_S + fill
    seq = (
        PoseSequence(fps=FPS)
        .lying(seconds=LEAD_S)
        .limb_motion(seconds=fill + HOLD + 3, speed_torso_per_s=VIGOROUS, whole_body=True)
        .build()
    )
    frames = with_face(seq, [face(seconds=pre), face(TWO, HOLD + 3)])
    (ev,) = face_events(frames)
    assert ev.priority == Priority.HIGH
    assert "activity_high" in ev.explanation["escalated_by"]  # type: ignore[operator]


def test_face_attention_escalates_with_state_change() -> None:
    seq = (
        PoseSequence(fps=FPS)
        .lying(seconds=LEAD_S + 0.5)
        .raise_to_sitting(seconds=1.0)
        .sitting(seconds=HOLD + 2)
        .build()
    )
    frames = with_face(seq, [face(seconds=LEAD_S), face(TWO, HOLD + 3.5)])
    (ev,) = face_events(frames)
    assert ev.priority == Priority.HIGH
    assert "state_change" in ev.explanation["escalated_by"]  # type: ignore[operator]


def test_no_observation_transition_not_state_change() -> None:
    """Mất quan sát rồi có lại (vào/ra `NO_OBSERVATION`) không tính là đổi trạng thái."""
    lost = CONFIG.quality.low_quality_to_no_observation_s + 1
    seq = (
        PoseSequence(fps=FPS)
        .lying(seconds=LEAD_S)
        .drop_landmarks(lost, mode="missing")
        .lying(seconds=LEAD_S + HOLD + 2)
        .build()
    )
    frames = with_face(seq, [face(TWO, 2 * LEAD_S + lost + HOLD + 2)])
    found = face_events(frames)
    assert found
    assert all(e.priority == Priority.MEDIUM for e in found)
    assert all("escalated_by" not in e.explanation for e in found)


# ---- R7 ----


def test_face_attention_debounced() -> None:
    """Hai đoạn giữ cách nhau < `debounce.same_code_same_session_s` → chỉ một sự kiện."""
    gap = 2.0
    assert 2 * (HOLD + 1) + gap < CONFIG.debounce.same_code_same_session_s
    frames = with_face(
        lying(LEAD_S + 2 * (HOLD + 1) + gap),
        [face(seconds=LEAD_S), face(TWO, HOLD + 1), face(seconds=gap), face(TWO, HOLD + 1)],
    )
    assert len(face_events(frames)) == 1


def test_face_attention_once_per_held_segment() -> None:
    """Giữ liên tục rất lâu (quá cửa sổ debounce) → vẫn chỉ phát một lần cho đoạn đó."""
    long_s = CONFIG.debounce.same_code_same_session_s + 2 * HOLD
    frames = with_face(lying(LEAD_S + long_s), [face(seconds=LEAD_S), face(TWO, long_s)])
    assert len(face_events(frames)) == 1


# ---- cô lập ----


def test_face_does_not_change_body_events() -> None:
    """Cùng chuỗi pose có/không có face (kể cả mặt bật tín hiệu) → cùng sự kiện cơ thể."""
    seq = (
        PoseSequence(fps=FPS)
        .lying(seconds=LEAD_S)
        .raise_to_sitting(seconds=1.5)
        .sitting(seconds=4)
        .move_to_edge(seconds=1.5)
        .hold(seconds=3)
        .build()
    )
    with_signals = with_face(seq, [face(seconds=LEAD_S), face(TWO, 30)])
    not_visible = with_face(seq, [face(seconds=30, status=FaceStatus.NOT_VISIBLE)])
    baseline = body_codes(seq)
    assert baseline
    assert body_codes(with_signals) == baseline
    assert body_codes(not_visible) == baseline
