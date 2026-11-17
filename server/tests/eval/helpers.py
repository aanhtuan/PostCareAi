"""Tiện ích test F16: manifest/truth CSV tổng hợp nhỏ, dự đoán giả. Không có video."""

import csv
from collections.abc import Sequence
from pathlib import Path

from postcare.eval.matching import Prediction

from postcare.schemas.enums import Priority
from postcare.schemas.events import EventCode, default_priority

MANIFEST_HEADER = (
    "video_id",
    "path",
    "split",
    "participant_id",
    "session_id",
    "camera_condition",
    "duration_s",
    "notes",
)
TRUTH_HEADER = ("video_id", "event_code", "start_s", "end_s", "notes")


def manifest_row(
    video_id: str = "S06_P01_r1",
    *,
    path: str | None = None,
    split: str = "dev",
    participant_id: str = "P01",
    session_id: str = "day1",
    camera_condition: str = "tripod-head-left;light-normal",
    duration_s: str = "42.0",
    notes: str = "",
) -> dict[str, str]:
    return {
        "video_id": video_id,
        "path": path if path is not None else f"data/videos/{video_id}.mp4",
        "split": split,
        "participant_id": participant_id,
        "session_id": session_id,
        "camera_condition": camera_condition,
        "duration_s": duration_s,
        "notes": notes,
    }


def truth_row(
    video_id: str = "S06_P01_r1",
    event_code: str = "BED_EXIT",
    start_s: str = "27.0",
    end_s: str = "27.0",
    notes: str = "",
) -> dict[str, str]:
    return {
        "video_id": video_id,
        "event_code": event_code,
        "start_s": start_s,
        "end_s": end_s,
        "notes": notes,
    }


def write_csv(
    path: Path, rows: Sequence[dict[str, str]], header: Sequence[str] | None = None
) -> Path:
    fields = list(header) if header is not None else list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def write_dataset(
    tmp_path: Path,
    manifest: Sequence[dict[str, str]],
    truth: Sequence[dict[str, str]],
) -> tuple[Path, Path]:
    m = write_csv(tmp_path / "manifest.csv", manifest, MANIFEST_HEADER)
    t = write_csv(tmp_path / "truth.csv", truth, TRUTH_HEADER)
    return m, t


def pred(
    code: EventCode,
    occurred_s: float,
    *,
    detected_s: float | None = None,
    priority: Priority | None = None,
    video_id: str = "v1",
) -> Prediction:
    return Prediction(
        video_id=video_id,
        code=code,
        priority=priority or default_priority(code),
        occurred_s=occurred_s,
        detected_s=detected_s if detected_s is not None else occurred_s,
    )
