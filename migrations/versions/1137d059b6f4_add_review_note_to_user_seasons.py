"""add review_note to user_seasons

Revision ID: 1137d059b6f4
Revises: 6fe27563d4aa
Create Date: 2026-08-24 17:26:25.626851

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1137d059b6f4'
down_revision = '6fe27563d4aa'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user_seasons',
                  sa.Column('review_note', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('user_seasons', 'review_note')
