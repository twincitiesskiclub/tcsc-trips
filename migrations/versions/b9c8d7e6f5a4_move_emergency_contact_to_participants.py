"""move emergency contact from event registrations to participants

Revision ID: b9c8d7e6f5a4
Revises: 539ad532aeb3
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9c8d7e6f5a4'
down_revision = '539ad532aeb3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('event_participants', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'emergency_contact_name', sa.String(length=255), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                'emergency_contact_phone', sa.String(length=50), nullable=True
            )
        )

    op.execute(
        """
        UPDATE event_participants AS p
        SET emergency_contact_name = r.emergency_contact_name,
            emergency_contact_phone = r.emergency_contact_phone
        FROM event_registrations AS r
        WHERE p.registration_id = r.id
        """
    )

    with op.batch_alter_table('event_participants', schema=None) as batch_op:
        batch_op.alter_column(
            'emergency_contact_name',
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch_op.alter_column(
            'emergency_contact_phone',
            existing_type=sa.String(length=50),
            nullable=False,
        )

    with op.batch_alter_table('event_registrations', schema=None) as batch_op:
        batch_op.drop_column('emergency_contact_name')
        batch_op.drop_column('emergency_contact_phone')


def downgrade():
    with op.batch_alter_table('event_registrations', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'emergency_contact_name', sa.String(length=255), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                'emergency_contact_phone', sa.String(length=50), nullable=True
            )
        )

    # First participant's contact becomes the registration's; registrations
    # with no participants fall back to empty strings (matches the migrated
    # social registrations, which never collected one).
    op.execute(
        """
        UPDATE event_registrations AS r
        SET emergency_contact_name = p.emergency_contact_name,
            emergency_contact_phone = p.emergency_contact_phone
        FROM event_participants AS p
        WHERE p.registration_id = r.id AND p.position = 1
        """
    )
    op.execute(
        """
        UPDATE event_registrations
        SET emergency_contact_name = COALESCE(emergency_contact_name, ''),
            emergency_contact_phone = COALESCE(emergency_contact_phone, '')
        """
    )

    with op.batch_alter_table('event_registrations', schema=None) as batch_op:
        batch_op.alter_column(
            'emergency_contact_name',
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch_op.alter_column(
            'emergency_contact_phone',
            existing_type=sa.String(length=50),
            nullable=False,
        )

    with op.batch_alter_table('event_participants', schema=None) as batch_op:
        batch_op.drop_column('emergency_contact_phone')
        batch_op.drop_column('emergency_contact_name')
