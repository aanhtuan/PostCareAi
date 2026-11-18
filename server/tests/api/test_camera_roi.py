"""F08 AC1, AC2, R6: `PUT /cameras/{id}/roi` (chỉ ADMIN, polygon hợp lệ, config_version, audit)."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog, Camera, User
from postcare.domain.security import hash_password
from postcare.schemas.enums import UserRole
from tests.conftest import PASSWORD

Login = Callable[[str], dict[str, str]]
ROI_URL = "/api/v1/cameras/1/roi"
ROI = [[0.15, 0.2], [0.85, 0.2], [0.85, 0.9], [0.15, 0.9]]  # khác DEMO_ROI của seed


def _camera(db: Session, camera_id: int = 1) -> Camera:
    db.expire_all()
    camera = db.get(Camera, camera_id)
    assert camera is not None
    return camera


def _audits(db: Session, action: str) -> list[AuditLog]:
    db.expire_all()
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))


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


def test_put_roi_saves_normalized_polygon(client: TestClient, login: Login, db: Session) -> None:
    version = _camera(db).config_version
    r = client.put(ROI_URL, json={"roi_polygon": ROI}, headers=login("admin"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"camera_id": 1, "roi_polygon": ROI, "config_version": version + 1}
    camera = _camera(db)
    assert camera.roi_polygon == ROI and camera.config_version == version + 1
    # Chi tiết camera (F07) trả ROI mới.
    r = client.get("/api/v1/cameras/1", headers=login("nurse"))
    assert r.json()["roi_polygon"] == ROI


def test_put_roi_audit_before_after(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    before = _camera(db).roi_polygon
    assert client.put(ROI_URL, json={"roi_polygon": ROI}, headers=admin).status_code == 200
    logs = _audits(db, "camera.update_roi")
    assert len(logs) == 1
    log = logs[0]
    assert log.entity_type == "camera" and log.entity_id == 1
    assert log.before is not None and log.after is not None
    assert log.before["roi_polygon"] == before
    assert log.after["roi_polygon"] == ROI
    assert log.after["config_version"] == log.before["config_version"] + 1
    admin_user = db.scalar(select(User).where(User.username == "admin"))
    assert admin_user is not None and log.actor_user_id == admin_user.id


def test_put_roi_same_polygon_is_noop(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    client.put(ROI_URL, json={"roi_polygon": ROI}, headers=admin)
    version = _camera(db).config_version
    r = client.put(ROI_URL, json={"roi_polygon": ROI}, headers=admin)
    assert r.status_code == 200 and r.json()["config_version"] == version
    assert len(_audits(db, "camera.update_roi")) == 1


@pytest.mark.parametrize("username", ["nurse", "charge", "doctor"])
def test_put_roi_requires_admin(
    client: TestClient, login: Login, db: Session, username: str
) -> None:
    before = _camera(db)
    version, roi = before.config_version, before.roi_polygon
    r = client.put(ROI_URL, json={"roi_polygon": ROI}, headers=login(username))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"
    camera = _camera(db)
    assert camera.config_version == version and camera.roi_polygon == roi


def test_put_roi_family_forbidden(client: TestClient, family: dict[str, str], db: Session) -> None:
    version = _camera(db).config_version
    assert client.put(ROI_URL, json={"roi_polygon": ROI}, headers=family).status_code == 403
    assert _camera(db).config_version == version


def test_put_roi_unauthenticated_401(client: TestClient) -> None:
    assert client.put(ROI_URL, json={"roi_polygon": ROI}).status_code == 401


@pytest.mark.parametrize(
    ("points", "reason"),
    [
        ([[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]], "SELF_INTERSECTION"),
        ([[0.1, 0.1], [0.9, 0.1]], "TOO_FEW_POINTS"),
        ([[0.1, 0.1], [1.2, 0.1], [0.5, 0.9]], "OUT_OF_RANGE"),
        ([[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]], "ZERO_AREA"),
        ([[0.1, 0.1], [0.1, 0.1], [0.9, 0.1], [0.5, 0.9]], "DUPLICATE_POINT"),
        ([[0.1, 0.1], ["x", 0.1], [0.5, 0.9]], "INVALID_POINT"),
        ([[0.1, 0.1], [0.9], [0.5, 0.9]], "INVALID_POINT"),
        ([[0.02 * i, 0.5 + 0.1 * (i % 2)] for i in range(21)], "TOO_MANY_POINTS"),
    ],
)
def test_put_roi_invalid_polygon_400(
    client: TestClient, login: Login, db: Session, points: Any, reason: str
) -> None:
    before = _camera(db)
    version, roi = before.config_version, before.roi_polygon
    r = client.put(ROI_URL, json={"roi_polygon": points}, headers=login("admin"))
    assert r.status_code == 400, r.text
    err = r.json()["error"]
    assert err["code"] == "INVALID_ROI_POLYGON"
    assert err["details"]["reason"] == reason
    assert err["message"]
    camera = _camera(db)
    assert camera.config_version == version and camera.roi_polygon == roi
    assert _audits(db, "camera.update_roi") == []


def test_put_roi_self_intersecting_400(client: TestClient, login: Login) -> None:
    bowtie = [[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]]
    r = client.put(ROI_URL, json={"roi_polygon": bowtie}, headers=login("admin"))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_ROI_POLYGON"


def test_put_roi_concave_accepted(client: TestClient, login: Login) -> None:
    concave = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.5, 0.4], [0.1, 0.9]]
    r = client.put(ROI_URL, json={"roi_polygon": concave}, headers=login("admin"))
    assert r.status_code == 200, r.text


def test_put_roi_not_a_list_400(client: TestClient, login: Login) -> None:
    r = client.put(ROI_URL, json={"roi_polygon": "abc"}, headers=login("admin"))
    assert r.status_code in (400, 422)
    assert r.json()["error"]["code"] in ("INVALID_ROI_POLYGON", "VALIDATION_ERROR")


def test_put_roi_unknown_camera_404(client: TestClient, login: Login) -> None:
    r = client.put("/api/v1/cameras/9999/roi", json={"roi_polygon": ROI}, headers=login("admin"))
    assert r.status_code == 404


def test_put_roi_allowed_during_open_session(
    client: TestClient, login: Login, open_session: dict[str, Any]
) -> None:
    r = client.put(ROI_URL, json={"roi_polygon": ROI}, headers=login("admin"))
    assert r.status_code == 200, r.text
