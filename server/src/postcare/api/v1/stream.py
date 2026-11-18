"""MJPEG xem trực tiếp (F07 R1, R2; ADR-0002, ADR-0005).

API chỉ chuyển tiếp bytes JPEG worker đã gửi (đã render theo `display_mode` từ F28; trước F28 là
RAW), lấy từ `LatestFrameStore` trong RAM. Không import `vision`, không ghi khung ra đĩa hay log.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from postcare.api.deps import (
    get_frames,
    get_settings_dep,
    require_staff_query,
    staff_from_token,
)
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
    still_valid: Callable[[], Awaitable[bool]] | None = None,
    revalidate_s: float = 5.0,
) -> AsyncIterator[bytes]:
    """Gửi mỗi khung mới đúng một lần; dừng khi hết khung hoặc khung cũ hơn `stale_after_s`.

    Mỗi `revalidate_s` gọi `still_valid()`: người xem bị khóa, đặt lại mật khẩu hoặc đổi vai trò
    (F35) → dừng stream.
    """
    last: LatestFrame | None = None
    last_check = now()
    while True:
        if still_valid is not None and (now() - last_check).total_seconds() >= revalidate_s:
            last_check = now()
            if not await still_valid():
                return
        frame = frames.get(camera_id)
        if frame is None or not _fresh(frame, now(), stale_after_s):
            return
        if frame is not last:  # mỗi `put` tạo đối tượng mới
            last = frame
            yield _part(frame.data)
        await sleep(poll_s)


def _viewer_checker(request: Request, token: str) -> Callable[[], Awaitable[bool]]:
    """Kiểm tra lại token + tài khoản trong thread (DB đồng bộ), mở/đóng session mỗi lần."""
    app = request.app

    def _check() -> bool:
        db = app.state.session_factory()
        try:
            staff_from_token(db, token, app.state.settings)
            return True
        except DomainError:
            return False
        finally:
            db.close()

    async def _still_valid() -> bool:
        return await asyncio.to_thread(_check)

    return _still_valid


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
            still_valid=_viewer_checker(request, request.query_params.get("token", "")),
            revalidate_s=settings.stream_revalidate_s,
        ),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
