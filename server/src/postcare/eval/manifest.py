"""Đọc và kiểm tra `data/eval/manifest.csv`, `data/eval/truth.csv` (F16 R1, R2; HS §8.1).

Định dạng: evaluation.md mục 4 và mục 8 (cột bổ sung của dữ liệu ngoài). `notes` của manifest có
thể chứa `scenario=<mã>` và `eval_codes=<mã,…>` ngăn bằng `;` (datasets.md §3.5).
"""

from __future__ import annotations

import csv
import math
import os
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from postcare.schemas.events import EventCode

MANIFEST_COLUMNS = (
    "video_id",
    "path",
    "split",
    "participant_id",
    "session_id",
    "camera_condition",
    "duration_s",
    "notes",
)
TRUTH_COLUMNS = ("video_id", "event_code", "start_s", "end_s", "notes")
SPLITS = ("dev", "test")
_SCENARIO_PREFIX = re.compile(r"^(S\d{2})(?:_|$)")


@dataclass(frozen=True)
class ManifestRow:
    video_id: str
    path: str
    split: str
    participant_id: str
    session_id: str
    camera_condition: str
    duration_s: float
    notes: str = ""
    source: str = ""
    """Nguồn dữ liệu ngoài (URFD, GMDCSA24…); trống hoặc `team` với tập quay của nhóm."""
    license: str = ""
    display: str = ""
    camera_config: str = ""
    """Tuỳ chọn *(giả định F16)*: đường dẫn `config/cameras/*.yaml` dùng khi replay video này."""

    @property
    def note_fields(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for part in self.notes.split(";"):
            key, sep, value = part.partition("=")
            if sep and key.strip():
                out.setdefault(key.strip(), value.strip())
        return out

    @property
    def scenario(self) -> str:
        """`scenario=` trong `notes` (bỏ phần chú thích trong ngoặc), không có thì tiền tố `Sxx`."""
        raw = self.note_fields.get("scenario", "")
        raw = raw.split("(", 1)[0].strip()
        if raw:
            return raw
        m = _SCENARIO_PREFIX.match(self.video_id)
        return m.group(1) if m else "—"

    @property
    def eval_codes_raw(self) -> list[str] | None:
        raw = self.note_fields.get("eval_codes")
        if raw is None:
            return None
        return [c.strip() for c in raw.split(",") if c.strip()]

    @property
    def eval_codes(self) -> frozenset[EventCode] | None:
        """Mã được chấm trên video này; `None` = mọi mã (giả định F16, evaluation.md §8)."""
        raw = self.eval_codes_raw
        if raw is None:
            return None
        return frozenset(EventCode(c) for c in raw if c in EventCode.__members__)


@dataclass(frozen=True)
class TruthRow:
    video_id: str
    event_code: EventCode
    start_s: float
    end_s: float
    notes: str = ""
    label_source: str = ""
    """`dataset` hoặc `manual` (evaluation.md §8)."""


@dataclass
class ValidationResult:
    manifest: list[ManifestRow] = field(default_factory=list)
    truth: list[TruthRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def rows(self, split: str) -> list[ManifestRow]:
        return [r for r in self.manifest if r.split == split]

    def truth_by_video(self) -> dict[str, list[TruthRow]]:
        out: dict[str, list[TruthRow]] = defaultdict(list)
        for t in self.truth:
            out[t.video_id].append(t)
        return out


def _read_csv(
    path: Path, required: Iterable[str], errors: list[str]
) -> list[tuple[int, dict[str, str]]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            header = [h.strip() for h in reader.fieldnames or []]
            missing = [c for c in required if c not in header]
            if missing:
                errors.append(f"{path.name}: thiếu cột bắt buộc {', '.join(missing)}")
                return []
            rows = []
            for line, raw in enumerate(reader, start=2):
                rows.append(
                    (line, {(k or "").strip(): (v or "").strip() for k, v in raw.items() if k})
                )
            return rows
    except OSError as exc:
        errors.append(f"Không đọc được {path}: {exc}")
        return []


def _float(value: str, where: str, column: str, errors: list[str]) -> float | None:
    try:
        x = float(value)
    except ValueError:
        errors.append(f"{where}: {column} '{value}' không phải số")
        return None
    if not math.isfinite(x) or x < 0:
        errors.append(f"{where}: {column} '{value}' phải là số ≥ 0")
        return None
    return x


def _norm_path(p: str) -> str:
    return os.path.normpath(p.replace("\\", "/")).replace("\\", "/").lower()


def _parse_manifest(path: Path, errors: list[str]) -> list[ManifestRow]:
    out: list[ManifestRow] = []
    for line, r in _read_csv(path, MANIFEST_COLUMNS, errors):
        where = f"manifest.csv dòng {line}"
        video_id = r.get("video_id", "")
        if not video_id or not r.get("path"):
            errors.append(f"{where}: video_id và path không được trống")
            continue
        if r["split"] not in SPLITS:
            errors.append(f"{where} ({video_id}): split '{r['split']}' phải là dev hoặc test")
        duration = _float(r["duration_s"], where, "duration_s", errors)
        row = ManifestRow(
            video_id=video_id,
            path=r["path"],
            split=r["split"],
            participant_id=r["participant_id"],
            session_id=r["session_id"],
            camera_condition=r["camera_condition"],
            duration_s=duration if duration is not None else 0.0,
            notes=r.get("notes", ""),
            source=r.get("source", ""),
            license=r.get("license", ""),
            display=r.get("display", ""),
            camera_config=r.get("camera_config", ""),
        )
        unknown = [c for c in row.eval_codes_raw or [] if c not in EventCode.__members__]
        if row.eval_codes_raw == []:
            errors.append(f"{where} ({video_id}): eval_codes rỗng; bỏ khóa hoặc ghi ít nhất một mã")
        if unknown:
            errors.append(f"{where} ({video_id}): eval_codes có mã lạ {', '.join(unknown)}")
        out.append(row)
    return out


def _parse_truth(path: Path, errors: list[str]) -> list[TruthRow]:
    out: list[TruthRow] = []
    for line, r in _read_csv(path, TRUTH_COLUMNS, errors):
        where = f"truth.csv dòng {line}"
        code = r["event_code"]
        if code not in EventCode.__members__:
            errors.append(f"{where} ({r['video_id']}): event_code '{code}' không thuộc EventCode")
            continue
        start = _float(r["start_s"], where, "start_s", errors)
        end = _float(r["end_s"], where, "end_s", errors)
        if start is None or end is None:
            continue
        if start > end:
            errors.append(f"{where} ({r['video_id']}): start_s {start:g} > end_s {end:g}")
            continue
        out.append(
            TruthRow(
                video_id=r["video_id"],
                event_code=EventCode(code),
                start_s=start,
                end_s=end,
                notes=r.get("notes", ""),
                label_source=r.get("label_source", ""),
            )
        )
    return out


def _check_duplicates(rows: list[ManifestRow], errors: list[str]) -> None:
    by_id: dict[str, list[ManifestRow]] = defaultdict(list)
    by_path: dict[str, list[ManifestRow]] = defaultdict(list)
    for r in rows:
        by_id[r.video_id].append(r)
        by_path[_norm_path(r.path)].append(r)
    for video_id, group in by_id.items():
        if len(group) > 1:
            splits = ", ".join(sorted({g.split for g in group}))
            errors.append(
                f"video_id {video_id} xuất hiện {len(group)} lần (split: {splits}); "
                "mỗi video chỉ thuộc một split"
            )
    for group in by_path.values():
        if len(group) > 1:
            ids = ", ".join(g.video_id for g in group)
            errors.append(f"path {group[0].path} khai báo ở nhiều dòng ({ids})")


def _check_split_overlap(rows: list[ManifestRow], warnings: list[str]) -> None:
    for column in ("participant_id", "session_id"):
        dev = {getattr(r, column) for r in rows if r.split == "dev"} - {""}
        test = {getattr(r, column) for r in rows if r.split == "test"} - {""}
        shared = sorted(dev & test)
        if shared:
            warnings.append(
                f"{column} có ở cả dev và test: {', '.join(shared)} "
                "(HS §8.1: tập test nên dùng người/phiên khác)"
            )


def validate(
    manifest: list[ManifestRow], truth: list[TruthRow], errors: list[str], warnings: list[str]
) -> None:
    """Quy tắc chéo giữa hai file (R2)."""
    _check_duplicates(manifest, errors)
    _check_split_overlap(manifest, warnings)
    videos = {r.video_id: r for r in manifest}
    for t in truth:
        row = videos.get(t.video_id)
        if row is None:
            errors.append(f"truth.csv: video_id {t.video_id} không có trong manifest")
            continue
        codes = row.eval_codes
        if codes is not None and t.event_code not in codes:
            errors.append(
                f"truth.csv ({t.video_id}): {t.event_code.value} không thuộc eval_codes của video "
                f"({', '.join(sorted(c.value for c in codes))})"
            )
        if t.end_s > row.duration_s:
            errors.append(
                f"truth.csv ({t.video_id}, {t.event_code.value}): end_s {t.end_s:g} vượt "
                f"duration_s {row.duration_s:g}"
            )


def validate_files(manifest_path: Path, truth_path: Path) -> ValidationResult:
    """Đọc hai file và kiểm tra theo R2. Lỗi → `ok` False; trùng người/phiên → chỉ cảnh báo."""
    result = ValidationResult()
    result.manifest = _parse_manifest(manifest_path, result.errors)
    result.truth = _parse_truth(truth_path, result.errors)
    validate(result.manifest, result.truth, result.errors, result.warnings)
    return result
