"""
SQLAlchemy models for Practice Management System.

These models map to the Airtable schema and include additional fields
for status tracking, Slack integration, and the Skipper workflow.
"""

from datetime import datetime
from app.models import db
from app.practices.interfaces import (
    PracticeStatus,
    CancellationStatus,
    RSVPStatus,
    LeadRole
)


# =============================================================================
# Location Models
# =============================================================================

class SocialLocation(db.Model):
    """Post-practice social venues."""
    __tablename__ = 'social_locations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(500))
    google_maps_url = db.Column(db.String(500))
    airtable_id = db.Column(db.String(50), unique=True)  # For migration reference
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SocialLocation {self.name}>'


class PracticeLocation(db.Model):
    """Practice venues with coordinates for weather API."""
    __tablename__ = 'practice_locations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    spot = db.Column(db.String(255))  # Specific spot at location
    address = db.Column(db.String(500))
    google_maps_url = db.Column(db.String(500))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    parking_notes = db.Column(db.Text)
    airtable_id = db.Column(db.String(50), unique=True)  # For migration reference
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PracticeLocation {self.name}>'


# =============================================================================
# Activity & Type Models
# =============================================================================

class PracticeActivity(db.Model):
    """Activity types with gear requirements (e.g., Classic Skiing, Skate Skiing)."""
    __tablename__ = 'practice_activities'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    gear_required = db.Column(db.JSON)  # List of required gear as JSON array
    airtable_id = db.Column(db.String(50), unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PracticeActivity {self.name}>'


class PracticeType(db.Model):
    """Workout types with fitness goals (e.g., Intervals, Distance, Technique)."""
    __tablename__ = 'practice_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    fitness_goals = db.Column(db.JSON)  # List of fitness goals as JSON array
    has_intervals = db.Column(db.Boolean, default=False, nullable=False)
    airtable_id = db.Column(db.String(50), unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PracticeType {self.name}>'


# =============================================================================
# Many-to-Many Junction Tables
# =============================================================================

practice_activities_junction = db.Table(
    'practice_activities_junction',
    db.Column('practice_id', db.Integer, db.ForeignKey('practices.id'), primary_key=True),
    db.Column('activity_id', db.Integer, db.ForeignKey('practice_activities.id'), primary_key=True),
    db.Column('created_at', db.DateTime, nullable=False, default=datetime.utcnow)
)

practice_types_junction = db.Table(
    'practice_types_junction',
    db.Column('practice_id', db.Integer, db.ForeignKey('practices.id'), primary_key=True),
    db.Column('type_id', db.Integer, db.ForeignKey('practice_types.id'), primary_key=True),
    db.Column('created_at', db.DateTime, nullable=False, default=datetime.utcnow)
)


# =============================================================================
# Practice Model
# =============================================================================

class Practice(db.Model):
    """Individual practice/workout session."""
    __tablename__ = 'practices'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, index=True)
    day_of_week = db.Column(db.String(20), nullable=False)  # e.g., "Tuesday"
    status = db.Column(db.String(50), nullable=False, default=PracticeStatus.SCHEDULED.value)

    # Location
    location_id = db.Column(db.Integer, db.ForeignKey('practice_locations.id'))
    social_location_id = db.Column(db.Integer, db.ForeignKey('social_locations.id'))

    # Workout descriptions (from Airtable rich text)
    warmup_description = db.Column(db.Text)
    workout_description = db.Column(db.Text)
    cooldown_description = db.Column(db.Text)

    # Flags
    is_dark_practice = db.Column(db.Boolean, default=False, nullable=False)

    # Slack integration
    slack_message_ts = db.Column(db.String(50))  # Message timestamp for updates
    slack_channel_id = db.Column(db.String(50))
    slack_log_message_ts = db.Column(db.String(50))  # Logging thread in #tcsc-logging
    slack_collab_message_ts = db.Column(db.String(50))  # Collab review post in #collab-coaches-practices
    slack_coach_summary_ts = db.Column(db.String(50))  # Weekly coach summary post for threading edits

    # Coach review workflow
    coach_approved = db.Column(db.Boolean, default=False, nullable=False)
    approved_by_slack_uid = db.Column(db.String(50))
    approved_at = db.Column(db.DateTime)
    escalated = db.Column(db.Boolean, default=False, nullable=False)

    # Cancellation
    cancellation_reason = db.Column(db.Text)

    # Metadata
    airtable_id = db.Column(db.String(50), unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    location = db.relationship('PracticeLocation', backref='practices')
    social_location = db.relationship('SocialLocation', backref='practices')
    activities = db.relationship(
        'PracticeActivity',
        secondary=practice_activities_junction,
        backref='practices'
    )
    practice_types = db.relationship(
        'PracticeType',
        secondary=practice_types_junction,
        backref='practices'
    )
    leads = db.relationship('PracticeLead', backref='practice', cascade='all, delete-orphan')
    rsvps = db.relationship('PracticeRSVP', backref='practice', cascade='all, delete-orphan')
    cancellation_requests = db.relationship(
        'CancellationRequest',
        backref='practice',
        cascade='all, delete-orphan'
    )

    @property
    def has_social(self):
        """Derived from whether a social location is set."""
        return self.social_location_id is not None

    def __repr__(self):
        return f'<Practice {self.date} {self.location.name if self.location else "No Location"}>'


# =============================================================================
# Practice Lead/Coach Assignment Model
# =============================================================================

class PracticeLead(db.Model):
    """Assignment of a user to a practice role (lead/coach/assist)."""
    __tablename__ = 'practice_leads'

    id = db.Column(db.Integer, primary_key=True)
    practice_id = db.Column(db.Integer, db.ForeignKey('practices.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'lead', 'coach', 'assist'
    confirmed = db.Column(db.Boolean, default=False, nullable=False)
    confirmed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='practice_assignments')

    @property
    def display_name(self):
        """Return the name from the linked user."""
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}"
        return "Unknown"

    def __repr__(self):
        name = self.display_name
        return f'<PracticeLead {name} {self.role} Practice#{self.practice_id}>'


# =============================================================================
# RSVP Model
# =============================================================================

class PracticeRSVP(db.Model):
    """Member RSVP for a practice."""
    __tablename__ = 'practice_rsvps'

    id = db.Column(db.Integer, primary_key=True)
    practice_id = db.Column(db.Integer, db.ForeignKey('practices.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=RSVPStatus.MAYBE.value)
    slack_user_id = db.Column(db.String(50))  # For Slack integration
    notes = db.Column(db.Text)
    responded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='practice_rsvps')

    # Unique constraint: one RSVP per user per practice
    __table_args__ = (
        db.UniqueConstraint('practice_id', 'user_id', name='unique_practice_user_rsvp'),
    )

    def __repr__(self):
        return f'<PracticeRSVP User#{self.user_id} {self.status} Practice#{self.practice_id}>'


# =============================================================================
# Cancellation Request Model (Skipper Workflow)
# =============================================================================

class CancellationRequest(db.Model):
    """Cancellation proposal requiring human approval."""
    __tablename__ = 'cancellation_requests'

    id = db.Column(db.Integer, primary_key=True)
    practice_id = db.Column(db.Integer, db.ForeignKey('practices.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=CancellationStatus.PENDING.value)

    # Reason details
    reason_type = db.Column(db.String(50), nullable=False)  # 'weather', 'trail_conditions', 'no_lead', 'event_conflict'
    reason_summary = db.Column(db.Text, nullable=False)
    evaluation_data = db.Column(db.JSON)  # Serialized PracticeEvaluation

    # Slack integration
    slack_message_ts = db.Column(db.String(50))
    slack_channel_id = db.Column(db.String(50))

    # Decision tracking
    decided_at = db.Column(db.DateTime)
    decided_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    decided_by_slack_uid = db.Column(db.String(50))
    decision_notes = db.Column(db.Text)

    # Timeout
    proposed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # Fail-open if no decision by this time

    # Metadata
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    decided_by_user = db.relationship('User', backref='cancellation_decisions', foreign_keys=[decided_by_user_id])

    def __repr__(self):
        return f'<CancellationRequest Practice#{self.practice_id} {self.status}>'
