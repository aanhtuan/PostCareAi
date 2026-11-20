"""F17 AC3, AC5 (R8–R11): `POST /internal/v1/events`."""

import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from postcare.db.models import Alert, Camera, Event
from postcare.domain.notifications import InMemoryPublisher
from postcare.schemas.enums import ObservationProfile
from tests.conftest import WORKER_TOKEN


def _count(db: Session, model: type) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model)) or 0


def _body(code: str = "BED_EXIT", priority: str = "HIGH", **kw: Any) -> dict[str, Any]:
    t = datetime.now(UTC)
    body = {
        "event_uid": str(uuid.uuid4()),
        "camera_id": 1,
        "code": code,
        "priority": priority,
        "occurred_at": t.isoformat(),
        "detected_at": (t + timedelta(milliseconds=300)).isoformat(),
        "confidence": 0.9,
        "observation_quality": "GOOD",
        "explanation": {"rule_id": "body.bed_exit"},
        "config_hash": "h",
    }
    body.update(kw)
    return body


def test_same_event_uid_twice_single_row(
    open_session: Any, post_event: Any, db: Session, publisher: InMemoryPublisher
) -> None:
    uid = str(uuid.uuid4())
    publisher.messages.clear()
    first = post_event("BED_EXIT", "HIGH", event_uid=uid)
    assert first.status_code == 201 and first.json()["created"] is True
    assert publisher.types() == ["event.created", "alert.created"]
    second = post_event("BED_EXIT", "HIGH", event_uid=uid)
    assert second.status_code == 200
    assert second.json() == {"id": first.json()["id"], "created": False}
    assert _count(db, Event) == 1
    assert _count(db, Alert) == 1
    assert publisher.types() == ["event.created", "alert.created"]  # không phát thêm


@pytest.mark.real_commit
def test_concurrent_same_event_uid_single_row(
    app: Any, client: TestClient, open_session: Any
) -> None:
    """Hai request cùng `event_uid` đến cùng lúc: một dòng, một 201, một 200, phát một lần."""
    body = _body()
    results: list[tuple[int, dict[str, Any]]] = []
    barrier = threading.Barrier(2)

    def send() -> None:
        barrier.wait()
        r = client.post("/internal/v1/events", headers={"X-Worker-Token": WORKER_TOKEN}, json=body)
        results.append((r.status_code, r.json()))

    threads = [threading.Thread(target=send) for _ in range(2)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert sorted(s for s, _ in results) == [200, 201]
    assert len({r["id"] for _, r in results}) == 1
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Event)) == 1
        assert db.scalar(select(func.count()).select_from(Alert)) == 1
    assert app.state.hub.types().count("event.created") == 1


def test_engine_event_without_session_rejected(post_event: Any, db: Session) -> None:
    r = post_event("SIT_UP", "INFO")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "NO_ACTIVE_SESSION"
    assert _count(db, Event) == 0


@pytest.mark.parametrize("headers", [{}, {"X-Worker-Token": "sai-token"}])
def test_wrong_worker_token_401(
    client: TestClient, open_session: Any, headers: dict[str, str], db: Session
) -> None:
    r = client.post("/internal/v1/events", headers=headers, json=_body())
    assert r.status_code == 401
    assert _count(db, Event) == 0


@pytest.mark.parametrize(
    ("code", "priority"),
    [
        ("BED_EXIT", "LOG"),
        ("BED_EDGE", "HIGH"),
        ("OBSERVATION_LOST", "MEDIUM"),
        ("CAMERA_OFFLINE", "MEDIUM"),  # chỉ API sinh
        ("CAMERA_ONLINE", "LOG"),
    ],
)
def test_invalid_code_or_priority_400(
    client: TestClient,
    open_session: Any,
    worker_headers: dict[str, str],
    db: Session,
    code: str,
    priority: str,
) -> None:
    r = client.post("/internal/v1/events", headers=worker_headers, json=_body(code, priority))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _count(db, Event) == 0


def test_camera_unknown_or_without_bed_400(
    client: TestClient, open_session: Any, worker_headers: dict[str, str], db: Session
) -> None:
    r = client.post("/internal/v1/events", headers=worker_headers, json=_body(camera_id=999))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    # F38: hồ sơ theo dõi giường mà không gắn giường → 400.
    db.execute(
        update(Camera)
        .where(Camera.id == 2)
        .values(bed_id=None, observation_profile=ObservationProfile.BED_MONITORING)
    )
    db.commit()
    r = client.post("/internal/v1/events", headers=worker_headers, json=_body(camera_id=2))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _count(db, Event) == 0


def test_abnormal_movement_camera_without_bed_records_event(
    client: TestClient, worker_headers: dict[str, str], db: Session
) -> None:
    """F38 R: hồ sơ chuyển động bất thường ghi được sự kiện khi camera không gắn giường."""
    db.execute(
        update(Camera)
        .where(Camera.id == 2)
        .values(bed_id=None, observation_profile=ObservationProfile.ABNORMAL_MOVEMENT)
    )
    db.commit()
    r = client.post(
        "/internal/v1/events",
        headers=worker_headers,
        json=_body(camera_id=2, code="ABNORMAL_MOVEMENT", priority="HIGH"),
    )
    assert r.status_code == 201, r.text
    ev = db.scalars(select(Event)).one()
    assert ev.bed_id is None and ev.session_id is None


def test_unknown_code_422(
    client: TestClient, open_session: Any, worker_headers: dict[str, str]
) -> None:
    r = client.post("/internal/v1/events", headers=worker_headers, json=_body("NOT_A_CODE", "HIGH"))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_non_uuid_event_uid_400(
    client: TestClient, open_session: Any, worker_headers: dict[str, str]
) -> None:
    r = client.post(
        "/internal/v1/events", headers=worker_headers, json=_body(event_uid="not-a-uuid-xx")
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
