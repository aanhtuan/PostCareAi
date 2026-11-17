"""F01 AC3 (R10): test dùng DB `postcare_test` riêng, rollback sau mỗi test, lỗi rõ khi thiếu DB."""

import pytest
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from postcare.db.models import Bed
from postcare.settings import Settings
from tests.dbutil import DatabaseSetupError, ensure_reachable, ensure_safe_test_url

MARK = "ISO-TEST"


def test_uses_separate_test_database(test_engine: Engine) -> None:
    assert (test_engine.url.database or "").endswith("_test")
    assert test_engine.url != create_engine(Settings().database_url).url


def test_rollback_isolation_a(db_session: Session) -> None:
    db_session.add(Bed(code=MARK, area="Khu thử"))
    db_session.commit()  # commit trong code chỉ nhả savepoint, transaction ngoài vẫn rollback
    assert db_session.scalar(select(Bed).where(Bed.code == MARK)) is not None


def test_rollback_isolation_b(db_session: Session) -> None:
    assert db_session.scalar(select(Bed).where(Bed.code == MARK)) is None


def test_test_url_must_differ_from_dev_url() -> None:
    url = "postgresql+psycopg://postcare:postcare@localhost:5432/postcare_test"
    with pytest.raises(DatabaseSetupError, match="DATABASE_URL"):
        ensure_safe_test_url(url, url)


def test_test_url_must_end_with_test() -> None:
    with pytest.raises(DatabaseSetupError, match="_test"):
        ensure_safe_test_url(
            "postgresql+psycopg://postcare:postcare@localhost:5432/postcare",
            "postgresql+psycopg://postcare:postcare@localhost:5432/other",
        )


def test_unreachable_test_db_fails_clearly() -> None:
    """Không kết nối được thì báo lỗi kèm hướng dẫn, không skip."""
    engine = create_engine(
        "postgresql+psycopg://postcare:postcare@127.0.0.1:1/postcare_test",
        connect_args={"connect_timeout": 2},
    )
    with pytest.raises(DatabaseSetupError, match="docker start postcare-db"):
        ensure_reachable(engine)
