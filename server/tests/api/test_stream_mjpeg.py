"""F07 AC1, R1, R2: MJPEG xem trực tiếp từ bộ đệm RAM (F06), chỉ vai trò nhân viên."""

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from postcare.api.v1.stream import mjpeg_parts
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.api.deps import create_token
from postcare.api.frame_buffer import LatestFrameStore
from postcare.db.models import User
from postcare.domain.security import hash_password
from postcare.schemas.enums import UserRole
from postcare.settings import Settings
from tests.conftest import PASSWORD

Login = Callable[[str], dict[str, str]]

JPEG_A = b"\xff\xd8\xff\xe0frame-a\xff\xd9"
JPEG_B = b"\xff\xd8\xff\xe0frame-b\xff\xd9"
URL = "/api/v1/cameras/1/stream.mjpeg"


@pytest.fixture
def settings(test_settings: Settings) -> Settings:
    # Khung cũ sau 0,3 s để stream tự đóng nhanh trong test (mặc định 3 s).
    return test_settings.model_copy(
        update={"stream_stale_frame_s": 0.3, "stream_poll_interval_s": 0.02}
    )


def _token(login: Login, username: str) -> str:
    return login(username)["Authorization"].split(" ", 1)[1]


def _read_stream(client: TestClient, token: str, camera_id: int = 1) -> tuple[Any, bytes]:
    with client.stream("GET", f"/api/v1/cameras/{camera_id}/stream.mjpeg?token={token}") as r:
        body = r.read()
    return r, body


def test_default_stale_frame_is_3s() -> None:
    assert Settings().stream_stale_frame_s == 3.0


def test_mjpeg_requires_token(client: TestClient, db: Session, settings: Settings, app) -> None:
    app.state.frames.put(1, JPEG_A)
    assert client.get(URL).status_code == 401
    r = client.get(f"{URL}?token=not-a-jwt")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"
    nurse = db.scalar(select(User).where(User.username == "nurse"))
    assert nurse is not None
    expired = create_token(nurse, settings, now=datetime.now(UTC) - timedelta(days=2))
    assert client.get(f"{URL}?token={expired}").status_code == 401


def test_mjpeg_header_token_not_enough(client: TestClient, login: Login, app) -> None:
    """`<img>` không gửi header; endpoint chỉ đọc token từ query (api-conventions.md)."""
    app.state.frames.put(1, JPEG_A)
    assert client.get(URL, headers=login("nurse")).status_code == 401


def test_mjpeg_family_forbidden(client: TestClient, db: Session, login: Login, app) -> None:
    db.add(
        User(
            username="family",
            full_name="Người nhà thử nghiệm",
            password_hash=hash_password(PASSWORD),
            role=UserRole.FAMILY,
        )
    )
    db.commit()
    app.state.frames.put(1, JPEG_A)
    r = client.get(f"{URL}?token={_token(login, 'family')}")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"
    assert b"\xff\xd8" not in r.content


@pytest.mark.parametrize("username", ["nurse", "charge", "doctor", "admin"])
def test_mjpeg_all_staff_roles_allowed(client: TestClient, login: Login, app, username) -> None:
    app.state.frames.put(1, JPEG_A)
    r, body = _read_stream(client, _token(login, username))
    assert r.status_code == 200
    assert JPEG_A in body


def test_mjpeg_no_frame_404(client: TestClient, login: Login) -> None:
    r, body = _read_stream(client, _token(login, "nurse"))
    assert r.status_code == 404
    assert b"\xff\xd8" not in body


def test_mjpeg_stale_frame_at_connect_404(client: TestClient, login: Login, app) -> None:
    app.state.frames.put(1, JPEG_A, received_at=datetime.now(UTC) - timedelta(seconds=10))
    r, body = _read_stream(client, _token(login, "nurse"))
    assert r.status_code == 404
    assert b"\xff\xd8" not in body


def test_mjpeg_unknown_camera_404(client: TestClient, login: Login, app) -> None:
    app.state.frames.put(999, JPEG_A)
    r, _ = _read_stream(client, _token(login, "nurse"), camera_id=999)
    assert r.status_code == 404


def test_mjpeg_streams_latest_frame(client: TestClient, login: Login, app) -> None:
    app.state.frames.put(1, JPEG_A)
    app.state.frames.put(1, JPEG_B)
    r, body = _read_stream(client, _token(login, "nurse"))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("multipart/x-mixed-replace")
    assert "boundary=frame" in r.headers["content-type"]
    assert "no-store" in r.headers["cache-control"]
    assert body.startswith(b"--frame\r\n")
    head, _, rest = body.partition(b"\r\n\r\n")
    assert b"Content-Type: image/jpeg" in head
    assert f"Content-Length: {len(JPEG_B)}".encode() in head
    assert rest.startswith(JPEG_B)
    assert JPEG_A not in body


def test_mjpeg_closes_when_frame_stale(client: TestClient, login: Login, app) -> None:
    """Không có khung mới: gửi khung hiện có đúng một lần rồi đóng khi khung quá `stale_frame_s`."""
    app.state.frames.put(1, JPEG_A)
    start = time.monotonic()
    r, body = _read_stream(client, _token(login, "nurse"))
    assert r.status_code == 200
    assert time.monotonic() - start < 3.0
    assert body.count(b"--frame\r\n") == 1


def test_mjpeg_does_not_write_disk(
    client: TestClient, login: Login, app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    app.state.frames.put(1, JPEG_A)
    _read_stream(client, _token(login, "nurse"))
    assert list(tmp_path.rglob("*")) == []


class FakeClock:
    def __init__(self) -> None:
        self.t = datetime(2026, 11, 18, 8, 0, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += timedelta(seconds=seconds)


def _collect(store: LatestFrameStore, clock: FakeClock, script: dict[int, bytes]) -> list[bytes]:
    """Chạy generator với đồng hồ giả; `script[i]` = khung worker gửi sau lần ngủ thứ i."""
    calls = {"n": 0}

    async def fake_sleep(seconds: float) -> None:
        calls["n"] += 1
        clock.advance(seconds)
        data = script.get(calls["n"])
        if data is not None:
            store.put(1, data, received_at=clock.now())

    async def run() -> list[bytes]:
        gen = mjpeg_parts(store, 1, stale_after_s=3.0, poll_s=0.5, now=clock.now, sleep=fake_sleep)
        return [part async for part in gen]

    return asyncio.run(run())


def test_mjpeg_parts_sends_each_new_frame_once() -> None:
    clock = FakeClock()
    store = LatestFrameStore()
    store.put(1, JPEG_A, received_at=clock.now())
    parts = _collect(store, clock, {2: JPEG_B})
    # Khung A một lần, khung B một lần; không gửi lại khung cũ khi chưa có khung mới.
    assert len(parts) == 2
    assert parts[0].endswith(JPEG_A + b"\r\n")
    assert parts[1].endswith(JPEG_B + b"\r\n")
    # Dừng khi khung B cũ hơn 3 s (B đến lúc t = 1 s → dừng sau t > 4 s).
    assert clock.now() - datetime(2026, 11, 18, 8, 0, 0, tzinfo=UTC) <= timedelta(seconds=4.6)


def test_mjpeg_parts_no_frame_yields_nothing() -> None:
    clock = FakeClock()
    parts = _collect(LatestFrameStore(), clock, {})
    assert parts == []
