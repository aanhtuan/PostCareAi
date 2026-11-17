"""Xác thực người dùng."""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import User
from postcare.domain.errors import DomainError
from postcare.domain.security import hash_password, verify_password

# Hash bcrypt của chuỗi ngẫu nhiên, tạo một lần khi import: dùng khi không có tài khoản để
# thời gian kiểm tra gần như nhau (không lộ tài khoản có tồn tại hay không).
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def authenticate(db: Session, username: str, password: str) -> User:
    """Cùng một lỗi cho mọi trường hợp sai, không tiết lộ tài khoản có tồn tại hay không."""
    user = db.scalar(select(User).where(User.username == username.strip()))
    ok = verify_password(password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if user is None or not user.is_active or not ok:
        raise DomainError("INVALID_CREDENTIALS", "Tên đăng nhập hoặc mật khẩu không đúng", 401)
    return user


def get_active_user(db: Session, user_id: int) -> User | None:
    user = db.get(User, user_id)
    return user if user and user.is_active else None
