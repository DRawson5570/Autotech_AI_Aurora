"""add_tiered_billing_tables

Revision ID: add_tiered_billing_tables
Revises: add_billing_tables
Create Date: 2026-01-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from open_webui.migrations.util import get_existing_tables

# revision identifiers, used by Alembic.
revision: str = "add_tiered_billing_tables"
down_revision: Union[str, None] = "merge_add_token_purchase_and_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    # User subscription table for tiered billing
    if "user_subscription" not in existing_tables:
        op.create_table(
            "user_subscription",
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("tier_id", sa.String(), nullable=False, server_default="starter"),
            sa.Column("stripe_subscription_id", sa.String(), nullable=True),
            sa.Column("current_period_start", sa.BigInteger(), nullable=True),
            sa.Column("current_period_end", sa.BigInteger(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("user_id"),
        )

    # Daily usage table for analytics breakdown
    if "daily_usage" not in existing_tables:
        op.create_table(
            "daily_usage",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("date", sa.String(), nullable=False),  # YYYY-MM-DD format
            sa.Column("model_id", sa.String(), nullable=True),
            sa.Column("tokens_prompt", sa.BigInteger(), nullable=True, server_default="0"),
            sa.Column("tokens_completion", sa.BigInteger(), nullable=True, server_default="0"),
            sa.Column("tokens_total", sa.BigInteger(), nullable=True, server_default="0"),
            sa.Column("request_count", sa.BigInteger(), nullable=True, server_default="0"),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    # Add indexes
    try:
        op.create_index("ix_daily_usage_user_date", "daily_usage", ["user_id", "date"])
    except Exception:
        pass

    try:
        op.create_index("ix_daily_usage_user_id", "daily_usage", ["user_id"])
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_index("ix_daily_usage_user_id", table_name="daily_usage")
    except Exception:
        pass
    
    try:
        op.drop_index("ix_daily_usage_user_date", table_name="daily_usage")
    except Exception:
        pass

    try:
        op.drop_table("daily_usage")
    except Exception:
        pass
    
    try:
        op.drop_table("user_subscription")
    except Exception:
        pass
