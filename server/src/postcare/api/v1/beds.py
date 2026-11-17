"""Giường (F03): đọc cho mọi vai trò nhân viên, ghi chỉ ADMIN (api-conventions.md; QA#18, QA#36)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from postcare.api.deps import get_session, require_admin, require_staff
from postcare.db.models import User
from postcare.domain import catalog
from postcare.domain.dto import BedCreate, BedOut, BedUpdate, Page

router = APIRouter(prefix="/beds", tags=["catalog"])


@router.get("", response_model=Page[BedOut], dependencies=[Depends(require_staff)])
def list_beds(
    include_inactive: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
) -> Page[BedOut]:
    return catalog.list_beds(db, include_inactive, limit, offset)


@router.post("", response_model=BedOut, status_code=201)
def create_bed(
    body: BedCreate, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> BedOut:
    return catalog.create_bed(db, body, user)


@router.get("/{bed_id}", response_model=BedOut, dependencies=[Depends(require_staff)])
def get_bed(bed_id: int, db: Session = Depends(get_session)) -> BedOut:
    return catalog.get_bed(db, bed_id)


@router.patch("/{bed_id}", response_model=BedOut)
def update_bed(
    bed_id: int,
    body: BedUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
) -> BedOut:
    return catalog.update_bed(db, bed_id, body, user)


@router.delete("/{bed_id}", response_model=BedOut)
def delete_bed(
    bed_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> BedOut:
    """Xóa mềm. Lặp lại trả 200, không ghi audit."""
    return catalog.delete_bed(db, bed_id, user)


@router.post("/{bed_id}/restore", response_model=BedOut)
def restore_bed(
    bed_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> BedOut:
    return catalog.restore_bed(db, bed_id, user)
