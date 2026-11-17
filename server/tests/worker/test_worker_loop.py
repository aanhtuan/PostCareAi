"""F06: vòng lặp worker với API giả (httpx.MockTransport), nguồn/adapter/engine giả, đồng hồ giả.

Phần kéo trước từ F17 R3–R7 (sự kiện, state) và F36 R18 (tạm dừng) ghi ở spec F06 §9.
"""

import itertools
from pathlib import Path

import pytest

from postcare.schemas.enums import BodyState, CameraStatus
from postcare.worker.loop import WorkerStopError
from tests.worker.helpers import T0_UTC, frames_script, make_harness


def test_worker_fetches_config_on_start() -> None:
    h = make_harness()
    h.worker.step()
    first = h.api.calls[0]
    assert first[1:3] == ("GET", "/internal/v1/cameras/1/config")
    assert h.worker.config is not None
    assert h.worker.config.active_session_id == 7


def test_heartbeat_every_2s_with_stats() -> None:
    h = make_harness()
    h.run_until(10.0)
    beats = h.api.paths("/heartbeat")
    times = [round(c[0] - 100.0, 1) for c in beats]
    assert 5 <= len(beats) <= 6, times
    gaps = [b - a for a, b in itertools.pairwise(times)]
    assert all(1.9 <= g <= 2.2 for g in gaps), gaps
    body = beats[-1][3]
    assert set(body) == {"fps", "brightness", "dropped_frames", "source_status"}
    assert body["source_status"] == "ONLINE"
    assert 0 <= body["brightness"] <= 255


def test_worker_reloads_config_within_5s() -> None:
    h = make_harness()
    h.run_until(3.0)
    assert h.worker.config is not None and h.worker.config.config_version == 1
    changed_at = h.time.t
    h.api.config["config_version"] = 2
    h.api.config["roi_polygon"] = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]
    for _ in range(100_000):
        if h.worker.config.config_version == 2:
            break
        h.worker.step()
    assert h.time.t - changed_at <= 5.0
    assert h.worker.config.roi_polygon == [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]
    # Cấu hình mới → Engine mới với ROI mới.
    assert len(h.engines) == 2
    assert h.engines[-1].context.roi_polygon.points[0] == (0.1, 0.1)


def test_unchanged_config_fetched_only_on_poll_schedule() -> None:
    h = make_harness()
    h.run_until(12.0)
    fetches = [round(c[0] - 100.0, 1) for c in h.api.paths("/config")]
    # Lần đầu + poll mỗi 5 s; không tải thêm khi heartbeat trả cùng config_version.
    assert len(fetches) == 3, fetches
    assert len(h.engines) == 1


def test_worker_frame_rate_about_5fps() -> None:
    h = make_harness()
    h.run_until(10.0)
    frames = h.api.paths("/frame")
    assert 45 <= len(frames) <= 55, len(frames)
    assert frames[0][3][:2] == b"\xff\xd8"  # JPEG


def test_state_posted_only_on_change_and_refresh() -> None:
    h = make_harness(engine_kwargs={"states": {30: BodyState.SITTING}})
    h.run_until(4.0)
    states = h.api.paths("/state")
    # Khung 0 (trạng thái đầu) và khung 30 (đổi sang SITTING); không gửi mỗi khung.
    assert [c[3]["body_state"] for c in states] == ["LYING", "SITTING"]
    assert states[0][3]["ts"].startswith(T0_UTC.strftime("%Y-%m-%dT%H:%M:%S"))
    assert states[1][3]["ts"].startswith("2026-11-18T03:00:02")  # khung 30 ở 2 s


def test_event_posted_with_utc_times_and_config_hash() -> None:
    h = make_harness(engine_kwargs={"events_at": [15]})
    h.run_until(3.0)
    events = h.api.paths("/internal/v1/events")
    assert len(events) == 1
    body = events[0][3]
    assert body["camera_id"] == 1
    assert body["code"] == "BED_EXIT"
    assert body["config_hash"] == "hash-test"
    assert body["explanation"]["rule_id"] == "test.rule"
    # Khung 15 có ts 1000 ms; khung đầu (ts 0) ứng với giờ UTC lúc nhận khung đầu.
    assert body["detected_at"].startswith("2026-11-18T03:00:01")
    assert body["occurred_at"].startswith("2026-11-18T03:00:00.5")


def test_event_retried_with_same_uid_on_5xx_and_network_error() -> None:
    h = make_harness(engine_kwargs={"events_at": [15]})
    h.api.event_statuses = [503, 500]
    h.run_until(1.2)
    h.api.down = True
    h.run_until(3.0)
    h.api.down = False
    h.run_until(30.0)
    events = h.api.paths("/internal/v1/events")
    assert len(events) == 3  # 503, 500, 201 (lần gửi lúc API sập không tới được API)
    uids = {c[3]["event_uid"] for c in events}
    assert len(uids) == 1
    assert h.worker.pending_events == 0


def test_event_409_dropped_not_retried() -> None:
    h = make_harness(engine_kwargs={"events_at": [15]})
    h.api.event_statuses = [409]
    h.run_until(20.0)
    assert len(h.api.paths("/internal/v1/events")) == 1
    assert h.worker.pending_events == 0


def test_no_active_session_sends_state_but_no_events() -> None:
    from tests.worker.helpers import default_config

    h = make_harness(
        engine_kwargs={"events_at": [15]}, config=default_config(active_session_id=None)
    )
    h.run_until(3.0)
    assert h.api.paths("/state")
    assert h.api.paths("/internal/v1/events") == []


def test_session_change_creates_new_engine() -> None:
    h = make_harness()
    h.run_until(3.0)
    h.api.config["active_session_id"] = 8
    h.run_until(9.0)
    assert len(h.engines) == 2


def test_api_down_worker_keeps_running_and_recovers() -> None:
    h = make_harness()
    h.api.down = True
    h.run_until(20.0)  # không ném lỗi, không thoát
    assert h.api.calls == []
    h.api.down = False
    h.run_until(40.0)
    assert h.worker.config is not None
    assert h.api.paths("/heartbeat")


def test_api_down_midway_then_recovers() -> None:
    h = make_harness()
    h.run_until(3.0)
    h.api.down = True
    h.run_until(15.0)
    n = len(h.api.calls)
    h.api.down = False
    h.run_until(20.0)
    assert len(h.api.calls) > n
    assert h.api.paths("/heartbeat")[-1][0] > 115.0


def test_source_offline_reported_in_heartbeat() -> None:
    h = make_harness(script=lambda: [*frames_script(2), CameraStatus.OFFLINE])
    h.run_until(8.0)
    statuses = [c[3]["source_status"] for c in h.api.paths("/heartbeat")]
    assert statuses[0] == "ONLINE"
    assert statuses[-1] == "OFFLINE"


def test_source_reopened_when_source_changes() -> None:
    h = make_harness()
    h.run_until(3.0)
    h.api.config.update(config_version=2, source="other.mp4")
    h.run_until(9.0)
    assert len(h.sources) == 2
    assert h.sources[0].status is CameraStatus.OFFLINE  # nguồn cũ đã đóng
    assert len(h.adapters) == 2  # adapter mới: ts_ms nguồn mới bắt đầu lại


def test_capture_paused_stops_reading_and_engine() -> None:
    h = make_harness()
    h.run_until(3.0)
    h.api.config["capture_paused"] = True
    h.run_until(9.0)
    processed = len(h.engines[0].processed)
    frames = len(h.api.paths("/frame"))
    h.run_until(20.0)
    assert len(h.engines[0].processed) == processed
    assert len(h.api.paths("/frame")) == frames
    assert h.sources[0].status is CameraStatus.OFFLINE  # nguồn đã đóng
    beats = [c for c in h.api.paths("/heartbeat") if c[0] > 110.0]
    assert beats and all(c[3]["source_status"] == "PAUSED" for c in beats)


def test_config_404_stops_worker() -> None:
    h = make_harness()
    h.api.config_status = 404
    with pytest.raises(WorkerStopError):
        h.run_until(5.0)


def test_config_401_stops_worker() -> None:
    h = make_harness()
    h.api.config_status = 401
    with pytest.raises(WorkerStopError):
        h.run_until(5.0)


def test_no_roi_sends_frames_but_no_engine() -> None:
    from tests.worker.helpers import default_config

    h = make_harness(config=default_config(roi_polygon=None))
    h.run_until(4.0)
    assert h.engines == []
    assert h.api.paths("/frame")
    assert h.api.paths("/state") == []


def test_close_releases_source_and_adapter() -> None:
    h = make_harness()
    h.run_until(2.0)
    h.worker.close()
    assert h.sources[0].status is CameraStatus.OFFLINE
    assert h.adapters[0].closed


# ---- Sửa sau review (2026-11-18) -------------------------------------------------------------


def test_mask_source_hides_url_credentials() -> None:
    from postcare.worker.config import mask_source

    assert mask_source("rtsp://user:pass@10.0.0.5:554/s") == "rtsp://***@10.0.0.5:554/s"
    assert mask_source("http://admin@cam.local/video") == "http://***@cam.local/video"
    assert mask_source("http://192.168.1.5:4747/video") == "http://192.168.1.5:4747/video"
    assert mask_source("0") == "0"
    assert mask_source("D:/clip.mp4") == "D:/clip.mp4"


def test_worker_logs_do_not_contain_url_password(caplog: pytest.LogCaptureFixture) -> None:
    from tests.worker.helpers import default_config

    caplog.set_level("INFO", logger="postcare.worker")
    h = make_harness(config=default_config(source_type="URL", source="rtsp://u:secret@cam/s"))
    h.run_until(2.0)
    h.api.config.update(config_version=2, source="rtsp://u:secret2@cam/s2")
    h.run_until(6.0)
    assert "rtsp://***@cam/s" in caplog.text
    assert "secret" not in caplog.text


def test_event_flush_skipped_while_api_circuit_open() -> None:
    h = make_harness(engine_kwargs={"events_at": [15]})
    attempts: list[float] = []
    post_event = h.worker.api.post_event

    def spy(body: dict) -> object:
        attempts.append(h.time.t)
        return post_event(body)

    h.worker.api.post_event = spy  # type: ignore[method-assign]
    h.run_until(0.5)
    h.api.down = True
    h.run_until(0.9)  # heartbeat/khung lỗi → circuit mở trước khi có sự kiện (khung 15, 1 s)
    h.run_until(10.0)
    # Lúc circuit mở, sự kiện nằm trong hàng đợi, không thử gửi mỗi khung.
    assert h.worker.pending_events == 1
    assert len(attempts) <= 3, attempts
    h.api.down = False
    h.run_until(30.0)
    assert len(h.api.paths("/internal/v1/events")) == 1
    assert h.worker.pending_events == 0


def test_hung_api_does_not_block_a_step_long() -> None:
    h = make_harness(hang=True, engine_kwargs={"events_at": [15, 60]})
    h.run_until(0.5)
    h.api.down = True
    longest = 0.0
    while h.time.t < 140.0:
        before = h.time.t
        h.worker.step()
        longest = max(longest, h.time.t - before)
    hb = [c for c in h.api.calls if c[2].endswith("/heartbeat#timeout")]
    assert hb, "heartbeat phải được thử khi API treo"
    # Heartbeat dùng timeout ngắn; khi circuit mở, các request khác bị bỏ qua.
    assert longest <= 4.0, longest


def test_file_source_played_at_real_speed(tmp_path: Path) -> None:
    from postcare.vision.camera import FileSource
    from tests.camera.synthetic import write_video

    video = write_video(tmp_path / "clip.avi", n_frames=60, fps=15.0)  # 4 s
    h = make_harness(
        source=lambda: FileSource(video, max_fps=15),
        pace=lambda src: isinstance(src, FileSource),  # như mặc định của Worker
    )
    for _ in range(100_000):
        h.worker.step()
        if h.worker.source is not None and h.worker.source.ended:
            break
    # Khung cuối ở 59/15 = 3,93 s: tổng thời gian chờ giả lập ≈ thời lượng video.
    assert 3.7 <= h.time.slept <= 4.3, h.time.slept
