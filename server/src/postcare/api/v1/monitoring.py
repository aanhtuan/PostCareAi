"""Tổng quan, sự kiện, timeline theo giường, bàn giao ca (mọi vai trò đã đăng nhập)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from postcare.api.deps import get_current_user, get_db, get_store
from postcare.db.types import utcnow
from postcare.domain import events as ev
from postcare.domain import handover as ho
from postcare.domain import timeline as tl
from postcare.domain.dto import EventOut, HandoverOut, OverviewOut, Page, TimelineItemOut
from postcare.domain.overview import get_overview
from postcare.domain.runtime import RuntimeStore
from postcare.schemas.enums import Priority
from postcare.schemas.events import EventCode

router = APIRouter(tags=["monitoring"], dependencies=[Depends(get_current_user)])


@router.get("/overview", response_model=OverviewOut)
def overview(
    db: Session = Depends(get_db), store: RuntimeStore = Depends(get_store)
) -> OverviewOut:
    return get_overview(db, store, utcnow())


@router.get("/events", response_model=Page[EventOut])
def list_events(
    bed_id: int | None = None,
    session_id: int | None = None,
    from_: AwareDatetime | None = Query(None, alias="from"),
    to: AwareDatetime | None = None,
    priority: list[Priority] | None = Query(None),
    code: EventCode | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[EventOut]:
    return ev.list_events(
        db,
        bed_id=bed_id,
        session_id=session_id,
        from_=from_,
        to=to,
        priorities=priority,
        code=code,
        limit=limit,
        offset=offset,
    )


@router.get("/timeline", response_model=Page[TimelineItemOut])
def bed_timeline(
    bed_id: int,
    from_: AwareDatetime | None = Query(None, alias="from"),
    to: AwareDatetime | None = None,
    priority: list[Priority] | None = Query(None),
    limit: int = Query(200, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Page[TimelineItemOut]:
    return tl.bed_timeline(db, bed_id, from_, to, priority, limit, offset)


@router.get("/handover", response_model=HandoverOut)
def handover(
    shift_id: int | None = None,
    date_: date | None = Query(None, alias="date"),
    from_: AwareDatetime | None = Query(None, alias="from"),
    to: AwareDatetime | None = None,
    db: Session = Depends(get_db),
) -> HandoverOut:
    start, end, shift = ho.resolve_window(db, shift_id=shift_id, day=date_, from_=from_, to=to)
    return ho.build_handover(db, start, end, shift)
