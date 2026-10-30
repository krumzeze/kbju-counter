"""admin, promo codes, referrals, broadcasts

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _flag(name: str) -> sa.Column:
    return sa.Column(name, sa.Boolean(), server_default=sa.false(), nullable=False)


def _created_at(index: bool = False) -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        index=index,
    )


def _user_fk(name: str, ondelete: str, nullable: bool = True) -> sa.Column:
    return sa.Column(
        name, sa.BigInteger(), sa.ForeignKey("users.id", ondelete=ondelete), nullable=nullable
    )


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(128)))
    op.add_column("users", sa.Column("source", sa.String(64)))
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True)))
    for name in ("is_admin", "is_blocked", "bot_blocked", "lifetime_access"):
        op.add_column("users", _flag(name))
    op.add_column("users", sa.Column("daily_limit", sa.Integer()))
    op.add_column("users", sa.Column("admin_prefs", sa.JSON()))
    op.add_column("users", sa.Column("referral_code", sa.String(16), unique=True))
    op.add_column("users", _user_fk("referred_by_id", "SET NULL"))
    op.create_index("ix_users_referred_by_id", "users", ["referred_by_id"])

    op.add_column("llm_usage", _flag("no_food"))
    op.create_index("ix_llm_usage_created_at", "llm_usage", ["created_at"])

    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("max_activations", sa.Integer()),
        sa.Column("activations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        _flag("new_users_only"),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("note", sa.String(255)),
        _user_fk("created_by_id", "SET NULL"),
        _created_at(),
    )
    op.create_table(
        "promo_redemptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "promo_id",
            sa.Integer(),
            sa.ForeignKey("promo_codes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _user_fk("user_id", "CASCADE", nullable=False),
        _created_at(),
        sa.UniqueConstraint("promo_id", "user_id"),
    )
    op.create_index("ix_promo_redemptions_user_id", "promo_redemptions", ["user_id"])
    op.create_table(
        "promo_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_fk("user_id", "CASCADE", nullable=False),
        _created_at(),
    )
    op.create_index(
        "ix_promo_attempts_user_id_created_at", "promo_attempts", ["user_id", "created_at"]
    )
    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_fk("referrer_id", "CASCADE", nullable=False),
        _user_fk("referred_id", "SET NULL"),
        sa.Column("payment_ref", sa.String(128), nullable=False, unique=True),
        sa.Column("days", sa.Integer(), nullable=False),
        _created_at(),
    )
    op.create_index("ix_referral_rewards_referrer_id", "referral_rewards", ["referrer_id"])
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_fk("created_by_id", "SET NULL"),
        _created_at(),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("segment", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("cursor", sa.BigInteger(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("sent", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("blocked", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "admin_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_fk("admin_id", "SET NULL"),
        _created_at(index=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("target_user_id", sa.BigInteger(), index=True),
        sa.Column("details", sa.JSON()),
    )


def downgrade() -> None:
    op.drop_table("admin_actions")
    op.drop_table("broadcasts")
    op.drop_table("referral_rewards")
    op.drop_table("promo_attempts")
    op.drop_table("promo_redemptions")
    op.drop_table("promo_codes")
    op.drop_index("ix_llm_usage_created_at", "llm_usage")
    op.drop_column("llm_usage", "no_food")
    op.drop_index("ix_users_referred_by_id", "users")
    for name in (
        "referred_by_id",
        "referral_code",
        "admin_prefs",
        "daily_limit",
        "lifetime_access",
        "bot_blocked",
        "is_blocked",
        "is_admin",
        "last_seen_at",
        "source",
        "first_name",
    ):
        op.drop_column("users", name)
