"""F06: API nội bộ cho worker: config, heartbeat, frame (AC1, AC2, AC4)."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from postcare.db.models import Camera, Event
from postcare.db.types import utcnow
from postcare.domain.cameras import mark_offline_cameras
from postcare.domain.notifications import InMemoryPublisher

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


def _hb(client: TestClient, headers: dict[str, str], **body: Any) -> Any:
    return client.post("/internal/v1/cameras/1/heartbeat", headers=headers, json=body)


def _frame(
    client: TestClient, headers: dict[str, str], data: bytes, ctype: str = "image/jpeg"
) -> Any:
    return client.post(
        "/internal/v1/cameras/1/frame",
        headers={**headers, "Content-Type": ctype},
        content=data,
    )


# ---- AC1 -------------------------------------------------------------------------------------


def test_internal_config_returns_camera_config(client: TestClient, worker_headers) -> None:
    r = client.get("/internal/v1/cameras/1/config", headers=worker_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {
        "camera_id",
        "bed_id",
        "source_type",
        "source",
        "roi_polygon",
        "thresholds",
        "display_mode",
        "config_version",
        "active_session_id",
        "capture_paused",
    }
    assert body["camera_id"] == 1 and body["bed_id"] == 1
    assert body["active_session_id"] is None


def test_internal_config_includes_active_session(
    client: TestClient, worker_headers, open_session
) -> None:
    r = client.get("/internal/v1/cameras/1/config", headers=worker_headers)
    assert r.json()["active_session_id"] == open_session["id"]


def test_internal_config_unknown_or_inactive_camera_404(
    client: TestClient, worker_headers, db: Session
) -> None:
    assert client.get("/internal/v1/cameras/999/config", headers=worker_headers).status_code == 404
    db.execute(update(Camera).where(Camera.id == 2).values(is_active=False))
    db.commit()
    assert client.get("/internal/v1/cameras/2/config", headers=worker_headers).status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("GET", "/internal/v1/cameras/1/config", {}),
        ("POST", "/internal/v1/cameras/1/heartbeat", {"json": {}}),
        (
            "POST",
            "/internal/v1/cameras/1/frame",
            {"content": JPEG, "headers": {"Content-Type": "image/jpeg"}},
        ),
    ],
)
@pytest.mark.parametrize("token", [None, "sai-token"])
def test_internal_endpoints_require_worker_token(
    client: TestClient, method: str, path: str, kwargs: dict[str, Any], token: str | None
) -> None:
    headers = dict(kwargs.pop("headers", {}))
    if token is not None:
        headers["X-Worker-Token"] = token
    r = client.request(method, path, headers=headers, **kwargs)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


# ---- AC2 -------------------------------------------------------------------------------------


def test_heartbeat_sets_online_and_last_seen(
    client: TestClient, worker_headers, db: Session
) -> None:
    before = utcnow()
    r = _hb(
        client, worker_headers, fps=14.5, brightness=120.0, dropped_frames=3, source_status="ONLINE"
    )
    assert r.status_code == 200
    assert r.json() == {"config_version": 1}
    db.expire_all()
    cam = db.get(Camera, 1)
    assert cam is not None
    assert cam.status == "ONLINE"
    assert cam.last_seen_at is not None and cam.last_seen_at >= before - timedelta(seconds=1)


def test_heartbeat_source_offline_sets_offline(
    app: Any,
    client: TestClient,
    worker_headers,
    open_session,
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    _hb(client, worker_headers, source_status="ONLINE")
    r = _hb(client, worker_headers, source_status="OFFLINE")
    assert r.status_code == 200
    db.expire_all()
    cam = db.get(Camera, 1)
    assert cam is not None and cam.status == "OFFLINE"
    # Worker còn sống: last_seen_at vẫn cập nhật; chuyển ONLINE → OFFLINE sinh CAMERA_OFFLINE.
    ev = db.scalar(select(Event).where(Event.code == "CAMERA_OFFLINE"))
    assert ev is not None and ev.explanation["reason"] == "source_offline"
    assert app.state.store.get_bed_state(1).body_state == "NO_OBSERVATION"
    # Nguồn có lại → ONLINE.
    _hb(client, worker_headers, source_status="ONLINE")
    db.expire_all()
    assert db.get(Camera, 1).status == "ONLINE"  # type: ignore[union-attr]


def test_heartbeat_paused_keeps_online(client: TestClient, worker_headers, db: Session) -> None:
    _hb(client, worker_headers, source_status="ONLINE")
    _hb(client, worker_headers, source_status="PAUSED")
    db.expire_all()
    assert db.get(Camera, 1).status == "ONLINE"  # type: ignore[union-attr]


def test_heartbeat_4s_apart_stays_online(
    app: Any, client: TestClient, worker_headers, db: Session, publisher: InMemoryPublisher
) -> None:
    _hb(client, worker_headers, source_status="ONLINE")
    db.expire_all()
    seen = db.get(Camera, 1).last_seen_at  # type: ignore[union-attr]
    assert seen is not None
    changed = mark_offline_cameras(
        db, app.state.store, publisher, offline_after_s=5, now=seen + timedelta(seconds=4)
    )
    assert changed == []
    db.expire_all()
    assert db.get(Camera, 1).status == "ONLINE"  # type: ignore[union-attr]


def test_stale_camera_marked_offline(
    app: Any, client: TestClient, worker_headers, db: Session, publisher: InMemoryPublisher
) -> None:
    _hb(client, worker_headers, source_status="ONLINE")
    db.expire_all()
    seen = db.get(Camera, 1).last_seen_at  # type: ignore[union-attr]
    assert seen is not None
    changed = mark_offline_cameras(
        db, app.state.store, publisher, offline_after_s=5, now=seen + timedelta(seconds=6)
    )
    assert changed == [1]
    db.expire_all()
    assert db.get(Camera, 1).status == "OFFLINE"  # type: ignore[union-attr]


def test_runtime_exposed_on_camera_detail(client: TestClient, worker_headers, login) -> None:
    r = client.get("/api/v1/cameras/1", headers=login("nurse"))
    assert r.status_code == 200
    assert r.json()["runtime"] is None
    _hb(
        client, worker_headers, fps=14.5, brightness=120.5, dropped_frames=3, source_status="ONLINE"
    )
    runtime = client.get("/api/v1/cameras/1", headers=login("nurse")).json()["runtime"]
    assert runtime["fps"] == 14.5
    assert runtime["brightness"] == 120.5
    assert runtime["dropped_frames"] == 3
    assert runtime["source_status"] == "ONLINE"
    assert runtime["updated_at"]


# ---- AC4 -------------------------------------------------------------------------------------


def test_frame_buffer_keeps_latest_only(app: Any, client: TestClient, worker_headers) -> None:
    first = JPEG + b"1"
    second = JPEG + b"2"
    assert _frame(client, worker_headers, first).status_code == 204
    assert _frame(client, worker_headers, second).status_code == 204
    latest = app.state.frames.get(1)
    assert latest is not None
    assert latest.data == second
    assert latest.received_at is not None
    assert app.state.frames.count() == 1


def test_frame_buffer_unit() -> None:
    from postcare.api.frame_buffer import LatestFrameStore

    store = LatestFrameStore()
    assert store.get(1) is None
    store.put(1, b"a")
    store.put(1, b"b")
    store.put(2, b"c")
    assert store.get(1).data == b"b"  # type: ignore[union-attr]
    assert store.count() == 2


def test_frame_post_does_not_write_disk(
    client: TestClient, worker_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def snapshot() -> set[str]:
        return {str(p) for p in tmp_path.rglob("*")}

    before = snapshot()
    for i in range(10):
        assert _frame(client, worker_headers, JPEG + bytes([i])).status_code == 204
    assert snapshot() == before


def test_frame_too_large_or_wrong_type_400(client: TestClient, worker_headers, settings) -> None:
    big = JPEG + b"\x00" * settings.frame_max_bytes
    r = _frame(client, worker_headers, big)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _frame(client, worker_headers, b"{}", "application/json").status_code == 400
    assert _frame(client, worker_headers, b"").status_code == 400


def test_frame_unknown_camera_404(client: TestClient, worker_headers) -> None:
    r = client.post(
        "/internal/v1/cameras/999/frame",
        headers={**worker_headers, "Content-Type": "image/jpeg"},
        content=JPEG,
    )
    assert r.status_code == 404
