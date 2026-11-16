"""Fixture chung: DB SQLite tạm cho mỗi test, TestClient, đăng nhập theo vai trò."""

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from postcare.api.main import create_app
from postcare.domain.notifications import InMemoryPublisher
from postcare.domain.seed import seed_base
from postcare.settings import Settings

PASSWORD = "test-pass"
WORKER_TOKEN = "test-worker-token"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        jwt_secret="test-secret-at-least-32-bytes-long!!",
        worker_token=WORKER_TOKEN,
        seed_password=PASSWORD,
    )


@pytest.fixture
def app(settings: Settings) -> Any:
    return create_app(settings, watch_cameras=False)


@pytest.fixture
def client(app: Any) -> Iterator[TestClient]:
    with TestClient(app) as c:
        with app.state.session_factory() as db:
            seed_base(db, PASSWORD)
        app.state.hub = InMemoryPublisher()
        yield c


@pytest.fixture
def publisher(app: Any, client: TestClient) -> InMemoryPublisher:
    return app.state.hub


@pytest.fixture
def db(app: Any, client: TestClient) -> Iterator[Session]:
    with app.state.session_factory() as s:
        yield s


@pytest.fixture
def login(client: TestClient) -> Callable[[str], dict[str, str]]:
    cache: dict[str, dict[str, str]] = {}

    def _login(username: str) -> dict[str, str]:
        if username not in cache:
            r = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
            assert r.status_code == 200, r.text
            cache[username] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return cache[username]

    return _login


@pytest.fixture
def worker_headers() -> dict[str, str]:
    return {"X-Worker-Token": WORKER_TOKEN}


@pytest.fixture
def open_session(client: TestClient, login: Callable[[str], dict[str, str]]) -> dict[str, Any]:
    """Phiên mở cho giường A01 (id 1, camera 1) và BN-001 (id 1)."""
    r = client.post("/api/v1/sessions", json={"bed_id": 1, "patient_id": 1}, headers=login("nurse"))
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def post_event(client: TestClient, worker_headers: dict[str, str]) -> Callable[..., Any]:
    def _post(
        code: str,
        priority: str,
        *,
        camera_id: int = 1,
        occurred_at: datetime | None = None,
        event_uid: str | None = None,
    ) -> Any:
        t = occurred_at or datetime.now(UTC)
        return client.post(
            "/internal/v1/events",
            headers=worker_headers,
            json={
                "event_uid": event_uid or str(uuid.uuid4()),
                "camera_id": camera_id,
                "code": code,
                "priority": priority,
                "occurred_at": t.isoformat(),
                "detected_at": (t + timedelta(milliseconds=300)).isoformat(),
                "confidence": 0.9,
                "observation_quality": "GOOD",
                "explanation": {"rule_id": "test"},
                "config_hash": "test",
            },
        )

    return _post
