"""F01: bảng nền users, patients, beds, cameras, monitoring_sessions, audit_logs, shift_definitions.

Theo docs/02-architecture/data-model.md (PDF §10.1; HS §6.2). Giá trị enum được chép cứng ở đây
(migration không đổi theo code); enum thêm giá trị sau này phải có migration riêng.

Revision ID: 0001
Revises:
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS: dict[str, tuple[str, ...]] = {
    "user_role": ("NURSE", "CHARGE_NURSE", "DOCTOR", "ADMIN"),  # QA#18
    "camera_source_type": ("WEBCAM", "URL", "FILE"),
    "display_mode": ("RAW", "BLUR", "SKELETON"),  # A08
    "camera_status": ("ONLINE", "OFFLINE", "UNKNOWN"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True)


def _pk(table: str) -> sa.PrimaryKeyConstraint:
    return sa.PrimaryKeyConstraint("id", name=f"pk_{table}")


def _uq(table: str, column: str) -> sa.UniqueConstraint:
    return sa.UniqueConstraint(column, name=f"uq_{table}_{column}")


def _is_active() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False)


def _created_at() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _fk(table: str, name: str, target: str, nullable: bool = False) -> sa.Column:  # type: ignore[type-arg]
    ref = target.split(".", 1)[0]
    fk = sa.ForeignKey(target, name=f"fk_{table}_{name}_{ref}")
    return sa.Column(name, sa.BigInteger(), fk, nullable=nullable)


def upgrade() -> None:
    bind = op.get_bind()
    for name in ENUMS:
        _enum(name).create(bind)

    op.create_table(
        "users",
        _id(),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", _enum("user_role"), nullable=False),
        _is_active(),
        _created_at(),
        _pk("users"),
        _uq("users", "username"),
    )
    op.create_table(
        "patients",
        _id(),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        _is_active(),
        _created_at(),
        _pk("patients"),
        _uq("patients", "code"),
    )
    op.create_table(
        "beds",
        _id(),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        _is_active(),
        _created_at(),
        _pk("beds"),
        _uq("beds", "code"),
    )
    op.create_table(
        "cameras",
        _id(),
        sa.Column("name", sa.Text(), nullable=False),
        _fk("cameras", "bed_id", "beds.id", nullable=True),
        sa.Column("source_type", _enum("camera_source_type"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("roi_polygon", postgresql.JSONB(), nullable=True),
        sa.Column(
            "thresholds", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("display_mode", _enum("display_mode"), server_default="BLUR", nullable=False),
        sa.Column("config_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", _enum("camera_status"), server_default="UNKNOWN", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        _is_active(),
        _pk("cameras"),
        _uq("cameras", "bed_id"),
    )
    op.create_table(
        "monitoring_sessions",
        _id(),
        _fk("monitoring_sessions", "patient_id", "patients.id"),
        _fk("monitoring_sessions", "bed_id", "beds.id"),
        _fk("monitoring_sessions", "camera_id", "cameras.id", nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        _fk("monitoring_sessions", "started_by", "users.id"),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        _fk("monitoring_sessions", "ended_by", "users.id", nullable=True),
        _pk("monitoring_sessions"),
    )
    # 1 phiên mở / giường và / bệnh nhân (data-model.md; logic ở F04).
    op.create_index(
        "uq_monitoring_sessions_open_bed",
        "monitoring_sessions",
        ["bed_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        "uq_monitoring_sessions_open_patient",
        "monitoring_sessions",
        ["patient_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_table(
        "audit_logs",
        _id(),
        _fk("audit_logs", "actor_user_id", "users.id", nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        _created_at(),
        _pk("audit_logs"),
    )
    op.create_table(
        "shift_definitions",
        _id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        _pk("shift_definitions"),
    )


def downgrade() -> None:
    op.drop_table("shift_definitions")
    op.drop_table("audit_logs")
    op.drop_index("uq_monitoring_sessions_open_patient", table_name="monitoring_sessions")
    op.drop_index("uq_monitoring_sessions_open_bed", table_name="monitoring_sessions")
    op.drop_table("monitoring_sessions")
    op.drop_table("cameras")
    op.drop_table("beds")
    op.drop_table("patients")
    op.drop_table("users")
    bind = op.get_bind()
    for name in reversed(list(ENUMS)):
        _enum(name).drop(bind)
