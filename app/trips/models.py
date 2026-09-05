from datetime import datetime

from app.models import db


class TripRegistrationStatus:
    PENDING_PAYMENT = "pending_payment"  # row created, card not yet authorized
    PENDING = "pending"                  # hold placed, awaiting roster confirm
    CONFIRMED = "confirmed"              # payment captured
    CANCELLED = "cancelled"              # hold released / registration void
    ALL = [PENDING_PAYMENT, PENDING, CONFIRMED, CANCELLED]


class TripSeries(db.Model):
    __tablename__ = "trip_series"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    slack_channel_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    editions = db.relationship(
        "Trip", backref="series", lazy=True,
        order_by="Trip.start_date.desc()",
    )

    def current_edition(self):
        """The edition the public URL should show.

        Preference order: soonest upcoming non-draft edition, else the most
        recently started non-draft edition, else the newest edition of any
        status (so a fresh draft-only series still resolves for admins).
        """
        now = datetime.utcnow()
        published = [e for e in self.editions if e.status != "draft"]
        upcoming = [e for e in published if e.start_date >= now]
        if upcoming:
            return min(upcoming, key=lambda e: e.start_date)
        if published:
            return max(published, key=lambda e: e.start_date)
        if self.editions:
            return max(self.editions, key=lambda e: e.start_date)
        return None

    def __repr__(self):
        return f"<TripSeries {self.slug}>"


class TripRegistration(db.Model):
    __tablename__ = "trip_registrations"
    __table_args__ = (
        db.UniqueConstraint("trip_id", "user_id", name="uq_trip_registration_member"),
    )

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(
        db.Integer, db.ForeignKey("trips.id"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    status = db.Column(
        db.String(50), nullable=False,
        default=TripRegistrationStatus.PENDING_PAYMENT,
    )
    answers = db.Column(db.JSON, nullable=False, default=dict)
    price_tier = db.Column(db.String(10), nullable=False)  # 'low' | 'high'
    amount_cents = db.Column(db.Integer, nullable=False)
    payment_intent_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    trip = db.relationship(
        "Trip", backref=db.backref("registrations", lazy=True)
    )
    user = db.relationship(
        "User", backref=db.backref("trip_registrations", lazy=True)
    )

    def __repr__(self):
        return f"<TripRegistration {self.id} trip={self.trip_id} user={self.user_id}>"


class TripProfile(db.Model):
    """Semi-stable per-member trip facts. Real columns because carpool and
    logistics queries filter on them. Updated (upserted) on every
    registration submit for enabled built-ins in Trip.custom_questions only.
    Disabled or absent built-ins leave previous values untouched; new profiles
    retain nulls (or the empty dietary defaults). Never pre-filled into forms
    until the auth project.
    """

    __tablename__ = "trip_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False
    )
    can_drive = db.Column(db.Boolean)
    seat_capacity = db.Column(db.Integer)
    bike_capacity = db.Column(db.Integer)
    hitch_size = db.Column(db.String(10))       # '', '1.25', '2'
    region_code = db.Column(db.String(10))
    dietary_restrictions = db.Column(db.JSON, nullable=False, default=list)
    dietary_other = db.Column(db.String(255), nullable=False, default="")
    has_tent = db.Column(db.Boolean)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    user = db.relationship(
        "User", backref=db.backref("trip_profile", uselist=False)
    )

    def __repr__(self):
        return f"<TripProfile user={self.user_id}>"
