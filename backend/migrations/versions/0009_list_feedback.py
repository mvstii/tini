"""list_feedback

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('list_feedback',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('list_id', sa.BigInteger(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('seed_id', sa.BigInteger(), nullable=True),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['list_id'], ['generated_list.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['seed_id'], ['artist.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_list_feedback_user_id'), 'list_feedback', ['user_id'], unique=False)
    op.create_index(op.f('ix_list_feedback_list_id'), 'list_feedback', ['list_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_list_feedback_list_id'), table_name='list_feedback')
    op.drop_index(op.f('ix_list_feedback_user_id'), table_name='list_feedback')
    op.drop_table('list_feedback')
