"""Ca trực: chỉ đọc (mọi vai trò đã đăng nhập). Giường, bệnh nhân, camera: `beds.py`, … (F03)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from postcare.api.deps import get_current_user, get_session
from postcare.domain.dto import ShiftOut, shift_out
from postcare.domain.shifts import list_shifts

router = APIRouter(tags=["catalog"], dependencies=[Depends(get_current_user)])


@router.get("/shifts", response_model=list[ShiftOut])
def shifts(db: Session = Depends(get_session)) -> list[ShiftOut]:
    return [shift_out(s) for s in list_shifts(db)]
