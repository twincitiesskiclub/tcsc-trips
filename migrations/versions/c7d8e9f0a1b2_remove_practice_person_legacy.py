"""Remove PracticePerson legacy model

Revision ID: c7d8e9f0a1b2
Revises: 344117c080a7
Create Date: 2025-12-29 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d8e9f0a1b2'
down_revision = '344117c080a7'
branch_labels = None
depends_on = None


def upgrade():
    # First, drop the foreign key constraint and person_id column from practice_leads
    with op.batch_alter_table('practice_leads', schema=None) as batch_op:
        # Drop the FK constraint to practice_people
        batch_op.drop_constraint('practice_leads_person_id_fkey', type_='foreignkey')
        batch_op.drop_column('person_id')

    # Now drop the practice_people table entirely
    op.drop_table('practice_people')


def downgrade():
    # Recreate practice_people table
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

    # Re-add person_id column to practice_leads
    with op.batch_alter_table('practice_leads', schema=None) as batch_op:
        batch_op.add_column(sa.Column('person_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'practice_leads_person_id_fkey',
            'practice_people',
            ['person_id'],
            ['id']
        )
