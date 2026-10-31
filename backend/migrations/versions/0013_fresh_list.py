"""generated_list.kind, list_item.release_id, slot 'fresh'

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0013'
down_revision: Union[str, Sequence[str], None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('generated_list', sa.Column('kind', sa.String(length=16), server_default='main', nullable=False))
    op.create_check_constraint('generated_list_kind', 'generated_list', "kind IN ('main','fresh')")
    op.add_column('list_item', sa.Column('release_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key('list_item_release_id_fkey', 'list_item', 'release', ['release_id'], ['id'])
    op.create_index(op.f('ix_list_item_release_id'), 'list_item', ['release_id'], unique=False)
    op.drop_constraint('list_item_slot', 'list_item', type_='check')
    op.create_check_constraint('list_item_slot', 'list_item', "slot IN ('familiar','unheard','explore','fresh')")


def downgrade() -> None:
    op.execute("DELETE FROM generated_list WHERE kind = 'fresh'")
    op.drop_constraint('list_item_slot', 'list_item', type_='check')
    op.create_check_constraint('list_item_slot', 'list_item', "slot IN ('familiar','unheard','explore')")
    op.drop_index(op.f('ix_list_item_release_id'), table_name='list_item')
    op.drop_constraint('list_item_release_id_fkey', 'list_item', type_='foreignkey')
    op.drop_column('list_item', 'release_id')
    op.drop_constraint('generated_list_kind', 'generated_list', type_='check')
    op.drop_column('generated_list', 'kind')
