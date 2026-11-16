"""Bảng DB theo docs/02-architecture/data-model.md (prototype: tạo bằng create_all, ADR-0010)."""

from datetime import datetime, time
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

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


def _enum(cls: type[StrEnum], name: str) -> Enum:
    # native_enum=False: VARCHAR + CHECK, chạy được trên cả SQLite và PostgreSQL.
    return Enum(
        cls,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    full_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Bed(Base):
    __tablename__ = "beds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    area: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    camera: Mapped["Camera | None"] = relationship(back_populates="bed", uselist=False)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    bed_id: Mapped[int | None] = mapped_column(ForeignKey("beds.id"), unique=True, nullable=True)
    source_type: Mapped[CameraSourceType] = mapped_column(
        _enum(CameraSourceType, "camera_source_type")
    )
    source: Mapped[str] = mapped_column(String(512))
    roi_polygon: Mapped[list[list[float]] | None] = mapped_column(JSON, nullable=True)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    display_mode: Mapped[DisplayMode] = mapped_column(
        _enum(DisplayMode, "display_mode"), default=DisplayMode.BLUR
    )
    config_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[CameraStatus] = mapped_column(
        _enum(CameraStatus, "camera_status"), default=CameraStatus.UNKNOWN
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_config_hash: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    bed: Mapped[Bed | None] = relationship(back_populates="camera")


class MonitoringSession(Base):
    __tablename__ = "monitoring_sessions"
    __table_args__ = (
        # 1 phiên mở / giường và / bệnh nhân. Partial index có ở cả SQLite và PostgreSQL;
        # domain vẫn kiểm tra trước để trả 409 rõ ràng.
        Index(
            "uq_session_open_bed",
            "bed_id",
            unique=True,
            sqlite_where=text("ended_at IS NULL"),
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index(
            "uq_session_open_patient",
            "patient_id",
            unique=True,
            sqlite_where=text("ended_at IS NULL"),
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    bed_id: Mapped[int] = mapped_column(ForeignKey("beds.id"))
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    started_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    ended_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_uid: Mapped[str] = mapped_column(String(36), unique=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("monitoring_sessions.id"), nullable=True
    )
    bed_id: Mapped[int | None] = mapped_column(ForeignKey("beds.id"), nullable=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"))
    code: Mapped[EventCode] = mapped_column(_enum(EventCode, "event_code"))
    priority: Mapped[Priority] = mapped_column(_enum(Priority, "priority"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    confidence: Mapped[float] = mapped_column(Float)
    observation_quality: Mapped[ObservationQuality] = mapped_column(
        _enum(ObservationQuality, "observation_quality")
    )
    explanation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    config_hash: Mapped[str] = mapped_column(String(128), default="")

    bed: Mapped[Bed | None] = relationship()
    session: Mapped[MonitoringSession | None] = relationship()
    alert: Mapped["Alert | None"] = relationship(back_populates="event", uselist=False)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), unique=True)
    status: Mapped[AlertStatus] = mapped_column(
        _enum(AlertStatus, "alert_status"), default=AlertStatus.PENDING
    )
    outcome: Mapped[AlertOutcome | None] = mapped_column(
        _enum(AlertOutcome, "alert_outcome"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    outcome_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    outcome_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    event: Mapped[Event] = relationship(back_populates="alert")
    acknowledger: Mapped[User | None] = relationship(foreign_keys=[acknowledged_by])
    outcome_user: Mapped[User | None] = relationship(foreign_keys=[outcome_by])
    resolver: Mapped[User | None] = relationship(foreign_keys=[resolved_by])


class AuditLog(Base):
    """Chỉ thêm, không sửa (PDF §10.1)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int] = mapped_column(Integer)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    actor: Mapped[User | None] = relationship()


class ShiftDefinition(Base):
    __tablename__ = "shift_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
