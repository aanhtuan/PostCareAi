"""Publisher: domain gọi SAU KHI commit DB (HS §4.2). Bản WebSocket nằm ở `api.realtime`."""

import logging
from typing import Any, Protocol

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Publisher(Protocol):
    def publish(self, type_: str, payload: dict[str, Any]) -> None: ...


class InMemoryPublisher:
    """Ghi nhận thông báo trong RAM, dùng cho test."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, dict[str, Any]]] = []

    def publish(self, type_: str, payload: dict[str, Any]) -> None:
        self.messages.append((type_, payload))

    def types(self) -> list[str]:
        return [t for t, _ in self.messages]


def safe_publish(publisher: Publisher, type_: str, payload: BaseModel | dict[str, Any]) -> None:
    """Publisher lỗi không được làm hỏng dữ liệu đã lưu (F17 R15)."""
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    try:
        publisher.publish(type_, data)
    except Exception:
        logger.exception("Không phát được thông báo %s", type_)
