"""Cấu hình camera do ADMIN chỉnh: Bed ROI và override ngưỡng (F08; PDF §7.2, §9.1; QA#15, QA#22).

- ROI kiểm tra bằng `validate_roi_polygon` (dùng chung với replay F12); sai → 400
  `INVALID_ROI_POLYGON`, `details.reason` là mã lý do.
- Override hợp nhất sâu với `config/engine.default.yaml` rồi validate bằng `EngineConfig` (F10);
  sai → 400 `VALIDATION_ERROR`, `details.errors[].path` dạng `thresholds.posture.lying_enter_deg`.
- Có thay đổi → `config_version += 1` (worker tải lại ≤5 s, F06) + audit `before`/`after` trong cùng
  transaction. Không đổi gì → không tăng version, không audit *(giả định, như F03 R16)*.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from postcare.db.models import Camera, User
from postcare.domain.audit import record_audit
from postcare.domain.dto import CameraRoiOut, CameraThresholdsOut
from postcare.domain.errors import DomainError, not_found, validation_error
from postcare.schemas.engine_config import EngineConfig, EngineConfigError, deep_merge
from postcare.schemas.roi import RoiPolygonError, validate_roi_polygon
from postcare.settings import REPO_ROOT

DEFAULT_ENGINE_CONFIG = REPO_ROOT / "config" / "engine.default.yaml"
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


def _effective(overrides: dict[str, Any], path: Path) -> dict[str, Any]:
    """Mặc định + override, đã validate; sai → 400 có đường dẫn khóa."""
    merged = deep_merge(_defaults(path), overrides)
    try:
        config = EngineConfig.from_mapping(merged, source="thresholds")
    except EngineConfigError as exc:
        errors = [{"path": f"thresholds.{p}", "msg": msg} for p, msg in exc.problems]
        keys = ", ".join(e["path"] for e in errors)
        raise validation_error(f"Ngưỡng không hợp lệ: {keys}", {"errors": errors}) from exc
    return config.model_dump(mode="json")


def _thresholds_out(camera: Camera, path: Path) -> CameraThresholdsOut:
    overrides = camera.thresholds or {}
    return CameraThresholdsOut(
        defaults=_defaults(path),
        overrides=overrides,
        effective=_effective(overrides, path),
        config_version=camera.config_version,
    )


def get_thresholds(
    db: Session, camera_id: int, path: Path = DEFAULT_ENGINE_CONFIG
) -> CameraThresholdsOut:
    return _thresholds_out(_get_camera(db, camera_id), path)


def update_thresholds(
    db: Session,
    camera_id: int,
    overrides: dict[str, Any],
    user: User,
    path: Path = DEFAULT_ENGINE_CONFIG,
) -> CameraThresholdsOut:
    _effective(overrides, path)  # kiểm tra trước khi khóa hàng
    camera = _locked_camera(db, camera_id)
    current = camera.thresholds or {}
    if current != overrides:
        before = {"thresholds": current, "config_version": camera.config_version}
        camera.thresholds = overrides
        camera.config_version += 1
        after = {"thresholds": overrides, "config_version": camera.config_version}
        _audit(db, user, "camera.update_thresholds", camera, before, after)
    db.commit()
    return _thresholds_out(camera, path)
