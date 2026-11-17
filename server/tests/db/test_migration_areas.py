"""F37 AC1, R2: migration 0005 chuyển `beds.area` (chuỗi) sang bảng `areas` + `beds.area_id`.

Chạy trên DB test thật (commit thật): hạ về 0004, chèn giường dạng cũ, nâng lên 0005, rồi hạ
lại 0004 để kiểm tra `downgrade`. Luôn dọn dữ liệu và nâng về `head` trong `finally`.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, inspect, text

from postcare.db.migrate import downgrade, upgrade

BEFORE = "0004"
AREAS_REVISION = "0005"

# Hai giường cùng khu vực (một bản có khoảng trắng thừa), một giường khu vực khác.
OLD_BEDS = [
    ("M01", "Khu hậu phẫu"),
    ("M02", "  Khu hậu phẫu "),
    ("M03", "Hồi sức"),
]


def _clean(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE beds RESTART IDENTITY CASCADE"))
        if inspect(conn).has_table("areas"):
            conn.execute(text("TRUNCATE areas RESTART IDENTITY CASCADE"))


@pytest.fixture
def old_schema(test_engine: Engine) -> Iterator[Engine]:
    _clean(test_engine)
    downgrade(test_engine, BEFORE)
    try:
        with test_engine.begin() as conn:
            for code, area in OLD_BEDS:
                conn.execute(
                    text("INSERT INTO beds (code, area) VALUES (:c, :a)"), {"c": code, "a": area}
                )
        yield test_engine
    finally:
        _clean(test_engine)
        upgrade(test_engine, "head")


def test_migration_areas_groups_same_area(old_schema: Engine) -> None:
    upgrade(old_schema, AREAS_REVISION)
    with old_schema.connect() as conn:
        areas = conn.execute(
            text("SELECT id, code, name, is_active FROM areas ORDER BY code")
        ).all()
        beds = dict(
            conn.execute(
                text("SELECT b.code, a.name FROM beds b JOIN areas a ON a.id = b.area_id")
            ).all()
        )
    # Thứ tự chữ cái của `name`: "Hồi sức" < "Khu hậu phẫu".
    assert [(a.code, a.name, a.is_active) for a in areas] == [
        ("KV01", "Hồi sức", True),
        ("KV02", "Khu hậu phẫu", True),
    ]
    assert beds == {"M01": "Khu hậu phẫu", "M02": "Khu hậu phẫu", "M03": "Hồi sức"}
    columns = {c["name"]: c for c in inspect(old_schema).get_columns("beds")}
    assert "area" not in columns
    assert columns["area_id"]["nullable"] is False


def test_migration_areas_downgrade_restores_text(old_schema: Engine) -> None:
    upgrade(old_schema, AREAS_REVISION)
    downgrade(old_schema, BEFORE)
    insp = inspect(old_schema)
    assert not insp.has_table("areas")
    with old_schema.connect() as conn:
        beds = dict(conn.execute(text("SELECT code, area FROM beds")).all())
    # Chuỗi đã chuẩn hóa (bỏ khoảng trắng đầu/cuối) khi lên 0005.
    assert beds == {"M01": "Khu hậu phẫu", "M02": "Khu hậu phẫu", "M03": "Hồi sức"}
    shift_cols = {c["name"] for c in insp.get_columns("shift_definitions")}
    assert {"is_active", "created_at"}.isdisjoint(shift_cols)


def test_migration_areas_empty_db(test_engine: Engine) -> None:
    """Không có giường nào: migration vẫn chạy, không tạo khu vực."""
    _clean(test_engine)
    downgrade(test_engine, BEFORE)
    try:
        upgrade(test_engine, AREAS_REVISION)
        with test_engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM areas")) == 0
    finally:
        upgrade(test_engine, "head")


def test_migration_area_codes_beyond_99(test_engine: Engine) -> None:
    """Review F37 #7: 101 khu vực → mã KV01…KV99, KV100, KV101 (không bị cắt, không trùng)."""
    _clean(test_engine)
    downgrade(test_engine, BEFORE)
    try:
        with test_engine.begin() as conn:
            for i in range(101):
                conn.execute(
                    text("INSERT INTO beds (code, area) VALUES (:c, :a)"),
                    {"c": f"N{i:03d}", "a": f"Khu {i:03d}"},
                )
        upgrade(test_engine, AREAS_REVISION)
        with test_engine.connect() as conn:
            rows = dict(conn.execute(text("SELECT name, code FROM areas")).all())
        assert len(set(rows.values())) == 101
        assert rows["Khu 000"] == "KV01" and rows["Khu 098"] == "KV99"
        assert rows["Khu 099"] == "KV100" and rows["Khu 100"] == "KV101"
    finally:
        _clean(test_engine)
        upgrade(test_engine, "head")
