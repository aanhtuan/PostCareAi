"""F02: đăng nhập, JWT, phân quyền theo vai trò (DOCTOR chỉ đọc), định dạng lỗi."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from postcare.api.deps import create_token
from postcare.db.models import User
from postcare.domain.security import verify_password
from postcare.settings import Settings
from tests.conftest import PASSWORD


def test_login_returns_token_and_user(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "nurse", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "NURSE"
    assert "password_hash" not in body["user"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == "nurse"


def test_login_wrong_password_and_unknown_user_same_error(client: TestClient) -> None:
    for username, password in (("nurse", "sai"), ("khong-co", PASSWORD)):
        r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_missing_or_bad_token_is_401(client: TestClient) -> None:
    assert client.get("/api/v1/overview").json()["error"]["code"] == "UNAUTHORIZED"
    r = client.get("/api/v1/overview", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_validation_error_is_wrapped(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "nurse"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_doctor_is_read_only(client: TestClient, login, open_session, post_event) -> None:
    doctor = login("doctor")
    # Đọc được mọi màn hình.
    for path in ("/api/v1/overview", "/api/v1/alerts", "/api/v1/events", "/api/v1/beds"):
        assert client.get(path, headers=doctor).status_code == 200, path
    # Không được ghi.
    alert_id = _make_alert(client, login, post_event)
    for path in (
        f"/api/v1/alerts/{alert_id}/acknowledge",
        f"/api/v1/sessions/{open_session['id']}/end",
    ):
        r = client.post(path, headers=doctor)
        assert r.status_code == 403, path
        assert r.json()["error"]["code"] == "FORBIDDEN"
    r = client.post("/api/v1/sessions", json={"bed_id": 2, "patient_id": 2}, headers=doctor)
    assert r.status_code == 403


def test_worker_endpoints_require_worker_token(client: TestClient, login) -> None:
    assert client.get("/internal/v1/cameras/1/config").status_code == 401
    r = client.get("/internal/v1/cameras/1/config", headers={"X-Worker-Token": "sai"})
    assert r.status_code == 401
    # JWT của người dùng không thay được worker token.
    assert client.get("/internal/v1/cameras/1/config", headers=login("admin")).status_code == 401


def _make_alert(client: TestClient, login, post_event) -> int:
    r = post_event("BED_EXIT", "HIGH")
    assert r.status_code == 201, r.text
    alerts = client.get("/api/v1/alerts", headers=login("nurse")).json()
    return alerts["items"][0]["id"]


# --- Bổ sung theo AC1, AC4 của spec F02 -------------------------------------------------------


def _user(db: Session, username: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    assert user is not None
    return user


def _login(client: TestClient, username: str, password: str) -> Any:
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_login_success_returns_jwt(client: TestClient, settings: Settings, db: Session) -> None:
    r = _login(client, "doctor", PASSWORD)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"access_token", "token_type", "user"}
    assert body["token_type"] == "bearer"
    # F35 R4 thêm is_active, created_at; không bao giờ có password_hash.
    assert set(body["user"]) == {"id", "username", "full_name", "role", "is_active", "created_at"}
    payload = jwt.decode(body["access_token"], settings.jwt_secret, algorithms=["HS256"])
    assert payload["sub"] == str(_user(db, "doctor").id)
    assert payload["role"] == "DOCTOR"
    assert "exp" in payload


def _assert_invalid_credentials(r: Any) -> dict[str, Any]:
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "INVALID_CREDENTIALS"
    assert err["message"] == "Tên đăng nhập hoặc mật khẩu không đúng"
    return err


def test_login_wrong_password_401(client: TestClient) -> None:
    _assert_invalid_credentials(_login(client, "nurse", "sai-mat-khau"))


def test_login_unknown_user_401(client: TestClient) -> None:
    _assert_invalid_credentials(_login(client, "khong-ton-tai", PASSWORD))


def test_login_inactive_user_401(client: TestClient, db: Session) -> None:
    _user(db, "nurse").is_active = False
    db.commit()
    inactive = _assert_invalid_credentials(_login(client, "nurse", PASSWORD))
    # Cùng một lỗi với sai mật khẩu: không tiết lộ tài khoản có tồn tại hay đã ngừng.
    wrong = _assert_invalid_credentials(_login(client, "charge", "sai"))
    assert inactive == wrong


def test_password_stored_as_hash(db: Session) -> None:
    nurse = _user(db, "nurse")
    assert PASSWORD not in nurse.password_hash
    assert nurse.password_hash.startswith("$2")  # bcrypt
    assert verify_password(PASSWORD, nurse.password_hash)
    assert not verify_password("sai", nurse.password_hash)


def test_me_does_not_expose_password_hash(client: TestClient, login) -> None:
    for username in ("nurse", "charge", "doctor", "admin"):
        r = client.get("/api/v1/auth/me", headers=login(username))
        assert r.status_code == 200
        assert "password_hash" not in r.text


def test_token_expiry_is_8_hours(settings: Settings, db: Session) -> None:
    assert settings.jwt_expire_hours == 8
    now = datetime(2026, 1, 1, 7, 0, tzinfo=UTC)
    token = create_token(_user(db, "nurse"), settings, now=now)
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=["HS256"], options={"verify_exp": False}
    )
    assert payload["exp"] - payload["iat"] == 8 * 3600
    assert payload["exp"] == int((now + timedelta(hours=8)).timestamp())


def test_expired_token_401(client: TestClient, settings: Settings, db: Session) -> None:
    issued = datetime.now(UTC) - timedelta(hours=8, seconds=1)
    token = create_token(_user(db, "nurse"), settings, now=issued)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"
    # Còn trong hạn (gần hết 8 giờ) thì vẫn dùng được.
    fresh = create_token(_user(db, "nurse"), settings, now=issued + timedelta(minutes=1))
    ok = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fresh}"})
    assert ok.status_code == 200


def test_deactivated_user_token_401(client: TestClient, login, db: Session) -> None:
    headers = login("nurse")
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    _user(db, "nurse").is_active = False
    db.commit()
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_ws_expired_token_closes_4401(client: TestClient, settings: Settings, db: Session) -> None:
    token = create_token(_user(db, "nurse"), settings, now=datetime.now(UTC) - timedelta(hours=9))
    with (
        client.websocket_connect(f"/api/v1/ws?token={token}") as ws,
        pytest.raises(WebSocketDisconnect) as exc,
    ):
        ws.receive_json()
    assert exc.value.code == 4401
