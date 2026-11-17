from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from postcare.api.deps import get_publisher, require_staff, require_writer
from postcare.api.deps import get_session as db_session
from postcare.db.models import User
from postcare.domain import sessions as svc
from postcare.domain import timeline as tl
from postcare.domain.dto import (
    Page,
    SessionChainItem,
    SessionCreate,
    SessionOut,
    SessionPause,
    SessionTransfer,
    TimelineItemOut,
)
from postcare.domain.notifications import Publisher
from postcare.schemas.enums import Priority

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=Page[SessionOut], dependencies=[Depends(require_staff)])
def list_sessions(
    active: bool | None = None,
    bed_id: int | None = None,
    patient_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
) -> Page[SessionOut]:
    return svc.list_sessions(
        db, active=active, bed_id=bed_id, patient_id=patient_id, limit=limit, offset=offset
    )


@router.post("", response_model=SessionOut, status_code=201)
def start_session(
    body: SessionCreate,
    user: User = Depends(require_writer),
    db: Session = Depends(db_session),
    publisher: Publisher = Depends(get_publisher),
) -> SessionOut:
    return svc.start_session(
        db, bed_id=body.bed_id, patient_id=body.patient_id, user=user, publisher=publisher
    )


@router.get("/{session_id}", response_model=SessionOut, dependencies=[Depends(require_staff)])
def get_session(session_id: int, db: Session = Depends(db_session)) -> SessionOut:
    return svc.get_session(db, session_id)


@router.post("/{session_id}/end", response_model=SessionOut)
def end_session(
    session_id: int,
    user: User = Depends(require_writer),
    db: Session = Depends(db_session),
    publisher: Publisher = Depends(get_publisher),
) -> SessionOut:
    return svc.end_session(db, session_id=session_id, user=user, publisher=publisher)


@router.post("/{session_id}/transfer", response_model=SessionOut, status_code=201)
def transfer_session(
    session_id: int,
    body: SessionTransfer,
    user: User = Depends(require_writer),
    db: Session = Depends(db_session),
    publisher: Publisher = Depends(get_publisher),
) -> SessionOut:
    """Chuyển giường: kết thúc phiên này và mở phiên mới ở giường đích (F04 R12–R17)."""
    return svc.transfer_session(
        db,
        session_id=session_id,
        target_bed_id=body.target_bed_id,
        reason=body.reason,
        user=user,
        publisher=publisher,
    )


@router.get(
    "/{session_id}/chain",
    response_model=Page[SessionChainItem],
    dependencies=[Depends(require_staff)],
)
def session_chain(session_id: int, db: Session = Depends(db_session)) -> Page[SessionChainItem]:
    return svc.session_chain(db, session_id)


@router.post("/{session_id}/pause", response_model=SessionOut)
def pause_session(
    session_id: int,
    body: SessionPause | None = None,
    user: User = Depends(require_writer),
    db: Session = Depends(db_session),
    publisher: Publisher = Depends(get_publisher),
) -> SessionOut:
    """Tạm dừng thu hình của phiên (F04 R19–R22; F36 R15–R18)."""
    reason = body.reason if body else None
    return svc.pause_session(
        db, session_id=session_id, reason=reason, user=user, publisher=publisher
    )


@router.post("/{session_id}/resume", response_model=SessionOut)
def resume_session(
    session_id: int,
    user: User = Depends(require_writer),
    db: Session = Depends(db_session),
    publisher: Publisher = Depends(get_publisher),
) -> SessionOut:
    return svc.resume_session(db, session_id=session_id, user=user, publisher=publisher)


@router.get(
    "/{session_id}/timeline",
    response_model=Page[TimelineItemOut],
    dependencies=[Depends(require_staff)],
)
def session_timeline(
    session_id: int,
    priority: list[Priority] | None = Query(None),
    limit: int = Query(200, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
) -> Page[TimelineItemOut]:
    return tl.session_timeline(db, session_id, priority, limit, offset)
