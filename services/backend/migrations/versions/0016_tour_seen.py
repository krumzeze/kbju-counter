"""tutorial steps seen

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("tour_seen", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    # Existing users already know the basics, they only get the per-screen and new-feature hints.
    op.execute("""UPDATE users SET tour_seen = '["home"]' WHERE birth_year IS NOT NULL""")


def downgrade() -> None:
    op.drop_column("users", "tour_seen")
