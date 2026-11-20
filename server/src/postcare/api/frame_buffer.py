"""Khung JPEG mới nhất của mỗi camera, chỉ trong RAM (F06 R8; QA#29; ADR-0002).

Không bao giờ ghi đĩa: mỗi camera giữ đúng một khung, khung mới ghi đè khung cũ.
F07 đọc từ đây để phát MJPEG.
"""

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from postcare.db.types import utcnow


@dataclass(frozen=True)
class LatestFrame:
    data: bytes
    received_at: datetime
    config_version: int | None = None

    def is_fresh(self, now: datetime, stale_after_s: float) -> bool:
        return (now - self.received_at).total_seconds() <= stale_after_s


class LatestFrameStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frames: dict[tuple[int, str], LatestFrame] = {}

    def put(
        self,
        camera_id: int,
        data: bytes,
        received_at: datetime | None = None,
        *,
        view: Literal["display", "skeleton"] = "display",
        config_version: int | None = None,
    ) -> None:
        frame = LatestFrame(data, received_at or utcnow(), config_version)
        key = (camera_id, view)
        with self._lock:
            # POST cũ có thể hoàn tất sau POST đã qua kiểm tra với cấu hình mới.
            previous = self._frames.get(key)
            if (
                previous is not None
                and previous.config_version is not None
                and config_version is not None
                and config_version < previous.config_version
            ):
                return
            self._frames[key] = frame

    def get(
        self, camera_id: int, *, view: Literal["display", "skeleton"] = "display"
    ) -> LatestFrame | None:
        with self._lock:
            return self._frames.get((camera_id, view))

    def count(self) -> int:
        with self._lock:
            return len({camera_id for camera_id, _ in self._frames})

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()
