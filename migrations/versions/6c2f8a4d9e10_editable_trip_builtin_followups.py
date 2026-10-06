"""Store editable follow-ups on carpool and dietary questions.

Revision ID: 6c2f8a4d9e10
Revises: 9f3a1c7e5b20
Create Date: 2026-09-05
"""
from copy import deepcopy

from alembic import op
import sqlalchemy as sa

revision = "6c2f8a4d9e10"
down_revision = "9f3a1c7e5b20"
branch_labels = None
depends_on = None

# Freeze the initial defaults so future wording changes do not alter this migration.
FOLLOWUP_DEFAULTS = {
    "carpool": {
        "seats": {"label": "How many people can you accommodate (besides yourself)?",
                  "help_text": "", "enabled": True},
        "bikes": {"label": "How many bikes can you accommodate?",
                  "help_text": "", "enabled": True},
        "hitch": {"label": "Do you have a trailer hitch?",
                  "help_text": "", "enabled": True},
    },
    "dietary": {
        "other": {"label": "Other dietary restriction(s)?", "help_text": ""},
    },
}


def add_followups(questions):
    """Fill missing follow-up settings while preserving stored edits and order."""
    updated = deepcopy(questions)
    for question in updated or []:
        defaults = FOLLOWUP_DEFAULTS.get(question.get("builtin"))
        if defaults is None:
            continue
        followups = question.setdefault("followups", {})
        for key, fields in defaults.items():
            followups[key] = deepcopy(fields) | followups.get(key, {})
    return updated


def remove_followups(questions):
    updated = deepcopy(questions)
    for question in updated or []:
        if question.get("builtin") in FOLLOWUP_DEFAULTS:
            question.pop("followups", None)
    return updated


def _rewrite(transform):
    trips = sa.table("trips", sa.column("id", sa.Integer()),
                     sa.column("custom_questions", sa.JSON()))
    connection = op.get_bind()
    for trip_id, questions in connection.execute(sa.select(trips)).fetchall():
        updated = transform(questions)
        if updated != questions:
            connection.execute(trips.update().where(trips.c.id == trip_id)
                               .values(custom_questions=updated))


def upgrade():
    _rewrite(add_followups)


def downgrade():
    _rewrite(remove_followups)
