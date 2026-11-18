"""Cấu hình đọc từ biến môi trường hoặc file `.env` ở thư mục gốc repo."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = SERVER_DIR.parent
DEFAULT_DATABASE_URL = "postgresql+psycopg://postcare:postcare@localhost:5432/postcare"
DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://postcare:postcare@localhost:5432/postcare_test"
MIN_SECRET_BYTES = 32
INSECURE_SECRET_PREFIX = "change-me"
GENERATE_SECRET_HINT = 'python -c "import secrets; print(secrets.token_urlsafe(48))"'


class InsecureSecretError(RuntimeError):
    """JWT_SECRET hoặc WORKER_TOKEN còn là giá trị mặc định hoặc quá ngắn."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", SERVER_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL 16 (ADR-0004; QA#34: chạy bằng Docker trên máy dev). Test dùng DB riêng (F01 R10).
    database_url: str = DEFAULT_DATABASE_URL
    test_database_url: str = DEFAULT_TEST_DATABASE_URL
    # Mặc định cố ý không dùng được: API từ chối khởi động (ensure_secure_secrets). Đặt trong .env.
    jwt_secret: str = "change-me"
    jwt_expire_hours: float = 8.0  # A10
    worker_token: str = "change-me-worker"
    api_base_url: str = "http://127.0.0.1:8000"
    tz_display: str = "Asia/Ho_Chi_Minh"
    web_origins: str = "http://localhost:5173"
    seed_password: str = "postcare"
    camera_offline_after_s: float = 5.0  # A02
    camera_watch_interval_s: float = 1.0
    # F06: khung JPEG xem trực tiếp (A03; giả định R7, R8). API chỉ giữ khung mới nhất trong RAM.
    frame_max_bytes: int = 2 * 1024 * 1024
    # F07 R1: MJPEG ngừng phát khi khung mới nhất cũ hơn ngưỡng này (giả định 3 s); chu kỳ kiểm tra.
    stream_stale_frame_s: float = 3.0
    stream_poll_interval_s: float = 0.05
    # Kiểm tra lại người xem (khóa, đặt lại mật khẩu, đổi vai trò; F35) trong lúc stream (giả định).
    stream_revalidate_s: float = 5.0
    # Worker (F06; A02, A03, ADR-0002): chu kỳ heartbeat, poll cấu hình, nhịp gửi khung, nén JPEG.
    worker_heartbeat_interval_s: float = 2.0
    worker_config_poll_s: float = 5.0
    worker_frame_fps: float = 5.0
    worker_jpeg_max_side: int = 960
    worker_jpeg_quality: int = 70
    worker_max_fps: float = 15.0  # A03: FPS xử lý tối đa (F05 DEFAULT_MAX_FPS)

    @property
    def web_origin_list(self) -> list[str]:
        return [o.strip() for o in self.web_origins.split(",") if o.strip()]

    def ensure_secure_secrets(self) -> None:
        """Từ chối JWT_SECRET / WORKER_TOKEN mặc định ("change-me…") hoặc ngắn hơn 32 byte."""
        bad = [
            name
            for name, value in (
                ("JWT_SECRET", self.jwt_secret),
                ("WORKER_TOKEN", self.worker_token),
            )
            if value.startswith(INSECURE_SECRET_PREFIX)
            or len(value.encode("utf-8")) < MIN_SECRET_BYTES
        ]
        if bad:
            names = ", ".join(bad)
            raise InsecureSecretError(
                f"{names} chưa an toàn (giá trị mặc định 'change-me…' hoặc ngắn hơn "
                f"{MIN_SECRET_BYTES} byte). Đặt trong .env (xem .env.example), tạo bằng: "
                f"{GENERATE_SECRET_HINT} / {names} is a default or shorter than "
                f"{MIN_SECRET_BYTES} bytes; set it in .env."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
