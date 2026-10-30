"""artist resolution: artist.name, artist_ref, user_track_artist, fetch_log

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('artist', sa.Column('name', sa.Text(), nullable=True))
    op.create_table('artist_ref',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('artist_id', sa.BigInteger(), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('provider_id', sa.String(length=128), nullable=False),
    sa.Column('match_method', sa.String(length=32), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['artist_id'], ['artist.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'provider_id')
    )
    op.create_index(op.f('ix_artist_ref_artist_id'), 'artist_ref', ['artist_id'], unique=False)
    op.create_table('user_track_artist',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('track_id', sa.BigInteger(), nullable=False),
    sa.Column('artist_id', sa.BigInteger(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('method', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['artist_id'], ['artist.id']),
    sa.ForeignKeyConstraint(['track_id'], ['track.id']),
    sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'track_id')
    )
    op.create_index(op.f('ix_user_track_artist_artist_id'), 'user_track_artist', ['artist_id'], unique=False)
    op.create_table('fetch_log',
    sa.Column('source', sa.String(length=32), nullable=False),
    sa.Column('key', sa.String(length=128), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('source', 'key')
    )
    op.create_index(op.f('ix_fetch_log_expires_at'), 'fetch_log', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fetch_log_expires_at'), table_name='fetch_log')
    op.drop_table('fetch_log')
    op.drop_index(op.f('ix_user_track_artist_artist_id'), table_name='user_track_artist')
    op.drop_table('user_track_artist')
    op.drop_index(op.f('ix_artist_ref_artist_id'), table_name='artist_ref')
    op.drop_table('artist_ref')
    op.drop_column('artist', 'name')
