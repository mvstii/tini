"""artist_tag, artist_tag_fetch

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0020'
down_revision: Union[str, Sequence[str], None] = '0019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('artist_tag',
    sa.Column('artist_id', sa.BigInteger(), nullable=False),
    sa.Column('tag', sa.String(length=64), nullable=False),
    sa.Column('weight', sa.SmallInteger(), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.ForeignKeyConstraint(['artist_id'], ['artist.id'], ),
    sa.PrimaryKeyConstraint('artist_id', 'tag')
    )
    op.create_table('artist_tag_fetch',
    sa.Column('artist_id', sa.BigInteger(), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('found', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['artist_id'], ['artist.id'], ),
    sa.PrimaryKeyConstraint('artist_id')
    )


def downgrade() -> None:
    op.drop_table('artist_tag_fetch')
    op.drop_table('artist_tag')
