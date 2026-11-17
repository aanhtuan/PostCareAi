"""Ghi kết quả replay: JSONL xác định (F12 R1, R5) và `run.json`.

- Mỗi dòng là JSON của một model Pydantic: thứ tự trường cố định theo khai báo, không khoảng
  trắng, UTF-8 (không escape tiếng Việt), xuống dòng LF.
- `events.jsonl`, `frames.jsonl` chỉ chứa dữ liệu suy ra từ `ts_ms`; số liệu phụ thuộc máy
  (FPS xử lý, CPU, RAM, thời điểm chạy) chỉ ghi vào `run.json` *(giả định của spec)*.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Self

from pydantic import BaseModel, ConfigDict

from postcare.schemas.enums import (
    ActivityLevel,
    BodyState,
    FaceStatus,
    ObservationQuality,
    RestStatus,
)
from postcare.schemas.events import EngineEvent, EngineOutput
from postcare.schemas.observation import FrameObservation


class EventRecord(EngineEvent):
    """Dòng `events.jsonl`: `EngineEvent` kèm `config_hash` của cấu hình đã chạy."""

    config_hash: str


class FrameRecord(BaseModel):
    """Dòng `frames.jsonl`: trạng thái engine sau mỗi khung (F16 tính coverage)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    frame_index: int
    ts_ms: int
    body_state: BodyState
    observation_quality: ObservationQuality
    activity_level: ActivityLevel
    rest_status: RestStatus
    face_status: FaceStatus
    persons: int
    """Số người adapter thấy trong khung (cả ngoài ROI)."""

    @classmethod
    def from_output(cls, obs: FrameObservation, output: EngineOutput) -> FrameRecord:
        state = output.state
        return cls(
            frame_index=obs.frame_index,
            ts_ms=obs.ts_ms,
            body_state=state.body_state,
            observation_quality=state.observation_quality,
            activity_level=state.activity_level,
            rest_status=state.rest_status,
            face_status=state.face_status,
            persons=len(obs.persons),
        )


def dump_line(model: BaseModel) -> str:
    """Một dòng JSONL (kết thúc bằng `\\n`)."""
    return model.model_dump_json() + "\n"


class JsonlWriter:
    """Ghi model vào file JSONL, UTF-8, LF."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.count = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        self._f: IO[str] = path.open("w", encoding="utf-8", newline="\n")

    def write(self, model: BaseModel) -> None:
        self._f.write(dump_line(model))
        self.count += 1

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def write_json(path: Path, data: Any) -> None:
    """JSON có thụt lề (run.json, .expected.json), UTF-8, LF, kết thúc bằng xuống dòng."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
