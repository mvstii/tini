"""release, release_artist, followed_artist

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0012'
down_revision: Union[str, Sequence[str], None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('release',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('mb_rgid', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('primary_type', sa.String(length=16), nullable=False),
    sa.Column('first_release_date', sa.Date(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('mb_rgid')
    )
    op.create_index(op.f('ix_release_first_release_date'), 'release', ['first_release_date'], unique=False)
    op.create_table('release_artist',
    sa.Column('release_id', sa.BigInteger(), nullable=False),
    sa.Column('artist_id', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['release_id'], ['release.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['artist_id'], ['artist.id'], ),
    sa.PrimaryKeyConstraint('release_id', 'artist_id')
    )
    op.create_index(op.f('ix_release_artist_artist_id'), 'release_artist', ['artist_id'], unique=False)
    op.create_table('followed_artist',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('artist_id', sa.BigInteger(), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('manual','muted')", name='followed_source'),
    sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['artist_id'], ['artist.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'artist_id')
    )


def downgrade() -> None:
    op.drop_table('followed_artist')
    op.drop_index(op.f('ix_release_artist_artist_id'), table_name='release_artist')
    op.drop_table('release_artist')
    op.drop_index(op.f('ix_release_first_release_date'), table_name='release')
    op.drop_table('release')
