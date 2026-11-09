"""genre_seed, track_popularity (genre backbone; additive, no personal data)

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0021'
down_revision: Union[str, Sequence[str], None] = '0020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('track_popularity',
    sa.Column('track_id', sa.BigInteger(), nullable=False),
    sa.Column('band', sa.String(length=8), nullable=False),
    sa.Column('listens', sa.Integer(), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['track_id'], ['track.id'], ),
    sa.PrimaryKeyConstraint('track_id')
    )
    op.create_table('genre_seed',
    sa.Column('sub_genre', sa.String(length=48), nullable=False),
    sa.Column('track_id', sa.BigInteger(), nullable=False),
    sa.Column('main_genre', sa.String(length=32), nullable=False),
    sa.Column('artist_id', sa.BigInteger(), nullable=False),
    sa.Column('band', sa.String(length=8), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['artist_id'], ['artist.id'], ),
    sa.ForeignKeyConstraint(['track_id'], ['track.id'], ),
    sa.PrimaryKeyConstraint('sub_genre', 'track_id')
    )
    op.create_index('ix_genre_seed_sub_genre_band', 'genre_seed', ['sub_genre', 'band'])
    op.create_index('ix_genre_seed_artist_id', 'genre_seed', ['artist_id'])


def downgrade() -> None:
    op.drop_index('ix_genre_seed_artist_id', table_name='genre_seed')
    op.drop_index('ix_genre_seed_sub_genre_band', table_name='genre_seed')
    op.drop_table('genre_seed')
    op.drop_table('track_popularity')
