"""Local, opt-in video demo. Only administrators may create records or launch processes."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from postcare.api.deps import get_publisher, get_session, require_admin, require_staff
from postcare.api.video_demo import DemoRunOut, DemoSetupOut, DemoStartIn, DemoStatusOut, DemoStopIn
from postcare.db.models import User
from postcare.domain.notifications import Publisher

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("", response_model=DemoStatusOut, dependencies=[Depends(require_staff)])
def status(
    request: Request,
    db: Session = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> DemoStatusOut:
    return request.app.state.video_demo.status(db, publisher)


@router.post("/prepare", response_model=DemoSetupOut)
def prepare(
    request: Request, db: Session = Depends(get_session), user: User = Depends(require_admin)
) -> DemoSetupOut:
    return request.app.state.video_demo.prepare(db, user)


@router.post("/start", response_model=DemoRunOut, status_code=201)
def start(
    body: DemoStartIn,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin),
    publisher: Publisher = Depends(get_publisher),
) -> DemoRunOut:
    return request.app.state.video_demo.start(db, publisher, user)


@router.post("/stop", response_model=DemoRunOut)
def stop(
    body: DemoStopIn,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin),
    publisher: Publisher = Depends(get_publisher),
) -> DemoRunOut:
    return request.app.state.video_demo.stop(db, publisher, user, body.session_id)
