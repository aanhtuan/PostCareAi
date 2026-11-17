"""Chạy replay F12 cho từng video của một split (F16 R3).

- Chế độ video: `replay_video` (pose + engine) với adapter do nơi gọi tạo (module này không import
  mediapipe).
- `from_observations`: đọc `<dir>/<video_id>/observations.jsonl` của lần chạy trước, chạy lại chỉ
  engine (không cần MediaPipe; dùng khi chỉ đổi ngưỡng).
- `reuse`: video đã có kết quả trong `runs_dir/<video_id>/` với cùng `config_hash` thì đọc lại.

Kết quả mỗi video ghi vào `runs_dir/<video_id>/` (gitignore).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from postcare.eval.manifest import ManifestRow, TruthRow
from postcare.eval.matching import Prediction, match_events
from postcare.eval.metrics import coverage_seconds
from postcare.eval.report import VideoResult
from postcare.replay.camera_config import CameraConfigError, load_camera_config
from postcare.replay.fixtures import ObservationFileError, read_observations
from postcare.replay.runner import (
    replay_observations,
    replay_video,
    source_run_info,
    video_duration_s,
)
from postcare.replay.writers import EventRecord, FrameRecord
from postcare.schemas.engine_config import EngineConfig
from postcare.settings import REPO_ROOT
from postcare.vision.camera import FileSource, FrameSource, SourceOpenError
from postcare.vision.inference.base import PoseAdapter

AdapterFactory = Callable[[EngineConfig], PoseAdapter]
SourceFactory = Callable[[Path, float | None], FrameSource]
ProgressCallback = Callable[[int, int, ManifestRow, str], None]

DEFAULT_MAX_FPS = 15.0
RESULT_FILES = ("events.jsonl", "frames.jsonl", "run.json")


@dataclass
class VideoRun:
    row: ManifestRow
    out_dir: Path
    events: list[EventRecord]
    frames: list[FrameRecord]
    run: dict[str, Any] = field(default_factory=dict)
    reused: bool = False

    def predictions(self) -> list[Prediction]:
        return [
            Prediction(
                video_id=self.row.video_id,
                code=e.code,
                priority=e.priority,
                occurred_s=e.occurred_at_ms / 1000,
                detected_s=e.detected_at_ms / 1000,
            )
            for e in self.events
        ]


@dataclass(frozen=True)
class VideoFailure:
    video_id: str
    error: str


def resolve_video_path(row: ManifestRow, data_dir: Path) -> Path:
    """Đường dẫn tuyệt đối giữ nguyên; `data/...` tính từ `data_dir`; còn lại tính từ gốc repo."""
    p = Path(row.path.replace("\\", "/"))
    if p.is_absolute():
        return p
    if p.parts and p.parts[0] == "data":
        return data_dir.joinpath(*p.parts[1:])
    return REPO_ROOT / p


def resolve_camera_config(row: ManifestRow, cameras_dir: Path, default: Path) -> Path:
    """Cột `camera_config` → `<cameras_dir>/<tên file video>.yaml` nếu có → `default`."""
    if row.camera_config:
        p = Path(row.camera_config)
        return p if p.is_absolute() else REPO_ROOT / p
    named = cameras_dir / f"{Path(row.path.replace(chr(92), '/')).stem}.yaml"
    if named.is_file():
        return named
    return default


def load_run(row: ManifestRow, out_dir: Path, *, reused: bool = False) -> VideoRun:
    run = json.loads((out_dir / "run.json").read_text(encoding="utf-8"))
    events = _read_jsonl(out_dir / "events.jsonl", EventRecord)
    frames = _read_jsonl(out_dir / "frames.jsonl", FrameRecord)
    return VideoRun(row, out_dir, events, frames, run, reused)


def _read_jsonl[T: (EventRecord, FrameRecord)](path: Path, model: type[T]) -> list[T]:
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f if line.strip()]


def _reusable(out_dir: Path, config_hash: str) -> bool:
    if not all((out_dir / n).is_file() for n in RESULT_FILES):
        return False
    try:
        run = json.loads((out_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(run, dict) and run.get("config_hash") == config_hash


def _default_source(path: Path, max_fps: float | None) -> FrameSource:
    return FileSource(path, max_fps=max_fps)


def _run_one(
    row: ManifestRow,
    *,
    runs_dir: Path,
    engine_config: Path,
    default_camera_config: Path,
    cameras_dir: Path,
    data_dir: Path,
    adapter_factory: AdapterFactory | None,
    source_factory: SourceFactory,
    from_observations: Path | None,
    reuse: bool,
    max_fps: float | None,
    model_info: dict[str, Any] | None,
) -> VideoRun:
    cam_path = resolve_camera_config(row, cameras_dir, default_camera_config)
    camera = load_camera_config(cam_path)
    config = camera.engine_config(engine_config)
    out_dir = runs_dir / row.video_id
    if reuse and _reusable(out_dir, config.config_hash()):
        return load_run(row, out_dir, reused=True)
    meta: dict[str, Any] = {
        "camera_config": str(cam_path),
        "engine_config": str(engine_config),
        "video_id": row.video_id,
    }
    if from_observations is not None:
        obs_path = from_observations / row.video_id / "observations.jsonl"
        if not obs_path.is_file():
            raise FileNotFoundError(f"Không có {obs_path}")
        observations = read_observations(obs_path)
        source_run = source_run_info(obs_path)
        meta.update(
            source_run,
            observations=str(obs_path),
            source_perf=_source_perf(obs_path.parent / "run.json"),
        )
        replay_observations(observations, camera, config, out_dir, overwrite=True, meta=meta)
        return load_run(row, out_dir)
    video = resolve_video_path(row, data_dir)
    if not video.is_file():
        raise FileNotFoundError(f"Không tìm thấy video {video}")
    if adapter_factory is None:
        raise RuntimeError("Cần adapter pose để chạy video (hoặc dùng --from-observations)")
    adapter = adapter_factory(config)
    try:
        meta.update(
            video=str(video),
            model=model_info,
            max_fps=max_fps,
            video_duration_s=video_duration_s(video),
        )
        replay_video(
            source_factory(video, max_fps), adapter, camera, config, out_dir,
            overwrite=True, meta=meta,
        )  # fmt: skip
    finally:
        adapter.close()
    return load_run(row, out_dir)


def _source_perf(run_path: Path) -> dict[str, Any] | None:
    """Số liệu hiệu năng của lần chạy pose gốc (khi `from_observations`)."""
    try:
        data = json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    keys = ("frames", "elapsed_s", "dropped_frames", "fps_processing", "cpu_percent", "ram_peak_mb")
    return {k: data.get(k) for k in keys}


def score_runs(
    results: Sequence[VideoRun | VideoFailure],
    truth_by_video: Mapping[str, Sequence[TruthRow]],
    *,
    tol_before_s: float,
    tol_after_s: float,
) -> tuple[list[VideoResult], list[tuple[str, str]]]:
    """Ghép sự kiện từng video với ground truth, tính coverage từ `frames.jsonl`."""
    videos: list[VideoResult] = []
    failures: list[tuple[str, str]] = []
    for res in results:
        if isinstance(res, VideoFailure):
            failures.append((res.video_id, res.error))
            continue
        truths = list(truth_by_video.get(res.row.video_id, []))
        match = match_events(
            res.predictions(),
            truths,
            tol_before_s=tol_before_s,
            tol_after_s=tol_after_s,
            eval_codes=res.row.eval_codes,
        )
        observed, total = coverage_seconds([(f.ts_ms, f.body_state) for f in res.frames])
        # Hiệu năng: khi chạy lại từ observations, lấy số liệu của lần chạy pose gốc.
        perf = res.run.get("source_perf") or {}
        run = {**res.run, **{k: v for k, v in perf.items() if v is not None}}
        videos.append(VideoResult(res.row, truths, match, observed, total, run))
    return videos, failures


def run_split(
    rows: Sequence[ManifestRow],
    *,
    runs_dir: Path,
    engine_config: Path,
    default_camera_config: Path,
    cameras_dir: Path,
    data_dir: Path,
    adapter_factory: AdapterFactory | None = None,
    source_factory: SourceFactory = _default_source,
    from_observations: Path | None = None,
    reuse: bool = False,
    max_fps: float | None = DEFAULT_MAX_FPS,
    model_info: dict[str, Any] | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[VideoRun | VideoFailure]:
    """Chạy từng video; lỗi của một video ghi thành `VideoFailure`, không dừng cả lượt."""
    out: list[VideoRun | VideoFailure] = []
    for i, row in enumerate(rows, start=1):
        try:
            res: VideoRun | VideoFailure = _run_one(
                row,
                runs_dir=runs_dir,
                engine_config=engine_config,
                default_camera_config=default_camera_config,
                cameras_dir=cameras_dir,
                data_dir=data_dir,
                adapter_factory=adapter_factory,
                source_factory=source_factory,
                from_observations=from_observations,
                reuse=reuse,
                max_fps=max_fps,
                model_info=model_info,
            )
            status = "dùng lại" if isinstance(res, VideoRun) and res.reused else "xong"
        except (
            OSError,
            ValueError,
            RuntimeError,
            CameraConfigError,
            ObservationFileError,
            SourceOpenError,
        ) as exc:
            res = VideoFailure(row.video_id, f"{row.video_id}: {exc}")
            status = f"lỗi: {exc}"
        out.append(res)
        if on_progress is not None:
            on_progress(i, len(rows), row, status)
    return out
