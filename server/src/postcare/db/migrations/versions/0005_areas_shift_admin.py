"""Bảng areas thay chuỗi beds.area; shift_definitions thêm is_active, created_at (F37).

Chuyển dữ liệu (F37 R2, giả định): mỗi giá trị `btrim(beds.area)` khác nhau thành một khu vực
`name = giá trị đó`, `code = KV01, KV02…` (từ 100 trở đi: KV100…) theo thứ tự chữ cái của
`name`; gán `beds.area_id` rồi bỏ cột `beds.area`. `downgrade` khôi phục `beds.area` từ
`areas.name`.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "areas",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_areas"),
        sa.UniqueConstraint("code", name="uq_areas_code"),
    )
    op.execute(
        """
        INSERT INTO areas (code, name)
        SELECT 'KV' || lpad(n::text, GREATEST(2, length(n::text)), '0'), name
        FROM (
            SELECT name, row_number() OVER (ORDER BY name) AS n
            FROM (SELECT DISTINCT btrim(area) AS name FROM beds) AS distinct_areas
        ) AS numbered
        ORDER BY n
        """
    )
    op.add_column("beds", sa.Column("area_id", sa.BigInteger(), nullable=True))
    op.execute("UPDATE beds SET area_id = areas.id FROM areas WHERE areas.name = btrim(beds.area)")
    op.alter_column("beds", "area_id", nullable=False)
    op.create_foreign_key("fk_beds_area_id_areas", "beds", "areas", ["area_id"], ["id"])
    op.drop_column("beds", "area")

    op.add_column(
        "shift_definitions",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "shift_definitions",
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("shift_definitions", "created_at")
    op.drop_column("shift_definitions", "is_active")

    op.add_column("beds", sa.Column("area", sa.Text(), nullable=True))
    op.execute("UPDATE beds SET area = areas.name FROM areas WHERE areas.id = beds.area_id")
    op.alter_column("beds", "area", nullable=False)
    op.drop_constraint("fk_beds_area_id_areas", "beds", type_="foreignkey")
    op.drop_column("beds", "area_id")
    op.drop_table("areas")
