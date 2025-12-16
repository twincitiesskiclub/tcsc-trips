"""Add social_events table

Revision ID: a1b2c3d4e5f6
Revises: d0b36a24fc23
Create Date: 2025-12-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'd0b36a24fc23'
branch_labels = None
depends_on = None


def upgrade():
    # Create social_events table
    op.create_table('social_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('location', sa.String(length=255), nullable=False),
        sa.Column('max_participants', sa.Integer(), nullable=False),
        sa.Column('event_date', sa.DateTime(), nullable=False),
        sa.Column('signup_start', sa.DateTime(), nullable=False),
        sa.Column('signup_end', sa.DateTime(), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )

    # Add social_event_id column to payments table
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('social_event_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_payments_social_event_id', 'social_events', ['social_event_id'], ['id'])


def downgrade():
    # Remove social_event_id column from payments
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_payments_social_event_id', type_='foreignkey')
        batch_op.drop_column('social_event_id')

    # Drop social_events table
    op.drop_table('social_events')
