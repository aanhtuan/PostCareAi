"""F17: lưu sự kiện idempotent, MEDIUM/HIGH tạo cảnh báo, lưu trước phát sau, camera offline."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from postcare.db.models import Alert, Event
from postcare.db.types import utcnow
from postcare.domain.cameras import mark_offline_cameras
from postcare.domain.notifications import InMemoryPublisher


def _count(db: Session, model: type) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_high_event_creates_pending_alert(
    client: TestClient,
    login,
    open_session,
    post_event,
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    publisher.messages.clear()
    r = post_event("BED_EXIT", "HIGH")
    assert r.status_code == 201
    assert r.json()["created"] is True
    alerts = client.get("/api/v1/alerts", headers=login("nurse")).json()
    assert alerts["total"] == 1
    a = alerts["items"][0]
    assert a["status"] == "PENDING" and a["outcome"] is None
    assert a["event"]["code"] == "BED_EXIT" and a["event"]["priority"] == "HIGH"
    assert a["bed"]["code"] == "A01" and a["session"]["patient_code"] == "BN-001"
    assert publisher.types() == ["event.created", "alert.created"]


def test_medium_creates_alert_info_and_log_do_not(
    open_session,
    post_event,
    db: Session,
) -> None:
    assert post_event("BED_EDGE", "MEDIUM").status_code == 201
    assert post_event("SIT_UP", "INFO").status_code == 201
    assert post_event("POSTURE_CHANGE", "LOG").status_code == 201
    assert _count(db, Event) == 3
    assert _count(db, Alert) == 1


def test_event_is_idempotent_by_uid(
    open_session,
    post_event,
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    uid = str(uuid.uuid4())
    first = post_event("BED_EXIT", "HIGH", event_uid=uid)
    publisher.messages.clear()
    second = post_event("BED_EXIT", "HIGH", event_uid=uid)
    assert first.status_code == 201 and second.status_code == 200
    assert second.json() == {"id": first.json()["id"], "created": False}
    assert _count(db, Event) == 1
    assert _count(db, Alert) == 1
    assert publisher.messages == []


def test_invalid_priority_or_api_only_code_rejected(open_session, post_event) -> None:
    r = post_event("BED_EXIT", "LOG")
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = post_event("CAMERA_OFFLINE", "MEDIUM")
    assert r.status_code == 400
    assert post_event("FACE_ATTENTION", "HIGH").status_code == 201
    assert post_event("FACE_ATTENTION", "MEDIUM").status_code == 201


def test_event_without_open_session_is_409(client: TestClient, post_event) -> None:
    r = post_event("BED_EXIT", "HIGH")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "NO_ACTIVE_SESSION"


@pytest.mark.real_commit
def test_publish_happens_after_commit(
    app: Any,
    client: TestClient,
    open_session,
    post_event,
) -> None:
    """Khi publisher được gọi, dữ liệu đã đọc được từ một kết nối DB khác (HS §4.2)."""
    seen: list[tuple[str, bool]] = []

    class CheckingPublisher:
        def publish(self, type_: str, payload: dict[str, Any]) -> None:
            with app.state.session_factory() as other:
                if type_ == "event.created":
                    seen.append((type_, other.get(Event, payload["id"]) is not None))
                elif type_ == "alert.created":
                    seen.append((type_, other.get(Alert, payload["alert"]["id"]) is not None))

    app.state.hub = CheckingPublisher()
    assert post_event("BED_EXIT", "HIGH").status_code == 201
    assert seen == [("event.created", True), ("alert.created", True)]


def test_bed_state_kept_in_memory_and_published(
    client: TestClient,
    login,
    worker_headers,
    publisher: InMemoryPublisher,
) -> None:
    r = client.post(
        "/internal/v1/cameras/1/state",
        headers=worker_headers,
        json={"body_state": "SITTING", "observation_quality": "GOOD"},
    )
    assert r.status_code == 200
    assert publisher.types() == ["bed.state"]
    beds = client.get("/api/v1/overview", headers=login("nurse")).json()["beds"]
    assert beds[0]["state"]["body_state"] == "SITTING"
    assert beds[1]["state"] is None


def test_camera_offline_creates_medium_alert_then_online(
    app: Any,
    client: TestClient,
    open_session,
    worker_headers,
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    assert client.post(
        "/internal/v1/cameras/1/heartbeat", headers=worker_headers, json={"fps": 15}
    ).json() == {"config_version": 1}
    changed = mark_offline_cameras(
        db, app.state.store, publisher, offline_after_s=5, now=utcnow() + timedelta(seconds=10)
    )
    assert changed == [1]
    db.expire_all()
    ev = db.scalar(select(Event).where(Event.code == "CAMERA_OFFLINE"))
    assert ev is not None and ev.priority == "MEDIUM" and ev.alert is not None
    assert app.state.store.get_bed_state(1).body_state == "NO_OBSERVATION"

    client.post("/internal/v1/cameras/1/heartbeat", headers=worker_headers, json={})
    db.expire_all()
    online = db.scalar(select(Event).where(Event.code == "CAMERA_ONLINE"))
    assert online is not None and online.alert is None
