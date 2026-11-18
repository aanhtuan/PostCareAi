"""Tiện ích chung cho test F36: tài khoản người nhà, phiên, cấp quyền, đồng hồ giả."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from postcare.db.models import User
from postcare.domain.security import hash_password
from postcare.schemas.enums import UserRole
from tests.conftest import PASSWORD

Login = Callable[[str], dict[str, str]]

# Mọi khóa được phép trong payload gửi cho FAMILY (R9, R11, R13). Không có ảnh, mã bệnh nhân, tên.
FAMILY_WS_TYPES = {"family.state", "family.event", "family.skeleton", "family.access_ended"}


class FakeClock:
    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now


def add_family_user(db: Session, username: str, *, active: bool = True) -> int:
    user = User(
        username=username,
        full_name=f"Người nhà {username}",
        password_hash=hash_password(PASSWORD),
        role=UserRole.FAMILY,
        is_active=active,
    )
    db.add(user)
    db.commit()
    return user.id


def start_session(client: TestClient, login: Login, bed_id: int, patient_id: int) -> int:
    r = client.post(
        "/api/v1/sessions",
        json={"bed_id": bed_id, "patient_id": patient_id},
        headers=login("nurse"),
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def grant(
    client: TestClient,
    login: Login,
    session_id: int,
    user_id: int,
    *,
    by: str = "charge",
    share_level: str | None = None,
    expires_at: datetime | None = None,
    consent_note: str = "Bệnh nhân đồng ý chia sẻ với con gái, 18/11 9:00",
) -> Any:
    body: dict[str, Any] = {"user_id": user_id, "consent_note": consent_note}
    if share_level is not None:
        body["share_level"] = share_level
    if expires_at is not None:
        body["expires_at"] = expires_at.isoformat()
    return client.post(f"/api/v1/sessions/{session_id}/family-grants", json=body, headers=login(by))


def grant_ok(client: TestClient, login: Login, session_id: int, user_id: int, **kw: Any) -> int:
    r = grant(client, login, session_id, user_id, **kw)
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def revoke(client: TestClient, login: Login, grant_id: int, *, by: str = "charge") -> Any:
    return client.post(
        f"/api/v1/family-grants/{grant_id}/revoke",
        json={"reason": "Gia đình yêu cầu"},
        headers=login(by),
    )


def assert_no_image(payload: Any) -> None:
    """Không có byte JPEG (`FF D8`), base64 ảnh hay đường dẫn MJPEG ở bất kỳ đâu (AC5)."""
    text = repr(payload)
    for bad in ("data:image", "stream.mjpeg", "\\xff\\xd8", "/9j/", "jpeg", "jpg", "base64"):
        assert bad not in text.lower(), (bad, text[:300])
    _check_values(payload)


def _check_values(value: Any) -> None:
    if isinstance(value, bytes | bytearray):
        raise AssertionError("payload có bytes")
    if isinstance(value, str):
        assert len(value) < 300, "chuỗi quá dài trong payload người nhà"
    if isinstance(value, dict):
        for v in value.values():
            _check_values(v)
    if isinstance(value, list):
        for v in value:
            _check_values(v)
