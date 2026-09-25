"""Widen analytics lineage to events and trips.

Revision ID: c3f9a1e7d2b4
Revises: b8e4d2a9c731
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "c3f9a1e7d2b4"
down_revision = "b8e4d2a9c731"
branch_labels = None
depends_on = None

CATEGORIES = "('practice','kickoff','social','board','race','volunteer','banquet','other','trip')"


def upgrade():
    op.add_column("practice_sessions", sa.Column(
        "category", sa.String(20), nullable=False, server_default="practice"))
    op.execute("UPDATE practice_sessions SET category = 'other' WHERE kind = 'event'")
    op.alter_column("practice_sessions", "category", server_default=None)
    op.create_index("ix_practice_sessions_category", "practice_sessions", ["category"])
    op.add_column("practice_sessions", sa.Column("reported_count", sa.Integer()))
    op.drop_constraint("ck_session_kind", "practice_sessions", type_="check")
    op.create_check_constraint("ck_session_kind", "practice_sessions", "kind IN ('practice','event','trip')")
    op.create_check_constraint("ck_session_category", "practice_sessions", f"category IN {CATEGORIES}")

    op.add_column("practice_attendance", sa.Column("person_key", sa.String(120)))
    op.execute("UPDATE practice_attendance SET person_key = 'slack:' || slack_uid")
    op.alter_column("practice_attendance", "person_key", nullable=False)
    op.alter_column("practice_attendance", "slack_uid", nullable=True)
    op.create_index("ix_practice_attendance_person_key", "practice_attendance", ["person_key"])
    op.drop_constraint("uq_attendance_session_uid_role_emoji", "practice_attendance", type_="unique")
    op.create_unique_constraint("uq_attendance_session_person_role_emoji", "practice_attendance",
                                ["session_id", "person_key", "role", "emoji"])
    op.drop_constraint("ck_attendance_role", "practice_attendance", type_="check")
    op.create_check_constraint("ck_attendance_role", "practice_attendance",
                               "role IN ('rsvp','plan','lead','coach','signup','decline')")


def downgrade():
    op.execute("DELETE FROM practice_attendance WHERE slack_uid IS NULL OR role IN ('signup','decline')")
    op.execute("DELETE FROM practice_sessions WHERE kind = 'trip'")
    op.drop_constraint("ck_attendance_role", "practice_attendance", type_="check")
    op.create_check_constraint("ck_attendance_role", "practice_attendance",
                               "role IN ('rsvp','plan','lead','coach')")
    op.drop_constraint("uq_attendance_session_person_role_emoji", "practice_attendance", type_="unique")
    op.create_unique_constraint("uq_attendance_session_uid_role_emoji", "practice_attendance",
                                ["session_id", "slack_uid", "role", "emoji"])
    op.drop_index("ix_practice_attendance_person_key", "practice_attendance")
    op.alter_column("practice_attendance", "slack_uid", nullable=False)
    op.drop_column("practice_attendance", "person_key")
    op.drop_constraint("ck_session_category", "practice_sessions", type_="check")
    op.drop_constraint("ck_session_kind", "practice_sessions", type_="check")
    op.create_check_constraint("ck_session_kind", "practice_sessions", "kind IN ('practice','event')")
    op.drop_column("practice_sessions", "reported_count")
    op.drop_index("ix_practice_sessions_category", "practice_sessions")
    op.drop_column("practice_sessions", "category")
