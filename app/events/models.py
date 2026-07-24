"""Database models for generic event registrations."""

from datetime import datetime

from app.models import db


class EventStatus:
    """Event publication and registration states."""

    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"

    ALL = [DRAFT, ACTIVE, CLOSED]


class RegistrationStatus:
    """Event registration payment states."""

    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

    ALL = [PENDING_PAYMENT, CONFIRMED, CANCELLED, REFUNDED]


class Audience:
    """Audiences that can access an event."""

    INTERNAL = "internal"
    EXTERNAL = "external"
    BOTH = "both"

    ALL = [INTERNAL, EXTERNAL, BOTH]


class Event(db.Model):
    """A public or club event with its own registration flow."""

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(
        db.String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(255), nullable=False)
    event_date = db.Column(db.DateTime, nullable=False)
    signup_start = db.Column(db.DateTime, nullable=False)
    signup_end = db.Column(db.DateTime, nullable=False)
    capacity = db.Column(db.Integer)
    status = db.Column(
        db.String(50),
        nullable=False,
        default=EventStatus.DRAFT,
    )
    audience = db.Column(
        db.String(50),
        nullable=False,
        default=Audience.BOTH,
    )
    details_url = db.Column(db.String(500))
    discount_code = db.Column(db.String(255))
    custom_questions = db.Column(db.JSON, nullable=False, default=list)
    template_key = db.Column(db.String(100))
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    price_options = db.relationship(
        "EventPriceOption",
        backref="event",
        order_by="EventPriceOption.sort_order",
        cascade="all, delete-orphan",
    )
    registrations = db.relationship(
        "EventRegistration",
        backref="event",
    )

    @property
    def confirmed_count(self):
        """Return the number of confirmed registrations."""
        return sum(
            registration.status == RegistrationStatus.CONFIRMED
            for registration in self.registrations
        )

    def __repr__(self):
        return f"<Event {self.slug}>"


class EventPriceOption(db.Model):
    """A purchasable registration option for an event."""

    __tablename__ = "event_price_options"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer,
        db.ForeignKey("events.id"),
        nullable=False,
    )
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(500))
    price_cents = db.Column(db.Integer, nullable=False)
    member_price_cents = db.Column(db.Integer)
    participant_roles = db.Column(
        db.JSON,
        nullable=False,
        default=lambda: ["Participant"],
    )
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)

    @property
    def participant_count(self):
        """Return the number of participants this option registers."""
        return len(self.participant_roles or ["Participant"])

    def __repr__(self):
        return f"<EventPriceOption {self.name}>"


class EventRegistration(db.Model):
    """A single event checkout, which may include multiple participants."""

    __tablename__ = "event_registrations"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer,
        db.ForeignKey("events.id"),
        nullable=False,
    )
    price_option_id = db.Column(
        db.Integer,
        db.ForeignKey("event_price_options.id"),
        nullable=False,
    )
    contact_email = db.Column(db.String(255), nullable=False)
    contact_phone = db.Column(db.String(50), nullable=False)
    team_name = db.Column(db.String(255))
    emergency_contact_name = db.Column(db.String(255), nullable=False)
    emergency_contact_phone = db.Column(db.String(50), nullable=False)
    answers = db.Column(db.JSON, nullable=False, default=dict)
    amount_cents = db.Column(db.Integer, nullable=False)
    discount_applied = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    status = db.Column(
        db.String(50),
        nullable=False,
        default=RegistrationStatus.PENDING_PAYMENT,
    )
    payment_intent_id = db.Column(db.String(255))
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    price_option = db.relationship(
        "EventPriceOption",
        backref="registrations",
    )
    participants = db.relationship(
        "EventParticipant",
        backref="registration",
        order_by="EventParticipant.position",
        cascade="all, delete-orphan",
    )
    payments = db.relationship(
        "Payment",
        backref="event_registration",
        lazy=True,
    )

    def __repr__(self):
        return f"<EventRegistration {self.id}>"


class EventParticipant(db.Model):
    """An individual included in an event registration."""

    __tablename__ = "event_participants"

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(
        db.Integer,
        db.ForeignKey("event_registrations.id"),
        nullable=False,
    )
    position = db.Column(db.Integer, nullable=False)
    role_label = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<EventParticipant {self.name}>"
