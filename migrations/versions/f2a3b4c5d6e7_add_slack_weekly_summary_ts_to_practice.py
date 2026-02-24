"""add slack_weekly_summary_ts to practice

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-02-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'practices',
        sa.Column('slack_weekly_summary_ts', sa.String(length=50), nullable=True)
    )


def downgrade():
    op.drop_column('practices', 'slack_weekly_summary_ts')
