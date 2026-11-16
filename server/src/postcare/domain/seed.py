"""Dữ liệu mẫu cho dev/demo: tài khoản, ca trực, giường A01–A03, camera, bệnh nhân mã thử nghiệm.

`seed_history` thêm vài sự kiện quá khứ cho A02/A03 để dashboard giống HS Hình 3
(A01 Đang theo dõi, A02 Cần kiểm tra, A03 Cảnh báo mới).
"""

import uuid
from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from postcare.db.models import (
    Alert,
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
from postcare.schemas.enums import (
    AlertOutcome,
    AlertStatus,
    CameraSourceType,
    ObservationQuality,
    UserRole,
)
from postcare.schemas.events import ALERT_PRIORITIES, EventCode, default_priority

AREA = "Khu hậu phẫu"

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


def seed_base(db: Session, password: str) -> None:
    """Tạo danh mục cơ bản. Gọi trên DB trống."""
    pw = hash_password(password)
    for username, full_name, role in SEED_USERS:
        db.add(User(username=username, full_name=full_name, password_hash=pw, role=role))
    for name, start, end in SEED_SHIFTS:
        db.add(ShiftDefinition(name=name, start_time=start, end_time=end))
    for code in ("A01", "A02", "A03"):
        bed = Bed(code=code, area=AREA)
        db.add(bed)
        db.flush()
        db.add(
            Camera(
                name=f"Camera {code}" + (" (giả lập)" if code == "A01" else ""),
                bed_id=bed.id,
                source_type=CameraSourceType.WEBCAM,
                source="0",
                roi_polygon=[[0.2, 0.25], [0.8, 0.25], [0.8, 0.85], [0.2, 0.85]],
                thresholds={},
            )
        )
    for i in range(1, 6):
        db.add(Patient(code=f"BN-{i:03d}", note=None))
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
