"""Đọc observation JSONL, cắt đoạn làm fixture test, chạy regression (F12 R7, R8; testing.md §2).

Fixture `server/tests/fixtures/<scenario>.jsonl`: mỗi dòng một `FrameObservation` (chỉ toạ độ,
không ảnh, không đường dẫn video; QA#29). File kỳ vọng `<scenario>.expected.json`:

```json
{
  "camera": {"version": 1, "camera_id": 1, "roi_polygon": [[0.2, 0.3], …], "thresholds": {}},
  "range_s": [2.0, 5.5],
  "config_hash": "…",
  "events": [{"code": "SIT_UP", "occurred_at_ms": 3133}]
}
```

`config_hash` chỉ để tham khảo; regression so `events` (mã + `occurred_at_ms`) với kết quả chạy
engine trên ngưỡng mặc định hiện tại hợp nhất với `camera.thresholds`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from postcare.engine import Engine
from postcare.replay.camera_config import CameraConfig
from postcare.replay.writers import JsonlWriter, write_json
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.observation import FrameObservation

EXPECTED_SUFFIX = ".expected.json"


class ObservationFileError(ValueError):
    """File observation JSONL hỏng; thông báo nêu số dòng."""


def read_observations(path: Path | str) -> list[FrameObservation]:
    path = Path(path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ObservationFileError(f"Không đọc được {path}: {exc}") from exc
    observations: list[FrameObservation] = []
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            observations.append(FrameObservation.model_validate_json(line))
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first["loc"]) or "<dòng>"
            raise ObservationFileError(
                f"{path}: dòng {lineno} không phải FrameObservation hợp lệ ({loc}: {first['msg']})"
            ) from exc
    return observations


def cut_range(
    observations: Iterable[FrameObservation], start_s: float | None, end_s: float | None
) -> list[FrameObservation]:
    """Giữ các observation có `start_s ≤ ts_ms / 1000 ≤ end_s` (biên nào `None` thì bỏ)."""
    if start_s is not None and end_s is not None and start_s > end_s:
        raise ValueError(f"--start-s ({start_s}) phải ≤ --end-s ({end_s})")
    lo = None if start_s is None else round(start_s * 1000)
    hi = None if end_s is None else round(end_s * 1000)
    return [
        o for o in observations if (lo is None or o.ts_ms >= lo) and (hi is None or o.ts_ms <= hi)
    ]


def run_events(
    observations: Sequence[FrameObservation], camera: CameraConfig, config: EngineConfig
) -> list[dict[str, Any]]:
    """Danh sách `(code, occurred_at_ms)` engine phát ra trên chuỗi observation."""
    if not observations:
        return []
    context = camera.context().model_copy(update={"camera_id": observations[0].camera_id})
    engine = Engine(config, context)
    events: list[dict[str, Any]] = []
    for obs in observations:
        for event in engine.process(obs).events:
            events.append({"code": event.code.value, "occurred_at_ms": event.occurred_at_ms})
    return events


def write_fixture(
    path: Path,
    observations: Sequence[FrameObservation],
    camera: CameraConfig,
    config: EngineConfig,
    *,
    range_s: tuple[float | None, float | None] = (None, None),
    save_expected: bool = False,
) -> Path | None:
    """Ghi fixture JSONL (chỉ trường `FrameObservation`) và, nếu cần, `.expected.json`."""
    with JsonlWriter(path) as writer:
        for obs in observations:
            writer.write(obs)
    if not save_expected:
        return None
    expected_path = expected_path_for(path)
    start, end = range_s
    write_json(
        expected_path,
        {
            "camera": camera.to_dict(),
            "range_s": None if start is None and end is None else [start, end],
            "config_hash": config.config_hash(),
            "events": run_events(observations, camera, config),
        },
    )
    return expected_path


def expected_path_for(fixture: Path) -> Path:
    return fixture.with_name(fixture.stem + EXPECTED_SUFFIX)


@dataclass(frozen=True)
class FixtureCase:
    name: str
    observations: Path
    expected: Path | None

    @property
    def skip_reason(self) -> str:
        return f"{self.observations.name}: thiếu {self.name}{EXPECTED_SUFFIX}, bỏ qua"


def discover_fixtures(directory: Path) -> list[FixtureCase]:
    """Mọi `*.jsonl` trong thư mục, kèm file expected nếu có (sắp xếp theo tên)."""
    if not directory.is_dir():
        return []
    cases = []
    for path in sorted(directory.glob("*.jsonl")):
        expected = expected_path_for(path)
        cases.append(FixtureCase(path.stem, path, expected if expected.is_file() else None))
    return cases


def run_fixture(
    case: FixtureCase, default_engine_config: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Chạy engine trên fixture; trả (sự kiện thực tế, sự kiện kỳ vọng)."""
    if case.expected is None:
        raise ValueError(case.skip_reason)
    data = json.loads(case.expected.read_text(encoding="utf-8"))
    camera = CameraConfig.from_mapping(data["camera"], source=str(case.expected))
    config = camera.engine_config(default_engine_config)
    actual = run_events(read_observations(case.observations), camera, config)
    expected = [{"code": e["code"], "occurred_at_ms": e["occurred_at_ms"]} for e in data["events"]]
    return actual, expected
