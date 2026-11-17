"""F02 review: API từ chối khởi động khi JWT_SECRET / WORKER_TOKEN là mặc định hoặc quá ngắn."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from postcare.api.main import create_app
from postcare.settings import REPO_ROOT, InsecureSecretError, Settings

STRONG = "x" * 32


def _settings(**overrides: str) -> Settings:
    values = {"jwt_secret": STRONG, "worker_token": STRONG, **overrides}
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def test_strong_secrets_are_accepted() -> None:
    _settings().ensure_secure_secrets()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("jwt_secret", "change-me"),
        ("jwt_secret", "change-me-to-a-long-random-string-32b"),  # mặc định cũ, đủ dài
        ("jwt_secret", "x" * 31),
        ("jwt_secret", "ngắn"),
        ("worker_token", "change-me-worker"),
        ("worker_token", "change-me-" + "y" * 40),
        ("worker_token", "y" * 31),
    ],
)
def test_default_or_short_secret_is_rejected(field: str, value: str) -> None:
    with pytest.raises(InsecureSecretError) as exc:
        _settings(**{field: value}).ensure_secure_secrets()
    assert field.upper() in str(exc.value)


def test_length_is_counted_in_bytes() -> None:
    _settings(jwt_secret="ệ" * 11).ensure_secure_secrets()  # 11 ký tự, 33 byte UTF-8
    with pytest.raises(InsecureSecretError):
        _settings(jwt_secret="é" * 15).ensure_secure_secrets()  # 30 byte


def test_class_defaults_are_rejected() -> None:
    """Không có .env và biến môi trường thì API không được chạy với giá trị mặc định."""
    defaults = Settings.model_fields
    with pytest.raises(InsecureSecretError) as exc:
        _settings(
            jwt_secret=defaults["jwt_secret"].default,
            worker_token=defaults["worker_token"].default,
        ).ensure_secure_secrets()
    assert "JWT_SECRET" in str(exc.value)
    assert "WORKER_TOKEN" in str(exc.value)


def test_api_refuses_to_start_with_default_secret() -> None:
    app = create_app(_settings(jwt_secret="change-me"), watch_cameras=False)
    with pytest.raises(InsecureSecretError), TestClient(app):
        pass


def test_api_starts_with_strong_secrets() -> None:
    app = create_app(_settings(), watch_cameras=False)
    with TestClient(app):  # lifespan chạy xong, không lỗi
        pass


def test_env_example_holds_accepted_dev_values() -> None:
    values: dict[str, str] = {}
    for line in Path(REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    _settings(
        jwt_secret=values["JWT_SECRET"], worker_token=values["WORKER_TOKEN"]
    ).ensure_secure_secrets()
