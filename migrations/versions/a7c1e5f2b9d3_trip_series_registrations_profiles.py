"""trip series, registrations, profiles

Revision ID: a7c1e5f2b9d3
Revises: 539ad532aeb3
Create Date: 2026-07-31

"""
from alembic import op
import sqlalchemy as sa

revision = 'a7c1e5f2b9d3'
down_revision = '539ad532aeb3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'trip_series',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('destination', sa.String(length=255), nullable=False),
        sa.Column('slack_channel_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_trip_series_slug'),
    )
    op.create_index('ix_trip_series_slug', 'trip_series', ['slug'])

    op.create_table(
        'trip_registrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trip_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('price_tier', sa.String(length=10), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('payment_intent_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trip_id', 'user_id',
                            name='uq_trip_registration_member'),
    )

    op.create_table(
        'trip_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('can_drive', sa.Boolean(), nullable=True),
        sa.Column('seat_capacity', sa.Integer(), nullable=True),
        sa.Column('bike_capacity', sa.Integer(), nullable=True),
        sa.Column('hitch_size', sa.String(length=10), nullable=True),
        sa.Column('region_code', sa.String(length=10), nullable=True),
        sa.Column('dietary_restrictions', sa.JSON(), nullable=False),
        sa.Column('dietary_other', sa.String(length=255), nullable=False),
        sa.Column('has_tent', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_trip_profile_user'),
    )

    with op.batch_alter_table('trips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('series_id', sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column('custom_questions', sa.JSON(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_trips_series_id', 'trip_series', ['series_id'], ['id']
        )

    # Data migration: each existing trip becomes the first edition of a new
    # series that inherits its slug, name, destination and Slack channel.
    conn = op.get_bind()
    trips = conn.execute(sa.text(
        "SELECT id, slug, name, destination, slack_channel_name FROM trips"
    )).fetchall()
    for trip in trips:
        series_id = conn.execute(
            sa.text(
                "INSERT INTO trip_series "
                "(slug, name, destination, slack_channel_name, created_at, updated_at) "
                "VALUES (:slug, :name, :destination, :channel, NOW(), NOW()) "
                "RETURNING id"
            ),
            {"slug": trip.slug, "name": trip.name,
             "destination": trip.destination,
             "channel": trip.slack_channel_name},
        ).scalar()
        conn.execute(
            sa.text(
                "UPDATE trips SET series_id = :sid, custom_questions = '[]' "
                "WHERE id = :tid"
            ),
            {"sid": series_id, "tid": trip.id},
        )
    conn.execute(sa.text(
        "UPDATE trips SET custom_questions = '[]' WHERE custom_questions IS NULL"
    ))


def downgrade():
    with op.batch_alter_table('trips', schema=None) as batch_op:
        batch_op.drop_constraint('fk_trips_series_id', type_='foreignkey')
        batch_op.drop_column('custom_questions')
        batch_op.drop_column('series_id')
    op.drop_table('trip_profiles')
    op.drop_table('trip_registrations')
    op.drop_index('ix_trip_series_slug', table_name='trip_series')
    op.drop_table('trip_series')
