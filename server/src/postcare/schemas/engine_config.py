"""Cấu hình ngưỡng của Event Engine (event-engine.md mục 6; QA#22).

Mặc định ở `config/engine.default.yaml`; override theo camera (`cameras.thresholds` hoặc
`config/cameras/<setup>.yaml`) được hợp nhất sâu rồi validate. Khóa lạ, sai kiểu, thiếu khóa
đều là lỗi có đường dẫn khóa, để bắt lỗi gõ nhầm *(giả định)*.
"""

import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, Strict, ValidationError

from postcare.schemas.observation import KeypointName, UnitFloat

NonNegFloat = Annotated[float, Field(ge=0.0)]
PosFloat = Annotated[float, Field(gt=0.0)]
PosInt = Annotated[int, Field(gt=0)]
NonNegInt = Annotated[int, Field(ge=0)]
Degrees = Annotated[float, Field(ge=0.0, le=180.0)]

# Khối không tính vào config_hash: chỉ ảnh hưởng hiển thị (F28).
HASH_EXCLUDED_BLOCKS = frozenset({"privacy"})


class EngineConfigError(ValueError):
    """Cấu hình engine không hợp lệ. `problems` là danh sách (đường dẫn khóa, mô tả)."""

    def __init__(self, source: str, problems: list[tuple[str, str]]) -> None:
        self.source = source
        self.problems = problems
        lines = "\n".join(f"  {path}: {msg}" for path, msg in problems)
        super().__init__(f"Cấu hình engine không hợp lệ ({source}):\n{lines}")


class _Block(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class PoseConfig(_Block):
    num_poses: PosInt
    min_keypoint_visibility: UnitFloat
    required_keypoints: Annotated[list[Annotated[KeypointName, Strict(False)]], Field(min_length=1)]


class QualityConfig(_Block):
    low_quality_to_no_observation_s: NonNegFloat
    restore_duration_s: NonNegFloat
    observation_lost_event_s: NonNegFloat


class TargetConfig(_Block):
    max_jump_torso_lengths: PosFloat


class SmoothingConfig(_Block):
    ema_alpha: Annotated[float, Field(gt=0.0, le=1.0)]


class PostureConfig(_Block):
    lying_enter_deg: Degrees
    lying_exit_deg: Degrees
    sitting_enter_deg: Degrees
    sitting_exit_deg: Degrees
    torso_length_ratio_sitting: UnitFloat
    standing_hip_above_knee_ratio: PosFloat


class LocationConfig(_Block):
    edge_distance_torso: NonNegFloat
    out_of_roi_margin_torso: NonNegFloat


class MinDurationConfig(_Block):
    """Thời gian giữ tối thiểu (giây) trước khi vào trạng thái đích. Tên khóa = mã trạng thái."""

    RAISING: NonNegFloat
    SITTING: NonNegFloat
    AT_EDGE: NonNegFloat
    STANDING: NonNegFloat
    OUT_OF_BED: NonNegFloat
    LYING: NonNegFloat
    RETURN_TO_BED: NonNegFloat


class PostureChangeConfig(_Block):
    shoulder_angle_delta_deg: Degrees
    stable_s: NonNegFloat


class DebounceConfig(_Block):
    same_code_same_session_s: NonNegFloat


class ActivityConfig(_Block):
    window_s: PosFloat
    sample_interval_s: PosFloat
    low_threshold: NonNegFloat
    high_threshold: NonNegFloat
    low_prolonged_s: NonNegFloat
    increased_hold_s: NonNegFloat


class AbnormalMovementConfig(_Block):
    window_s: PosFloat
    hip_drop_speed_torso_per_s: NonNegFloat
    displacement_torso: NonNegFloat
    trunk_angle_change_deg: Degrees
    final_low_position_ratio: UnitFloat
    hold_after_s: NonNegFloat
    min_conditions: PosInt


class FaceSignalConfig(_Block):
    """Một tín hiệu mặt: gộp các khóa blendshape bằng max rồi so ngưỡng (F26)."""

    keys: Annotated[list[str], Field(min_length=1)]
    threshold: UnitFloat


class FaceSignalsConfig(_Block):
    eyes_closed: FaceSignalConfig
    brow_down: FaceSignalConfig
    eye_squint: FaceSignalConfig
    nose_sneer: FaceSignalConfig
    mouth_change: FaceSignalConfig


class FaceConfig(_Block):
    enabled: bool
    min_head_box_px: NonNegInt
    run_every_n_frames: PosInt
    head_crop_scale: PosFloat
    signals: FaceSignalsConfig
    eyes_closed_prolonged_s: NonNegFloat
    attention_min_signals: PosInt
    attention_hold_s: NonNegFloat


class RestConfig(_Block):
    low_activity_s: NonNegFloat
    eyes_closed_s: NonNegFloat
    active_hold_s: NonNegFloat


class PrivacyConfig(_Block):
    head_box_scale: PosFloat
    pixelate_blocks: PosInt
    head_hold_s: NonNegFloat


class EngineConfig(_Block):
    """Toàn bộ ngưỡng của engine; cấu trúc khớp `config/engine.default.yaml`."""

    version: Literal[1]
    pose: PoseConfig
    quality: QualityConfig
    target: TargetConfig
    smoothing: SmoothingConfig
    posture: PostureConfig
    location: LocationConfig
    min_duration_s: MinDurationConfig
    posture_change: PostureChangeConfig
    debounce: DebounceConfig
    activity: ActivityConfig
    abnormal_movement: AbnormalMovementConfig
    face: FaceConfig
    rest: RestConfig
    privacy: PrivacyConfig

    @classmethod
    def load(
        cls,
        path: Path | str,
        overrides: Mapping[str, Any] | Path | str | None = None,
    ) -> Self:
        """Đọc YAML mặc định, hợp nhất sâu override (dict hoặc file YAML), rồi validate."""
        path = Path(path)
        data = _read_yaml(path)
        source = str(path)
        if overrides is not None:
            if isinstance(overrides, str | Path):
                extra = _read_yaml(Path(overrides))
                source = f"{path} + {overrides}"
            else:
                extra = dict(overrides)
                source = f"{path} + override"
            data = deep_merge(data, extra)
        return cls.from_mapping(data, source=source)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], *, source: str = "<dict>") -> Self:
        """Validate cấu hình đã hợp nhất; lỗi → `EngineConfigError` có đường dẫn khóa."""
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            problems = [
                (".".join(str(p) for p in err["loc"]) or "<root>", err["msg"])
                for err in exc.errors()
            ]
            raise EngineConfigError(source, problems) from exc

    def config_hash(self) -> str:
        """sha256 của cấu hình dạng JSON chuẩn (khóa sắp xếp, không khoảng trắng), bỏ `privacy`."""
        data = self.model_dump(mode="json", exclude=set(HASH_EXCLUDED_BLOCKS))
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Hợp nhất sâu: dict lồng nhau thì hợp nhất từng khóa, giá trị khác thì override thay thế.

    Không sửa đầu vào.
    """
    merged: dict[str, Any] = copy.deepcopy(dict(base))
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = deep_merge(current, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EngineConfigError(str(path), [("<file>", f"không đọc được file: {exc}")]) from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise EngineConfigError(str(path), [("<file>", f"YAML không hợp lệ: {exc}")]) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise EngineConfigError(str(path), [("<root>", "nội dung phải là một mapping")])
    return data
