"""unheard_event

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0010'
down_revision: Union[str, Sequence[str], None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('unheard_event',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('track_id', sa.BigInteger(), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("state IN ('pooled','presented','awaiting','expired')", name='unheard_state'),
    sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['track_id'], ['track.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_unheard_event_user_id'), 'unheard_event', ['user_id'], unique=False)
    op.create_index(op.f('ix_unheard_event_track_id'), 'unheard_event', ['track_id'], unique=False)
    op.execute(
        """
        CREATE FUNCTION unheard_event_no_update() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'unheard_event append-only: UPDATE yasak';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER unheard_event_no_update BEFORE UPDATE ON unheard_event "
        "FOR EACH ROW EXECUTE FUNCTION unheard_event_no_update()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS unheard_event_no_update ON unheard_event")
    op.execute("DROP FUNCTION IF EXISTS unheard_event_no_update()")
    op.drop_index(op.f('ix_unheard_event_track_id'), table_name='unheard_event')
    op.drop_index(op.f('ix_unheard_event_user_id'), table_name='unheard_event')
    op.drop_table('unheard_event')
