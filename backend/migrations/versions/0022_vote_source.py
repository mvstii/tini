"""vote_event.source, unheard_event.source (queue card source; nullable, additive)

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0022'
down_revision: Union[str, Sequence[str], None] = '0021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vote_event', sa.Column('source', sa.String(length=16), nullable=True))
    op.add_column('unheard_event', sa.Column('source', sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column('unheard_event', 'source')
    op.drop_column('vote_event', 'source')
