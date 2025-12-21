"""Replace roles and committees with tags

Revision ID: 36f58dc97c0c
Revises: b2c3d4e5f6a7
Create Date: 2025-12-20 21:54:26.179329

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '36f58dc97c0c'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None

# Initial tags to seed
INITIAL_TAGS = [
    ('PRESIDENT', 'President'),
    ('VICE_PRESIDENT', 'Vice President'),
    ('TREASURER', 'Treasurer'),
    ('SECRETARY', 'Secretary'),
    ('AUDITOR', 'Auditor'),
    ('BOARD_MEMBER', 'Board Member'),
    ('FRIEND_OF_BOARD', 'Friend of Board'),
    ('PRACTICES_DIRECTOR', 'Practices Director'),
    ('PRACTICES_LEAD', 'Practices Lead'),
    ('HEAD_COACH', 'Head Coach'),
    ('ASSISTANT_COACH', 'Assistant Coach'),
    ('WAX_MANAGER', 'Wax Manager'),
    ('TRIP_LEAD', 'Trip Lead'),
    ('ADVENTURES', 'Adventures'),
    ('SOCIAL', 'Social'),
    ('SOCIAL_COMMITTEE', 'Social Committee'),
    ('MARKETING', 'Marketing'),
    ('APPAREL', 'Apparel'),
]


def upgrade():
    # Get connection for conditional checks
    conn = op.get_bind()

    # Drop old tables (if they exist)
    for table in ['user_committees', 'user_roles', 'committees', 'roles']:
        if conn.dialect.has_table(conn, table):
            op.drop_table(table)

    # Drop new tables if they already exist (from db.create_all())
    for table in ['user_tags', 'tags']:
        if conn.dialect.has_table(conn, table):
            op.drop_table(table)

    # Create new tags table
    op.create_table('tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create user_tags junction table
    op.create_table('user_tags',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id', 'tag_id')
    )

    # Seed initial tags
    tags_table = sa.table('tags',
        sa.column('name', sa.String),
        sa.column('display_name', sa.String),
        sa.column('created_at', sa.DateTime)
    )

    op.bulk_insert(tags_table, [
        {'name': name, 'display_name': display_name, 'created_at': datetime.utcnow()}
        for name, display_name in INITIAL_TAGS
    ])


def downgrade():
    # Drop new tables
    op.drop_table('user_tags')
    op.drop_table('tags')

    # Recreate old tables
    op.create_table('roles',
        sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('roles_id_seq'::regclass)"), autoincrement=True, nullable=False),
        sa.Column('name', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint('id', name='roles_pkey'),
        sa.UniqueConstraint('name', name='roles_name_key'),
        postgresql_ignore_search_path=False
    )
    op.create_table('committees',
        sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('committees_id_seq'::regclass)"), autoincrement=True, nullable=False),
        sa.Column('name', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint('id', name='committees_pkey'),
        sa.UniqueConstraint('name', name='committees_name_key'),
        postgresql_ignore_search_path=False
    )
    op.create_table('user_roles',
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('role_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name='user_roles_role_id_fkey'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='user_roles_user_id_fkey'),
        sa.PrimaryKeyConstraint('user_id', 'role_id', name='user_roles_pkey')
    )
    op.create_table('user_committees',
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('committee_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('role', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['committee_id'], ['committees.id'], name='user_committees_committee_id_fkey'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='user_committees_user_id_fkey'),
        sa.PrimaryKeyConstraint('user_id', 'committee_id', name='user_committees_pkey')
    )
