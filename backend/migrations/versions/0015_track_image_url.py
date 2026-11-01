"""user_track_meta.image_url

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0015'
down_revision: Union[str, Sequence[str], None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_track_meta', sa.Column('image_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('user_track_meta', 'image_url')
