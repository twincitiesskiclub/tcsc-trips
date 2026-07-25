"""Lead availability poll models.

A poll owns one Slack message and the emoji-to-practice mapping for it. The
mapping is persisted because inbound reaction events identify only an emoji
name, and because the custom letter emoji have already been renamed once.
"""

from datetime import datetime

from app.models import db


class PollStatus:
    """Plain strings, matching the project's status-field convention."""
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class ParticipantStatus:
    PENDING = "pending"
    RESPONDED = "responded"
    DONE = "done"
    OPTED_OUT = "opted_out"


class LeadAvailabilityPoll(db.Model):
    __tablename__ = "lead_availability_polls"

    id = db.Column(db.Integer, primary_key=True)
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=PollStatus.DRAFT)
    is_shadow = db.Column(db.Boolean, nullable=False, default=False)

    channel_id = db.Column(db.String(50), nullable=False)
    message_ts = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    opened_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    practices = db.relationship(
        "LeadAvailabilityPollPractice", backref="poll",
        cascade="all, delete-orphan", order_by="LeadAvailabilityPollPractice.position",
    )
    participants = db.relationship(
        "LeadAvailabilityParticipant", backref="poll", cascade="all, delete-orphan")
    responses = db.relationship(
        "LeadAvailabilityResponse", backref="poll", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LeadAvailabilityPoll {self.starts_on}..{self.ends_on} {self.status}>"


class LeadAvailabilityPollPractice(db.Model):
    """Emoji-to-practice mapping. Position survives an emoji rename."""
    __tablename__ = "lead_availability_poll_practices"

    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("lead_availability_polls.id"), nullable=False)
    practice_id = db.Column(db.Integer, db.ForeignKey("practices.id"), nullable=False)
    emoji = db.Column(db.String(80), nullable=False)
    position = db.Column(db.Integer, nullable=False)

    practice = db.relationship("Practice")

    __table_args__ = (
        db.UniqueConstraint("poll_id", "emoji", name="uq_poll_emoji"),
        db.UniqueConstraint("poll_id", "practice_id", name="uq_poll_practice"),
    )


class LeadAvailabilityParticipant(db.Model):
    """Drives nudging: who was asked, who has answered, who opted out."""
    __tablename__ = "lead_availability_participants"

    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("lead_availability_polls.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=ParticipantStatus.PENDING)
    last_nudged_at = db.Column(db.DateTime)
    nudge_count = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("poll_id", "user_id", name="uq_poll_participant"),
    )


class LeadAvailabilityResponse(db.Model):
    """A row means available. Un-reacting deletes it; there is no boolean."""
    __tablename__ = "lead_availability_responses"

    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("lead_availability_polls.id"), nullable=False)
    practice_id = db.Column(db.Integer, db.ForeignKey("practices.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    responded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    source = db.Column(db.String(20), nullable=False, default="reaction")

    # Snapshot of what the practice looked like when answered. Staleness is a
    # mismatch against these, NOT against Practice.updated_at — that column has
    # onupdate and a workout-text edit would mark every response stale.
    answered_for_date = db.Column(db.DateTime)
    answered_for_location_id = db.Column(db.Integer)

    user = db.relationship("User")
    practice = db.relationship("Practice")

    __table_args__ = (
        db.UniqueConstraint("poll_id", "practice_id", "user_id", name="uq_poll_practice_user"),
    )
