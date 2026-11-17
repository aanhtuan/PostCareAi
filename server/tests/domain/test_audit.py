"""F01 AC5 (R12): helper `record_audit()` dùng chung, chỉ INSERT, không tự commit."""

from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import postcare.domain.audit as audit_module
from postcare.db.models import AuditLog, User
from postcare.domain.audit import record_audit
from postcare.schemas.enums import UserRole


def _user(db: Session) -> User:
    u = User(username="audit-u", full_name="Người thử", password_hash="x", role=UserRole.NURSE)
    db.add(u)
    db.flush()
    return u


def _count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(AuditLog)) or 0


def test_record_audit_inserts_row(db_session: Session) -> None:
    user = _user(db_session)
    record_audit(
        db_session,
        actor_user_id=user.id,
        action="camera.update_roi",
        entity_type="camera",
        entity_id=7,
        before={"roi_polygon": None},
        after={"roi_polygon": [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]]},
    )
    db_session.commit()
    row = db_session.scalars(select(AuditLog)).one()
    assert (row.actor_user_id, row.action, row.entity_type, row.entity_id) == (
        user.id,
        "camera.update_roi",
        "camera",
        7,
    )
    assert row.before == {"roi_polygon": None}
    assert row.after == {"roi_polygon": [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]]}
    assert row.created_at.tzinfo is not None


def test_record_audit_system_actor(db_session: Session) -> None:
    record_audit(
        db_session, actor_user_id=None, action="alert.create", entity_type="alert", entity_id=1
    )
    db_session.commit()
    row = db_session.scalars(select(AuditLog)).one()
    assert row.actor_user_id is None and row.before is None and row.after is None


def test_record_audit_rolls_back_with_transaction(db_session: Session) -> None:
    """Ca âm tính: nghiệp vụ rollback thì audit cũng không còn (cùng một transaction)."""
    user = _user(db_session)
    db_session.commit()
    record_audit(
        db_session, actor_user_id=user.id, action="bed.delete", entity_type="bed", entity_id=3
    )
    db_session.rollback()
    assert _count(db_session) == 0


def test_record_audit_does_not_commit(db_session: Session) -> None:
    record_audit(db_session, actor_user_id=None, action="x.y", entity_type="bed", entity_id=1)
    assert db_session.in_transaction()
    assert any(isinstance(o, AuditLog) for o in db_session.new), "chỉ thêm vào session"


def test_record_audit_serializes_datetime_utc(db_session: Session) -> None:
    ict = timezone(timedelta(hours=7))
    record_audit(
        db_session,
        actor_user_id=None,
        action="session.end",
        entity_type="session",
        entity_id=1,
        before={"ended_at": None},
        after={
            "ended_at": datetime(2026, 11, 17, 9, 30, tzinfo=ict),
            "shift": {"start": time(6, 0)},
            "role": UserRole.NURSE,
        },
    )
    db_session.commit()
    row = db_session.scalars(select(AuditLog)).one()
    assert row.after == {
        "ended_at": "2026-11-17T02:30:00+00:00",
        "shift": {"start": "06:00:00"},
        "role": "NURSE",
    }


def test_record_audit_rejects_naive_datetime(db_session: Session) -> None:
    with pytest.raises(ValueError):
        record_audit(
            db_session,
            actor_user_id=None,
            action="x.y",
            entity_type="bed",
            entity_id=1,
            after={"t": datetime(2026, 1, 1)},
        )


def test_audit_module_has_no_update_or_delete() -> None:
    """Bảng chỉ INSERT (data-model.md): module không có hàm sửa/xóa."""
    public = [n for n in dir(audit_module) if callable(getattr(audit_module, n))]
    assert not [n for n in public if "update" in n.lower() or "delete" in n.lower()]
