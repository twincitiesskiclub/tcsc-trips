"""Add practice indexes and constraints

Revision ID: 5aa6b7c8d9e0
Revises: 4ff744fa0fd6
Create Date: 2025-12-28 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5aa6b7c8d9e0'
down_revision = '4ff744fa0fd6'
branch_labels = None
depends_on = None


def upgrade():
    # Add CHECK constraint to practice_leads table
    with op.batch_alter_table('practice_leads', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'lead_must_have_person_or_user',
            'person_id IS NOT NULL OR user_id IS NOT NULL'
        )

    # Create performance indexes
    op.create_index('ix_practices_status', 'practices', ['status'], unique=False)
    op.create_index('ix_practice_leads_user_id', 'practice_leads', ['user_id'], unique=False)
    op.create_index('ix_practice_rsvps_user_id', 'practice_rsvps', ['user_id'], unique=False)
    op.create_index('ix_practice_rsvps_practice_id', 'practice_rsvps', ['practice_id'], unique=False)


def downgrade():
    # Remove indexes
    op.drop_index('ix_practice_rsvps_practice_id', table_name='practice_rsvps')
    op.drop_index('ix_practice_rsvps_user_id', table_name='practice_rsvps')
    op.drop_index('ix_practice_leads_user_id', table_name='practice_leads')
    op.drop_index('ix_practices_status', table_name='practices')

    # Remove CHECK constraint
    with op.batch_alter_table('practice_leads', schema=None) as batch_op:
        batch_op.drop_constraint('lead_must_have_person_or_user', type_='check')
