"""F09 AC1, AC2 (R1, R2, R4): `GET /api/v1/overview` – thẻ giường, phiên, camera, ca hiện tại."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from postcare.db.models import Bed, Camera, ShiftDefinition, User
from postcare.domain.cameras import mark_offline_cameras
from postcare.domain.notifications import InMemoryPublisher
from postcare.domain.security import hash_password
from postcare.schemas.enums import CameraStatus, UserRole
from tests.conftest import PASSWORD

Login = Callable[[str], dict[str, str]]
OVERVIEW = "/api/v1/overview"


def _beds(client: TestClient, headers: dict[str, str]) -> dict[str, dict[str, Any]]:
    r = client.get(OVERVIEW, headers=headers)
    assert r.status_code == 200, r.text
    return {b["code"]: b for b in r.json()["beds"]}


def test_overview_lists_active_beds_with_session_and_camera(
    client: TestClient, login: Login, db: Session, open_session: dict[str, Any]
) -> None:
    a03 = db.scalars(select(Bed).where(Bed.code == "A03")).one()
    a03.is_active = False  # ca âm: giường ngừng dùng không xuất hiện
    cam2 = db.scalars(select(Camera).where(Camera.name == "Camera A02")).one()
    cam2.status = CameraStatus.OFFLINE
    a01_cam = db.scalars(select(Camera).where(Camera.name == "Camera A01")).one()
    a01_cam.status = CameraStatus.ONLINE
    a04 = Bed(code="A00", area_id=a03.area_id)  # giường không có camera, mã đứng đầu
    db.add(a04)
    db.commit()

    body = client.get(OVERVIEW, headers=login("nurse")).json()
    codes = [b["code"] for b in body["beds"]]
    assert codes == ["A00", "A01", "A02"]  # sắp theo mã, không có A03
    a00, a01, a02 = body["beds"]
    assert a00["camera"] is None and a00["session"] is None
    assert isinstance(a01["area"], str) and a01["area"]
    assert a01["camera"] == {"id": a01_cam.id, "name": "Camera A01", "status": "ONLINE"}
    assert a01["session"]["id"] == open_session["id"]
    assert a01["session"]["patient_code"] == "BN-001"
    assert a01["session"]["started_at"] is not None
    assert a01["session"]["paused_at"] is None
    assert a02["camera"]["status"] == "OFFLINE"
    assert a02["session"] is None


def test_overview_current_shift_shape(client: TestClient, login: Login) -> None:
    shift = client.get(OVERVIEW, headers=login("doctor")).json()["current_shift"]
    # Ca mẫu phủ kín 24 giờ nên luôn có ca hiện tại (giờ Asia/Ho_Chi_Minh).
    assert shift is not None
    assert {"id", "name", "start_time", "end_time"} <= shift.keys()
    assert shift["name"] in {"Ca sáng", "Ca chiều", "Ca đêm"}


def test_overview_no_shift_is_null(client: TestClient, login: Login, db: Session) -> None:
    db.execute(update(ShiftDefinition).values(is_active=False))  # ca đã xóa không tính
    db.commit()
    assert client.get(OVERVIEW, headers=login("nurse")).json()["current_shift"] is None


def test_overview_session_paused_at(
    client: TestClient, login: Login, open_session: dict[str, Any]
) -> None:
    nurse = login("nurse")
    sid = open_session["id"]
    assert client.post(f"/api/v1/sessions/{sid}/pause", json={}, headers=nurse).status_code == 200
    assert _beds(client, nurse)["A01"]["session"]["paused_at"] is not None
    assert client.post(f"/api/v1/sessions/{sid}/resume", headers=nurse).status_code == 200
    assert _beds(client, nurse)["A01"]["session"]["paused_at"] is None


def test_overview_requires_staff(client: TestClient, login: Login, db: Session) -> None:
    assert client.get(OVERVIEW).status_code == 401
    for username in ("nurse", "charge", "doctor", "admin"):
        assert client.get(OVERVIEW, headers=login(username)).status_code == 200
    db.add(
        User(
            username="family",
            full_name="Người nhà thử nghiệm",
            password_hash=hash_password(PASSWORD),
            role=UserRole.FAMILY,
        )
    )
    db.commit()
    r = client.get(OVERVIEW, headers=login("family"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_overview_camera_online_to_offline_sets_no_observation(
    app: Any,
    client: TestClient,
    login: Login,
    db: Session,
    worker_headers: dict[str, str],
    open_session: dict[str, Any],
    publisher: InMemoryPublisher,
) -> None:
    hb = "/internal/v1/cameras/1/heartbeat"
    r = client.post(hb, headers=worker_headers, json={"source_status": "ONLINE"})
    assert r.status_code == 200
    assert _beds(client, login("nurse"))["A01"]["camera"]["status"] == "ONLINE"
    db.expire_all()
    seen = db.get(Camera, 1).last_seen_at  # type: ignore[union-attr]
    assert seen is not None
    mark_offline_cameras(
        db, app.state.store, publisher, offline_after_s=5, now=seen + timedelta(seconds=6)
    )
    a01 = _beds(client, login("nurse"))["A01"]
    assert a01["camera"]["status"] == "OFFLINE"
    # Mất camera: không đủ dữ liệu quan sát, không bao giờ là rời giường (AGENTS.md quy tắc 6).
    assert a01["state"]["body_state"] == "NO_OBSERVATION"
