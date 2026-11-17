"""Phiên theo dõi (F04): 1 phiên mở / giường và / bệnh nhân."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from postcare.db.models import Bed, MonitoringSession, Patient, User
from postcare.db.types import utcnow
from postcare.domain.audit import record_audit
from postcare.domain.dto import Page, SessionOut, session_out
from postcare.domain.errors import DomainError, not_found, validation_error
from postcare.domain.notifications import Publisher, safe_publish


def _open_session_for(db: Session, *, bed_id: int | None = None, patient_id: int | None = None):
    q = select(MonitoringSession).where(MonitoringSession.ended_at.is_(None))
    if bed_id is not None:
        q = q.where(MonitoringSession.bed_id == bed_id)
    if patient_id is not None:
        q = q.where(MonitoringSession.patient_id == patient_id)
    return db.scalar(q)


def _already_open(target: str) -> DomainError:
    msg = (
        "Giường này đang có phiên theo dõi"
        if target == "bed"
        else "Bệnh nhân này đang được theo dõi ở giường khác"
    )
    return DomainError("SESSION_ALREADY_OPEN", msg, 409, {"conflict": target})


def _snapshot(s: MonitoringSession) -> dict[str, object]:
    return {
        "bed_id": s.bed_id,
        "patient_id": s.patient_id,
        "camera_id": s.camera_id,
        "started_at": s.started_at.isoformat(),
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
    }


def start_session(
    db: Session, *, bed_id: int, patient_id: int, user: User, publisher: Publisher
) -> SessionOut:
    # Khóa hàng giường và bệnh nhân tới hết transaction: không tranh chấp với xóa mềm (F03 R14).
    bed = db.get(Bed, bed_id, with_for_update=True)
    if bed is None:
        raise not_found("Không tìm thấy giường")
    patient = db.get(Patient, patient_id, with_for_update=True)
    if patient is None:
        raise not_found("Không tìm thấy bệnh nhân")
    if not bed.is_active or not patient.is_active:
        raise validation_error("Giường hoặc bệnh nhân đã ngừng dùng")
    if _open_session_for(db, bed_id=bed_id):
        raise _already_open("bed")
    if _open_session_for(db, patient_id=patient_id):
        raise _already_open("patient")

    session = MonitoringSession(
        bed_id=bed_id,
        patient_id=patient_id,
        camera_id=bed.camera.id if bed.camera else None,
        started_at=utcnow(),
        started_by=user.id,
    )
    db.add(session)
    try:
        db.flush()
    except IntegrityError as exc:  # hai yêu cầu đồng thời: partial unique index chặn
        db.rollback()
        raise _already_open("bed") from exc
    record_audit(
        db,
        actor_user_id=user.id,
        action="session.start",
        entity_type="session",
        entity_id=session.id,
        after=_snapshot(session),
    )
    db.commit()
    out = session_out(session)
    safe_publish(publisher, "session.updated", out)
    return out


def end_session(db: Session, *, session_id: int, user: User, publisher: Publisher) -> SessionOut:
    session = db.get(MonitoringSession, session_id)
    if session is None:
        raise not_found("Không tìm thấy phiên theo dõi")
    if session.ended_at is not None:
        raise DomainError("SESSION_ALREADY_ENDED", "Phiên theo dõi đã kết thúc", 409)
    before = _snapshot(session)
    session.ended_at = utcnow()
    session.ended_by = user.id
    record_audit(
        db,
        actor_user_id=user.id,
        action="session.end",
        entity_type="session",
        entity_id=session.id,
        before=before,
        after=_snapshot(session),
    )
    db.commit()
    out = session_out(session)
    safe_publish(publisher, "session.updated", out)
    return out


def get_session(db: Session, session_id: int) -> SessionOut:
    session = db.get(MonitoringSession, session_id)
    if session is None:
        raise not_found("Không tìm thấy phiên theo dõi")
    return session_out(session)


def list_sessions(
    db: Session,
    *,
    active: bool | None,
    bed_id: int | None,
    patient_id: int | None,
    limit: int,
    offset: int,
) -> Page[SessionOut]:
    q = select(MonitoringSession)
    if active is True:
        q = q.where(MonitoringSession.ended_at.is_(None))
    elif active is False:
        q = q.where(MonitoringSession.ended_at.is_not(None))
    if bed_id is not None:
        q = q.where(MonitoringSession.bed_id == bed_id)
    if patient_id is not None:
        q = q.where(MonitoringSession.patient_id == patient_id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(MonitoringSession.started_at.desc()).limit(limit).offset(offset))
    return Page[SessionOut](items=[session_out(s) for s in rows], total=total)


def session_at(db: Session, bed_id: int, at: datetime) -> MonitoringSession | None:
    """Phiên của giường đang mở tại thời điểm `at` (F17 R11)."""
    return db.scalar(
        select(MonitoringSession)
        .where(
            MonitoringSession.bed_id == bed_id,
            MonitoringSession.started_at <= at,
            (MonitoringSession.ended_at.is_(None)) | (MonitoringSession.ended_at > at),
        )
        .order_by(MonitoringSession.started_at.desc())
        .limit(1)
    )
