"""meal photos

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("meals", sa.Column("photo_key", sa.String(64)))
    op.add_column(
        "users",
        sa.Column(
            "photo_eval_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.create_table(
        "photo_evals",
        sa.Column(
            "meal_id",
            sa.Integer(),
            sa.ForeignKey("meals.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("photo_key", sa.String(64), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_photo_evals_user_id", "photo_evals", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_photo_evals_user_id", table_name="photo_evals")
    op.drop_table("photo_evals")
    op.drop_column("users", "photo_eval_consent")
    op.drop_column("meals", "photo_key")
