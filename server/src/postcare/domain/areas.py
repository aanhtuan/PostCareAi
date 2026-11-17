"""Khu vực (F37): thêm, sửa, xóa mềm, khôi phục; theo pattern danh mục F03 (`catalog.py`).

- Mã duy nhất kể cả khu vực đã xóa (R1). Trùng → 409 `DUPLICATE_CODE`.
- Xóa khu vực còn giường đang dùng → 409 `AREA_IN_USE`, `details.bed_ids` (R5).
- Xóa/khôi phục lặp lại: không đổi, không audit (R11). Audit `area.*` có before/after (R12).
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from postcare.db.models import Area, Bed, User
from postcare.domain.catalog import _audit, _check_code, _flush, _locked, _page
from postcare.domain.dto import AreaCreate, AreaOut, AreaUpdate, Page, area_out
from postcare.domain.errors import DomainError, not_found

_LABEL = "Mã khu vực"
_NOT_FOUND = "Không tìm thấy khu vực"


def _snapshot(a: Area) -> dict[str, Any]:
    return {"code": a.code, "name": a.name, "is_active": a.is_active}


def _active_bed_ids(db: Session, area_id: int) -> list[int]:
    q = select(Bed.id).where(Bed.area_id == area_id, Bed.is_active.is_(True)).order_by(Bed.id)
    return list(db.scalars(q))


def _out(db: Session, a: Area) -> AreaOut:
    return area_out(a, len(_active_bed_ids(db, a.id)))


def _conflict(code: str) -> DomainError:
    return DomainError("DUPLICATE_CODE", f"{_LABEL} {code} đã tồn tại", 409, {"field": "code"})


def list_areas(
    db: Session, include_inactive: bool = False, limit: int = 50, offset: int = 0
) -> Page[AreaOut]:
    q = select(Area).order_by(Area.code)
    if not include_inactive:
        q = q.where(Area.is_active.is_(True))
    counts: dict[int, int] = dict(
        db.execute(  # type: ignore[arg-type]
            select(Bed.area_id, func.count()).where(Bed.is_active.is_(True)).group_by(Bed.area_id)
        ).all()
    )
    return _page(db, q, limit, offset, lambda a: area_out(a, counts.get(a.id, 0)))


def create_area(db: Session, data: AreaCreate, user: User) -> AreaOut:
    _check_code(db, Area, _LABEL, data.code, None)
    area = Area(code=data.code, name=data.name)
    db.add(area)
    _flush(db, _conflict(data.code))
    _audit(db, user, "area.create", area, None, _snapshot(area))
    db.commit()
    return _out(db, area)


def update_area(db: Session, area_id: int, data: AreaUpdate, user: User) -> AreaOut:
    area = _locked(db, Area, area_id, _NOT_FOUND)
    before = _snapshot(area)
    if data.code is not None and data.code != area.code:
        _check_code(db, Area, _LABEL, data.code, area.id)
        area.code = data.code
    if data.name is not None:
        area.name = data.name
    after = _snapshot(area)
    if after != before:
        _flush(db, _conflict(area.code))
        _audit(db, user, "area.update", area, before, after)
    db.commit()
    return _out(db, area)


def delete_area(db: Session, area_id: int, user: User) -> AreaOut:
    area = _locked(db, Area, area_id, _NOT_FOUND)
    if area.is_active:
        bed_ids = _active_bed_ids(db, area.id)
        if bed_ids:
            raise DomainError(
                "AREA_IN_USE",
                f"Khu vực {area.name} còn {len(bed_ids)} giường đang dùng. "
                "Chuyển hoặc xóa các giường đó trước.",
                409,
                {"bed_ids": bed_ids},
            )
        before = _snapshot(area)
        area.is_active = False
        _audit(db, user, "area.delete", area, before, _snapshot(area))
    db.commit()
    return _out(db, area)


def restore_area(db: Session, area_id: int, user: User) -> AreaOut:
    area = _locked(db, Area, area_id, _NOT_FOUND)
    if not area.is_active:
        before = _snapshot(area)
        area.is_active = True
        _audit(db, user, "area.restore", area, before, _snapshot(area))
    db.commit()
    return _out(db, area)


def get_area(db: Session, area_id: int) -> AreaOut:
    area = db.get(Area, area_id)
    if area is None:
        raise not_found(_NOT_FOUND)
    return _out(db, area)
