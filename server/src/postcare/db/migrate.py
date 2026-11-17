"""Chạy migration Alembic từ code (CLI `postcare seed --reset`, fixture test).

Dòng lệnh dùng `alembic` trực tiếp: `uv --directory server run alembic upgrade head`
(`make db-upgrade`).
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def alembic_config(connection: Connection | None = None) -> Config:
    """Cấu hình Alembic không cần `alembic.ini`; dùng `connection` có sẵn nếu truyền vào."""
    cfg = Config()
    cfg.set_main_option("script_location", MIGRATIONS_DIR.as_posix())
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def upgrade(engine: Engine, revision: str = "head") -> None:
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), revision)


def downgrade(engine: Engine, revision: str) -> None:
    with engine.begin() as conn:
        command.downgrade(alembic_config(conn), revision)


def reset_schema(engine: Engine) -> None:
    """XÓA toàn bộ bảng rồi tạo lại bằng migration (chỉ dùng cho dữ liệu demo trên máy dev)."""
    downgrade(engine, "base")
    upgrade(engine, "head")
