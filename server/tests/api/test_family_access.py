"""F36 AC2–AC6 (REST): người nhà chỉ xem đúng phiên được cấp, dữ liệu đã lọc, không có ảnh."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog
from tests.api.family_utils import (
    FakeClock,
    Login,
    assert_no_image,
    grant_ok,
    revoke,
    start_session,
)

FAMILY = "/api/v1/family/grants"
KEYPOINTS = {
    "nose": [0.5, 0.3, 0.9],
    "left_shoulder": [0.45, 0.4, 0.95],
    "right_shoulder": [0.55, 0.4, 0.95],
}


def _state(client: TestClient, worker_headers: dict[str, str], camera_id: int = 1, **extra: Any):
    body = {
        "body_state": "SITTING",
        "observation_quality": "GOOD",
        "activity_level": "NORMAL",
        "rest_status": "ACTIVE",
        "face_status": "OK",
        **extra,
    }
    return client.post(f"/internal/v1/cameras/{camera_id}/state", headers=worker_headers, json=body)


def _views(db: Session) -> list[AuditLog]:
    db.expire_all()
    return list(
        db.scalars(
            select(AuditLog).where(AuditLog.action == "family_access.view").order_by(AuditLog.id)
        )
    )


# AC2 -------------------------------------------------------------------------


def _staff_requests(token: str) -> list[tuple[str, str]]:
    return [
        ("GET", "/api/v1/overview"),
        ("GET", "/api/v1/alerts"),
        ("POST", "/api/v1/alerts/1/acknowledge"),
        ("GET", "/api/v1/timeline"),
        ("GET", "/api/v1/sessions/1/timeline"),
        ("GET", "/api/v1/handover"),
        ("GET", "/api/v1/beds"),
        ("GET", "/api/v1/sessions/1/family-grants"),
        ("POST", "/api/v1/sessions/1/pause"),
        ("GET", f"/api/v1/cameras/1/stream.mjpeg?token={token}"),
    ]


@pytest.mark.parametrize("idx", range(10))
def test_family_forbidden_on_staff_endpoints(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int, idx: int
) -> None:
    grant_ok(client, login, open_session["id"], fam, share_level="SKELETON")
    headers = login("family")
    token = headers["Authorization"].split(" ", 1)[1]
    method, path = _staff_requests(token)[idx]
    r = client.request(method, path, headers=headers)
    assert r.status_code == 403, (path, r.text)
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_family_endpoints_forbidden_for_staff(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    for user in ("nurse", "charge", "doctor", "admin"):
        for path in (FAMILY, f"{FAMILY}/{gid}/view", f"{FAMILY}/{gid}/timeline"):
            assert client.get(path, headers=login(user)).status_code == 403


def test_family_other_grant_403(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int, fam2: int
) -> None:
    grant_ok(client, login, open_session["id"], fam)
    other_session = start_session(client, login, 2, 2)
    other = grant_ok(client, login, other_session, fam2)
    for path in (f"{FAMILY}/{other}/view", f"{FAMILY}/{other}/timeline", f"{FAMILY}/9999/view"):
        r = client.get(path, headers=login("family"))
        assert r.status_code == 403, path
        assert r.json()["error"]["code"] == "FORBIDDEN"


def test_family_grants_lists_only_own_active(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int, fam2: int
) -> None:
    mine = grant_ok(client, login, open_session["id"], fam, share_level="SKELETON")
    grant_ok(client, login, start_session(client, login, 2, 2), fam2)
    r = client.get(FAMILY, headers=login("family"))
    assert r.status_code == 200
    items = r.json()["items"]
    assert [g["id"] for g in items] == [mine]
    assert items[0]["bed_code"] == "A01"
    assert items[0]["share_level"] == "SKELETON"
    assert "patient_code" not in repr(items) and "BN-" not in repr(items)


def test_family_view_audited_once_per_request(
    client: TestClient, login: Login, db: Session, open_session: dict[str, Any], fam: int
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    for _ in range(2):
        assert client.get(f"{FAMILY}/{gid}/view", headers=login("family")).status_code == 200
    client.get(f"{FAMILY}/{gid}/timeline", headers=login("family"))
    client.get(FAMILY, headers=login("family"))
    views = _views(db)
    assert len(views) == 2
    assert all(
        (v.entity_type, v.entity_id, v.actor_user_id) == ("family_access_grant", gid, fam)
        for v in views
    )


def test_family_view_has_no_patient_or_face(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    fam: int,
    worker_headers: dict[str, str],
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    assert _state(client, worker_headers).status_code == 200
    r = client.get(f"{FAMILY}/{gid}/view", headers=login("family"))
    body = r.json()
    assert set(body) == {
        "grant_id",
        "bed_code",
        "session_started_at",
        "share_level",
        "capture_paused",
        "state",
        "skeleton",
    }
    assert body["bed_code"] == "A01"
    assert set(body["state"]) == {
        "body_state",
        "observation_quality",
        "activity_level",
        "rest_status",
        "capture_paused",
        "updated_at",
    }
    assert body["state"]["body_state"] == "SITTING"
    assert "BN-001" not in r.text and "face" not in r.text


# AC3 -------------------------------------------------------------------------


def test_family_view_after_revoke_403(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    assert revoke(client, login, gid).status_code == 200
    for path in (f"{FAMILY}/{gid}/view", f"{FAMILY}/{gid}/timeline"):
        r = client.get(path, headers=login("family"))
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "FAMILY_ACCESS_ENDED"
    assert client.get(FAMILY, headers=login("family")).json()["items"] == []


def test_family_view_expired_403(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int, clock: FakeClock
) -> None:
    gid = grant_ok(
        client, login, open_session["id"], fam, expires_at=clock.now + timedelta(minutes=30)
    )
    assert client.get(f"{FAMILY}/{gid}/view", headers=login("family")).status_code == 200
    clock.now += timedelta(minutes=30)  # expires_at = now → hết hiệu lực
    r = client.get(f"{FAMILY}/{gid}/view", headers=login("family"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FAMILY_ACCESS_ENDED"


# AC4 -------------------------------------------------------------------------


def test_grant_ends_when_session_ends(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    sid = open_session["id"]
    gid = grant_ok(client, login, sid, fam)
    assert client.post(f"/api/v1/sessions/{sid}/end", headers=login("nurse")).status_code == 200
    r = client.get(f"{FAMILY}/{gid}/view", headers=login("family"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FAMILY_ACCESS_ENDED"
    staff = client.get(f"/api/v1/sessions/{sid}/family-grants", headers=login("nurse")).json()
    assert staff["items"][0]["end_reason"] == "SESSION_ENDED"


def _transfer(client: TestClient, login: Login, sid: int) -> int:
    r = client.post(
        f"/api/v1/sessions/{sid}/transfer",
        json={"target_bed_id": 2, "reason": "Đổi phòng"},
        headers=login("nurse"),
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def test_old_session_grant_invalid_after_transfer(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    _transfer(client, login, open_session["id"])
    r = client.get(f"{FAMILY}/{gid}/view", headers=login("family"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FAMILY_ACCESS_ENDED"


def test_new_session_after_transfer_requires_new_grant(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    grant_ok(client, login, open_session["id"], fam)
    new_sid = _transfer(client, login, open_session["id"])
    assert client.get(FAMILY, headers=login("family")).json()["items"] == []
    gid = grant_ok(client, login, new_sid, fam)
    view = client.get(f"{FAMILY}/{gid}/view", headers=login("family"))
    assert view.status_code == 200
    assert view.json()["bed_code"] == "A02"


def test_account_locked_ends_access(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    headers = login("family")
    assert client.post(f"/api/v1/users/{fam}/lock", headers=login("admin")).status_code == 200
    assert client.get(f"{FAMILY}/{gid}/view", headers=headers).status_code == 401
    staff = client.get(
        f"/api/v1/sessions/{open_session['id']}/family-grants", headers=login("nurse")
    ).json()
    assert staff["items"][0]["end_reason"] == "ACCOUNT_LOCKED"


# Timeline (R10) ----------------------------------------------------------------


def test_family_timeline_filtered(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    fam: int,
    post_event: Callable[..., Any],
) -> None:
    sid = open_session["id"]
    gid = grant_ok(client, login, sid, fam)
    t0 = datetime.fromisoformat(open_session["started_at"])  # sự kiện ngay sau khi mở phiên
    ms = timedelta(milliseconds=1)
    assert post_event("POSTURE_CHANGE", "LOG", occurred_at=t0 + ms).status_code == 201
    assert post_event("SIT_UP", "INFO", occurred_at=t0 + 2 * ms).status_code == 201
    r = post_event("BED_EXIT", "HIGH", occurred_at=t0 + 3 * ms)
    assert r.status_code == 201
    alerts = client.get("/api/v1/alerts", headers=login("nurse")).json()["items"]
    alert_id = alerts[0]["id"]
    nurse = login("nurse")
    assert client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=nurse).status_code == 200
    # Sự kiện ở giường khác không được lọt vào timeline người nhà.
    start_session(client, login, 2, 2)
    assert post_event("STAND_UP", "INFO", camera_id=2).status_code == 201
    assert (
        client.post(
            f"/api/v1/sessions/{sid}/pause", json={"reason": "Thay đồ"}, headers=nurse
        ).status_code
        == 200
    )
    assert client.post(f"/api/v1/sessions/{sid}/resume", headers=nurse).status_code == 200

    r = client.get(f"{FAMILY}/{gid}/timeline", headers=login("family"))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    kinds = [(i["kind"], i["code"]) for i in items]
    assert kinds == [
        ("event", "SIT_UP"),
        ("event", "BED_EXIT"),
        ("capture_paused", None),
        ("capture_resumed", None),
    ]
    assert items[1]["alert_status"] == "ACKNOWLEDGED"
    assert set(items[0]) == {"time", "kind", "event_id", "code", "priority", "alert_status"}
    text = r.text
    for bad in ("Nguyễn Thị Hoa", "Thay đồ", "explanation", "rule_id", "note", "BN-"):
        assert bad not in text, bad


# AC5 -------------------------------------------------------------------------


def test_skeleton_level_view_has_keypoints_info_does_not(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    fam: int,
    fam2: int,
    worker_headers: dict[str, str],
) -> None:
    sid = open_session["id"]
    skel = grant_ok(client, login, sid, fam, share_level="SKELETON")
    info = grant_ok(client, login, sid, fam2)
    assert _state(client, worker_headers, target_keypoints=KEYPOINTS).status_code == 200
    body = client.get(f"{FAMILY}/{skel}/view", headers=login("family")).json()
    assert body["skeleton"]["keypoints"] == KEYPOINTS
    assert body["skeleton"]["roi_polygon"] is not None
    assert_no_image(body)
    body2 = client.get(f"{FAMILY}/{info}/view", headers=login("family2")).json()
    assert body2["skeleton"] is None
    assert "nose" not in repr(body2)


def test_skeleton_null_when_no_target(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    fam: int,
    worker_headers: dict[str, str],
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam, share_level="SKELETON")
    r = _state(client, worker_headers, observation_quality="MULTIPLE_PEOPLE", target_keypoints=None)
    assert r.status_code == 200
    body = client.get(f"{FAMILY}/{gid}/view", headers=login("family")).json()
    assert body["skeleton"]["keypoints"] is None


def test_target_keypoints_validated(client: TestClient, worker_headers: dict[str, str]) -> None:
    bad = {"nose": [1.5, 0.2, 0.9]}
    assert _state(client, worker_headers, target_keypoints=bad).status_code == 422
    assert (
        _state(client, worker_headers, target_keypoints={"tail": [0.1, 0.1, 1]}).status_code == 422
    )


def test_family_rest_payloads_have_no_image(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    fam: int,
    worker_headers: dict[str, str],
    post_event: Callable[..., Any],
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam, share_level="SKELETON")
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100
    client.post(
        "/internal/v1/cameras/1/frame",
        headers={**worker_headers, "Content-Type": "image/jpeg"},
        content=jpeg,
    )
    _state(client, worker_headers, target_keypoints=KEYPOINTS)
    post_event("SIT_UP", "INFO")
    for path in (FAMILY, f"{FAMILY}/{gid}/view", f"{FAMILY}/{gid}/timeline"):
        r = client.get(path, headers=login("family"))
        assert r.status_code == 200
        assert_no_image(r.json())
        assert b"\xff\xd8" not in r.content


# AC6 -------------------------------------------------------------------------


def test_family_view_shows_paused(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    sid = open_session["id"]
    gid = grant_ok(client, login, sid, fam)
    assert (
        client.post(f"/api/v1/sessions/{sid}/pause", json={}, headers=login("nurse")).status_code
        == 200
    )
    body = client.get(f"{FAMILY}/{gid}/view", headers=login("family")).json()
    assert body["capture_paused"] is True
    assert client.get(FAMILY, headers=login("family")).json()["items"][0]["capture_paused"] is True


def test_state_and_frame_ignored_while_paused(
    app: Any,
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    worker_headers: dict[str, str],
) -> None:
    sid = open_session["id"]
    assert _state(client, worker_headers, body_state="LYING").status_code == 200
    assert (
        client.post(f"/api/v1/sessions/{sid}/pause", json={}, headers=login("nurse")).status_code
        == 200
    )
    before = len(app.state.hub.messages)
    assert _state(client, worker_headers, body_state="STANDING").status_code == 200
    r = client.post(
        "/internal/v1/cameras/1/frame",
        headers={**worker_headers, "Content-Type": "image/jpeg"},
        content=b"\xff\xd8\xff\xe0" + b"0" * 100,
    )
    assert r.status_code == 204
    assert app.state.store.get_bed_state(1).body_state == "LYING"
    assert app.state.frames.get(1) is None
    assert app.state.hub.messages[before:] == []
