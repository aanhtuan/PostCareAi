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
        self.disconnected: list[int] = []

    def disconnect_user(self, user_id: int, code: int = 4401) -> None:
        self.disconnected.append(user_id)

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


def disconnect_user(publisher: Publisher, user_id: int, code: int) -> None:
    """Đóng mọi kết nối realtime của một tài khoản (F35 R7: khóa tài khoản). Gọi SAU commit.

    Publisher không có kết nối (worker, test) thì bỏ qua.
    """
    fn = getattr(publisher, "disconnect_user", None)
    if fn is None:
        return
    try:
        fn(user_id, code)
    except Exception:
        logger.exception("Không đóng được kết nối realtime của người dùng %s", user_id)
