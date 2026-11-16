"""API nội bộ cho worker / giả lập (ADR-0002). Xác thực bằng header `X-Worker-Token`."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from postcare.api.deps import get_db, get_publisher, get_store, require_worker
from postcare.domain import cameras as svc
from postcare.domain.dto import (
    BedStateIn,
    BedStateOut,
    CameraConfigOut,
    EventIn,
    EventIngestOut,
    HeartbeatIn,
    HeartbeatOut,
)
from postcare.domain.events import ingest_event
from postcare.domain.notifications import Publisher
from postcare.domain.runtime import RuntimeStore

router = APIRouter(prefix="/internal/v1", tags=["internal"], dependencies=[Depends(require_worker)])


@router.get("/cameras/{camera_id}/config", response_model=CameraConfigOut)
def config(camera_id: int, db: Session = Depends(get_db)) -> CameraConfigOut:
    return svc.camera_config(db, camera_id)


@router.post("/cameras/{camera_id}/heartbeat", response_model=HeartbeatOut)
def heartbeat(
    camera_id: int,
    body: HeartbeatIn,
    db: Session = Depends(get_db),
    store: RuntimeStore = Depends(get_store),
    publisher: Publisher = Depends(get_publisher),
) -> HeartbeatOut:
    return svc.heartbeat(db, camera_id, body, store, publisher)


@router.post("/cameras/{camera_id}/state", response_model=BedStateOut)
def state(
    camera_id: int,
    body: BedStateIn,
    db: Session = Depends(get_db),
    store: RuntimeStore = Depends(get_store),
    publisher: Publisher = Depends(get_publisher),
) -> BedStateOut:
    return svc.update_bed_state(db, camera_id, body, store, publisher)


@router.post("/events", response_model=EventIngestOut, status_code=201)
def events(
    body: EventIn,
    response: Response,
    db: Session = Depends(get_db),
    publisher: Publisher = Depends(get_publisher),
) -> EventIngestOut:
    out, created = ingest_event(db, body, publisher)
    if not created:
        response.status_code = 200
    return out
