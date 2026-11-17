from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from postcare.api.deps import get_publisher, require_staff, require_writer
from postcare.api.deps import get_session as db_session
from postcare.db.models import User
from postcare.domain import sessions as svc
from postcare.domain import timeline as tl
from postcare.domain.dto import Page, SessionCreate, SessionOut, TimelineItemOut
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
