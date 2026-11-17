"""F05 AC3: mất nguồn → OFFLINE, kết nối lại theo backoff, callback trạng thái đúng thứ tự.

Không `sleep` thật: đồng hồ và hàm chờ được inject (FakeClock); chạy từng bước bằng `step()`.
"""

from collections.abc import Callable, Iterator

import pytest

from postcare.schemas.enums import CameraStatus
from postcare.vision.camera import SourceOpenError, UrlSource, WebcamSource
from postcare.vision.fake import FakeCapture
from tests.camera.synthetic import FakeClock


def _factory(captures: list[FakeCapture]) -> Callable[[], FakeCapture]:
    it: Iterator[FakeCapture] = iter(captures)
    return lambda: next(it)


def _dead(n: int) -> list[FakeCapture]:
    return [FakeCapture(opened=False) for _ in range(n)]


def _source(
    captures: list[FakeCapture], changes: list[CameraStatus], clock: FakeClock, **kw: object
) -> WebcamSource:
    return WebcamSource(
        0,
        capture_factory=_factory(captures),
        on_status_change=changes.append,
        clock_ns=clock,
        sleep=clock.sleep,
        threaded=False,
        max_read_failures=2,
        **kw,  # type: ignore[arg-type]
    )


def test_reconnect_with_backoff() -> None:
    clock, changes = FakeClock(), []
    src = _source([FakeCapture(n_frames=3), *_dead(6), FakeCapture()], changes, clock)
    src.open()
    assert src.status is CameraStatus.ONLINE
    for _ in range(3):
        src.step()
    assert src.status is CameraStatus.ONLINE
    src.step()  # đọc lỗi lần 1: chưa coi là mất nguồn
    assert src.status is CameraStatus.ONLINE
    src.step()  # đọc lỗi lần 2 liên tiếp → OFFLINE
    assert src.status is CameraStatus.OFFLINE
    assert src.stats.disconnects == 1
    for _ in range(6):  # 6 lần mở lại thất bại
        src.step()
        assert src.status is CameraStatus.OFFLINE
    assert clock.sleeps == [1, 2, 4, 8, 10, 10]
    src.step()  # mở lại được
    assert src.status is CameraStatus.ONLINE
    assert changes == [CameraStatus.ONLINE, CameraStatus.OFFLINE, CameraStatus.ONLINE]
    assert src.read() is not None
    src.close()


def test_status_callback_order() -> None:
    clock, changes = FakeClock(), []
    captures = [FakeCapture(n_frames=1), *_dead(2), FakeCapture(n_frames=1), *_dead(1)]
    src = _source([*captures, FakeCapture()], changes, clock)
    src.open()
    for _ in range(3):  # 1 khung + 2 lỗi đọc → OFFLINE
        src.step()
    for _ in range(3):  # 2 lần mở lỗi, lần 3 được
        src.step()
    for _ in range(3):  # 1 khung + 2 lỗi đọc → OFFLINE
        src.step()
    for _ in range(2):  # 1 lần mở lỗi, lần 2 được
        src.step()
    src.close()
    online, offline = CameraStatus.ONLINE, CameraStatus.OFFLINE
    assert changes == [online, offline, online, offline, online, offline]
    # Backoff bắt đầu lại từ 1 s sau mỗi lần kết nối lại thành công.
    assert clock.sleeps == [1, 2, 1]
    assert src.stats.disconnects == 2


def test_single_read_failure_keeps_online() -> None:
    clock, changes = FakeClock(), []
    cap = FakeCapture(fail_reads={2})
    src = _source([cap], changes, clock)
    src.open()
    for _ in range(5):
        src.step()
    assert src.status is CameraStatus.ONLINE
    assert changes == [CameraStatus.ONLINE]
    assert src.stats.disconnects == 0
    src.close()


def test_initial_open_failure_raises() -> None:
    clock, changes = FakeClock(), []
    src = _source(_dead(1), changes, clock)
    with pytest.raises(SourceOpenError):
        src.open()
    assert src.status is CameraStatus.OFFLINE


def test_initial_open_failure_retries_when_not_fail_fast() -> None:
    clock, changes = FakeClock(), []
    src = _source([*_dead(2), FakeCapture()], changes, clock, fail_fast=False)
    src.open()
    assert src.status is CameraStatus.OFFLINE
    src.step()  # mở lỗi lần 2
    src.step()  # mở được
    assert src.status is CameraStatus.ONLINE
    assert changes == [CameraStatus.OFFLINE, CameraStatus.ONLINE]
    src.close()


def test_url_source_uses_same_reconnect_logic() -> None:
    clock, changes = FakeClock(), []
    src = UrlSource(
        "http://192.168.1.5:4747/video",
        capture_factory=_factory([FakeCapture(n_frames=1), *_dead(1), FakeCapture()]),
        on_status_change=changes.append,
        clock_ns=clock,
        sleep=clock.sleep,
        threaded=False,
        max_read_failures=1,
    )
    src.open()
    src.step()
    src.step()  # lỗi đọc → OFFLINE
    src.step()  # mở lỗi → chờ 1 s
    src.step()  # mở được
    assert changes == [CameraStatus.ONLINE, CameraStatus.OFFLINE, CameraStatus.ONLINE]
    assert clock.sleeps == [1]
    src.close()
