"""workout sessions, exercise catalog links and templates

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _user_fk() -> sa.Column:
    return sa.Column(
        "user_id",
        sa.BigInteger(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )


def _created_at(name: str = "created_at") -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.add_column("exercises", sa.Column("catalog_id", sa.String(96)))
    op.add_column("exercises", sa.Column("group", sa.String(16)))
    op.add_column(
        "exercises",
        sa.Column("cardio", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.drop_constraint("exercises_user_id_name_key", "exercises", type_="unique")
    op.create_index(
        "uq_exercises_user_id_name",
        "exercises",
        ["user_id", "name"],
        unique=True,
        postgresql_where=sa.text("catalog_id IS NULL"),
    )
    op.create_index(
        "uq_exercises_user_id_catalog_id",
        "exercises",
        ["user_id", "catalog_id"],
        unique=True,
        postgresql_where=sa.text("catalog_id IS NOT NULL"),
    )

    op.create_table(
        "workouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_fk(),
        sa.Column("day", sa.Date(), nullable=False),
        _created_at("started_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("title", sa.String(64)),
        sa.Column("plan", sa.JSON(), nullable=False),
    )
    op.create_index("ix_workouts_user_id_day", "workouts", ["user_id", "day"])

    op.add_column("workout_sets", sa.Column("workout_id", sa.Integer()))
    op.add_column("workout_sets", sa.Column("duration_s", sa.Integer()))
    op.alter_column("workout_sets", "reps", nullable=True)
    op.execute(
        """
        INSERT INTO workouts (user_id, day, started_at, finished_at, plan)
        SELECT user_id, day, min(created_at), max(created_at), '[]'
        FROM workout_sets GROUP BY user_id, day
        """
    )
    op.execute(
        """
        UPDATE workout_sets s SET workout_id = w.id
        FROM workouts w WHERE w.user_id = s.user_id AND w.day = s.day
        """
    )
    op.alter_column("workout_sets", "workout_id", nullable=False)
    op.create_foreign_key(
        "workout_sets_workout_id_fkey",
        "workout_sets",
        "workouts",
        ["workout_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_workout_sets_workout_id", "workout_sets", ["workout_id"])

    op.create_table(
        "workout_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_fk(),
        sa.Column("name", sa.String(64), nullable=False),
        _created_at(),
        sa.Column("items", sa.JSON(), nullable=False),
    )
    op.create_index("ix_workout_templates_user_id", "workout_templates", ["user_id"])


def downgrade() -> None:
    op.drop_table("workout_templates")
    op.execute("DELETE FROM workout_sets WHERE reps IS NULL")
    op.alter_column("workout_sets", "reps", nullable=False)
    op.drop_index("ix_workout_sets_workout_id", "workout_sets")
    op.drop_constraint("workout_sets_workout_id_fkey", "workout_sets", type_="foreignkey")
    op.drop_column("workout_sets", "duration_s")
    op.drop_column("workout_sets", "workout_id")
    op.drop_table("workouts")
    op.execute("DELETE FROM exercises WHERE catalog_id IS NOT NULL")
    op.drop_index("uq_exercises_user_id_catalog_id", "exercises")
    op.drop_index("uq_exercises_user_id_name", "exercises")
    op.create_unique_constraint("exercises_user_id_name_key", "exercises", ["user_id", "name"])
    op.drop_column("exercises", "cardio")
    op.drop_column("exercises", "group")
    op.drop_column("exercises", "catalog_id")
