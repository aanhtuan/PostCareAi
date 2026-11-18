"""F36 AC1 (R1–R4, R6): cấp, liệt kê, thu hồi quyền xem của người nhà; audit."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog
from postcare.domain.notifications import InMemoryPublisher
from tests.api.family_utils import (
    FakeClock,
    Login,
    grant,
    grant_ok,
    revoke,
)


def _audits(db: Session, prefix: str = "family_access.") -> list[AuditLog]:
    db.expire_all()
    return list(
        db.scalars(select(AuditLog).where(AuditLog.action.startswith(prefix)).order_by(AuditLog.id))
    )


@pytest.mark.parametrize("by", ["charge", "admin"])
def test_grant_default_level_info(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int, by: str
) -> None:
    r = grant(client, login, open_session["id"], fam, by=by)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["share_level"] == "INFO"
    assert out["session_id"] == open_session["id"]
    assert out["user"]["id"] == fam
    assert out["active"] is True
    assert out["end_reason"] is None
    assert out["revoked_at"] is None
    assert out["expires_at"] is None


def test_grant_skeleton_level(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    r = grant(client, login, open_session["id"], fam, share_level="SKELETON")
    assert r.status_code == 201, r.text
    assert r.json()["share_level"] == "SKELETON"


def test_grant_and_revoke_audited(
    client: TestClient,
    login: Login,
    db: Session,
    open_session: dict[str, Any],
    fam: int,
    publisher: InMemoryPublisher,
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam, share_level="SKELETON")
    r = revoke(client, login, gid)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["revoked_at"] is not None
    assert out["revoked_by"]["full_name"] == "Trần Văn Minh"
    assert out["active"] is False
    assert out["end_reason"] == "REVOKED"
    logs = _audits(db)
    assert [a.action for a in logs] == ["family_access.grant", "family_access.revoke"]
    g, rv = logs
    assert (g.entity_type, g.entity_id) == ("family_access_grant", gid)
    assert g.after is not None
    assert g.after["session_id"] == open_session["id"]
    assert g.after["user_id"] == fam
    assert g.after["share_level"] == "SKELETON"
    assert g.after["consent_note"].startswith("Bệnh nhân đồng ý")
    assert "expires_at" in g.after
    assert rv.before == {"revoked_at": None}
    assert rv.after is not None
    assert rv.after["revoked_at"] is not None
    assert rv.after["reason"] == "Gia đình yêu cầu"
    # Sau commit: hub được báo để ngắt luồng của grant (R14).
    assert ("family.grant_ended", {"grant_id": gid, "user_id": fam, "reason": "REVOKED"}) in (
        publisher.messages
    )


@pytest.mark.parametrize("by", ["nurse", "doctor", "family"])
def test_grant_requires_charge_nurse_or_admin(
    client: TestClient, login: Login, db: Session, open_session: dict[str, Any], fam: int, by: str
) -> None:
    r = grant(client, login, open_session["id"], fam, by=by)
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "FORBIDDEN"
    assert _audits(db) == []


@pytest.mark.parametrize("by", ["nurse", "doctor", "family"])
def test_revoke_requires_charge_nurse_or_admin(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int, by: str
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    r = revoke(client, login, gid, by=by)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize("target", ["nurse", "inactive", "missing"])
def test_grant_to_non_family_user_400(
    client: TestClient, login: Login, db: Session, open_session: dict[str, Any], target: str
) -> None:
    from tests.api.family_utils import add_family_user

    if target == "nurse":
        from postcare.db.models import User

        user_id = db.scalars(select(User.id).where(User.username == "nurse")).one()
    elif target == "inactive":
        user_id = add_family_user(db, "locked", active=False)
    else:
        user_id = 99999
    r = grant(client, login, open_session["id"], user_id)
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("note", ["", "   "])
def test_grant_requires_consent_note(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int, note: str
) -> None:
    r = grant(client, login, open_session["id"], fam, consent_note=note)
    assert r.status_code in (400, 422)
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_grant_expires_in_past_400(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int, clock: FakeClock
) -> None:
    r = grant(client, login, open_session["id"], fam, expires_at=clock.now - timedelta(minutes=1))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_grant_on_ended_session_409(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    sid = open_session["id"]
    assert client.post(f"/api/v1/sessions/{sid}/end", headers=login("nurse")).status_code == 200
    r = grant(client, login, sid, fam)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SESSION_ALREADY_ENDED"


def test_grant_unknown_session_404(client: TestClient, login: Login, fam: int) -> None:
    assert grant(client, login, 9999, fam).status_code == 404


def test_duplicate_active_grant_409(
    client: TestClient, login: Login, db: Session, open_session: dict[str, Any], fam: int
) -> None:
    grant_ok(client, login, open_session["id"], fam)
    r = grant(client, login, open_session["id"], fam, share_level="SKELETON")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "FAMILY_GRANT_ALREADY_ACTIVE"
    assert [a.action for a in _audits(db)] == ["family_access.grant"]


def test_grant_again_after_revoke(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    assert revoke(client, login, gid).status_code == 200
    assert grant(client, login, open_session["id"], fam).status_code == 201


def test_regrant_after_expiry(
    client: TestClient,
    login: Login,
    db: Session,
    open_session: dict[str, Any],
    fam: int,
    clock: FakeClock,
) -> None:
    """Quyền cũ hết hạn nhưng chưa thu hồi: cấp lại được (hệ thống đóng quyền cũ, giả định)."""
    sid = open_session["id"]
    old = grant_ok(client, login, sid, fam, expires_at=clock.now + timedelta(minutes=5))
    clock.now += timedelta(minutes=10)
    new = grant_ok(client, login, sid, fam)
    assert new != old
    items = {
        g["id"]: g
        for g in client.get(f"/api/v1/sessions/{sid}/family-grants", headers=login("nurse")).json()[
            "items"
        ]
    }
    assert items[old]["active"] is False
    assert items[old]["end_reason"] in ("EXPIRED", "REVOKED")
    assert items[new]["active"] is True
    actions = [(a.action, a.actor_user_id) for a in _audits(db)]
    assert actions[:2] == [("family_access.grant", actions[0][1]), ("family_access.revoke", None)]


def test_revoke_twice_409(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    gid = grant_ok(client, login, open_session["id"], fam)
    assert revoke(client, login, gid).status_code == 200
    r = revoke(client, login, gid)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "FAMILY_GRANT_NOT_ACTIVE"


def test_revoke_expired_409(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int, clock: FakeClock
) -> None:
    gid = grant_ok(
        client, login, open_session["id"], fam, expires_at=clock.now + timedelta(minutes=1)
    )
    clock.now += timedelta(minutes=2)
    r = revoke(client, login, gid)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "FAMILY_GRANT_NOT_ACTIVE"


def test_revoke_unknown_404(client: TestClient, login: Login) -> None:
    assert revoke(client, login, 9999).status_code == 404


@pytest.mark.parametrize("by", ["nurse", "charge", "doctor", "admin"])
def test_list_grants_staff(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int, fam2: int, by: str
) -> None:
    sid = open_session["id"]
    gid = grant_ok(client, login, sid, fam)
    grant_ok(client, login, sid, fam2)
    assert revoke(client, login, gid).status_code == 200
    r = client.get(f"/api/v1/sessions/{sid}/family-grants", headers=login(by))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert {g["active"] for g in body["items"]} == {True, False}  # gồm cả quyền đã hết


def test_list_grants_forbidden_for_family(
    client: TestClient, login: Login, open_session: dict[str, Any], fam: int
) -> None:
    r = client.get(f"/api/v1/sessions/{open_session['id']}/family-grants", headers=login("family"))
    assert r.status_code == 403


@pytest.mark.parametrize(("by", "status"), [("charge", 200), ("admin", 200), ("nurse", 403)])
def test_family_accounts_list(
    client: TestClient, login: Login, db: Session, fam: int, by: str, status: int
) -> None:
    from tests.api.family_utils import add_family_user

    add_family_user(db, "locked", active=False)
    r = client.get("/api/v1/family-grants/accounts", headers=login(by))
    assert r.status_code == status
    if status == 200:
        assert [a["username"] for a in r.json()["items"]] == ["family"]
        assert set(r.json()["items"][0]) == {"id", "username", "full_name"}


def test_internal_config_share_skeleton(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    fam: int,
    fam2: int,
    worker_headers: dict[str, str],
) -> None:
    """Worker chỉ gửi keypoint khi phiên có quyền mức SKELETON đang hiệu lực (tối thiểu hóa)."""

    def cfg() -> dict[str, Any]:
        return client.get("/internal/v1/cameras/1/config", headers=worker_headers).json()

    assert cfg()["share_skeleton"] is False
    grant_ok(client, login, open_session["id"], fam)
    assert cfg()["share_skeleton"] is False
    gid = grant_ok(client, login, open_session["id"], fam2, share_level="SKELETON")
    assert cfg()["share_skeleton"] is True
    assert revoke(client, login, gid).status_code == 200
    assert cfg()["share_skeleton"] is False
