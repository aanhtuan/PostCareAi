"""Quyền xem của người nhà theo phiên: enum share_level, bảng family_access_grants (F36).

Partial unique `(session_id, user_id) WHERE revoked_at IS NULL` (data-model.md; F36 R1).

Revision ID: 0007_f36
Revises: 0006 (F37). F24/F31 làm song song: khi merge, nối lại `down_revision` nếu cần.
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_f36"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)
SHARE_LEVEL = postgresql.ENUM("INFO", "SKELETON", name="share_level", create_type=False)


def upgrade() -> None:
    SHARE_LEVEL.create(op.get_bind(), checkfirst=False)
    op.create_table(
        "family_access_grants",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "session_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "monitoring_sessions.id",
                name="fk_family_access_grants_session_id_monitoring_sessions",
            ),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", name="fk_family_access_grants_user_id_users"),
            nullable=False,
        ),
        sa.Column("share_level", SHARE_LEVEL, server_default="INFO", nullable=False),
        sa.Column("consent_note", sa.Text(), nullable=False),
        sa.Column(
            "granted_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", name="fk_family_access_grants_granted_by_users"),
            nullable=False,
        ),
        sa.Column("granted_at", _TS, nullable=False),
        sa.Column("expires_at", _TS, nullable=True),
        sa.Column("revoked_at", _TS, nullable=True),
        sa.Column(
            "revoked_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", name="fk_family_access_grants_revoked_by_users"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_family_access_grants"),
    )
    op.create_index(
        "uq_family_access_grants_active",
        "family_access_grants",
        ["session_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_family_access_grants_active", table_name="family_access_grants")
    op.drop_table("family_access_grants")
    SHARE_LEVEL.drop(op.get_bind(), checkfirst=False)
