"""Xác thực người dùng."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import User
from postcare.domain.errors import DomainError
from postcare.domain.security import verify_password


def authenticate(db: Session, username: str, password: str) -> User:
    """Cùng một lỗi cho mọi trường hợp sai, không tiết lộ tài khoản có tồn tại hay không."""
    user = db.scalar(select(User).where(User.username == username.strip()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise DomainError("INVALID_CREDENTIALS", "Tên đăng nhập hoặc mật khẩu không đúng", 401)
    return user


def get_active_user(db: Session, user_id: int) -> User | None:
    user = db.get(User, user_id)
    return user if user and user.is_active else None
