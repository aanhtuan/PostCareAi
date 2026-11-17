"""File cấu hình camera dùng khi quay / replay: `config/cameras/<setup>.yaml` (F12 R3).

```yaml
version: 1
camera_id: 0              # tuỳ chọn; camera_id ghi vào observation khi replay video
roi_polygon:              # toạ độ chuẩn hóa 0–1 theo khung hình, theo thứ tự vẽ
  - [0.2, 0.3]
  - [0.8, 0.3]
  - [0.8, 0.8]
thresholds: {}            # override `config/engine.default.yaml` (hợp nhất sâu), có thể rỗng
notes: "…"                # tuỳ chọn
```

ROI kiểm tra bằng `validate_roi_polygon`; ngưỡng hợp nhất bằng `EngineConfig.load` (F10).
Sai định dạng → `CameraConfigError` nêu đường dẫn khóa (evaluation.md §4).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from postcare.schemas.context import EngineContext
from postcare.schemas.engine_config import EngineConfig, EngineConfigError
from postcare.schemas.roi import RoiPolygon, validate_roi_polygon


class CameraConfigError(ValueError):
    """File cấu hình camera không hợp lệ."""

    def __init__(self, source: str, problems: list[tuple[str, str]]) -> None:
        self.source = source
        self.problems = problems
        lines = "\n".join(f"  {path}: {msg}" for path, msg in problems)
        super().__init__(f"Cấu hình camera không hợp lệ ({source}):\n{lines}")


class CameraConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal[1]
    camera_id: int = 0
    roi_polygon: RoiPolygon
    thresholds: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""

    @field_validator("roi_polygon", mode="before")
    @classmethod
    def _roi(cls, value: Any) -> RoiPolygon:
        if isinstance(value, RoiPolygon):
            return validate_roi_polygon(value.points)
        if isinstance(value, dict) and "points" in value:
            value = value["points"]
        if not isinstance(value, list | tuple) or not all(
            isinstance(p, list | tuple) for p in value
        ):
            raise ValueError("phải là danh sách đỉnh [x, y]")
        return validate_roi_polygon(value)

    @field_validator("thresholds", mode="before")
    @classmethod
    def _thresholds(cls, value: Any) -> Any:
        return {} if value is None else value

    def context(self) -> EngineContext:
        return EngineContext(camera_id=self.camera_id, roi_polygon=self.roi_polygon)

    def engine_config(self, default_path: Path | str) -> EngineConfig:
        """Ngưỡng mặc định hợp nhất với `thresholds`; sai → `CameraConfigError`."""
        try:
            return EngineConfig.load(default_path, self.thresholds)
        except EngineConfigError as exc:
            problems = [(f"thresholds.{path}", msg) for path, msg in exc.problems]
            raise CameraConfigError(exc.source, problems) from exc

    def to_dict(self) -> dict[str, Any]:
        """Dạng ghi vào `.expected.json` của fixture (không có `notes`)."""
        return {
            "version": self.version,
            "camera_id": self.camera_id,
            "roi_polygon": [list(p) for p in self.roi_polygon.points],
            "thresholds": self.thresholds,
        }

    @classmethod
    def from_mapping(cls, data: Any, *, source: str) -> CameraConfig:
        if not isinstance(data, dict):
            raise CameraConfigError(source, [("<root>", "nội dung phải là một mapping")])
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            problems = [
                (".".join(str(p) for p in err["loc"]) or "<root>", err["msg"])
                for err in exc.errors()
            ]
            raise CameraConfigError(source, problems) from exc


def load_camera_config(path: Path | str) -> CameraConfig:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CameraConfigError(str(path), [("<file>", f"không đọc được file: {exc}")]) from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CameraConfigError(str(path), [("<file>", f"YAML không hợp lệ: {exc}")]) from exc
    return CameraConfig.from_mapping(data, source=str(path))
