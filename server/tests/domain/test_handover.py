"""F24 AC2, AC3, R3–R5: tổng hợp bàn giao ca bằng SQL trên dữ liệu chèn trực tiếp.

Dữ liệu seed: giường A01/A02/A03 (id 1–3), camera 1–3. Ngày mốc 12/10/2026 (đã qua, nên
"cuối khoảng" là `to`, không phải hiện tại). Giờ VN = UTC+7.
"""

from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from postcare.db.models import Bed, ShiftDefinition
from postcare.domain.handover import build_handover, resolve_window
from postcare.domain.shifts import shift_window
from postcare.schemas.enums import AlertOutcome, Priority
from postcare.schemas.events import EventCode
from tests.handover_data import add_event, z

DAY = date(2026, 10, 12)
VN = timezone(timedelta(hours=7))


def handover(db: Session, start: datetime, end: datetime):  # type: ignore[no-untyped-def]
    db.expire_all()
    return build_handover(db, start, end, None)


def bed(body, code: str):  # type: ignore[no-untyped-def]
    return next(b for b in body.beds if b.code == code)


def shift(db: Session, name: str) -> ShiftDefinition:
    return db.scalars(select(ShiftDefinition).where(ShiftDefinition.name == name)).one()


def total_events(body, code: str = "A01") -> int:  # type: ignore[no-untyped-def]
    return sum(bed(body, code).event_counts.values())


# ------------------------------------------------------------------------------------ AC2


def test_outstanding_includes_older_unresolved_excludes_resolved_before_end(
    db: Session,
) -> None:
    start, end = z(10), z(12)
    older = add_event(db, EventCode.BED_EDGE, z(8), priority=Priority.MEDIUM, alert=True)
    add_event(
        db, EventCode.BED_EXIT, z(10, 30), priority=Priority.HIGH, alert=True, resolved_at=z(11)
    )
    later = add_event(
        db, EventCode.BED_EXIT, z(10, 40), priority=Priority.HIGH, alert=True, resolved_at=z(13)
    )
    at_end = add_event(
        db, EventCode.BED_EXIT, z(10, 50), priority=Priority.HIGH, alert=True, resolved_at=z(12)
    )
    add_event(db, EventCode.BED_EXIT, z(12, 30), priority=Priority.HIGH, alert=True)  # sau `to`
    # Sự kiện trong khoảng nhưng bản ghi cảnh báo tạo muộn (gửi trễ / dữ liệu lịch sử).
    late = add_event(
        db,
        EventCode.STAND_UP,
        z(11),
        priority=Priority.MEDIUM,
        alert=True,
        alert_created_at=datetime.now(UTC),
    )
    assert older and later and at_end and late

    body = handover(db, start, end)
    ids = [a.id for a in body.outstanding_alerts]
    assert set(ids) == {older.id, later.id, at_end.id, late.id}
    a01 = bed(body, "A01")
    # Trong khoảng: 4 cảnh báo; chỉ cái xử lý lúc 11:00 là "đã xử lý" trước cuối khoảng.
    assert (a01.alerts_resolved, a01.alerts_unresolved) == (1, 3)


def test_outstanding_order_high_first_then_oldest(db: Session) -> None:
    m_old = add_event(db, EventCode.BED_EDGE, z(9), priority=Priority.MEDIUM, alert=True)
    h_new = add_event(db, EventCode.BED_EXIT, z(11), priority=Priority.HIGH, alert=True, bed_id=2)
    m_new = add_event(db, EventCode.BED_EDGE, z(10, 30), priority=Priority.MEDIUM, alert=True)
    h_old = add_event(db, EventCode.BED_EXIT, z(10), priority=Priority.HIGH, alert=True, bed_id=3)
    h_tie = add_event(db, EventCode.BED_EXIT, z(10), priority=Priority.HIGH, alert=True)
    assert m_old and h_new and m_new and h_old and h_tie
    body = handover(db, z(10), z(12))
    assert [a.id for a in body.outstanding_alerts] == [
        h_old.id,
        h_tie.id,  # trùng giờ: theo id
        h_new.id,
        m_old.id,
        m_new.id,
    ]


# ------------------------------------------------------------------------------------ AC3


def test_counts_match_seed_data(db: Session) -> None:
    afternoon = shift(db, "Ca chiều")
    start, end, _ = resolve_window(db, shift_id=afternoon.id, day=DAY, from_=None, to=None)
    assert (start, end) == (z(7), z(15))
    add_event(db, EventCode.SIT_UP, z(8))
    add_event(db, EventCode.BED_EDGE, z(8, 1), priority=Priority.MEDIUM, alert=True)
    add_event(
        db, EventCode.BED_EXIT, z(8, 2), priority=Priority.HIGH, alert=True, resolved_at=z(8, 10)
    )
    add_event(db, EventCode.RETURN_TO_BED, z(8, 20))
    add_event(db, EventCode.SIT_UP, z(9))
    add_event(db, EventCode.ACTIVITY_INCREASED, z(9, 30), bed_id=2, priority=Priority.MEDIUM)
    add_event(db, EventCode.SIT_UP, z(6, 59))  # ca sáng: không đếm
    add_event(db, EventCode.SIT_UP, z(15))  # ca đêm: không đếm

    body = handover(db, start, end)
    assert [b.code for b in body.beds] == ["A01", "A02", "A03"]
    a01, a02, a03 = body.beds
    assert a01.event_counts == {
        EventCode.BED_EDGE: 1,
        EventCode.BED_EXIT: 1,
        EventCode.RETURN_TO_BED: 1,
        EventCode.SIT_UP: 2,
    }
    assert list(a01.event_counts) == sorted(a01.event_counts)  # sắp theo mã, in ổn định
    assert (a01.alerts_resolved, a01.alerts_unresolved, a01.state_change_count) == (1, 1, 5)
    assert a02.event_counts == {EventCode.ACTIVITY_INCREASED: 1}
    assert (a02.alerts_resolved, a02.alerts_unresolved, a02.state_change_count) == (0, 0, 0)
    assert a03.event_counts == {} and a03.state_change_count == 0


def test_night_shift_crosses_midnight(db: Session) -> None:
    night = shift(db, "Ca đêm")
    start, end, s = resolve_window(db, shift_id=night.id, day=DAY, from_=None, to=None)
    assert s is night
    assert (start, end) == (z(15), z(23))  # 22:00 12/10 → 06:00 13/10 giờ VN
    add_event(db, EventCode.SIT_UP, z(14, 59))  # 21:59 VN: ca chiều
    add_event(db, EventCode.SIT_UP, z(15))  # 22:00 VN
    add_event(db, EventCode.SIT_UP, z(18))  # 01:00 VN ngày 13/10, vẫn ca đêm 12/10
    add_event(db, EventCode.SIT_UP, z(22, 59))  # 05:59 VN
    add_event(db, EventCode.SIT_UP, z(23))  # 06:00 VN: ca sáng 13/10
    assert total_events(handover(db, start, end)) == 3
    # Ca đêm ngày 11/10 kết thúc lúc 06:00 12/10 = 23:00Z 11/10: không lấy sự kiện của 12/10.
    s11, e11, _ = resolve_window(db, shift_id=night.id, day=date(2026, 10, 11), from_=None, to=None)
    assert total_events(handover(db, s11, e11)) == 0


def test_event_at_boundary_counted_once(db: Session) -> None:
    morning, afternoon = shift(db, "Ca sáng"), shift(db, "Ca chiều")
    add_event(db, EventCode.POSTURE_CHANGE, z(7))  # đúng 14:00 VN
    m = handover(db, *shift_window(morning, DAY))
    a = handover(db, *shift_window(afternoon, DAY))
    assert total_events(m) == 0 and m.beds[0].state_change_count == 0
    assert total_events(a) == 1 and a.beds[0].state_change_count == 1


def test_local_time_to_utc_conversion(db: Session) -> None:
    start, end, s = resolve_window(
        db,
        shift_id=None,
        day=None,
        from_=datetime(2026, 10, 12, 17, 0, tzinfo=VN),
        to=datetime(2026, 10, 12, 19, 30, tzinfo=VN),
    )
    assert s is None
    assert (start, end) == (z(10), z(12, 30))
    assert start.tzinfo == UTC and end.tzinfo == UTC
    morning = shift(db, "Ca sáng")
    start, end, _ = resolve_window(db, shift_id=morning.id, day=DAY, from_=None, to=None)
    assert (start, end) == (z(23, day=11), z(7))  # 06:00–14:00 VN


# ------------------------------------------------------------------------------------ R3


def test_state_change_count_only_posture_codes(db: Session) -> None:
    posture = [
        EventCode.POSTURE_CHANGE,
        EventCode.SIT_UP,
        EventCode.STAND_UP,
        EventCode.BED_EDGE,
        EventCode.BED_EXIT,
        EventCode.RETURN_TO_BED,
    ]
    others = [
        EventCode.ACTIVITY_INCREASED,
        EventCode.ACTIVITY_LOW_PROLONGED,
        EventCode.ABNORMAL_MOVEMENT,
        EventCode.FACE_ATTENTION,
        EventCode.OBSERVATION_LOST,
        EventCode.OBSERVATION_RESTORED,
        EventCode.CAMERA_OFFLINE,
        EventCode.CAMERA_ONLINE,
    ]
    for i, code in enumerate(posture + others):
        add_event(db, code, z(10, i))
    a01 = bed(handover(db, z(10), z(11)), "A01")
    assert a01.state_change_count == len(posture)
    assert sum(a01.event_counts.values()) == len(posture) + len(others)


def test_outcome_counts(db: Session) -> None:
    for outcome in (AlertOutcome.CONFIRMED, AlertOutcome.CONFIRMED, AlertOutcome.FALSE_ALARM):
        add_event(
            db,
            EventCode.BED_EXIT,
            z(10, 10),
            priority=Priority.HIGH,
            alert=True,
            resolved_at=z(10, 30),
            outcome=outcome,
        )
    # Ghi kết quả (chưa xử lý) trong khoảng: vẫn tính.
    add_event(
        db,
        EventCode.BED_EDGE,
        z(10, 20),
        priority=Priority.MEDIUM,
        alert=True,
        outcome=AlertOutcome.PATIENT_SAFE,
        outcome_at=z(10, 25),
    )
    # Ghi kết quả sau cuối khoảng: chưa có tại `to`.
    add_event(
        db,
        EventCode.BED_EDGE,
        z(10, 40),
        priority=Priority.MEDIUM,
        alert=True,
        resolved_at=z(13),
        outcome=AlertOutcome.PATIENT_SAFE,
    )
    # Sự kiện ngoài khoảng: không tính.
    add_event(
        db,
        EventCode.BED_EXIT,
        z(9),
        priority=Priority.HIGH,
        alert=True,
        resolved_at=z(10, 5),
        outcome=AlertOutcome.FALSE_ALARM,
    )
    body = handover(db, z(10), z(12))
    assert bed(body, "A01").outcome_counts == {
        AlertOutcome.CONFIRMED: 2,
        AlertOutcome.FALSE_ALARM: 1,
        AlertOutcome.PATIENT_SAFE: 1,
    }
    assert bed(body, "A02").outcome_counts == {}


# ------------------------------------------------------------------------------- giường đã xóa


def test_deleted_bed_with_events_listed(db: Session) -> None:
    add_event(db, EventCode.SIT_UP, z(10, 5), bed_id=3)
    db.execute(update(Bed).where(Bed.id.in_([2, 3])).values(is_active=False))
    db.commit()
    body = handover(db, z(10), z(11))
    # A02 đã xóa, không có sự kiện: ẩn. A03 đã xóa nhưng có sự kiện trong khoảng: vẫn hiện.
    assert [(b.code, b.is_active) for b in body.beds] == [("A01", True), ("A03", False)]
    assert bed(body, "A03").event_counts == {EventCode.SIT_UP: 1}
