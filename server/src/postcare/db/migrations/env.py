"""Môi trường Alembic: URL từ `DATABASE_URL` (settings), hoặc connection do code truyền vào."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, create_engine, pool

from postcare.db import models  # noqa: F401  (đăng ký bảng vào Base.metadata)
from postcare.db.base import Base
from postcare.settings import get_settings

config = context.config
target_metadata = Base.metadata

if config.config_file_name is not None and "connection" not in config.attributes:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        _run(conn)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
