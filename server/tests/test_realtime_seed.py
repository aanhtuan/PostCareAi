"""F18: WebSocket từ chối token sai (4401) và nhận thông báo; seed + giả lập chạy được."""

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from postcare.api.realtime import WsHub
from postcare.cli.simulator import SCENARIOS, Simulator
from postcare.domain.seed import seed_history
from postcare.schemas.events import EVENT_CATALOG
from tests.conftest import WORKER_TOKEN


def test_ws_rejects_bad_token(client: TestClient) -> None:
    with (
        client.websocket_connect("/api/v1/ws?token=sai") as ws,
        pytest.raises(WebSocketDisconnect) as exc,
    ):
        ws.receive_json()
    assert exc.value.code == 4401


def test_ws_receives_event_after_commit(
    app: Any,
    client: TestClient,
    login,
    open_session,
    post_event,
) -> None:
    hub = WsHub()
    hub.bind_loop(client.portal.call(_get_loop))  # type: ignore[union-attr]
    app.state.hub = hub
    token = login("doctor")["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        ws.send_json({"type": "ping"})
        _wait_for_clients(hub)
        assert post_event("BED_EXIT", "HIGH").status_code == 201
        first, second = ws.receive_json(), ws.receive_json()
    assert first["type"] == "event.created" and first["payload"]["code"] == "BED_EXIT"
    assert second["type"] == "alert.created"
    assert second["payload"]["alert"]["status"] == "PENDING"


async def _get_loop() -> Any:
    import asyncio

    return asyncio.get_running_loop()


def _wait_for_clients(hub: WsHub) -> None:
    import time

    for _ in range(100):
        if hub.client_count:
            return
        time.sleep(0.02)
    raise AssertionError("WebSocket chưa đăng ký")


def test_seed_history_builds_dashboard_like_hs_figure_3(
    app: Any,
    client: TestClient,
    login,
) -> None:
    from postcare.db.types import utcnow

    with app.state.session_factory() as db:
        seed_history(db, utcnow())
    beds = {
        b["code"]: b for b in client.get("/api/v1/overview", headers=login("nurse")).json()["beds"]
    }
    assert beds["A01"]["pending_alert_count"] == 0
    assert beds["A02"]["acknowledged_alert_count"] == 1 and beds["A02"]["pending_alert_count"] == 0
    assert beds["A03"]["pending_alert_count"] == 2 and beds["A03"]["max_open_priority"] == "HIGH"


def test_simulator_bed_exit_scenario_against_app(
    app: Any,
    client: TestClient,
    login,
    open_session,
) -> None:
    """Chạy kịch bản demo chính qua TestClient (không ngủ thật)."""
    from datetime import timedelta

    from postcare.db.models import MonitoringSession

    with app.state.session_factory() as db:  # sự kiện lùi 0,5 s phải nằm trong phiên
        s = db.get(MonitoringSession, open_session["id"])
        s.started_at = s.started_at - timedelta(minutes=1)
        db.commit()

    class _Transport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            r = client.request(
                request.method,
                request.url.path,
                content=request.content,
                headers=dict(request.headers),
            )
            return httpx.Response(r.status_code, content=r.content, headers=r.headers)

    logs: list[str] = []
    sim = Simulator(
        base_url="http://test",
        worker_token=WORKER_TOKEN,
        camera_id=1,
        log=logs.append,
        transport=_Transport(),
        sleep=lambda _s: None,
    )
    assert sim.config()["active_session_id"] == open_session["id"]
    sim.heartbeat_once()
    sim.run("bed-exit", speed=1, away_s=1, repeat=1, gap_s=0)
    sim.stop()

    nurse = login("nurse")
    codes = [e["code"] for e in client.get("/api/v1/events", headers=nurse).json()["items"]]
    assert codes[::-1] == ["SIT_UP", "BED_EDGE", "STAND_UP", "BED_EXIT", "RETURN_TO_BED"]
    alerts = client.get("/api/v1/alerts?priority=HIGH&status=PENDING", headers=nurse).json()
    assert alerts["items"][0]["event"]["code"] == "BED_EXIT"
    state = client.get("/api/v1/overview", headers=nurse).json()["beds"][0]["state"]
    assert state["body_state"] == "LYING"


def test_all_scenarios_use_catalog_codes() -> None:
    for name, build in SCENARIOS.items():
        for step in build(1.0):
            if step.event is not None:
                assert step.event in EVENT_CATALOG, name
                assert not EVENT_CATALOG[step.event].api_generated, name
