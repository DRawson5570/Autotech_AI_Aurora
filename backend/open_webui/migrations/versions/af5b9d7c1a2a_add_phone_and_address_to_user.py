"""Add phone and address to user

Revision ID: af5b9d7c1a2a
Revises: b10670c03dd5
Create Date: 2026-01-02 16:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


import json

# revision identifiers, used by Alembic.
revision: str = "af5b9d7c1a2a"
down_revision: Union[str, None] = "b10670c03dd5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("phone", sa.String(), nullable=True))
    op.add_column("user", sa.Column("address", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("address")
        batch_op.drop_column("phone")
