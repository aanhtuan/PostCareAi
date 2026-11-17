"""Prototype (ADR-0010): bảng events, alerts và cột cameras.last_config_hash.

Không thuộc phạm vi F01, nhưng API prototype (sự kiện, cảnh báo, timeline, bàn giao) cần để
chạy được sau khi bỏ `create_all`. Cấu trúc theo data-model.md mục events/alerts (F17).
F17 tiếp nhận hai bảng này: thay đổi bằng migration mới, không sửa file này sau khi merge.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS: dict[str, tuple[str, ...]] = {
    # event-engine.md mục 5 (catalog), giá trị tại thời điểm F01
    "event_code": (
        "POSTURE_CHANGE",
        "SIT_UP",
        "STAND_UP",
        "BED_EDGE",
        "BED_EXIT",
        "RETURN_TO_BED",
        "ACTIVITY_INCREASED",
        "ACTIVITY_LOW_PROLONGED",
        "ABNORMAL_MOVEMENT",
        "FACE_ATTENTION",
        "OBSERVATION_LOST",
        "OBSERVATION_RESTORED",
        "CAMERA_OFFLINE",
        "CAMERA_ONLINE",
    ),
    "priority": ("LOG", "INFO", "MEDIUM", "HIGH"),
    "observation_quality": (
        "GOOD",
        "LOW_CONFIDENCE",
        "MULTIPLE_PEOPLE",
        "NO_PERSON",
        "CAMERA_ISSUE",
    ),
    "alert_status": ("PENDING", "ACKNOWLEDGED", "RESOLVED"),  # ADR-0007
    "alert_outcome": ("CONFIRMED", "FALSE_ALARM", "PATIENT_SAFE"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _ts(name: str, nullable: bool = False) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _fk(table: str, name: str, target: str, nullable: bool = False) -> sa.Column:  # type: ignore[type-arg]
    ref = target.split(".", 1)[0]
    fk = sa.ForeignKey(target, name=f"fk_{table}_{name}_{ref}")
    return sa.Column(name, sa.BigInteger(), fk, nullable=nullable)


def upgrade() -> None:
    bind = op.get_bind()
    for name in ENUMS:
        _enum(name).create(bind)

    op.add_column(
        "cameras",
        sa.Column("last_config_hash", sa.Text(), server_default=sa.text("''"), nullable=False),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("event_uid", postgresql.UUID(as_uuid=False), nullable=False),
        _fk("events", "session_id", "monitoring_sessions.id", nullable=True),
        _fk("events", "bed_id", "beds.id", nullable=True),
        _fk("events", "camera_id", "cameras.id"),
        sa.Column("code", _enum("event_code"), nullable=False),
        sa.Column("priority", _enum("priority"), nullable=False),
        _ts("occurred_at"),
        _ts("detected_at"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("confidence", sa.REAL(), nullable=False),
        sa.Column("observation_quality", _enum("observation_quality"), nullable=False),
        sa.Column("explanation", postgresql.JSONB(), nullable=False),
        sa.Column("config_hash", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_events"),
        sa.UniqueConstraint("event_uid", name="uq_events_event_uid"),
    )
    op.create_index("ix_events_session_occurred", "events", ["session_id", "occurred_at"])
    op.create_index("ix_events_bed_occurred", "events", ["bed_id", "occurred_at"])
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        _fk("alerts", "event_id", "events.id"),
        sa.Column("status", _enum("alert_status"), server_default="PENDING", nullable=False),
        sa.Column("outcome", _enum("alert_outcome"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        _fk("alerts", "acknowledged_by", "users.id", nullable=True),
        _ts("acknowledged_at", nullable=True),
        _fk("alerts", "outcome_by", "users.id", nullable=True),
        _ts("outcome_at", nullable=True),
        _fk("alerts", "resolved_by", "users.id", nullable=True),
        _ts("resolved_at", nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_alerts"),
        sa.UniqueConstraint("event_id", name="uq_alerts_event_id"),
    )
    op.create_index("ix_alerts_status_created", "alerts", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_alerts_status_created", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_events_bed_occurred", table_name="events")
    op.drop_index("ix_events_session_occurred", table_name="events")
    op.drop_table("events")
    op.drop_column("cameras", "last_config_hash")
    bind = op.get_bind()
    for name in reversed(list(ENUMS)):
        _enum(name).drop(bind)
