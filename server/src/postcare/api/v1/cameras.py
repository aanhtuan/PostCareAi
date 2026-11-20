"""Camera (F03): đọc cho mọi vai trò nhân viên, ghi chỉ ADMIN (api-conventions.md; QA#18, QA#36)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from postcare.api.deps import (
    get_frames,
    get_session,
    get_settings_dep,
    get_store,
    require_admin,
    require_roles,
    require_staff,
)
from postcare.api.frame_buffer import LatestFrameStore
from postcare.db.models import Camera, User
from postcare.db.types import utcnow
from postcare.domain import camera_config, catalog
from postcare.domain.dto import (
    CameraCreate,
    CameraDetailOut,
    CameraDisplayModeIn,
    CameraOut,
    CameraRoiIn,
    CameraRoiOut,
    CameraRuntimeOut,
    CameraThresholdsIn,
    CameraThresholdsOut,
    CameraUpdate,
    Page,
)
from postcare.domain.runtime import RuntimeStore
from postcare.schemas.enums import UserRole
from postcare.settings import Settings

router = APIRouter(prefix="/cameras", tags=["catalog"])


@router.get("", response_model=Page[CameraOut], dependencies=[Depends(require_staff)])
def list_cameras(
    include_inactive: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
) -> Page[CameraOut]:
    return catalog.list_cameras(db, include_inactive, limit, offset)


@router.post("", response_model=CameraOut, status_code=201)
def create_camera(
    body: CameraCreate, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> CameraOut:
    return catalog.create_camera(db, body, user)


@router.get("/{camera_id}", response_model=CameraDetailOut, dependencies=[Depends(require_staff)])
def get_camera(
    camera_id: int,
    db: Session = Depends(get_session),
    store: RuntimeStore = Depends(get_store),
    frames: LatestFrameStore = Depends(get_frames),
    settings: Settings = Depends(get_settings_dep),
) -> CameraDetailOut:
    """Kèm `runtime` từ heartbeat trong RAM (F06 R9) và `roi_polygon` (F07 R6)."""
    out = catalog.get_camera(db, camera_id)
    rt = store.find_camera(camera_id)
    runtime = None
    if rt is not None and rt.updated_at is not None:
        runtime = CameraRuntimeOut(
            fps=rt.fps,
            brightness=rt.brightness,
            dropped_frames=rt.dropped_frames,
            source_status=rt.source_status,
            updated_at=rt.updated_at,
        )
    camera = db.get(Camera, camera_id)
    roi = camera.roi_polygon if camera is not None else None
    now = utcnow()
    return CameraDetailOut(
        **out.model_dump(),
        runtime=runtime,
        roi_polygon=roi,
        worker_active=runtime is not None
        and (now - runtime.updated_at).total_seconds() <= settings.camera_offline_after_s,
        has_current_frames=all(
            frame is not None
            and frame.config_version == out.config_version
            and frame.is_fresh(now, settings.stream_stale_frame_s)
            for frame in (frames.get(camera_id), frames.get(camera_id, view="skeleton"))
        ),
    )


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: int,
    body: CameraUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
) -> CameraOut:
    return catalog.update_camera(db, camera_id, body, user)


@router.delete("/{camera_id}", response_model=CameraOut)
def delete_camera(
    camera_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> CameraOut:
    """Xóa mềm. Lặp lại trả 200, không ghi audit."""
    return catalog.delete_camera(db, camera_id, user)


@router.post("/{camera_id}/restore", response_model=CameraOut)
def restore_camera(
    camera_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> CameraOut:
    return catalog.restore_camera(db, camera_id, user)


# ---------- Cấu hình camera (F08): chỉ ADMIN; mỗi lần đổi tăng config_version + audit ----------


@router.put("/{camera_id}/roi", response_model=CameraRoiOut)
def update_roi(
    camera_id: int,
    body: CameraRoiIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
) -> CameraRoiOut:
    """Lưu Bed ROI (toạ độ chuẩn hóa 0–1). Sai → 400 `INVALID_ROI_POLYGON`, `details.reason`."""
    return camera_config.update_roi(db, camera_id, body.roi_polygon, user)


@router.get(
    "/{camera_id}/thresholds",
    response_model=CameraThresholdsOut,
    dependencies=[Depends(require_admin)],
)
def get_thresholds(camera_id: int, db: Session = Depends(get_session)) -> CameraThresholdsOut:
    """Ngưỡng mặc định, override của camera và giá trị đang áp dụng."""
    return camera_config.get_thresholds(db, camera_id)


@router.put("/{camera_id}/thresholds", response_model=CameraThresholdsOut)
def update_thresholds(
    camera_id: int,
    body: CameraThresholdsIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
) -> CameraThresholdsOut:
    """Thay toàn bộ override; `{}` = khôi phục mặc định. Sai → 400 kèm đường dẫn khóa."""
    return camera_config.update_thresholds(db, camera_id, body.thresholds, user)


# ---------- Chế độ hiển thị (F28): ADMIN và CHARGE_NURSE ----------

require_display_mode_editor = require_roles(UserRole.ADMIN, UserRole.CHARGE_NURSE)


@router.put("/{camera_id}/display-mode", response_model=CameraOut)
def update_display_mode(
    camera_id: int,
    body: CameraDisplayModeIn,
    user: User = Depends(require_display_mode_editor),
    db: Session = Depends(get_session),
) -> CameraOut:
    """Đổi chế độ hiển thị `RAW` / `BLUR` / `SKELETON`; đổi → tăng `config_version` + audit."""
    return camera_config.update_display_mode(db, camera_id, body.display_mode, user)
