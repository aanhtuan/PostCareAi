"""Nguồn giả cho test (F05 R11; testing.md §1): không cần camera, mạng hay file video.

- `FakeCapture`: thay `cv2.VideoCapture` trong `WebcamSource` / `UrlSource` (mở lỗi, đọc lỗi).
- `FakeFrameSource`: một `FrameSource` hoàn chỉnh với dãy `ts_ms` cho trước và mất nguồn giả lập,
  dùng cho test worker (F06) và test tích hợp.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

import numpy as np

from postcare.schemas.enums import CameraStatus
from postcare.vision.camera import BaseSource, Frame, Image, StatusCallback

_FAKE_FPS = 30.0


class FakeCapture:
    """Giống `cv2.VideoCapture`: khung tổng hợp đánh số; kịch bản mở/đọc lỗi.

    - `opened=False`: không mở được.
    - `n_frames`: sau số khung này mọi `read()` đều lỗi (`None` = không giới hạn).
    - `fail_reads`: chỉ số các lần `read()` (đếm từ 0) trả lỗi.
    - `delay_s`: thời gian chờ mỗi lần đọc (giả lập camera chậm).
    """

    def __init__(
        self,
        *,
        opened: bool = True,
        n_frames: int | None = None,
        fail_reads: Iterable[int] = (),
        delay_s: float = 0.0,
        size: tuple[int, int] = (64, 48),
    ) -> None:
        self._opened = opened
        self._n_frames = n_frames
        self._fail_reads = set(fail_reads)
        self._delay_s = delay_s
        self._size = size
        self.reads = 0
        self._frames = 0

    @staticmethod
    def make_image(number: int, size: tuple[int, int] = (64, 48)) -> Image:
        """Khung xám, số thứ tự mã hóa ở pixel (0, 0) kênh B (thấp) và G (cao)."""
        width, height = size
        image = np.full((height, width, 3), 80, dtype=np.uint8)
        image[0, 0, 0] = number % 256
        image[0, 0, 1] = (number // 256) % 256
        return image

    @staticmethod
    def frame_number(image: Image) -> int:
        return int(image[0, 0, 0]) + 256 * int(image[0, 0, 1])

    def isOpened(self) -> bool:  # noqa: N802 (tên theo OpenCV)
        return self._opened

    def read(self) -> tuple[bool, Any]:
        if self._delay_s:
            time.sleep(self._delay_s)
        attempt = self.reads
        self.reads += 1
        if not self._opened or attempt in self._fail_reads:
            return False, None
        if self._n_frames is not None and self._frames >= self._n_frames:
            return False, None
        image = self.make_image(attempt, self._size)
        self._frames += 1
        return True, image

    def get(self, prop_id: int) -> float:
        return _FAKE_FPS

    def release(self) -> None:
        self._opened = False


class FakeFrameSource(BaseSource):
    """`FrameSource` theo kịch bản: số nguyên = khung có `ts_ms` đó; `CameraStatus` = đổi trạng thái

    `CameraStatus.OFFLINE` trong kịch bản làm `read()` trả `None` (mất nguồn, chưa kết thúc).
    Hết kịch bản → `read()` trả `None` và `ended = True`.
    """

    def __init__(
        self,
        script: Iterable[int | CameraStatus],
        *,
        size: tuple[int, int] = (64, 48),
        max_fps: float | None = None,
        on_status_change: StatusCallback | None = None,
    ) -> None:
        super().__init__(max_fps=max_fps, on_status_change=on_status_change)
        self._script = list(script)
        self._pos = 0
        self._image_size = size

    def open(self) -> None:
        self._set_status(CameraStatus.ONLINE)

    def read(self, timeout_s: float = 1.0) -> Frame | None:
        while self._pos < len(self._script):
            item = self._script[self._pos]
            self._pos += 1
            if isinstance(item, CameraStatus):
                self._set_status(item)
                if item is CameraStatus.OFFLINE:
                    return None
                continue
            return self._emit(FakeCapture.make_image(self._next_index, self._image_size), item)
        self._ended = True
        return None

    def close(self) -> None:
        self._set_status(CameraStatus.OFFLINE, lost=False)
