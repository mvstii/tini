"""artist_edge, graph_snapshot

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('artist_edge',
    sa.Column('src', sa.BigInteger(), nullable=False),
    sa.Column('dst', sa.BigInteger(), nullable=False),
    sa.Column('source', sa.String(length=32), nullable=False),
    sa.Column('weight', sa.Float(), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['dst'], ['artist.id']),
    sa.ForeignKeyConstraint(['src'], ['artist.id']),
    sa.PrimaryKeyConstraint('src', 'dst', 'source')
    )
    op.create_index(op.f('ix_artist_edge_fetched_at'), 'artist_edge', ['fetched_at'], unique=False)
    op.create_index(op.f('ix_artist_edge_expires_at'), 'artist_edge', ['expires_at'], unique=False)
    op.create_table('graph_snapshot',
    sa.Column('version', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('edge_count', sa.Integer(), nullable=False),
    sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint('version')
    )


def downgrade() -> None:
    op.drop_table('graph_snapshot')
    op.drop_index(op.f('ix_artist_edge_expires_at'), table_name='artist_edge')
    op.drop_index(op.f('ix_artist_edge_fetched_at'), table_name='artist_edge')
    op.drop_table('artist_edge')
