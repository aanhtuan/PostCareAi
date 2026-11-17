"""Khung JPEG mới nhất của mỗi camera, chỉ trong RAM (F06 R8; QA#29; ADR-0002).

Không bao giờ ghi đĩa: mỗi camera giữ đúng một khung, khung mới ghi đè khung cũ.
F07 đọc từ đây để phát MJPEG.
"""

import threading
from dataclasses import dataclass
from datetime import datetime

from postcare.db.types import utcnow


@dataclass(frozen=True)
class LatestFrame:
    data: bytes
    received_at: datetime


class LatestFrameStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frames: dict[int, LatestFrame] = {}

    def put(self, camera_id: int, data: bytes, received_at: datetime | None = None) -> None:
        frame = LatestFrame(data=data, received_at=received_at or utcnow())
        with self._lock:
            self._frames[camera_id] = frame

    def get(self, camera_id: int) -> LatestFrame | None:
        with self._lock:
            return self._frames.get(camera_id)

    def count(self) -> int:
        with self._lock:
            return len(self._frames)

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()
