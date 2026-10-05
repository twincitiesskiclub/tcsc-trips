"""Lead availability block posts: block post ts, opener, Wednesday reminder,
monotonic letter position.

Revision ID: 9b2e6d4f1a37
Revises: d4e8f2a6b1c9
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa

revision = "9b2e6d4f1a37"
down_revision = "d4e8f2a6b1c9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lead_availability_polls") as batch:
        batch.add_column(sa.Column("block_post_ts", sa.String(50)))
        batch.add_column(sa.Column("opened_by_slack_uid", sa.String(50)))
        batch.add_column(sa.Column("wednesday_reminder_sent_at", sa.DateTime()))
        batch.add_column(sa.Column(
            "next_position", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("lead_availability_polls") as batch:
        batch.drop_column("next_position")
        batch.drop_column("wednesday_reminder_sent_at")
        batch.drop_column("opened_by_slack_uid")
        batch.drop_column("block_post_ts")
