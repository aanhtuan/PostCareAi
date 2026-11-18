"""F29 AC2: client đo ghi được delivery latency từ message `event.created` thật của API."""

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from postcare.eval.delivery import DeliveryRecorder, delivery_stats, read_samples, write_sample

from postcare.api.realtime import WsHub

Login = Callable[[str], dict[str, str]]


async def _get_loop() -> Any:
    return asyncio.get_running_loop()


def test_measure_delivery_records_event_created(
    app: Any, client: TestClient, login: Login, open_session: Any, post_event: Any, tmp_path: Any
) -> None:
    hub = WsHub()
    hub.bind_loop(client.portal.call(_get_loop))  # type: ignore[union-attr]
    app.state.hub = hub
    token = login("nurse")["Authorization"].split(" ", 1)[1]
    rec = DeliveryRecorder()
    out = tmp_path / "delivery.jsonl"
    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        for _ in range(200):
            if hub.client_count:
                break
            time.sleep(0.01)
        assert post_event("BED_EXIT", "HIGH").status_code == 201
        for _ in range(2):  # event.created rồi alert.created
            sample = rec.feed(ws.receive_json(), datetime.now(UTC))
            if sample is not None:
                write_sample(out, sample)
    [sample] = rec.samples
    assert sample.code == "BED_EXIT"
    assert sample.latency_ms >= 0
    stats = delivery_stats(read_samples(out))
    assert stats.samples == 1
    assert stats.median_ms is not None and stats.median_ms >= 0
