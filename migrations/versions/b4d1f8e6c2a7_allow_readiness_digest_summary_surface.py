"""allow readiness_digest practice summary surface

Revision ID: b4d1f8e6c2a7
Revises: 3d34ea39db0f
Create Date: 2026-07-26
"""

from alembic import op

revision = "b4d1f8e6c2a7"
down_revision = "3d34ea39db0f"
branch_labels = None
depends_on = None

TABLE = "practice_summary_posts"
CONSTRAINT = "ck_practice_summary_post_surface"


def upgrade():
    op.drop_constraint(CONSTRAINT, TABLE, type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        TABLE,
        "surface IN ('coach_summary', 'weekly_summary', 'readiness_digest')",
    )


def downgrade():
    # readiness_digest rows would violate the restored two-value constraint.
    # They only cache a Slack message identity; deleting them just means the
    # next daily nudge posts a fresh top-level digest and re-records itself.
    op.execute(f"DELETE FROM {TABLE} WHERE surface = 'readiness_digest'")
    op.drop_constraint(CONSTRAINT, TABLE, type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        TABLE,
        "surface IN ('coach_summary', 'weekly_summary')",
    )
