"""Dependency dùng chung: DB session, settings, kho RAM, publisher, xác thực và phân quyền."""

import secrets
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from postcare.db.models import User
from postcare.domain.errors import DomainError
from postcare.domain.notifications import Publisher
from postcare.domain.runtime import RuntimeStore
from postcare.domain.users import get_active_user
from postcare.schemas.enums import UserRole
from postcare.settings import Settings

_bearer = HTTPBearer(auto_error=False)

# Ma trận quyền (api-conventions.md; QA#18). DOCTOR chỉ đọc.
WRITE_ROLES = (UserRole.NURSE, UserRole.CHARGE_NURSE, UserRole.ADMIN)


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def get_store(request: Request) -> RuntimeStore:
    return request.app.state.store


def get_publisher(request: Request) -> Publisher:
    return request.app.state.hub


def create_token(user: User, settings: Settings, now: datetime | None = None) -> str:
    """`now` chỉ để test giả lập thời điểm cấp token (không `sleep`)."""
    now = now or datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _unauthorized() -> DomainError:
    return DomainError("UNAUTHORIZED", "Chưa đăng nhập hoặc phiên đăng nhập đã hết hạn", 401)


def user_from_token(db: Session, token: str, settings: Settings) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise _unauthorized() from exc
    user = get_active_user(db, user_id)
    if user is None:
        raise _unauthorized()
    return user


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized()
    return user_from_token(db, creds.credentials, settings)


def require_roles(*roles: UserRole) -> Callable[..., User]:
    def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise DomainError("FORBIDDEN", "Không đủ quyền thực hiện thao tác này", 403)
        return user

    return _guard


require_writer = require_roles(*WRITE_ROLES)


def require_worker(
    x_worker_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    if not x_worker_token or not secrets.compare_digest(x_worker_token, settings.worker_token):
        raise DomainError("UNAUTHORIZED", "Worker token không hợp lệ", 401)
