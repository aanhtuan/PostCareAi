"""Quản lý người dùng, chỉ ADMIN (F35; QA#36; api-conventions.md ma trận quyền)."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from postcare.api.deps import get_publisher, require_admin
from postcare.api.deps import get_session as db_session
from postcare.db.models import User
from postcare.domain import users as svc
from postcare.domain.dto import Page, PasswordReset, UserCreate, UserOut, UserUpdate
from postcare.domain.notifications import Publisher, disconnect_user
from postcare.schemas.enums import UserRole

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserOut], dependencies=[Depends(require_admin)])
def list_users(
    role: UserRole | None = None,
    include_inactive: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
) -> Page[UserOut]:
    return svc.list_users(
        db, role=role, include_inactive=include_inactive, limit=limit, offset=offset
    )


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    actor: User = Depends(require_admin),
    db: Session = Depends(db_session),
) -> UserOut:
    return svc.create_user(db, data=body, actor=actor)


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(require_admin)])
def get_user(user_id: int, db: Session = Depends(db_session)) -> UserOut:
    return svc.get_user(db, user_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    actor: User = Depends(require_admin),
    db: Session = Depends(db_session),
) -> UserOut:
    return svc.update_user(
        db, user_id=user_id, actor=actor, full_name=body.full_name, role=body.role
    )


@router.post("/{user_id}/lock", response_model=UserOut)
def lock_user(
    user_id: int,
    actor: User = Depends(require_admin),
    db: Session = Depends(db_session),
    publisher: Publisher = Depends(get_publisher),
) -> UserOut:
    out, changed = svc.lock_user(db, user_id=user_id, actor=actor)
    if changed:  # sau commit (AGENTS.md quy tắc 7)
        disconnect_user(publisher, user_id)
    return out


@router.post("/{user_id}/unlock", response_model=UserOut)
def unlock_user(
    user_id: int,
    actor: User = Depends(require_admin),
    db: Session = Depends(db_session),
) -> UserOut:
    return svc.unlock_user(db, user_id=user_id, actor=actor)


@router.post("/{user_id}/reset-password", status_code=204, response_class=Response)
def reset_password(
    user_id: int,
    body: PasswordReset,
    actor: User = Depends(require_admin),
    db: Session = Depends(db_session),
) -> Response:
    svc.reset_password(db, user_id=user_id, actor=actor, new_password=body.new_password)
    return Response(status_code=204)
