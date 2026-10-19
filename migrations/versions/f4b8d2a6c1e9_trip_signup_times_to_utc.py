"""Trip signup times: Central wall time to UTC.

The plain admin trip form (in use since the Tabulator grid went away on
2026-06-04) saved what admins typed (Central) while every reader treated the
columns as UTC, so trip signup opened and closed 5 to 6 hours early. From this
revision on the form converts on save; this converts the rows it already
stored. Rows from before 2026-06-04 were saved through the grid in UTC and are
left alone. Each value uses its own offset (CDT or CST).

Revision ID: f4b8d2a6c1e9
Revises: e3a7c1f9b4d2
Create Date: 2026-10-19
"""
from alembic import op

revision = "f4b8d2a6c1e9"
down_revision = "e3a7c1f9b4d2"
branch_labels = None
depends_on = None

COLUMNS = ("signup_start", "signup_end")
FORM_ERA = "2026-06-04"


def _convert(source_zone, target_zone, where_column) -> None:
    assignments = ", ".join(
        f"{c} = (({c}) AT TIME ZONE '{source_zone}') AT TIME ZONE '{target_zone}'" for c in COLUMNS)
    op.execute(f"UPDATE trips SET {assignments} WHERE {where_column} >= '{FORM_ERA}'")


def upgrade():
    _convert("America/Chicago", "UTC", "signup_start")


def downgrade():
    # signup_start only moves later on upgrade, so the same rows still match.
    _convert("UTC", "America/Chicago", "signup_start")
