"""Cấp / liệt kê / thu hồi quyền xem của người nhà (F36 R2–R4). Logic ở `domain.family_access`."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from postcare.api.deps import get_now, get_publisher, require_grant_manager, require_staff
from postcare.api.deps import get_session as db_session
from postcare.db.models import User
from postcare.domain import family_access as svc
from postcare.domain.dto import (
    FamilyAccountOut,
    FamilyGrantCreate,
    FamilyGrantOut,
    FamilyGrantRevoke,
    Page,
)
from postcare.domain.notifications import Publisher

router = APIRouter(tags=["family-grants"])


@router.get(
    "/sessions/{session_id}/family-grants",
    response_model=Page[FamilyGrantOut],
    dependencies=[Depends(require_staff)],
)
def list_grants(
    session_id: int, db: Session = Depends(db_session), now: datetime = Depends(get_now)
) -> Page[FamilyGrantOut]:
    return svc.list_session_grants(db, session_id, now)


@router.post("/sessions/{session_id}/family-grants", response_model=FamilyGrantOut, status_code=201)
def create_grant(
    session_id: int,
    body: FamilyGrantCreate,
    actor: User = Depends(require_grant_manager),
    db: Session = Depends(db_session),
    now: datetime = Depends(get_now),
) -> FamilyGrantOut:
    return svc.grant_access(db, session_id=session_id, data=body, actor=actor, now=now)


@router.post("/family-grants/{grant_id}/revoke", response_model=FamilyGrantOut)
def revoke_grant(
    grant_id: int,
    body: FamilyGrantRevoke | None = None,
    actor: User = Depends(require_grant_manager),
    db: Session = Depends(db_session),
    now: datetime = Depends(get_now),
    publisher: Publisher = Depends(get_publisher),
) -> FamilyGrantOut:
    return svc.revoke_access(
        db,
        grant_id=grant_id,
        reason=body.reason if body else None,
        actor=actor,
        now=now,
        publisher=publisher,
    )


@router.get(
    "/family-grants/accounts",
    response_model=Page[FamilyAccountOut],
    dependencies=[Depends(require_grant_manager)],
)
def family_accounts(db: Session = Depends(db_session)) -> Page[FamilyAccountOut]:
    """Tài khoản người nhà đang dùng, để chọn người nhận quyền (giả định F36 §9)."""
    return svc.list_family_accounts(db)
