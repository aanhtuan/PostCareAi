"""Bảng DB theo docs/02-architecture/data-model.md (PostgreSQL 16, ADR-0004).

Schema do Alembic tạo (`db/migrations/`), không dùng `create_all`. Sửa model thì phải thêm
migration mới; test `test_models_match_migrations` bắt lệch giữa model và migration.

- 7 bảng nền của F01: users, patients, beds, cameras, monitoring_sessions, audit_logs,
  shift_definitions (migration 0001).
- events, alerts và cột cameras.last_config_hash: phần prototype (ADR-0010) được giữ để API
  chạy được, tạo ở migration 0002; F17 tiếp nhận.
"""

from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from postcare.db.base import Base, pg_enum
from postcare.db.types import UTCDateTime, utcnow
from postcare.schemas.enums import (
    AlertOutcome,
    AlertStatus,
    CameraSourceType,
    CameraStatus,
    DisplayMode,
    ObservationQuality,
    Priority,
    UserRole,
)
from postcare.schemas.events import EventCode


def _id() -> Mapped[int]:
    return mapped_column(BigInteger, primary_key=True)


def _fk(target: str, *, nullable: bool = False, unique: bool = False) -> Mapped[Any]:
    return mapped_column(BigInteger, ForeignKey(target), nullable=nullable, unique=unique)


def _is_active() -> Mapped[bool]:
    return mapped_column(Boolean, default=True, server_default=text("true"))


def _created_at() -> Mapped[datetime]:
    return mapped_column(UTCDateTime, default=utcnow, server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = _id()
    username: Mapped[str] = mapped_column(Text, unique=True)
    full_name: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"))
    is_active: Mapped[bool] = _is_active()
    created_at: Mapped[datetime] = _created_at()


class Patient(Base):
    """Chỉ có mã thử nghiệm, không có họ tên hay ảnh (PDF §10.1; HS §6.3)."""

    __tablename__ = "patients"

    id: Mapped[int] = _id()
    code: Mapped[str] = mapped_column(Text, unique=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = _is_active()
    created_at: Mapped[datetime] = _created_at()


class Bed(Base):
    __tablename__ = "beds"

    id: Mapped[int] = _id()
    code: Mapped[str] = mapped_column(Text, unique=True)
    area: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = _is_active()
    created_at: Mapped[datetime] = _created_at()

    camera: Mapped["Camera | None"] = relationship(back_populates="bed", uselist=False)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = _id()
    name: Mapped[str] = mapped_column(Text)
    # MVP: 1 camera / giường (QA#13)
    bed_id: Mapped[int | None] = _fk("beds.id", nullable=True, unique=True)
    source_type: Mapped[CameraSourceType] = mapped_column(
        pg_enum(CameraSourceType, "camera_source_type")
    )
    source: Mapped[str] = mapped_column(Text)
    roi_polygon: Mapped[list[list[float]] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    thresholds: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    display_mode: Mapped[DisplayMode] = mapped_column(
        pg_enum(DisplayMode, "display_mode"),
        default=DisplayMode.BLUR,
        server_default=DisplayMode.BLUR.value,
    )
    config_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    status: Mapped[CameraStatus] = mapped_column(
        pg_enum(CameraStatus, "camera_status"),
        default=CameraStatus.UNKNOWN,
        server_default=CameraStatus.UNKNOWN.value,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Prototype (ADR-0010, migration 0002): hash cấu hình gần nhất worker gửi lên.
    last_config_hash: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    is_active: Mapped[bool] = _is_active()

    bed: Mapped[Bed | None] = relationship(back_populates="camera")


class MonitoringSession(Base):
    __tablename__ = "monitoring_sessions"
    __table_args__ = (
        # 1 phiên mở / giường và / bệnh nhân. Domain vẫn kiểm tra trước để trả 409 rõ ràng.
        Index(
            "uq_monitoring_sessions_open_bed",
            "bed_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index(
            "uq_monitoring_sessions_open_patient",
            "patient_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    id: Mapped[int] = _id()
    patient_id: Mapped[int] = _fk("patients.id")
    bed_id: Mapped[int] = _fk("beds.id")
    camera_id: Mapped[int | None] = _fk("cameras.id", nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    started_by: Mapped[int] = _fk("users.id")
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    ended_by: Mapped[int | None] = _fk("users.id", nullable=True)

    patient: Mapped[Patient] = relationship()
    bed: Mapped[Bed] = relationship()
    starter: Mapped[User] = relationship(foreign_keys=[started_by])
    ender: Mapped[User | None] = relationship(foreign_keys=[ended_by])


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_session_occurred", "session_id", "occurred_at"),
        Index("ix_events_bed_occurred", "bed_id", "occurred_at"),
    )

    id: Mapped[int] = _id()
    event_uid: Mapped[str] = mapped_column(UUID(as_uuid=False), unique=True)
    session_id: Mapped[int | None] = _fk("monitoring_sessions.id", nullable=True)
    bed_id: Mapped[int | None] = _fk("beds.id", nullable=True)
    camera_id: Mapped[int] = _fk("cameras.id")
    code: Mapped[EventCode] = mapped_column(pg_enum(EventCode, "event_code"))
    priority: Mapped[Priority] = mapped_column(pg_enum(Priority, "priority"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = _created_at()
    confidence: Mapped[float] = mapped_column(REAL)
    observation_quality: Mapped[ObservationQuality] = mapped_column(
        pg_enum(ObservationQuality, "observation_quality")
    )
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB)
    config_hash: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))

    bed: Mapped[Bed | None] = relationship()
    session: Mapped[MonitoringSession | None] = relationship()
    alert: Mapped["Alert | None"] = relationship(back_populates="event", uselist=False)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_status_created", "status", "created_at"),)

    id: Mapped[int] = _id()
    event_id: Mapped[int] = _fk("events.id", unique=True)
    status: Mapped[AlertStatus] = mapped_column(
        pg_enum(AlertStatus, "alert_status"),
        default=AlertStatus.PENDING,
        server_default=AlertStatus.PENDING.value,
    )
    outcome: Mapped[AlertOutcome | None] = mapped_column(
        pg_enum(AlertOutcome, "alert_outcome"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged_by: Mapped[int | None] = _fk("users.id", nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    outcome_by: Mapped[int | None] = _fk("users.id", nullable=True)
    outcome_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolved_by: Mapped[int | None] = _fk("users.id", nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = _created_at()

    event: Mapped[Event] = relationship(back_populates="alert")
    acknowledger: Mapped[User | None] = relationship(foreign_keys=[acknowledged_by])
    outcome_user: Mapped[User | None] = relationship(foreign_keys=[outcome_by])
    resolver: Mapped[User | None] = relationship(foreign_keys=[resolved_by])


class AuditLog(Base):
    """Chỉ thêm, không sửa (PDF §10.1). Ghi qua `postcare.domain.audit.record_audit`."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = _id()
    actor_user_id: Mapped[int | None] = _fk("users.id", nullable=True)  # null = hệ thống
    action: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[int] = mapped_column(BigInteger)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = _created_at()

    actor: Mapped[User | None] = relationship()


class ShiftDefinition(Base):
    __tablename__ = "shift_definitions"

    id: Mapped[int] = _id()
    name: Mapped[str] = mapped_column(Text)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
