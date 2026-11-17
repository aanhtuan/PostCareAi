"""MJPEG xem trực tiếp (F07 R1, R2; ADR-0002, ADR-0005).

API chỉ chuyển tiếp bytes JPEG worker đã gửi (đã render theo `display_mode` từ F28; trước F28 là
RAW), lấy từ `LatestFrameStore` trong RAM. Không import `vision`, không ghi khung ra đĩa hay log.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from postcare.api.deps import get_frames, get_settings_dep, require_staff_query
from postcare.api.frame_buffer import LatestFrame, LatestFrameStore
from postcare.db.models import Camera
from postcare.db.types import utcnow
from postcare.domain.errors import DomainError
from postcare.settings import Settings

router = APIRouter(prefix="/cameras", tags=["live"])

BOUNDARY = "frame"


def _part(data: bytes) -> bytes:
    head = (
        f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(data)}\r\n\r\n"
    ).encode()
    return head + data + b"\r\n"


def _fresh(frame: LatestFrame | None, now: datetime, stale_after_s: float) -> bool:
    return frame is not None and (now - frame.received_at).total_seconds() <= stale_after_s


async def mjpeg_parts(
    frames: LatestFrameStore,
    camera_id: int,
    *,
    stale_after_s: float,
    poll_s: float,
    now: Callable[[], datetime] = utcnow,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AsyncIterator[bytes]:
    """Gửi mỗi khung mới đúng một lần; dừng khi hết khung hoặc khung cũ hơn `stale_after_s`."""
    last: LatestFrame | None = None
    while True:
        frame = frames.get(camera_id)
        if frame is None or not _fresh(frame, now(), stale_after_s):
            return
        if frame is not last:  # mỗi `put` tạo đối tượng mới
            last = frame
            yield _part(frame.data)
        await sleep(poll_s)


def _ensure_camera(request: Request, camera_id: int) -> None:
    db = request.app.state.session_factory()
    try:
        camera = db.get(Camera, camera_id)
        exists = camera is not None and camera.is_active
    finally:
        db.close()
    if not exists:
        raise DomainError("NOT_FOUND", "Không tìm thấy camera", 404)


@router.get(
    "/{camera_id}/stream.mjpeg",
    response_class=StreamingResponse,
    responses={200: {"content": {f"multipart/x-mixed-replace; boundary={BOUNDARY}": {}}}},
    dependencies=[Depends(require_staff_query)],
)
def stream_mjpeg(
    camera_id: int,
    request: Request,
    frames: LatestFrameStore = Depends(get_frames),
    settings: Settings = Depends(get_settings_dep),
) -> StreamingResponse:
    """`?token=<jwt>`, chỉ vai trò nhân viên. Chưa có khung hoặc khung cũ → 404, không gửi ảnh."""
    _ensure_camera(request, camera_id)
    if not _fresh(frames.get(camera_id), utcnow(), settings.stream_stale_frame_s):
        raise DomainError("NOT_FOUND", "Chưa có hình ảnh mới từ camera", 404)
    return StreamingResponse(
        mjpeg_parts(
            frames,
            camera_id,
            stale_after_s=settings.stream_stale_frame_s,
            poll_s=settings.stream_poll_interval_s,
        ),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
