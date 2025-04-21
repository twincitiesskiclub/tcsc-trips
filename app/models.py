from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.dialects.sqlite import JSON  # Since you're using SQLite
from sqlalchemy.sql import func

db = SQLAlchemy()

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    payment_intent_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # Amount in cents
    status = db.Column(db.String(50), nullable=False)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def __repr__(self):
        return f'<Payment {self.payment_intent_id}>'

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

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    slack_user_id = db.Column(db.Integer, db.ForeignKey('slack_users.id'), unique=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending')
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
    
    # Relationship with seasons through UserSeason
    seasons = db.relationship('Season', secondary='user_seasons', lazy='dynamic')

    # Relationships
    roles = db.relationship('Role', secondary='user_roles', backref='users')
    committees = db.relationship('Committee', secondary='user_committees', backref='users')
    status_changes = db.relationship('StatusChange', backref='user')
    payments = db.relationship('Payment', backref='user', lazy=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Season(db.Model):
    __tablename__ = 'seasons'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    registration_open_date = db.Column(db.Date)
    registration_close_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserSeason(db.Model):
    __tablename__ = 'user_seasons'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), primary_key=True)
    registration_type = db.Column(db.String(50), nullable=False)
    registration_date = db.Column(db.Date, nullable=False)
    payment_date = db.Column(db.Date)
    status = db.Column(db.String(50), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)

class UserRole(db.Model):
    __tablename__ = 'user_roles'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Committee(db.Model):
    __tablename__ = 'committees'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)

class UserCommittee(db.Model):
    __tablename__ = 'user_committees'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    committee_id = db.Column(db.Integer, db.ForeignKey('committees.id'), primary_key=True)
    role = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class StatusChange(db.Model):
    __tablename__ = 'status_changes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    previous_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50))
    reason = db.Column(db.Text)
    changed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)