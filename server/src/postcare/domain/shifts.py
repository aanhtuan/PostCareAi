"""Ca trực: tính ca hiện tại và khoảng thời gian của một ca (QA#19)."""

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import ShiftDefinition

DISPLAY_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _in_shift(t: time, start: time, end: time) -> bool:
    if start < end:
        return start <= t < end
    # Ca vắt qua nửa đêm (ví dụ 22:00–06:00).
    return t >= start or t < end


def current_shift(now: datetime, shifts: Sequence[ShiftDefinition]) -> ShiftDefinition | None:
    """Ca có `start ≤ giờ hiện tại < end` theo Asia/Ho_Chi_Minh; không khớp → None."""
    local_t = now.astimezone(DISPLAY_TZ).time()
    for s in shifts:
        if _in_shift(local_t, s.start_time, s.end_time):
            return s
    return None


def shift_start_date(now: datetime, shift: ShiftDefinition) -> date:
    """Ngày bắt đầu của lần chạy ca `shift` chứa `now` (ca đêm sau 00:00 thuộc ngày hôm trước)."""
    local = now.astimezone(DISPLAY_TZ)
    if shift.start_time > shift.end_time and local.time() < shift.end_time:
        return local.date() - timedelta(days=1)
    return local.date()


def shift_window(shift: ShiftDefinition, day: date) -> tuple[datetime, datetime]:
    """Khoảng nửa mở `[start, end)` của ca bắt đầu vào ngày `day` (giờ VN), trả về có tz."""
    start = datetime.combine(day, shift.start_time, DISPLAY_TZ)
    end_day = day if shift.start_time < shift.end_time else day + timedelta(days=1)
    end = datetime.combine(end_day, shift.end_time, DISPLAY_TZ)
    return start, end


def list_shifts(db: Session) -> list[ShiftDefinition]:
    return list(db.scalars(select(ShiftDefinition).order_by(ShiftDefinition.start_time)))
