"""Camera (F03): đọc cho mọi vai trò nhân viên, ghi chỉ ADMIN (api-conventions.md; QA#18, QA#36)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from postcare.api.deps import get_current_user, get_session, require_admin
from postcare.db.models import User
from postcare.domain import catalog
from postcare.domain.dto import CameraCreate, CameraOut, CameraUpdate, Page

router = APIRouter(prefix="/cameras", tags=["catalog"])


@router.get("", response_model=Page[CameraOut], dependencies=[Depends(get_current_user)])
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


@router.get("/{camera_id}", response_model=CameraOut, dependencies=[Depends(get_current_user)])
def get_camera(camera_id: int, db: Session = Depends(get_session)) -> CameraOut:
    return catalog.get_camera(db, camera_id)


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
