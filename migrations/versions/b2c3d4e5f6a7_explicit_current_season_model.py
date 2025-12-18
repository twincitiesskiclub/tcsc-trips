"""Explicit current season data model

Add Season.is_current, User.seasons_since_active, normalize status values to
uppercase, rename INACTIVE to ALUMNI, expand UserSeasonStatus for lottery tracking.

See DRR-001 for full decision rationale.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add new columns to seasons table
    with op.batch_alter_table('seasons', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_current', sa.Boolean(), nullable=False, server_default='false'))

    # Step 2: Add new columns to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('seasons_since_active', sa.Integer(), nullable=False, server_default='0'))

    # Step 3: Drop old UserSeason status constraint and add expanded one
    with op.batch_alter_table('user_seasons', schema=None) as batch_op:
        batch_op.drop_constraint('check_userseason_status_valid', type_='check')
        batch_op.create_check_constraint(
            'check_userseason_status_valid',
            "status IN ('PENDING_LOTTERY', 'ACTIVE', 'DROPPED_LOTTERY', 'DROPPED_VOLUNTARY', 'DROPPED_CAUSE')"
        )

    # Step 4: Drop old User status constraint before data migration
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('check_user_status_valid', type_='check')

    # Step 5: Migrate User.status data to uppercase and rename 'inactive' to 'ALUMNI'
    op.execute("UPDATE users SET status = 'ACTIVE' WHERE status = 'active'")
    op.execute("UPDATE users SET status = 'ALUMNI' WHERE status = 'inactive'")
    op.execute("UPDATE users SET status = 'PENDING' WHERE status = 'pending'")
    op.execute("UPDATE users SET status = 'DROPPED' WHERE status = 'dropped'")

    # Step 6: Add new User status constraint with uppercase values
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'check_user_status_valid',
            "status IN ('PENDING', 'ACTIVE', 'ALUMNI', 'DROPPED')"
        )

    # Step 7: Set Season id=3 (2025 Fall/Winter) as is_current=True
    op.execute("UPDATE seasons SET is_current = true WHERE id = 3")

    # Step 8: Backfill seasons_since_active from UserSeason history
    # 0 = active in current season (id=3)
    # 1 = active in previous season (id=2) but not current
    # 2 = only active in legacy (id=1) or never active
    op.execute("""
        UPDATE users SET seasons_since_active =
            CASE
                WHEN id IN (SELECT user_id FROM user_seasons WHERE season_id = 3 AND status = 'ACTIVE') THEN 0
                WHEN id IN (SELECT user_id FROM user_seasons WHERE season_id = 2 AND status = 'ACTIVE') THEN 1
                ELSE 2
            END
    """)


def downgrade():
    # Reverse Step 8: Reset seasons_since_active to default
    op.execute("UPDATE users SET seasons_since_active = 0")

    # Reverse Step 7: Clear is_current
    op.execute("UPDATE seasons SET is_current = false")

    # Reverse Step 6: Drop new User status constraint
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('check_user_status_valid', type_='check')

    # Reverse Step 5: Migrate User.status data back to lowercase
    op.execute("UPDATE users SET status = 'active' WHERE status = 'ACTIVE'")
    op.execute("UPDATE users SET status = 'inactive' WHERE status = 'ALUMNI'")
    op.execute("UPDATE users SET status = 'pending' WHERE status = 'PENDING'")
    op.execute("UPDATE users SET status = 'dropped' WHERE status = 'DROPPED'")

    # Reverse Step 4: Recreate old User status constraint
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'check_user_status_valid',
            "status IN ('pending', 'active', 'inactive', 'dropped')"
        )

    # Reverse Step 3: Restore old UserSeason status constraint
    with op.batch_alter_table('user_seasons', schema=None) as batch_op:
        batch_op.drop_constraint('check_userseason_status_valid', type_='check')
        batch_op.create_check_constraint(
            'check_userseason_status_valid',
            "status IN ('PENDING_LOTTERY', 'ACTIVE', 'DROPPED')"
        )

    # Reverse Step 2: Remove seasons_since_active column
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('seasons_since_active')

    # Reverse Step 1: Remove is_current column
    with op.batch_alter_table('seasons', schema=None) as batch_op:
        batch_op.drop_column('is_current')
