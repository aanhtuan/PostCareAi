"""Realtime gateway (F18): WsHub cài `Publisher`; route `GET /api/v1/ws?token=`.

Endpoint REST chạy trong thread pool, nên `publish()` chuyển message về event loop
bằng `call_soon_threadsafe`. Mỗi kết nối có hàng đợi riêng; client chậm bị đóng (1013) để tự
kết nối lại và làm mới dữ liệu, không chặn ai.

Mỗi kết nối là một `Connection` (user, vai trò, bộ lọc `accept`). F36 thêm luồng `FAMILY` bằng
cách đăng ký với bộ lọc theo quyền xem và đóng 4403 bằng `close_where`, không phải viết lại hub
(QA#31).
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
from postcare.domain.errors import DomainError

logger = logging.getLogger(__name__)

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403  # FAMILY trước F36 (F35 R2; api-conventions.md)
CLOSE_TRY_AGAIN = 1013  # client chậm bị loại: kết nối lại và làm mới (F18 R7, giả định)
CLOSE_MESSAGE = "__close__"  # message nội bộ trong hàng đợi: đóng kết nối, không gửi cho client
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
            if conn.accept is not None:
                try:
                    if not conn.accept(message):
                        continue
                except Exception:
                    logger.exception("Bộ lọc kết nối WebSocket lỗi; bỏ qua message cho kết nối này")
                    continue
            try:
                conn.queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Đóng client WebSocket gửi chậm (%s)", CLOSE_TRY_AGAIN)
                self._close(conn, CLOSE_TRY_AGAIN)

    def close_where(self, predicate: Callable[[Connection], bool], code: int) -> None:
        """Đóng mọi kết nối thỏa `predicate` với mã `code`. Gọi SAU commit."""
        self._call_in_loop(self._close_matching, predicate, code)

    def disconnect_user(self, user_id: int, code: int = CLOSE_UNAUTHORIZED) -> None:
        """Đóng kết nối của user: 4401 (khóa, đặt lại mật khẩu), 4403 (không còn là nhân viên)."""
        self.close_where(lambda c: c.user_id == user_id, code)

    def _close_matching(self, predicate: Callable[[Connection], bool], code: int) -> None:
        for conn in list(self._conns.values()):
            if predicate(conn):
                self._close(conn, code)

    def _close(self, conn: Connection, code: int) -> None:
        self._conns.pop(conn.queue, None)
        while not conn.queue.empty():  # bỏ message chưa gửi: không gửi thêm gì sau khi đóng
            conn.queue.get_nowait()
        conn.queue.put_nowait({"type": CLOSE_MESSAGE, "code": code})

    def register(
        self, user_id: int | None = None, *, role: str | None = None, accept: Accept | None = None
    ) -> asyncio.Queue[Message]:
        queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._conns[queue] = Connection(queue, user_id, role, accept)
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


@router.websocket("/api/v1/ws")
async def websocket_endpoint(ws: WebSocket, token: str | None = None) -> None:
    app = ws.app
    await ws.accept()
    db = app.state.session_factory()
    try:
        user = user_from_token(db, token or "", app.state.settings)
        user_id, role = user.id, user.role
    except DomainError:
        await ws.close(code=CLOSE_UNAUTHORIZED)
        return
    finally:
        db.close()
    if role not in STAFF_ROLES:
        # Luồng nhân viên chỉ dành cho vai trò nhân viên; FAMILY có luồng riêng ở F36.
        await ws.close(code=CLOSE_FORBIDDEN)
        return

    hub: WsHub = app.state.hub
    queue = hub.register(user_id, role=role.value)
    tasks = [asyncio.create_task(_sender(ws, queue)), asyncio.create_task(_receiver(ws))]
    try:
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                await t
    finally:
        hub.unregister(queue)
