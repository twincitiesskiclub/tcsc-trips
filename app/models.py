from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import JSON  # Database-agnostic: uses JSONB on PostgreSQL, TEXT on SQLite
from sqlalchemy.sql import func

from app.constants import UserStatus, UserSeasonStatus

db = SQLAlchemy()

class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    payment_intent_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # Amount in cents
    status = db.Column(db.String(50), nullable=False)
    payment_type = db.Column(db.String(50), nullable=False)  # 'season', 'trip', 'social_event'
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=True)  # Nullable for season payments
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), nullable=True)  # For season payments
    social_event_id = db.Column(db.Integer, db.ForeignKey('social_events.id'), nullable=True)  # For social event payments
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    season = db.relationship('Season', backref='payments', lazy=True)

    def __repr__(self):
        return f'<Payment {self.payment_intent_id}>'

    @classmethod
    def get_by_payment_intent(cls, payment_intent_id):
        """Find a payment by Stripe payment_intent_id. Returns None if not found."""
        return cls.query.filter_by(payment_intent_id=payment_intent_id).first()

class Trip(db.Model):
    __tablename__ = 'trips'
    
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False)  # e.g., 'training-trip'
    name = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    slack_channel_name = db.Column(db.String(255), nullable=True)
    max_participants_standard = db.Column(db.Integer, nullable=False)
    max_participants_extra = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    signup_start = db.Column(db.DateTime, nullable=False)
    signup_end = db.Column(db.DateTime, nullable=False)
    price_low = db.Column(db.Integer, nullable=False)  # Amount in cents
    price_high = db.Column(db.Integer, nullable=False)  # Amount in cents
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='draft')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with payments
    payments = db.relationship('Payment', backref='trip', lazy=True)

    def __repr__(self):
        return f'<Trip {self.slug}>'

    @property
    def formatted_date_range(self):
        """Returns formatted date range for display"""
        if self.start_date.month == self.end_date.month:
            return f"{self.start_date.strftime('%B %-d')}-{self.end_date.strftime('%-d, %Y')}"
        return f"{self.start_date.strftime('%B %-d')} - {self.end_date.strftime('%B %-d, %Y')}"


class SocialEvent(db.Model):
    __tablename__ = 'social_events'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False)  # e.g., 'pickleball-spring-2025'
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    max_participants = db.Column(db.Integer, nullable=False)
    event_date = db.Column(db.DateTime, nullable=False)
    signup_start = db.Column(db.DateTime, nullable=False)
    signup_end = db.Column(db.DateTime, nullable=False)
    price = db.Column(db.Integer, nullable=False)  # Amount in cents
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='draft')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with payments
    payments = db.relationship('Payment', backref='social_event', lazy=True)

    def __repr__(self):
        return f'<SocialEvent {self.slug}>'

    @property
    def formatted_date(self):
        """Returns formatted date for display"""
        return self.event_date.strftime('%B %-d, %Y')

    @property
    def formatted_time(self):
        """Returns formatted time for display"""
        return self.event_date.strftime('%-I:%M %p')


class SlackUser(db.Model):
    __tablename__ = 'slack_users'

    id = db.Column(db.Integer, primary_key=True)
    slack_uid = db.Column(db.String(255), unique=True, nullable=False)
    display_name = db.Column(db.String(255))
    full_name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    title = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    status = db.Column(db.Text)
    timezone = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = db.relationship('User', backref='slack_user', uselist=False)

    def __repr__(self):
        return f'<SlackUser {self.slack_uid}>'

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    slack_user_id = db.Column(db.Integer, db.ForeignKey('slack_users.id'), unique=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    status = db.Column(db.String(50), nullable=False, default=UserStatus.PENDING)
    seasons_since_active = db.Column(db.Integer, default=0, nullable=False)  # 0=active now, 1=skipped 1 season, 2+=long-term alumni
    notes = db.Column(db.Text)
    user_metadata = db.Column(JSON)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    date_of_birth = db.Column(db.Date)
    pronouns = db.Column(db.String(50))
    preferred_technique = db.Column(db.String(50))
    tshirt_size = db.Column(db.String(10))
    ski_experience = db.Column(db.String(20))
    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_relation = db.Column(db.String(50))
    emergency_contact_phone = db.Column(db.String(20))
    emergency_contact_email = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tags = db.relationship('Tag', secondary='user_tags', backref='users')
    status_changes = db.relationship('StatusChange', backref='user')
    payments = db.relationship('Payment', backref='user', lazy=True)
    user_seasons = db.relationship('UserSeason', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.id} {self.email}>'

    @classmethod
    def get_by_email(cls, email):
        """Find a user by email address. Returns None if not found."""
        return cls.query.filter_by(email=email).one_or_none()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_returning(self):
        # A user is returning if they have been ACTIVE in any past season
        # This includes users who were "new" but made it through the lottery
        # Excludes PENDING_LOTTERY and DROPPED users who never made it through
        return any(us.status == UserSeasonStatus.ACTIVE for us in self.user_seasons)

    @property
    def derived_status(self):
        """Compute status from UserSeason history. Source of truth."""
        current_season = Season.get_current()
        if not current_season:
            return self.status  # fallback to cached

        user_season = UserSeason.get_for_user_season(self.id, current_season.id)
        if not user_season:
            return UserStatus.ALUMNI  # Not registered in current season

        status_map = {
            UserSeasonStatus.ACTIVE: UserStatus.ACTIVE,
            UserSeasonStatus.PENDING_LOTTERY: UserStatus.PENDING,
            UserSeasonStatus.DROPPED_LOTTERY: UserStatus.DROPPED,
            UserSeasonStatus.DROPPED_VOLUNTARY: UserStatus.DROPPED,
            UserSeasonStatus.DROPPED_CAUSE: UserStatus.DROPPED,
        }
        return status_map.get(user_season.status, UserStatus.PENDING)

    def sync_status(self):
        """Update cached status and counter from computed values.

        Called when activating a new season to update all users' statuses.
        """
        new_status = self.derived_status
        if new_status == UserStatus.ACTIVE:
            self.seasons_since_active = 0
        elif self.status == UserStatus.ACTIVE and new_status == UserStatus.ALUMNI:
            # Was active, now alumni - start counter at 1
            self.seasons_since_active = 1
        elif self.status == UserStatus.ALUMNI and new_status == UserStatus.ALUMNI:
            # Still alumni - increment counter (cap at 2 for long-term alumni)
            if self.seasons_since_active < 2:
                self.seasons_since_active += 1
        elif new_status == UserStatus.ALUMNI:
            # Transitioning from PENDING/DROPPED to ALUMNI
            self.seasons_since_active = 2  # Treat as long-term
        self.status = new_status

    def get_slack_tier(self):
        """Determine Slack membership tier based on status and activity."""
        if self.status == UserStatus.ACTIVE:
            return 'full_member'
        elif self.status == UserStatus.ALUMNI:
            if self.seasons_since_active == 1:
                return 'multi_channel_guest'
            else:  # 2+ seasons
                return 'single_channel_guest'
        # PENDING and DROPPED = no Slack automation
        return None

    __table_args__ = (
        db.CheckConstraint(
            status.in_([UserStatus.PENDING, UserStatus.ACTIVE, UserStatus.ALUMNI, UserStatus.DROPPED]),
            name='check_user_status_valid'
        ),
    )

class Season(db.Model):
    __tablename__ = 'seasons'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    season_type = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    price_cents = db.Column(db.Integer, nullable=True)
    returning_start = db.Column(db.DateTime, nullable=True)
    returning_end = db.Column(db.DateTime, nullable=True)
    new_start = db.Column(db.DateTime, nullable=True)
    new_end = db.Column(db.DateTime, nullable=True)
    registration_limit = db.Column(db.Integer, nullable=True)  # Max allowed registrations for this season
    description = db.Column(db.Text, nullable=True)  # Season description
    is_current = db.Column(db.Boolean, default=False, nullable=False)  # Only one season should be current
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Season {self.id} {self.name}>'

    @classmethod
    def get_current(cls):
        """Get the current season. Returns None if no season is marked current."""
        return cls.query.filter_by(is_current=True).first()

    def is_open_for(self, member_type: str, when: datetime = None) -> bool:
        """
        Returns True if registration is open for the given member_type ('new' or 'returning') at the given time.
        If 'when' is not provided, uses current UTC time.
        """
        if when is None:
            when = datetime.utcnow()
        if member_type == 'new':
            if self.new_start and self.new_end:
                return self.new_start <= when <= self.new_end
        elif member_type == 'returning':
            if self.returning_start and self.returning_end:
                return self.returning_start <= when <= self.returning_end
        return False

    def is_returning_open(self, when: datetime = None) -> bool:
        """Check if returning member registration is open at the given time."""
        return self.is_open_for('returning', when)

    def is_new_open(self, when: datetime = None) -> bool:
        """Check if new member registration is open at the given time."""
        return self.is_open_for('new', when)

    def is_any_registration_open(self, when: datetime = None) -> bool:
        """Check if any registration (new or returning) is open at the given time."""
        return self.is_returning_open(when) or self.is_new_open(when)


class UserSeason(db.Model):
    __tablename__ = 'user_seasons'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), primary_key=True)
    registration_type = db.Column(db.String(50), nullable=False)
    registration_date = db.Column(db.Date, nullable=False)
    payment_date = db.Column(db.Date)
    status = db.Column(db.String(50), nullable=False, default=UserSeasonStatus.PENDING_LOTTERY)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<UserSeason user={self.user_id} season={self.season_id} status={self.status}>'

    @classmethod
    def get_for_user_season(cls, user_id, season_id):
        """Find a UserSeason by user_id and season_id. Returns None if not found."""
        return cls.query.filter_by(user_id=user_id, season_id=season_id).one_or_none()

    __table_args__ = (
        db.CheckConstraint(
            status.in_([
                UserSeasonStatus.PENDING_LOTTERY,
                UserSeasonStatus.ACTIVE,
                UserSeasonStatus.DROPPED_LOTTERY,
                UserSeasonStatus.DROPPED_VOLUNTARY,
                UserSeasonStatus.DROPPED_CAUSE
            ]),
            name='check_userseason_status_valid'
        ),
    )


class Tag(db.Model):
    """Predefined tags for user roles/designations (board member, coach, lead, etc.)"""
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # e.g., 'BOARD_MEMBER'
    display_name = db.Column(db.String(100), nullable=False)      # e.g., 'Board Member'
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Tag {self.name}>'


class UserTag(db.Model):
    """Junction table linking users to tags"""
    __tablename__ = 'user_tags'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<UserTag user={self.user_id} tag={self.tag_id}>'


class StatusChange(db.Model):
    __tablename__ = 'status_changes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    previous_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50))
    reason = db.Column(db.Text)
    changed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<StatusChange {self.id} {self.previous_status}->{self.new_status}>'