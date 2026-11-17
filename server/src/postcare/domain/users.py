"""Xác thực người dùng (F02) và quản lý tài khoản (F35)."""

import secrets
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from postcare.db.models import User
from postcare.domain.audit import record_audit
from postcare.domain.dto import Page, UserCreate, UserOut, user_out
from postcare.domain.errors import DomainError, not_found
from postcare.domain.security import hash_password, verify_password
from postcare.schemas.enums import STAFF_ROLES, UserRole

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


# ---------- Quản lý người dùng (F35) ----------
# Mọi hàm ghi audit cùng transaction rồi commit. `before`/`after` chỉ gồm các trường dưới đây,
# không bao giờ có mật khẩu hay hash (F35 R10; PRD NFR08).
_AUDIT_FIELDS = ("username", "full_name", "role", "is_active")


def _snapshot(user: User) -> dict[str, Any]:
    return {f: getattr(user, f) for f in _AUDIT_FIELDS}


def _get(db: Session, user_id: int, *, for_update: bool = False) -> User:
    q = select(User).where(User.id == user_id)
    if for_update:
        q = q.with_for_update()
    user = db.scalar(q)
    if user is None:
        raise not_found("Không tìm thấy người dùng")
    return user


def list_users(
    db: Session,
    *,
    role: UserRole | None,
    include_inactive: bool,
    limit: int,
    offset: int,
) -> Page[UserOut]:
    q = select(User)
    if role is not None:
        q = q.where(User.role == role)
    if not include_inactive:
        q = q.where(User.is_active.is_(True))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(User.username).limit(limit).offset(offset))
    return Page[UserOut](items=[user_out(u) for u in rows], total=total)


def get_user(db: Session, user_id: int) -> UserOut:
    return user_out(_get(db, user_id))


def _duplicate() -> DomainError:
    return DomainError("DUPLICATE_CODE", "Tên đăng nhập đã tồn tại", 409, {"field": "username"})


def create_user(db: Session, *, data: UserCreate, actor: User) -> UserOut:
    """`data.username` đã chuẩn hóa ở schema (chữ thường, bỏ khoảng trắng)."""
    if db.scalar(select(User.id).where(func.lower(User.username) == data.username)):
        raise _duplicate()
    user = User(
        username=data.username,
        full_name=data.full_name,
        role=data.role,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:  # hai yêu cầu đồng thời: unique constraint chặn
        db.rollback()
        raise _duplicate() from exc
    record_audit(
        db,
        actor_user_id=actor.id,
        action="user.create",
        entity_type="user",
        entity_id=user.id,
        after=_snapshot(user),
    )
    db.commit()
    return user_out(user)


def _guard_admin_loss(db: Session, target: User, actor: User) -> None:
    """Chặn mất quyền quản trị khi `target` sắp bị khóa hoặc rời vai trò ADMIN (F35 R8).

    Kiểm tra ADMIN cuối cùng trước (khóa các dòng ADMIN đang hoạt động để hai yêu cầu đồng
    thời không cùng lọt), rồi mới tới tự thao tác lên chính mình.
    """
    if target.role == UserRole.ADMIN and target.is_active:
        admins = db.scalars(
            select(User.id)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
            .with_for_update()
        ).all()
        if len(admins) <= 1:
            raise DomainError(
                "LAST_ADMIN", "Không thể khóa hoặc đổi vai trò quản trị viên cuối cùng", 409
            )
    if target.id == actor.id:
        raise DomainError(
            "CANNOT_MODIFY_SELF", "Không thể tự khóa hoặc tự đổi vai trò của chính mình", 409
        )


def update_user(
    db: Session,
    *,
    user_id: int,
    actor: User,
    full_name: str | None = None,
    role: UserRole | None = None,
) -> tuple[UserOut, bool]:
    """Trả `(user, left_staff)`: `left_staff` khi vai trò đổi từ nhân viên sang vai trò khác
    (ví dụ FAMILY); người gọi đóng luồng realtime nhân viên của người đó sau commit."""
    user = _get(db, user_id, for_update=True)
    was_staff = user.role in STAFF_ROLES
    before = _snapshot(user)
    if role is not None and role != user.role and user.role == UserRole.ADMIN:
        _guard_admin_loss(db, user, actor)
    if full_name is not None:
        user.full_name = full_name
    if role is not None:
        user.role = role
    after = _snapshot(user)
    if after != before:
        record_audit(
            db,
            actor_user_id=actor.id,
            action="user.update",
            entity_type="user",
            entity_id=user.id,
            before=before,
            after=after,
        )
    db.commit()
    return user_out(user), was_staff and user.role not in STAFF_ROLES


def _set_active(db: Session, user_id: int, actor: User, active: bool) -> tuple[UserOut, bool]:
    user = _get(db, user_id, for_update=True)
    if user.is_active == active:  # thao tác lặp: không đổi, không audit (F35 R7)
        db.commit()
        return user_out(user), False
    if not active:
        _guard_admin_loss(db, user, actor)
    before = _snapshot(user)
    user.is_active = active
    record_audit(
        db,
        actor_user_id=actor.id,
        action="user.unlock" if active else "user.lock",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=_snapshot(user),
    )
    db.commit()
    return user_out(user), True


def lock_user(db: Session, *, user_id: int, actor: User) -> tuple[UserOut, bool]:
    """Trả `(user, changed)`; người gọi đóng kết nối realtime khi `changed` (sau commit)."""
    return _set_active(db, user_id, actor, False)


def unlock_user(db: Session, *, user_id: int, actor: User) -> UserOut:
    return _set_active(db, user_id, actor, True)[0]


def reset_password(db: Session, *, user_id: int, actor: User, new_password: str) -> None:
    user = _get(db, user_id, for_update=True)
    user.password_hash = hash_password(new_password)
    user.token_version += 1  # token cũ hết hiệu lực; người gọi đóng WS sau commit
    record_audit(
        db,
        actor_user_id=actor.id,
        action="user.reset_password",
        entity_type="user",
        entity_id=user.id,
        after={"username": user.username},
    )
    db.commit()
