"""add_billing_tables

Revision ID: add_billing_tables
Revises: 7e5b5dc7342b
Create Date: 2026-01-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from open_webui.migrations.util import get_existing_tables

# revision identifiers, used by Alembic.
revision: str = "add_billing_tables"
down_revision: Union[str, None] = "7e5b5dc7342b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    if "usage_event" not in existing_tables:
        op.create_table(
            "usage_event",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("chat_id", sa.String(), nullable=True),
            sa.Column("message_id", sa.String(), nullable=True),
            sa.Column("tokens_prompt", sa.BigInteger(), nullable=True),
            sa.Column("tokens_completion", sa.BigInteger(), nullable=True),
            sa.Column("tokens_total", sa.BigInteger(), nullable=True),
            sa.Column("token_source", sa.String(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if "user_token_usage" not in existing_tables:
        op.create_table(
            "user_token_usage",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("period_start", sa.BigInteger(), nullable=True),
            sa.Column("period_end", sa.BigInteger(), nullable=True),
            sa.Column("tokens_prompt", sa.BigInteger(), nullable=True),
            sa.Column("tokens_completion", sa.BigInteger(), nullable=True),
            sa.Column("tokens_total", sa.BigInteger(), nullable=True),
            sa.Column("cost_total", sa.String(), nullable=True),
            sa.Column("currency", sa.String(), nullable=True),
            sa.Column("billed", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=True),
            sa.Column("updated_at", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    # add indexes for lookups
    try:
        op.create_index("ix_usage_event_user_id", "usage_event", ["user_id"])
    except Exception:
        pass

    try:
        op.create_index("ix_user_token_usage_user_id", "user_token_usage", ["user_id", "period_start"])
    except Exception:
        pass


def downgrade() -> None:
    op.drop_index("ix_user_token_usage_user_id", table_name="user_token_usage")
    op.drop_index("ix_usage_event_user_id", table_name="usage_event")

    op.drop_table("user_token_usage")
    op.drop_table("usage_event")
