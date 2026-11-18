"""Endpoint của người nhà (F36 R7): chỉ vai trò `FAMILY`, chỉ dữ liệu của grant đang hiệu lực."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from postcare.api.deps import get_now, get_store, require_family
from postcare.api.deps import get_session as db_session
from postcare.db.models import User
from postcare.domain import family_access as svc
from postcare.domain.dto import FamilyGrantSummaryOut, FamilyTimelineItemOut, FamilyViewOut, Page
from postcare.domain.runtime import RuntimeStore

router = APIRouter(prefix="/family", tags=["family"])


@router.get("/grants", response_model=Page[FamilyGrantSummaryOut])
def my_grants(
    user: User = Depends(require_family),
    db: Session = Depends(db_session),
    now: datetime = Depends(get_now),
) -> Page[FamilyGrantSummaryOut]:
    return svc.my_grants(db, user, now)


@router.get("/grants/{grant_id}/view", response_model=FamilyViewOut)
def view(
    grant_id: int,
    user: User = Depends(require_family),
    db: Session = Depends(db_session),
    store: RuntimeStore = Depends(get_store),
    now: datetime = Depends(get_now),
) -> FamilyViewOut:
    return svc.family_view(db, user=user, grant_id=grant_id, store=store, now=now)


@router.get("/grants/{grant_id}/timeline", response_model=Page[FamilyTimelineItemOut])
def timeline(
    grant_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_family),
    db: Session = Depends(db_session),
    now: datetime = Depends(get_now),
) -> Page[FamilyTimelineItemOut]:
    return svc.family_timeline(
        db, user=user, grant_id=grant_id, limit=limit, offset=offset, now=now
    )
