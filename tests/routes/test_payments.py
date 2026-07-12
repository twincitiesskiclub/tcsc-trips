"""Tests for app.routes.payments."""

from datetime import datetime, timedelta
import re
from unittest.mock import patch, MagicMock

import pytest
from flask import Response

from app import create_app
from app.models import db, Season, SocialEvent, Trip


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
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
def season_returning_only(app, db_session):
    """A season where only the RETURNING window is currently open."""
    now = datetime.utcnow()
    with app.app_context():
        season = Season(
            name=f'Test Season {now.timestamp()}',
            season_type='winter',
            year=now.year,
            start_date=now.date(),
            end_date=(now + timedelta(days=180)).date(),
            price_cents=10500,
            returning_start=now - timedelta(days=1),
            returning_end=now + timedelta(days=1),
            new_start=now + timedelta(days=2),
            new_end=now + timedelta(days=10),
        )
        db.session.add(season)
        db.session.commit()
        season_id = season.id
    yield season_id
    with app.app_context():
        s = Season.query.get(season_id)
        if s:
            db.session.delete(s)
            db.session.commit()


@pytest.fixture
def returning_member(app, db_session):
    """Seed a returning user (has an ACTIVE prior UserSeason in another season)."""
    from app.models import User, UserSeason
    from app.constants import UserStatus, UserSeasonStatus

    with app.app_context():
        other_season = Season(
            name=f'Prior Season {datetime.utcnow().timestamp()}',
            season_type='winter',
            year=2024,
            start_date=datetime(2024, 1, 1).date(),
            end_date=datetime(2024, 6, 1).date(),
            price_cents=10000,
        )
        db.session.add(other_season)
        db.session.flush()
        user = User(
            email='returning@example.com',
            first_name='Re',
            last_name='Turning',
            status=UserStatus.ACTIVE,
        )
        db.session.add(user)
        db.session.flush()
        us = UserSeason(
            user_id=user.id,
            season_id=other_season.id,
            registration_type='returning',
            status=UserSeasonStatus.ACTIVE,
            registration_date=datetime.utcnow().date(),
        )
        db.session.add(us)
        db.session.commit()
        ids = {'user_id': user.id, 'other_season_id': other_season.id}
    yield ids
    with app.app_context():
        UserSeason.query.filter_by(user_id=ids['user_id']).delete()
        User.query.filter_by(id=ids['user_id']).delete()
        Season.query.filter_by(id=ids['other_season_id']).delete()
        db.session.commit()


@pytest.fixture
def active_trip(app, db_session):
    """Seed a trip whose signup window is currently open."""
    now = datetime.utcnow()
    with app.app_context():
        trip = Trip(
            slug=f"security-test-trip-{int(now.timestamp() * 1000000)}",
            name="Security Test Trip",
            destination="Test Trails",
            max_participants_standard=20,
            max_participants_extra=5,
            start_date=now + timedelta(days=30),
            end_date=now + timedelta(days=33),
            signup_start=now - timedelta(days=1),
            signup_end=now + timedelta(days=1),
            price_low=13500,
            price_high=19500,
            status="active",
        )
        db.session.add(trip)
        db.session.commit()
        trip_id = trip.id
        trip_slug = trip.slug
    yield {"id": trip_id, "slug": trip_slug}
    with app.app_context():
        Trip.query.filter_by(id=trip_id).delete()
        db.session.commit()


@pytest.fixture
def social_event(app, db_session):
    now = datetime.utcnow()
    with app.app_context():
        event = SocialEvent(
            slug=f"security-test-social-{int(now.timestamp() * 1000000)}",
            name="Security Test Social",
            location="Test Venue",
            max_participants=30,
            event_date=now + timedelta(days=10),
            signup_start=now - timedelta(days=1),
            signup_end=now + timedelta(days=1),
            price=2500,
            status="active",
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id
    yield event_id
    with app.app_context():
        SocialEvent.query.filter_by(id=event_id).delete()
        db.session.commit()


def test_state_changing_routes_do_not_accept_get(client):
    paths = [
        '/admin/trips/1/delete',
        '/admin/seasons/1/delete-json',
        '/admin/social-events/1/delete',
        '/admin/skipper/evaluate/1',
    ]

    for path in paths:
        assert client.get(path).status_code == 405, path

    # The public /<slug> trip route catches a GET to /logout and returns 404;
    # importantly, it cannot clear the authenticated session.
    with client.session_transaction() as session:
        session['user'] = {'email': 'admin@twincitiesskiclub.org'}
    assert client.get('/logout').status_code == 404
    with client.session_transaction() as session:
        assert 'user' in session


@patch('app.routes.payments.stripe.Webhook.construct_event')
def test_stripe_webhook_is_exempt_but_browser_api_is_protected(
    mock_construct_event, app, client
):
    app.config['TESTING'] = False
    mock_construct_event.return_value = {
        'type': 'unhandled.test_event',
        'data': {'object': {}},
    }

    protected = client.post('/api/is_returning_member', json={'email': 'x@example.com'})
    assert protected.status_code == 400
    assert 'security token' in protected.get_json()['error']

    with patch.dict('os.environ', {'STRIPE_WEBHOOK_SECRET': 'whsec_test'}):
        webhook = client.post(
            '/webhook',
            data='{}',
            content_type='application/json',
            headers={'Stripe-Signature': 'test-signature'},
        )
    assert webhook.status_code == 200


def test_slack_blueprint_uses_signature_handler_instead_of_browser_csrf(app, client):
    app.config['TESTING'] = False
    fake_handler = MagicMock()
    fake_handler.handle.return_value = Response('accepted', status=200)

    with patch('app.routes.slack_interactivity._handler', fake_handler):
        response = client.post('/slack/events', data='signed-by-slack')

    assert response.status_code == 200
    fake_handler.handle.assert_called_once()


def test_real_admin_template_token_authorizes_form_and_fetch_flows(app, client):
    app.config['TESTING'] = False
    base_url = 'https://tcsc.test'
    with client.session_transaction(base_url=base_url) as session:
        session['user'] = {
            'email': 'admin@twincitiesskiclub.org',
            'name': 'Test Admin',
        }

    page = client.get('/admin', base_url=base_url)
    assert page.status_code == 200
    match = re.search(rb'name="csrf-token" content="([^"]+)"', page.data)
    assert match
    token = match.group(1).decode()

    # A representative JSON mutation reaches its route (404 for a missing
    # season) instead of being rejected by CSRF.
    ajax = client.post(
        '/admin/seasons/999999/late-link',
        json={'email': 'member@example.com'},
        base_url=base_url,
        headers={'X-CSRFToken': token, 'Referer': f'{base_url}/admin'},
    )
    assert ajax.status_code == 404

    logout = client.post(
        '/logout',
        data={'csrf_token': token},
        base_url=base_url,
        headers={'Referer': f'{base_url}/admin'},
    )
    assert logout.status_code == 302
    with client.session_transaction(base_url=base_url) as session:
        assert 'user' not in session


def test_trip_page_matches_server_registration_window(app, client, active_trip):
    with patch('app.routes.trips.render_template', return_value='rendered') as render:
        assert client.get(f"/{active_trip['slug']}").status_code == 200
        assert render.call_args.kwargs['registration_open'] is True

    with (
        patch('app.routes.trips.datetime') as clock,
        patch('app.routes.trips.render_template', return_value='rendered') as render,
    ):
        clock.utcnow.return_value = datetime(2000, 1, 1)
        assert client.get(f"/{active_trip['slug']}").status_code == 200
        assert render.call_args.kwargs['registration_open'] is False
        assert 'opens' in render.call_args.kwargs['registration_message'].lower()


class TestCreateTripPaymentIntentIntegrity:
    @patch('app.routes.payments.stripe')
    def test_uses_database_price_and_explicit_trip_slug(
        self, mock_stripe, client, active_trip
    ):
        mock_stripe.PaymentIntent.create.return_value = MagicMock(
            client_secret='cs_trip_test',
            id='pi_trip_test',
            amount=19500,
            status='requires_payment_method',
        )

        response = client.post(
            '/create-payment-intent',
            json={
                'trip_slug': active_trip['slug'],
                'price_tier': 'high',
                'amount': 0.01,
                'email': 'trip-test@example.com',
                'name': 'Trip Tester',
            },
            headers={
                'Referer': '/forged-trip',
                'Idempotency-Key': 'trip-request-123',
            },
        )

        assert response.status_code == 200
        kwargs = mock_stripe.PaymentIntent.create.call_args.kwargs
        assert kwargs['amount'] == 19500
        assert kwargs['metadata']['trip_id'] == str(active_trip['id'])
        assert kwargs['idempotency_key'] == 'trip-request-123'

    @patch('app.routes.payments.stripe')
    def test_rejects_unknown_price_tier(self, mock_stripe, client, active_trip):
        response = client.post(
            '/create-payment-intent',
            json={
                'trip_slug': active_trip['slug'],
                'price_tier': 'one-cent-special',
                'email': 'trip-test@example.com',
                'name': 'Trip Tester',
            },
        )

        assert response.status_code == 400
        mock_stripe.PaymentIntent.create.assert_not_called()


@patch('app.routes.payments.stripe')
def test_social_event_forwards_idempotency_key(mock_stripe, client, social_event):
    mock_stripe.PaymentIntent.create.return_value = MagicMock(
        client_secret='cs_social_test',
        id='pi_social_test',
        amount=2500,
        status='requires_payment_method',
    )

    response = client.post(
        '/create-social-event-payment-intent',
        json={
            'social_event_id': social_event,
            'email': 'social-test@example.com',
            'name': 'Social Tester',
        },
        headers={'Idempotency-Key': 'social-request-123'},
    )

    assert response.status_code == 200
    assert (
        mock_stripe.PaymentIntent.create.call_args.kwargs['idempotency_key']
        == 'social-request-123'
    )


class TestCreateSeasonPaymentIntentWindowGate:
    """Regression tests: do not create a PaymentIntent when the user's
    registration window is closed."""

    @patch('app.routes.payments.stripe')
    def test_new_member_blocked_when_new_window_closed(
        self, mock_stripe, client, season_returning_only
    ):
        # NEW window opens in 2 days; only RETURNING is open right now.
        resp = client.post(
            '/create-season-payment-intent',
            json={
                'season_id': season_returning_only,
                'email': 'brand-new-user@example.com',
                'name': 'Brand New',
            },
        )

        assert resp.status_code == 400
        body = resp.get_json()
        assert 'not currently open' in body['error'].lower()
        assert 'new' in body['error'].lower()
        mock_stripe.PaymentIntent.create.assert_not_called()

    @patch('app.routes.payments.stripe')
    def test_returning_member_allowed_when_returning_window_open(
        self, mock_stripe, client, season_returning_only, returning_member
    ):
        mock_stripe.PaymentIntent.create.return_value = MagicMock(
            client_secret='cs_test_xyz',
            id='pi_test_123',
            amount=10500,
            status='requires_payment_method',
        )

        resp = client.post(
            '/create-season-payment-intent',
            json={
                'season_id': season_returning_only,
                'email': 'returning@example.com',
                'name': 'Re Turning',
            },
        )

        assert resp.status_code == 200
        mock_stripe.PaymentIntent.create.assert_called_once()
