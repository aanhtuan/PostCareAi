"""Ca trực: đọc cho mọi vai trò nhân viên (F24), ghi chỉ ADMIN (F37). Giường…: `beds.py` (F03)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from postcare.api.deps import get_session, require_admin, require_staff
from postcare.db.models import User
from postcare.domain import shifts as sh
from postcare.domain.dto import ShiftCreate, ShiftOut, ShiftUpdate, shift_out

router = APIRouter(prefix="/shifts", tags=["catalog"])


@router.get("", response_model=list[ShiftOut], dependencies=[Depends(require_staff)])
def shifts(include_inactive: bool = False, db: Session = Depends(get_session)) -> list[ShiftOut]:
    """Mặc định chỉ ca đang dùng, sắp theo `start_time` (không phân trang: tối đa vài ca)."""
    return [shift_out(s) for s in sh.list_shifts(db, include_inactive)]


@router.post("", response_model=ShiftOut, status_code=201)
def create_shift(
    body: ShiftCreate, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> ShiftOut:
    return sh.create_shift(db, body, user)


@router.patch("/{shift_id}", response_model=ShiftOut)
def update_shift(
    shift_id: int,
    body: ShiftUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
) -> ShiftOut:
    return sh.update_shift(db, shift_id, body, user)


@router.delete("/{shift_id}", response_model=ShiftOut)
def delete_shift(
    shift_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> ShiftOut:
    """Xóa mềm. Bàn giao theo ca đã xóa vẫn tra cứu được (F37 R9)."""
    return sh.delete_shift(db, shift_id, user)


@router.post("/{shift_id}/restore", response_model=ShiftOut)
def restore_shift(
    shift_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> ShiftOut:
    """Khôi phục gây chồng giờ hoặc trùng tên với ca đang dùng → 409."""
    return sh.restore_shift(db, shift_id, user)
