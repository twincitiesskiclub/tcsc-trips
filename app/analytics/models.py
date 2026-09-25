"""Analytics tables. Layer 1 (archive) is written by archive.py and
reaction_log.py; layer 2 (sessions, attendance) only by rebuild.py;
weather_hours only by weather.py."""
from datetime import datetime

from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from app.models import db


class SlackArchiveMessage(db.Model):
    __tablename__ = "slack_archive_messages"

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.String(20), nullable=False)
    ts = db.Column(db.String(32), nullable=False)
    thread_ts = db.Column(db.String(32))
    user_id = db.Column(db.String(20))
    bot_id = db.Column(db.String(20))
    subtype = db.Column(db.String(64))
    text = db.Column(db.Text, nullable=False, default="")
    posted_at = db.Column(db.DateTime, nullable=False)
    edited_at = db.Column(db.DateTime)
    deleted_at = db.Column(db.DateTime)
    raw = db.Column(JSONB, nullable=False)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("channel_id", "ts", name="uq_slack_archive_channel_ts"),
        db.Index("ix_slack_archive_thread", "channel_id", "thread_ts"),
        db.Index("ix_slack_archive_posted_at", "posted_at"),
    )


class SlackReactionEvent(db.Model):
    __tablename__ = "slack_reaction_events"

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.String(20), nullable=False)
    message_ts = db.Column(db.String(32), nullable=False)
    emoji = db.Column(db.String(100), nullable=False)
    slack_uid = db.Column(db.String(20), nullable=False)
    action = db.Column(db.String(10), nullable=False)  # added | removed
    event_ts = db.Column(db.String(32))
    received_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("action IN ('added','removed')", name="ck_reaction_event_action"),
        db.Index("ix_reaction_events_message", "channel_id", "message_ts"),
    )


class PracticeSession(db.Model):
    __tablename__ = "practice_sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_key = db.Column(db.String(80), nullable=False)
    era = db.Column(db.String(10), nullable=False)          # template | app | trip
    kind = db.Column(db.String(10), nullable=False, default="practice")  # practice | event | trip
    category = db.Column(db.String(20), nullable=False, default="practice", index=True)
    source_message_id = db.Column(db.Integer, db.ForeignKey("slack_archive_messages.id", ondelete="SET NULL"))
    practice_id = db.Column(db.Integer, db.ForeignKey("practices.id", ondelete="SET NULL"))
    date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time)
    day_of_week = db.Column(db.String(10), nullable=False)
    season_label = db.Column(db.String(40), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey("practice_locations.id", ondelete="SET NULL"))
    location_name = db.Column(db.String(255))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    is_indoor = db.Column(db.Boolean, nullable=False, default=False)
    activity = db.Column(db.String(40), nullable=False, default="Other", index=True)
    activities = db.Column(ARRAY(db.String(80)), nullable=False, default=list)
    workout_type = db.Column(db.String(40), nullable=False, default="Other")
    workout_types = db.Column(ARRAY(db.String(80)), nullable=False, default=list)
    title = db.Column(db.Text, nullable=False, default="")
    format = db.Column(db.String(10), nullable=False, default="single")  # single | split | merged
    slot = db.Column(db.String(10))                                      # early | late
    group_key = db.Column(db.String(80), nullable=False)
    rsvp_emoji = db.Column(db.String(100))
    status = db.Column(db.String(10), nullable=False, default="held")  # held | cancelled
    rsvp_count = db.Column(db.Integer, nullable=False, default=0)
    reported_count = db.Column(db.Integer)  # count-only sessions: names were lost
    temp_f = db.Column(db.Float)
    feels_like_f = db.Column(db.Float)
    wind_mph = db.Column(db.Float)
    precip_in = db.Column(db.Float)
    snowfall_in = db.Column(db.Float)
    snowfall_prior_24h_in = db.Column(db.Float)
    snow_depth_in = db.Column(db.Float)
    weather_code = db.Column(db.Integer)
    minutes_after_sunset = db.Column(db.Integer)
    flags = db.Column(ARRAY(db.String(40)), nullable=False, default=list)
    needs_review = db.Column(db.Boolean, nullable=False, default=False)
    rebuilt_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    attendance = db.relationship(
        "PracticeAttendance", backref="session", cascade="all, delete-orphan",
        passive_deletes=True)

    __table_args__ = (
        db.UniqueConstraint("session_key", name="uq_practice_sessions_session_key"),
        db.CheckConstraint("format IN ('single','split','merged')", name="ck_session_format"),
        db.CheckConstraint("status IN ('held','cancelled')", name="ck_session_status"),
        db.CheckConstraint("kind IN ('practice','event','trip')", name="ck_session_kind"),
        db.CheckConstraint(
            "category IN ('practice','kickoff','social','board','race','volunteer','banquet','other','trip')",
            name="ck_session_category"),
    )


class PracticeAttendance(db.Model):
    __tablename__ = "practice_attendance"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True)
    slack_uid = db.Column(db.String(20), index=True)
    person_key = db.Column(db.String(120), nullable=False, index=True)  # slack:U.. | user:N | name:...
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    role = db.Column(db.String(10), nullable=False)    # rsvp | plan | lead | coach | signup | decline
    emoji = db.Column(db.String(100))
    slot = db.Column(db.String(10))                    # early | late
    source = db.Column(db.String(12), nullable=False)  # reaction | button | post_text | app | correction

    __table_args__ = (
        db.UniqueConstraint("session_id", "person_key", "role", "emoji",
                            name="uq_attendance_session_person_role_emoji"),
        db.CheckConstraint("role IN ('rsvp','plan','lead','coach','signup','decline')",
                           name="ck_attendance_role"),
    )


class WeatherHour(db.Model):
    __tablename__ = "weather_hours"

    lat = db.Column(db.Numeric(6, 2), primary_key=True)
    lon = db.Column(db.Numeric(6, 2), primary_key=True)
    hour_local = db.Column(db.DateTime, primary_key=True)  # naive Central
    temp_f = db.Column(db.Float)
    feels_like_f = db.Column(db.Float)
    precip_in = db.Column(db.Float)
    snowfall_in = db.Column(db.Float)
    snow_depth_in = db.Column(db.Float)
    wind_mph = db.Column(db.Float)
    weather_code = db.Column(db.Integer)
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class AnalyticsCorrection(db.Model):
    """One fix to the lineage, keyed by session_key or "<channel>:<ts>" (whole post).
    Data, not config: lives here, never in the repo."""
    __tablename__ = "analytics_corrections"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), nullable=False)
    fields = db.Column(JSONB, nullable=False)          # validated by corrections.validate_correction
    note = db.Column(db.Text, nullable=False)          # why; required
    author = db.Column(db.String(80), nullable=False)  # "claude-fixer", "rob", ...
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("key", name="uq_analytics_corrections_key"),
    )
