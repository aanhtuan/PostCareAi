from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from postcare.api.deps import get_publisher, get_session, require_staff, require_writer
from postcare.db.models import User
from postcare.domain import alerts as svc
from postcare.domain.dto import AlertOut, OutcomeIn, Page, ResolveIn
from postcare.domain.notifications import Publisher
from postcare.schemas.enums import AlertStatus, Priority

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=Page[AlertOut], dependencies=[Depends(require_staff)])
def list_alerts(
    status: list[AlertStatus] | None = Query(None),
    bed_id: int | None = None,
    priority: list[Priority] | None = Query(None),
    from_: AwareDatetime | None = Query(None, alias="from"),
    to: AwareDatetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
) -> Page[AlertOut]:
    return svc.list_alerts(
        db,
        statuses=status,
        bed_id=bed_id,
        priorities=priority,
        from_=from_,
        to=to,
        limit=limit,
        offset=offset,
    )


@router.get("/{alert_id}", response_model=AlertOut, dependencies=[Depends(require_staff)])
def get_alert(alert_id: int, db: Session = Depends(get_session)) -> AlertOut:
    return svc.get_alert(db, alert_id)


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(
    alert_id: int,
    user: User = Depends(require_writer),
    db: Session = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> AlertOut:
    return svc.acknowledge(db, alert_id, user, publisher)


@router.post("/{alert_id}/outcome", response_model=AlertOut)
def outcome(
    alert_id: int,
    body: OutcomeIn,
    user: User = Depends(require_writer),
    db: Session = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> AlertOut:
    return svc.set_outcome(db, alert_id, body.outcome, body.note, user, publisher)


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve(
    alert_id: int,
    body: ResolveIn | None = None,
    user: User = Depends(require_writer),
    db: Session = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> AlertOut:
    return svc.resolve(db, alert_id, body.note if body else None, user, publisher)
