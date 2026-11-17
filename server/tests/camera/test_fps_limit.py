"""F05 AC5: giới hạn FPS xử lý, không có hàng đợi khung cũ, đếm khung bỏ."""

import time
from itertools import pairwise
from pathlib import Path

from postcare.vision.camera import FileSource, Frame, LatestFrameBuffer, WebcamSource
from postcare.vision.fake import FakeCapture
from tests.camera.synthetic import FakeClock, write_video


def _read_all(source: FileSource) -> list[Frame]:
    return list(iter(source.read, None))


def test_default_max_fps_is_15(tmp_path: Path) -> None:
    assert FileSource(tmp_path / "x.avi").max_fps == 15
    assert WebcamSource(0).max_fps == 15


def test_fps_limit_file_source(tmp_path: Path) -> None:
    video = write_video(tmp_path / "a.avi", n_frames=60, fps=30)  # 2 giây video
    with FileSource(video, max_fps=15) as src:
        frames = _read_all(src)
    assert len(frames) == 30
    assert src.stats.dropped_frames == 30
    for second in (0, 1):
        in_second = [f for f in frames if second * 1000 <= f.ts_ms < (second + 1) * 1000]
        assert len(in_second) <= 15
    gaps = {b.ts_ms - a.ts_ms for a, b in pairwise(frames)}
    assert gaps <= {66, 67}
    assert abs(src.stats.fps - 15) < 0.5


def test_slow_file_source_drops_nothing(tmp_path: Path) -> None:
    video = write_video(tmp_path / "a.avi", n_frames=10, fps=10)
    with FileSource(video, max_fps=15) as src:
        frames = _read_all(src)
    assert len(frames) == 10
    assert src.stats.dropped_frames == 0


def test_latest_frame_buffer_keeps_newest() -> None:
    buf = LatestFrameBuffer()
    for i in range(5):
        buf.put(FakeCapture.make_image(i), ts_ms=i * 10)
    item = buf.take(timeout_s=0)
    assert item is not None
    image, ts = item
    assert FakeCapture.frame_number(image) == 4
    assert ts == 40
    assert buf.dropped == 4
    assert buf.take(timeout_s=0) is None
    buf.put(FakeCapture.make_image(9), ts_ms=90)
    assert buf.take(timeout_s=0) is not None
    assert buf.dropped == 4


def test_live_source_returns_latest_frame() -> None:
    cap = FakeCapture(delay_s=0.001)
    src = WebcamSource(0, capture_factory=lambda: cap, max_fps=20)
    with src:
        frames = [src.read(timeout_s=2.0) for _ in range(5)]
        time.sleep(0.2)  # người dùng chậm: khung cũ không được xếp hàng
        reads_before_late = cap.reads
        late = src.read(timeout_s=2.0)
    got = [f for f in frames if f is not None]
    assert len(got) == 5
    assert [f.frame_index for f in got] == [0, 1, 2, 3, 4]
    numbers = [FakeCapture.frame_number(f.image) for f in got]
    assert all(b > a for a, b in pairwise(numbers))
    assert any(b - a > 1 for a, b in pairwise(numbers))
    assert late is not None
    assert FakeCapture.frame_number(late.image) >= reads_before_late - 2
    assert src.stats.dropped_frames > 0
    ts = [f.ts_ms for f in [*got, late]]
    assert all(b > a for a, b in pairwise(ts))


def test_slow_live_source_drops_nothing() -> None:
    cap = FakeCapture(delay_s=0.05)
    src = WebcamSource(0, capture_factory=lambda: cap, max_fps=1000)
    with src:
        frames = [src.read(timeout_s=2.0) for _ in range(5)]
    assert all(f is not None for f in frames)
    assert src.stats.dropped_frames == 0


def test_live_fps_limit_uses_injected_clock() -> None:
    clock = FakeClock()
    src = WebcamSource(
        0,
        capture_factory=FakeCapture,
        max_fps=10,
        clock_ns=clock,
        sleep=clock.sleep,
        threaded=False,
    )
    with src:
        frames = [src.read() for _ in range(4)]
    ts = [f.ts_ms for f in frames if f is not None]
    assert len(ts) == 4
    assert all(b - a >= 100 for a, b in pairwise(ts))
