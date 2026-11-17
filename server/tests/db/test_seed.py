"""F01 AC2 (R7–R9): seed dữ liệu mẫu idempotent, mật khẩu đã hash."""

from datetime import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from postcare.db.models import Area, Bed, Camera, ShiftDefinition, User
from postcare.domain.security import verify_password
from postcare.domain.seed import seed_base, seed_demo
from postcare.schemas.enums import CameraSourceType, UserRole

PW = "seed-pass"


def _counts(db: Session) -> dict[str, int]:
    return {
        m.__tablename__: db.scalar(select(func.count()).select_from(m)) or 0
        for m in (User, Area, Bed, Camera, ShiftDefinition)
    }


def test_seed_creates_sample_data(db_session: Session) -> None:
    seed_base(db_session, PW)
    beds = db_session.scalars(select(Bed).order_by(Bed.code)).all()
    assert [b.code for b in beds] == ["A01", "A02", "A03"]
    assert {(b.area.code, b.area.name) for b in beds} == {("KV01", "Khu hậu phẫu")}
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
            "areas": 1,
            "beds": 3,
            "cameras": 1,
            "shift_definitions": 3,
        }
    )
    assert sum(first.values()) == 12
    assert sum(second.values()) == 0


def test_seed_does_not_overwrite_edited_data(db_session: Session) -> None:
    """R8 (ca âm tính): chạy lại seed không ghi đè dữ liệu người dùng đã sửa."""
    seed_base(db_session, PW)
    nurse = db_session.scalars(select(User).where(User.username == "nurse")).one()
    nurse.full_name = "Tên đã sửa"
    nurse.password_hash = "hash-da-doi"
    bed = db_session.scalars(select(Bed).where(Bed.code == "A02")).one()
    bed.area = Area(code="KV-X", name="Khu khác")
    cam = db_session.scalars(select(Camera)).one()
    cam.source = "http://10.0.0.5:4747/video"
    db_session.commit()

    seed_base(db_session, "mat-khau-khac")
    db_session.expire_all()
    assert db_session.get(User, nurse.id).full_name == "Tên đã sửa"  # type: ignore[union-attr]
    assert db_session.get(User, nurse.id).password_hash == "hash-da-doi"  # type: ignore[union-attr]
    assert db_session.get(Bed, bed.id).area.name == "Khu khác"  # type: ignore[union-attr]
    assert db_session.get(Camera, cam.id).source == "http://10.0.0.5:4747/video"  # type: ignore[union-attr]


def test_seed_skips_camera_soft_deleted_by_f03(db_session: Session) -> None:
    """F03 §8: xóa mềm camera đặt `bed_id = null`; chạy lại seed không tạo thêm "Camera A01"."""
    seed_base(db_session, PW)
    cam = db_session.scalars(select(Camera)).one()
    cam.bed_id = None
    cam.is_active = False
    db_session.commit()

    assert seed_base(db_session, PW)["cameras"] == 0
    assert db_session.scalar(select(func.count()).select_from(Camera)) == 1


def test_seed_demo_skips_existing_camera_names(db_session: Session) -> None:
    seed_base(db_session, PW)
    seed_demo(db_session)
    for cam in db_session.scalars(select(Camera)):
        cam.bed_id = None
    db_session.commit()
    seed_demo(db_session)
    seed_base(db_session, PW)
    names = sorted(db_session.scalars(select(Camera.name)))
    assert names == ["Camera A01", "Camera A02", "Camera A03"]


def test_seed_area_code_taken_by_other_area(db_session: Session) -> None:
    """F37: DB cũ qua migration 0006 có thể đã dùng KV01 cho khu vực khác; seed không gán nhầm."""
    db_session.add(Area(code="KV01", name="Hồi sức"))
    db_session.commit()
    seed_base(db_session, PW)
    beds = db_session.scalars(select(Bed)).all()
    assert {(b.area.code, b.area.name) for b in beds} == {("KV02", "Khu hậu phẫu")}


def test_seed_area_skips_deleted_area(db_session: Session) -> None:
    """Review F37 #6: khu vực "Khu hậu phẫu" đã xóa không được dùng cho giường mẫu mới."""
    db_session.add(Area(code="KV01", name="Khu hậu phẫu", is_active=False))
    db_session.commit()
    seed_base(db_session, PW)
    beds = db_session.scalars(select(Bed)).all()
    assert {(b.area.code, b.area.is_active) for b in beds} == {("KV02", True)}


def test_seed_area_prefers_active_area(db_session: Session) -> None:
    db_session.add_all(
        [
            Area(code="OLD", name="Khu hậu phẫu", is_active=False),
            Area(code="HP", name="Khu hậu phẫu"),
        ]
    )
    db_session.commit()
    created = seed_base(db_session, PW)
    assert created["areas"] == 0
    assert {b.area.code for b in db_session.scalars(select(Bed))} == {"HP"}


def test_seed_shifts_do_not_overlap_existing(db_session: Session) -> None:
    """Review F37 #8: ca mẫu chồng giờ ca đang dùng (do ADMIN tạo) thì bỏ qua, không tạo chồng."""
    db_session.add(ShiftDefinition(name="Ca hành chính", start_time=time(7), end_time=time(16)))
    db_session.commit()
    created = seed_base(db_session, PW)
    names = {s.name for s in db_session.scalars(select(ShiftDefinition))}
    # 06–14 và 14–22 chồng 07–16; 22–06 không chồng nên vẫn được tạo.
    assert names == {"Ca hành chính", "Ca đêm"}
    assert created["shift_definitions"] == 1


def test_seed_shifts_ignore_deleted_overlap(db_session: Session) -> None:
    db_session.add(
        ShiftDefinition(name="Ca cũ", start_time=time(7), end_time=time(16), is_active=False)
    )
    db_session.commit()
    created = seed_base(db_session, PW)
    assert created["shift_definitions"] == 3
