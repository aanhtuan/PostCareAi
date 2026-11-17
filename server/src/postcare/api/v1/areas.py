"""Khu vực (F37): đọc cho mọi vai trò nhân viên, ghi chỉ ADMIN (QA#36; api-conventions.md)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from postcare.api.deps import get_session, require_admin, require_staff
from postcare.db.models import User
from postcare.domain import areas
from postcare.domain.dto import AreaCreate, AreaOut, AreaUpdate, Page

router = APIRouter(prefix="/areas", tags=["catalog"])


@router.get("", response_model=Page[AreaOut], dependencies=[Depends(require_staff)])
def list_areas(
    include_inactive: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
) -> Page[AreaOut]:
    return areas.list_areas(db, include_inactive, limit, offset)


@router.post("", response_model=AreaOut, status_code=201)
def create_area(
    body: AreaCreate, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> AreaOut:
    return areas.create_area(db, body, user)


@router.get("/{area_id}", response_model=AreaOut, dependencies=[Depends(require_staff)])
def get_area(area_id: int, db: Session = Depends(get_session)) -> AreaOut:
    return areas.get_area(db, area_id)


@router.patch("/{area_id}", response_model=AreaOut)
def update_area(
    area_id: int,
    body: AreaUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
) -> AreaOut:
    return areas.update_area(db, area_id, body, user)


@router.delete("/{area_id}", response_model=AreaOut)
def delete_area(
    area_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> AreaOut:
    """Xóa mềm. Còn giường đang dùng → 409 `AREA_IN_USE`. Lặp lại trả 200, không audit."""
    return areas.delete_area(db, area_id, user)


@router.post("/{area_id}/restore", response_model=AreaOut)
def restore_area(
    area_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> AreaOut:
    return areas.restore_area(db, area_id, user)
