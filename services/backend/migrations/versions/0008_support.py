"""support messages

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("from_admin", sa.Boolean(), nullable=False),
        sa.Column("admin_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_index("ix_support_messages_user_id", "support_messages", ["user_id"])
    op.create_table(
        "support_relays",
        sa.Column("admin_chat_id", sa.BigInteger(), primary_key=True),
        sa.Column("admin_message_id", sa.Integer(), primary_key=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("support_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_support_relays_message_id", "support_relays", ["message_id"])


def downgrade() -> None:
    op.drop_table("support_relays")
    op.drop_table("support_messages")
