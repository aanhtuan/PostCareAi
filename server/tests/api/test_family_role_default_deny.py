"""F35 AC5, R2, R7, R9: `FAMILY` bị chặn mặc định ở API nhân viên và WS; vai trò đọc từ DB."""

import asyncio
import time
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from postcare.api.deps import STAFF_ROLES
from postcare.api.realtime import WsHub
from postcare.db.models import User
from postcare.domain.security import hash_password
from postcare.schemas.enums import UserRole
from tests.conftest import PASSWORD

Login = Callable[[str], dict[str, str]]

STAFF_READ_ENDPOINTS = [
    "/api/v1/beds",
    "/api/v1/patients",
    "/api/v1/cameras",
    "/api/v1/shifts",
    "/api/v1/sessions",
    "/api/v1/sessions/1",
    "/api/v1/sessions/1/timeline",
    "/api/v1/overview",
    "/api/v1/events",
    "/api/v1/alerts",
    "/api/v1/alerts/1",
    "/api/v1/timeline",
    "/api/v1/handover",
]
STAFF_WRITE_ENDPOINTS = [
    ("/api/v1/sessions", {"bed_id": 1, "patient_id": 1}),
    ("/api/v1/sessions/1/end", None),
    ("/api/v1/alerts/1/acknowledge", None),
    ("/api/v1/alerts/1/resolve", {}),
]


@pytest.fixture
def family(client: TestClient, db: Session, login: Login) -> dict[str, str]:
    db.add(
        User(
            username="family",
            full_name="Người nhà thử nghiệm",
            password_hash=hash_password(PASSWORD),
            role=UserRole.FAMILY,
        )
    )
    db.commit()
    return login("family")


def test_staff_roles() -> None:
    assert set(STAFF_ROLES) == {
        UserRole.NURSE,
        UserRole.CHARGE_NURSE,
        UserRole.DOCTOR,
        UserRole.ADMIN,
    }


@pytest.mark.parametrize("path", STAFF_READ_ENDPOINTS)
def test_family_forbidden_on_staff_read_endpoints(
    client: TestClient, family: dict[str, str], path: str
) -> None:
    r = client.get(path, headers=family)
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize(("path", "body"), STAFF_WRITE_ENDPOINTS)
def test_family_forbidden_on_staff_write_endpoints(
    client: TestClient, family: dict[str, str], path: str, body: Any
) -> None:
    r = client.post(path, json=body, headers=family)
    assert r.status_code == 403, r.text


@pytest.mark.parametrize("path", ["/api/v1/beds", "/api/v1/overview", "/api/v1/alerts"])
def test_staff_still_reads(client: TestClient, login: Login, path: str) -> None:
    for username in ("nurse", "charge", "doctor", "admin"):
        assert client.get(path, headers=login(username)).status_code == 200, username


def test_family_can_login_and_me(client: TestClient, family: dict[str, str]) -> None:
    me = client.get("/api/v1/auth/me", headers=family)
    assert me.status_code == 200
    assert me.json()["role"] == "FAMILY"


def test_family_ws_closed_4403(client: TestClient, family: dict[str, str]) -> None:
    token = family["Authorization"].split(" ", 1)[1]
    with (
        client.websocket_connect(f"/api/v1/ws?token={token}") as ws,
        pytest.raises(WebSocketDisconnect) as exc,
    ):
        ws.receive_json()
    assert exc.value.code == 4403


def test_role_change_effective_next_request(
    client: TestClient, login: Login, family: dict[str, str]
) -> None:
    admin = login("admin")
    fam_id = client.get("/api/v1/auth/me", headers=family).json()["id"]
    assert client.get("/api/v1/beds", headers=family).status_code == 403
    r = client.patch(f"/api/v1/users/{fam_id}", json={"role": "NURSE"}, headers=admin)
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/beds", headers=family).status_code == 200  # cùng token
    client.patch(f"/api/v1/users/{fam_id}", json={"role": "FAMILY"}, headers=admin)
    assert client.get("/api/v1/beds", headers=family).status_code == 403


def test_demoted_admin_old_token_forbidden(client: TestClient, login: Login) -> None:
    """Token cũ mang `role=ADMIN` của người đã bị hạ vai trò → 403 ở endpoint ADMIN."""
    admin = login("admin")
    r = client.post(
        "/api/v1/users",
        json={"username": "admin2", "full_name": "B", "role": "ADMIN", "password": PASSWORD},
        headers=admin,
    )
    a2 = r.json()["id"]
    a2_headers = login("admin2")
    assert client.get("/api/v1/users", headers=a2_headers).status_code == 200
    client.patch(f"/api/v1/users/{a2}", json={"role": "NURSE"}, headers=admin)
    assert client.get("/api/v1/users", headers=a2_headers).status_code == 403


async def _get_loop() -> Any:
    return asyncio.get_running_loop()


def test_ws_closed_when_user_locked(app: Any, client: TestClient, login: Login) -> None:
    """R7: khóa tài khoản đóng kết nối WebSocket đang mở với mã 4401."""
    hub = WsHub()
    hub.bind_loop(client.portal.call(_get_loop))  # type: ignore[union-attr]
    app.state.hub = hub
    nurse_token = login("nurse")["Authorization"].split(" ", 1)[1]
    nurse_id = client.get("/api/v1/auth/me", headers=login("nurse")).json()["id"]
    with client.websocket_connect(f"/api/v1/ws?token={nurse_token}") as ws:
        for _ in range(100):
            if hub.client_count:
                break
            time.sleep(0.02)
        assert hub.client_count == 1
        r = client.post(f"/api/v1/users/{nurse_id}/lock", headers=login("admin"))
        assert r.status_code == 200
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 4401


def test_ws_closed_when_role_changed_to_family(app: Any, client: TestClient, login: Login) -> None:
    """Review F35: nhân viên đang kết nối bị đổi sang FAMILY → đóng luồng nhân viên (4403)."""
    hub = WsHub()
    hub.bind_loop(client.portal.call(_get_loop))  # type: ignore[union-attr]
    app.state.hub = hub
    nurse_token = login("nurse")["Authorization"].split(" ", 1)[1]
    nurse_id = client.get("/api/v1/auth/me", headers=login("nurse")).json()["id"]
    with client.websocket_connect(f"/api/v1/ws?token={nurse_token}") as ws:
        for _ in range(100):
            if hub.client_count:
                break
            time.sleep(0.02)
        assert hub.client_count == 1
        r = client.patch(
            f"/api/v1/users/{nurse_id}", json={"role": "FAMILY"}, headers=login("admin")
        )
        assert r.status_code == 200, r.text
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 4403


def test_staff_role_change_keeps_ws(publisher: Any, client: TestClient, login: Login) -> None:
    """Ca âm tính: đổi giữa các vai trò nhân viên không đóng kết nối."""
    nurse_id = client.get("/api/v1/auth/me", headers=login("nurse")).json()["id"]
    r = client.patch(f"/api/v1/users/{nurse_id}", json={"role": "DOCTOR"}, headers=login("admin"))
    assert r.status_code == 200
    assert publisher.disconnected == []
