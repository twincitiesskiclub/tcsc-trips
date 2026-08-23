"""volunteer interests on user_seasons

Revision ID: 6fe27563d4aa
Revises: 8055e0305cc4
Create Date: 2026-08-23 20:17:50.524730

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6fe27563d4aa'
down_revision = '8055e0305cc4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user_seasons', schema=None) as batch_op:
        batch_op.add_column(sa.Column('volunteer_interests', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('volunteer_committees', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('user_seasons', schema=None) as batch_op:
        batch_op.drop_column('volunteer_committees')
        batch_op.drop_column('volunteer_interests')
