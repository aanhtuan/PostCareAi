"""Cột chuyển giường và tạm dừng thu hình của monitoring_sessions (F04).

`previous_session_id` (unique: chuỗi chuyển giường tuyến tính), `transfer_reason`,
`paused_at`, `paused_by` (data-model.md).

Revision ID: 0005_f04
Revises: 0004
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_f04"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "monitoring_sessions"
FK_PREVIOUS = "fk_monitoring_sessions_previous_session_id_monitoring_sessions"
FK_PAUSED_BY = "fk_monitoring_sessions_paused_by_users"
UQ_PREVIOUS = "uq_monitoring_sessions_previous_session_id"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("previous_session_id", sa.BigInteger(), nullable=True))
    op.add_column(TABLE, sa.Column("transfer_reason", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABLE, sa.Column("paused_by", sa.BigInteger(), nullable=True))
    op.create_foreign_key(FK_PREVIOUS, TABLE, TABLE, ["previous_session_id"], ["id"])
    op.create_foreign_key(FK_PAUSED_BY, TABLE, "users", ["paused_by"], ["id"])
    op.create_unique_constraint(UQ_PREVIOUS, TABLE, ["previous_session_id"])


def downgrade() -> None:
    op.drop_constraint(UQ_PREVIOUS, TABLE, type_="unique")
    op.drop_constraint(FK_PAUSED_BY, TABLE, type_="foreignkey")
    op.drop_constraint(FK_PREVIOUS, TABLE, type_="foreignkey")
    op.drop_column(TABLE, "paused_by")
    op.drop_column(TABLE, "paused_at")
    op.drop_column(TABLE, "transfer_reason")
    op.drop_column(TABLE, "previous_session_id")
