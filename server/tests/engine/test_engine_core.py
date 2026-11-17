"""F10 AC3: khung Event Engine, Engine.process(obs). Dữ liệu tổng hợp, không đồng hồ thật."""

import datetime as dt
import time
from pathlib import Path

import pytest

from postcare.engine import Engine
from postcare.schemas.context import EngineContext
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.enums import ActivityLevel, BodyState, ObservationQuality, RestStatus
from postcare.schemas.events import EngineOutput
from postcare.schemas.observation import FrameObservation, Keypoint, KeypointName, PersonPose
from postcare.schemas.roi import RoiPolygon

ROOT = Path(__file__).resolve().parents[3]
CONFIG = EngineConfig.load(ROOT / "config" / "engine.default.yaml")
ROI = RoiPolygon(points=[(0.2, 0.25), (0.8, 0.25), (0.8, 0.85), (0.2, 0.85)])
CTX = EngineContext(camera_id=1, roi_polygon=ROI)
FPS_MS = 66


def _person() -> PersonPose:
    kp = Keypoint(x=0.5, y=0.5, visibility=0.9)
    return PersonPose(keypoints={name: kp for name in KeypointName})


def _obs(
    i: int, *, persons: int = 0, source_ok: bool = True, ts_ms: int | None = None
) -> FrameObservation:
    return FrameObservation(
        camera_id=1,
        frame_index=i,
        ts_ms=i * FPS_MS if ts_ms is None else ts_ms,
        image_size=(1280, 720),
        persons=[_person() for _ in range(persons)],
        source_ok=source_ok,
    )


def _engine() -> Engine:
    return Engine(CONFIG, CTX)


def _run(seq: list[FrameObservation]) -> list[EngineOutput]:
    engine = _engine()
    return [engine.process(o) for o in seq]


def test_initial_state_is_no_observation() -> None:
    assert _engine().state.body_state == BodyState.NO_OBSERVATION


def test_empty_observation_gives_no_observation() -> None:
    out = _engine().process(_obs(0))
    assert out.state.body_state == BodyState.NO_OBSERVATION
    assert out.state.observation_quality == ObservationQuality.NO_PERSON
    assert out.state.activity_level == ActivityLevel.UNKNOWN
    assert out.state.rest_status == RestStatus.UNKNOWN
    assert out.events == []


def test_source_not_ok_gives_camera_issue() -> None:
    # Kể cả khi adapter vẫn trả người, nguồn lỗi thì không tin khung hình
    out = _engine().process(_obs(0, persons=1, source_ok=False))
    assert out.state.body_state == BodyState.NO_OBSERVATION
    assert out.state.observation_quality == ObservationQuality.CAMERA_ISSUE
    assert out.events == []


def test_persons_without_f14_stay_no_observation() -> None:
    """Chưa có phân loại tư thế (F14) thì không kết luận tư thế, càng không rời giường."""
    outs = _run([_obs(i, persons=1) for i in range(60)])
    assert {o.state.body_state for o in outs} == {BodyState.NO_OBSERVATION}
    assert all(o.events == [] for o in outs)


def test_state_changed_only_when_snapshot_changes() -> None:
    outs = _run([_obs(0), _obs(1), _obs(2, source_ok=False), _obs(3, source_ok=False), _obs(4)])
    assert [o.state_changed for o in outs] == [True, False, True, False, True]


def test_engine_is_deterministic() -> None:
    seq = [_obs(i, persons=i % 3, source_ok=i % 7 != 0) for i in range(100)]
    first = _run(seq)
    second = _run(seq)
    assert first == second
    assert [o.model_dump_json() for o in first] == [o.model_dump_json() for o in second]


def test_non_increasing_ts_raises() -> None:
    engine = _engine()
    engine.process(_obs(0, ts_ms=1000))
    with pytest.raises(ValueError, match="ts_ms"):
        engine.process(_obs(1, ts_ms=1000))
    with pytest.raises(ValueError, match="ts_ms"):
        engine.process(_obs(2, ts_ms=900))
    # Lỗi không làm hỏng trạng thái: frame hợp lệ tiếp theo vẫn xử lý được
    assert engine.process(_obs(3, ts_ms=1066)).state.body_state == BodyState.NO_OBSERVATION


def test_camera_id_mismatch_raises() -> None:
    obs = _obs(0).model_copy(update={"camera_id": 2})
    with pytest.raises(ValueError, match="camera_id"):
        _engine().process(obs)


def test_engine_does_not_read_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> float:
        raise AssertionError("engine đọc đồng hồ hệ thống")

    engine = _engine()
    for name in ("time", "monotonic", "perf_counter", "time_ns", "monotonic_ns"):
        monkeypatch.setattr(time, name, boom)

    class _NoClock(dt.datetime):
        @classmethod
        def now(cls, tz: dt.tzinfo | None = None) -> "_NoClock":
            raise AssertionError("engine đọc đồng hồ hệ thống")

    monkeypatch.setattr(dt, "datetime", _NoClock)
    for i in range(10):
        engine.process(_obs(i, persons=i % 2))


def test_engine_exposes_config_hash() -> None:
    assert _engine().config_hash == CONFIG.config_hash()
