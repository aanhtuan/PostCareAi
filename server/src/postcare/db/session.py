"""Tạo engine/session SQLAlchemy cho SQLite (mặc định) hoặc PostgreSQL."""

from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from postcare.db.models import Base


def make_engine(database_url: str) -> Engine:
    kwargs: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
    engine = create_engine(database_url, **kwargs)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_schema(engine: Engine) -> None:
    """Prototype: tạo bảng bằng create_all thay vì Alembic (ADR-0010)."""
    Base.metadata.create_all(engine)


def reset_schema(engine: Engine) -> None:
    """Xóa và tạo lại toàn bộ bảng (chỉ dùng cho `postcare seed`)."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
