"""list_item.slot: 'far' (list-4)

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-06
"""
from typing import Sequence, Union

from alembic import op

revision: str = '0019'
down_revision: Union[str, Sequence[str], None] = '0018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('list_item_slot', 'list_item', type_='check')
    op.create_check_constraint('list_item_slot', 'list_item', "slot IN ('familiar','unheard','explore','far','fresh')")


def downgrade() -> None:
    op.execute("UPDATE list_item SET slot = 'explore' WHERE slot = 'far'")
    op.drop_constraint('list_item_slot', 'list_item', type_='check')
    op.create_check_constraint('list_item_slot', 'list_item', "slot IN ('familiar','unheard','explore','fresh')")
