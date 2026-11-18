"""Chốt `config_hash` trước khi chạy tập test (F29 R1, R2; HS §8.2; ADR-0008; evaluation.md §6).

- `reports/frozen-config.txt` (commit): dòng `config_hash: <hash>` cùng thông tin đối chiếu.
- `postcare eval --split test --frozen <hash>` từ chối khi cấu hình hợp nhất (mặc định + override
  camera) của bất kỳ video nào có hash khác, khi file chốt ghi hash khác, hoặc khi `runs/` còn sự
  kiện của cấu hình khác.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

HASH_KEY = "config_hash"


class FrozenConfigError(Exception):
    """Cấu hình lệch so với hash đã chốt: không được chạy tập test."""


def read_frozen_hash(path: Path) -> str | None:
    """Hash ghi trong file chốt; `None` nếu file chưa có hoặc không có dòng `config_hash:`."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == HASH_KEY and value.strip():
            return value.strip()
    return None


def render_frozen(config_hash: str, info: Mapping[str, str | None]) -> str:
    lines = [
        "# Cấu hình đã chốt cho tập test (F29 R1; evaluation.md §6). Không sửa tay.",
        "# Sinh bởi `postcare eval freeze`; commit file này trước khi chạy",
        "# `postcare eval --split test --frozen <config_hash>`.",
        f"{HASH_KEY}: {config_hash}",
    ]
    lines += [f"{k}: {v if v is not None else '—'}" for k, v in info.items()]
    return "\n".join(lines) + "\n"


def write_frozen(path: Path, config_hash: str, info: Mapping[str, str | None]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(render_frozen(config_hash, info))


def single_hash(hashes_by_video: Mapping[str, str]) -> str:
    """Hash chung của mọi video; nhiều hash (override ngưỡng khác nhau) → lỗi (spec §8)."""
    distinct = sorted(set(hashes_by_video.values()))
    if not distinct:
        raise FrozenConfigError("Không có video nào để tính config_hash.")
    if len(distinct) > 1:
        detail = "; ".join(
            f"{h[:12]}…: {', '.join(sorted(v for v, x in hashes_by_video.items() if x == h))}"
            for h in distinct
        )
        raise FrozenConfigError(
            f"Các video dùng {len(distinct)} config_hash khác nhau ({detail}). "
            "Tập test chỉ dùng một cấu hình đã chốt."
        )
    return distinct[0]


def check_config(frozen: str, hashes_by_video: Mapping[str, str]) -> None:
    bad = sorted(v for v, h in hashes_by_video.items() if h != frozen)
    if bad:
        current = sorted({hashes_by_video[v] for v in bad})
        raise FrozenConfigError(
            f"config_hash hiện tại ({', '.join(current)}) khác hash đã chốt {frozen} "
            f"ở {len(bad)} video (ví dụ {bad[0]}). Không sửa ngưỡng sau khi chốt; "
            "khôi phục cấu hình hoặc chốt lại trên tập dev."
        )


def check_frozen_file(frozen: str, path: Path) -> bool:
    """True nếu file chốt đã có và trùng; False nếu chưa có; lệch → lỗi."""
    recorded = read_frozen_hash(path)
    if recorded is None:
        return False
    if recorded != frozen:
        raise FrozenConfigError(f"{path} ghi config_hash {recorded}, khác --frozen {frozen}.")
    return True


def run_dir_hashes(out_dir: Path) -> set[str]:
    """Mọi `config_hash` trong `events.jsonl` và `run.json` của một thư mục kết quả replay."""
    found: set[str] = set()
    events = out_dir / "events.jsonl"
    if events.is_file():
        with events.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    h = json.loads(line).get(HASH_KEY)
                    if isinstance(h, str):
                        found.add(h)
    run = out_dir / "run.json"
    if run.is_file():
        data = json.loads(run.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get(HASH_KEY), str):
            found.add(data[HASH_KEY])
    return found


def check_runs(frozen: str, runs_dir: Path, video_ids: Iterable[str]) -> None:
    """`runs/<video>/` còn sự kiện mang hash khác → lỗi (không trộn kết quả hai cấu hình)."""
    stale: list[str] = []
    for vid in video_ids:
        other = run_dir_hashes(runs_dir / vid) - {frozen}
        stale += [f"{vid} ({h})" for h in sorted(other)]
    if stale:
        raise FrozenConfigError(
            f"{runs_dir} có kết quả mang config_hash khác {frozen}: {', '.join(stale[:5])}"
            + (f" và {len(stale) - 5} mục khác" if len(stale) > 5 else "")
            + ". Xóa thư mục kết quả cũ hoặc dùng --runs-dir khác."
        )
