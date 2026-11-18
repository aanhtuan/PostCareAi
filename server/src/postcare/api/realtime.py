"""Realtime gateway (F18): WsHub cài `Publisher`; route `GET /api/v1/ws?token=`.

Endpoint REST chạy trong thread pool, nên `publish()` chuyển message về event loop
bằng `call_soon_threadsafe`. Mỗi kết nối có hàng đợi riêng; client chậm bị đóng (1013) để tự
kết nối lại và làm mới dữ liệu, không chặn ai.

Mỗi kết nối là một `Connection` (user, vai trò, bộ lọc `accept`, bản chiếu `projection`).
Kết nối nhân viên có bộ lọc bỏ message nội bộ của người nhà. Kết nối `FAMILY` (F36) có
`FamilyProjection`: mỗi message của hub được chiếu thành `family.*` của đúng grant của kết nối đó;
hết grant cuối → đóng 4403 (QA#31).
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from postcare.api.deps import STAFF_ROLES, user_from_token
from postcare.api.family_stream import (
    CLOSE_MESSAGE,
    EXPIRY_CHECK_S,
    FamilyProjection,
    GrantStream,
    staff_accept,
)
from postcare.db.models import User
from postcare.domain.errors import DomainError
from postcare.domain.family_access import active_grants_for_user, family_state, record_view
from postcare.schemas.enums import FamilyAccessEndReason, UserRole

logger = logging.getLogger(__name__)

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403  # không (còn) quyền vào luồng: FAMILY hết grant, rời vai trò (F35, F36)
CLOSE_TRY_AGAIN = 1013  # client chậm bị loại: kết nối lại và làm mới (F18 R7, giả định)
QUEUE_SIZE = 200

Message = dict[str, Any]
Accept = Callable[[Message], bool]

router = APIRouter()


@dataclass(eq=False)
class Connection:
    queue: "asyncio.Queue[Message]"
    user_id: int | None
    role: str | None
    accept: Accept | None = None
    projection: FamilyProjection | None = None


class WsHub:
    def __init__(self) -> None:
        self._conns: dict[asyncio.Queue[Message], Connection] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def client_count(self) -> int:
        return len(self._conns)

    def _call_in_loop(self, fn: Callable[..., None], *args: Any) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            fn(*args)
        else:
            loop.call_soon_threadsafe(fn, *args)

    def publish(self, type_: str, payload: dict[str, Any]) -> None:
        message = {"type": type_, "payload": payload, "sent_at": datetime.now(UTC).isoformat()}
        self._call_in_loop(self._fanout, message)

    def _fanout(self, message: Message) -> None:
        for conn in list(self._conns.values()):
            if conn.projection is not None:
                try:
                    out = conn.projection.project(message)
                except Exception:
                    logger.exception("Bản chiếu người nhà lỗi; bỏ qua message cho kết nối này")
                    continue
                self._deliver(conn, out)
                continue
            if conn.accept is not None:
                try:
                    if not conn.accept(message):
                        continue
                except Exception:
                    logger.exception("Bộ lọc kết nối WebSocket lỗi; bỏ qua message cho kết nối này")
                    continue
            self._deliver(conn, [message])

    def _deliver(self, conn: Connection, messages: list[Message]) -> None:
        """Đưa message vào hàng đợi; message đóng (`CLOSE_MESSAGE`) đóng kết nối sau các message
        đứng trước nó (ví dụ `family.access_ended` rồi 4403)."""
        for message in messages:
            if message.get("type") == CLOSE_MESSAGE:
                self._close(conn, int(message["code"]), drain=False)
                return
            try:
                conn.queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Đóng client WebSocket gửi chậm (%s)", CLOSE_TRY_AGAIN)
                self._close(conn, CLOSE_TRY_AGAIN)
                return

    def deliver_to(self, queue: asyncio.Queue[Message], messages: list[Message]) -> None:
        """Gửi message cho một kết nối (gọi trong event loop của hub)."""
        conn = self._conns.get(queue)
        if conn is not None and messages:
            self._deliver(conn, messages)

    def is_registered(self, queue: asyncio.Queue[Message]) -> bool:
        return queue in self._conns

    def close_where(self, predicate: Callable[[Connection], bool], code: int) -> None:
        """Đóng mọi kết nối thỏa `predicate` với mã `code`. Gọi SAU commit."""
        self._call_in_loop(self._close_matching, predicate, code)

    def disconnect_user(self, user_id: int, code: int = CLOSE_UNAUTHORIZED) -> None:
        """Đóng kết nối của user: 4401 (khóa, đặt lại mật khẩu), 4403 (không còn là nhân viên)."""
        self.close_where(lambda c: c.user_id == user_id, code)

    def _close_matching(self, predicate: Callable[[Connection], bool], code: int) -> None:
        for conn in list(self._conns.values()):
            try:
                matched = predicate(conn)
            except Exception:
                logger.exception("Điều kiện đóng kết nối WebSocket lỗi; bỏ qua kết nối này")
                continue
            if not matched:
                continue
            if conn.projection is not None:
                # Người nhà bị khóa / đổi vai trò: báo hết quyền từng grant rồi mới đóng (F36 R14).
                ended = conn.projection.end_all(FamilyAccessEndReason.ACCOUNT_LOCKED)
                self._deliver(conn, [*ended, {"type": CLOSE_MESSAGE, "code": code}])
            else:
                self._close(conn, code)

    def _close(self, conn: Connection, code: int, *, drain: bool = True) -> None:
        self._conns.pop(conn.queue, None)
        # Mặc định bỏ message chưa gửi; `drain=False` giữ chúng (gửi `access_ended` trước 4403).
        while drain and not conn.queue.empty():
            conn.queue.get_nowait()
        if conn.queue.full():
            conn.queue.get_nowait()
        conn.queue.put_nowait({"type": CLOSE_MESSAGE, "code": code})

    def register(
        self,
        user_id: int | None = None,
        *,
        role: str | None = None,
        accept: Accept | None = None,
        projection: FamilyProjection | None = None,
    ) -> asyncio.Queue[Message]:
        queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._conns[queue] = Connection(queue, user_id, role, accept, projection)
        return queue

    def unregister(self, queue: asyncio.Queue[Message]) -> None:
        self._conns.pop(queue, None)


async def _sender(ws: WebSocket, queue: asyncio.Queue[Message]) -> None:
    while True:
        message = await queue.get()
        if message.get("type") == CLOSE_MESSAGE:
            await ws.close(code=message["code"])
            return
        await ws.send_json(message)


async def _receiver(ws: WebSocket) -> None:
    # Client chỉ gửi {"type":"ping"}; mọi message khác bỏ qua.
    while True:
        await ws.receive_text()


async def _watch_expiry(
    hub: WsHub,
    queue: asyncio.Queue[Message],
    projection: FamilyProjection,
    clock: Callable[[], datetime],
) -> None:
    """Quyền hết hạn giữa chừng (F36 R14): kiểm tra mỗi `EXPIRY_CHECK_S` giây."""
    while hub.is_registered(queue):
        await asyncio.sleep(EXPIRY_CHECK_S)
        hub.deliver_to(queue, projection.expire(clock()))
    await asyncio.Event().wait()  # đã đóng: chờ `_sender` gửi lệnh đóng rồi bị hủy


def _family_projection(app: Any, db: Any, user: User) -> FamilyProjection | None:
    """Grant đang hiệu lực của người nhà → bản chiếu; không có grant → None (đóng 4403)."""
    grants = active_grants_for_user(db, user, app.state.clock())
    if not grants:
        return None
    streams = []
    for g in grants:
        paused = g.session.paused_at is not None
        state = family_state(g, app.state.store, paused)
        streams.append(
            GrantStream(
                grant_id=g.id,
                session_id=g.session_id,
                bed_id=g.session.bed_id,
                share_level=g.share_level,
                expires_at=g.expires_at,
                capture_paused=paused,
                state=state.model_dump(mode="json", exclude={"capture_paused"}) if state else None,
            )
        )
        record_view(db, user, g, "ws")  # mỗi lần mở kết nối, không theo message (R6)
    db.commit()
    return FamilyProjection(streams)


async def _run(ws: WebSocket, hub: WsHub, queue: asyncio.Queue[Message], *extra: Any) -> None:
    tasks = [
        asyncio.create_task(_sender(ws, queue)),
        asyncio.create_task(_receiver(ws)),
        *(asyncio.create_task(c) for c in extra),
    ]
    try:
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                await t
    finally:
        hub.unregister(queue)


@router.websocket("/api/v1/ws")
async def websocket_endpoint(ws: WebSocket, token: str | None = None) -> None:
    app = ws.app
    await ws.accept()
    db = app.state.session_factory()
    projection: FamilyProjection | None = None
    try:
        user = user_from_token(db, token or "", app.state.settings)
        user_id, role = user.id, user.role
        if role is UserRole.FAMILY:
            projection = _family_projection(app, db, user)
    except DomainError:
        await ws.close(code=CLOSE_UNAUTHORIZED)
        return
    finally:
        db.close()

    hub: WsHub = app.state.hub
    if role is UserRole.FAMILY:
        if projection is None:  # không có quyền xem nào đang hiệu lực (F36 R12)
            await ws.close(code=CLOSE_FORBIDDEN)
            return
        queue = hub.register(user_id, role=role.value, projection=projection)
        hub.deliver_to(queue, projection.initial())
        await _run(ws, hub, queue, _watch_expiry(hub, queue, projection, app.state.clock))
        return
    if role not in STAFF_ROLES:
        await ws.close(code=CLOSE_FORBIDDEN)
        return
    queue = hub.register(user_id, role=role.value, accept=staff_accept)
    await _run(ws, hub, queue)
