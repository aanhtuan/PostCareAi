"""Realtime gateway (F18): WsHub cài `Publisher`; route `GET /api/v1/ws?token=`.

Endpoint REST chạy trong thread pool, nên `publish()` chuyển message về event loop
bằng `call_soon_threadsafe`. Mỗi client có hàng đợi riêng; client chậm bị loại, không chặn ai.
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from postcare.api.deps import user_from_token
from postcare.domain.errors import DomainError

logger = logging.getLogger(__name__)

CLOSE_UNAUTHORIZED = 4401
QUEUE_SIZE = 200

router = APIRouter()


class WsHub:
    def __init__(self) -> None:
        self._clients: set[asyncio.Queue[dict[str, Any]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def publish(self, type_: str, payload: dict[str, Any]) -> None:
        message = {"type": type_, "payload": payload, "sent_at": datetime.now(UTC).isoformat()}
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self._fanout(message)
        else:
            loop.call_soon_threadsafe(self._fanout, message)

    def _fanout(self, message: dict[str, Any]) -> None:
        for queue in list(self._clients):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Loại client WebSocket gửi chậm")
                self._clients.discard(queue)

    def register(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._clients.add(queue)
        return queue

    def unregister(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._clients.discard(queue)


async def _sender(ws: WebSocket, queue: asyncio.Queue[dict[str, Any]]) -> None:
    while True:
        message = await queue.get()
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
        user_from_token(db, token or "", app.state.settings)
    except DomainError:
        await ws.close(code=CLOSE_UNAUTHORIZED)
        return
    finally:
        db.close()

    hub: WsHub = app.state.hub
    queue = hub.register()
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
