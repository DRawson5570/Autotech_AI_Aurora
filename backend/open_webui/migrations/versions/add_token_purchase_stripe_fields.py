"""add_token_purchase_stripe_fields

Revision ID: add_token_purchase_stripe_fields
Revises: add_token_purchase_tables
Create Date: 2026-01-03 00:10:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_token_purchase_stripe_fields"
down_revision = "add_token_purchase_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('token_purchase', sa.Column('status', sa.String(), nullable=False, server_default='pending'))
    op.add_column('token_purchase', sa.Column('stripe_session_id', sa.String(), nullable=True))


def downgrade():
    op.drop_column('token_purchase', 'stripe_session_id')
    op.drop_column('token_purchase', 'status')
