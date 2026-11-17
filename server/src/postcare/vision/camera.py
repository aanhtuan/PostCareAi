"""Camera Service (F05): nhận khung hình từ webcam, URL HTTP/RTSP hoặc file video.

Nguồn: PDF §10 (Camera Service "nhận stream, lấy frame và theo dõi trạng thái kết nối"),
PDF bảng §8 (OpenCV/RTSP), HS §4.2, QA#24, ADR-0003 (timestamp đơn điệu cho MediaPipe VIDEO).

- File video: `ts_ms` lấy từ thời gian của chính video → replay lặp lại được.
- Webcam/URL: một luồng nền đọc liên tục và chỉ giữ khung mới nhất (không hàng đợi);
  `ts_ms` lấy từ đồng hồ đơn điệu tính từ lúc mở nguồn; mất nguồn thì tự kết nối lại có backoff.
- Không ghi khung hình ra đĩa (QA#29).
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, Self

import cv2
import numpy as np

from postcare.schemas.enums import CameraSourceType, CameraStatus

logger = logging.getLogger(__name__)

DEFAULT_MAX_FPS = 15.0  # A03
BACKOFF_INITIAL_S = 1.0  # (giả định) 1 s, 2 s, 4 s… tối đa 10 s
BACKOFF_MAX_S = 10.0
DEFAULT_MAX_READ_FAILURES = 5  # (giả định) số lần đọc lỗi liên tiếp coi là mất nguồn
URL_TIMEOUT_MS = 5000  # (giả định) timeout mở/đọc của backend FFMPEG
_FPS_WINDOW = 30  # số khung cho FPS trung bình trượt
_URL_PREFIXES = ("http://", "https://", "rtsp://")

Image = np.ndarray[Any, Any]
StatusCallback = Callable[[CameraStatus], None]


class SourceOpenError(RuntimeError):
    """Không mở được nguồn video."""


@dataclass(frozen=True)
class Frame:
    """Một khung hình BGR kèm timestamp đơn điệu (ms) và số thứ tự."""

    image: Image
    ts_ms: int
    frame_index: int

    @property
    def width(self) -> int:
        return int(self.image.shape[1])

    @property
    def height(self) -> int:
        return int(self.image.shape[0])


@dataclass(frozen=True)
class SourceStats:
    """Thống kê đọc nguồn (HS §8.2: FPS, khung bỏ)."""

    fps: float
    width: int
    height: int
    frames: int
    dropped_frames: int
    disconnects: int


class Capture(Protocol):
    """Phần tối thiểu của `cv2.VideoCapture` mà Camera Service dùng (cho phép inject bản giả)."""

    def isOpened(self) -> bool: ...  # noqa: N802 (tên theo OpenCV)

    def read(self) -> tuple[bool, Any]: ...

    def get(self, prop_id: int) -> float: ...

    def release(self) -> None: ...


CaptureFactory = Callable[[], Capture]


class FrameSource(Protocol):
    """Nguồn khung hình chung cho worker (F06, F17) và replay (F12)."""

    @property
    def status(self) -> CameraStatus: ...

    @property
    def ended(self) -> bool: ...

    @property
    def stats(self) -> SourceStats: ...

    def open(self) -> None: ...

    def read(self, timeout_s: float = 1.0) -> Frame | None: ...

    def close(self) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


class BaseSource:
    """Phần chung: trạng thái + callback, `ts_ms` tăng ngặt, `frame_index`, thống kê."""

    def __init__(self, *, max_fps: float | None, on_status_change: StatusCallback | None) -> None:
        self.max_fps = max_fps
        self._on_status_change = on_status_change
        self._status = CameraStatus.UNKNOWN
        self._ended = False
        self._next_index = 0
        self._last_ts: int | None = None
        self._ts_window: deque[int] = deque(maxlen=_FPS_WINDOW)
        self._size = (0, 0)
        self._dropped = 0
        self._disconnects = 0

    @property
    def status(self) -> CameraStatus:
        return self._status

    @property
    def ended(self) -> bool:
        """True khi nguồn đã hết khung (chỉ file / nguồn giả); không phải mất kết nối."""
        return self._ended

    @property
    def stats(self) -> SourceStats:
        window = self._ts_window
        span = window[-1] - window[0] if len(window) >= 2 else 0
        fps = (len(window) - 1) * 1000 / span if span > 0 else 0.0
        return SourceStats(
            fps=fps,
            width=self._size[0],
            height=self._size[1],
            frames=self._next_index,
            dropped_frames=self._dropped_count(),
            disconnects=self._disconnects,
        )

    def _dropped_count(self) -> int:
        return self._dropped

    def _set_status(self, status: CameraStatus, *, lost: bool = True) -> None:
        """Đổi trạng thái và gọi callback; `lost=False` khi đóng chủ động (không đếm mất nguồn)."""
        if status is self._status:
            return
        if lost and self._status is CameraStatus.ONLINE and status is CameraStatus.OFFLINE:
            self._disconnects += 1
        self._status = status
        if self._on_status_change is not None:
            self._on_status_change(status)

    def _emit(self, image: Image, ts_ms: int) -> Frame:
        # R3: ts_ms tăng ngặt; trùng hoặc lùi thì lấy ts trước + 1 ms (giả định).
        if self._last_ts is not None and ts_ms <= self._last_ts:
            ts_ms = self._last_ts + 1
        self._last_ts = ts_ms
        frame = Frame(image=image, ts_ms=ts_ms, frame_index=self._next_index)
        self._next_index += 1
        self._ts_window.append(ts_ms)
        self._size = (frame.width, frame.height)
        return frame

    def __enter__(self) -> Self:
        self.open()  # type: ignore[attr-defined]
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()  # type: ignore[attr-defined]


class FileSource(BaseSource):
    """File video. `ts_ms` = thời gian của khung trong video (không dùng đồng hồ máy).

    Giới hạn FPS chọn khung theo ô thời gian video `floor(t · max_fps)` nên kết quả xác định.
    Hết file → `read()` trả `None`, `ended = True`, trạng thái vẫn `ONLINE` (R5).
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_fps: float | None = DEFAULT_MAX_FPS,
        on_status_change: StatusCallback | None = None,
        capture_factory: CaptureFactory | None = None,
    ) -> None:
        super().__init__(max_fps=max_fps, on_status_change=on_status_change)
        self.path = Path(path)
        self._factory = capture_factory or (lambda: cv2.VideoCapture(str(self.path)))
        self._cap: Capture | None = None
        self._video_fps = 0.0
        self._raw_index = 0
        self._last_slot: int | None = None

    def open(self) -> None:
        if not self.path.is_file():
            self._set_status(CameraStatus.OFFLINE)
            raise SourceOpenError(f"Không tìm thấy file video: {self.path}")
        cap = self._factory()
        if not cap.isOpened():
            cap.release()
            self._set_status(CameraStatus.OFFLINE)
            raise SourceOpenError(f"OpenCV không mở được file video: {self.path}")
        self._cap = cap
        self._video_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        self._set_status(CameraStatus.ONLINE)

    def read(self, timeout_s: float = 1.0) -> Frame | None:
        """Trả khung kế tiếp đã qua giới hạn FPS; `None` khi hết file. Bỏ qua `timeout_s`."""
        cap = self._cap
        while cap is not None and not self._ended:
            ok, image = cap.read()
            if not ok or image is None:
                self._ended = True
                return None
            t_ms = self._video_time_ms(cap)
            self._raw_index += 1
            if not self._take_slot(t_ms):
                self._dropped += 1
                continue
            return self._emit(image, round(t_ms))
        return None

    def _video_time_ms(self, cap: Capture) -> float:
        if self._video_fps > 0:
            return self._raw_index * 1000.0 / self._video_fps
        # File không báo FPS: dùng vị trí thời gian OpenCV đọc được (giả định).
        return float(cap.get(cv2.CAP_PROP_POS_MSEC))

    def _take_slot(self, t_ms: float) -> bool:
        if not self.max_fps:
            return True
        slot = math.floor(t_ms * self.max_fps / 1000.0 + 1e-6)
        if self._last_slot is not None and slot <= self._last_slot:
            return False
        self._last_slot = slot
        return True

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._set_status(CameraStatus.OFFLINE, lost=False)


class LatestFrameBuffer:
    """Ô chứa một khung mới nhất (thread-safe). Ghi đè khung chưa lấy → đếm là khung bỏ."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._item: tuple[Image, int] | None = None
        self._dropped = 0

    @property
    def dropped(self) -> int:
        return self._dropped

    def put(self, image: Image, ts_ms: int) -> None:
        with self._cond:
            if self._item is not None:
                self._dropped += 1
            self._item = (image, ts_ms)
            self._cond.notify_all()

    def take(self, timeout_s: float | None = 0) -> tuple[Image, int] | None:
        """Lấy và xóa khung mới nhất; chờ tối đa `timeout_s` giây nếu đang trống."""
        with self._cond:
            if self._item is None and timeout_s:
                self._cond.wait_for(lambda: self._item is not None, timeout=timeout_s)
            item, self._item = self._item, None
            return item


class LiveSource(BaseSource):
    """Nguồn trực tiếp (webcam/URL): luồng đọc nền, khung mới nhất, tự kết nối lại.

    `threaded=False` dùng cho test: không chạy luồng nền, mỗi `read()` / `step()` đọc đồng bộ.
    `on_status_change` được gọi từ luồng đọc nền khi trạng thái đổi.
    """

    def __init__(
        self,
        capture_factory: CaptureFactory,
        *,
        max_fps: float | None = DEFAULT_MAX_FPS,
        on_status_change: StatusCallback | None = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
        sleep: Callable[[float], Any] | None = None,
        threaded: bool = True,
        fail_fast: bool = True,
        max_read_failures: int = DEFAULT_MAX_READ_FAILURES,
    ) -> None:
        super().__init__(max_fps=max_fps, on_status_change=on_status_change)
        self._factory = capture_factory
        self._clock_ns = clock_ns
        self._stop = threading.Event()
        self._sleep = sleep or self._stop.wait
        self._threaded = threaded
        self._fail_fast = fail_fast
        self._max_read_failures = max(1, max_read_failures)
        self._buffer = LatestFrameBuffer()
        self._cap: Capture | None = None
        self._failures = 0
        self._backoff = BACKOFF_INITIAL_S
        self._opened_ns = 0
        self._last_return_ns: int | None = None
        self._thread: threading.Thread | None = None

    def _dropped_count(self) -> int:
        return self._buffer.dropped

    def open(self) -> None:
        self._stop.clear()
        self._opened_ns = self._clock_ns()
        if not self._connect():
            self._set_status(CameraStatus.OFFLINE)
            if self._fail_fast:
                raise SourceOpenError(f"Không mở được nguồn: {self.describe()}")
        if self._threaded:
            self._thread = threading.Thread(target=self._run, name="frame-reader", daemon=True)
            self._thread.start()

    def describe(self) -> str:
        return type(self).__name__

    def read(self, timeout_s: float = 1.0) -> Frame | None:
        """Trả khung mới nhất (giãn cách ≥ 1/max_fps); `None` nếu chưa có khung trong timeout."""
        self._wait_for_fps_slot()
        if self._threaded:
            item = self._buffer.take(timeout_s)
        else:
            self.step()
            item = self._buffer.take(0)
        if item is None:
            return None
        self._last_return_ns = self._clock_ns()
        return self._emit(*item)

    def _wait_for_fps_slot(self) -> None:
        if not self.max_fps or self._last_return_ns is None:
            return
        due_ns = self._last_return_ns + int(1e9 / self.max_fps)
        remaining_ns = due_ns - self._clock_ns()
        if remaining_ns > 0:
            self._sleep(remaining_ns / 1e9)

    def step(self) -> None:
        """Một bước của luồng đọc: kết nối lại (có backoff) hoặc đọc một khung vào buffer."""
        if self._cap is None:
            if self._connect():
                return
            self._set_status(CameraStatus.OFFLINE)
            self._sleep(self._backoff)
            self._backoff = min(self._backoff * 2, BACKOFF_MAX_S)
            return
        try:
            ok, image = self._cap.read()
        except cv2.error:
            logger.warning("Lỗi OpenCV khi đọc %s", self.describe(), exc_info=True)
            ok, image = False, None
        if ok and image is not None:
            self._failures = 0
            self._buffer.put(image, (self._clock_ns() - self._opened_ns) // 1_000_000)
            return
        self._failures += 1
        if self._failures >= self._max_read_failures:
            logger.warning("Mất nguồn %s, sẽ kết nối lại", self.describe())
            self._release()
            self._set_status(CameraStatus.OFFLINE)

    def _connect(self) -> bool:
        try:
            cap = self._factory()
        except cv2.error:
            logger.warning("Lỗi OpenCV khi mở %s", self.describe(), exc_info=True)
            return False
        if not cap.isOpened():
            cap.release()
            return False
        self._cap = cap
        self._failures = 0
        self._backoff = BACKOFF_INITIAL_S
        self._set_status(CameraStatus.ONLINE)
        return True

    def _release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _run(self) -> None:
        while not self._stop.is_set():
            self.step()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._release()
        self._set_status(CameraStatus.OFFLINE, lost=False)


class WebcamSource(LiveSource):
    """Webcam theo index (kể cả webcam ảo của DroidCam client)."""

    def __init__(
        self, index: int, *, capture_factory: CaptureFactory | None = None, **kwargs: Any
    ) -> None:
        self.index = index
        super().__init__(capture_factory or (lambda: cv2.VideoCapture(index)), **kwargs)

    def describe(self) -> str:
        return f"webcam {self.index}"


def _open_url(url: str) -> Capture:
    params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, URL_TIMEOUT_MS]
    params += [cv2.CAP_PROP_READ_TIMEOUT_MSEC, URL_TIMEOUT_MS]
    return cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)


class UrlSource(LiveSource):
    """URL HTTP MJPEG (DroidCam `:4747/video`, IP Webcam `:8080/video`, A14) hoặc RTSP."""

    def __init__(
        self, url: str, *, capture_factory: CaptureFactory | None = None, **kwargs: Any
    ) -> None:
        self.url = url
        super().__init__(capture_factory or (lambda: _open_url(url)), **kwargs)

    def describe(self) -> str:
        return f"URL {self.url}"


def guess_source_type(text: str) -> tuple[CameraSourceType, int | str]:
    """Đoán loại nguồn cho `probe` (R8): số nguyên → webcam; http(s)/rtsp → URL; còn lại → file."""
    value = text.strip()
    if value.isdigit():
        return CameraSourceType.WEBCAM, int(value)
    if value.lower().startswith(_URL_PREFIXES):
        return CameraSourceType.URL, value
    return CameraSourceType.FILE, value


def open_source(
    source_type: CameraSourceType | str,
    source: int | str | Path,
    *,
    max_fps: float | None = DEFAULT_MAX_FPS,
    on_status_change: StatusCallback | None = None,
    **kwargs: Any,
) -> FileSource | WebcamSource | UrlSource:
    """Tạo nguồn đúng loại theo `CameraSourceType` (chưa mở; gọi `open()` hoặc dùng `with`)."""
    try:
        kind = CameraSourceType(source_type)
    except ValueError as exc:
        raise ValueError(f"source_type không hợp lệ: {source_type!r}") from exc
    common: dict[str, Any] = {"max_fps": max_fps, "on_status_change": on_status_change}
    if kind is CameraSourceType.WEBCAM:
        try:
            index = int(source)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Webcam cần index số nguyên, nhận {source!r}") from exc
        return WebcamSource(index, **common, **kwargs)
    if kind is CameraSourceType.URL:
        return UrlSource(str(source), **common, **kwargs)
    return FileSource(source, **common, **kwargs)
