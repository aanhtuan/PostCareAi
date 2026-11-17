"""F02 review: `authenticate` luôn chạy verify_password, kể cả khi không có tài khoản.

Mục đích: thời gian trả lời gần như nhau, không lộ tài khoản có tồn tại hay không.
"""

import pytest
from sqlalchemy.orm import Session

from postcare.db.models import User
from postcare.domain import users
from postcare.domain.errors import DomainError
from postcare.domain.security import hash_password
from postcare.schemas.enums import UserRole

PASSWORD = "mat-khau-dung"


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    real = users.verify_password

    def _spy(password: str, password_hash: str) -> bool:
        seen.append((password, password_hash))
        return real(password, password_hash)

    monkeypatch.setattr(users, "verify_password", _spy)
    return seen


def _add_user(db: Session, username: str, *, active: bool = True) -> User:
    user = User(
        username=username,
        full_name="Người dùng thử",
        password_hash=hash_password(PASSWORD),
        role=UserRole.NURSE,
        is_active=active,
    )
    db.add(user)
    db.flush()
    return user


def test_unknown_user_still_verifies_against_dummy_hash(
    db_session: Session, calls: list[tuple[str, str]]
) -> None:
    with pytest.raises(DomainError) as exc:
        users.authenticate(db_session, "khong-ton-tai-f02", PASSWORD)
    assert exc.value.code == "INVALID_CREDENTIALS"
    assert len(calls) == 1
    password, password_hash = calls[0]
    assert password == PASSWORD
    assert password_hash == users.DUMMY_PASSWORD_HASH
    assert password_hash.startswith("$2")  # bcrypt thật, tốn thời gian như hash thật


def test_known_user_verifies_against_own_hash(
    db_session: Session, calls: list[tuple[str, str]]
) -> None:
    user = _add_user(db_session, "f02-known")
    assert users.authenticate(db_session, "f02-known", PASSWORD).id == user.id
    assert calls == [(PASSWORD, user.password_hash)]


def test_wrong_password_and_inactive_user_also_verify(
    db_session: Session, calls: list[tuple[str, str]]
) -> None:
    _add_user(db_session, "f02-wrong")
    _add_user(db_session, "f02-inactive", active=False)
    for username, password in (("f02-wrong", "sai"), ("f02-inactive", PASSWORD)):
        with pytest.raises(DomainError) as exc:
            users.authenticate(db_session, username, password)
        assert exc.value.code == "INVALID_CREDENTIALS"
    assert len(calls) == 2


def test_dummy_hash_never_matches_common_passwords() -> None:
    for password in ("", "postcare", "change-me", PASSWORD):
        assert not users.verify_password(password, users.DUMMY_PASSWORD_HASH)
