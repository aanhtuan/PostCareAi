"""F05 AC1, AC2, AC3 (ca âm tính): FileSource, open_source, timestamp theo thời gian video."""

from itertools import pairwise
from pathlib import Path

import pytest

from postcare.schemas.enums import CameraSourceType, CameraStatus
from postcare.vision.camera import (
    FileSource,
    Frame,
    SourceOpenError,
    UrlSource,
    WebcamSource,
    guess_source_type,
    open_source,
)
from postcare.vision.fake import FakeFrameSource
from tests.camera.synthetic import write_video


def _read_all(source: FileSource) -> list[Frame]:
    frames: list[Frame] = []
    while (frame := source.read()) is not None:
        frames.append(frame)
    return frames


# ---------------------------------------------------------------- AC1


def test_open_source_dispatch(tmp_path: Path) -> None:
    video = write_video(tmp_path / "a.avi")
    assert isinstance(open_source(CameraSourceType.WEBCAM, 0), WebcamSource)
    assert isinstance(open_source(CameraSourceType.WEBCAM, "1"), WebcamSource)
    for url in ("http://192.168.1.5:4747/video", "http://10.0.0.2:8080/video", "rtsp://h/s"):
        src = open_source(CameraSourceType.URL, url)
        assert isinstance(src, UrlSource)
        assert src.url == url
    assert isinstance(open_source(CameraSourceType.FILE, video), FileSource)
    assert isinstance(open_source("FILE", str(video)), FileSource)


def test_open_source_rejects_invalid_type() -> None:
    with pytest.raises(ValueError, match="source_type"):
        open_source("CAMERA_X", "0")


def test_open_source_rejects_non_integer_webcam() -> None:
    with pytest.raises(ValueError):
        open_source(CameraSourceType.WEBCAM, "abc")


def test_file_source_reads_all_frames(tmp_path: Path) -> None:
    video = write_video(tmp_path / "a.avi", n_frames=20, fps=10, size=(64, 48))
    with FileSource(video, max_fps=None) as src:
        frames = _read_all(src)
        assert src.status is CameraStatus.ONLINE
    assert len(frames) == 20
    assert [f.frame_index for f in frames] == list(range(20))
    assert (frames[0].width, frames[0].height) == (64, 48)
    assert frames[0].image.shape == (48, 64, 3)
    assert src.stats.width == 64 and src.stats.height == 48
    assert src.stats.dropped_frames == 0


def test_file_missing_cannot_open(tmp_path: Path) -> None:
    src = FileSource(tmp_path / "khong-co.mp4")
    with pytest.raises(SourceOpenError):
        src.open()


def test_guess_source_type() -> None:
    assert guess_source_type("0") == (CameraSourceType.WEBCAM, 0)
    assert guess_source_type(" 2 ") == (CameraSourceType.WEBCAM, 2)
    assert guess_source_type("http://1.2.3.4:4747/video") == (
        CameraSourceType.URL,
        "http://1.2.3.4:4747/video",
    )
    assert guess_source_type("HTTPS://x/y")[0] is CameraSourceType.URL
    assert guess_source_type("rtsp://cam/live")[0] is CameraSourceType.URL
    assert guess_source_type("data/clip.mp4") == (CameraSourceType.FILE, "data/clip.mp4")
    assert guess_source_type("-1")[0] is CameraSourceType.FILE


# ---------------------------------------------------------------- AC2


def test_timestamps_strictly_increasing(tmp_path: Path) -> None:
    video = write_video(tmp_path / "a.avi", n_frames=30, fps=30)
    with FileSource(video, max_fps=None) as src:
        ts = [f.ts_ms for f in _read_all(src)]
    assert all(b > a for a, b in pairwise(ts))


def test_file_source_uses_video_time(tmp_path: Path) -> None:
    video = write_video(tmp_path / "a.avi", n_frames=10, fps=10)
    with FileSource(video, max_fps=None) as src:
        ts = [f.ts_ms for f in _read_all(src)]
    # Thời gian của chính video (khung i ở i × 100 ms), không phải đồng hồ máy.
    assert ts == [i * 100 for i in range(10)]


def test_file_source_deterministic(tmp_path: Path) -> None:
    video = write_video(tmp_path / "a.avi", n_frames=25, fps=30)
    runs = []
    for _ in range(2):
        with FileSource(video, max_fps=15) as src:
            runs.append([(f.frame_index, f.ts_ms) for f in _read_all(src)])
    assert runs[0] == runs[1]
    assert runs[0]


def test_equal_timestamps_bumped_by_1ms() -> None:
    with FakeFrameSource([0, 10, 10, 10, 5, 20]) as src:
        ts = [f.ts_ms for f in iter(src.read, None)]
    assert ts == [0, 10, 11, 12, 13, 20]


# ---------------------------------------------------------------- AC3 (ca âm tính)


def test_file_eof_is_not_offline(tmp_path: Path) -> None:
    video = write_video(tmp_path / "a.avi", n_frames=5, fps=10)
    changes: list[CameraStatus] = []
    src = FileSource(video, on_status_change=changes.append)
    src.open()
    _read_all(src)
    assert src.ended
    assert src.read() is None
    assert src.status is CameraStatus.ONLINE
    assert src.stats.disconnects == 0
    assert changes == [CameraStatus.ONLINE]
    src.close()
