"""F04: phiên theo dõi, 1 phiên mở / giường, audit, thông báo session.updated."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog
from postcare.domain.notifications import InMemoryPublisher


def test_start_and_end_session(
    client: TestClient,
    login,
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    nurse = login("nurse")
    r = client.post("/api/v1/sessions", json={"bed_id": 1, "patient_id": 1}, headers=nurse)
    assert r.status_code == 201
    s = r.json()
    assert s["bed_code"] == "A01" and s["patient_code"] == "BN-001"
    assert s["camera_id"] == 1
    assert s["started_by"]["full_name"]

    beds = client.get("/api/v1/beds", headers=nurse).json()
    assert beds[0]["active_session"]["id"] == s["id"]

    r = client.post(f"/api/v1/sessions/{s['id']}/end", headers=nurse)
    assert r.status_code == 200
    assert r.json()["ended_at"] is not None

    r = client.post(f"/api/v1/sessions/{s['id']}/end", headers=nurse)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SESSION_ALREADY_ENDED"

    actions = [a.action for a in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert actions == ["session.start", "session.end"]
    assert publisher.types() == ["session.updated", "session.updated"]


def test_one_open_session_per_bed_and_patient(client: TestClient, login) -> None:
    nurse = login("nurse")
    assert (
        client.post("/api/v1/sessions", json={"bed_id": 1, "patient_id": 1}, headers=nurse)
    ).status_code == 201
    r = client.post("/api/v1/sessions", json={"bed_id": 1, "patient_id": 2}, headers=nurse)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SESSION_ALREADY_OPEN"
    assert r.json()["error"]["details"]["conflict"] == "bed"
    r = client.post("/api/v1/sessions", json={"bed_id": 2, "patient_id": 1}, headers=nurse)
    assert r.status_code == 409
    assert r.json()["error"]["details"]["conflict"] == "patient"


def test_unknown_bed_is_404(client: TestClient, login) -> None:
    r = client.post(
        "/api/v1/sessions", json={"bed_id": 99, "patient_id": 1}, headers=login("nurse")
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
