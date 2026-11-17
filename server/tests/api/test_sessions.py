"""F04 AC1–AC4: mở/kết thúc phiên theo dõi, 1 phiên mở / giường và / bệnh nhân, audit.

Dữ liệu seed: giường A01/A02/A03 (id 1–3) có camera 1–3; bệnh nhân BN-001…BN-005 (id 1–5).
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog, MonitoringSession, User
from postcare.domain.notifications import InMemoryPublisher
from postcare.domain.security import hash_password
from postcare.schemas.enums import UserRole
from tests.conftest import PASSWORD

Login = Callable[[str], dict[str, str]]
SESSIONS = "/api/v1/sessions"


def _start(client: TestClient, headers: dict[str, str], bed_id: int, patient_id: int) -> Any:
    return client.post(SESSIONS, json={"bed_id": bed_id, "patient_id": patient_id}, headers=headers)


def _actions(db: Session) -> list[str]:
    db.expire_all()
    return [a.action for a in db.scalars(select(AuditLog).order_by(AuditLog.id))]


@pytest.fixture
def family(client: TestClient, db: Session, login: Login) -> dict[str, str]:
    db.add(
        User(
            username="family",
            full_name="Người nhà thử nghiệm",
            password_hash=hash_password(PASSWORD),
            role=UserRole.FAMILY,
        )
    )
    db.commit()
    return login("family")


# ------------------------------------------------------------------------------------ AC1


def test_start_session_uses_bed_camera(client: TestClient, login: Login) -> None:
    r = _start(client, login("nurse"), 2, 2)
    assert r.status_code == 201, r.text
    s = r.json()
    assert (s["bed_code"], s["patient_code"], s["camera_id"]) == ("A02", "BN-002", 2)
    assert s["previous_session_id"] is None and s["next_session_id"] is None
    assert s["transfer_reason"] is None and s["paused_at"] is None


def test_start_session_records_actor_and_time(client: TestClient, login: Login) -> None:
    before = datetime.now(UTC)
    r = _start(client, login("charge"), 1, 1)
    assert r.status_code == 201
    s = r.json()
    assert s["started_by"]["full_name"] == "Trần Văn Minh"
    started = datetime.fromisoformat(s["started_at"])
    assert started.tzinfo is not None
    assert before - timedelta(seconds=1) <= started <= datetime.now(UTC) + timedelta(seconds=1)
    assert s["ended_at"] is None and s["ended_by"] is None


def test_start_session_bed_without_camera(client: TestClient, login: Login) -> None:
    r = client.patch("/api/v1/cameras/3", json={"bed_id": None}, headers=login("admin"))
    assert r.status_code == 200, r.text
    r = _start(client, login("nurse"), 3, 3)
    assert r.status_code == 201, r.text
    assert r.json()["camera_id"] is None


def test_doctor_cannot_start_session(client: TestClient, login: Login, db: Session) -> None:
    r = _start(client, login("doctor"), 1, 1)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"
    assert _actions(db) == []


def test_start_session_unknown_bed_or_patient_404(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    for bed_id, patient_id in ((99, 1), (1, 99)):
        r = _start(client, nurse, bed_id, patient_id)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"


def test_start_session_inactive_bed_or_patient_400(client: TestClient, login: Login) -> None:
    admin = login("admin")
    assert client.delete("/api/v1/beds/3", headers=admin).status_code == 200
    assert client.delete("/api/v1/patients/5", headers=admin).status_code == 200
    nurse = login("nurse")
    for bed_id, patient_id in ((3, 1), (1, 5)):
        r = _start(client, nurse, bed_id, patient_id)
        assert r.status_code == 400, r.text
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ------------------------------------------------------------------------------------ AC2


def test_second_open_session_same_bed_409(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    assert _start(client, nurse, 1, 1).status_code == 201
    r = _start(client, nurse, 1, 2)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "SESSION_ALREADY_OPEN"
    assert err["details"] == {"conflict": "bed", "bed_id": 1}


def test_second_open_session_same_patient_409(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    assert _start(client, nurse, 1, 1).status_code == 201
    r = _start(client, nurse, 2, 1)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "SESSION_ALREADY_OPEN"
    assert err["details"] == {"conflict": "patient", "patient_id": 1}


# ------------------------------------------------------------------------------------ AC3


def test_end_session_records_actor_and_time(client: TestClient, login: Login) -> None:
    s = _start(client, login("nurse"), 1, 1).json()
    r = client.post(f"{SESSIONS}/{s['id']}/end", headers=login("admin"))
    assert r.status_code == 200
    out = r.json()
    assert out["ended_by"]["full_name"] == "Phạm Thu Hà"
    assert datetime.fromisoformat(out["ended_at"]) >= datetime.fromisoformat(out["started_at"])


def test_end_closed_session_409(client: TestClient, login: Login, db: Session) -> None:
    nurse = login("nurse")
    s = _start(client, nurse, 1, 1).json()
    assert client.post(f"{SESSIONS}/{s['id']}/end", headers=nurse).status_code == 200
    r = client.post(f"{SESSIONS}/{s['id']}/end", headers=nurse)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SESSION_ALREADY_ENDED"
    assert _actions(db) == ["session.start", "session.end"]


def test_end_unknown_session_404(client: TestClient, login: Login) -> None:
    r = client.post(f"{SESSIONS}/999/end", headers=login("nurse"))
    assert r.status_code == 404


def test_doctor_cannot_end_session(client: TestClient, login: Login) -> None:
    s = _start(client, login("nurse"), 1, 1).json()
    r = client.post(f"{SESSIONS}/{s['id']}/end", headers=login("doctor"))
    assert r.status_code == 403
    assert client.get(f"{SESSIONS}/{s['id']}", headers=login("doctor")).json()["ended_at"] is None


def test_can_reopen_after_end(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    s = _start(client, nurse, 1, 1).json()
    client.post(f"{SESSIONS}/{s['id']}/end", headers=nurse)
    r = _start(client, nurse, 1, 1)
    assert r.status_code == 201
    assert r.json()["id"] != s["id"]


# ------------------------------------------------------------------------------------ AC4


def test_session_start_end_audited(
    client: TestClient, login: Login, db: Session, publisher: InMemoryPublisher
) -> None:
    nurse = login("nurse")
    s = _start(client, nurse, 1, 1).json()
    assert _start(client, nurse, 1, 2).status_code == 409  # thất bại → không có audit
    client.post(f"{SESSIONS}/{s['id']}/end", headers=nurse)
    db.expire_all()
    logs = list(db.scalars(select(AuditLog).order_by(AuditLog.id)))
    assert [(a.action, a.entity_type, a.entity_id) for a in logs] == [
        ("session.start", "session", s["id"]),
        ("session.end", "session", s["id"]),
    ]
    nurse_id = db.scalar(select(User.id).where(User.username == "nurse"))
    assert {a.actor_user_id for a in logs} == {nurse_id}
    assert publisher.types() == ["session.updated", "session.updated"]


# ------------------------------------------------------------------------------------ R7


def test_list_sessions_filters_and_order(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    s1 = _start(client, nurse, 1, 1).json()
    client.post(f"{SESSIONS}/{s1['id']}/end", headers=nurse)
    s2 = _start(client, nurse, 2, 2).json()
    doctor = login("doctor")
    every = client.get(SESSIONS, headers=doctor).json()
    assert [s["id"] for s in every["items"]] == [s2["id"], s1["id"]] and every["total"] == 2
    active = client.get(SESSIONS, params={"active": "true"}, headers=doctor).json()
    assert [s["id"] for s in active["items"]] == [s2["id"]]
    by_bed = client.get(SESSIONS, params={"bed_id": 1}, headers=doctor).json()
    assert [s["id"] for s in by_bed["items"]] == [s1["id"]]
    by_patient = client.get(SESSIONS, params={"patient_id": 2}, headers=doctor).json()
    assert [s["id"] for s in by_patient["items"]] == [s2["id"]]
    page = client.get(SESSIONS, params={"limit": 1, "offset": 1}, headers=doctor).json()
    assert [s["id"] for s in page["items"]] == [s1["id"]] and page["total"] == 2


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/sessions"),
        ("get", "/api/v1/sessions/1"),
        ("get", "/api/v1/sessions/1/chain"),
        ("post", "/api/v1/sessions"),
        ("post", "/api/v1/sessions/1/end"),
        ("post", "/api/v1/sessions/1/transfer"),
        ("post", "/api/v1/sessions/1/pause"),
        ("post", "/api/v1/sessions/1/resume"),
    ],
)
def test_family_forbidden_on_session_endpoints(
    client: TestClient, login: Login, family: dict[str, str], method: str, path: str
) -> None:
    _start(client, login("nurse"), 1, 1)
    bodies = {SESSIONS: {"bed_id": 2, "patient_id": 2}}
    kwargs: dict[str, Any] = {"headers": family}
    if method == "post":
        kwargs["json"] = bodies.get(path, {"target_bed_id": 2, "reason": "x"})
    r = getattr(client, method)(path, **kwargs)
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "FORBIDDEN"


# ----------------------------------------------------------------------- phát sau commit


@pytest.mark.real_commit
def test_session_updates_published_after_commit(app: Any, client: TestClient, login: Login) -> None:
    """Khi publisher được gọi, phiên đã đọc được từ kết nối DB khác (AGENTS.md quy tắc 7)."""
    seen: list[tuple[int, bool, bool, bool]] = []

    class CheckingPublisher:
        def publish(self, type_: str, payload: dict[str, Any]) -> None:
            assert type_ == "session.updated"
            with app.state.session_factory() as other:
                row = other.get(MonitoringSession, payload["id"])
                seen.append(
                    (
                        payload["id"],
                        row is not None,
                        row is not None and (row.ended_at is None) == (payload["ended_at"] is None),
                        row is not None
                        and (row.paused_at is None) == (payload["paused_at"] is None),
                    )
                )

    app.state.hub = CheckingPublisher()
    nurse = login("nurse")
    s = _start(client, nurse, 1, 1).json()
    assert client.post(f"{SESSIONS}/{s['id']}/pause", json={}, headers=nurse).status_code == 200
    assert client.post(f"{SESSIONS}/{s['id']}/resume", headers=nurse).status_code == 200
    r = client.post(
        f"{SESSIONS}/{s['id']}/transfer",
        json={"target_bed_id": 2, "reason": "Đổi phòng"},
        headers=nurse,
    )
    assert r.status_code == 201, r.text
    new = r.json()
    assert client.post(f"{SESSIONS}/{new['id']}/end", headers=nurse).status_code == 200
    ids = [x[0] for x in seen]
    assert ids == [s["id"], s["id"], s["id"], s["id"], new["id"], new["id"]]
    assert all(ok and ended and paused for _, ok, ended, paused in seen), seen
