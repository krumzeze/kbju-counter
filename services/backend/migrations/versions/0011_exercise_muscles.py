"""custom exercise muscles

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exercises", sa.Column("primary_muscles", sa.JSON()))
    op.add_column("exercises", sa.Column("secondary_muscles", sa.JSON()))


def downgrade() -> None:
    op.drop_column("exercises", "secondary_muscles")
    op.drop_column("exercises", "primary_muscles")
