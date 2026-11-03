"""artist_image

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0016'
down_revision: Union[str, Sequence[str], None] = '0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'artist_image',
        sa.Column('artist_id', sa.BigInteger(), sa.ForeignKey('artist.id'), primary_key=True),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('source', sa.String(32), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_artist_image_expires_at', 'artist_image', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_artist_image_expires_at', table_name='artist_image')
    op.drop_table('artist_image')
