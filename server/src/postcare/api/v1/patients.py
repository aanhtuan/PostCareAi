"""Bệnh nhân, chỉ mã thử nghiệm (F03): đọc cho nhân viên, ghi chỉ ADMIN (QA#18, QA#36)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from postcare.api.deps import get_session, require_admin, require_staff
from postcare.db.models import User
from postcare.domain import catalog
from postcare.domain.dto import Page, PatientCreate, PatientOut, PatientUpdate

router = APIRouter(prefix="/patients", tags=["catalog"])


@router.get("", response_model=Page[PatientOut], dependencies=[Depends(require_staff)])
def list_patients(
    include_inactive: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
) -> Page[PatientOut]:
    return catalog.list_patients(db, include_inactive, limit, offset)


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(
    body: PatientCreate, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> PatientOut:
    return catalog.create_patient(db, body, user)


@router.get("/{patient_id}", response_model=PatientOut, dependencies=[Depends(require_staff)])
def get_patient(patient_id: int, db: Session = Depends(get_session)) -> PatientOut:
    return catalog.get_patient(db, patient_id)


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: int,
    body: PatientUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
) -> PatientOut:
    return catalog.update_patient(db, patient_id, body, user)


@router.delete("/{patient_id}", response_model=PatientOut)
def delete_patient(
    patient_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> PatientOut:
    """Xóa mềm. Lặp lại trả 200, không ghi audit."""
    return catalog.delete_patient(db, patient_id, user)


@router.post("/{patient_id}/restore", response_model=PatientOut)
def restore_patient(
    patient_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)
) -> PatientOut:
    return catalog.restore_patient(db, patient_id, user)
