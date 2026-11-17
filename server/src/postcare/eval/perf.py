"""Gộp số liệu hiệu năng (FPS xử lý, khung bỏ, CPU %, RAM MB) từ `run.json` của replay F12.

psutil đo trong lúc replay (`postcare.replay.runner._Meter`); module này chỉ gộp (F16 R5).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PerfSummary:
    fps_processing: float | None
    """Tổng khung / tổng thời gian xử lý."""
    dropped_frames: int
    cpu_percent: float | None
    """Trung bình CPU % của tiến trình, trọng số theo thời gian chạy từng video."""
    ram_peak_mb: float | None
    elapsed_s: float


def _num(run: Mapping[str, Any], key: str) -> float | None:
    v = run.get(key)
    return float(v) if isinstance(v, int | float) else None


def aggregate_perf(runs: Iterable[Mapping[str, Any]]) -> PerfSummary:
    frames = 0.0
    elapsed = 0.0
    dropped = 0
    cpu_weighted = 0.0
    cpu_time = 0.0
    ram: float | None = None
    for run in runs:
        f, e = _num(run, "frames"), _num(run, "elapsed_s")
        if f is not None and e is not None:
            frames += f
            elapsed += e
        dropped += int(_num(run, "dropped_frames") or 0)
        cpu = _num(run, "cpu_percent")
        if cpu is not None and e:
            cpu_weighted += cpu * e
            cpu_time += e
        r = _num(run, "ram_peak_mb")
        if r is not None:
            ram = r if ram is None else max(ram, r)
    return PerfSummary(
        fps_processing=frames / elapsed if elapsed > 0 else None,
        dropped_frames=dropped,
        cpu_percent=cpu_weighted / cpu_time if cpu_time > 0 else None,
        ram_peak_mb=ram,
        elapsed_s=elapsed,
    )
