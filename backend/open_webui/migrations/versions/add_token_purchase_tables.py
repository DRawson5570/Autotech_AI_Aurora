"""add_token_purchase_tables

Revision ID: add_token_purchase_tables
Revises: add_billing_tables
Create Date: 2026-01-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_token_purchase_tables"
down_revision = "add_billing_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_token_balance",
        sa.Column("user_id", sa.String(), primary_key=True, nullable=False),
        sa.Column("tokens_balance", sa.BigInteger(), nullable=True, server_default="0"),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )

    op.create_table(
        "token_purchase",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=True, index=True),
        sa.Column("tokens", sa.BigInteger(), nullable=False),
        sa.Column("cost", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("stripe_payment_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )


def downgrade():
    op.drop_table("token_purchase")
    op.drop_table("user_token_balance")
