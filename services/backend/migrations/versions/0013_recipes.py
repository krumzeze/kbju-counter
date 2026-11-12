"""recipes

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "owner_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("forked_from_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("portions", sa.Integer(), nullable=False),
        sa.Column("cooked_grams", sa.Float()),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("photo_key", sa.String(64)),
        sa.Column("author_name", sa.String(64)),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("reject_reason", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_recipes_owner_id", "recipes", ["owner_id"])
    op.create_index("ix_recipes_forked_from_id", "recipes", ["forked_from_id"])
    op.create_index("ix_recipes_status", "recipes", ["status"])
    op.create_table(
        "recipe_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recipe_id",
            sa.Integer(),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("grams", sa.Float(), nullable=False),
        sa.Column("kcal", sa.Float(), nullable=False),
        sa.Column("protein", sa.Float(), nullable=False),
        sa.Column("fat", sa.Float(), nullable=False),
        sa.Column("carbs", sa.Float(), nullable=False),
    )
    op.create_index("ix_recipe_items_recipe_id", "recipe_items", ["recipe_id"])
    for name in ("recipe_favorites", "recipe_ratings"):
        columns = [
            sa.Column(
                "user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "recipe_id",
                sa.Integer(),
                sa.ForeignKey("recipes.id", ondelete="CASCADE"),
                primary_key=True,
            ),
        ]
        if name == "recipe_favorites":
            columns.append(
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                )
            )
        else:
            columns.append(sa.Column("stars", sa.Integer(), nullable=False))
        op.create_table(name, *columns)
        op.create_index(f"ix_{name}_recipe_id", name, ["recipe_id"])
    op.add_column(
        "meals",
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="SET NULL")),
    )
    op.create_index("ix_meals_recipe_id", "meals", ["recipe_id"])


def downgrade() -> None:
    op.drop_index("ix_meals_recipe_id", "meals")
    op.drop_column("meals", "recipe_id")
    op.drop_table("recipe_ratings")
    op.drop_table("recipe_favorites")
    op.drop_table("recipe_items")
    op.drop_table("recipes")
