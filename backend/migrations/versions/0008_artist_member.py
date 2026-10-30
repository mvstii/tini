"""artist_member

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('artist_member',
    sa.Column('collab_id', sa.BigInteger(), nullable=False),
    sa.Column('member_id', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['collab_id'], ['artist.id'], ),
    sa.ForeignKeyConstraint(['member_id'], ['artist.id'], ),
    sa.PrimaryKeyConstraint('collab_id', 'member_id')
    )
    op.create_index(op.f('ix_artist_member_member_id'), 'artist_member', ['member_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_artist_member_member_id'), table_name='artist_member')
    op.drop_table('artist_member')
