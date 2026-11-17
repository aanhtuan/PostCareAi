"""API nội bộ cho worker / giả lập (ADR-0002). Xác thực bằng header `X-Worker-Token`."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from postcare.api.deps import (
    get_frames,
    get_publisher,
    get_session,
    get_settings_dep,
    get_store,
    require_worker,
)
from postcare.api.frame_buffer import LatestFrameStore
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
from postcare.domain.errors import validation_error
from postcare.domain.events import ingest_event
from postcare.domain.notifications import Publisher
from postcare.domain.runtime import RuntimeStore
from postcare.settings import Settings

JPEG_MAGIC = b"\xff\xd8"  # SOI: mọi file JPEG bắt đầu bằng FF D8

router = APIRouter(prefix="/internal/v1", tags=["internal"], dependencies=[Depends(require_worker)])


@router.get("/cameras/{camera_id}/config", response_model=CameraConfigOut)
def config(camera_id: int, db: Session = Depends(get_session)) -> CameraConfigOut:
    return svc.camera_config(db, camera_id)


@router.post("/cameras/{camera_id}/heartbeat", response_model=HeartbeatOut)
def heartbeat(
    camera_id: int,
    body: HeartbeatIn,
    db: Session = Depends(get_session),
    store: RuntimeStore = Depends(get_store),
    publisher: Publisher = Depends(get_publisher),
) -> HeartbeatOut:
    return svc.heartbeat(db, camera_id, body, store, publisher)


@router.post("/cameras/{camera_id}/state", response_model=BedStateOut)
def state(
    camera_id: int,
    body: BedStateIn,
    db: Session = Depends(get_session),
    store: RuntimeStore = Depends(get_store),
    publisher: Publisher = Depends(get_publisher),
) -> BedStateOut:
    return svc.update_bed_state(db, camera_id, body, store, publisher)


@router.post("/events", response_model=EventIngestOut, status_code=201)
def events(
    body: EventIn,
    response: Response,
    db: Session = Depends(get_session),
    publisher: Publisher = Depends(get_publisher),
) -> EventIngestOut:
    out, created = ingest_event(db, body, publisher)
    if not created:
        response.status_code = 200
    return out


@router.post("/cameras/{camera_id}/frame", status_code=204, response_class=Response)
async def frame(
    camera_id: int,
    request: Request,
    db: Session = Depends(get_session),
    frames: LatestFrameStore = Depends(get_frames),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    """Khung JPEG xem trực tiếp (F06 R7, R8): chỉ giữ khung mới nhất trong RAM, không ghi đĩa."""
    ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype != "image/jpeg":
        raise validation_error("Khung hình phải là image/jpeg", {"content_type": ctype})
    limit = settings.frame_max_bytes
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise validation_error("Khung hình quá lớn", {"max_bytes": limit})
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limit:
            raise validation_error("Khung hình quá lớn", {"max_bytes": limit})
    if not data:
        raise validation_error("Khung hình rỗng")
    if not data.startswith(JPEG_MAGIC):
        raise validation_error("Khung hình không phải JPEG")
    await run_in_threadpool(svc.ensure_worker_camera, db, camera_id)
    frames.put(camera_id, bytes(data))
    return Response(status_code=204)
