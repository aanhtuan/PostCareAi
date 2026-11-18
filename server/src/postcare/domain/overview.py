"""Dữ liệu màn hình Tổng quan (F09, F21): thẻ giường + ca hiện tại."""

from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from postcare.db.models import Alert, Bed, Event, MonitoringSession
from postcare.domain.alerts import PRIORITY_RANK_SQL
from postcare.domain.dto import (
    OverviewBedOut,
    OverviewOut,
    OverviewSessionOut,
    camera_ref,
    shift_out,
)
from postcare.domain.runtime import RuntimeStore
from postcare.domain.shifts import current_shift, list_shifts
from postcare.schemas.enums import PRIORITY_RANK, AlertStatus

_RANK_TO_PRIORITY = {rank: p for p, rank in PRIORITY_RANK.items()}


def _alert_stats(db: Session) -> dict[int, tuple[int, int, int | None]]:
    """(pending, acknowledged, hạng ưu tiên cao nhất) theo giường, bằng SQL GROUP BY."""
    rows = db.execute(
        select(
            Event.bed_id,
            func.sum(case((Alert.status == AlertStatus.PENDING, 1), else_=0)),
            func.sum(case((Alert.status == AlertStatus.ACKNOWLEDGED, 1), else_=0)),
            func.max(PRIORITY_RANK_SQL),
        )
        .join(Alert, Alert.event_id == Event.id)
        .where(Alert.status != AlertStatus.RESOLVED, Event.bed_id.is_not(None))
        .group_by(Event.bed_id)
    ).all()
    return {r[0]: (int(r[1] or 0), int(r[2] or 0), r[3]) for r in rows}


def get_overview(db: Session, store: RuntimeStore, now: datetime) -> OverviewOut:
    shift = current_shift(now, list_shifts(db))
    beds = db.scalars(
        select(Bed)
        .where(Bed.is_active.is_(True))
        .options(selectinload(Bed.camera), selectinload(Bed.area))
        .order_by(Bed.code)
    )
    sessions = {
        s.bed_id: s
        for s in db.scalars(
            select(MonitoringSession)
            .where(MonitoringSession.ended_at.is_(None))
            .options(selectinload(MonitoringSession.patient))
        )
    }
    stats = _alert_stats(db)
    items: list[OverviewBedOut] = []
    for bed in beds:
        s = sessions.get(bed.id)
        pending, acked, rank = stats.get(bed.id, (0, 0, None))
        items.append(
            OverviewBedOut(
                bed_id=bed.id,
                code=bed.code,
                area=bed.area.name,
                session=OverviewSessionOut(
                    id=s.id,
                    patient_code=s.patient.code,
                    started_at=s.started_at,
                    paused_at=s.paused_at,
                )
                if s
                else None,
                camera=camera_ref(bed.camera),
                pending_alert_count=pending,
                acknowledged_alert_count=acked,
                max_open_priority=_RANK_TO_PRIORITY.get(rank) if rank is not None else None,
                state=store.get_bed_state(bed.id),
            )
        )
    return OverviewOut(current_shift=shift_out(shift) if shift else None, beds=items)
