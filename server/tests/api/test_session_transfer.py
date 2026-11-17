"""F04 AC5, AC6: "Chuyển giường" trong một transaction, liên kết phiên, không để trạng thái dở dang.

Dữ liệu seed: giường A01/A02/A03 (id 1–3) có camera 1–3; bệnh nhân BN-001…BN-005 (id 1–5).
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog, Event, MonitoringSession, User
from postcare.domain.notifications import InMemoryPublisher

Login = Callable[[str], dict[str, str]]
SESSIONS = "/api/v1/sessions"


def _start(client: TestClient, headers: dict[str, str], bed_id: int, patient_id: int) -> Any:
    r = client.post(SESSIONS, json={"bed_id": bed_id, "patient_id": patient_id}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _transfer(
    client: TestClient,
    headers: dict[str, str],
    session_id: int,
    target: int,
    reason: Any = "Đổi phòng",
) -> Any:
    body: dict[str, Any] = {"target_bed_id": target}
    if reason is not None:
        body["reason"] = reason
    return client.post(f"{SESSIONS}/{session_id}/transfer", json=body, headers=headers)


def _audits(db: Session) -> list[AuditLog]:
    db.expire_all()
    return list(db.scalars(select(AuditLog).order_by(AuditLog.id)))


def _get(client: TestClient, headers: dict[str, str], session_id: int) -> Any:
    return client.get(f"{SESSIONS}/{session_id}", headers=headers).json()


# ------------------------------------------------------------------------------------ AC5


def test_transfer_ends_old_and_opens_new(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    old = _start(client, nurse, 1, 1)
    r = _transfer(client, login("charge"), old["id"], 2)
    assert r.status_code == 201, r.text
    new = r.json()
    assert (new["bed_code"], new["patient_code"], new["ended_at"]) == ("A02", "BN-001", None)
    assert new["started_by"]["full_name"] == "Trần Văn Minh"
    old_now = _get(client, nurse, old["id"])
    assert old_now["ended_by"]["full_name"] == "Trần Văn Minh"
    assert old_now["ended_at"] == new["started_at"]  # liền mạch, không có khoảng trống
    beds = {b["code"]: b for b in client.get("/api/v1/beds", headers=nurse).json()["items"]}
    assert beds["A01"]["active_session"] is None
    assert beds["A02"]["active_session"]["id"] == new["id"]


def test_transfer_links_sessions(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    old = _start(client, nurse, 1, 1)
    new = _transfer(client, nurse, old["id"], 2, "  Cần phòng yên tĩnh  ").json()
    assert new["previous_session_id"] == old["id"]
    assert new["previous_bed_code"] == "A01"
    assert new["transfer_reason"] == "Cần phòng yên tĩnh"
    assert new["next_session_id"] is None
    old_now = _get(client, nurse, old["id"])
    assert old_now["next_session_id"] == new["id"]
    assert old_now["previous_session_id"] is None


def test_transfer_uses_target_bed_camera(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    old = _start(client, nurse, 1, 1)
    new = _transfer(client, nurse, old["id"], 3).json()
    assert new["camera_id"] == 3
    assert _get(client, nurse, old["id"])["camera_id"] == 1


def test_transfer_to_bed_without_camera(client: TestClient, login: Login) -> None:
    assert (
        client.patch("/api/v1/cameras/3", json={"bed_id": None}, headers=login("admin"))
    ).status_code == 200
    nurse = login("nurse")
    old = _start(client, nurse, 1, 1)
    r = _transfer(client, nurse, old["id"], 3)
    assert r.status_code == 201, r.text
    assert r.json()["camera_id"] is None


def test_transfer_audited_once(
    client: TestClient, login: Login, db: Session, publisher: InMemoryPublisher
) -> None:
    nurse = login("nurse")
    old = _start(client, nurse, 1, 1)
    new = _transfer(client, nurse, old["id"], 2, "Đổi phòng").json()
    logs = _audits(db)
    assert [a.action for a in logs] == ["session.start", "session.transfer"]
    t = logs[1]
    assert (t.entity_type, t.entity_id) == ("session", new["id"])
    assert t.actor_user_id == db.scalar(select(User.id).where(User.username == "nurse"))
    assert t.before == {"session_id": old["id"], "bed_id": 1, "paused_at": None}
    assert t.after == {"session_id": new["id"], "bed_id": 2, "reason": "Đổi phòng"}
    msgs = publisher.messages[-2:]
    assert [(m[0], m[1]["id"]) for m in msgs] == [
        ("session.updated", old["id"]),
        ("session.updated", new["id"]),
    ]


def test_session_chain_ordered(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    s1 = _start(client, nurse, 1, 1)
    s2 = _transfer(client, nurse, s1["id"], 2, "Lần 1").json()
    s3 = _transfer(client, nurse, s2["id"], 3, "Lần 2").json()
    _start(client, nurse, 1, 2)  # phiên khác, không thuộc chuỗi
    doctor = login("doctor")
    for sid in (s1["id"], s2["id"], s3["id"]):
        r = client.get(f"{SESSIONS}/{sid}/chain", headers=doctor)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 3
        assert [(i["id"], i["bed_code"], i["transfer_reason"]) for i in body["items"]] == [
            (s1["id"], "A01", None),
            (s2["id"], "A02", "Lần 1"),
            (s3["id"], "A03", "Lần 2"),
        ]
        assert body["items"][0]["ended_at"] == body["items"][1]["started_at"]
        assert body["items"][2]["ended_at"] is None


def test_chain_of_single_session_and_unknown(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    s = _start(client, nurse, 1, 1)
    body = client.get(f"{SESSIONS}/{s['id']}/chain", headers=nurse).json()
    assert [i["id"] for i in body["items"]] == [s["id"]]
    assert client.get(f"{SESSIONS}/999/chain", headers=nurse).status_code == 404


@pytest.mark.parametrize("username", ["doctor"])
def test_transfer_forbidden_for_doctor(
    client: TestClient, login: Login, db: Session, username: str
) -> None:
    old = _start(client, login("nurse"), 1, 1)
    r = _transfer(client, login(username), old["id"], 2)
    assert r.status_code == 403
    assert _get(client, login("nurse"), old["id"])["ended_at"] is None
    assert [a.action for a in _audits(db)] == ["session.start"]


# ------------------------------------------------------------------------------------ AC6


def _assert_untouched(client: TestClient, login: Login, db: Session, old: Any) -> None:
    nurse = login("nurse")
    now = _get(client, nurse, old["id"])
    assert now["ended_at"] is None and now["next_session_id"] is None
    assert [a.action for a in _audits(db) if a.action == "session.transfer"] == []
    db.expire_all()
    patient_open = db.scalars(
        select(MonitoringSession).where(
            MonitoringSession.patient_id == old["patient_id"], MonitoringSession.ended_at.is_(None)
        )
    ).all()
    assert [s.id for s in patient_open] == [old["id"]]


def test_transfer_target_busy_409_keeps_old_open(
    client: TestClient, login: Login, db: Session, publisher: InMemoryPublisher
) -> None:
    nurse = login("nurse")
    old = _start(client, nurse, 1, 1)
    _start(client, nurse, 2, 2)
    sent = len(publisher.messages)
    r = _transfer(client, nurse, old["id"], 2)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "SESSION_ALREADY_OPEN"
    assert err["details"]["bed_id"] == 2
    _assert_untouched(client, login, db, old)
    assert len(publisher.messages) == sent


def test_transfer_same_bed_400(client: TestClient, login: Login, db: Session) -> None:
    old = _start(client, login("nurse"), 1, 1)
    r = _transfer(client, login("nurse"), old["id"], 1)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    _assert_untouched(client, login, db, old)


def test_transfer_to_deleted_bed_400(client: TestClient, login: Login, db: Session) -> None:
    assert client.delete("/api/v1/beds/3", headers=login("admin")).status_code == 200
    old = _start(client, login("nurse"), 1, 1)
    r = _transfer(client, login("nurse"), old["id"], 3)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    _assert_untouched(client, login, db, old)


def test_transfer_to_unknown_bed_404(client: TestClient, login: Login, db: Session) -> None:
    old = _start(client, login("nurse"), 1, 1)
    r = _transfer(client, login("nurse"), old["id"], 99)
    assert r.status_code == 404
    _assert_untouched(client, login, db, old)


def test_transfer_unknown_session_404(client: TestClient, login: Login) -> None:
    assert _transfer(client, login("nurse"), 999, 2).status_code == 404


def test_transfer_closed_session_409(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    old = _start(client, nurse, 1, 1)
    client.post(f"{SESSIONS}/{old['id']}/end", headers=nurse)
    r = _transfer(client, nurse, old["id"], 2)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SESSION_ALREADY_ENDED"


def test_transfer_twice_from_same_session_409(client: TestClient, login: Login) -> None:
    nurse = login("nurse")
    old = _start(client, nurse, 1, 1)
    assert _transfer(client, nurse, old["id"], 2).status_code == 201
    r = _transfer(client, nurse, old["id"], 3)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SESSION_ALREADY_ENDED"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_transfer_requires_reason(
    client: TestClient, login: Login, db: Session, reason: str | None
) -> None:
    old = _start(client, login("nurse"), 1, 1)
    r = _transfer(client, login("nurse"), old["id"], 2, reason)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    _assert_untouched(client, login, db, old)


def test_transfer_keeps_old_events_on_old_session(
    client: TestClient, login: Login, db: Session, post_event: Callable[..., Any]
) -> None:
    nurse = login("nurse")
    old = _start(client, nurse, 1, 1)
    t = datetime.now(UTC)  # sau lúc mở phiên, trước lúc chuyển
    r = post_event("SIT_UP", "INFO", camera_id=1, occurred_at=t)
    assert r.status_code == 201, r.text
    event_id = r.json()["id"]
    new = _transfer(client, nurse, old["id"], 2).json()
    db.expire_all()
    ev = db.get(Event, event_id)
    assert ev is not None
    assert (ev.session_id, ev.bed_id) == (old["id"], 1)
    old_tl = client.get(f"{SESSIONS}/{old['id']}/timeline", headers=nurse).json()
    assert [i["event_id"] for i in old_tl["items"]] == [event_id]
    new_tl = client.get(f"{SESSIONS}/{new['id']}/timeline", headers=nurse).json()
    assert new_tl["items"] == []
