"""track_like

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0018'
down_revision: Union[str, Sequence[str], None] = '0017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('track_like',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('track_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['track_id'], ['track.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'track_id')
    )


def downgrade() -> None:
    op.drop_table('track_like')
