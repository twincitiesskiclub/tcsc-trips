"""Add lead_nudge_sent_at to Practice model

Tracks when the 4pm/10pm lead verification nudge DM was sent
to prevent duplicate messages.

Revision ID: e1f2a3b4c5d6
Revises: affb7c8eff3d
Create Date: 2026-01-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'affb7c8eff3d'
branch_labels = None
depends_on = None


def upgrade():
    # Add lead_nudge_sent_at column to practices table
    op.add_column(
        'practices',
        sa.Column('lead_nudge_sent_at', sa.DateTime(), nullable=True)
    )


def downgrade():
    # Remove lead_nudge_sent_at column
    op.drop_column('practices', 'lead_nudge_sent_at')
