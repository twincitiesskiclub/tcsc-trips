"""Tests for app.routes.admin_practices page renders."""

from datetime import datetime, timedelta
import logging
from types import SimpleNamespace

import pytest

from app import create_app
from app.models import db
from app.practices.models import Practice, PracticeLocation


ADMIN_CREATE_REFRESH_DATE = datetime(2126, 8, 6, 18, 15)


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips'
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()


@pytest.fixture
def admin_client(client):
    """A test client with an authenticated admin session."""
    with client.session_transaction() as sess:
        sess['user'] = {'email': 'tester@twincitiesskiclub.org', 'name': 'Tester'}
    return client


@pytest.fixture
def admin_create_records(db_session):
    """Own one collision-refusing future week and delete only created rows."""
    week_start = (
        ADMIN_CREATE_REFRESH_DATE
        - timedelta(days=ADMIN_CREATE_REFRESH_DATE.weekday())
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)
    collisions = Practice.query.filter(
        Practice.date >= week_start,
        Practice.date < week_end,
    ).count()
    assert collisions == 0, (
        "Reserved Admin Create refresh test week contains existing rows; "
        "refusing to mutate persistent data"
    )

    location = PracticeLocation(name="Admin Create Refresh Test Location")
    db.session.add(location)
    db.session.commit()
    records = SimpleNamespace(location_id=location.id, practice_id=None)

    yield records

    db.session.rollback()
    owned_practices = Practice.query.filter(
        Practice.location_id == records.location_id,
        Practice.date == ADMIN_CREATE_REFRESH_DATE,
    ).all()
    assert len(owned_practices) <= 1, (
        "Admin Create refresh fixture found multiple practices for its exact "
        "location and date; refusing ambiguous teardown deletion"
    )
    if records.practice_id is not None and owned_practices:
        assert owned_practices[0].id == records.practice_id, (
            "Admin Create refresh fixture practice ID does not match its "
            "exact location-and-date-owned row; refusing teardown deletion"
        )
    for practice in owned_practices:
        db.session.delete(practice)
        db.session.flush()
    owned_location = db.session.get(PracticeLocation, records.location_id)
    if owned_location is not None:
        db.session.delete(owned_location)
    db.session.commit()


def test_new_practice_route_renders_create_mode(admin_client, db_session):
    resp = admin_client.get('/admin/practices/new')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Create mode: title says "New Practice" and there is no context rail yet.
    assert 'New Practice' in body
    assert 'Lead Confirmations' not in body


def test_new_practice_route_requires_auth(client, db_session):
    resp = client.get('/admin/practices/new')
    # Unauthenticated users are redirected to login.
    assert resp.status_code == 302
    assert '/login' in resp.headers.get('Location', '')


def test_practices_list_renders_new_shell(admin_client, db_session):
    resp = admin_client.get('/admin/practices', follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # New shell present; old Tabulator grid container gone.
    assert 'id="practice-list"' in body
    assert 'id="pl-drawer"' in body
    assert 'practices-table' not in body


def test_admin_create_records_teardown_finds_practice_when_id_is_unset(
    db_session,
):
    fixture_generator = admin_create_records.__wrapped__(db_session)
    records = next(fixture_generator)
    practice = Practice(
        date=ADMIN_CREATE_REFRESH_DATE,
        day_of_week=ADMIN_CREATE_REFRESH_DATE.strftime("%A"),
        location_id=records.location_id,
    )
    db.session.add(practice)
    db.session.commit()
    practice_id = practice.id
    teardown_error = None

    try:
        try:
            next(fixture_generator)
        except StopIteration:
            pass
        except Exception as exc:
            teardown_error = exc
            db.session.rollback()

        assert records.practice_id is None
        assert db.session.get(Practice, practice_id) is None
        assert teardown_error is None
    finally:
        db.session.rollback()
        surviving_practice = db.session.get(Practice, practice_id)
        if surviving_practice is not None:
            db.session.delete(surviving_practice)
            db.session.flush()
        surviving_location = db.session.get(
            PracticeLocation,
            records.location_id,
        )
        if surviving_location is not None:
            db.session.delete(surviving_location)
        db.session.commit()


def test_admin_create_refreshes_summaries_after_commit(
    admin_client,
    admin_create_records,
    monkeypatch,
):
    refresh_calls = []
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *args, **kwargs: refresh_calls.append((args, kwargs)),
    )

    response = admin_client.post(
        "/admin/practices/create",
        json={
            "date": ADMIN_CREATE_REFRESH_DATE.isoformat(),
            "location_id": admin_create_records.location_id,
        },
    )

    assert response.status_code == 200
    admin_create_records.practice_id = response.get_json()["practice_id"]
    saved = db.session.get(Practice, admin_create_records.practice_id)
    assert saved is not None
    assert len(refresh_calls) == 1
    args, kwargs = refresh_calls[0]
    assert args[0].id == saved.id
    assert kwargs == {"change_type": "create"}


def test_admin_create_refresh_failure_keeps_truthful_success(
    admin_client,
    admin_create_records,
    monkeypatch,
):
    refresh_attempts = []

    def fail_refresh(*args, **kwargs):
        refresh_attempts.append((args, kwargs))
        raise RuntimeError("summary refresh unavailable")

    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        fail_refresh,
    )

    response = admin_client.post(
        "/admin/practices/create",
        json={
            "date": ADMIN_CREATE_REFRESH_DATE.isoformat(),
            "location_id": admin_create_records.location_id,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    admin_create_records.practice_id = response.get_json()["practice_id"]
    assert db.session.get(Practice, admin_create_records.practice_id) is not None
    assert len(refresh_attempts) == 1
    args, kwargs = refresh_attempts[0]
    assert args[0].id == admin_create_records.practice_id
    assert kwargs == {"change_type": "create"}


def test_admin_create_logs_returned_refresh_failure_without_rolling_back(
    admin_client,
    admin_create_records,
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *_args, **_kwargs: {
            "coach_summary": {
                "success": False,
                "error": "summary unavailable",
            }
        },
    )

    with caplog.at_level(logging.WARNING):
        response = admin_client.post(
            "/admin/practices/create",
            json={
                "date": ADMIN_CREATE_REFRESH_DATE.isoformat(),
                "location_id": admin_create_records.location_id,
            },
        )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    admin_create_records.practice_id = response.get_json()["practice_id"]
    assert db.session.get(Practice, admin_create_records.practice_id) is not None
    assert "coach_summary" in caplog.text
    assert "summary unavailable" in caplog.text
