"""merge add_billing_tables and mergepoint

Revision ID: 0c5df843210a
Revises: add_billing_tables, 228f37899486
Create Date: 2026-01-03 05:26:23.077838

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '0c5df843210a'
down_revision: Union[str, None] = ('add_billing_tables', '228f37899486')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
