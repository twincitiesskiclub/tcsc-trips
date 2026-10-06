"""Event datetimes: Central wall time to UTC.

The admin event form saved what admins typed (Central) while every reader
treated the columns as UTC, so the public page showed a 9:00 AM race at
4:00 AM. From this revision on the form converts on save; this converts the
rows already stored. Each value uses its own offset (CDT or CST).

Revision ID: c7e1a9d3f5b2
Revises: 9b2e6d4f1a37
Create Date: 2026-10-06
"""
from alembic import op

revision = "c7e1a9d3f5b2"
down_revision = "9b2e6d4f1a37"
branch_labels = None
depends_on = None

COLUMNS = ("event_date", "signup_start", "signup_end")


def central_to_utc_sql(column: str) -> str:
    return f"(({column}) AT TIME ZONE 'America/Chicago') AT TIME ZONE 'UTC'"


def utc_to_central_sql(column: str) -> str:
    return f"(({column}) AT TIME ZONE 'UTC') AT TIME ZONE 'America/Chicago'"


def _convert(expression) -> None:
    assignments = ", ".join(f"{c} = {expression(c)}" for c in COLUMNS)
    op.execute(f"UPDATE events SET {assignments}")


def upgrade():
    _convert(central_to_utc_sql)


def downgrade():
    _convert(utc_to_central_sql)
