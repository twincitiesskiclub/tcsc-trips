"""add practice plan reactions

Revision ID: c4f1a8e2d9b7
Revises: e36bbec59bde
Create Date: 2026-07-12
"""

import json

from alembic import op
import sqlalchemy as sa

revision = "c4f1a8e2d9b7"
down_revision = "e36bbec59bde"
branch_labels = None
depends_on = None

EVERGREEN = json.dumps([
    {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}
])


def upgrade():
    op.add_column(
        "practice_activities",
        sa.Column(
            "default_plan_reactions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "practice_types",
        sa.Column(
            "default_plan_reactions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "practices",
        sa.Column(
            "plan_reactions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column("practices", sa.Column("slack_session_emoji", sa.String(80)))

    op.execute(sa.text("""
        UPDATE practice_types
        SET default_plan_reactions = CAST(:evergreen AS JSON)
        WHERE has_intervals IS TRUE
    """).bindparams(evergreen=EVERGREEN))
    op.execute(sa.text("""
        UPDATE practices AS p
        SET plan_reactions = CAST(:evergreen AS JSON)
        WHERE EXISTS (
            SELECT 1
            FROM practice_types_junction AS j
            JOIN practice_types AS t ON t.id = j.type_id
            WHERE j.practice_id = p.id AND t.has_intervals IS TRUE
        )
    """).bindparams(evergreen=EVERGREEN))


def downgrade():
    op.drop_column("practices", "slack_session_emoji")
    op.drop_column("practices", "plan_reactions")
    op.drop_column("practice_types", "default_plan_reactions")
    op.drop_column("practice_activities", "default_plan_reactions")
