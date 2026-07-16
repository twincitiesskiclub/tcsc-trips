"""add practice summary posts

Revision ID: d8b2c6f4a901
Revises: c4f1a8e2d9b7
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa

revision = "d8b2c6f4a901"
down_revision = "c4f1a8e2d9b7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "practice_summary_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("surface", sa.String(32), nullable=False),
        sa.Column("channel_id", sa.String(50)),
        sa.Column("message_ts", sa.String(50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "week_start", "surface",
            name="uq_practice_summary_post_week_surface",
        ),
        sa.CheckConstraint(
            "surface IN ('coach_summary', 'weekly_summary')",
            name="ck_practice_summary_post_surface",
        ),
    )
    op.execute(sa.text("""
        DO $$
        BEGIN
          IF EXISTS (
            WITH legacy AS (
              SELECT date_trunc('week', date)::date AS week_start,
                     'coach_summary'::text AS surface,
                     slack_coach_summary_ts AS message_ts
              FROM practices WHERE slack_coach_summary_ts IS NOT NULL
              UNION ALL
              SELECT date_trunc('week', date)::date,
                     'weekly_summary'::text,
                     slack_weekly_summary_ts
              FROM practices WHERE slack_weekly_summary_ts IS NOT NULL
            )
            SELECT 1 FROM legacy
            GROUP BY week_start, surface
            HAVING count(DISTINCT message_ts) > 1
          ) THEN
            RAISE EXCEPTION
              'conflicting legacy practice summary timestamps';
          END IF;
        END $$;
    """))
    op.execute(sa.text("""
        INSERT INTO practice_summary_posts
            (week_start, surface, channel_id, message_ts)
        SELECT date_trunc('week', date)::date,
               'coach_summary', NULL, min(slack_coach_summary_ts)
        FROM practices
        WHERE slack_coach_summary_ts IS NOT NULL
        GROUP BY date_trunc('week', date)::date
        UNION ALL
        SELECT date_trunc('week', date)::date,
               'weekly_summary', NULL, min(slack_weekly_summary_ts)
        FROM practices
        WHERE slack_weekly_summary_ts IS NOT NULL
        GROUP BY date_trunc('week', date)::date
    """))


def downgrade():
    op.drop_table("practice_summary_posts")
