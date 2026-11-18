"""F01 R4, AC1: enum trong PostgreSQL khớp enum trong `postcare.schemas` (data-model.md)."""

from enum import StrEnum

from sqlalchemy import Engine, text

from postcare.schemas.enums import (
    AlertOutcome,
    AlertStatus,
    CameraSourceType,
    CameraStatus,
    DisplayMode,
    ObservationQuality,
    Priority,
    ShareLevel,
    UserRole,
)
from postcare.schemas.events import EventCode

FOUNDATION_ENUMS: dict[str, type[StrEnum]] = {
    "user_role": UserRole,
    "camera_source_type": CameraSourceType,
    "display_mode": DisplayMode,
    "camera_status": CameraStatus,
}
# Bảng events/alerts của prototype (migration 0002; F17 tiếp nhận).
PROTOTYPE_ENUMS: dict[str, type[StrEnum]] = {
    "event_code": EventCode,
    "priority": Priority,
    "observation_quality": ObservationQuality,
    "alert_status": AlertStatus,
    "alert_outcome": AlertOutcome,
}
# Quyền xem của người nhà (F36, migration 0007_f36).
FAMILY_ENUMS: dict[str, type[StrEnum]] = {"share_level": ShareLevel}


def _db_enums(engine: Engine) -> dict[str, list[str]]:
    sql = text(
        "SELECT t.typname, e.enumlabel FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid "
        "ORDER BY t.typname, e.enumsortorder"
    )
    out: dict[str, list[str]] = {}
    with engine.connect() as conn:
        for name, label in conn.execute(sql):
            out.setdefault(name, []).append(label)
    return out


def test_enums_match_schemas(test_engine: Engine) -> None:
    db = _db_enums(test_engine)
    expected = FOUNDATION_ENUMS | PROTOTYPE_ENUMS | FAMILY_ENUMS
    assert set(db) == set(expected), f"enum DB: {sorted(db)}"
    for name, cls in expected.items():
        assert db[name] == [m.value for m in cls], name


def test_user_role_values_match_qa18_qa31(test_engine: Engine) -> None:
    """QA#18 bốn vai trò nhân viên; QA#31 thêm `FAMILY` (F35, migration 0003)."""
    assert _db_enums(test_engine)["user_role"] == [
        "NURSE",
        "CHARGE_NURSE",
        "DOCTOR",
        "ADMIN",
        "FAMILY",
    ]
