"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _user_fk(ondelete: str = "CASCADE") -> sa.ForeignKey:
    return sa.ForeignKey("users.id", ondelete=ondelete)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=False, primary_key=True),
        sa.Column("username", sa.String(64)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subscription_until", sa.DateTime(timezone=True)),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("sex", sa.String(1)),
        sa.Column("birth_year", sa.Integer()),
        sa.Column("height_cm", sa.Integer()),
        sa.Column("goal", sa.String(16)),
    )
    op.create_table(
        "meals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), _user_fk(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("scale", sa.Float(), nullable=False),
    )
    op.create_index("ix_meals_user_id_day", "meals", ["user_id", "day"])
    op.create_table(
        "meal_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "meal_id",
            sa.Integer(),
            sa.ForeignKey("meals.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("grams", sa.Float(), nullable=False),
        sa.Column("kcal", sa.Float(), nullable=False),
        sa.Column("protein", sa.Float(), nullable=False),
        sa.Column("fat", sa.Float(), nullable=False),
        sa.Column("carbs", sa.Float(), nullable=False),
    )
    op.create_table(
        "body_weights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), _user_fk(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.UniqueConstraint("user_id", "day"),
    )
    op.create_table(
        "daily_activity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), _user_fk(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.UniqueConstraint("user_id", "day"),
    )
    op.create_table(
        "exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), _user_fk(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.UniqueConstraint("user_id", "name"),
    )
    op.create_table(
        "workout_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), _user_fk(), nullable=False),
        sa.Column(
            "exercise_id",
            sa.Integer(),
            sa.ForeignKey("exercises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
    )
    op.create_index("ix_workout_sets_user_id_day", "workout_sets", ["user_id", "day"])
    op.create_index("ix_workout_sets_exercise_id_day", "workout_sets", ["exercise_id", "day"])
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), _user_fk("SET NULL")),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float()),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_llm_usage_user_id_day", "llm_usage", ["user_id", "day"])


def downgrade() -> None:
    for table in (
        "llm_usage",
        "workout_sets",
        "exercises",
        "daily_activity",
        "body_weights",
        "meal_items",
        "meals",
        "users",
    ):
        op.drop_table(table)
