"""F36 R1: bảng family_access_grants (migration 0007_f36) theo data-model.md."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from postcare.db.models import Bed, FamilyAccessGrant, MonitoringSession, Patient, User
from postcare.domain.seed import seed_base
from postcare.schemas.enums import ShareLevel, UserRole


def test_family_access_grants_columns(test_engine: Engine) -> None:
    insp = inspect(test_engine)
    cols = {c["name"]: c for c in insp.get_columns("family_access_grants")}
    expected = {
        "id": False,
        "session_id": False,
        "user_id": False,
        "share_level": False,
        "consent_note": False,
        "granted_by": False,
        "granted_at": False,
        "expires_at": True,
        "revoked_at": True,
        "revoked_by": True,
    }
    assert set(cols) == set(expected)
    for name, nullable in expected.items():
        assert cols[name]["nullable"] is nullable, name
    assert "INFO" in str(cols["share_level"]["default"])
    fks = {
        (fk["constrained_columns"][0], fk["referred_table"])
        for fk in insp.get_foreign_keys("family_access_grants")
    }
    assert fks == {
        ("session_id", "monitoring_sessions"),
        ("user_id", "users"),
        ("granted_by", "users"),
        ("revoked_by", "users"),
    }
    idx = [i for i in insp.get_indexes("family_access_grants") if i["unique"]]
    assert [tuple(i["column_names"]) for i in idx] == [("session_id", "user_id")]
    assert "revoked_at IS NULL" in str(idx[0]["dialect_options"].get("postgresql_where"))


def test_partial_unique_active_grant(db_session: Session) -> None:
    seed_base(db_session, "x")
    nurse = db_session.scalars(select(User).where(User.username == "nurse")).one()
    fam = User(username="f", full_name="F", password_hash="x", role=UserRole.FAMILY)
    patient = Patient(code="BN-T")
    db_session.add_all([fam, patient])
    db_session.flush()
    now = datetime.now(UTC)
    bed_id = db_session.scalars(select(Bed.id).where(Bed.code == "A01")).one()
    s = MonitoringSession(bed_id=bed_id, patient_id=patient.id, started_at=now, started_by=nurse.id)
    db_session.add(s)
    db_session.flush()

    def _grant(revoked: bool) -> FamilyAccessGrant:
        return FamilyAccessGrant(
            session_id=s.id,
            user_id=fam.id,
            share_level=ShareLevel.INFO,
            consent_note="đồng ý",
            granted_by=nurse.id,
            granted_at=now,
            revoked_at=now if revoked else None,
        )

    db_session.add_all([_grant(True), _grant(True), _grant(False)])
    db_session.flush()  # nhiều quyền đã thu hồi + một quyền đang hiệu lực: hợp lệ
    db_session.add(_grant(False))
    with pytest.raises(IntegrityError):
        db_session.flush()
