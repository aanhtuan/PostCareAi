"""F38: hồ sơ quan sát theo camera."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    profile = sa.Enum(
        "BED_MONITORING",
        "ABNORMAL_MOVEMENT",
        "FACE_SIGNALS",
        name="observation_profile",
    )
    profile.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "cameras",
        sa.Column(
            "observation_profile",
            profile,
            server_default="BED_MONITORING",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("cameras", "observation_profile")
    sa.Enum(name="observation_profile").drop(op.get_bind(), checkfirst=True)
