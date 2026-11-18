"""F27 AC1–AC3: trạng thái nghỉ/hoạt động tham khảo (`engine/rest.py`; event-engine.md mục 5).

Phần lớn test gọi thẳng `RestTracker` với chuỗi đầu vào tổng hợp (mức vận động, trạng thái mặt, tín
hiệu mắt) để kiểm soát chính xác thời lượng. Một số ca chạy qua `Engine` đầy đủ (`PoseSequence` +
`face_builders`). Thời lượng lấy từ `engine.default.yaml`, không viết cứng.

Đây **không** phải phân loại giấc ngủ: chỉ là mức hoạt động quan sát được (HS §5.3; PDF §4.2).
"""

import itertools
from collections.abc import Iterable
from dataclasses import dataclass

from postcare.engine import Engine
from postcare.engine.activity import ActivityReading
from postcare.engine.face import FaceReading
from postcare.engine.rest import RestTracker
from postcare.schemas.events import EngineOutput
from postcare.schemas.observation import FrameObservation
from postcare.schemas.state import ActivityLevel as A
from postcare.schemas.state import BodyState as S
from postcare.schemas.state import FaceSignals
from postcare.schemas.state import FaceStatus as F
from postcare.schemas.state import RestStatus as R
from tests.engine.builders import PoseSequence, context, default_config
from tests.engine.face_builders import ON, face, with_face

CONFIG = default_config()
REST = CONFIG.rest
FPS = 15
STEP_MS = round(1000 / FPS)
MS = 1000


@dataclass(frozen=True)
class Seg:
    """Một đoạn đầu vào giữ nguyên trong `seconds` (hoặc đúng `frames` frame)."""

    seconds: float = 0.0
    activity: A = A.LOW
    face: F = F.OK
    eyes_closed: bool = False
    body: S = S.LYING
    frames: int | None = None


def _activity(level: A) -> ActivityReading:
    index = None if level == A.UNKNOWN else 0.0
    return ActivityReading(level=level, index=index, sample_speed=None)


def _face(status: F, eyes_closed: bool) -> FaceReading:
    closed = eyes_closed and status == F.OK
    return FaceReading(status=status, signals=FaceSignals(eyes_closed=closed), values={})


def drive(segments: Iterable[Seg], tracker: RestTracker | None = None) -> list[tuple[int, R]]:
    """Chạy tracker qua các đoạn; trả (ts_ms, rest_status) mỗi frame."""
    rest = tracker or RestTracker(CONFIG)
    out: list[tuple[int, R]] = []
    ts = 0
    for seg in segments:
        n = seg.frames if seg.frames is not None else round(seg.seconds * FPS)
        for _ in range(n):
            ts += STEP_MS
            reading = rest.update(
                ts, seg.body, _activity(seg.activity), _face(seg.face, seg.eyes_closed)
            )
            out.append((ts, reading.status))
    return out


def statuses(trace: list[tuple[int, R]]) -> list[R]:
    return [s for _, s in trace]


REST_ENTRY_S = max(REST.low_activity_s, REST.eyes_closed_s) + 1
"""LOW + mắt đóng (mặt rõ) đủ lâu để vào RESTING."""


def resting() -> Seg:
    return Seg(seconds=REST_ENTRY_S, eyes_closed=True)


# ---- AC1 -------------------------------------------------------------------------------------


def test_rest_enters_when_low_activity_and_eyes_closed() -> None:
    trace = drive([resting()])
    assert trace[-1][1] == R.RESTING
    first = next(ts for ts, s in trace if s == R.RESTING)
    # Phải đủ cả hai thời lượng (R1) trước khi vào RESTING.
    assert first >= max(REST.low_activity_s, REST.eyes_closed_s) * MS


def test_brief_low_activity_not_resting() -> None:
    """Âm tính: ít vận động ngắn hơn `rest.low_activity_s` (dù mắt đóng) → không RESTING."""
    short = REST.low_activity_s - 1
    trace = drive([Seg(seconds=short, eyes_closed=True)])
    assert R.RESTING not in statuses(trace)


def test_brief_eyes_closed_not_resting() -> None:
    """Âm tính: LOW đủ lâu nhưng mắt mới đóng < `rest.eyes_closed_s` → không RESTING."""
    trace = drive(
        [
            Seg(seconds=REST.low_activity_s + 1),
            Seg(seconds=REST.eyes_closed_s - 1, eyes_closed=True),
        ]
    )
    assert R.RESTING not in statuses(trace)


def test_low_activity_eyes_open_not_resting() -> None:
    """Âm tính: ít vận động 10 phút nhưng mắt mở, mặt rõ → ACTIVE, không RESTING (R3)."""
    trace = drive([Seg(seconds=600)])
    assert set(statuses(trace)) == {R.ACTIVE}


def test_rest_exits_on_activity_or_eyes_open() -> None:
    hold_frames = round(REST.active_hold_s * FPS) + 2
    # Vận động tăng
    by_activity = drive([resting(), Seg(frames=hold_frames, activity=A.NORMAL, eyes_closed=True)])
    assert by_activity[-1][1] == R.ACTIVE
    # Mắt mở (mặt rõ, vẫn LOW)
    by_eyes = drive([resting(), Seg(frames=hold_frames)])
    assert by_eyes[-1][1] == R.ACTIVE
    # Chuyển chỉ xảy ra sau khi giữ ≥ active_hold_s (R2)
    trace = drive([resting(), Seg(frames=hold_frames, activity=A.HIGH, eyes_closed=True)])
    start = round(REST_ENTRY_S * FPS)
    exit_ts = next(ts for ts, s in trace[start:] if s == R.ACTIVE)
    first_change_ts = trace[start][0]
    assert exit_ts - first_change_ts >= REST.active_hold_s * MS


def test_eyes_open_few_frames_keeps_resting() -> None:
    """Âm tính: mở mắt 1–3 frame (hoặc cử động một nhịp ngắn) → vẫn RESTING (hysteresis)."""
    for n in (1, 2, 3):
        trace = drive(
            [
                resting(),
                Seg(frames=n),
                Seg(seconds=2, eyes_closed=True),
                Seg(frames=n, activity=A.NORMAL, eyes_closed=True),
                Seg(seconds=2, eyes_closed=True),
            ]
        )
        start = round(REST_ENTRY_S * FPS)
        assert set(statuses(trace)[start - 1 :]) == {R.RESTING}


def test_exit_hold_restarts_when_condition_breaks() -> None:
    """Âm tính: các đoạn mở mắt ngắn hơn `active_hold_s`, xen kẽ mắt đóng → không cộng dồn."""
    half = max(1, round(REST.active_hold_s * FPS / 2))
    segs = [resting()]
    for _ in range(6):
        segs += [Seg(frames=half), Seg(frames=2, eyes_closed=True)]
    trace = drive(segs)
    start = round(REST_ENTRY_S * FPS)
    assert set(statuses(trace)[start - 1 :]) == {R.RESTING}


# ---- AC2 -------------------------------------------------------------------------------------


def test_no_resting_without_clear_face() -> None:
    """Mặt `TOO_SMALL` / `NOT_VISIBLE` / `LOW_CONFIDENCE` + ít vận động 10 phút → UNKNOWN."""
    for status in (F.TOO_SMALL, F.NOT_VISIBLE, F.LOW_CONFIDENCE):
        trace = drive([Seg(seconds=600, face=status, eyes_closed=True)])
        assert set(statuses(trace)) == {R.UNKNOWN}, status


def test_resting_to_unknown_when_face_lost() -> None:
    trace = drive([resting(), Seg(frames=1, face=F.NOT_VISIBLE)])
    assert trace[-1][1] == R.UNKNOWN
    # Mặt quay lại với mắt đóng: phải đếm lại `eyes_closed_s`, không quay về RESTING ngay.
    back = drive([resting(), Seg(frames=1, face=F.NOT_VISIBLE), Seg(seconds=1, eyes_closed=True)])
    assert back[-1][1] != R.RESTING


def test_resting_to_unknown_when_face_lost_even_with_activity() -> None:
    """Review F27: đang RESTING mà mặt không rõ → UNKNOWN ngay, bất kể mức vận động."""
    for level in (A.HIGH, A.NORMAL):
        trace = drive([resting(), Seg(frames=1, activity=level, face=F.NOT_VISIBLE)])
        assert trace[-1][1] == R.UNKNOWN, level


def test_eyes_closed_but_face_not_ok_relies_on_activity() -> None:
    """Mặt không rõ: chỉ dựa vào vận động. Vận động không LOW → ACTIVE; LOW → UNKNOWN."""
    moving = drive([Seg(seconds=10, activity=A.NORMAL, face=F.NOT_VISIBLE)])
    assert set(statuses(moving)) == {R.ACTIVE}
    still = drive([Seg(seconds=REST_ENTRY_S, face=F.NOT_VISIBLE, eyes_closed=True)])
    assert set(statuses(still)) == {R.UNKNOWN}


def test_unknown_when_no_observation_or_activity_unknown() -> None:
    no_obs = drive([Seg(seconds=REST_ENTRY_S, body=S.NO_OBSERVATION, eyes_closed=True)])
    assert set(statuses(no_obs)) == {R.UNKNOWN}
    act_unknown = drive([Seg(seconds=REST_ENTRY_S, activity=A.UNKNOWN, eyes_closed=True)])
    assert set(statuses(act_unknown)) == {R.UNKNOWN}
    # Đang RESTING mà mất quan sát → UNKNOWN ngay, không giữ "Đang nghỉ"
    lost = drive([resting(), Seg(frames=1, body=S.NO_OBSERVATION, activity=A.UNKNOWN)])
    assert lost[-1][1] == R.UNKNOWN


def test_initial_status_unknown_then_active() -> None:
    trace = drive([Seg(frames=1, activity=A.UNKNOWN), Seg(frames=1, activity=A.NORMAL)])
    assert statuses(trace) == [R.UNKNOWN, R.ACTIVE]


# ---- AC3 -------------------------------------------------------------------------------------


def test_transition_writes_log_entry() -> None:
    rest = RestTracker(CONFIG)
    drive([resting()], rest)
    exp = rest.reading.explanation
    assert exp is not None
    assert exp["rule_id"] == "rest.resting"
    assert exp["priority"] == "LOG"
    assert exp["to_status"] == R.RESTING.value
    assert exp["activity_level"] == A.LOW.value
    eyes = exp["eyes_closed_ms"]
    assert isinstance(eyes, int) and eyes >= REST.eyes_closed_s * MS
    low = exp["low_activity_ms"]
    assert isinstance(low, int) and low >= REST.low_activity_s * MS


def engine_frames() -> list[FrameObservation]:
    """Nằm yên mắt đóng (nghỉ) → cử động mạnh (hoạt động) → nằm yên mắt đóng (nghỉ)."""
    act = CONFIG.activity
    still_s = (
        REST_ENTRY_S + act.window_s + act.sample_interval_s + CONFIG.quality.restore_duration_s
    )
    move_s = act.window_s + REST.active_hold_s + 2
    seq = PoseSequence(fps=FPS).lying(seconds=still_s)
    seq.limb_motion(seconds=move_s, speed_torso_per_s=3 * act.high_threshold, whole_body=True)
    seq.lying(seconds=still_s)
    frames = seq.build()
    total_s = len(frames) / FPS + 1
    return with_face(frames, [face(signals={"eyes_closed": ON}, seconds=total_s)])


def run(frames: list[FrameObservation]) -> list[EngineOutput]:
    engine = Engine(CONFIG, context())
    return [engine.process(f) for f in frames]


def test_rest_transitions_emit_no_events() -> None:
    frames = engine_frames()
    outs = run(frames)
    seen = [o.state.rest_status for o in outs]
    # nghỉ → hoạt động → nghỉ
    compressed = [s for i, s in enumerate(seen) if i == 0 or s != seen[i - 1]]
    assert compressed[-3:] == [R.RESTING, R.ACTIVE, R.RESTING]
    for o in outs:
        for ev in o.events:
            assert "rest" not in str(ev.explanation.get("rule_id", ""))
    # Không có sự kiện nào trong chuỗi này (nằm yên, mặt chỉ có tín hiệu mắt).
    lying_only = with_face(
        PoseSequence(fps=FPS).lying(seconds=REST_ENTRY_S + 20).build(),
        [face(signals={"eyes_closed": ON}, seconds=REST_ENTRY_S + 21)],
    )
    lying_outs = run(lying_only)
    assert lying_outs[-1].state.rest_status == R.RESTING
    assert all(not o.events for o in lying_outs)
    # Mỗi lần đổi rest_status có entry LOG mới, state_changed bật
    for prev, cur in itertools.pairwise(outs):
        if cur.state.rest_status != prev.state.rest_status:
            assert cur.state_changed
            exp = cur.state.rest_explanation
            assert exp is not None and exp["to_status"] == cur.state.rest_status.value
            assert exp["from_status"] == prev.state.rest_status.value


def test_rest_does_not_change_body_explanation() -> None:
    """`explanation` vẫn là lần chuyển body_state gần nhất (F14 R10), rest có trường riêng."""
    outs = run(engine_frames())
    for prev, cur in itertools.pairwise(outs):
        if cur.state.body_state == prev.state.body_state:
            assert cur.state.explanation == prev.state.explanation


def test_rest_deterministic() -> None:
    frames = engine_frames()
    a = [o.state for o in run(frames)]
    b = [o.state for o in run(frames)]
    assert a == b
