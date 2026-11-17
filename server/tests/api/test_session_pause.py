"""F04 AC7 (R19–R22; F36 R15–R18 phần phiên): tạm dừng / tiếp tục thu hình theo phiên."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog
from postcare.domain.notifications import InMemoryPublisher

Login = Callable[[str], dict[str, str]]
SESSIONS = "/api/v1/sessions"


def _pause(client: TestClient, headers: dict[str, str], sid: int, body: Any = None) -> Any:
    return client.post(
        f"{SESSIONS}/{sid}/pause", json=body if body is not None else {}, headers=headers
    )


def _resume(client: TestClient, headers: dict[str, str], sid: int) -> Any:
    return client.post(f"{SESSIONS}/{sid}/resume", headers=headers)


def _audits(db: Session) -> list[AuditLog]:
    db.expire_all()
    return list(db.scalars(select(AuditLog).order_by(AuditLog.id)))


def test_pause_resume_audited(
    client: TestClient,
    login: Login,
    db: Session,
    open_session: dict[str, Any],
    publisher: InMemoryPublisher,
) -> None:
    sid = open_session["id"]
    r = _pause(client, login("charge"), sid, {"reason": "Thay đồ"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["paused_at"] is not None
    assert out["paused_by"]["full_name"] == "Trần Văn Minh"
    r = _resume(client, login("nurse"), sid)
    assert r.status_code == 200
    assert r.json()["paused_at"] is None and r.json()["paused_by"] is None
    logs = _audits(db)
    assert [a.action for a in logs] == ["session.start", "session.pause", "session.resume"]
    pause, resume = logs[1], logs[2]
    assert (pause.entity_type, pause.entity_id) == ("session", sid)
    assert pause.after is not None
    assert pause.after["reason"] == "Thay đồ"
    assert datetime.fromisoformat(pause.after["paused_at"]) == datetime.fromisoformat(
        out["paused_at"]
    )
    assert resume.before is not None and resume.before["paused_at"] is not None
    assert publisher.types()[-2:] == ["session.updated", "session.updated"]


def test_pause_without_reason(
    client: TestClient, login: Login, open_session: dict[str, Any]
) -> None:
    r = client.post(f"{SESSIONS}/{open_session['id']}/pause", headers=login("nurse"))
    assert r.status_code == 200, r.text


def test_pause_twice_409(
    client: TestClient, login: Login, db: Session, open_session: dict[str, Any]
) -> None:
    nurse = login("nurse")
    assert _pause(client, nurse, open_session["id"]).status_code == 200
    r = _pause(client, nurse, open_session["id"])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SESSION_ALREADY_PAUSED"
    assert [a.action for a in _audits(db)].count("session.pause") == 1


def test_resume_when_not_paused_409(
    client: TestClient, login: Login, db: Session, open_session: dict[str, Any]
) -> None:
    r = _resume(client, login("nurse"), open_session["id"])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SESSION_NOT_PAUSED"
    assert [a.action for a in _audits(db)] == ["session.start"]


def test_pause_or_resume_ended_session_409(
    client: TestClient, login: Login, open_session: dict[str, Any]
) -> None:
    nurse = login("nurse")
    client.post(f"{SESSIONS}/{open_session['id']}/end", headers=nurse)
    for r in (
        _pause(client, nurse, open_session["id"]),
        _resume(client, nurse, open_session["id"]),
    ):
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "SESSION_ALREADY_ENDED"


def test_pause_unknown_session_404(client: TestClient, login: Login) -> None:
    assert _pause(client, login("nurse"), 999).status_code == 404
    assert _resume(client, login("nurse"), 999).status_code == 404


def test_pause_forbidden_for_doctor(
    client: TestClient, login: Login, open_session: dict[str, Any]
) -> None:
    doctor = login("doctor")
    assert _pause(client, doctor, open_session["id"]).status_code == 403
    assert _pause(client, login("nurse"), open_session["id"]).status_code == 200
    assert _resume(client, doctor, open_session["id"]).status_code == 403


def test_end_while_paused_clears_pause(
    client: TestClient, login: Login, db: Session, open_session: dict[str, Any]
) -> None:
    nurse = login("nurse")
    _pause(client, nurse, open_session["id"])
    r = client.post(f"{SESSIONS}/{open_session['id']}/end", headers=nurse)
    assert r.status_code == 200
    assert r.json()["paused_at"] is None
    end = _audits(db)[-1]
    assert end.action == "session.end"
    assert end.before is not None and end.before["paused_at"] is not None


def test_transfer_while_paused_new_session_not_paused(
    client: TestClient, login: Login, open_session: dict[str, Any]
) -> None:
    nurse = login("nurse")
    _pause(client, nurse, open_session["id"])
    r = client.post(
        f"{SESSIONS}/{open_session['id']}/transfer",
        json={"target_bed_id": 2, "reason": "Đổi phòng"},
        headers=nurse,
    )
    assert r.status_code == 201, r.text
    assert r.json()["paused_at"] is None
    old = client.get(f"{SESSIONS}/{open_session['id']}", headers=nurse).json()
    assert old["paused_at"] is None and old["ended_at"] is not None


def test_internal_config_reports_capture_paused(
    client: TestClient, login: Login, worker_headers: dict[str, str], open_session: dict[str, Any]
) -> None:
    def cfg(camera_id: int) -> Any:
        r = client.get(f"/internal/v1/cameras/{camera_id}/config", headers=worker_headers)
        assert r.status_code == 200, r.text
        return r.json()

    assert cfg(1)["capture_paused"] is False
    assert cfg(2)["capture_paused"] is False  # giường không có phiên
    _pause(client, login("nurse"), open_session["id"])
    assert cfg(1)["capture_paused"] is True
    assert cfg(1)["active_session_id"] == open_session["id"]
    assert cfg(2)["capture_paused"] is False
    _resume(client, login("nurse"), open_session["id"])
    assert cfg(1)["capture_paused"] is False


def test_engine_event_rejected_while_paused(
    client: TestClient, login: Login, open_session: dict[str, Any], post_event: Callable[..., Any]
) -> None:
    before_pause = datetime.now(UTC) - timedelta(seconds=1)
    _pause(client, login("nurse"), open_session["id"])
    r = post_event("BED_EXIT", "HIGH")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CAPTURE_PAUSED"
    # sự kiện xảy ra trước lúc tạm dừng, gửi muộn: vẫn nhận (R22)
    assert post_event("SIT_UP", "INFO", occurred_at=before_pause).status_code == 201
    _resume(client, login("nurse"), open_session["id"])
    assert post_event("BED_EXIT", "HIGH").status_code == 201


@pytest.mark.parametrize("body", [{"reason": "x" * 1001}, {"other": 1}])
def test_pause_body_validated(
    client: TestClient, login: Login, open_session: dict[str, Any], body: dict[str, Any]
) -> None:
    r = _pause(client, login("nurse"), open_session["id"], body)
    assert r.status_code == 422
