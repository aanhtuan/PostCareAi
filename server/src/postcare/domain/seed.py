"""Dữ liệu mẫu.

- `seed_base` (F01 R7–R9, `make db-seed`): tài khoản 4 vai trò, 3 ca trực, khu vực
  "Khu hậu phẫu" (F37), giường A01–A03, 1 camera gắn A01. Idempotent theo khóa tự nhiên:
  chỉ thêm bản ghi còn thiếu, không sửa bản ghi có sẵn (R8). Ca mẫu chồng giờ một ca đang
  dùng (ADMIN đã tạo ở F37) thì bỏ qua, để không vi phạm quy tắc không chồng giờ (F37 R8).
- `seed_demo` + `seed_history` (prototype ADR-0010, chỉ `postcare seed --reset` / `make seed`):
  camera A02/A03, ROI mẫu, bệnh nhân mã thử nghiệm BN-001…BN-005, phiên mở và sự kiện quá khứ
  cho A02/A03 để dashboard giống HS Hình 3 (A01 Đang theo dõi, A02 Cần kiểm tra, A03 Cảnh báo
  mới). F30 sẽ thay bằng `make demo-seed`.
"""

import uuid
from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import (
    Alert,
    Area,
    Bed,
    Camera,
    Event,
    MonitoringSession,
    Patient,
    ShiftDefinition,
    User,
)
from postcare.domain.audit import record_audit
from postcare.domain.security import hash_password
from postcare.domain.shifts import list_shifts, shifts_overlap
from postcare.schemas.enums import (
    AlertOutcome,
    AlertStatus,
    CameraSourceType,
    ObservationQuality,
    UserRole,
)
from postcare.schemas.events import ALERT_PRIORITIES, EventCode, default_priority

AREA = "Khu hậu phẫu"  # giả định F01
AREA_CODE = "KV01"  # trùng mã migration 0006 sinh cho DB cũ có khu vực này (F37 R2)
BED_CODES = ("A01", "A02", "A03")  # HS Hình 3
DEMO_ROI = [[0.2, 0.25], [0.8, 0.25], [0.8, 0.85], [0.2, 0.85]]

SEED_USERS: list[tuple[str, str, UserRole]] = [
    ("nurse", "Nguyễn Thị Hoa", UserRole.NURSE),
    ("charge", "Trần Văn Minh", UserRole.CHARGE_NURSE),
    ("doctor", "Lê Quốc Bảo", UserRole.DOCTOR),
    ("admin", "Phạm Thu Hà", UserRole.ADMIN),
]

SEED_SHIFTS: list[tuple[str, time, time]] = [
    ("Ca sáng", time(6, 0), time(14, 0)),
    ("Ca chiều", time(14, 0), time(22, 0)),
    ("Ca đêm", time(22, 0), time(6, 0)),
]


def _webcam(name: str, bed: Bed) -> Camera:
    return Camera(name=name, bed_id=bed.id, source_type=CameraSourceType.WEBCAM, source="0")


def _needs_camera(db: Session, bed: Bed, name: str) -> bool:
    """Giường chưa có camera và chưa có camera nào mang tên mẫu (kể cả đã xóa hoặc đã gỡ).

    Xóa mềm camera (F03) đặt `bed_id = null`; nếu chỉ tìm theo giường thì chạy lại seed sẽ
    tạo thêm một "Camera A01" (F03 §8).
    """
    has_bed_camera = db.scalar(select(Camera.id).where(Camera.bed_id == bed.id)) is not None
    has_named = db.scalar(select(Camera.id).where(Camera.name == name).limit(1)) is not None
    return not has_bed_camera and not has_named


def _seed_area(db: Session, created: dict[str, int]) -> Area:
    """Khu vực cho giường mẫu: khu vực đang dùng mang tên mẫu; không có (chưa có hoặc chỉ có
    khu vực đã xóa) thì tạo mới với mã còn trống. Không gán giường vào khu vực đã xóa (F37 R3)."""
    area = db.scalar(
        select(Area).where(Area.name == AREA, Area.is_active.is_(True)).order_by(Area.id).limit(1)
    )
    if area is None:
        used = set(db.scalars(select(Area.code)))
        code = AREA_CODE
        n = 1
        while code in used:  # KV01 đã dùng (khu vực khác hoặc đã xóa; DB cũ qua migration 0006)
            n += 1
            code = f"KV{n:02d}"
        area = Area(code=code, name=AREA)
        db.add(area)
        created["areas"] += 1
    return area


def seed_base(db: Session, password: str) -> dict[str, int]:
    """Tạo danh mục nền còn thiếu rồi commit. Trả số bản ghi mới theo bảng."""
    created = {"users": 0, "shift_definitions": 0, "areas": 0, "beds": 0, "cameras": 0}
    existing_users = set(db.scalars(select(User.username)))
    pw: str | None = None
    for username, full_name, role in SEED_USERS:
        if username in existing_users:
            continue
        pw = pw or hash_password(password)
        db.add(User(username=username, full_name=full_name, password_hash=pw, role=role))
        created["users"] += 1
    existing_shifts = set(db.scalars(select(ShiftDefinition.name)))
    active = [(s.start_time, s.end_time) for s in list_shifts(db)]
    for name, start, end in SEED_SHIFTS:
        if name in existing_shifts or any(shifts_overlap((start, end), a) for a in active):
            continue
        db.add(ShiftDefinition(name=name, start_time=start, end_time=end))
        active.append((start, end))
        created["shift_definitions"] += 1
    beds = {b.code: b for b in db.scalars(select(Bed).where(Bed.code.in_(BED_CODES)))}
    area: Area | None = None
    for code in BED_CODES:
        if code not in beds:
            area = area or _seed_area(db, created)
            beds[code] = Bed(code=code, area=area)
            db.add(beds[code])
            created["beds"] += 1
    db.flush()
    a01 = beds["A01"]
    if _needs_camera(db, a01, "Camera A01"):
        db.add(_webcam("Camera A01", a01))
        created["cameras"] += 1
    db.commit()
    return created


def seed_demo(db: Session) -> None:
    """Prototype: camera cho A02/A03, ROI mẫu, bệnh nhân BN-001…BN-005 (chỉ thêm, rồi commit)."""
    beds = {b.code: b for b in db.scalars(select(Bed).where(Bed.code.in_(BED_CODES)))}
    for code in BED_CODES[1:]:
        bed = beds[code]
        if _needs_camera(db, bed, f"Camera {code}"):
            db.add(_webcam(f"Camera {code}", bed))
    db.flush()
    for cam in db.scalars(select(Camera).where(Camera.roi_polygon.is_(None))):
        cam.roi_polygon = DEMO_ROI
    existing = set(db.scalars(select(Patient.code)))
    for i in range(1, 6):
        code = f"BN-{i:03d}"
        if code not in existing:
            db.add(Patient(code=code, note=None))
    db.commit()


class _History:
    def __init__(self, db: Session, now: datetime) -> None:
        self.db = db
        self.now = now
        self.users = {u.username: u for u in db.query(User).all()}
        self.beds = {b.code: b for b in db.query(Bed).all()}

    def at(self, minutes_ago: float) -> datetime:
        return self.now - timedelta(minutes=minutes_ago)

    def session(self, bed: str, patient: str, minutes_ago: float) -> MonitoringSession:
        b = self.beds[bed]
        p = self.db.query(Patient).filter_by(code=patient).one()
        s = MonitoringSession(
            bed_id=b.id,
            patient_id=p.id,
            camera_id=b.camera.id if b.camera else None,
            started_at=self.at(minutes_ago),
            started_by=self.users["nurse"].id,
        )
        self.db.add(s)
        self.db.flush()
        log = record_audit(
            self.db,
            actor_user_id=self.users["nurse"].id,
            action="session.start",
            entity_type="session",
            entity_id=s.id,
            after={"bed_id": b.id, "patient_id": p.id},
        )
        log.created_at = s.started_at
        return s

    def event(self, s: MonitoringSession, code: EventCode, minutes_ago: float) -> Alert | None:
        t = self.at(minutes_ago)
        b = self.beds[s.bed.code]
        priority = default_priority(code)
        e = Event(
            event_uid=str(uuid.uuid4()),
            session_id=s.id,
            bed_id=b.id,
            camera_id=b.camera.id if b.camera else 0,
            code=code,
            priority=priority,
            occurred_at=t,
            detected_at=t + timedelta(seconds=1),
            created_at=t + timedelta(seconds=1),
            confidence=0.9,
            observation_quality=ObservationQuality.GOOD,
            explanation={"rule_id": "seed.history", "source": "seed"},
            config_hash="seed",
        )
        self.db.add(e)
        self.db.flush()
        if priority not in ALERT_PRIORITIES:
            return None
        a = Alert(event_id=e.id, status=AlertStatus.PENDING, created_at=e.created_at)
        self.db.add(a)
        self.db.flush()
        self._audit(a, None, "alert.create", e.created_at, {"status": "PENDING"})
        return a

    def _audit(
        self, a: Alert, user: str | None, action: str, t: datetime, after: dict[str, object]
    ) -> None:
        log = record_audit(
            self.db,
            actor_user_id=self.users[user].id if user else None,
            action=action,
            entity_type="alert",
            entity_id=a.id,
            after=after,
        )
        log.created_at = t

    def ack(self, a: Alert, user: str, minutes_ago: float) -> None:
        t = self.at(minutes_ago)
        a.status, a.acknowledged_by, a.acknowledged_at = (
            AlertStatus.ACKNOWLEDGED,
            self.users[user].id,
            t,
        )
        self._audit(a, user, "alert.acknowledge", t, {"status": "ACKNOWLEDGED"})

    def outcome(
        self, a: Alert, user: str, outcome: AlertOutcome, note: str, minutes_ago: float
    ) -> None:
        t = self.at(minutes_ago)
        a.outcome, a.outcome_by, a.outcome_at, a.note = outcome, self.users[user].id, t, note
        self._audit(
            a,
            user,
            "alert.outcome",
            t,
            {"status": a.status.value, "outcome": outcome.value, "note": note},
        )

    def resolve(self, a: Alert, user: str, minutes_ago: float) -> None:
        t = self.at(minutes_ago)
        a.status, a.resolved_by, a.resolved_at = AlertStatus.RESOLVED, self.users[user].id, t
        self._audit(
            a,
            user,
            "alert.resolve",
            t,
            {
                "status": "RESOLVED",
                "outcome": a.outcome.value if a.outcome else None,
                "note": a.note,
            },
        )


def seed_history(db: Session, now: datetime) -> None:
    """Phiên mở cho A01–A03 và sự kiện quá khứ cho A02/A03."""
    h = _History(db, now)
    h.session("A01", "BN-001", 120)
    s2 = h.session("A02", "BN-002", 180)
    s3 = h.session("A03", "BN-003", 60)

    h.event(s2, EventCode.SIT_UP, 150)
    a = h.event(s2, EventCode.BED_EDGE, 149)
    assert a is not None
    h.ack(a, "nurse", 148)
    h.outcome(a, "nurse", AlertOutcome.PATIENT_SAFE, "Đã hỗ trợ bệnh nhân nằm lại", 146)
    h.resolve(a, "nurse", 145)
    h.event(s2, EventCode.POSTURE_CHANGE, 90)
    h.event(s2, EventCode.SIT_UP, 13)
    a = h.event(s2, EventCode.BED_EDGE, 12)
    assert a is not None
    h.ack(a, "charge", 11)

    h.event(s3, EventCode.POSTURE_CHANGE, 40)
    h.event(s3, EventCode.SIT_UP, 6)
    h.event(s3, EventCode.BED_EDGE, 5)
    h.event(s3, EventCode.STAND_UP, 4.7)
    h.event(s3, EventCode.BED_EXIT, 4.5)
    db.commit()
