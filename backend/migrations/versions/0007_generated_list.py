"""generated_list, list_item

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('generated_list',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('algo_version', sa.String(length=32), nullable=False),
    sa.Column('candidate_algo_version', sa.String(length=32), nullable=False),
    sa.Column('profile_version', sa.Integer(), nullable=False),
    sa.Column('graph_version', sa.Integer(), nullable=False),
    sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_generated_list_user_id'), 'generated_list', ['user_id'], unique=False)
    op.create_table('list_item',
    sa.Column('list_id', sa.BigInteger(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('artist_id', sa.BigInteger(), nullable=False),
    sa.Column('track_id', sa.BigInteger(), nullable=True),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('reasons', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['list_id'], ['generated_list.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['artist_id'], ['artist.id']),
    sa.ForeignKeyConstraint(['track_id'], ['track.id']),
    sa.PrimaryKeyConstraint('list_id', 'position')
    )


def downgrade() -> None:
    op.drop_table('list_item')
    op.drop_index(op.f('ix_generated_list_user_id'), table_name='generated_list')
    op.drop_table('generated_list')
