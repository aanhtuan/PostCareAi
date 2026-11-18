"""Cấu hình camera do ADMIN chỉnh: Bed ROI và override ngưỡng (F08; PDF §7.2, §9.1; QA#15, QA#22).

- ROI kiểm tra bằng `validate_roi_polygon` (dùng chung với replay F12); sai → 400
  `INVALID_ROI_POLYGON`, `details.reason` là mã lý do.
- Override chỉ được dùng khóa trong `config/camera_overrides.yaml` (`allowed`); hợp nhất sâu với
  `config/engine.default.yaml`, validate bằng `EngineConfig` (F10), rồi kiểm tra giới hạn an toàn
  (`limits`) và quan hệ giữa ngưỡng (`relations`) để override không vô hiệu hóa quy tắc an toàn
  (AGENTS.md quy tắc 6). Sai → 400 `VALIDATION_ERROR`, `details.errors[].path` dạng
  `thresholds.posture.lying_enter_deg`.
- Có thay đổi → `config_version += 1` (worker tải lại ≤5 s, F06) + audit `before`/`after` trong cùng
  transaction. Không đổi gì → không tăng version, không audit *(giả định, như F03 R16)*.
"""

from collections.abc import Iterator, Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, NoReturn

import yaml
from sqlalchemy.orm import Session

from postcare.db.models import Camera, User
from postcare.domain.audit import record_audit
from postcare.domain.dto import CameraRoiOut, CameraThresholdsOut, ThresholdRules
from postcare.domain.errors import DomainError, not_found, validation_error
from postcare.schemas.engine_config import EngineConfig, EngineConfigError, deep_merge
from postcare.schemas.roi import RoiPolygonError, validate_roi_polygon
from postcare.settings import REPO_ROOT

DEFAULT_ENGINE_CONFIG = REPO_ROOT / "config" / "engine.default.yaml"
DEFAULT_OVERRIDE_RULES = REPO_ROOT / "config" / "camera_overrides.yaml"
_CAMERA_NOT_FOUND = "Không tìm thấy camera"


@lru_cache(maxsize=4)
def _defaults(path: Path) -> dict[str, Any]:
    """Ngưỡng mặc định đã validate, dạng JSON. Đọc một lần mỗi tiến trình API."""
    return EngineConfig.load(path).model_dump(mode="json")


def _locked_camera(db: Session, camera_id: int) -> Camera:
    camera = db.get(Camera, camera_id, with_for_update=True)
    if camera is None:
        raise not_found(_CAMERA_NOT_FOUND)
    return camera


def _get_camera(db: Session, camera_id: int) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise not_found(_CAMERA_NOT_FOUND)
    return camera


def _audit(db: Session, user: User, action: str, camera: Camera, before: Any, after: Any) -> None:
    record_audit(
        db,
        actor_user_id=user.id,
        action=action,
        entity_type="camera",
        entity_id=camera.id,
        before=before,
        after=after,
    )


# ---------- Bed ROI ----------


def update_roi(db: Session, camera_id: int, points: list[Any], user: User) -> CameraRoiOut:
    try:
        roi = validate_roi_polygon(points)
    except RoiPolygonError as exc:
        raise DomainError(
            "INVALID_ROI_POLYGON",
            f"Vùng giường không hợp lệ: {exc}",
            400,
            {"reason": exc.reason},
        ) from exc
    camera = _locked_camera(db, camera_id)
    new_roi = [[x, y] for x, y in roi.points]
    if camera.roi_polygon != new_roi:
        before = {"roi_polygon": camera.roi_polygon, "config_version": camera.config_version}
        camera.roi_polygon = new_roi
        camera.config_version += 1
        after = {"roi_polygon": new_roi, "config_version": camera.config_version}
        _audit(db, user, "camera.update_roi", camera, before, after)
    db.commit()
    return CameraRoiOut(
        camera_id=camera.id, roi_polygon=new_roi, config_version=camera.config_version
    )


# ---------- Ngưỡng ----------

Problem = tuple[str, str]


@lru_cache(maxsize=4)
def load_override_rules(path: Path = DEFAULT_OVERRIDE_RULES) -> ThresholdRules:
    """Đọc `config/camera_overrides.yaml` (khóa được phép, giới hạn an toàn, quan hệ)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or data.pop("version", None) != 1:
        raise ValueError(f"{path}: cần `version: 1`")
    return ThresholdRules.model_validate(data)


def _leaf_paths(tree: Mapping[str, Any], prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Đường dẫn `a.b` tới từng giá trị lá; dict rỗng không có lá."""
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if isinstance(value, Mapping):
            yield from _leaf_paths(value, f"{path}.")
        else:
            yield path, value


def _value(tree: Mapping[str, Any], path: str) -> Any:
    node: Any = tree
    for part in path.split("."):
        if not isinstance(node, Mapping):
            return None
        node = node.get(part)
    return node


def _is_number(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def rule_violations(effective: Mapping[str, Any], rules: ThresholdRules) -> list[Problem]:
    """Giá trị đang áp dụng vi phạm `limits` hoặc `relations` (đường dẫn chưa có `thresholds.`)."""
    problems: list[Problem] = []
    for path, value in _leaf_paths(effective):
        limit = rules.limit_for(path)
        if limit is None or not _is_number(value):
            continue
        if limit.min is not None and value < limit.min:
            problems.append((path, f"phải ≥ {limit.min:g} (giới hạn an toàn)"))
        if limit.max is not None and value > limit.max:
            problems.append((path, f"phải ≤ {limit.max:g} (giới hạn an toàn)"))
    for rel in rules.relations:
        low, high = _value(effective, rel.low), _value(effective, rel.high)
        if not (_is_number(low) and _is_number(high)):
            continue
        if low > high or (rel.strict and low >= high):
            above, below = (">", "<") if rel.strict else ("≥", "≤")
            problems.append((rel.high, f"phải {above} {rel.low} ({low:g})"))
            problems.append((rel.low, f"phải {below} {rel.high} ({high:g})"))
    return problems


def _raise(problems: list[Problem]) -> NoReturn:
    errors = [{"path": f"thresholds.{p}", "msg": msg} for p, msg in problems]
    keys = ", ".join(dict.fromkeys(e["path"] for e in errors))
    raise validation_error(f"Ngưỡng không hợp lệ: {keys}", {"errors": errors})


def _merged(overrides: dict[str, Any], path: Path) -> dict[str, Any]:
    """Mặc định + override, validate bằng `EngineConfig`; sai → 400 có đường dẫn khóa."""
    merged = deep_merge(_defaults(path), overrides)
    try:
        config = EngineConfig.from_mapping(merged, source="thresholds")
    except EngineConfigError as exc:
        _raise(list(exc.problems))
    return config.model_dump(mode="json")


def _effective(overrides: dict[str, Any], path: Path, rules: ThresholdRules) -> dict[str, Any]:
    """Kiểm tra khi lưu: khóa được phép → EngineConfig → giới hạn an toàn và quan hệ."""
    blocked = [
        (p, "không được chỉnh theo camera")
        for p, _ in _leaf_paths(overrides)
        if not rules.is_allowed(p)
    ]
    if blocked:
        _raise(blocked)
    effective = _merged(overrides, path)
    problems = rule_violations(effective, rules)
    if problems:
        _raise(problems)
    return effective


def _thresholds_out(camera: Camera, path: Path, rules: ThresholdRules) -> CameraThresholdsOut:
    overrides = camera.thresholds or {}
    return CameraThresholdsOut(
        defaults=_defaults(path),
        overrides=overrides,
        effective=_merged(overrides, path),
        config_version=camera.config_version,
        rules=rules,
    )


def get_thresholds(
    db: Session,
    camera_id: int,
    path: Path = DEFAULT_ENGINE_CONFIG,
    rules_path: Path = DEFAULT_OVERRIDE_RULES,
) -> CameraThresholdsOut:
    return _thresholds_out(_get_camera(db, camera_id), path, load_override_rules(rules_path))


def update_thresholds(
    db: Session,
    camera_id: int,
    overrides: dict[str, Any],
    user: User,
    path: Path = DEFAULT_ENGINE_CONFIG,
    rules_path: Path = DEFAULT_OVERRIDE_RULES,
) -> CameraThresholdsOut:
    rules = load_override_rules(rules_path)
    _effective(overrides, path, rules)  # kiểm tra trước khi khóa hàng
    camera = _locked_camera(db, camera_id)
    current = camera.thresholds or {}
    if current != overrides:
        before = {"thresholds": current, "config_version": camera.config_version}
        camera.thresholds = overrides
        camera.config_version += 1
        after = {"thresholds": overrides, "config_version": camera.config_version}
        _audit(db, user, "camera.update_thresholds", camera, before, after)
    db.commit()
    return _thresholds_out(camera, path, rules)
