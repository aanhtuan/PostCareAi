"""Cấu hình đọc từ biến môi trường hoặc file `.env` ở thư mục gốc repo."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = SERVER_DIR.parent
DEFAULT_DATABASE_URL = "postgresql+psycopg://postcare:postcare@localhost:5432/postcare"
DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://postcare:postcare@localhost:5432/postcare_test"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", SERVER_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL 16 (ADR-0004; QA#34: chạy bằng Docker trên máy dev). Test dùng DB riêng (F01 R10).
    database_url: str = DEFAULT_DATABASE_URL
    test_database_url: str = DEFAULT_TEST_DATABASE_URL
    jwt_secret: str = "change-me"
    jwt_expire_hours: float = 8.0  # A10
    worker_token: str = "change-me-worker"
    api_base_url: str = "http://127.0.0.1:8000"
    tz_display: str = "Asia/Ho_Chi_Minh"
    web_origins: str = "http://localhost:5173"
    seed_password: str = "postcare"
    camera_offline_after_s: float = 5.0  # A02
    camera_watch_interval_s: float = 1.0

    @property
    def web_origin_list(self) -> list[str]:
        return [o.strip() for o in self.web_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
