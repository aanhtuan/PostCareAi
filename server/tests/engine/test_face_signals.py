"""F26 AC1, AC4: tín hiệu khuôn mặt theo thời gian trong `BodyStateSnapshot` (R1–R3).

Chuỗi pose nằm yên (`PoseSequence`) + kịch bản mặt tổng hợp (`face_builders`). Ngưỡng, hệ số làm
mượt và thời lượng lấy từ `engine.default.yaml`; không viết cứng.
"""

from postcare.schemas.enums import FaceStatus
from postcare.schemas.events import EngineOutput
from postcare.schemas.observation import FrameObservation
from tests.engine.builders import PoseSequence, default_config, run_engine
from tests.engine.face_builders import OFF, ON, all_keys, face, with_face

CONFIG = default_config()
FACE = CONFIG.face
SIG = FACE.signals
FPS = 15
LEAD_S = 6.0
"""Đoạn đầu mặt trung tính: đủ để cổng chất lượng mở và `LYING` ổn định."""


def lying(seconds: float) -> list[FrameObservation]:
    return PoseSequence(fps=FPS).lying(seconds=seconds).build()


def at(outs: list[EngineOutput], t_s: float) -> EngineOutput:
    """Output của frame cuối có `ts_ms` ≤ `t_s`."""
    ms = t_s * 1000
    return [o for o, f in zip(outs, FRAMES_TS, strict=False) if f <= ms][-1]


FRAMES_TS: list[int] = [round(i * 1000 / FPS) for i in range(100_000)]


def test_face_signals_on_off_with_threshold() -> None:
    frames = with_face(
        lying(LEAD_S + 9),
        [
            face(seconds=LEAD_S),
            face(signals={"brow_down": ON, "nose_sneer": ON, "mouth_change": ON}, seconds=4),
            face(seconds=5),
        ],
    )
    outs = run_engine(frames)
    on = at(outs, LEAD_S + 3).state
    assert on.face_status == FaceStatus.OK
    assert on.face_signals.brow_down
    assert on.face_signals.nose_sneer
    assert on.face_signals.mouth_change
    assert not on.face_signals.eyes_closed
    assert not on.face_signals.eye_squint
    off = at(outs, LEAD_S + 8).state
    assert off.face_status == FaceStatus.OK
    assert not any(off.face_signals.model_dump().values())


def test_face_signals_below_threshold_stay_off() -> None:
    """Giá trị dao động ngay dưới ngưỡng → không bật (âm tính)."""
    just_below = {
        "eyes_closed": SIG.eyes_closed.threshold - 0.02,
        "brow_down": SIG.brow_down.threshold - 0.02,
        "eye_squint": SIG.eye_squint.threshold - 0.02,
        "nose_sneer": SIG.nose_sneer.threshold - 0.02,
        "mouth_change": SIG.mouth_change.threshold - 0.02,
    }
    segments = [face(seconds=LEAD_S)]
    for i in range(20):
        segments.append(face(signals=just_below if i % 2 else {}, seconds=0.5))
    outs = run_engine(with_face(lying(LEAD_S + 10), segments))
    assert all(not any(o.state.face_signals.model_dump().values()) for o in outs)
    assert any(o.state.face_status == FaceStatus.OK for o in outs)


def test_face_signal_single_frame_spike_smoothed() -> None:
    """Một frame có blendshape = 1 giữa các frame trung tính → EMA không vượt ngưỡng (âm tính)."""
    frames = lying(LEAD_S + 4)
    spike_i = round((LEAD_S + 1) * FPS)
    base = with_face(frames, [face(seconds=LEAD_S + 4)])
    spike = with_face([base[spike_i]], [face(signals={"brow_down": 1.0}, seconds=1)])[0]
    seq = [*base[:spike_i], spike, *base[spike_i + 1 :]]
    outs = run_engine(seq)
    assert all(not o.state.face_signals.brow_down for o in outs)


def test_signal_uses_max_of_keys() -> None:
    """Một trong các khóa của tín hiệu vượt ngưỡng (bên trái) là đủ (R1: gộp bằng max)."""
    keys = all_keys(CONFIG)
    shapes = {k: OFF for ks in keys.values() for k in ks}
    shapes[keys["eye_squint"][0]] = ON
    frames = with_face(
        lying(LEAD_S + 3), [face(seconds=LEAD_S), face(blendshapes=shapes, seconds=3)]
    )
    assert at(run_engine(frames), LEAD_S + 2.5).state.face_signals.eye_squint


def test_face_signals_hold_on_skipped_frames() -> None:
    """`face = None` ở frame không chạy face → giữ tín hiệu gần nhất (R3)."""
    frames = with_face(
        lying(LEAD_S + 4),
        [face(seconds=LEAD_S), face(signals={"brow_down": ON}, seconds=4)],
        every_n=FACE.run_every_n_frames + 1,
    )
    outs = run_engine(frames)
    tail = outs[round((LEAD_S + 2) * FPS) :]
    assert all(o.state.face_signals.brow_down for o in tail)
    assert all(o.state.face_status == FaceStatus.OK for o in tail)


def test_eyes_closed_prolonged() -> None:
    hold = FACE.eyes_closed_prolonged_s
    frames = with_face(
        lying(LEAD_S + hold + 3),
        [face(seconds=LEAD_S), face(signals={"eyes_closed": ON}, seconds=hold + 3)],
    )
    outs = run_engine(frames)
    before = at(outs, LEAD_S + hold - 1).state.face_signals
    assert before.eyes_closed
    assert not before.eyes_closed_prolonged
    after = at(outs, LEAD_S + hold + 2).state.face_signals
    assert after.eyes_closed
    assert after.eyes_closed_prolonged


def test_eyes_closed_prolonged_resets_when_eyes_open() -> None:
    """Mở mắt giữa chừng → đếm lại từ đầu (âm tính)."""
    hold = FACE.eyes_closed_prolonged_s
    half = hold * 0.6
    frames = with_face(
        lying(LEAD_S + 2 * half + 1),
        [
            face(seconds=LEAD_S),
            face(signals={"eyes_closed": ON}, seconds=half),
            face(seconds=1),
            face(signals={"eyes_closed": ON}, seconds=half),
        ],
    )
    assert all(not o.state.face_signals.eyes_closed_prolonged for o in run_engine(frames))


def test_face_too_small_no_signals() -> None:
    """`TOO_SMALL` / `LOW_CONFIDENCE` → không tín hiệu; trạng thái mặt báo đúng lớp (AC4)."""
    for status in (FaceStatus.TOO_SMALL, FaceStatus.LOW_CONFIDENCE, FaceStatus.NOT_VISIBLE):
        frames = with_face(lying(LEAD_S + 4), [face(seconds=LEAD_S + 4, status=status)])
        outs = run_engine(frames)
        assert all(not any(o.state.face_signals.model_dump().values()) for o in outs)
        assert outs[-1].state.face_status == status


def test_face_not_ok_clears_signals_immediately() -> None:
    """Mặt quay đi (NOT_VISIBLE) → xóa ngay mọi tín hiệu, không giữ giá trị cũ (R3)."""
    frames = with_face(
        lying(LEAD_S + 4),
        [
            face(seconds=LEAD_S),
            face(signals={"brow_down": ON, "eye_squint": ON}, seconds=2),
            face(seconds=2, status=FaceStatus.NOT_VISIBLE),
        ],
    )
    outs = run_engine(frames)
    assert at(outs, LEAD_S + 1.9).state.face_signals.brow_down
    first_lost = round((LEAD_S + 2) * FPS)
    for o in outs[first_lost:]:
        assert o.state.face_status == FaceStatus.NOT_VISIBLE
        assert not any(o.state.face_signals.model_dump().values())


def test_no_face_data_is_not_visible() -> None:
    """Không bao giờ có dữ liệu mặt → `NOT_VISIBLE`, không tín hiệu (không coi là bình thường)."""
    outs = run_engine(lying(LEAD_S))
    assert all(o.state.face_status == FaceStatus.NOT_VISIBLE for o in outs)
    assert all(not any(o.state.face_signals.model_dump().values()) for o in outs)
