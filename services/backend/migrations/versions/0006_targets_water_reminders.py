"""target settings, reminders, water and barcode products

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_FLAGS = {
    "activity_adjust": sa.true(),
    "adaptive_target": sa.false(),
    "remind_meals": sa.true(),
    "remind_weight": sa.true(),
}


def upgrade() -> None:
    for name, default in USER_FLAGS.items():
        op.add_column(
            "users", sa.Column(name, sa.Boolean(), server_default=default, nullable=False)
        )
    op.alter_column("daily_activity", "steps", server_default="0")
    op.add_column(
        "daily_activity",
        sa.Column("water_ml", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(14), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kcal", sa.Float(), nullable=False),
        sa.Column("protein", sa.Float(), nullable=False),
        sa.Column("fat", sa.Float(), nullable=False),
        sa.Column("carbs", sa.Float(), nullable=False),
        sa.Column("serving_g", sa.Float()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "uq_products_code_shared",
        "products",
        ["code"],
        unique=True,
        postgresql_where=sa.text("user_id IS NULL"),
    )
    op.create_index(
        "uq_products_code_user_id",
        "products",
        ["code", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("products")
    op.drop_column("daily_activity", "water_ml")
    op.alter_column("daily_activity", "steps", server_default=None)
    for name in USER_FLAGS:
        op.drop_column("users", name)
