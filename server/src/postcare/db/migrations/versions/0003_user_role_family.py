"""Thêm vai trò FAMILY vào enum user_role (F35; QA#31).

PostgreSQL ≥ 12 cho phép `ALTER TYPE ... ADD VALUE` trong transaction, miễn là giá trị mới
không được dùng trong cùng transaction đó.

Downgrade tạo lại enum không có FAMILY; dừng nếu còn tài khoản FAMILY (không tự xóa dữ liệu).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'FAMILY'")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM users WHERE role = 'FAMILY') THEN
                RAISE EXCEPTION 'Còn tài khoản FAMILY: đổi vai trò hoặc xóa trước khi downgrade';
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TYPE user_role RENAME TO user_role_old")
    op.execute("CREATE TYPE user_role AS ENUM ('NURSE', 'CHARGE_NURSE', 'DOCTOR', 'ADMIN')")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::text::user_role")
    op.execute("DROP TYPE user_role_old")
