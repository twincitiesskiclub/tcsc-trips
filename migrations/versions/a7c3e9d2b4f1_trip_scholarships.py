"""Trip scholarships: one-time per-member trip discount codes.

Revision ID: a7c3e9d2b4f1
Revises: f4b8d2a6c1e9
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op

revision = "a7c3e9d2b4f1"
down_revision = "f4b8d2a6c1e9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trip_scholarships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id"),
                  nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("sent_at", sa.DateTime()),
        sa.Column("claimed_at", sa.DateTime()),
        sa.Column("slack_channel_id", sa.String(32)),
        sa.Column("slack_message_ts", sa.String(32)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "season_id",
                            name="uq_trip_scholarship_member_season"),
    )
    op.add_column(
        "trip_registrations",
        sa.Column("scholarship_id", sa.Integer(),
                  sa.ForeignKey("trip_scholarships.id",
                                name="fk_trip_registrations_scholarship_id"),
                  nullable=True),
    )


def downgrade():
    op.drop_constraint("fk_trip_registrations_scholarship_id",
                       "trip_registrations", type_="foreignkey")
    op.drop_column("trip_registrations", "scholarship_id")
    op.drop_table("trip_scholarships")
