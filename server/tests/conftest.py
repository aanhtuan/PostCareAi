"""Fixture chung (F01 R10; testing.md §3).

- DB test PostgreSQL riêng (`TEST_DATABASE_URL`, mặc định `postcare_test`), schema tạo bằng
  `alembic upgrade head` một lần mỗi lần chạy test. Không kết nối được thì test lỗi, không skip.
- `db_session`: mỗi test một transaction ngoài, rollback sau test; `commit()` trong code chỉ nhả
  savepoint.
- `app`/`client`: API dùng chung connection đó, nên dữ liệu test API cũng bị rollback.
  Test đánh dấu `real_commit` dùng commit thật (cần kết nối thứ hai), dọn bằng TRUNCATE.
"""

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, text
from sqlalchemy.orm import Session, sessionmaker

from postcare.api.main import create_app
from postcare.db.base import Base
from postcare.db.migrate import upgrade
from postcare.db.session import make_engine, make_session_factory
from postcare.domain.notifications import InMemoryPublisher
from postcare.domain.seed import seed_base, seed_demo
from postcare.settings import Settings
from tests.dbutil import DatabaseSetupError, ensure_reachable, ensure_safe_test_url

PASSWORD = "test-pass"
WORKER_TOKEN = "test-worker-token-at-least-32-bytes!"  # API từ chối token < 32 byte


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    env = Settings()
    try:
        ensure_safe_test_url(env.test_database_url, env.database_url)
    except DatabaseSetupError as exc:
        pytest.fail(str(exc), pytrace=False)
    return Settings(
        database_url=env.test_database_url,
        test_database_url=env.test_database_url,
        jwt_secret="test-secret-at-least-32-bytes-long!!",
        worker_token=WORKER_TOKEN,
        seed_password=PASSWORD,
    )


@pytest.fixture(scope="session")
def test_engine(test_settings: Settings) -> Iterator[Engine]:
    engine = make_engine(test_settings.database_url)
    try:
        ensure_reachable(test_settings.database_url)
    except DatabaseSetupError as exc:
        pytest.fail(str(exc), pytrace=False)
    upgrade(engine, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def connection(test_engine: Engine) -> Iterator[Connection]:
    conn = test_engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        if trans.is_active:
            trans.rollback()
        conn.close()


def _savepoint_factory(conn: Connection) -> sessionmaker[Session]:
    return sessionmaker(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)


@pytest.fixture
def db_session(connection: Connection) -> Iterator[Session]:
    with _savepoint_factory(connection)() as s:
        yield s


def truncate_all(conn: Connection) -> None:
    """Xóa dữ liệu và đặt lại id về 1 (test API cũ giả định giường A01 có id 1)."""
    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def settings(test_settings: Settings) -> Settings:
    return test_settings


@pytest.fixture
def app(request: pytest.FixtureRequest, settings: Settings, test_engine: Engine) -> Iterator[Any]:
    application = create_app(settings, watch_cameras=False)
    application.state.engine.dispose()
    if request.node.get_closest_marker("real_commit"):
        with test_engine.begin() as conn:
            truncate_all(conn)
        application.state.session_factory = make_session_factory(test_engine)
        yield application
        with test_engine.begin() as conn:
            truncate_all(conn)
        return
    conn: Connection = request.getfixturevalue("connection")
    truncate_all(conn)  # trong transaction ngoài: rollback cả việc đặt lại id
    application.state.session_factory = _savepoint_factory(conn)
    yield application


@pytest.fixture
def client(app: Any) -> Iterator[TestClient]:
    with TestClient(app) as c:
        with app.state.session_factory() as db:
            seed_base(db, PASSWORD)
            seed_demo(db)
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
