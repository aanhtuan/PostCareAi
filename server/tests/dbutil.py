"""Kiểm tra DB test trước khi chạy (F01 R10): đúng DB riêng, kết nối được, không tự skip."""

from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

HINT = (
    "Khởi động PostgreSQL (docker start postcare-db) và tạo DB postcare_test "
    "(docs/04-guides/dev-setup.md mục 4), hoặc đặt TEST_DATABASE_URL đúng."
)


class DatabaseSetupError(RuntimeError):
    """DB test không dùng được. Test phải lỗi, không skip (tránh `make check` xanh giả)."""


def ensure_safe_test_url(test_url: str, dev_url: str) -> None:
    """Không bao giờ chạy test trên DB dev: URL phải khác và tên DB kết thúc bằng `_test`."""
    test, dev = make_url(test_url), make_url(dev_url)
    if test.render_as_string(hide_password=False) == dev.render_as_string(hide_password=False):
        raise DatabaseSetupError(
            "TEST_DATABASE_URL trùng DATABASE_URL: từ chối chạy test trên DB dev."
        )
    if not (test.database or "").endswith("_test"):
        raise DatabaseSetupError(
            f"Tên DB test phải kết thúc bằng '_test' (đang là {test.database!r})."
        )


def ensure_reachable(url: str, timeout_s: int = 5) -> None:
    """Thử kết nối một lần với timeout ngắn để báo lỗi nhanh thay vì treo."""
    probe: Engine = create_engine(
        url, poolclass=NullPool, connect_args={"connect_timeout": timeout_s}
    )
    try:
        with probe.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        shown = probe.url.render_as_string(hide_password=True)
        raise DatabaseSetupError(f"Không kết nối được DB test {shown}. {HINT}") from exc
    finally:
        probe.dispose()
