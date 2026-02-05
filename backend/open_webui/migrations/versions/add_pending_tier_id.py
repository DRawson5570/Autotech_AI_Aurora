"""add_pending_tier_id

Revision ID: add_pending_tier_id
Revises: add_tiered_billing_tables
Create Date: 2026-01-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_pending_tier_id"
down_revision: Union[str, None] = "add_tiered_billing_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add pending_tier_id column to user_subscription
    # This stores the tier that will take effect at the next billing cycle
    try:
        op.add_column(
            "user_subscription",
            sa.Column("pending_tier_id", sa.String(), nullable=True)
        )
    except Exception:
        # Column may already exist
        pass
    
    # Add unique constraint on billing_invoice to prevent double billing
    # (user_id, period_start) should be unique
    try:
        op.create_index(
            "uq_billing_invoice_user_period",
            "billing_invoice",
            ["user_id", "period_start"],
            unique=True
        )
    except Exception:
        # Index may already exist
        pass


def downgrade() -> None:
    try:
        op.drop_index("uq_billing_invoice_user_period", table_name="billing_invoice")
    except Exception:
        pass
    try:
        op.drop_column("user_subscription", "pending_tier_id")
    except Exception:
        pass
