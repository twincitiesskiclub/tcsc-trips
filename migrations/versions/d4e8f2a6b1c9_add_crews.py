"""Add crew configs and drafts.

Revision ID: d4e8f2a6b1c9
Revises: 7a1c5e9d3b20
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "d4e8f2a6b1c9"
down_revision = "7a1c5e9d3b20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crew_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("settings", JSONB(), nullable=False, server_default="{}"),
        sa.Column("overrides", JSONB(), nullable=False, server_default="{}"),
        sa.Column("rules", JSONB(), nullable=False, server_default="[]"),
        sa.Column("speedy_user_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("speedy_refreshed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "crew_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("seed", sa.Integer()),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("settings", JSONB(), nullable=False, server_default="{}"),
        sa.Column("rules", JSONB(), nullable=False, server_default="[]"),
        sa.Column("members", JSONB(), nullable=False, server_default="[]"),
        sa.Column("crew_names", JSONB(), nullable=False, server_default="{}"),
        sa.Column("score", sa.Float()),
        sa.Column("created_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('draft','final')", name="ck_crew_draft_status"),
    )
    op.create_index("ix_crew_drafts_season", "crew_drafts", ["season_id"])
    op.create_index("uq_crew_draft_one_final", "crew_drafts", ["season_id"], unique=True,
                    postgresql_where=sa.text("status = 'final'"))


def downgrade():
    op.drop_index("uq_crew_draft_one_final", "crew_drafts")
    op.drop_index("ix_crew_drafts_season", "crew_drafts")
    op.drop_table("crew_drafts")
    op.drop_table("crew_configs")
