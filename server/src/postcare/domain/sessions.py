"""Phiên theo dõi (F04): 1 phiên mở / giường và / bệnh nhân, chuyển giường, tạm dừng thu hình.

Mọi thao tác ghi: khóa hàng liên quan (`FOR UPDATE`), ghi audit trong cùng transaction, commit,
rồi mới phát `session.updated` (AGENTS.md quy tắc 7).
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from postcare.db.models import Bed, MonitoringSession, Patient, User
from postcare.db.types import utcnow
from postcare.domain.audit import record_audit
from postcare.domain.dto import Page, SessionChainItem, SessionOut, session_out
from postcare.domain.errors import DomainError, not_found, validation_error
from postcare.domain.notifications import Publisher, safe_publish


def _open_session_for(db: Session, *, bed_id: int | None = None, patient_id: int | None = None):
    q = select(MonitoringSession).where(MonitoringSession.ended_at.is_(None))
    if bed_id is not None:
        q = q.where(MonitoringSession.bed_id == bed_id)
    if patient_id is not None:
        q = q.where(MonitoringSession.patient_id == patient_id)
    return db.scalar(q)


def _already_open(target: str, entity_id: int) -> DomainError:
    msg = (
        "Giường này đang có phiên theo dõi"
        if target == "bed"
        else "Bệnh nhân này đang được theo dõi ở giường khác"
    )
    return DomainError(
        "SESSION_ALREADY_OPEN", msg, 409, {"conflict": target, f"{target}_id": entity_id}
    )


def _already_ended() -> DomainError:
    return DomainError("SESSION_ALREADY_ENDED", "Phiên theo dõi đã kết thúc", 409)


def _snapshot(s: MonitoringSession) -> dict[str, object]:
    return {
        "bed_id": s.bed_id,
        "patient_id": s.patient_id,
        "camera_id": s.camera_id,
        "started_at": s.started_at.isoformat(),
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "paused_at": s.paused_at.isoformat() if s.paused_at else None,
    }


def _locked_session(db: Session, session_id: int) -> MonitoringSession:
    """Khóa hàng phiên: kết thúc, chuyển giường, tạm dừng không chạy chồng lên nhau."""
    session = db.get(MonitoringSession, session_id, with_for_update=True, populate_existing=True)
    if session is None:
        raise not_found("Không tìm thấy phiên theo dõi")
    return session


def _locked_open_session(db: Session, session_id: int) -> MonitoringSession:
    session = _locked_session(db, session_id)
    if session.ended_at is not None:
        raise _already_ended()
    return session


def _locked_active_bed(db: Session, bed_id: int) -> Bed:
    bed = db.get(Bed, bed_id, with_for_update=True)
    if bed is None:
        raise not_found("Không tìm thấy giường")
    if not bed.is_active:
        raise validation_error("Giường đã ngừng dùng", {"bed_id": bed_id})
    return bed


def _close(session: MonitoringSession, user: User, at: datetime) -> None:
    session.ended_at = at
    session.ended_by = user.id
    # Phiên đã kết thúc không còn "tạm dừng"; giá trị cũ nằm trong `before` của audit (R20).
    session.paused_at = None
    session.paused_by = None


def _commit_and_publish(
    db: Session, publisher: Publisher, *sessions: MonitoringSession
) -> list[SessionOut]:
    db.commit()
    outs = []
    for s in sessions:
        db.refresh(s)
        outs.append(session_out(s))
    for out in outs:
        safe_publish(publisher, "session.updated", out)
    return outs


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
        raise _already_open("bed", bed_id)
    if _open_session_for(db, patient_id=patient_id):
        raise _already_open("patient", patient_id)

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
        raise _already_open("bed", bed_id) from exc
    record_audit(
        db,
        actor_user_id=user.id,
        action="session.start",
        entity_type="session",
        entity_id=session.id,
        after=_snapshot(session),
    )
    return _commit_and_publish(db, publisher, session)[0]


def end_session(db: Session, *, session_id: int, user: User, publisher: Publisher) -> SessionOut:
    session = _locked_open_session(db, session_id)
    before = _snapshot(session)
    _close(session, user, utcnow())
    record_audit(
        db,
        actor_user_id=user.id,
        action="session.end",
        entity_type="session",
        entity_id=session.id,
        before=before,
        after=_snapshot(session),
    )
    return _commit_and_publish(db, publisher, session)[0]


def transfer_session(
    db: Session,
    *,
    session_id: int,
    target_bed_id: int,
    reason: str,
    user: User,
    publisher: Publisher,
) -> SessionOut:
    """Chuyển giường trong một transaction (F04 R13–R15). Lỗi ở bất kỳ bước nào → rollback."""
    old = _locked_open_session(db, session_id)
    if target_bed_id == old.bed_id:
        raise validation_error("Giường chuyển đến trùng giường hiện tại", {"bed_id": target_bed_id})
    target = _locked_active_bed(db, target_bed_id)
    if _open_session_for(db, bed_id=target_bed_id):
        raise _already_open("bed", target_bed_id)

    now = utcnow()
    # Ghi trước khi _close xóa `paused_at` (R20): audit giữ trạng thái tạm dừng của phiên cũ.
    before = {
        "session_id": old.id,
        "bed_id": old.bed_id,
        "paused_at": old.paused_at.isoformat() if old.paused_at else None,
    }
    _close(old, user, now)
    new = MonitoringSession(
        bed_id=target.id,
        patient_id=old.patient_id,
        camera_id=target.camera.id if target.camera else None,
        started_at=now,
        started_by=user.id,
        previous_session_id=old.id,
        transfer_reason=reason,
    )
    try:
        db.flush()  # đóng phiên cũ trước: không vi phạm UNIQUE (patient_id) WHERE ended_at IS NULL
        db.add(new)
        db.flush()
    except IntegrityError as exc:  # yêu cầu đồng thời vào cùng giường đích
        db.rollback()
        raise _already_open("bed", target_bed_id) from exc
    record_audit(
        db,
        actor_user_id=user.id,
        action="session.transfer",
        entity_type="session",
        entity_id=new.id,
        before=before,
        after={"session_id": new.id, "bed_id": new.bed_id, "reason": reason},
    )
    # Phát phiên cũ trước (người nhà của phiên cũ hết quyền ở F36), rồi phiên mới (R17).
    return _commit_and_publish(db, publisher, old, new)[1]


def pause_session(
    db: Session, *, session_id: int, reason: str | None, user: User, publisher: Publisher
) -> SessionOut:
    session = _locked_open_session(db, session_id)
    if session.paused_at is not None:
        raise DomainError("SESSION_ALREADY_PAUSED", "Phiên theo dõi đang tạm dừng thu hình", 409)
    session.paused_at = utcnow()
    session.paused_by = user.id
    record_audit(
        db,
        actor_user_id=user.id,
        action="session.pause",
        entity_type="session",
        entity_id=session.id,
        after={"paused_at": session.paused_at.isoformat(), "reason": reason or None},
    )
    return _commit_and_publish(db, publisher, session)[0]


def resume_session(db: Session, *, session_id: int, user: User, publisher: Publisher) -> SessionOut:
    session = _locked_open_session(db, session_id)
    if session.paused_at is None:
        raise DomainError("SESSION_NOT_PAUSED", "Phiên theo dõi không tạm dừng thu hình", 409)
    before = {"paused_at": session.paused_at.isoformat(), "paused_by": session.paused_by}
    session.paused_at = None
    session.paused_by = None
    record_audit(
        db,
        actor_user_id=user.id,
        action="session.resume",
        entity_type="session",
        entity_id=session.id,
        before=before,
    )
    return _commit_and_publish(db, publisher, session)[0]


def get_session(db: Session, session_id: int) -> SessionOut:
    session = db.get(MonitoringSession, session_id)
    if session is None:
        raise not_found("Không tìm thấy phiên theo dõi")
    return session_out(session)


def session_chain(db: Session, session_id: int) -> Page[SessionChainItem]:
    """Các phiên cùng chuỗi chuyển giường, theo `started_at` (F04 R16; F22 ghép timeline)."""
    session = db.get(MonitoringSession, session_id)
    if session is None:
        raise not_found("Không tìm thấy phiên theo dõi")
    # `seen` chặn vòng lặp vô hạn nếu dữ liệu lỗi tạo chu trình previous_session_id.
    first = session
    seen = {first.id}
    while first.previous_session is not None and first.previous_session.id not in seen:
        first = first.previous_session
        seen.add(first.id)
    chain: list[MonitoringSession] = []
    seen = set()
    cur: MonitoringSession | None = first
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        chain.append(cur)
        cur = cur.next_session
    items = [
        SessionChainItem(
            id=s.id,
            bed_id=s.bed_id,
            bed_code=s.bed.code,
            started_at=s.started_at,
            ended_at=s.ended_at,
            previous_session_id=s.previous_session_id,
            transfer_reason=s.transfer_reason,
        )
        for s in chain
    ]
    return Page[SessionChainItem](items=items, total=len(items))


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
    rows = db.scalars(
        q.order_by(MonitoringSession.started_at.desc(), MonitoringSession.id.desc())
        .limit(limit)
        .offset(offset)
    )
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
