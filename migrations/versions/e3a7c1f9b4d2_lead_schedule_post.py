"""Lead availability: ts of the lead schedule post in #coord-practices-leads-assists.

Revision ID: e3a7c1f9b4d2
Revises: c7e1a9d3f5b2
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = "e3a7c1f9b4d2"
down_revision = "c7e1a9d3f5b2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lead_availability_polls") as batch:
        batch.add_column(sa.Column("schedule_ts", sa.String(50)))


def downgrade():
    with op.batch_alter_table("lead_availability_polls") as batch:
        batch.drop_column("schedule_ts")
