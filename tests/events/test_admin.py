"""Admin event management route tests."""

import csv
from datetime import date, datetime, timedelta
from io import StringIO
from unittest.mock import patch

import pytest

from app.events.models import (
    Event,
    EventParticipant,
    EventPriceOption,
    EventRegistration,
    EventStatus,
    RegistrationStatus,
)
from app.models import Payment


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as session:
        session["user"] = {"email": "admin@twincitiesskiclub.org"}
    return client


def _event(slug, status=EventStatus.DRAFT, custom_questions=None):
    now = datetime.utcnow()
    event = Event(
        slug=slug,
        name="Admin Event",
        description="An event managed from the admin.",
        location="Theodore Wirth Park",
        event_date=now + timedelta(days=30),
        signup_start=now - timedelta(days=1),
        signup_end=now + timedelta(days=20),
        capacity=40,
        status=status,
        audience="both",
        custom_questions=custom_questions or [],
        template_key="blank",
    )
    event.price_options.append(
        EventPriceOption(
            name="Team of 3",
            description="One registration for a relay team.",
            price_cents=10500,
            member_price_cents=9000,
            participant_roles=[
                "Rollerskier",
                "Mountain Biker",
                "Trail Runner",
            ],
            sort_order=0,
        )
    )
    return event


def _registration(event, status=RegistrationStatus.CONFIRMED):
    registration = EventRegistration(
        event=event,
        price_option=event.price_options[0],
        contact_email="captain@example.com",
        contact_phone="612-555-0100",
        team_name="Nordic Rockets",
        emergency_contact_name="Casey Contact",
        emergency_contact_phone="612-555-0199",
        answers={"course": "Long course"},
        amount_cents=10500,
        discount_applied=True,
        status=status,
        created_at=datetime(2026, 7, 24, 15, 30),
    )
    registration.participants.extend(
        [
            EventParticipant(
                position=1,
                role_label="Rollerskier",
                name="Ada Skier",
                date_of_birth=date(1990, 1, 2),
                email="ada@example.com",
                phone="612-555-0101",
            ),
            EventParticipant(
                position=2,
                role_label="Mountain Biker",
                name="Ben Biker",
                date_of_birth=date(1991, 2, 3),
                email="ben@example.com",
                phone="612-555-0102",
            ),
            EventParticipant(
                position=3,
                role_label="Trail Runner",
                name="Cam Runner",
                date_of_birth=date(1992, 3, 4),
                email="cam@example.com",
                phone="612-555-0103",
            ),
        ]
    )
    return registration


def test_events_data_returns_confirmed_revenue(
    admin_client,
    db_session,
):
    event = _event("admin-grid-test", status=EventStatus.ACTIVE)
    event.registrations.extend(
        [
            _registration(event),
            _registration(event, RegistrationStatus.PENDING_PAYMENT),
        ]
    )
    db_session.session.add(event)
    db_session.session.commit()

    response = admin_client.get("/admin/events/data")

    assert response.status_code == 200
    row = next(
        item
        for item in response.get_json()["events"]
        if item["id"] == event.id
    )
    assert row == {
        "id": event.id,
        "name": "Admin Event",
        "slug": "admin-grid-test",
        "event_date": event.event_date.isoformat(),
        "audience": "both",
        "status": "active",
        "confirmed_count": 1,
        "capacity": 40,
        "revenue_cents": 10500,
        "template_key": "blank",
    }


def test_create_from_dry_tri_template_copies_three_price_options(
    admin_client,
    db_session,
):
    now = datetime.utcnow()
    response = admin_client.post(
        "/admin/events/new",
        data={
            "slug": "dry-tri-2026",
            "name": "Dry Tri 2026",
            "description": "Roll, ride, and run.",
            "location": "Carver Park Reserve",
            "event_date": (now + timedelta(days=90)).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "signup_start": now.strftime("%Y-%m-%dT%H:%M"),
            "signup_end": (now + timedelta(days=80)).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "capacity": "150",
            "status": EventStatus.DRAFT,
            "audience": "both",
            "details_url": "",
            "discount_code": "",
            "template_key": "dry_tri",
        },
    )

    assert response.status_code == 302
    event = Event.query.filter_by(slug="dry-tri-2026").one()
    assert event.template_key == "dry_tri"
    assert [option.name for option in event.price_options] == [
        "Individual",
        "Team of 3",
        "Run-only 6K",
    ]


def test_duplicate_copies_configuration_as_draft_without_registrations(
    admin_client,
    db_session,
):
    event = _event(
        "admin-duplicate-test",
        status=EventStatus.ACTIVE,
        custom_questions=[
            {
                "key": "course",
                "label": "Course",
                "type": "choice",
                "options": ["Long", "Short"],
                "required": True,
                "help_text": "",
            }
        ],
    )
    event.registrations.append(_registration(event))
    db_session.session.add(event)
    db_session.session.commit()

    response = admin_client.post(
        f"/admin/events/{event.id}/duplicate"
    )

    assert response.status_code == 200
    duplicate = Event.query.filter_by(
        slug="admin-duplicate-test-copy"
    ).one()
    assert duplicate.status == EventStatus.DRAFT
    assert duplicate.custom_questions == event.custom_questions
    assert len(duplicate.price_options) == len(event.price_options)
    assert duplicate.price_options[0].participant_roles == [
        "Rollerskier",
        "Mountain Biker",
        "Trail Runner",
    ]
    assert duplicate.registrations == []


def test_delete_active_event_returns_conflict(
    admin_client,
    db_session,
):
    event = _event("admin-delete-test", status=EventStatus.ACTIVE)
    db_session.session.add(event)
    db_session.session.commit()

    response = admin_client.post(f"/admin/events/{event.id}/delete")

    assert response.status_code == 409
    assert db_session.session.get(Event, event.id) is not None


@pytest.fixture
def registration_event(db_session):
    event = _event(
        "admin-registration-test",
        status=EventStatus.ACTIVE,
        custom_questions=[
            {
                "key": "course",
                "label": "Course",
                "type": "choice",
                "options": ["Long course", "Short course"],
                "required": True,
                "help_text": "",
            }
        ],
    )
    registration = _registration(event)
    db_session.session.add(event)
    db_session.session.commit()
    return event, registration


def test_registrations_data_flattens_participants_and_answers(
    admin_client,
    registration_event,
):
    event, registration = registration_event

    page = admin_client.get(
        f"/admin/events/{event.id}/registrations"
    )
    response = admin_client.get(
        f"/admin/events/{event.id}/registrations/data"
    )

    assert page.status_code == 200
    assert "Registrations and race-day roster" in page.get_data(
        as_text=True
    )
    assert response.status_code == 200
    row = response.get_json()["registrations"][0]
    assert row["id"] == registration.id
    assert row["price_option_name"] == "Team of 3"
    assert row["participant_1"] == (
        "Rollerskier: Ada Skier "
        "(1990-01-02, ada@example.com, 612-555-0101)"
    )
    assert row["participant_3"] == (
        "Trail Runner: Cam Runner "
        "(1992-03-04, cam@example.com, 612-555-0103)"
    )
    assert row["course"] == "Long course"
    assert row["amount_cents"] == 10500


def test_registration_csv_contains_flattened_headers_and_values(
    admin_client,
    registration_event,
):
    event, _registration_row = registration_event

    response = admin_client.get(
        f"/admin/events/{event.id}/registrations/export.csv"
    )

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert (
        response.headers["Content-Disposition"]
        == 'attachment; filename="registrations-admin-registration-test.csv"'
    )
    csv_text = response.get_data(as_text=True)
    assert "price_option_name" in csv_text.splitlines()[0]
    assert "participant_1" in csv_text.splitlines()[0]
    assert "course" in csv_text.splitlines()[0]
    assert "Nordic Rockets" in csv_text
    assert "Rollerskier: Ada Skier" in csv_text
    assert "Long course" in csv_text


def test_registration_csv_escapes_formulas_without_changing_json(
    admin_client,
    db_session,
    registration_event,
):
    event, registration = registration_event
    registration.team_name = '=HYPERLINK("http://evil")'
    participant = registration.participants[0]
    participant.role_label = "+Rollerskier"
    participant.name = "+Ada Skier"
    db_session.session.commit()

    csv_response = admin_client.get(
        f"/admin/events/{event.id}/registrations/export.csv"
    )
    assert csv_response.status_code == 200
    csv_row = next(
        csv.DictReader(StringIO(csv_response.get_data(as_text=True)))
    )

    assert csv_row["team_name"] == '\'=HYPERLINK("http://evil")'
    assert csv_row["participant_1"].startswith(
        "'+Rollerskier: +Ada Skier"
    )

    data_response = admin_client.get(
        f"/admin/events/{event.id}/registrations/data"
    )
    assert data_response.status_code == 200
    data_row = data_response.get_json()["registrations"][0]

    assert data_row["team_name"] == '=HYPERLINK("http://evil")'
    assert data_row["participant_1"].startswith(
        "+Rollerskier: +Ada Skier"
    )


def test_cancel_unpaid_pending_registration(
    admin_client,
    db_session,
):
    event = _event(
        "admin-registration-test",
        status=EventStatus.ACTIVE,
    )
    registration = _registration(
        event,
        status=RegistrationStatus.PENDING_PAYMENT,
    )
    db_session.session.add(event)
    db_session.session.commit()

    response = admin_client.post(
        f"/admin/events/registrations/{registration.id}/cancel"
    )

    assert response.status_code == 200
    db_session.session.refresh(registration)
    assert registration.status == RegistrationStatus.CANCELLED


@pytest.mark.parametrize(
    "path",
    [
        "/admin/events",
        "/admin/events/data",
        "/admin/events/new",
    ],
)
def test_admin_event_pages_require_admin_session(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_event_pages_render_grid_and_json_editors(admin_client):
    events_page = admin_client.get("/admin/events")
    form_page = admin_client.get("/admin/events/new")

    assert events_page.status_code == 200
    assert "event-grid-body" in events_page.get_data(as_text=True)
    assert form_page.status_code == 200
    form_html = form_page.get_data(as_text=True)
    assert 'name="price_options_json"' in form_html
    assert 'name="custom_questions_json"' in form_html
    assert 'value="dry_tri"' in form_html


def test_status_endpoint_rejects_unknown_value(
    admin_client,
    db_session,
):
    event = _event("admin-grid-test")
    db_session.session.add(event)
    db_session.session.commit()

    response = admin_client.post(
        f"/admin/events/{event.id}/status",
        json={"status": "published"},
    )

    assert response.status_code == 400
    db_session.session.refresh(event)
    assert event.status == EventStatus.DRAFT


def test_edit_cannot_remove_price_option_with_registration(
    admin_client,
    db_session,
):
    event = _event("admin-registration-test")
    event.registrations.append(_registration(event))
    db_session.session.add(event)
    db_session.session.commit()

    response = admin_client.post(
        f"/admin/events/{event.id}/edit",
        data={
            "slug": event.slug,
            "name": event.name,
            "description": event.description,
            "location": event.location,
            "event_date": event.event_date.strftime("%Y-%m-%dT%H:%M"),
            "signup_start": event.signup_start.strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "signup_end": event.signup_end.strftime("%Y-%m-%dT%H:%M"),
            "capacity": str(event.capacity),
            "status": event.status,
            "audience": event.audience,
            "details_url": "",
            "discount_code": "",
            "price_options_json": "[]",
            "custom_questions_json": "[]",
        },
    )

    assert response.status_code == 400
    assert (
        "cannot be removed because it has registrations"
        in response.get_data(as_text=True)
    )
    db_session.session.refresh(event)
    assert len(event.price_options) == 1


@patch("app.routes.admin_events.refund_or_cancel_payment")
def test_cancel_paid_registration_uses_shared_refund_helper(
    refund,
    admin_client,
    db_session,
):
    event = _event("admin-registration-test")
    registration = _registration(event)
    payment = Payment(
        payment_intent_id="pi_admin_event_refund",
        email=registration.contact_email,
        name="Ada Skier",
        amount=registration.amount_cents,
        status="succeeded",
        payment_type="event",
        event_registration=registration,
    )
    db_session.session.add_all([event, payment])
    db_session.session.commit()

    response = admin_client.post(
        f"/admin/events/registrations/{registration.id}/cancel"
    )

    assert response.status_code == 200
    refund.assert_called_once_with(payment)
    db_session.session.refresh(registration)
    assert registration.status == RegistrationStatus.REFUNDED
