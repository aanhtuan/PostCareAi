"""F35 AC1–AC4: quản lý người dùng (chỉ ADMIN), khóa/mở khóa, ADMIN cuối cùng, audit."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog, User
from postcare.schemas.enums import UserRole
from tests.conftest import PASSWORD

Login = Callable[[str], dict[str, str]]
URL = "/api/v1/users"
NEW_PASSWORD = "mat-khau-moi-123"


def _create(
    client: TestClient,
    headers: dict[str, str],
    username: str = "hoa.nguyen",
    role: str = "NURSE",
    password: str = NEW_PASSWORD,
) -> Any:
    return client.post(
        URL,
        json={
            "username": username,
            "full_name": "Nguyễn Văn Hòa",
            "role": role,
            "password": password,
        },
        headers=headers,
    )


def _login(client: TestClient, username: str, password: str) -> Any:
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def _bearer(client: TestClient, username: str, password: str) -> dict[str, str]:
    r = _login(client, username, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _id(client: TestClient, login: Login, username: str) -> int:
    return client.get("/api/v1/auth/me", headers=login(username)).json()["id"]


def _audits(db: Session, entity_id: int | None = None) -> list[AuditLog]:
    q = select(AuditLog).where(AuditLog.entity_type == "user").order_by(AuditLog.id)
    if entity_id is not None:
        q = q.where(AuditLog.entity_id == entity_id)
    return list(db.scalars(q))


# ---------- AC1 ----------


def test_admin_user_crud(client: TestClient, login: Login) -> None:
    admin = login("admin")
    r = _create(client, admin)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["username"] == "hoa.nguyen"
    assert created["role"] == "NURSE"
    assert created["is_active"] is True
    assert "created_at" in created
    uid = created["id"]

    listed = client.get(URL, headers=admin).json()
    assert listed["total"] == 5
    assert {u["username"] for u in listed["items"]} >= {"admin", "nurse", "hoa.nguyen"}

    assert client.get(f"{URL}/{uid}", headers=admin).json()["full_name"] == "Nguyễn Văn Hòa"

    r = client.patch(
        f"{URL}/{uid}", json={"full_name": "Nguyễn Văn Hòa B", "role": "DOCTOR"}, headers=admin
    )
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Nguyễn Văn Hòa B"
    assert r.json()["role"] == "DOCTOR"

    r = client.post(f"{URL}/{uid}/lock", headers=admin)
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert all(u["id"] != uid for u in client.get(URL, headers=admin).json()["items"])
    inactive = client.get(URL, params={"include_inactive": "true"}, headers=admin).json()
    assert any(u["id"] == uid and not u["is_active"] for u in inactive["items"])

    r = client.post(f"{URL}/{uid}/unlock", headers=admin)
    assert r.status_code == 200 and r.json()["is_active"] is True

    filtered = client.get(URL, params={"role": "DOCTOR"}, headers=admin).json()
    assert {u["username"] for u in filtered["items"]} == {"doctor", "hoa.nguyen"}

    assert client.get(f"{URL}/999999", headers=admin).status_code == 404


def test_admin_can_create_family_user(client: TestClient, login: Login) -> None:
    r = _create(client, login("admin"), username="nguoinha01", role="FAMILY")
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "FAMILY"
    assert _login(client, "nguoinha01", NEW_PASSWORD).json()["user"]["role"] == "FAMILY"


@pytest.mark.parametrize("username", ["nurse", "charge", "doctor", "family"])
def test_users_endpoints_admin_only(
    client: TestClient, login: Login, db: Session, username: str
) -> None:
    if username == "family":
        _create(client, login("admin"), username="family", role="FAMILY", password=PASSWORD)
    headers = login(username)
    target = _id(client, login, "nurse")
    calls = [
        ("GET", URL, None),
        ("GET", f"{URL}/{target}", None),
        (
            "POST",
            URL,
            {"username": "x.y.z", "full_name": "X", "role": "NURSE", "password": "12345678"},
        ),
        ("PATCH", f"{URL}/{target}", {"full_name": "X"}),
        ("POST", f"{URL}/{target}/lock", None),
        ("POST", f"{URL}/{target}/unlock", None),
        ("POST", f"{URL}/{target}/reset-password", {"new_password": "12345678"}),
    ]
    for method, path, body in calls:
        r = client.request(method, path, json=body, headers=headers)
        assert r.status_code == 403, (username, method, path, r.text)
        assert r.json()["error"]["code"] == "FORBIDDEN"
    assert db.scalar(select(User).where(User.username == "x.y.z")) is None


def test_users_endpoints_require_login(client: TestClient) -> None:
    assert client.get(URL).status_code == 401


def test_reset_password_allows_new_login(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    uid = _id(client, login, "nurse")
    r = client.post(
        f"{URL}/{uid}/reset-password", json={"new_password": NEW_PASSWORD}, headers=admin
    )
    assert r.status_code == 204, r.text
    assert _login(client, "nurse", PASSWORD).status_code == 401
    assert _login(client, "nurse", NEW_PASSWORD).status_code == 200
    assert [a.action for a in _audits(db, uid)] == ["user.reset_password"]


@pytest.mark.parametrize(
    "body",
    [
        {"username": "abc.def", "full_name": "A", "role": "FOO", "password": NEW_PASSWORD},
        {
            "username": "abc.def",
            "full_name": "A",
            "role": "NURSE",
            "password": NEW_PASSWORD,
            "password_hash": "$2b$x",
        },
        {"username": "abc.def", "full_name": "A", "role": "NURSE", "password": "1234567"},
        {"username": "ab", "full_name": "A", "role": "NURSE", "password": NEW_PASSWORD},
        {"username": "có dấu", "full_name": "A", "role": "NURSE", "password": NEW_PASSWORD},
        {"username": "abc/def", "full_name": "A", "role": "NURSE", "password": NEW_PASSWORD},
        {"username": "abc.def", "full_name": "  ", "role": "NURSE", "password": NEW_PASSWORD},
    ],
)
def test_create_user_validation(client: TestClient, login: Login, body: dict[str, Any]) -> None:
    r = client.post(URL, json=body, headers=login("admin"))
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patch_rejects_unknown_fields(client: TestClient, login: Login) -> None:
    uid = _id(client, login, "nurse")
    for body in ({"username": "khac"}, {"is_active": False}, {"password": NEW_PASSWORD}):
        r = client.patch(f"{URL}/{uid}", json=body, headers=login("admin"))
        assert r.status_code == 422, body


def test_reset_password_too_short(client: TestClient, login: Login) -> None:
    uid = _id(client, login, "nurse")
    r = client.post(
        f"{URL}/{uid}/reset-password", json={"new_password": "1234567"}, headers=login("admin")
    )
    assert r.status_code == 422


# ---------- AC2 ----------


def test_duplicate_username_409(client: TestClient, login: Login) -> None:
    admin = login("admin")
    assert _create(client, admin).status_code == 201
    for name in ("hoa.nguyen", "  HOA.Nguyen  ", "NURSE"):
        r = _create(client, admin, username=name)
        assert r.status_code == 409, name
        err = r.json()["error"]
        assert err["code"] == "DUPLICATE_CODE"
        assert err["details"] == {"field": "username"}


def test_duplicate_username_includes_locked(client: TestClient, login: Login) -> None:
    admin = login("admin")
    uid = _create(client, admin).json()["id"]
    client.post(f"{URL}/{uid}/lock", headers=admin)
    assert _create(client, admin).status_code == 409


def test_username_normalized(client: TestClient, login: Login) -> None:
    r = _create(client, login("admin"), username="  Hoa.Nguyen ")
    assert r.status_code == 201
    assert r.json()["username"] == "hoa.nguyen"


def test_locked_user_cannot_login(client: TestClient, login: Login) -> None:
    uid = _id(client, login, "nurse")
    assert client.post(f"{URL}/{uid}/lock", headers=login("admin")).status_code == 200
    r = _login(client, "nurse", PASSWORD)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_locked_user_token_rejected(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    uid = _id(client, login, "nurse")
    client.post(f"{URL}/{uid}/lock", headers=login("admin"))
    r = client.get("/api/v1/overview", headers=nurse)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_unlock_restores_login(client: TestClient, login: Login) -> None:
    admin = login("admin")
    uid = _id(client, login, "nurse")
    client.post(f"{URL}/{uid}/lock", headers=admin)
    client.post(f"{URL}/{uid}/unlock", headers=admin)
    assert _login(client, "nurse", PASSWORD).status_code == 200


# ---------- AC3 ----------


def test_cannot_lock_self(client: TestClient, login: Login) -> None:
    admin = login("admin")
    _create(client, admin, username="admin2", role="ADMIN")  # còn ADMIN khác vẫn bị chặn
    r = client.post(f"{URL}/{_id(client, login, 'admin')}/lock", headers=admin)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CANNOT_MODIFY_SELF"


def test_cannot_demote_self(client: TestClient, login: Login) -> None:
    admin = login("admin")
    _create(client, admin, username="admin2", role="ADMIN")
    me = _id(client, login, "admin")
    r = client.patch(f"{URL}/{me}", json={"role": "NURSE"}, headers=admin)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CANNOT_MODIFY_SELF"
    # Tự sửa họ tên (giữ vai trò ADMIN) thì được.
    r = client.patch(
        f"{URL}/{me}", json={"full_name": "Phạm Thu Hà", "role": "ADMIN"}, headers=admin
    )
    assert r.status_code == 200


def test_cannot_lock_last_admin(client: TestClient, login: Login) -> None:
    """Chỉ còn một ADMIN: tự khóa/tự hạ → LAST_ADMIN (kiểm tra trước CANNOT_MODIFY_SELF)."""
    admin = login("admin")
    me = _id(client, login, "admin")
    r = client.post(f"{URL}/{me}/lock", headers=admin)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "LAST_ADMIN"
    r = client.patch(f"{URL}/{me}", json={"role": "DOCTOR"}, headers=admin)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "LAST_ADMIN"


def test_last_admin_guard_in_domain(db: Session) -> None:
    """Domain chặn cả khi người gọi không phải mục tiêu (ví dụ ADMIN khác vừa bị khóa)."""
    from postcare.domain import users as svc
    from postcare.domain.errors import DomainError

    admin = db.scalar(select(User).where(User.username == "admin"))
    nurse = db.scalar(select(User).where(User.username == "nurse"))
    assert admin is not None and nurse is not None
    with pytest.raises(DomainError) as exc:
        svc.lock_user(db, user_id=admin.id, actor=nurse)
    assert exc.value.code == "LAST_ADMIN"
    with pytest.raises(DomainError) as exc:
        svc.update_user(db, user_id=admin.id, actor=nurse, role=UserRole.NURSE)
    assert exc.value.code == "LAST_ADMIN"


def test_two_admins_lock_one_not_the_other(client: TestClient, login: Login) -> None:
    """Hai ADMIN: khóa người kia được; sau đó người còn lại là ADMIN cuối cùng."""
    admin = login("admin")
    a2 = _create(client, admin, username="admin2", role="ADMIN").json()["id"]
    assert client.post(f"{URL}/{a2}/lock", headers=admin).status_code == 200
    me = _id(client, login, "admin")
    assert client.post(f"{URL}/{me}/lock", headers=admin).json()["error"]["code"] == "LAST_ADMIN"


def test_can_lock_admin_when_another_exists(client: TestClient, login: Login) -> None:
    admin = login("admin")
    uid = _create(client, admin, username="admin2", role="ADMIN").json()["id"]
    assert client.post(f"{URL}/{uid}/lock", headers=admin).status_code == 200
    assert client.post(f"{URL}/{uid}/unlock", headers=admin).status_code == 200
    r = client.patch(f"{URL}/{uid}", json={"role": "DOCTOR"}, headers=admin)
    assert r.status_code == 200 and r.json()["role"] == "DOCTOR"


# ---------- AC4 ----------


def test_user_writes_audited(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    admin_id = _id(client, login, "admin")
    uid = _create(client, admin).json()["id"]
    client.patch(f"{URL}/{uid}", json={"full_name": "Tên mới"}, headers=admin)
    client.post(f"{URL}/{uid}/lock", headers=admin)
    client.post(f"{URL}/{uid}/lock", headers=admin)  # lặp: không audit
    client.post(f"{URL}/{uid}/unlock", headers=admin)
    client.post(f"{URL}/{uid}/unlock", headers=admin)  # lặp: không audit
    client.post(f"{URL}/{uid}/reset-password", json={"new_password": NEW_PASSWORD}, headers=admin)
    logs = _audits(db, uid)
    assert [a.action for a in logs] == [
        "user.create",
        "user.update",
        "user.lock",
        "user.unlock",
        "user.reset_password",
    ]
    assert all(a.actor_user_id == admin_id for a in logs)
    create, update, lock = logs[0], logs[1], logs[2]
    assert create.before is None
    assert create.after == {
        "username": "hoa.nguyen",
        "full_name": "Nguyễn Văn Hòa",
        "role": "NURSE",
        "is_active": True,
    }
    assert update.before is not None and update.before["full_name"] == "Nguyễn Văn Hòa"
    assert update.after is not None and update.after["full_name"] == "Tên mới"
    assert lock.after is not None and lock.after["is_active"] is False


def test_noop_update_not_audited(client: TestClient, login: Login, db: Session) -> None:
    uid = _id(client, login, "nurse")
    nurse = client.get(f"{URL}/{uid}", headers=login("admin")).json()
    r = client.patch(f"{URL}/{uid}", json={"full_name": nurse["full_name"]}, headers=login("admin"))
    assert r.status_code == 200
    assert _audits(db, uid) == []


def test_audit_never_contains_password(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    uid = _create(client, admin).json()["id"]
    client.post(
        f"{URL}/{uid}/reset-password", json={"new_password": "mat-khau-khac-456"}, headers=admin
    )
    client.patch(f"{URL}/{uid}", json={"role": "FAMILY"}, headers=admin)
    dumped = json.dumps([[a.before, a.after] for a in _audits(db)], ensure_ascii=False)
    assert NEW_PASSWORD not in dumped
    assert "mat-khau-khac-456" not in dumped
    assert "$2" not in dumped
    assert "password" not in dumped


def test_user_out_has_no_password_hash(client: TestClient, login: Login) -> None:
    admin = login("admin")
    created = _create(client, admin).json()
    uid = created["id"]
    bodies = [
        created,
        client.get(f"{URL}/{uid}", headers=admin).json(),
        *client.get(URL, headers=admin).json()["items"],
        client.patch(f"{URL}/{uid}", json={"full_name": "B"}, headers=admin).json(),
        client.post(f"{URL}/{uid}/lock", headers=admin).json(),
        client.get("/api/v1/auth/me", headers=admin).json(),
    ]
    for body in bodies:
        assert set(body) == {"id", "username", "full_name", "role", "is_active", "created_at"}


def _reset(client: TestClient, login: Login, uid: int) -> Any:
    return client.post(
        f"{URL}/{uid}/reset-password", json={"new_password": NEW_PASSWORD}, headers=login("admin")
    )


def test_reset_password_revokes_old_tokens(client: TestClient, login: Login) -> None:
    """Review F35: đặt lại mật khẩu làm token cũ hết hiệu lực; token mới dùng được."""
    old = login("nurse")
    uid = _id(client, login, "nurse")
    assert _reset(client, login, uid).status_code == 204
    r = client.get("/api/v1/auth/me", headers=old)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"
    fresh = _bearer(client, "nurse", NEW_PASSWORD)
    assert client.get("/api/v1/auth/me", headers=fresh).status_code == 200


def test_reset_password_closes_ws(publisher: Any, client: TestClient, login: Login) -> None:
    uid = _id(client, login, "nurse")
    _reset(client, login, uid)
    assert publisher.disconnected == [uid]


def test_other_users_tokens_survive_reset(client: TestClient, login: Login) -> None:
    doctor = login("doctor")
    _reset(client, login, _id(client, login, "nurse"))
    assert client.get("/api/v1/auth/me", headers=doctor).status_code == 200
