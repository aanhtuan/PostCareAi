"""F02 AC2: guard theo vai trò với router ghi tạm (chỉ mount trong test).

Ma trận quyền: api-conventions.md "Xác thực và phân quyền" (QA#18). DOCTOR chỉ đọc.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from postcare.api.deps import WRITE_ROLES, get_current_user, require_roles, require_writer
from postcare.db.models import User
from postcare.schemas.enums import UserRole
from postcare.settings import Settings

PROBE = "/api/v1/_test_guard"

USERS = {
    UserRole.NURSE: "nurse",
    UserRole.CHARGE_NURSE: "charge",
    UserRole.DOCTOR: "doctor",
    UserRole.ADMIN: "admin",
}


def _probe_router() -> APIRouter:
    router = APIRouter(prefix=PROBE)

    @router.get("/read")
    def read(user: User = Depends(get_current_user)) -> dict[str, str]:
        return {"role": user.role.value}

    @router.post("/write")
    def write(user: User = Depends(require_writer)) -> dict[str, str]:
        return {"role": user.role.value}

    @router.post("/admin")
    def admin(user: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, str]:
        return {"role": user.role.value}

    return router


@pytest.fixture
def guarded(app: FastAPI, client: TestClient) -> TestClient:
    app.include_router(_probe_router())
    return client


def test_write_roles_match_permission_matrix() -> None:
    assert set(WRITE_ROLES) == {UserRole.NURSE, UserRole.CHARGE_NURSE, UserRole.ADMIN}


@pytest.mark.parametrize("role", list(USERS))
def test_role_matrix(guarded: TestClient, login, role: UserRole) -> None:
    headers = login(USERS[role])
    expected = {
        "read": 200,
        "write": 403 if role == UserRole.DOCTOR else 200,
        "admin": 200 if role == UserRole.ADMIN else 403,
    }
    for action, status in expected.items():
        call = guarded.get if action == "read" else guarded.post
        r = call(f"{PROBE}/{action}", headers=headers)
        assert r.status_code == status, (role, action, r.text)
        if status == 403:
            assert r.json()["error"]["code"] == "FORBIDDEN"
        else:
            assert r.json() == {"role": role.value}


def test_doctor_write_forbidden(guarded: TestClient, login) -> None:
    r = guarded.post(f"{PROBE}/write", headers=login("doctor"))
    assert r.status_code == 403
    err = r.json()["error"]
    assert err["code"] == "FORBIDDEN"
    assert err["message"] == "Không đủ quyền thực hiện thao tác này"


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer"}, {"Authorization": "Basic abc"}, {"Authorization": "abc"}],
)
def test_missing_token_401(guarded: TestClient, headers: dict[str, str]) -> None:
    for call, action in ((guarded.get, "read"), (guarded.post, "write")):
        r = call(f"{PROBE}/{action}", headers=headers)
        assert r.status_code == 401, (headers, action)
        assert r.json()["error"]["code"] == "UNAUTHORIZED"


def _forged(secret: str, **claims: Any) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": "1",
        "role": "ADMIN",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


def test_bad_signature_401(guarded: TestClient, settings: Settings) -> None:
    tokens = [
        _forged("another-secret-at-least-32-bytes-long!"),
        _forged(settings.jwt_secret, sub="khong-phai-so"),
        _forged(settings.jwt_secret, sub="999999"),
        jwt.encode({"sub": "1", "role": "ADMIN"}, settings.jwt_secret + "x" * 40, "HS512"),
        "abc.def.ghi",
    ]
    for token in tokens:
        r = guarded.get(f"{PROBE}/read", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401, token
        assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_role_comes_from_db_not_token(guarded: TestClient, settings: Settings, login) -> None:
    """Claim `role` trong JWT không được tin (api-conventions.md): DOCTOR sửa claim vẫn 403."""
    me = guarded.get("/api/v1/auth/me", headers=login("doctor")).json()
    token = _forged(settings.jwt_secret, sub=str(me["id"]), role="ADMIN")
    r = guarded.post(f"{PROBE}/write", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
