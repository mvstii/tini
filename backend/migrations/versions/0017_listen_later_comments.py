"""listen_later ve track_comment

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0017'
down_revision: Union[str, Sequence[str], None] = '0016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('listen_later',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('track_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['track_id'], ['track.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'track_id')
    )
    op.create_table('track_comment',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('track_id', sa.BigInteger(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['track_id'], ['track.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_track_comment_user_id'), 'track_comment', ['user_id'], unique=False)
    op.create_index(op.f('ix_track_comment_track_id'), 'track_comment', ['track_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_track_comment_track_id'), table_name='track_comment')
    op.drop_index(op.f('ix_track_comment_user_id'), table_name='track_comment')
    op.drop_table('track_comment')
    op.drop_table('listen_later')
