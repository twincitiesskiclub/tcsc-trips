"""Include built-ins in each trip's ordered question list.

Revision ID: 9f3a1c7e5b20
Revises: 2b7e4c9d1f30
Create Date: 2026-09-05
"""
from alembic import op
import sqlalchemy as sa

from app.trips.questions import default_builtin_questions

revision = "9f3a1c7e5b20"
down_revision = "2b7e4c9d1f30"
branch_labels = None
depends_on = None


def prepend_builtins(questions):
    """Keep existing entries and their order, adding only missing built-ins."""
    questions = questions or []
    present = {q["builtin"] for q in questions if "builtin" in q}
    return [q for q in default_builtin_questions() if q["builtin"] not in present] + questions


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
    _rewrite(prepend_builtins)


def downgrade():
    _rewrite(lambda questions: [q for q in questions or [] if "builtin" not in q])
