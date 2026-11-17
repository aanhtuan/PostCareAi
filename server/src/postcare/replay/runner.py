"""Chạy replay (F12 R1, R4, R5, R6): video → pipeline dùng chung, hoặc observations → engine.

Đầu ra trong `out_dir` (thường `runs/<id>/`, gitignore):
- `observations.jsonl`: mỗi dòng một `FrameObservation`;
- `events.jsonl`: mỗi dòng một `EventRecord` (`EngineEvent` + `config_hash`);
- `frames.jsonl`: mỗi khung một `FrameRecord`;
- `run.json`: thông tin lần chạy, gồm số liệu phụ thuộc máy (FPS xử lý, CPU %, RAM MB);
- `preview.mp4` khi `preview=True` (chỉ chế độ video).

Không gọi API, không cần DB (R9). Module này không import mediapipe: adapter do nơi gọi tạo.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import cv2
import psutil

from postcare.engine import Engine
from postcare.pipeline import process_frame
from postcare.replay.camera_config import CameraConfig
from postcare.replay.writers import EventRecord, FrameRecord, JsonlWriter, write_json
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.events import EngineEvent, EngineOutput
from postcare.schemas.observation import FrameObservation
from postcare.settings import REPO_ROOT
from postcare.vision.camera import Frame, FrameSource
from postcare.vision.inference.base import PoseAdapter
from postcare.vision.render import draw_debug_overlay

OUTPUT_FILES = ("observations.jsonl", "events.jsonl", "frames.jsonl", "run.json")
PREVIEW_FILE = "preview.mp4"
PREVIEW_EVENT_HOLD_MS = 2000
"""Nhãn sự kiện còn hiện trên preview bao lâu sau `detected_at_ms` (giả định; chỉ để xem)."""
PREVIEW_DEFAULT_FPS = 15.0


class OutputExistsError(FileExistsError):
    """Thư mục `--out` đã có dữ liệu và không có `--overwrite`."""


@dataclass(frozen=True)
class ReplaySummary:
    out_dir: Path
    frames: int
    events: int
    run: dict[str, Any]


def prepare_out_dir(out_dir: Path, *, overwrite: bool) -> None:
    """Tạo `out_dir`; đã có file → lỗi, trừ khi `overwrite` (chỉ xóa các file replay ghi ra)."""
    if out_dir.exists() and not out_dir.is_dir():
        raise OutputExistsError(f"{out_dir} không phải thư mục")
    if out_dir.is_dir() and any(out_dir.iterdir()):
        if not overwrite:
            raise OutputExistsError(
                f"Thư mục {out_dir} đã có dữ liệu. Dùng --overwrite để ghi đè hoặc chọn --out khác."
            )
        for name in (*OUTPUT_FILES, PREVIEW_FILE):
            (out_dir / name).unlink(missing_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)


class _Meter:
    """FPS xử lý, CPU %, RAM đỉnh của tiến trình (HS §8.2). Chỉ ghi vào run.json."""

    def __init__(self) -> None:
        self.proc = psutil.Process()
        self.proc.cpu_percent(None)
        self.t0 = time.perf_counter()
        self.started_at = datetime.now(UTC).isoformat(timespec="seconds")
        self.peak_rss = self.proc.memory_info().rss
        self._n = 0

    def sample(self) -> None:
        self._n += 1
        if self._n % 15 == 0:
            self.peak_rss = max(self.peak_rss, self.proc.memory_info().rss)

    def finish(self, frames: int) -> dict[str, Any]:
        elapsed = time.perf_counter() - self.t0
        self.peak_rss = max(self.peak_rss, self.proc.memory_info().rss)
        return {
            "fps_processing": round(frames / elapsed, 2) if elapsed > 0 else None,
            "cpu_percent": round(self.proc.cpu_percent(None), 1),
            "ram_peak_mb": round(self.peak_rss / 2**20, 1),
            "elapsed_s": round(elapsed, 3),
            "started_at": self.started_at,
        }


class _Outputs:
    """Ba file JSONL của một lần chạy."""

    def __init__(self, out_dir: Path, config_hash: str) -> None:
        self.config_hash = config_hash
        self.observations = JsonlWriter(out_dir / "observations.jsonl")
        self.events = JsonlWriter(out_dir / "events.jsonl")
        self.frames = JsonlWriter(out_dir / "frames.jsonl")
        self.first_ts: int | None = None
        self.last_ts: int | None = None

    def write(self, obs: FrameObservation, output: EngineOutput) -> None:
        if self.first_ts is None:
            self.first_ts = obs.ts_ms
        self.last_ts = obs.ts_ms
        self.observations.write(obs)
        self.frames.write(FrameRecord.from_output(obs, output))
        for event in output.events:
            self.events.write(EventRecord(**event.model_dump(), config_hash=self.config_hash))

    @property
    def span_s(self) -> float | None:
        if self.first_ts is None or self.last_ts is None:
            return None
        return round((self.last_ts - self.first_ts) / 1000, 3)

    def close(self) -> None:
        for w in (self.observations, self.events, self.frames):
            w.close()


class _Preview:
    """Ghi `preview.mp4` (mp4v). Mở khi có khung đầu tiên (biết kích thước)."""

    def __init__(self, path: Path, fps: float, camera: CameraConfig) -> None:
        self.path = path
        self.fps = fps
        self.roi = camera.roi_polygon
        self._writer: cv2.VideoWriter | None = None
        self._recent: list[EngineEvent] = []

    def write(self, frame: Frame, obs: FrameObservation, output: EngineOutput) -> None:
        if self._writer is None:
            fourcc = cv2.VideoWriter.fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(
                str(self.path), fourcc, self.fps, (frame.width, frame.height)
            )
            if not self._writer.isOpened():
                raise RuntimeError(f"OpenCV không mở được {self.path} để ghi (codec mp4v)")
        self._recent = [
            e
            for e in [*self._recent, *output.events]
            if obs.ts_ms - e.detected_at_ms <= PREVIEW_EVENT_HOLD_MS
        ]
        image = draw_debug_overlay(frame.image, obs, self.roi, output.state, self._recent)
        self._writer.write(image)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None


def code_version() -> dict[str, Any]:
    try:
        pkg: str | None = package_version("postcare")
    except PackageNotFoundError:
        pkg = None
    commit: str | None = None
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode == 0:
            commit = proc.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        commit = None
    return {"package": pkg, "commit": commit}


def _base_run(
    mode: str, camera: CameraConfig, config: EngineConfig, meta: dict[str, Any] | None
) -> dict[str, Any]:
    run: dict[str, Any] = {
        "mode": mode,
        "video": None,
        "observations": None,
        "camera_config": None,
        "engine_config": None,
        "model": None,
        "camera_id": camera.camera_id,
        "roi_polygon": [list(p) for p in camera.roi_polygon.points],
        "config_hash": config.config_hash(),
        "code_version": code_version(),
    }
    run.update(meta or {})
    return run


def replay_video(
    source: FrameSource,
    adapter: PoseAdapter,
    camera: CameraConfig,
    config: EngineConfig,
    out_dir: Path,
    *,
    overwrite: bool = False,
    preview: bool = False,
    preview_fps: float | None = None,
    meta: dict[str, Any] | None = None,
) -> ReplaySummary:
    """Đọc hết `source`, mỗi khung chạy `process_frame` (pipeline dùng chung với worker)."""
    prepare_out_dir(out_dir, overwrite=overwrite)
    run = _base_run("video", camera, config, meta)
    engine = Engine(config, camera.context())
    outputs = _Outputs(out_dir, run["config_hash"])
    fps = preview_fps or getattr(source, "max_fps", None) or PREVIEW_DEFAULT_FPS
    writer = _Preview(out_dir / PREVIEW_FILE, fps, camera) if preview else None
    meter = _Meter()
    try:
        with source:
            while True:
                frame = source.read()
                if frame is None:
                    if source.ended:
                        break
                    continue
                obs, output = process_frame(frame, adapter, engine)
                outputs.write(obs, output)
                if writer is not None:
                    writer.write(frame, obs, output)
                meter.sample()
            stats = source.stats
    finally:
        outputs.close()
        if writer is not None:
            writer.close()
    frames = outputs.frames.count
    run.setdefault("video_duration_s", outputs.span_s)
    run.update(
        frames=frames,
        dropped_frames=stats.dropped_frames,
        events=outputs.events.count,
        image_size=[stats.width, stats.height],
        preview=PREVIEW_FILE if preview else None,
        **meter.finish(frames),
    )
    write_json(out_dir / "run.json", run)
    return ReplaySummary(out_dir, frames, outputs.events.count, run)


def replay_observations(
    observations: Iterable[FrameObservation],
    camera: CameraConfig,
    config: EngineConfig,
    out_dir: Path,
    *,
    overwrite: bool = False,
    meta: dict[str, Any] | None = None,
) -> ReplaySummary:
    """Chạy lại chỉ engine trên observation đã có (không cần MediaPipe; R4, R5).

    `camera_id` của engine lấy từ observation đầu tiên (observation ghi từ lần chạy trước).
    """
    observations = list(observations)
    prepare_out_dir(out_dir, overwrite=overwrite)
    run = _base_run("observations", camera, config, meta)
    context = camera.context()
    if observations:
        context = context.model_copy(update={"camera_id": observations[0].camera_id})
    engine = Engine(config, context)
    outputs = _Outputs(out_dir, run["config_hash"])
    meter = _Meter()
    try:
        for obs in observations:
            outputs.write(obs, engine.process(obs))
            meter.sample()
    finally:
        outputs.close()
    frames = outputs.frames.count
    run.setdefault("video_duration_s", outputs.span_s)
    run.update(
        camera_id=context.camera_id,
        frames=frames,
        dropped_frames=0,
        events=outputs.events.count,
        image_size=list(observations[0].image_size) if observations else None,
        preview=None,
        **meter.finish(frames),
    )
    write_json(out_dir / "run.json", run)
    return ReplaySummary(out_dir, frames, outputs.events.count, run)


def video_duration_s(path: Path) -> float | None:
    """Thời lượng video theo metadata (số khung / FPS); không đọc được → `None`."""
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return None
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        return round(count / fps, 3) if fps > 0 and count > 0 else None
    finally:
        cap.release()


def summarize(observations: Sequence[FrameObservation]) -> str:
    """Một dòng mô tả khoảng thời gian (cho thông báo CLI)."""
    if not observations:
        return "0 khung"
    a, b = observations[0].ts_ms / 1000, observations[-1].ts_ms / 1000
    return f"{len(observations)} khung, {a:.2f}–{b:.2f} s"
