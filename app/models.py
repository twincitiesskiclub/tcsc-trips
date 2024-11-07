from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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

    def __repr__(self):
        return f'<Payment {self.payment_intent_id}>'

class Trip(db.Model):
    __tablename__ = 'trips'
    
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False)  # e.g., 'training-trip'
    name = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
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