"""F36 R5: bảng chân trị hiệu lực quyền xem của người nhà với đồng hồ giả."""

from datetime import UTC, datetime, timedelta

import pytest
from postcare.domain.family_access import grant_end_reason, is_grant_active

from postcare.db.models import FamilyAccessGrant, MonitoringSession, User
from postcare.schemas.enums import FamilyAccessEndReason, ShareLevel, UserRole

NOW = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)


def _grant(
    *,
    revoked: bool = False,
    expires_at: datetime | None = None,
    session_ended: bool = False,
    user_active: bool = True,
    role: UserRole = UserRole.FAMILY,
) -> FamilyAccessGrant:
    session = MonitoringSession(
        bed_id=1,
        patient_id=1,
        started_at=NOW - timedelta(hours=1),
        started_by=1,
        ended_at=NOW - timedelta(minutes=1) if session_ended else None,
    )
    user = User(username="f", full_name="F", password_hash="x", role=role, is_active=user_active)
    return FamilyAccessGrant(
        session=session,
        user=user,
        share_level=ShareLevel.INFO,
        consent_note="đồng ý",
        granted_by=1,
        granted_at=NOW - timedelta(minutes=30),
        expires_at=expires_at,
        revoked_at=NOW - timedelta(minutes=5) if revoked else None,
    )


def test_active_grant() -> None:
    g = _grant()
    assert grant_end_reason(g, NOW) is None
    assert is_grant_active(g, NOW)


def test_future_expiry_still_active() -> None:
    assert grant_end_reason(_grant(expires_at=NOW + timedelta(seconds=1)), NOW) is None


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"revoked": True}, FamilyAccessEndReason.REVOKED),
        ({"session_ended": True}, FamilyAccessEndReason.SESSION_ENDED),
        ({"user_active": False}, FamilyAccessEndReason.ACCOUNT_LOCKED),
        ({"role": UserRole.NURSE}, FamilyAccessEndReason.ACCOUNT_LOCKED),
        ({"expires_at": NOW}, FamilyAccessEndReason.EXPIRED),  # expires_at = now → hết hiệu lực
        ({"expires_at": NOW - timedelta(seconds=1)}, FamilyAccessEndReason.EXPIRED),
    ],
)
def test_inactive_grants(kwargs: dict, reason: FamilyAccessEndReason) -> None:
    g = _grant(**kwargs)
    assert grant_end_reason(g, NOW) is reason
    assert not is_grant_active(g, NOW)


def test_revoked_takes_precedence_over_expiry() -> None:
    g = _grant(revoked=True, expires_at=NOW - timedelta(hours=1), session_ended=True)
    assert grant_end_reason(g, NOW) is FamilyAccessEndReason.REVOKED
