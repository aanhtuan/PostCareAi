"""Kho trong RAM của API: trạng thái giường hiện tại và số liệu camera (không lưu DB)."""

import threading
from dataclasses import dataclass

from postcare.domain.dto import BedStateOut


@dataclass
class CameraRuntime:
    fps: float | None = None
    brightness: float | None = None
    dropped_frames: int | None = None
    source_status: str | None = None


class RuntimeStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bed_states: dict[int, BedStateOut] = {}
        self._cameras: dict[int, CameraRuntime] = {}

    def set_bed_state(self, state: BedStateOut) -> None:
        with self._lock:
            self._bed_states[state.bed_id] = state

    def get_bed_state(self, bed_id: int) -> BedStateOut | None:
        with self._lock:
            return self._bed_states.get(bed_id)

    def set_camera(self, camera_id: int, runtime: CameraRuntime) -> None:
        with self._lock:
            self._cameras[camera_id] = runtime

    def get_camera(self, camera_id: int) -> CameraRuntime:
        with self._lock:
            return self._cameras.get(camera_id, CameraRuntime())

    def clear(self) -> None:
        with self._lock:
            self._bed_states.clear()
            self._cameras.clear()
