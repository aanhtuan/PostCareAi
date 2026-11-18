"""F18: realtime gateway qua WebSocket (AC1–AC4, R3, R6, R7; bộ lọc theo kết nối cho F36)."""

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from postcare.api import realtime
from postcare.api.deps import create_token
from postcare.api.realtime import WsHub
from postcare.db.models import Alert, Event
from postcare.settings import Settings

Login = Callable[[str], dict[str, str]]
STAFF = ("nurse", "charge", "doctor", "admin")


async def _get_loop() -> Any:
    return asyncio.get_running_loop()


@pytest.fixture
def hub(app: Any, client: TestClient) -> WsHub:
    """Thay `InMemoryPublisher` của conftest bằng hub thật, gắn vào event loop của TestClient."""
    h = WsHub()
    h.bind_loop(client.portal.call(_get_loop))  # type: ignore[union-attr]
    app.state.hub = h
    return h


def _token(login: Login, username: str = "nurse") -> str:
    return login(username)["Authorization"].split(" ", 1)[1]


def _wait_for_clients(hub: WsHub, n: int = 1) -> None:
    for _ in range(200):
        if hub.client_count >= n:
            return
        time.sleep(0.01)
    raise AssertionError(f"WebSocket chưa đăng ký đủ {n} kết nối")


# AC1 -------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["?token=sai", "?token=", "?token=a.b.c"])
def test_ws_rejects_invalid_token(client: TestClient, query: str) -> None:
    with (
        client.websocket_connect(f"/api/v1/ws{query}") as ws,
        pytest.raises(WebSocketDisconnect) as exc,
    ):
        ws.receive_json()
    assert exc.value.code == 4401


def test_ws_rejects_missing_token(client: TestClient) -> None:
    with (
        client.websocket_connect("/api/v1/ws") as ws,
        pytest.raises(WebSocketDisconnect) as exc,
    ):
        ws.receive_json()
    assert exc.value.code == 4401


def test_ws_rejects_expired_token(client: TestClient, settings: Settings, db: Session) -> None:
    from datetime import UTC, timedelta

    from postcare.db.models import User

    nurse = db.query(User).filter_by(username="nurse").one()
    token = create_token(nurse, settings, now=datetime.now(UTC) - timedelta(hours=9))
    with (
        client.websocket_connect(f"/api/v1/ws?token={token}") as ws,
        pytest.raises(WebSocketDisconnect) as exc,
    ):
        ws.receive_json()
    assert exc.value.code == 4401


@pytest.mark.parametrize("username", STAFF)
def test_ws_accepts_valid_token(
    client: TestClient, hub: WsHub, login: Login, open_session: Any, post_event: Any, username: str
) -> None:
    """R2: mọi vai trò nhân viên nhận cùng luồng."""
    with client.websocket_connect(f"/api/v1/ws?token={_token(login, username)}") as ws:
        _wait_for_clients(hub)
        assert post_event("SIT_UP", "INFO").status_code == 201
        assert ws.receive_json()["type"] == "event.created"


def test_invalid_token_receives_nothing(
    client: TestClient, hub: WsHub, login: Login, open_session: Any, post_event: Any
) -> None:
    with client.websocket_connect(f"/api/v1/ws?token={_token(login)}") as good:
        _wait_for_clients(hub)
        with client.websocket_connect("/api/v1/ws?token=sai") as bad:
            assert post_event("BED_EXIT", "HIGH").status_code == 201
            with pytest.raises(WebSocketDisconnect) as exc:
                bad.receive_json()  # bị đóng trước khi có message nào
            assert exc.value.code == 4401
        assert good.receive_json()["type"] == "event.created"
    assert hub.client_count == 0


# R3 --------------------------------------------------------------------------


def test_message_envelope_has_type_payload_sent_at(
    client: TestClient, hub: WsHub, login: Login, open_session: Any, post_event: Any
) -> None:
    with client.websocket_connect(f"/api/v1/ws?token={_token(login)}") as ws:
        _wait_for_clients(hub)
        assert post_event("BED_EXIT", "HIGH").status_code == 201
        first, second = ws.receive_json(), ws.receive_json()
    for msg in (first, second):
        assert set(msg) == {"type", "payload", "sent_at"}
        sent_at = datetime.fromisoformat(msg["sent_at"])
        assert sent_at.utcoffset() is not None and sent_at.utcoffset().total_seconds() == 0
    assert first["type"] == "event.created"
    assert {"id", "code", "priority", "occurred_at", "bed_id"} <= set(first["payload"])
    assert second["type"] == "alert.created"
    assert second["payload"]["alert"]["event"]["id"] == first["payload"]["id"]
    assert second["payload"]["event"]["id"] == first["payload"]["id"]


# AC2 -------------------------------------------------------------------------


@pytest.mark.real_commit
def test_ws_alert_created_after_commit(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    post_event: Any,
    test_engine: Engine,
) -> None:
    """Khi client nhận message, một kết nối DB khác (commit thật) đã đọc được bản ghi."""
    with client.websocket_connect(f"/api/v1/ws?token={_token(login)}") as ws:
        _wait_for_clients(hub)
        assert post_event("BED_EXIT", "HIGH").status_code == 201
        ev, al = ws.receive_json(), ws.receive_json()
        with Session(test_engine) as other:
            assert other.get(Event, ev["payload"]["id"]) is not None
            alert = other.get(Alert, al["payload"]["alert"]["id"])
            assert alert is not None and alert.event_id == ev["payload"]["id"]


def test_no_broadcast_when_transaction_fails(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    post_event: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_commit(self: Session) -> None:
        raise OperationalError("COMMIT", {}, Exception("mất kết nối DB"))

    with client.websocket_connect(f"/api/v1/ws?token={_token(login)}") as ws:
        _wait_for_clients(hub)
        with monkeypatch.context() as m:
            m.setattr(Session, "commit", broken_commit)
            with pytest.raises(OperationalError):
                post_event("BED_EXIT", "HIGH")
        # Message đầu tiên client nhận là của sự kiện sau, không phải của transaction lỗi.
        assert post_event("SIT_UP", "INFO").status_code == 201
        msg = ws.receive_json()
    assert msg["type"] == "event.created" and msg["payload"]["code"] == "SIT_UP"


def test_duplicate_event_uid_no_second_message(
    client: TestClient, hub: WsHub, login: Login, open_session: Any, post_event: Any
) -> None:
    with client.websocket_connect(f"/api/v1/ws?token={_token(login)}") as ws:
        _wait_for_clients(hub)
        uid = str(uuid.uuid4())
        assert post_event("BED_EXIT", "HIGH", event_uid=uid).status_code == 201
        assert post_event("BED_EXIT", "HIGH", event_uid=uid).status_code == 200
        assert post_event("SIT_UP", "INFO").status_code == 201
        types = [(m["type"], m["payload"].get("code")) for m in _receive(ws, 3)]
    assert types == [
        ("event.created", "BED_EXIT"),
        ("alert.created", None),
        ("event.created", "SIT_UP"),
    ]


def _receive(ws: WebSocketTestSession, n: int) -> list[dict[str, Any]]:
    return [ws.receive_json() for _ in range(n)]


# R6 --------------------------------------------------------------------------


def test_ping_and_unknown_messages_ignored(
    client: TestClient, hub: WsHub, login: Login, open_session: Any, post_event: Any
) -> None:
    with client.websocket_connect(f"/api/v1/ws?token={_token(login)}") as ws:
        ws.send_json({"type": "ping"})
        ws.send_json({"type": "subscribe", "bed_id": 1})
        ws.send_text("không phải JSON")
        _wait_for_clients(hub)
        assert post_event("SIT_UP", "INFO").status_code == 201
        msg = ws.receive_json()  # không có trả lời cho ping, kết nối vẫn mở
    assert msg["type"] == "event.created"


# AC4 (A07) -------------------------------------------------------------------


def test_alert_created_delivered_within_1s(
    client: TestClient, hub: WsHub, login: Login, open_session: Any, post_event: Any
) -> None:
    with client.websocket_connect(f"/api/v1/ws?token={_token(login)}") as ws:
        _wait_for_clients(hub)
        t0 = time.perf_counter()
        assert post_event("BED_EXIT", "HIGH").status_code == 201
        while ws.receive_json()["type"] != "alert.created":
            pass
        elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"alert.created tới sau {elapsed:.3f} s"


# Hub: R7 (client chậm) và bộ lọc theo kết nối (F36) ---------------------------


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_slow_client_dropped_others_still_receive() -> None:
    async def scenario() -> tuple[WsHub, list[dict[str, Any]], asyncio.Queue[Any]]:
        h = WsHub()
        h.bind_loop(asyncio.get_running_loop())
        slow = h.register(1)  # không ai đọc
        fast = h.register(2)
        got: list[dict[str, Any]] = []
        for i in range(realtime.QUEUE_SIZE + 5):
            h.publish("event.created", {"i": i})
            got.append(fast.get_nowait())  # client nhanh đọc ngay
        return h, got, slow

    h, got, _ = _run(scenario())
    assert len(got) == realtime.QUEUE_SIZE + 5
    assert h.client_count == 1


def test_slow_client_closed_so_it_reconnects() -> None:
    """Client bị loại không được giữ socket mở mà im lặng: hub đóng với mã 1013 (giả định)."""

    async def scenario() -> list[dict[str, Any]]:
        h = WsHub()
        h.bind_loop(asyncio.get_running_loop())
        slow = h.register(1)
        for i in range(realtime.QUEUE_SIZE + 1):
            h.publish("event.created", {"i": i})
        items = []
        while not slow.empty():
            items.append(slow.get_nowait())
        return items

    items = _run(scenario())
    assert items == [{"type": realtime.CLOSE_MESSAGE, "code": realtime.CLOSE_TRY_AGAIN}]
    assert realtime.CLOSE_TRY_AGAIN == 1013


def test_per_connection_filter() -> None:
    """QA#31: F36 thêm bộ lọc theo từng kết nối mà không viết lại hub."""

    async def scenario() -> tuple[list[Any], list[Any]]:
        h = WsHub()
        h.bind_loop(asyncio.get_running_loop())
        everyone = h.register(1)
        only_bed_1 = h.register(2, accept=lambda m: m["payload"].get("bed_id") == 1)
        h.publish("bed.state", {"bed_id": 1})
        h.publish("bed.state", {"bed_id": 2})
        return _drain(everyone), _drain(only_bed_1)

    everyone, only = _run(scenario())
    assert [m["payload"]["bed_id"] for m in everyone] == [1, 2]
    assert [m["payload"]["bed_id"] for m in only] == [1]


def test_filter_error_does_not_block_others() -> None:
    async def scenario() -> list[Any]:
        h = WsHub()
        h.bind_loop(asyncio.get_running_loop())

        def broken(_m: dict[str, Any]) -> bool:
            raise RuntimeError("lọc lỗi")

        h.register(1, accept=broken)
        ok = h.register(2)
        h.publish("bed.state", {"bed_id": 1})
        return _drain(ok)

    got = _run(scenario())
    assert len(got) == 1  # kết nối có bộ lọc lỗi không nhận gì; kết nối khác vẫn nhận


def test_close_where_closes_matching_connections() -> None:
    async def scenario() -> tuple[list[Any], list[Any], int]:
        h = WsHub()
        h.bind_loop(asyncio.get_running_loop())
        a = h.register(1, role="FAMILY")
        b = h.register(2, role="NURSE")
        h.close_where(lambda c: c.role == "FAMILY", realtime.CLOSE_FORBIDDEN)
        h.publish("bed.state", {"bed_id": 1})
        return _drain(a), _drain(b), h.client_count

    a, b, count = _run(scenario())
    assert a == [{"type": realtime.CLOSE_MESSAGE, "code": 4403}]
    assert [m["type"] for m in b] == ["bed.state"]
    assert count == 1


def test_close_where_predicate_error_does_not_stop_others() -> None:
    async def scenario() -> tuple[list[Any], list[Any], int]:
        h = WsHub()
        h.bind_loop(asyncio.get_running_loop())
        bad = h.register(1)
        good = h.register(2)

        def pred(c: realtime.Connection) -> bool:
            if c.user_id == 1:
                raise RuntimeError("điều kiện lỗi")
            return True

        h.close_where(pred, realtime.CLOSE_FORBIDDEN)
        return _drain(bad), _drain(good), h.client_count

    bad, good, count = _run(scenario())
    assert bad == []  # điều kiện lỗi: giữ nguyên kết nối đó
    assert good == [{"type": realtime.CLOSE_MESSAGE, "code": 4403}]
    assert count == 1


def test_ws_slow_client_closed_1013(
    client: TestClient, hub: WsHub, login: Login, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R7 qua WebSocket thật: hàng đợi đầy trong một nhịp event loop → client nhận mã đóng 1013."""
    monkeypatch.setattr(realtime, "QUEUE_SIZE", 2)

    async def burst() -> None:  # chạy trong loop: sender chưa kịp lấy message nào
        for i in range(5):
            hub.publish("bed.state", {"bed_id": 1, "i": i})

    with client.websocket_connect(f"/api/v1/ws?token={_token(login)}") as ws:
        _wait_for_clients(hub)
        client.portal.call(burst)  # type: ignore[union-attr]
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == realtime.CLOSE_TRY_AGAIN
    assert hub.client_count == 0


def _drain(q: asyncio.Queue[Any]) -> list[Any]:
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    return items


# Log: `?token=` của WS không vào log (F07 log_redaction) ------------------------


def test_ws_token_redacted_in_server_log(app: Any, caplog: pytest.LogCaptureFixture) -> None:
    """uvicorn ghi "WebSocket <path>?token=…" qua logger `uvicorn.error`, không qua access log."""
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    logging.getLogger("uvicorn.error").info(
        '%s - "WebSocket %s" [accepted]', "127.0.0.1:50000", "/api/v1/ws?token=abc.def.ghi"
    )
    assert "abc.def.ghi" not in caplog.text
    assert "/api/v1/ws?token=***" in caplog.text
