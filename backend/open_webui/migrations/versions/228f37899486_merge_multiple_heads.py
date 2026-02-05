"""merge multiple heads

Revision ID: 228f37899486
Revises: af5b9d7c1a2a, c440947495f3
Create Date: 2026-01-02 18:22:36.682304

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '228f37899486'
down_revision: Union[str, None] = ('af5b9d7c1a2a', 'c440947495f3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
