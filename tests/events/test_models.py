from datetime import date, datetime

from app.constants import PaymentType
from app.events.models import (
    Audience,
    Event,
    EventParticipant,
    EventPriceOption,
    EventRegistration,
    EventStatus,
    RegistrationStatus,
)
from app.models import Payment


def _event(slug):
    return Event(
        slug=slug,
        name="Dry Tri",
        location="Carver Park",
        event_date=datetime(2026, 10, 24, 9, 0),
        signup_start=datetime(2026, 8, 1),
        signup_end=datetime(2026, 10, 22),
    )


def test_event_with_options_and_registration(db_session):
    event = Event(
        slug="dry-tri-2026",
        name="Dry Tri",
        location="Carver Park",
        event_date=datetime(2026, 10, 24, 9, 0),
        signup_start=datetime(2026, 8, 1),
        signup_end=datetime(2026, 10, 22),
        custom_questions=[
            {
                "key": "course",
                "label": "Course?",
                "type": "choice",
                "options": ["Long", "Short"],
                "required": True,
            }
        ],
    )
    opt = EventPriceOption(
        name="Team of 3",
        price_cents=10500,
        participant_roles=[
            "Rollerskier",
            "Mountain Biker",
            "Trail Runner",
        ],
    )
    event.price_options.append(opt)
    db_session.session.add(event)
    db_session.session.commit()

    assert opt.participant_count == 3
    assert event.price_options == [opt]

    reg = EventRegistration(
        event_id=event.id,
        price_option_id=opt.id,
        contact_email="cap@x.com",
        contact_phone="555",
        emergency_contact_name="EC",
        emergency_contact_phone="911",
        amount_cents=10500,
        status="pending_payment",
        answers={"course": "Long"},
    )
    participant = EventParticipant(
        position=1,
        role_label="Rollerskier",
        name="A B",
        date_of_birth=date(1990, 1, 1),
        email="a@x.com",
        phone="1",
    )
    reg.participants.append(participant)
    db_session.session.add(reg)
    db_session.session.commit()

    assert reg.participants == [participant]
    assert event.confirmed_count == 0

    reg.status = "confirmed"
    db_session.session.commit()

    assert event.confirmed_count == 1


def test_payment_links_to_event_registration(db_session):
    event = _event("payment-link-test")
    option = EventPriceOption(
        name="Individual",
        price_cents=5500,
        participant_roles=["Participant"],
    )
    event.price_options.append(option)
    db_session.session.add(event)
    db_session.session.flush()

    registration = EventRegistration(
        event_id=event.id,
        price_option_id=option.id,
        contact_email="skier@example.com",
        contact_phone="555-0100",
        emergency_contact_name="Emergency Contact",
        emergency_contact_phone="555-0199",
        amount_cents=5500,
        status=RegistrationStatus.CONFIRMED,
    )
    db_session.session.add(registration)
    db_session.session.flush()

    payment = Payment(
        payment_intent_id="pi_event_model_test",
        email=registration.contact_email,
        name="Event Skier",
        amount=registration.amount_cents,
        status="succeeded",
        payment_type=PaymentType.EVENT,
        event_registration_id=registration.id,
    )
    db_session.session.add(payment)
    db_session.session.commit()
    payment_id = payment.id
    registration_id = registration.id
    db_session.session.expire_all()

    saved_payment = db_session.session.get(Payment, payment_id)
    saved_registration = db_session.session.get(
        EventRegistration, registration_id
    )

    assert PaymentType.EVENT == "event"
    assert PaymentType.EVENT in PaymentType.ALL
    assert saved_payment.event_registration_id == registration_id
    assert saved_payment.event_registration == saved_registration
    assert saved_registration.payments == [saved_payment]


def test_event_defaults_and_string_constants(db_session):
    event = _event("dry-tri-2026")
    db_session.session.add(event)
    db_session.session.commit()

    assert event.status == EventStatus.DRAFT == "draft"
    assert event.audience == Audience.BOTH == "both"
    assert event.custom_questions == []
    assert EventStatus.ALL == ["draft", "active", "closed"]
    assert RegistrationStatus.ALL == [
        "pending_payment",
        "confirmed",
        "cancelled",
        "refunded",
    ]
    assert Audience.ALL == ["internal", "external", "both"]


def test_event_tables_have_no_user_fk():
    from app.events import models as m

    for table in (
        m.Event.__table__,
        m.EventRegistration.__table__,
        m.EventParticipant.__table__,
        m.EventPriceOption.__table__,
    ):
        for fk in table.foreign_keys:
            assert "users" not in fk.target_fullname
