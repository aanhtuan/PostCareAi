"""F03 AC1, AC2: camera (nguồn theo loại, 1 camera / giường, config_version)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog

CAMERAS = "/api/v1/cameras"


def _new_bed(client: TestClient, admin: dict[str, str], code: str = "B01") -> int:
    r = client.post("/api/v1/beds", json={"code": code, "area": "Khu"}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_admin_crud_cameras(client: TestClient, login, db: Session) -> None:
    admin = login("admin")
    bed_id = _new_bed(client, admin)
    r = client.post(
        CAMERAS,
        json={
            "name": "Camera B01",
            "source_type": "URL",
            "source": "rtsp://10.0.0.5/live",
            "bed_id": bed_id,
        },
        headers=admin,
    )
    assert r.status_code == 201, r.text
    cam = r.json()
    assert cam["bed_id"] == bed_id and cam["bed_code"] == "B01"
    assert cam["source_type"] == "URL" and cam["config_version"] == 1 and cam["is_active"] is True

    r = client.patch(f"{CAMERAS}/{cam['id']}", json={"name": "Camera giường B01"}, headers=admin)
    assert r.status_code == 200 and r.json()["name"] == "Camera giường B01"
    r = client.get(f"{CAMERAS}/{cam['id']}", headers=login("doctor"))
    assert r.status_code == 200 and r.json()["name"] == "Camera giường B01"

    # Camera không gắn giường.
    r = client.post(
        CAMERAS,
        json={"name": "Dự phòng", "source_type": "FILE", "source": "data/a.mp4"},
        headers=admin,
    )
    assert r.status_code == 201 and r.json()["bed_id"] is None

    db.expire_all()
    actions = [
        a.action
        for a in db.scalars(
            select(AuditLog).where(AuditLog.entity_type == "camera").order_by(AuditLog.id)
        )
    ]
    assert actions == ["camera.create", "camera.update", "camera.create"]


@pytest.mark.parametrize(
    ("source_type", "source"),
    [
        ("WEBCAM", "abc"),
        ("WEBCAM", "-1"),
        ("WEBCAM", ""),
        ("URL", "ftp://x"),
        ("URL", "10.0.0.5/live"),
        ("FILE", "   "),
    ],
)
def test_camera_source_validated_by_type(
    client: TestClient, login, source_type: str, source: str
) -> None:
    r = client.post(
        CAMERAS,
        json={"name": "C", "source_type": source_type, "source": source},
        headers=login("admin"),
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert r.json()["error"]["details"]["field"] == "source"


@pytest.mark.parametrize(
    ("source_type", "source"),
    [
        ("WEBCAM", "0"),
        ("WEBCAM", "2"),
        ("URL", "http://x/y"),
        ("URL", "https://x"),
        ("FILE", "a.mp4"),
    ],
)
def test_camera_source_valid_values(
    client: TestClient, login, source_type: str, source: str
) -> None:
    r = client.post(
        CAMERAS,
        json={"name": "C", "source_type": source_type, "source": source},
        headers=login("admin"),
    )
    assert r.status_code == 201, r.text


def test_patch_changing_type_revalidates_source(client: TestClient, login) -> None:
    # Camera 1 là WEBCAM "0"; đổi sang URL mà không đổi nguồn → nguồn "0" không hợp lệ.
    r = client.patch(f"{CAMERAS}/1", json={"source_type": "URL"}, headers=login("admin"))
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_second_camera_same_bed_409(client: TestClient, login) -> None:
    admin = login("admin")
    r = client.post(
        CAMERAS,
        json={"name": "C2", "source_type": "WEBCAM", "source": "1", "bed_id": 1},
        headers=admin,
    )
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "BED_ALREADY_HAS_CAMERA" and err["details"]["camera_id"] == 1
    # Chuyển camera 2 sang giường 1 (đã có camera 1) cũng bị chặn.
    r = client.patch(f"{CAMERAS}/2", json={"bed_id": 1}, headers=admin)
    assert r.status_code == 409 and r.json()["error"]["code"] == "BED_ALREADY_HAS_CAMERA"
    # Gán lại đúng giường của chính nó thì không xung đột.
    r = client.patch(f"{CAMERAS}/1", json={"bed_id": 1}, headers=admin)
    assert r.status_code == 200


def test_camera_unknown_or_deleted_bed(client: TestClient, login) -> None:
    admin = login("admin")
    r = client.post(
        CAMERAS,
        json={"name": "C", "source_type": "WEBCAM", "source": "1", "bed_id": 999},
        headers=admin,
    )
    assert r.status_code == 404
    bed_id = _new_bed(client, admin, "B02")
    assert client.delete(f"/api/v1/beds/{bed_id}", headers=admin).status_code == 200
    r = client.post(
        CAMERAS,
        json={"name": "C", "source_type": "WEBCAM", "source": "1", "bed_id": bed_id},
        headers=admin,
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("patch", "bumps"),
    [
        ({"source": "1"}, True),
        ({"source_type": "FILE", "source": "a.mp4"}, True),
        ({"bed_id": None}, True),
        ({"name": "Tên mới"}, False),
        ({"source": "0"}, False),  # giá trị không đổi
    ],
)
def test_camera_update_bumps_config_version(
    client: TestClient, login, patch: dict[str, Any], bumps: bool
) -> None:
    admin = login("admin")
    before = client.get(f"{CAMERAS}/1", headers=admin).json()["config_version"]
    r = client.patch(f"{CAMERAS}/1", json=patch, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["config_version"] == before + (1 if bumps else 0)


def test_camera_move_to_free_bed(client: TestClient, login) -> None:
    admin = login("admin")
    bed_id = _new_bed(client, admin)
    r = client.patch(f"{CAMERAS}/3", json={"bed_id": bed_id}, headers=admin)
    assert r.status_code == 200 and r.json()["bed_code"] == "B01"
    beds = {b["code"]: b for b in client.get("/api/v1/beds", headers=admin).json()["items"]}
    assert beds["A03"]["camera"] is None
    assert beds["B01"]["camera"]["id"] == 3


def test_camera_rejects_unknown_fields(client: TestClient, login) -> None:
    r = client.patch(f"{CAMERAS}/1", json={"status": "ONLINE"}, headers=login("admin"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
