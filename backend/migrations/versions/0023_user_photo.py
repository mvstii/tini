"""user_photo (profile photo, personal data, cascades with the account)

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0023'
down_revision: Union[str, Sequence[str], None] = '0022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_photo',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('mime', sa.String(length=32), nullable=False),
        sa.Column('etag', sa.String(length=40), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
    )


def downgrade() -> None:
    op.drop_table('user_photo')
