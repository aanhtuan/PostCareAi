"""Ca trực: ca hiện tại, khoảng thời gian của một ca (QA#19); quản lý ca (F37).

Quy tắc ca (F37 R8, giả định):
- giờ dạng `HH:mm` (giây = 0), `start_time ≠ end_time`; `end_time < start_time` là ca qua đêm;
- ca đang dùng không chồng giờ theo `[start, end)` trên vòng 24 giờ (`SHIFT_OVERLAP`);
- tên duy nhất trong các ca đang dùng (`DUPLICATE_CODE`); không bắt buộc phủ kín 24 giờ.
Ca đã xóa vẫn tra cứu bàn giao được (`db.get`, R9) nhưng không vào ca hiện tại/danh sách mặc định.
"""

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from postcare.db.models import ShiftDefinition, User
from postcare.domain.catalog import _audit, _locked
from postcare.domain.dto import ShiftCreate, ShiftOut, ShiftUpdate, shift_out
from postcare.domain.errors import DomainError, validation_error

DISPLAY_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_DAY = 24 * 60
_NOT_FOUND = "Không tìm thấy ca trực"
# Khóa tư vấn trong transaction: tạo/sửa/khôi phục ca chạy tuần tự để kiểm tra chồng giờ đúng.
_SHIFT_LOCK_KEY = 37_0001


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


def list_shifts(db: Session, include_inactive: bool = False) -> list[ShiftDefinition]:
    """Mặc định chỉ ca đang dùng (F37 R7), sắp theo giờ bắt đầu."""
    q = select(ShiftDefinition).order_by(ShiftDefinition.start_time, ShiftDefinition.id)
    if not include_inactive:
        q = q.where(ShiftDefinition.is_active.is_(True))
    return list(db.scalars(q))


# ---------- Chồng giờ (thuần) ----------


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _segments(span: tuple[time, time]) -> list[tuple[int, int]]:
    """Ca → các đoạn phút nửa mở trong [0, 1440); ca qua đêm tách làm hai."""
    start, end = _minutes(span[0]), _minutes(span[1])
    if start < end:
        return [(start, end)]
    return [(start, _DAY), (0, end)]


def shifts_overlap(a: tuple[time, time], b: tuple[time, time]) -> bool:
    """Hai ca `(start, end)` chồng giờ theo `[start, end)` trên vòng 24 giờ (kề nhau: không)."""
    return any(s1 < e2 and s2 < e1 for s1, e1 in _segments(a) for s2, e2 in _segments(b))


# ---------- Quản lý ca (F37) ----------


def _hhmm(t: time) -> str:
    return t.strftime("%H:%M")


def _snapshot(s: ShiftDefinition) -> dict[str, Any]:
    return {
        "name": s.name,
        "start_time": _hhmm(s.start_time),
        "end_time": _hhmm(s.end_time),
        "is_active": s.is_active,
    }


def _check_times(start: time, end: time) -> None:
    for field, t in (("start_time", start), ("end_time", end)):
        if t.second or t.microsecond or t.tzinfo is not None:
            raise validation_error("Giờ ca phải có dạng giờ:phút (ví dụ 06:00)", {"field": field})
    if start == end:
        raise validation_error("Giờ kết thúc phải khác giờ bắt đầu", {"field": "end_time"})


def _lock_shifts(db: Session) -> None:
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _SHIFT_LOCK_KEY})


def _check_active_conflicts(
    db: Session, name: str, start: time, end: time, own_id: int | None
) -> None:
    others = [s for s in list_shifts(db) if s.id != own_id]
    same_name = next((s for s in others if s.name == name), None)
    if same_name is not None:
        raise DomainError(
            "DUPLICATE_CODE",
            f"Tên ca {name} đã có trong các ca đang dùng",
            409,
            {"field": "name", "existing_id": same_name.id},
        )
    conflicts = [s for s in others if shifts_overlap((start, end), (s.start_time, s.end_time))]
    if conflicts:
        names = ", ".join(
            f"{s.name} ({_hhmm(s.start_time)}–{_hhmm(s.end_time)})" for s in conflicts
        )
        raise DomainError(
            "SHIFT_OVERLAP",
            f"Giờ ca bị chồng với: {names}",
            409,
            {"conflicting_shift_ids": [s.id for s in conflicts]},
        )


def create_shift(db: Session, data: ShiftCreate, user: User) -> ShiftOut:
    _check_times(data.start_time, data.end_time)
    _lock_shifts(db)
    _check_active_conflicts(db, data.name, data.start_time, data.end_time, None)
    shift = ShiftDefinition(name=data.name, start_time=data.start_time, end_time=data.end_time)
    db.add(shift)
    db.flush()
    _audit(db, user, "shift.create", shift, None, _snapshot(shift))
    db.commit()
    return shift_out(shift)


def update_shift(db: Session, shift_id: int, data: ShiftUpdate, user: User) -> ShiftOut:
    _lock_shifts(db)
    shift = _locked(db, ShiftDefinition, shift_id, _NOT_FOUND)
    before = _snapshot(shift)
    name = data.name if data.name is not None else shift.name
    start = data.start_time if data.start_time is not None else shift.start_time
    end = data.end_time if data.end_time is not None else shift.end_time
    _check_times(start, end)
    if shift.is_active:
        _check_active_conflicts(db, name, start, end, shift.id)
    shift.name, shift.start_time, shift.end_time = name, start, end
    after = _snapshot(shift)
    if after != before:
        _audit(db, user, "shift.update", shift, before, after)
    db.commit()
    return shift_out(shift)


def delete_shift(db: Session, shift_id: int, user: User) -> ShiftOut:
    shift = _locked(db, ShiftDefinition, shift_id, _NOT_FOUND)
    if shift.is_active:
        before = _snapshot(shift)
        shift.is_active = False
        _audit(db, user, "shift.delete", shift, before, _snapshot(shift))
    db.commit()
    return shift_out(shift)


def restore_shift(db: Session, shift_id: int, user: User) -> ShiftOut:
    _lock_shifts(db)
    shift = _locked(db, ShiftDefinition, shift_id, _NOT_FOUND)
    if not shift.is_active:
        _check_active_conflicts(db, shift.name, shift.start_time, shift.end_time, shift.id)
        before = _snapshot(shift)
        shift.is_active = True
        _audit(db, user, "shift.restore", shift, before, _snapshot(shift))
    db.commit()
    return shift_out(shift)
