"""Add interest_signups.

Revision ID: 7a1c5e9d3b20
Revises: c3f9a1e7d2b4
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa

revision = "7a1c5e9d3b20"
down_revision = "c3f9a1e7d2b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interest_signups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone_e164", sa.String(20)),
        sa.Column("sms_consent_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email", name="uq_interest_signups_email"),
    )


def downgrade():
    op.drop_table("interest_signups")
