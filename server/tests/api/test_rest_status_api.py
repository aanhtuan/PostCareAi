"""F27 AC3 (API): `rest_status` chỉ là trạng thái hiển thị, không tạo sự kiện hay cảnh báo."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from postcare.db.models import Alert, Event
from postcare.domain.notifications import InMemoryPublisher


def _count(db: Session, model: type) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_state_with_rest_status_creates_no_alert(
    client: TestClient,
    login,
    open_session,
    worker_headers,
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    publisher.messages.clear()
    for rest in ("RESTING", "ACTIVE", "RESTING", "UNKNOWN"):
        r = client.post(
            "/internal/v1/cameras/1/state",
            headers=worker_headers,
            json={
                "body_state": "LYING",
                "observation_quality": "GOOD",
                "activity_level": "LOW",
                "rest_status": rest,
                "face_status": "OK",
            },
        )
        assert r.status_code == 200
    assert _count(db, Event) == 0
    assert _count(db, Alert) == 0
    assert set(publisher.types()) == {"bed.state"}
    beds = client.get("/api/v1/overview", headers=login("nurse")).json()["beds"]
    assert beds[0]["state"]["rest_status"] == "UNKNOWN"
