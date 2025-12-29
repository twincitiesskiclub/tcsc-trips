"""Add practice management models

Revision ID: abc123456789
Revises: 88054c86f617
Create Date: 2025-12-27 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'abc123456789'
down_revision = '88054c86f617'
branch_labels = None
depends_on = None


def upgrade():
    # Create social_locations table
    op.create_table(
        'social_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('google_maps_url', sa.String(length=500), nullable=True),
        sa.Column('airtable_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('airtable_id')
    )

    # Create practice_locations table
    op.create_table(
        'practice_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('spot', sa.String(length=255), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('google_maps_url', sa.String(length=500), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('parking_notes', sa.Text(), nullable=True),
        sa.Column('social_location_id', sa.Integer(), nullable=True),
        sa.Column('airtable_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['social_location_id'], ['social_locations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('airtable_id')
    )

    # Create practice_activities table
    op.create_table(
        'practice_activities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('gear_required', sa.JSON(), nullable=True),
        sa.Column('airtable_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('airtable_id')
    )

    # Create practice_types table
    op.create_table(
        'practice_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('fitness_goals', sa.JSON(), nullable=True),
        sa.Column('has_intervals', sa.Boolean(), nullable=False),
        sa.Column('airtable_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('airtable_id')
    )

    # Create practice_people table
    op.create_table(
        'practice_people',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('short_name', sa.String(length=255), nullable=False),
        sa.Column('slack_user_id', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('airtable_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('airtable_id')
    )

    # Create practices table
    op.create_table(
        'practices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('day_of_week', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('location_id', sa.Integer(), nullable=True),
        sa.Column('warmup_description', sa.Text(), nullable=True),
        sa.Column('workout_description', sa.Text(), nullable=True),
        sa.Column('cooldown_description', sa.Text(), nullable=True),
        sa.Column('has_social', sa.Boolean(), nullable=False),
        sa.Column('is_dark_practice', sa.Boolean(), nullable=False),
        sa.Column('slack_message_ts', sa.String(length=50), nullable=True),
        sa.Column('slack_channel_id', sa.String(length=50), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('airtable_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['location_id'], ['practice_locations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('airtable_id')
    )
    op.create_index(op.f('ix_practices_date'), 'practices', ['date'], unique=False)

    # Create practice_activities_junction table
    op.create_table(
        'practice_activities_junction',
        sa.Column('practice_id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['practice_activities.id'], ),
        sa.ForeignKeyConstraint(['practice_id'], ['practices.id'], ),
        sa.PrimaryKeyConstraint('practice_id', 'activity_id')
    )

    # Create practice_types_junction table
    op.create_table(
        'practice_types_junction',
        sa.Column('practice_id', sa.Integer(), nullable=False),
        sa.Column('type_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['practice_id'], ['practices.id'], ),
        sa.ForeignKeyConstraint(['type_id'], ['practice_types.id'], ),
        sa.PrimaryKeyConstraint('practice_id', 'type_id')
    )

    # Create practice_leads table
    op.create_table(
        'practice_leads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('practice_id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('confirmed', sa.Boolean(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['person_id'], ['practice_people.id'], ),
        sa.ForeignKeyConstraint(['practice_id'], ['practices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create practice_rsvps table
    op.create_table(
        'practice_rsvps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('practice_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('slack_user_id', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('responded_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['practice_id'], ['practices.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('practice_id', 'user_id', name='unique_practice_user_rsvp')
    )

    # Create cancellation_requests table
    op.create_table(
        'cancellation_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('practice_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reason_type', sa.String(length=50), nullable=False),
        sa.Column('reason_summary', sa.Text(), nullable=False),
        sa.Column('evaluation_data', sa.JSON(), nullable=True),
        sa.Column('slack_message_ts', sa.String(length=50), nullable=True),
        sa.Column('slack_channel_id', sa.String(length=50), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('decided_by_user_id', sa.Integer(), nullable=True),
        sa.Column('decided_by_slack_uid', sa.String(length=50), nullable=True),
        sa.Column('decision_notes', sa.Text(), nullable=True),
        sa.Column('proposed_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['decided_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['practice_id'], ['practices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('cancellation_requests')
    op.drop_table('practice_rsvps')
    op.drop_table('practice_leads')
    op.drop_table('practice_types_junction')
    op.drop_table('practice_activities_junction')
    op.drop_index(op.f('ix_practices_date'), table_name='practices')
    op.drop_table('practices')
    op.drop_table('practice_people')
    op.drop_table('practice_types')
    op.drop_table('practice_activities')
    op.drop_table('practice_locations')
    op.drop_table('social_locations')
