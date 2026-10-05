from datetime import datetime

from app.models import db


class InterestSignup(db.Model):
    """Someone who wants to hear when registration opens.

    Not a member. Rows here never create or update a User; the admin page
    only reads User to label rows that match an existing account.
    """
    __tablename__ = 'interest_signups'
    __table_args__ = (
        db.UniqueConstraint('email', name='uq_interest_signups_email'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone_e164 = db.Column(db.String(20))
    # Set whenever a phone is saved: the consent line sits under the field.
    sms_consent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
