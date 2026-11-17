"""F01 AC1, AC4: migration Alembic tạo đúng 7 bảng nền theo data-model.md và chạy được hai chiều."""

from datetime import UTC, datetime
from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from postcare.db.base import Base
from postcare.db.migrate import downgrade, upgrade
from postcare.db.models import Bed, Camera, MonitoringSession, Patient, User
from postcare.schemas.enums import CameraSourceType, UserRole

TS = "TIMESTAMP WITH TIME ZONE"
FOUNDATION_TABLES = {
    "users",
    "patients",
    "beds",
    "cameras",
    "monitoring_sessions",
    "audit_logs",
    "shift_definitions",
}

# (kiểu, nullable, server default chứa chuỗi này hoặc None) theo data-model.md.
EXPECTED: dict[str, dict[str, tuple[str, bool, str | None]]] = {
    "users": {
        "id": ("BIGINT", False, None),
        "username": ("TEXT", False, None),
        "full_name": ("TEXT", False, None),
        "password_hash": ("TEXT", False, None),
        "role": ("user_role", False, None),
        "is_active": ("BOOLEAN", False, "true"),
        "created_at": (TS, False, "now()"),
    },
    "patients": {
        "id": ("BIGINT", False, None),
        "code": ("TEXT", False, None),
        "note": ("TEXT", True, None),
        "is_active": ("BOOLEAN", False, "true"),
        "created_at": (TS, False, "now()"),
    },
    "beds": {
        "id": ("BIGINT", False, None),
        "code": ("TEXT", False, None),
        "area": ("TEXT", False, None),
        "is_active": ("BOOLEAN", False, "true"),
        "created_at": (TS, False, "now()"),
    },
    "cameras": {
        "id": ("BIGINT", False, None),
        "name": ("TEXT", False, None),
        "bed_id": ("BIGINT", True, None),
        "source_type": ("camera_source_type", False, None),
        "source": ("TEXT", False, None),
        "roi_polygon": ("JSONB", True, None),
        "thresholds": ("JSONB", False, "'{}'"),
        "display_mode": ("display_mode", False, "'BLUR'"),
        "config_version": ("INTEGER", False, "1"),
        "status": ("camera_status", False, "'UNKNOWN'"),
        "last_seen_at": (TS, True, None),
        "is_active": ("BOOLEAN", False, "true"),
    },
    "monitoring_sessions": {
        "id": ("BIGINT", False, None),
        "patient_id": ("BIGINT", False, None),
        "bed_id": ("BIGINT", False, None),
        "camera_id": ("BIGINT", True, None),
        "started_at": (TS, False, None),
        "started_by": ("BIGINT", False, None),
        "ended_at": (TS, True, None),
        "ended_by": ("BIGINT", True, None),
    },
    "audit_logs": {
        "id": ("BIGINT", False, None),
        "actor_user_id": ("BIGINT", True, None),
        "action": ("TEXT", False, None),
        "entity_type": ("TEXT", False, None),
        "entity_id": ("BIGINT", False, None),
        "before": ("JSONB", True, None),
        "after": ("JSONB", True, None),
        "created_at": (TS, False, "now()"),
    },
    "shift_definitions": {
        "id": ("BIGINT", False, None),
        "name": ("TEXT", False, None),
        "start_time": ("TIME WITHOUT TIME ZONE", False, None),
        "end_time": ("TIME WITHOUT TIME ZONE", False, None),
    },
}
# Cột prototype (ADR-0010) ngoài data-model.md, tạo ở migration 0002 (xem spec F01 mục 7).
PROTOTYPE_EXTRA_COLUMNS = {"cameras": {"last_config_hash"}}

EXPECTED_FKS = {
    ("cameras", "bed_id", "beds"),
    ("monitoring_sessions", "patient_id", "patients"),
    ("monitoring_sessions", "bed_id", "beds"),
    ("monitoring_sessions", "camera_id", "cameras"),
    ("monitoring_sessions", "started_by", "users"),
    ("monitoring_sessions", "ended_by", "users"),
    ("audit_logs", "actor_user_id", "users"),
}
EXPECTED_UNIQUE = {
    ("users", "username"),
    ("patients", "code"),
    ("beds", "code"),
    ("cameras", "bed_id"),
}


def _type_name(col: dict[str, Any]) -> str:
    t = col["type"]
    if isinstance(t, postgresql.ENUM):
        return str(t.name)
    return str(t.compile(dialect=postgresql.dialect()))


def test_upgrade_creates_foundation_tables(test_engine: Engine) -> None:
    insp = inspect(test_engine)
    assert set(insp.get_table_names()) >= FOUNDATION_TABLES
    problems: list[str] = []
    for table, columns in EXPECTED.items():
        actual = {c["name"]: c for c in insp.get_columns(table)}
        extra = set(actual) - set(columns) - PROTOTYPE_EXTRA_COLUMNS.get(table, set())
        missing = set(columns) - set(actual)
        if extra or missing:
            problems.append(f"{table}: thiếu {sorted(missing)}, thừa {sorted(extra)}")
        for name, (type_, nullable, default) in columns.items():
            if name not in actual:
                continue
            col = actual[name]
            if _type_name(col) != type_:
                problems.append(f"{table}.{name}: kiểu {_type_name(col)} != {type_}")
            if col["nullable"] != nullable:
                problems.append(f"{table}.{name}: nullable {col['nullable']} != {nullable}")
            if default is not None and default not in str(col["default"] or ""):
                problems.append(f"{table}.{name}: default {col['default']!r} thiếu {default!r}")
        if insp.get_pk_constraint(table)["constrained_columns"] != ["id"]:
            problems.append(f"{table}: khóa chính không phải id")
    assert not problems, "\n".join(problems)


def test_foreign_keys_and_unique_constraints(test_engine: Engine) -> None:
    insp = inspect(test_engine)
    fks = {
        (t, fk["constrained_columns"][0], fk["referred_table"])
        for t in FOUNDATION_TABLES
        for fk in insp.get_foreign_keys(t)
    }
    assert fks >= EXPECTED_FKS, sorted(EXPECTED_FKS - fks)
    uniques = {
        (t, u["column_names"][0])
        for t in FOUNDATION_TABLES
        for u in insp.get_unique_constraints(t)
        if len(u["column_names"]) == 1
    }
    assert uniques >= EXPECTED_UNIQUE, sorted(EXPECTED_UNIQUE - uniques)


def test_partial_unique_indexes_exist(test_engine: Engine) -> None:
    idx = {
        tuple(i["column_names"]): i
        for i in inspect(test_engine).get_indexes("monitoring_sessions")
        if i["unique"]
    }
    for col in ("bed_id", "patient_id"):
        assert (col,) in idx, f"thiếu unique index trên {col}"
        where = idx[(col,)]["dialect_options"].get("postgresql_where", "")
        assert "ended_at IS NULL" in str(where), where


def test_patients_has_no_name_or_photo_column(test_engine: Engine) -> None:
    """R3 (ca âm tính): bệnh nhân chỉ có mã thử nghiệm (PDF §10.1; HS §6.3)."""
    names = {c["name"] for c in inspect(test_engine).get_columns("patients")}
    banned = [n for n in names if any(w in n for w in ("name", "photo", "image", "avatar"))]
    assert not banned, banned


def test_models_match_migrations(test_engine: Engine) -> None:
    """Model SQLAlchemy và migration không lệch nhau (autogenerate không thấy khác biệt)."""
    with test_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], diff


# ----------------------------------------------------------------- ràng buộc (ca âm tính)


def _catalog(db: Session) -> tuple[User, Bed, Bed, Patient, Patient]:
    user = User(username="u-mig", full_name="Người thử", password_hash="x", role=UserRole.NURSE)
    b1, b2 = Bed(code="T-MIG-1", area="Khu thử"), Bed(code="T-MIG-2", area="Khu thử")
    p1, p2 = Patient(code="T-MIG-P1"), Patient(code="T-MIG-P2")
    db.add_all([user, b1, b2, p1, p2])
    db.flush()
    return user, b1, b2, p1, p2


def _session(user: User, bed: Bed, patient: Patient, ended: bool = False) -> MonitoringSession:
    now = datetime.now(UTC)
    return MonitoringSession(
        patient_id=patient.id,
        bed_id=bed.id,
        started_at=now,
        started_by=user.id,
        ended_at=now if ended else None,
        ended_by=user.id if ended else None,
    )


def _camera(bed: Bed) -> Camera:
    return Camera(name="Cam", bed_id=bed.id, source_type=CameraSourceType.WEBCAM, source="0")


def test_two_cameras_same_bed_rejected(db_session: Session) -> None:
    _, b1, _, _, _ = _catalog(db_session)
    db_session.add(_camera(b1))
    db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(_camera(b1))
        db_session.flush()


def test_partial_unique_open_session_per_bed(db_session: Session) -> None:
    user, b1, _, p1, p2 = _catalog(db_session)
    db_session.add(_session(user, b1, p1))
    db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(_session(user, b1, p2))
        db_session.flush()


def test_partial_unique_open_session_per_patient(db_session: Session) -> None:
    user, b1, b2, p1, _ = _catalog(db_session)
    db_session.add(_session(user, b1, p1))
    db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(_session(user, b2, p1))
        db_session.flush()


def test_closed_session_does_not_block_new_one(db_session: Session) -> None:
    user, b1, _, p1, _ = _catalog(db_session)
    db_session.add_all([_session(user, b1, p1, ended=True), _session(user, b1, p1, ended=True)])
    db_session.flush()
    db_session.add(_session(user, b1, p1))
    db_session.flush()


def test_timestamps_are_stored_as_utc(db_session: Session) -> None:
    _catalog(db_session)
    row = db_session.execute(
        text("SELECT created_at, current_setting('TimeZone') FROM users WHERE username = 'u-mig'")
    ).one()
    assert row[0].utcoffset() is not None


# ----------------------------------------------------------------- AC4: hai chiều


def test_migrations_roundtrip(test_engine: Engine) -> None:
    try:
        downgrade(test_engine, "base")
        insp = inspect(test_engine)
        assert set(insp.get_table_names()) <= {"alembic_version"}
        with test_engine.connect() as conn:
            enums = conn.scalars(text("SELECT typname FROM pg_type WHERE typtype = 'e'")).all()
        assert enums == [], f"downgrade còn sót enum: {enums}"
    finally:
        upgrade(test_engine, "head")  # để test sau vẫn có schema dù assert trên lỗi
    assert set(inspect(test_engine).get_table_names()) >= FOUNDATION_TABLES
