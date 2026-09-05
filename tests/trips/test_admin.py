import json
import csv
import re
from copy import deepcopy
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from markupsafe import escape

from app.constants import UserStatus
from app.models import db, Trip
from app.models import Payment, User
from app.trips.models import TripProfile, TripRegistration, TripRegistrationStatus
from app.trips.models import TripSeries
from app.trips.questions import load_trip_templates


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as session:
        session["user"] = {"email": "admin@twincitiesskiclub.org"}
    return client


def _series_with_edition(db_session, slug="test-trip-admin",
                         edition_slug="test-trip-admin-2027"):
    series = TripSeries(slug=slug, name="TEST Trip", destination="Testville",
                        slack_channel_name="test-channel")
    db.session.add(series)
    db.session.flush()
    trip = Trip(
        slug=edition_slug, name="TEST Trip 2027", destination="Testville",
        series_id=series.id, max_participants_standard=20,
        max_participants_extra=5,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime(2098, 11, 1), signup_end=datetime(2098, 12, 31),
        price_low=10000, price_high=15000, status="active",
        custom_questions=[{"key": "chore_preference", "label": "Which task?",
                           "type": "choice",
                           "options": ["Cooking", "Cleaning"],
                           "required": True}],
    )
    db.session.add(trip)
    db.session.commit()
    return series, trip


def test_announce_posts_blocks_to_channel(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    client_mock = MagicMock()
    with patch("app.routes.admin.get_slack_client",
               return_value=client_mock), \
         patch("app.routes.admin.get_channel_id_by_name",
               return_value="C_ANNOUNCE"):
        response = admin_client.post(f"/admin/trips/{trip.id}/announce",
                                     json={"channel": ""})
    assert response.get_json()["success"] is True
    kwargs = client_mock.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "C_ANNOUNCE"
    assert any(b["type"] == "actions" for b in kwargs["blocks"])


def test_announce_without_channel_errors(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    series.slack_channel_name = None
    db.session.commit()
    response = admin_client.post(f"/admin/trips/{trip.id}/announce",
                                 json={"channel": ""})
    assert response.status_code == 400


def test_new_edition_clones_questions_and_prices(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    response = admin_client.post(f"/admin/trips/{trip.id}/new-edition")
    assert response.status_code == 200
    new_id = response.get_json()["id"]
    clone = db_session.session.get(Trip, new_id)
    assert clone.series_id == series.id
    assert clone.status == "draft"
    assert clone.custom_questions == trip.custom_questions
    assert clone.custom_questions is not trip.custom_questions
    assert clone.price_low == trip.price_low
    assert clone.slug == "test-trip-admin-2100"  # 2099-01-10 + 364d -> 2100
    assert clone.start_date == trip.start_date + timedelta(days=364)


def test_new_trip_duplicate_series_keeps_submitted_questions(
        admin_client, db_session):
    series, _ = _series_with_edition(db_session)
    questions = [{"key": "survivor", "label": "Submitted survivor label",
                  "type": "text", "options": [], "required": False}]
    trip_count = Trip.query.count()
    series_count = TripSeries.query.count()
    form = {
        "series_slug": series.slug,
        "name": "TEST Trip 2028", "slug": "test-trip-admin-2028",
        "destination": "Testville",
        "max_participants_standard": "20", "max_participants_extra": "5",
        "start_date": "2100-01-09", "end_date": "2100-01-11",
        "signup_start": "2099-11-01T00:00",
        "signup_end": "2099-12-31T00:00",
        "price_low": "100", "price_high": "150",
        "description": "Duplicate-series test", "status": "draft",
        "template_key": "blank",
        "custom_questions_json": json.dumps(questions),
    }

    response = admin_client.post("/admin/trips/new", data=form)

    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "Submitted survivor label" in body
    assert series.slug in body
    assert "already exists" in body
    assert Trip.query.count() == trip_count
    assert TripSeries.query.count() == series_count


def test_edit_saves_custom_questions_json(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    questions = [{"key": "vibe", "label": "Vibe?", "type": "choice",
                  "options": ["Early bird", "Night owl"], "required": True}]
    form = {
        "name": trip.name, "destination": trip.destination,
        "max_participants_standard": "20", "max_participants_extra": "5",
        "start_date": "2099-01-10", "end_date": "2099-01-12",
        "signup_start": "2098-11-01T00:00", "signup_end": "2098-12-31T00:00",
        "price_low": "100", "price_high": "150",
        "description": "", "status": "active",
        "custom_questions_json": json.dumps(questions),
    }
    response = admin_client.post(f"/admin/trips/{trip.id}/edit", data=form)
    assert response.status_code in (200, 302)
    db_session.session.expire_all()
    assert trip.custom_questions == questions


def test_edit_rejects_invalid_question_json(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    form = {
        "name": trip.name, "destination": trip.destination,
        "max_participants_standard": "20", "max_participants_extra": "5",
        "start_date": "2099-01-10", "end_date": "2099-01-12",
        "signup_start": "2098-11-01T00:00", "signup_end": "2098-12-31T00:00",
        "price_low": "100", "price_high": "150",
        "description": "", "status": "active",
        "custom_questions_json": json.dumps([{"key": "bad"}]),
    }
    response = admin_client.post(f"/admin/trips/{trip.id}/edit", data=form)
    assert response.status_code == 400
    db_session.session.expire_all()
    assert trip.custom_questions[0]["key"] == "chore_preference"


@pytest.fixture
def preview_questions():
    return deepcopy(load_trip_templates()["north_shore"]["custom_questions"]) + [
        {"key": "sharing", "label": "Will you share a bed?", "type": "yes_no",
         "required": True},
        {"key": "share_with", "label": "Who will you share with?", "type": "text",
         "required": False, "visible_if": {"question": "sharing", "equals": "yes"}},
    ]


@pytest.mark.parametrize("email", [None, "trip-member@example.com"])
def test_questions_preview_requires_admin(client, email):
    if email:
        with client.session_transaction() as session:
            session["user"] = {"email": email}
    response = client.post("/admin/trips/questions-preview",
                           data={"custom_questions_json": "[]"})
    assert response.status_code == 302
    assert b"Preview only" not in response.data


@pytest.mark.parametrize(("raw", "message"), [
    ("not-json", "Custom questions must contain valid JSON."),
    ("{}", "Custom questions must be a list"),
    ('[{"key":"broken"}]', "Question 'broken' is missing 'label'"),
])
def test_questions_preview_renders_validation_errors(admin_client, raw, message):
    response = admin_client.post("/admin/trips/questions-preview",
                                 data={"custom_questions_json": raw})
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert str(escape(message)) in html
    assert 'role="alert"' in html
    assert "Preview only. Nothing is saved or submitted." in html
    assert "css/styles/main.css" in html
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"


def _assert_preview_profile(html):
    for label in ("Getting there", "Food and sleeping", "Can you drive a carpool?",
                  "How many people can you accommodate (besides yourself)?",
                  "How many bikes can you accommodate?", "Do you have a trailer hitch?",
                  "What is your region code?", "Dietary restrictions",
                  "Other dietary restriction(s)?", "Do you have a 2+ person tent?"):
        assert label in html
    assert 'id="dietary-options"' in html


def test_questions_preview_renders_unsaved_survey_without_saving(
        admin_client, db_session, preview_questions):
    _, trip = _series_with_edition(db_session)
    saved_questions = deepcopy(trip.custom_questions)
    trip_count = Trip.query.count()
    response = admin_client.post("/admin/trips/questions-preview", data={
        "custom_questions_json": json.dumps(preview_questions),
    })
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Preview only. Nothing is saved or submitted." in html
    assert "css/styles/main.css" in html
    assert "trip_questions_preview.js" in html
    _assert_preview_profile(html)
    assert re.findall(r'data-question-key="([^"]+)"', html) == [
        q["key"] for q in preview_questions]
    for question in preview_questions:
        assert str(escape(question["label"])) in html
        if question.get("help_text"):
            assert str(escape(question["help_text"])) in html
        for option in question.get("options", []):
            assert str(escape(option)) in html
    assert 'data-visible-if=\'{"equals": "yes", "question": "sharing"}\'' in html
    assert 'data-max-selections="8"' in html
    assert 'data-question-type="yes_no"' in html
    for excluded in ('id="gate-section"', 'id="card-element"', '<form',
                     'type="submit"', 'stripe.com', 'trip_registration.js'):
        assert excluded not in html
    db.session.expire_all()
    assert trip.custom_questions == saved_questions
    assert Trip.query.count() == trip_count
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    csp = response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'self'" in csp
    assert "frame-src 'none'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src ")[1].split(";")[0]


def test_questions_preview_without_custom_questions_still_shows_profile(admin_client):
    response = admin_client.post("/admin/trips/questions-preview",
                                 data={"custom_questions_json": "[]"})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    _assert_preview_profile(html)
    assert 'id="trip-questions"' not in html


def test_registration_and_preview_render_identical_survey_sections(
        admin_client, db_session, preview_questions):
    series, trip = _series_with_edition(db_session)
    trip.custom_questions = preview_questions
    trip.signup_start = datetime.utcnow() - timedelta(days=1)
    trip.signup_end = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    registration = admin_client.get(f"/{series.slug}/register")
    preview = admin_client.post("/admin/trips/questions-preview", data={
        "custom_questions_json": json.dumps(preview_questions),
    })
    assert registration.status_code == preview.status_code == 200

    def sections(response):
        html = response.get_data(as_text=True)
        # The preview omits the member check, so its step numbers start at one.
        return [re.sub(r'(<span data-step-number\b[^>]*>)\d+', r'\1', section) for section in
                re.findall(r'<section\b[^>]*>.*?</section>', html, re.S)]

    # Compare every byte of the survey markup, including labels and the
    # data-question-key, data-visible-if and data-max-selections attributes.
    assert len(sections(preview)) == 3
    assert sections(registration)[1:4] == sections(preview)
    assert 'type="module"' in registration.get_data(as_text=True)
    assert registration.headers["X-Frame-Options"] == "DENY"


def test_trip_editors_include_preview_and_allow_only_same_origin_frames(admin_client, db_session):
    _, trip = _series_with_edition(db_session)
    for url in ("/admin/trips/new", f"/admin/trips/{trip.id}/edit"):
        response = admin_client.get(url)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'id="preview-trip-survey"' in html
        assert '<dialog id="trip-survey-dialog"' in html
        assert 'action="/admin/trips/questions-preview"' in html
        assert 'target="trip-survey-preview-frame"' in html
        assert "frame-src 'self'" in response.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert response.headers["X-Frame-Options"] == "DENY"
    response = admin_client.get("/admin/trips")
    assert "frame-src 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"] == "DENY"


def test_questions_preview_requires_the_admin_form_csrf_token(admin_client, app):
    app.config["TESTING"] = False
    missing = admin_client.post("/admin/trips/questions-preview",
                                data={"custom_questions_json": "[]"})
    assert missing.status_code == 400
    assert b"security token" in missing.data
    editor = admin_client.get("/admin/trips/new").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', editor)[1]
    accepted = admin_client.post("/admin/trips/questions-preview", data={
        "csrf_token": token, "custom_questions_json": "[]",
    })
    assert accepted.status_code == 200


def _registered_member(db_session, trip, email="trip-member@example.com"):
    user = User(first_name="Test", last_name="Member", email=email,
                status=UserStatus.ACTIVE)
    db.session.add(user)
    db.session.flush()
    db.session.add(TripProfile(user_id=user.id, can_drive=True,
                               seat_capacity=3, region_code="4",
                               dietary_restrictions=["Vegetarian"],
                               dietary_other="", has_tent=None))
    registration = TripRegistration(
        trip_id=trip.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING,
        answers={"chore_preference": "Cooking"},
        price_tier="low", amount_cents=10000,
        payment_intent_id="pi_trip_admin",
    )
    db.session.add(registration)
    db.session.add(Payment(payment_intent_id="pi_trip_admin",
                           email=email, name="Test Member", amount=10000,
                           status="requires_capture", payment_type="trip",
                           trip_id=trip.id, user_id=user.id))
    db.session.commit()
    return user, registration


def test_roster_data_has_profile_and_question_columns(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    _registered_member(db_session, trip)
    response = admin_client.get(f"/admin/trips/{trip.id}/registrations/data")
    body = response.get_json()
    keys = [c["key"] for c in body["columns"]]
    assert "region_code" in keys
    assert "chore_preference" in keys
    row = body["registrations"][0]
    assert row["member"] == "Test Member"
    assert row["chore_preference"] == "Cooking"
    assert row["region_code"] == "4"
    assert row["payment_status"] == "requires_capture"
    assert row["payment_id"] is not None


def test_roster_disambiguates_duplicate_question_labels(admin_client,
                                                        db_session):
    series, trip = _series_with_edition(db_session)
    trip.custom_questions = [
        {"key": "first_choice", "label": "Choice", "type": "text",
         "required": False},
        {"key": "second_choice", "label": "Choice", "type": "text",
         "required": False},
    ]
    _, registration = _registered_member(db_session, trip)
    registration.answers = {
        "first_choice": "First value",
        "second_choice": "Second value",
    }
    db.session.commit()

    response = admin_client.get(f"/admin/trips/{trip.id}/registrations/data")
    columns = {column["key"]: column["label"]
               for column in response.get_json()["columns"]}
    assert columns["first_choice"] == "Choice"
    assert columns["second_choice"] == "Choice (second_choice)"

    response = admin_client.get(
        f"/admin/trips/{trip.id}/registrations/export.csv")
    row = next(csv.DictReader(StringIO(response.get_data(as_text=True))))
    assert row["Choice"] == "First value"
    assert row["Choice (second_choice)"] == "Second value"


def test_roster_csv_export(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    _registered_member(db_session, trip)
    response = admin_client.get(
        f"/admin/trips/{trip.id}/registrations/export.csv")
    reader = csv.DictReader(StringIO(response.get_data(as_text=True)))
    rows = list(reader)
    assert rows[0]["Member"] == "Test Member"
    assert rows[0]["Region"] == "4"
