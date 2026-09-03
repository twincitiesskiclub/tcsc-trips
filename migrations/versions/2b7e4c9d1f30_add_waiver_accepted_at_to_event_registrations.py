"""add waiver_accepted_at to event_registrations

Revision ID: 2b7e4c9d1f30
Revises: 1137d059b6f4
Create Date: 2026-09-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2b7e4c9d1f30'
down_revision = '1137d059b6f4'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable on purpose: registrations taken before the waiver shipped
    # have no acceptance to record.
    op.add_column(
        'event_registrations',
        sa.Column('waiver_accepted_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column('event_registrations', 'waiver_accepted_at')
