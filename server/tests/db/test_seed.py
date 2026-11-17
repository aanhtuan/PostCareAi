"""F01 AC2 (R7–R9): seed dữ liệu mẫu idempotent, mật khẩu đã hash."""

from datetime import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from postcare.db.models import Bed, Camera, ShiftDefinition, User
from postcare.domain.security import verify_password
from postcare.domain.seed import seed_base
from postcare.schemas.enums import CameraSourceType, UserRole

PW = "seed-pass"


def _counts(db: Session) -> dict[str, int]:
    return {
        m.__tablename__: db.scalar(select(func.count()).select_from(m)) or 0
        for m in (User, Bed, Camera, ShiftDefinition)
    }


def test_seed_creates_sample_data(db_session: Session) -> None:
    seed_base(db_session, PW)
    beds = db_session.scalars(select(Bed).order_by(Bed.code)).all()
    assert [b.code for b in beds] == ["A01", "A02", "A03"]
    assert {b.area for b in beds} == {"Khu hậu phẫu"}
    cams = db_session.scalars(select(Camera)).all()
    assert len(cams) == 1
    cam = cams[0]
    assert cam.bed_id == beds[0].id and cam.name == "Camera A01"
    assert cam.source_type == CameraSourceType.WEBCAM and cam.source == "0"
    users = {u.username: u.role for u in db_session.scalars(select(User))}
    assert users == {
        "nurse": UserRole.NURSE,
        "charge": UserRole.CHARGE_NURSE,
        "doctor": UserRole.DOCTOR,
        "admin": UserRole.ADMIN,
    }
    shifts = {
        s.name: (s.start_time, s.end_time) for s in db_session.scalars(select(ShiftDefinition))
    }
    assert shifts == {
        "Ca sáng": (time(6), time(14)),
        "Ca chiều": (time(14), time(22)),
        "Ca đêm": (time(22), time(6)),
    }


def test_seed_passwords_are_hashed(db_session: Session) -> None:
    seed_base(db_session, PW)
    for user in db_session.scalars(select(User)):
        assert user.password_hash != PW
        assert user.password_hash.startswith("$2"), "phải là bcrypt"
        assert verify_password(PW, user.password_hash)


def test_seed_is_idempotent(db_session: Session) -> None:
    first = seed_base(db_session, PW)
    before = _counts(db_session)
    second = seed_base(db_session, PW)
    assert (
        _counts(db_session)
        == before
        == {
            "users": 4,
            "beds": 3,
            "cameras": 1,
            "shift_definitions": 3,
        }
    )
    assert sum(first.values()) == 11
    assert sum(second.values()) == 0


def test_seed_does_not_overwrite_edited_data(db_session: Session) -> None:
    """R8 (ca âm tính): chạy lại seed không ghi đè dữ liệu người dùng đã sửa."""
    seed_base(db_session, PW)
    nurse = db_session.scalars(select(User).where(User.username == "nurse")).one()
    nurse.full_name = "Tên đã sửa"
    nurse.password_hash = "hash-da-doi"
    bed = db_session.scalars(select(Bed).where(Bed.code == "A02")).one()
    bed.area = "Khu khác"
    cam = db_session.scalars(select(Camera)).one()
    cam.source = "http://10.0.0.5:4747/video"
    db_session.commit()

    seed_base(db_session, "mat-khau-khac")
    db_session.expire_all()
    assert db_session.get(User, nurse.id).full_name == "Tên đã sửa"  # type: ignore[union-attr]
    assert db_session.get(User, nurse.id).password_hash == "hash-da-doi"  # type: ignore[union-attr]
    assert db_session.get(Bed, bed.id).area == "Khu khác"  # type: ignore[union-attr]
    assert db_session.get(Camera, cam.id).source == "http://10.0.0.5:4747/video"  # type: ignore[union-attr]
