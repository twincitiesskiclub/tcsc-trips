"""Public event registration route tests."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.events.models import (
    Event,
    EventPriceOption,
    EventRegistration,
    EventStatus,
    RegistrationStatus,
)


@pytest.fixture
def public_event(db_session):
    now = datetime.utcnow()
    event = Event(
        slug="dry-tri-2026",
        name="Dry Tri 2026",
        description="Roll, ride, and run through Carver Park.",
        location="Carver Park Reserve",
        event_date=now + timedelta(days=30),
        signup_start=now - timedelta(days=1),
        signup_end=now + timedelta(days=1),
        capacity=100,
        status=EventStatus.ACTIVE,
        details_url="https://twincitiesskiclub.org/dry-tri",
        discount_code="TCSC MEMBER",
        custom_questions=[
            {
                "key": "course",
                "label": "Course",
                "type": "choice",
                "options": ["Long", "Short"],
                "required": True,
                "help_text": "Choose the course you plan to race.",
            },
            {
                "key": "club",
                "label": "Club",
                "type": "text",
                "options": [],
                "required": False,
                "help_text": "",
            },
        ],
    )
    individual = EventPriceOption(
        name="Individual",
        description="Complete all three legs yourself.",
        price_cents=5500,
        member_price_cents=4500,
        participant_roles=["Participant"],
        sort_order=0,
    )
    team = EventPriceOption(
        name="Team of 3",
        description="One registration covers all three teammates.",
        price_cents=10500,
        member_price_cents=9000,
        participant_roles=[
            "Rollerskier",
            "Mountain Biker",
            "Trail Runner",
        ],
        sort_order=1,
    )
    free = EventPriceOption(
        name="Volunteer",
        description="Help on course.",
        price_cents=0,
        participant_roles=["Volunteer"],
        sort_order=2,
    )
    event.price_options.extend([individual, team, free])
    db_session.session.add(event)
    db_session.session.commit()
    return event, individual, team, free


def _participant(position):
    return {
        "name": f"Participant {position}",
        "date_of_birth": f"199{position}-01-0{position}",
        "email": f"participant{position}@example.com",
        "phone": f"555-010{position}",
        "emergency_contact_name": f"Emergency {position}",
        "emergency_contact_phone": f"555-099{position}",
    }


def _payload(option, participant_count=None):
    count = (
        option.participant_count
        if participant_count is None
        else participant_count
    )
    return {
        "price_option_id": option.id,
        "team_name": "Nordic Rockets" if option.participant_count > 1 else "",
        "participants": [
            _participant(position) for position in range(1, count + 1)
        ],
        "answers": {"course": "Long", "club": "TCSC"},
        "discount_code": "",
    }


def _intent(intent_id="pi_event_test", amount=5500):
    return SimpleNamespace(
        id=intent_id,
        client_secret=f"cs_{intent_id}",
        amount=amount,
        status="requires_payment_method",
    )


def test_get_active_event_shows_event_and_active_price_options(
    client,
    public_event,
):
    event, _individual, _team, _free = public_event

    response = client.get(f"/events/{event.slug}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Dry Tri 2026" in page
    assert "Carver Park Reserve" in page
    assert "Individual" in page
    assert "Team of 3" in page
    assert "Volunteer" in page
    assert event.details_url in page


def test_get_draft_event_is_404_for_anonymous_and_preview_for_admin(
    client,
    db_session,
    public_event,
):
    event, _individual, _team, _free = public_event
    event.status = EventStatus.DRAFT
    db_session.session.commit()

    assert client.get(f"/events/{event.slug}").status_code == 404

    with client.session_transaction() as session:
        session["user"] = {"email": "admin@twincitiesskiclub.org"}

    response = client.get(f"/events/{event.slug}")
    assert response.status_code == 200
    assert "DRAFT — admin preview" in response.get_data(as_text=True)


@pytest.mark.parametrize("status", [EventStatus.CLOSED])
def test_get_closed_or_unknown_event_is_404(
    client,
    db_session,
    public_event,
    status,
):
    event, _individual, _team, _free = public_event
    event.status = status
    db_session.session.commit()

    assert client.get(f"/events/{event.slug}").status_code == 404
    assert client.get("/events/not-a-real-event").status_code == 404


def test_get_event_expires_stale_pending_registration(
    client,
    db_session,
    public_event,
):
    event, individual, _team, _free = public_event
    registration = EventRegistration(
        event_id=event.id,
        price_option_id=individual.id,
        contact_email="stale@example.com",
        contact_phone="555-0100",
        answers={},
        amount_cents=individual.price_cents,
        status=RegistrationStatus.PENDING_PAYMENT,
        created_at=datetime.utcnow() - timedelta(hours=25),
    )
    db_session.session.add(registration)
    db_session.session.commit()
    registration_id = registration.id

    assert client.get(f"/events/{event.slug}").status_code == 200

    db_session.session.expire_all()
    saved = db_session.session.get(EventRegistration, registration_id)
    assert saved.status == RegistrationStatus.CANCELLED


@patch("app.routes.events.stripe.PaymentIntent.create")
def test_post_valid_individual_creates_pending_registration_and_intent(
    create_intent,
    client,
    db_session,
    public_event,
):
    event, individual, _team, _free = public_event
    create_intent.return_value = _intent()

    response = client.post(
        f"/events/{event.slug}/register",
        json=_payload(individual),
        headers={"Idempotency-Key": "event-attempt-123"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["clientSecret"] == "cs_pi_event_test"
    assert body["amountCents"] == 5500
    registration = db_session.session.get(
        EventRegistration,
        body["registrationId"],
    )
    assert registration.status == RegistrationStatus.PENDING_PAYMENT
    assert registration.payment_intent_id == "pi_event_test"

    kwargs = create_intent.call_args.kwargs
    assert kwargs["amount"] == 5500
    assert kwargs["currency"] == "usd"
    assert kwargs["capture_method"] == "automatic"
    assert kwargs["receipt_email"] == "participant1@example.com"
    assert kwargs["statement_descriptor"].startswith("TCSC_EVENT_")
    assert kwargs["description"] == "TCSC Event - Dry Tri 2026"
    assert kwargs["metadata"] == {
        "payment_type": "event",
        "event_id": str(event.id),
        "registration_id": str(registration.id),
        "email": "participant1@example.com",
        "name": "Participant 1",
    }
    assert kwargs["idempotency_key"] == "event-attempt-123"


@patch("app.routes.events.stripe.PaymentIntent.create")
def test_post_team_missing_third_participant_returns_field_error(
    create_intent,
    client,
    public_event,
):
    event, _individual, team, _free = public_event

    response = client.post(
        f"/events/{event.slug}/register",
        json=_payload(team, participant_count=2),
    )

    assert response.status_code == 400
    assert "participants" in response.get_json()["error"]
    create_intent.assert_not_called()


@patch("app.routes.events.stripe.PaymentIntent.create")
def test_post_discount_uses_server_computed_member_price(
    create_intent,
    client,
    public_event,
):
    event, individual, _team, _free = public_event
    create_intent.return_value = _intent(amount=4500)
    payload = _payload(individual)
    payload["discount_code"] = " tcsc member "

    response = client.post(
        f"/events/{event.slug}/register",
        json=payload,
    )

    assert response.status_code == 200
    assert response.get_json()["amountCents"] == 4500
    assert create_intent.call_args.kwargs["amount"] == 4500


@patch("app.routes.events.stripe.PaymentIntent.create")
def test_zero_price_registration_confirms_without_stripe(
    create_intent,
    client,
    db_session,
    public_event,
):
    event, _individual, _team, free = public_event

    response = client.post(
        f"/events/{event.slug}/register",
        json=_payload(free),
    )

    assert response.status_code == 200
    assert response.get_json()["free"] is True
    registration = db_session.session.get(
        EventRegistration,
        response.get_json()["registrationId"],
    )
    assert registration.status == RegistrationStatus.CONFIRMED
    assert registration.payment_intent_id is None
    create_intent.assert_not_called()


@patch("app.routes.events.stripe.PaymentIntent.create")
def test_stripe_failure_leaves_registration_pending(
    create_intent,
    client,
    db_session,
    public_event,
):
    event, individual, _team, _free = public_event
    create_intent.side_effect = RuntimeError("Stripe is unavailable")

    response = client.post(
        f"/events/{event.slug}/register",
        json=_payload(individual),
    )

    assert response.status_code == 500
    assert response.get_json() == {"error": "Stripe is unavailable"}
    registration = EventRegistration.query.filter_by(event_id=event.id).one()
    assert registration.status == RegistrationStatus.PENDING_PAYMENT
    assert registration.payment_intent_id is None


@patch("app.routes.events.stripe.PaymentIntent.create")
def test_admin_can_register_for_draft_event(
    create_intent,
    client,
    db_session,
    public_event,
):
    event, individual, _team, _free = public_event
    event.status = EventStatus.DRAFT
    db_session.session.commit()
    create_intent.return_value = _intent()

    anonymous = client.post(
        f"/events/{event.slug}/register",
        json=_payload(individual),
    )
    assert anonymous.status_code == 404

    with client.session_transaction() as session:
        session["user"] = {"email": "admin@twincitiesskiclub.org"}

    preview = client.post(
        f"/events/{event.slug}/register",
        json=_payload(individual),
    )
    assert preview.status_code == 200


@pytest.mark.parametrize("path", ["/tri", "/dryland-triathlon"])
def test_dry_tri_legacy_urls_redirect_to_generic_event_page(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert response.headers["Location"] == "/events/dry-tri-2026"


def test_get_event_page_drops_the_registration_contact_section(
    client,
    public_event,
):
    event, _individual, _team, _free = public_event

    page = client.get(f"/events/{event.slug}").get_data(as_text=True)

    assert "Registration contact" not in page
    assert 'id="contact-email"' not in page
    assert 'id="contact-phone"' not in page
    # The standalone emergency contact section is gone too; the fields now
    # render client-side inside each participant card. Team name stays.
    assert 'id="emergency-contact-name"' not in page
    assert "Emergency contact" not in page
    assert 'id="team-name"' in page


def test_get_event_page_puts_team_name_with_participant_details(
    client,
    public_event,
):
    event, _individual, _team, _free = public_event

    page = client.get(f"/events/{event.slug}").get_data(as_text=True)

    participants_heading = page.index("Participant details")
    team_name_field = page.index('id="team-name"')

    assert participants_heading < team_name_field


def test_get_event_page_preserves_description_line_breaks(
    client,
    db_session,
    public_event,
):
    event, _individual, _team, _free = public_event
    event.description = "Roll. Ride. Run.\n\n- 7:30 AM Packet pickup"
    db_session.session.commit()

    page = client.get(f"/events/{event.slug}").get_data(as_text=True)

    assert "white-space: pre-line" in page
    assert "Roll. Ride. Run.\n\n- 7:30 AM Packet pickup" in page


def test_get_event_page_publishes_each_question_scope(
    client,
    db_session,
    public_event,
):
    event, _individual, _team, _free = public_event
    event.custom_questions = [
        {
            "key": "course",
            "label": "Course",
            "type": "choice",
            "options": ["Long", "Short"],
            "required": True,
            "price_options": ["Individual", "Team of 3"],
        },
        {
            "key": "club",
            "label": "Club",
            "type": "text",
            "required": False,
        },
    ]
    db_session.session.commit()

    page = client.get(f"/events/{event.slug}").get_data(as_text=True)

    # tojson output is markup-safe, so the attribute is single-quoted.
    assert 'data-question-scope=\'["Individual", "Team of 3"]\'' in page
    assert "data-question-scope='[]'" in page
    # Ids are index-based so a key repeated across scopes stays unique.
    assert 'id="question-0"' in page
    assert 'id="question-1"' in page
    # The section wrapper is what the client hides when nothing is in scope.
    assert 'id="event-questions"' in page


def test_post_ignores_a_client_supplied_registration_contact(
    db_session,
    client,
    public_event,
):
    event, individual, _team, _free = public_event
    payload = _payload(individual)
    payload["contact_email"] = "spoofed@example.com"
    payload["contact_phone"] = "555-9999"

    with patch("app.routes.events.stripe.PaymentIntent.create") as create:
        create.return_value = _intent()
        response = client.post(
            f"/events/{event.slug}/register",
            json=payload,
        )

    assert response.status_code == 200
    registration = db_session.session.get(
        EventRegistration,
        response.get_json()["registrationId"],
    )
    assert registration.contact_email == "participant1@example.com"
    assert registration.contact_phone == "555-0101"


def test_get_event_page_withholds_member_pricing(client, public_event):
    event, _individual, _team, _free = public_event

    page = client.get(f"/events/{event.slug}").get_data(as_text=True)

    # Neither the rendered hint nor the JSON blob may carry the member rate.
    assert "memberPriceCents" not in page
    assert "$45.00" not in page
    assert "$90.00" not in page
    # The public prices still render, alongside the control that reveals the
    # member rate.
    assert "$55.00" in page
    assert "$105.00" in page
    assert 'id="discount-apply"' in page


def test_discount_check_returns_member_prices_for_a_valid_code(
    client,
    public_event,
):
    event, individual, team, free = public_event

    response = client.post(
        f"/events/{event.slug}/discount",
        json={"code": " tcsc member "},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["valid"] is True
    prices = {option["id"]: option["priceCents"] for option in body["options"]}
    assert prices[individual.id] == 4500
    assert prices[team.id] == 9000
    # An option with no member rate stays at its public price.
    assert prices[free.id] == 0


def test_discount_check_rejects_an_unknown_code(client, public_event):
    event, _individual, _team, _free = public_event

    response = client.post(
        f"/events/{event.slug}/discount",
        json={"code": "not-the-code"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"valid": False}


def test_discount_check_rejects_everything_when_no_code_is_configured(
    client,
    db_session,
    public_event,
):
    event, _individual, _team, _free = public_event
    event.discount_code = None
    db_session.session.commit()

    for code in ("", "TCSC MEMBER"):
        response = client.post(
            f"/events/{event.slug}/discount",
            json={"code": code},
        )
        assert response.get_json() == {"valid": False}


def test_discount_check_throttles_repeated_guessing(client, public_event):
    from app.routes.events import DISCOUNT_ATTEMPT_LIMIT, _discount_attempts

    event, _individual, _team, _free = public_event
    _discount_attempts.clear()

    for _ in range(DISCOUNT_ATTEMPT_LIMIT):
        client.post(f"/events/{event.slug}/discount", json={"code": "guess"})

    # A correct code past the limit is refused along with the wrong ones.
    response = client.post(
        f"/events/{event.slug}/discount",
        json={"code": "TCSC MEMBER"},
    )
    assert response.get_json() == {"valid": False}
    _discount_attempts.clear()


def test_discount_check_on_draft_is_404_for_anonymous_and_open_for_admin(
    client,
    db_session,
    public_event,
):
    event, _individual, _team, _free = public_event
    event.status = EventStatus.DRAFT
    db_session.session.commit()

    anonymous = client.post(
        f"/events/{event.slug}/discount",
        json={"code": "TCSC MEMBER"},
    )
    assert anonymous.status_code == 404

    with client.session_transaction() as session:
        session["user"] = {"email": "admin@twincitiesskiclub.org"}

    response = client.post(
        f"/events/{event.slug}/discount",
        json={"code": "TCSC MEMBER"},
    )
    assert response.status_code == 200
    assert response.get_json()["valid"] is True
