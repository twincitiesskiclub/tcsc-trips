"""add practice draft flag and leads_needed

Revision ID: 1b29976741b6
Revises: d4e7f9a1b2c3
Create Date: 2026-07-25 17:37:30.948124

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1b29976741b6'
down_revision = 'd4e7f9a1b2c3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('practices', sa.Column('is_draft', sa.Boolean(), nullable=True))
    op.add_column('practices', sa.Column('leads_needed', sa.Integer(), nullable=True))
    # Existing practices are all published and historically wanted 2 leads.
    op.execute("UPDATE practices SET is_draft = FALSE WHERE is_draft IS NULL")
    op.execute("UPDATE practices SET leads_needed = 2 WHERE leads_needed IS NULL")
    op.alter_column('practices', 'is_draft', nullable=False,
                    server_default=sa.text('false'))
    op.alter_column('practices', 'leads_needed', nullable=False,
                    server_default=sa.text('2'))


def downgrade():
    op.drop_column('practices', 'leads_needed')
    op.drop_column('practices', 'is_draft')
