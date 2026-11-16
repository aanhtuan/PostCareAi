"""Danh mục giường, bệnh nhân (mã thử nghiệm), camera: chỉ đọc trong prototype."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from postcare.db.models import Bed, Camera, MonitoringSession, Patient
from postcare.domain.dto import (
    BedOut,
    CameraOut,
    PatientOut,
    bed_out,
    camera_out,
    patient_out,
)


def _active_sessions(db: Session) -> list[MonitoringSession]:
    return list(
        db.scalars(
            select(MonitoringSession)
            .where(MonitoringSession.ended_at.is_(None))
            .options(
                selectinload(MonitoringSession.patient),
                selectinload(MonitoringSession.bed),
                selectinload(MonitoringSession.starter),
            )
        )
    )


def list_beds(db: Session, include_inactive: bool = False) -> list[BedOut]:
    q = select(Bed).options(selectinload(Bed.camera)).order_by(Bed.code)
    if not include_inactive:
        q = q.where(Bed.is_active.is_(True))
    by_bed = {s.bed_id: s for s in _active_sessions(db)}
    return [bed_out(b, by_bed.get(b.id)) for b in db.scalars(q)]


def list_patients(db: Session, include_inactive: bool = False) -> list[PatientOut]:
    q = select(Patient).order_by(Patient.code)
    if not include_inactive:
        q = q.where(Patient.is_active.is_(True))
    by_patient = {s.patient_id: s.id for s in _active_sessions(db)}
    return [patient_out(p, by_patient.get(p.id)) for p in db.scalars(q)]


def list_cameras(db: Session, include_inactive: bool = False) -> list[CameraOut]:
    q = select(Camera).options(selectinload(Camera.bed)).order_by(Camera.id)
    if not include_inactive:
        q = q.where(Camera.is_active.is_(True))
    return [camera_out(c) for c in db.scalars(q)]
