"""list_item.slot

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0011'
down_revision: Union[str, Sequence[str], None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('list_item', sa.Column('slot', sa.String(length=16), server_default='explore', nullable=False))
    op.create_check_constraint('list_item_slot', 'list_item', "slot IN ('familiar','unheard','explore')")


def downgrade() -> None:
    op.drop_constraint('list_item_slot', 'list_item', type_='check')
    op.drop_column('list_item', 'slot')
