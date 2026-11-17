"""F05 R11: FakeFrameSource (dùng lại cho test F06 và tích hợp)."""

from postcare.schemas.enums import CameraStatus
from postcare.vision.fake import FakeFrameSource


def test_fake_source_frames_and_outage() -> None:
    changes: list[CameraStatus] = []
    src = FakeFrameSource(
        [0, 66, CameraStatus.OFFLINE, CameraStatus.ONLINE, 200],
        size=(32, 24),
        on_status_change=changes.append,
    )
    src.open()
    a, b = src.read(), src.read()
    assert a is not None and b is not None
    assert (a.ts_ms, b.ts_ms) == (0, 66)
    assert a.image.shape == (24, 32, 3)
    assert src.read() is None  # mất nguồn
    assert src.status is CameraStatus.OFFLINE
    assert not src.ended
    c = src.read()
    assert c is not None and c.ts_ms == 200 and c.frame_index == 2
    assert src.read() is None
    assert src.ended
    assert src.stats.disconnects == 1
    src.close()
    assert changes == [
        CameraStatus.ONLINE,
        CameraStatus.OFFLINE,
        CameraStatus.ONLINE,
        CameraStatus.OFFLINE,
    ]
