"""F36 R12–R14, AC2–AC6 (WebSocket): bản chiếu `family.*` theo từng kết nối, đóng 4403."""

import asyncio
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from postcare.api.realtime import WsHub
from postcare.db.models import AuditLog
from tests.api.family_utils import (
    FAMILY_WS_TYPES,
    FakeClock,
    Login,
    assert_no_image,
    grant_ok,
    revoke,
    start_session,
)

KEYPOINTS = {"nose": [0.5, 0.3, 0.9], "left_hip": [0.45, 0.6, 0.8]}


async def _get_loop() -> Any:
    return asyncio.get_running_loop()


@pytest.fixture
def hub(app: Any, client: TestClient) -> WsHub:
    h = WsHub()
    h.bind_loop(client.portal.call(_get_loop))  # type: ignore[union-attr]
    app.state.hub = h
    return h


def _token(login: Login, username: str) -> str:
    return login(username)["Authorization"].split(" ", 1)[1]


def _wait_for_clients(hub: WsHub, n: int = 1) -> None:
    for _ in range(300):
        if hub.client_count >= n:
            return
        time.sleep(0.01)
    raise AssertionError(f"WebSocket chưa đăng ký đủ {n} kết nối")


def _connect(client: TestClient, login: Login, username: str = "family") -> Any:
    return client.websocket_connect(f"/api/v1/ws?token={_token(login, username)}")


def _state(client: TestClient, worker_headers: dict[str, str], camera_id: int = 1, **extra: Any):
    body = {"body_state": "SITTING", "observation_quality": "GOOD", "face_status": "OK", **extra}
    r = client.post(f"/internal/v1/cameras/{camera_id}/state", headers=worker_headers, json=body)
    assert r.status_code == 200, r.text


def _initial(ws: WebSocketTestSession, n: int = 1) -> list[dict[str, Any]]:
    """Khi kết nối, mỗi grant nhận một `family.state` ban đầu."""
    msgs = [ws.receive_json() for _ in range(n)]
    assert [m["type"] for m in msgs] == ["family.state"] * n
    return msgs


def _until(ws: WebSocketTestSession, type_: str, limit: int = 20) -> list[dict[str, Any]]:
    """Đọc tới (gồm) message đầu tiên có `type_`."""
    out = []
    for _ in range(limit):
        m = ws.receive_json()
        out.append(m)
        if m["type"] == type_:
            return out
    raise AssertionError(f"không nhận được {type_}: {[m['type'] for m in out]}")


def _closed_code(ws: WebSocketTestSession) -> int:
    with pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_json()
    return exc.value.code


def test_family_ws_without_grant_closes_4403(client: TestClient, login: Login, fam: int) -> None:
    with _connect(client, login) as ws:
        assert _closed_code(ws) == 4403


def test_family_ws_view_audited_on_connect(
    client: TestClient, hub: WsHub, login: Login, db: Session, open_session: Any, fam: int
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    with _connect(client, login) as ws:
        _initial(ws)
    db.expire_all()
    views = list(db.scalars(select(AuditLog).where(AuditLog.action == "family_access.view")))
    assert len(views) == 1
    assert (views[0].entity_id, views[0].actor_user_id) == (gid, fam)
    assert views[0].after == {"channel": "ws"}


def test_family_ws_not_delivered_other_bed(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    fam: int,
    worker_headers: dict[str, str],
    post_event: Callable[..., Any],
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    other = start_session(client, login, 2, 2)
    with _connect(client, login) as ws:
        _initial(ws)
        _wait_for_clients(hub)
        # Giường khác: sự kiện, cảnh báo, trạng thái, phiên → không message nào.
        assert post_event("BED_EXIT", "HIGH", camera_id=2).status_code == 201
        _state(client, worker_headers, camera_id=2, target_keypoints=KEYPOINTS)
        nurse = login("nurse")
        client.post(f"/api/v1/sessions/{other}/pause", json={}, headers=nurse)
        client.post(f"/api/v1/sessions/{other}/end", headers=nurse)
        # Giường được cấp quyền: message đầu tiên phải là của A01.
        assert post_event("SIT_UP", "INFO").status_code == 201
        m = ws.receive_json()
        assert m["type"] == "family.event"
        assert m["payload"]["grant_id"] == gid
        assert m["payload"]["code"] == "SIT_UP"


def test_family_ws_receives_only_family_types(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    fam: int,
    worker_headers: dict[str, str],
    post_event: Callable[..., Any],
) -> None:
    sid = open_session["id"]
    gid = grant_ok(client, login, sid, fam, share_level="SKELETON")
    with _connect(client, login) as ws:
        msgs = _initial(ws)
        _wait_for_clients(hub)
        assert post_event("POSTURE_CHANGE", "LOG").status_code == 201  # LOG: không gửi
        assert post_event("BED_EXIT", "HIGH").status_code == 201
        msgs += _until(ws, "family.event")
        alert_id = client.get("/api/v1/alerts", headers=login("nurse")).json()["items"][0]["id"]
        client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=login("nurse"))
        msgs += _until(ws, "family.event")
        assert msgs[-1]["payload"]["alert_status"] == "ACKNOWLEDGED"
        _state(client, worker_headers, target_keypoints=KEYPOINTS)
        msgs += _until(ws, "family.skeleton")
        client.post(f"/api/v1/sessions/{sid}/pause", json={}, headers=login("nurse"))
        msgs += _until(ws, "family.state")
    for m in msgs:
        assert m["type"] in FAMILY_WS_TYPES, m["type"]
        assert m["payload"]["grant_id"] == gid
        assert_no_image(m)
        assert "face" not in repr(m)
        assert "BN-" not in repr(m) and "explanation" not in repr(m)
    events = [m for m in msgs if m["type"] == "family.event"]
    assert [e["payload"]["code"] for e in events] == ["BED_EXIT", "BED_EXIT"]
    assert set(events[0]["payload"]) == {
        "grant_id",
        "event_id",
        "time",
        "code",
        "priority",
        "alert_status",
    }
    state = next(m for m in msgs[1:] if m["type"] == "family.state")
    assert set(state["payload"]) == {
        "grant_id",
        "body_state",
        "observation_quality",
        "activity_level",
        "rest_status",
        "capture_paused",
        "updated_at",
    }


def test_staff_ws_never_gets_family_messages(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    fam: int,
    worker_headers: dict[str, str],
    post_event: Callable[..., Any],
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam, share_level="SKELETON")
    with _connect(client, login, "nurse") as ws:
        _wait_for_clients(hub)
        _state(client, worker_headers, target_keypoints=KEYPOINTS)
        assert revoke(client, login, gid).status_code == 200
        assert post_event("SIT_UP", "INFO").status_code == 201
        types = [m["type"] for m in _until(ws, "event.created")]
    assert types == ["bed.state", "event.created"]


# AC3 -------------------------------------------------------------------------


def test_family_ws_revoked_mid_stream_closes_within_2s(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    fam: int,
    post_event: Callable[..., Any],
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    with _connect(client, login) as ws:
        _initial(ws)
        _wait_for_clients(hub)
        post_event("SIT_UP", "INFO")
        assert ws.receive_json()["type"] == "family.event"
        t0 = time.monotonic()
        assert revoke(client, login, gid).status_code == 200
        m = ws.receive_json()
        assert m == {
            "type": "family.access_ended",
            "payload": {"grant_id": gid, "reason": "REVOKED"},
            "sent_at": m["sent_at"],
        }
        assert _closed_code(ws) == 4403
        assert time.monotonic() - t0 <= 2.0
    assert hub.client_count == 0
    r = client.get(f"/api/v1/family/grants/{gid}/view", headers=login("family"))
    assert r.json()["error"]["code"] == "FAMILY_ACCESS_ENDED"


def test_revoke_one_grant_keeps_other(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    fam: int,
    post_event: Callable[..., Any],
) -> None:
    g1 = grant_ok(client, login, open_session["id"], fam)
    g2 = grant_ok(client, login, start_session(client, login, 2, 2), fam)
    with _connect(client, login) as ws:
        _initial(ws, 2)
        _wait_for_clients(hub)
        assert revoke(client, login, g1).status_code == 200
        m = ws.receive_json()
        assert m["type"] == "family.access_ended"
        assert m["payload"]["grant_id"] == g1
        assert post_event("SIT_UP", "INFO").status_code == 201  # A01: grant đã thu hồi
        assert post_event("STAND_UP", "INFO", camera_id=2).status_code == 201
        m = ws.receive_json()
        assert m["type"] == "family.event"
        assert (m["payload"]["grant_id"], m["payload"]["code"]) == (g2, "STAND_UP")


def test_family_ws_expired_grant_closes(
    client: TestClient, hub: WsHub, login: Login, open_session: Any, fam: int, clock: FakeClock
) -> None:
    gid = grant_ok(
        client, login, open_session["id"], fam, expires_at=clock.now + timedelta(minutes=1)
    )
    with _connect(client, login) as ws:
        _initial(ws)
        _wait_for_clients(hub)
        t0 = time.monotonic()
        clock.now += timedelta(minutes=2)
        m = ws.receive_json()
        assert m["type"] == "family.access_ended"
        assert m["payload"] == {"grant_id": gid, "reason": "EXPIRED"}
        assert _closed_code(ws) == 4403
        assert time.monotonic() - t0 <= 2.0


# AC4 -------------------------------------------------------------------------


def test_family_ws_session_end_sends_session_ended(
    client: TestClient, hub: WsHub, login: Login, open_session: Any, fam: int
) -> None:
    sid = open_session["id"]
    gid = grant_ok(client, login, sid, fam)
    with _connect(client, login) as ws:
        _initial(ws)
        _wait_for_clients(hub)
        client.post(f"/api/v1/sessions/{sid}/end", headers=login("nurse"))
        m = ws.receive_json()
        assert m["type"] == "family.access_ended"
        assert m["payload"] == {"grant_id": gid, "reason": "SESSION_ENDED"}
        assert _closed_code(ws) == 4403


def test_family_ws_transfer_ends_grant(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    fam: int,
    post_event: Callable[..., Any],
) -> None:
    sid = open_session["id"]
    gid = grant_ok(client, login, sid, fam)
    with _connect(client, login) as ws:
        _initial(ws)
        _wait_for_clients(hub)
        r = client.post(
            f"/api/v1/sessions/{sid}/transfer",
            json={"target_bed_id": 2, "reason": "Đổi phòng"},
            headers=login("nurse"),
        )
        assert r.status_code == 201
        m = ws.receive_json()
        assert m["payload"] == {"grant_id": gid, "reason": "SESSION_ENDED"}
        assert _closed_code(ws) == 4403


def test_family_ws_account_locked(
    client: TestClient, hub: WsHub, login: Login, open_session: Any, fam: int
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    with _connect(client, login) as ws:
        _initial(ws)
        _wait_for_clients(hub)
        assert client.post(f"/api/v1/users/{fam}/lock", headers=login("admin")).status_code == 200
        m = ws.receive_json()
        assert m["payload"] == {"grant_id": gid, "reason": "ACCOUNT_LOCKED"}
        assert _closed_code(ws) == 4401


def test_family_ws_role_change_closes(
    client: TestClient, hub: WsHub, login: Login, open_session: Any, fam: int
) -> None:
    grant_ok(client, login, open_session["id"], fam)
    with _connect(client, login) as ws:
        _initial(ws)
        _wait_for_clients(hub)
        r = client.patch(f"/api/v1/users/{fam}", json={"role": "NURSE"}, headers=login("admin"))
        assert r.status_code == 200
        assert ws.receive_json()["payload"]["reason"] == "ACCOUNT_LOCKED"
        assert _closed_code(ws) == 4403


# AC5 -------------------------------------------------------------------------


def test_family_skeleton_has_no_jpeg(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    fam: int,
    worker_headers: dict[str, str],
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam, share_level="SKELETON")
    with _connect(client, login) as ws:
        msgs = _initial(ws)
        _wait_for_clients(hub)
        jpeg = b"\xff\xd8\xff\xe0" + b"0" * 200
        client.post(
            "/internal/v1/cameras/1/frame",
            headers={**worker_headers, "Content-Type": "image/jpeg"},
            content=jpeg,
        )
        _state(client, worker_headers, target_keypoints=KEYPOINTS)
        msgs += _until(ws, "family.skeleton")
    skel = msgs[-1]["payload"]
    assert set(skel) == {"grant_id", "keypoints", "roi_polygon", "ts"}
    assert skel["grant_id"] == gid
    assert skel["keypoints"] == KEYPOINTS
    for pt in skel["roi_polygon"]:
        assert all(isinstance(v, float | int) for v in pt)
    for m in msgs:
        assert_no_image(m)


def test_info_level_gets_no_skeleton(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    fam: int,
    worker_headers: dict[str, str],
    post_event: Callable[..., Any],
) -> None:
    grant_ok(client, login, open_session["id"], fam)
    with _connect(client, login) as ws:
        _initial(ws)
        _wait_for_clients(hub)
        _state(client, worker_headers, target_keypoints=KEYPOINTS)
        post_event("SIT_UP", "INFO")
        types = [m["type"] for m in _until(ws, "family.event")]
    assert types == ["family.state", "family.event"]


def test_skeleton_null_when_multiple_people(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    fam: int,
    worker_headers: dict[str, str],
) -> None:
    grant_ok(client, login, open_session["id"], fam, share_level="SKELETON")
    with _connect(client, login) as ws:
        _initial(ws)
        _wait_for_clients(hub)
        _state(client, worker_headers, observation_quality="MULTIPLE_PEOPLE", target_keypoints=None)
        skel = _until(ws, "family.skeleton")[-1]
    assert skel["payload"]["keypoints"] is None


def test_skeleton_rate_limited(
    client: TestClient,
    hub: WsHub,
    login: Login,
    open_session: Any,
    fam: int,
    worker_headers: dict[str, str],
    post_event: Callable[..., Any],
) -> None:
    grant_ok(client, login, open_session["id"], fam, share_level="SKELETON")
    with _connect(client, login) as ws:
        _initial(ws)
        _wait_for_clients(hub)
        t0 = time.monotonic()
        for _ in range(10):
            _state(client, worker_headers, target_keypoints=KEYPOINTS)
        elapsed = time.monotonic() - t0
        post_event("SIT_UP", "INFO")
        msgs = _until(ws, "family.event", limit=30)
    n = sum(1 for m in msgs if m["type"] == "family.skeleton")
    assert 1 <= n <= int(elapsed * 5) + 2


# AC6 -------------------------------------------------------------------------


def test_family_ws_paused_state(
    client: TestClient, hub: WsHub, login: Login, open_session: Any, fam: int
) -> None:
    sid = open_session["id"]
    grant_ok(client, login, sid, fam)
    with _connect(client, login) as ws:
        assert _initial(ws)[0]["payload"]["capture_paused"] is False
        _wait_for_clients(hub)
        client.post(f"/api/v1/sessions/{sid}/pause", json={}, headers=login("nurse"))
        m = ws.receive_json()
        assert m["type"] == "family.state"
        assert m["payload"]["capture_paused"] is True
        client.post(f"/api/v1/sessions/{sid}/resume", headers=login("nurse"))
        m = ws.receive_json()
        assert m["payload"]["capture_paused"] is False
