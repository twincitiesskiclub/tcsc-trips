"""Add practice analytics archive, lineage, weather and corrections tables.

Revision ID: b8e4d2a9c731
Revises: 6c2f8a4d9e10
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b8e4d2a9c731"
down_revision = "6c2f8a4d9e10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "slack_archive_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.String(20), nullable=False),
        sa.Column("ts", sa.String(32), nullable=False),
        sa.Column("thread_ts", sa.String(32)),
        sa.Column("user_id", sa.String(20)),
        sa.Column("bot_id", sa.String(20)),
        sa.Column("subtype", sa.String(64)),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("posted_at", sa.DateTime(), nullable=False),
        sa.Column("edited_at", sa.DateTime()),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("raw", postgresql.JSONB(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("channel_id", "ts", name="uq_slack_archive_channel_ts"),
    )
    op.create_index("ix_slack_archive_thread", "slack_archive_messages",
                    ["channel_id", "thread_ts"])
    op.create_index("ix_slack_archive_posted_at", "slack_archive_messages", ["posted_at"])

    op.create_table(
        "slack_reaction_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.String(20), nullable=False),
        sa.Column("message_ts", sa.String(32), nullable=False),
        sa.Column("emoji", sa.String(100), nullable=False),
        sa.Column("slack_uid", sa.String(20), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("event_ts", sa.String(32)),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("action IN ('added','removed')", name="ck_reaction_event_action"),
    )
    op.create_index("ix_reaction_events_message", "slack_reaction_events",
                    ["channel_id", "message_ts"])

    op.create_table(
        "weather_hours",
        sa.Column("lat", sa.Numeric(6, 2), primary_key=True),
        sa.Column("lon", sa.Numeric(6, 2), primary_key=True),
        sa.Column("hour_local", sa.DateTime(), primary_key=True),
        sa.Column("temp_f", sa.Float()),
        sa.Column("feels_like_f", sa.Float()),
        sa.Column("precip_in", sa.Float()),
        sa.Column("snowfall_in", sa.Float()),
        sa.Column("snow_depth_in", sa.Float()),
        sa.Column("wind_mph", sa.Float()),
        sa.Column("weather_code", sa.Integer()),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_key", sa.String(80), nullable=False),
        sa.Column("era", sa.String(10), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("source_message_id", sa.Integer(),
                  sa.ForeignKey("slack_archive_messages.id", ondelete="SET NULL")),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id", ondelete="SET NULL")),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time()),
        sa.Column("day_of_week", sa.String(10), nullable=False),
        sa.Column("season_label", sa.String(40), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("practice_locations.id", ondelete="SET NULL")),
        sa.Column("location_name", sa.String(255)),
        sa.Column("lat", sa.Float()),
        sa.Column("lon", sa.Float()),
        sa.Column("is_indoor", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("activity", sa.String(40), nullable=False),
        sa.Column("activities", postgresql.ARRAY(sa.String(80)), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("workout_type", sa.String(40), nullable=False),
        sa.Column("workout_types", postgresql.ARRAY(sa.String(80)), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("slot", sa.String(10)),
        sa.Column("group_key", sa.String(80), nullable=False),
        sa.Column("rsvp_emoji", sa.String(100)),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("rsvp_count", sa.Integer(), nullable=False),
        sa.Column("temp_f", sa.Float()),
        sa.Column("feels_like_f", sa.Float()),
        sa.Column("wind_mph", sa.Float()),
        sa.Column("precip_in", sa.Float()),
        sa.Column("snowfall_in", sa.Float()),
        sa.Column("snowfall_prior_24h_in", sa.Float()),
        sa.Column("snow_depth_in", sa.Float()),
        sa.Column("weather_code", sa.Integer()),
        sa.Column("minutes_after_sunset", sa.Integer()),
        sa.Column("flags", postgresql.ARRAY(sa.String(40)), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rebuilt_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_key", name="uq_practice_sessions_session_key"),
        sa.CheckConstraint("format IN ('single','split','merged')", name="ck_session_format"),
        sa.CheckConstraint("status IN ('held','cancelled')", name="ck_session_status"),
        sa.CheckConstraint("kind IN ('practice','event')", name="ck_session_kind"),
    )
    op.create_index("ix_practice_sessions_date", "practice_sessions", ["date"])
    op.create_index("ix_practice_sessions_season_label", "practice_sessions", ["season_label"])
    op.create_index("ix_practice_sessions_activity", "practice_sessions", ["activity"])

    op.create_table(
        "practice_attendance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(),
                  sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slack_uid", sa.String(20), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("emoji", sa.String(100)),
        sa.Column("slot", sa.String(10)),
        sa.Column("source", sa.String(12), nullable=False),
        sa.UniqueConstraint("session_id", "slack_uid", "role", "emoji",
                            name="uq_attendance_session_uid_role_emoji"),
        sa.CheckConstraint("role IN ('rsvp','plan','lead','coach')", name="ck_attendance_role"),
    )
    op.create_index("ix_practice_attendance_session_id", "practice_attendance", ["session_id"])
    op.create_index("ix_practice_attendance_slack_uid", "practice_attendance", ["slack_uid"])

    op.create_table(
        "analytics_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("author", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("key", name="uq_analytics_corrections_key"),
    )


def downgrade():
    op.drop_table("analytics_corrections")
    op.drop_table("practice_attendance")
    op.drop_table("practice_sessions")
    op.drop_table("weather_hours")
    op.drop_table("slack_reaction_events")
    op.drop_table("slack_archive_messages")
