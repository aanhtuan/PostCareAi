"""Giường, bệnh nhân, camera, ca trực: chỉ đọc trong prototype (mọi vai trò đã đăng nhập)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from postcare.api.deps import get_session, require_staff
from postcare.domain import catalog
from postcare.domain.dto import BedOut, CameraOut, PatientOut, ShiftOut, shift_out
from postcare.domain.shifts import list_shifts

router = APIRouter(tags=["catalog"], dependencies=[Depends(require_staff)])


@router.get("/beds", response_model=list[BedOut])
def beds(include_inactive: bool = False, db: Session = Depends(get_session)) -> list[BedOut]:
    return catalog.list_beds(db, include_inactive)


@router.get("/patients", response_model=list[PatientOut])
def patients(
    include_inactive: bool = False, db: Session = Depends(get_session)
) -> list[PatientOut]:
    return catalog.list_patients(db, include_inactive)


@router.get("/cameras", response_model=list[CameraOut])
def cameras(include_inactive: bool = False, db: Session = Depends(get_session)) -> list[CameraOut]:
    return catalog.list_cameras(db, include_inactive)


@router.get("/shifts", response_model=list[ShiftOut])
def shifts(db: Session = Depends(get_session)) -> list[ShiftOut]:
    return [shift_out(s) for s in list_shifts(db)]
