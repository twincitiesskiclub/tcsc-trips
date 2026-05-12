"""add slack activity metrics to slack_users

Revision ID: a7c3f9d2e1b8
Revises: b62e16189188
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7c3f9d2e1b8'
down_revision = 'b62e16189188'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('slack_users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('slack_days_active', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('slack_messages_posted', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('slack_users', schema=None) as batch_op:
        batch_op.drop_column('slack_messages_posted')
        batch_op.drop_column('slack_days_active')
