"""F28 AC1, R1–R3: `PUT /cameras/{id}/display-mode` (ADMIN, CHARGE_NURSE; audit, version)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog, Camera, User
from postcare.domain.security import hash_password
from postcare.schemas.enums import DisplayMode, UserRole
from tests.conftest import PASSWORD

Login = Callable[[str], dict[str, str]]
URL = "/api/v1/cameras/1/display-mode"
ACTION = "camera.update_display_mode"


def _camera(db: Session) -> Camera:
    db.expire_all()
    camera = db.get(Camera, 1)
    assert camera is not None
    return camera


def _audits(db: Session) -> list[AuditLog]:
    db.expire_all()
    return list(db.scalars(select(AuditLog).where(AuditLog.action == ACTION).order_by(AuditLog.id)))


def _other(mode: DisplayMode) -> DisplayMode:
    return DisplayMode.SKELETON if mode is not DisplayMode.SKELETON else DisplayMode.RAW


@pytest.fixture
def family(db: Session, login: Login) -> dict[str, str]:
    db.add(
        User(
            username="family",
            full_name="Người nhà",
            password_hash=hash_password(PASSWORD),
            role=UserRole.FAMILY,
        )
    )
    db.commit()
    return login("family")


def test_default_display_mode_is_blur(client: TestClient, login: Login) -> None:
    r = client.post(
        "/api/v1/cameras",
        json={"name": "Camera mới", "source_type": "WEBCAM", "source": "0"},
        headers=login("admin"),
    )
    assert r.status_code == 201, r.text
    assert r.json()["display_mode"] == "BLUR"


@pytest.mark.parametrize(
    ("username", "status"),
    [("admin", 200), ("charge", 200), ("nurse", 403), ("doctor", 403)],
)
def test_put_display_mode_by_role(
    client: TestClient, login: Login, db: Session, username: str, status: int
) -> None:
    before = _camera(db)
    version, mode = before.config_version, before.display_mode
    target = _other(mode)
    r = client.put(URL, json={"display_mode": target.value}, headers=login(username))
    assert r.status_code == status, r.text
    camera = _camera(db)
    if status == 200:
        body = r.json()
        assert body["id"] == 1 and body["display_mode"] == target.value
        assert body["config_version"] == version + 1
        assert camera.display_mode is target and camera.config_version == version + 1
    else:
        assert r.json()["error"]["code"] == "FORBIDDEN"
        assert camera.display_mode is mode and camera.config_version == version
        assert _audits(db) == []


def test_put_display_mode_family_forbidden(
    client: TestClient, family: dict[str, str], db: Session
) -> None:
    version = _camera(db).config_version
    r = client.put(URL, json={"display_mode": "RAW"}, headers=family)
    assert r.status_code == 403
    assert _camera(db).config_version == version


def test_put_display_mode_unauthenticated_401(client: TestClient) -> None:
    assert client.put(URL, json={"display_mode": "RAW"}).status_code == 401


def test_display_mode_change_writes_audit_and_bumps_version(
    client: TestClient, login: Login, db: Session, worker_headers: dict[str, str]
) -> None:
    before = _camera(db)
    v0, mode0 = before.config_version, before.display_mode
    target = _other(mode0)
    assert client.put(URL, json={"display_mode": target.value}, headers=login("charge")).is_success
    logs = _audits(db)
    assert len(logs) == 1
    log = logs[0]
    assert log.entity_type == "camera" and log.entity_id == 1
    assert log.before == {"display_mode": mode0.value, "config_version": v0}
    assert log.after == {"display_mode": target.value, "config_version": v0 + 1}
    charge = db.scalar(select(User).where(User.username == "charge"))
    assert charge is not None and log.actor_user_id == charge.id
    # Gửi lại giá trị y hệt: không tăng version, không audit thêm.
    assert client.put(URL, json={"display_mode": target.value}, headers=login("admin")).is_success
    assert _camera(db).config_version == v0 + 1
    assert len(_audits(db)) == 1
    # Worker nhận chế độ mới qua API nội bộ (F06 R2).
    r = client.get("/internal/v1/cameras/1/config", headers=worker_headers)
    assert r.json()["display_mode"] == target.value
    assert r.json()["config_version"] == v0 + 1


@pytest.mark.parametrize("value", ["FOO", "blur", "", None, 1])
def test_put_display_mode_invalid_value_rejected(
    client: TestClient, login: Login, db: Session, value: object
) -> None:
    version = _camera(db).config_version
    r = client.put(URL, json={"display_mode": value}, headers=login("admin"))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _camera(db).config_version == version


def test_put_display_mode_missing_field_rejected(client: TestClient, login: Login) -> None:
    r = client.put(URL, json={}, headers=login("admin"))
    assert r.status_code == 422


def test_put_display_mode_unknown_camera_404(client: TestClient, login: Login) -> None:
    r = client.put(
        "/api/v1/cameras/9999/display-mode", json={"display_mode": "RAW"}, headers=login("admin")
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
