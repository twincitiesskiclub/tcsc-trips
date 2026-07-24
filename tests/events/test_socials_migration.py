"""Post-migration integration tests for folded social events."""

from datetime import date, datetime, timedelta

from app.events.models import (
    Event,
    EventParticipant,
    EventPriceOption,
    EventRegistration,
)


def _event(slug, name, *, audience, status="active", signup_end=None):
    now = datetime.utcnow()
    event = Event(
        slug=slug,
        name=name,
        description=f"Details for {name}.",
        location="The Trailhead",
        event_date=now + timedelta(days=30),
        signup_start=now - timedelta(days=1),
        signup_end=signup_end or now + timedelta(days=20),
        capacity=30,
        status=status,
        audience=audience,
        custom_questions=[],
        template_key="social",
    )
    event.price_options.append(
        EventPriceOption(
            name="Registration",
            price_cents=2500,
            participant_roles=["Participant"],
            sort_order=0,
            active=True,
        )
    )
    return event


def test_legacy_social_url_redirects_to_event(client):
    response = client.get("/social/migrated-social")

    assert response.status_code == 302
    assert response.headers["Location"] == "/events/migrated-social"


def test_homepage_only_lists_open_public_events(client, db_session):
    now = datetime.utcnow()
    db_session.session.add_all(
        [
            _event(
                "migration-home-external",
                "Visible External Event",
                audience="external",
            ),
            _event(
                "migration-home-both",
                "Visible Both Event",
                audience="both",
            ),
            _event(
                "migration-home-internal",
                "Hidden Internal Event",
                audience="internal",
            ),
            _event(
                "migration-home-draft",
                "Hidden Draft Event",
                audience="external",
                status="draft",
            ),
            _event(
                "migration-home-expired",
                "Hidden Expired Event",
                audience="both",
                signup_end=now - timedelta(minutes=1),
            ),
        ]
    )
    db_session.session.commit()

    response = client.get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Visible External Event" in page
    assert "Visible Both Event" in page
    assert "/events/migration-home-external" in page
    assert "/events/migration-home-both" in page
    assert "Hidden Internal Event" not in page
    assert "Hidden Draft Event" not in page
    assert "Hidden Expired Event" not in page


def test_migrated_registration_shape_renders_in_admin_data(
    client,
    db_session,
):
    event = _event(
        "migration-registration-shape",
        "Migrated Registration Event",
        audience="internal",
        status="closed",
    )
    registration = EventRegistration(
        event=event,
        price_option=event.price_options[0],
        contact_email="migrated@example.com",
        contact_phone="",
        team_name=None,
        emergency_contact_name="",
        emergency_contact_phone="",
        answers={},
        amount_cents=2500,
        discount_applied=False,
        status="confirmed",
        payment_intent_id="pi_migrated_shape",
        created_at=datetime(2020, 1, 2, 15, 30),
        updated_at=datetime(2020, 1, 2, 15, 30),
    )
    registration.participants.append(
        EventParticipant(
            position=1,
            role_label="Participant",
            name="Migrated Skier",
            date_of_birth=date(1900, 1, 1),
            email="migrated@example.com",
            phone="",
        )
    )
    db_session.session.add(event)
    db_session.session.commit()

    with client.session_transaction() as session:
        session["user"] = {"email": "admin@twincitiesskiclub.org"}

    response = client.get(
        f"/admin/events/{event.id}/registrations/data"
    )

    assert response.status_code == 200
    row = response.get_json()["registrations"][0]
    assert row["status"] == "confirmed"
    assert row["contact_email"] == "migrated@example.com"
    assert row["contact_phone"] == ""
    assert row["emergency_contact"] == ""
    assert row["participant_1"] == (
        "Participant: Migrated Skier "
        "(1900-01-01, migrated@example.com, )"
    )
