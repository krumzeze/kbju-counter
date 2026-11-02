"""app errors

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_errors",
        sa.Column("fingerprint", sa.String(40), primary_key=True),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("path", sa.String(256)),
        sa.Column("user_id", sa.BigInteger()),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alerted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_app_errors_last_seen", "app_errors", ["last_seen"])


def downgrade() -> None:
    op.drop_table("app_errors")
