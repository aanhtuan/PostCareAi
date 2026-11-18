"""Camera (F03): đọc cho mọi vai trò nhân viên, ghi chỉ ADMIN (api-conventions.md; QA#18, QA#36)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from postcare.api.deps import get_session, get_store, require_admin, require_staff
from postcare.db.models import Camera, User
from postcare.domain import camera_config, catalog
from postcare.domain.dto import (
    CameraCreate,
    CameraDetailOut,
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
    camera_id: int, db: Session = Depends(get_session), store: RuntimeStore = Depends(get_store)
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
    return CameraDetailOut(**out.model_dump(), runtime=runtime, roi_polygon=roi)


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
