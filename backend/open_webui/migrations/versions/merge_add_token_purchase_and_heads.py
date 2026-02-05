"""merge add_token_purchase_stripe_fields and heads

Revision ID: merge_add_token_purchase_and_heads
Revises: 0c5df843210a, add_token_purchase_stripe_fields
Create Date: 2026-01-03 00:20:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "merge_add_token_purchase_and_heads"
down_revision = ("0c5df843210a", "add_token_purchase_stripe_fields")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
