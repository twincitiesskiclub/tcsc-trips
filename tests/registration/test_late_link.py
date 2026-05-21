"""Tests for the late-registration token helper."""
import os
import time
from unittest.mock import patch

import pytest

from app import create_app
from app.late_link import MAX_AGE_SECONDS, generate, verify

_TEST_DB = "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"


@pytest.fixture
def app():
    with patch.dict(os.environ, {"DATABASE_URL": _TEST_DB}, clear=False):
        application = create_app()
    application.config["TESTING"] = True
    application.config["SECRET_KEY"] = "test-secret-key"
    return application


class TestLateLinkToken:
    def test_roundtrip_returns_payload(self, app):
        with app.app_context():
            token = generate(42, "Foo@Bar.com")
            payload = verify(token)
            assert payload == {"season_id": 42, "email": "foo@bar.com"}

    def test_tampered_token_returns_none(self, app):
        with app.app_context():
            token = generate(1, "x@y.com")
            tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
            assert verify(tampered) is None

    def test_wrong_secret_returns_none(self, app):
        with app.app_context():
            token = generate(1, "x@y.com")
        app.config["SECRET_KEY"] = "different-secret"
        with app.app_context():
            assert verify(token) is None

    def test_expired_token_returns_none(self, app):
        with app.app_context():
            token = generate(1, "x@y.com")
            # itsdangerous.timed uses time.time() via get_timestamp(); jump forward 8 days.
            future = time.time() + MAX_AGE_SECONDS + 60
            with patch("itsdangerous.timed.time.time", return_value=future):
                assert verify(token) is None

    def test_empty_token_returns_none(self, app):
        with app.app_context():
            assert verify("") is None
            assert verify(None) is None


from datetime import datetime, timedelta

from app.constants import UserSeasonStatus, UserStatus
from app.late_link import generate
from app.models import Season, User, UserSeason, db


@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()


@pytest.fixture
def closed_season(db_session):
    """A season whose new+returning registration windows are both in the past."""
    past_start = datetime.utcnow() - timedelta(days=30)
    past_end = datetime.utcnow() - timedelta(days=14)
    season = Season(
        name='Test Closed Season',
        year=2026,
        season_type='winter',
        start_date=datetime.utcnow().date() + timedelta(days=30),
        end_date=datetime.utcnow().date() + timedelta(days=120),
        returning_start=past_start,
        returning_end=past_end,
        new_start=past_start,
        new_end=past_end,
        price_cents=10000,
        registration_limit=100,
        is_current=False,
    )
    db.session.add(season)
    db.session.commit()
    yield season
    UserSeason.query.filter_by(season_id=season.id).delete()
    db.session.delete(season)
    db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


class TestRegistrationInviteBypass:
    """The registration route only checks the token's signature/expiry/email-match
    — payment and form validation are NOT covered here (out of scope for this
    feature). These tests use GET requests and inspect the rendered template /
    redirect behavior."""

    def test_get_with_valid_invite_renders_form_when_window_closed(self, app, client, closed_season):
        with app.app_context():
            token = generate(closed_season.id, 'guest@example.com')
        response = client.get(f'/seasons/{closed_season.id}/register?invite={token}', follow_redirects=False)
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert 'guest@example.com' in body
        assert 'readonly' in body

    def test_get_with_invalid_invite_redirects_when_window_closed(self, app, client, closed_season):
        response = client.get(f'/seasons/{closed_season.id}/register?invite=garbage', follow_redirects=False)
        # Existing closed-window UX: redirect (302) to home.
        assert response.status_code == 302

    def test_get_with_invite_for_other_season_redirects(self, app, client, closed_season):
        with app.app_context():
            token = generate(closed_season.id + 9999, 'guest@example.com')
        response = client.get(f'/seasons/{closed_season.id}/register?invite={token}', follow_redirects=False)
        assert response.status_code == 302

    def test_already_registered_short_circuits(self, app, client, closed_season):
        email = 'already-bypass-test@example.com'
        with app.app_context():
            # Clean up any leftover state from a prior run.
            existing = User.get_by_email(email)
            if existing:
                UserSeason.query.filter_by(user_id=existing.id).delete()
                db.session.delete(existing)
                db.session.commit()

            user = User(email=email, status=UserStatus.ACTIVE, first_name='A', last_name='B')
            db.session.add(user)
            db.session.flush()
            db.session.add(UserSeason(
                user_id=user.id,
                season_id=closed_season.id,
                registration_type='new',
                registration_date=datetime.utcnow().date(),
                status=UserSeasonStatus.ACTIVE,
            ))
            db.session.commit()
            token = generate(closed_season.id, email)
        try:
            # POST minimally — we expect to be short-circuited before form validation runs.
            response = client.post(
                f'/seasons/{closed_season.id}/register?invite={token}',
                data={'email': email},
                follow_redirects=False,
            )
            # The route short-circuits and redirects back to the register page.
            assert response.status_code == 302
            assert f'/seasons/{closed_season.id}/register' in response.headers['Location']
            # The flash message is set in the session; follow one hop and verify it
            # renders in the season_register template (which re-renders with a valid
            # invite in the URL so the window-closed guard is skipped).
            location = response.headers['Location']
            # Re-attach the invite token so the GET renders the form (not a further redirect)
            if '?' not in location:
                location = f'{location}?invite={token}'
            followed = client.get(location, follow_redirects=False)
            assert followed.status_code == 200
            assert b'already been used' in followed.data
        finally:
            with app.app_context():
                u = User.get_by_email(email)
                if u:
                    UserSeason.query.filter_by(user_id=u.id).delete()
                    db.session.delete(u)
                    db.session.commit()


class TestPaymentIntentInviteBypass:
    """The /create-season-payment-intent endpoint is the *first* server call
    when a user submits the registration form. It independently gates on
    season.is_open_for(), so an invite must bypass it there too."""

    def test_payment_intent_blocked_when_window_closed_without_invite(self, app, client, closed_season):
        response = client.post(
            '/create-season-payment-intent',
            json={
                'season_id': closed_season.id,
                'email': 'walkup@example.com',
                'name': 'Walk Up',
            },
        )
        assert response.status_code == 400
        assert b'not currently open' in response.data

    def test_payment_intent_bypassed_with_valid_invite(self, app, client, closed_season):
        with app.app_context():
            token = generate(closed_season.id, 'invited@example.com')
        from unittest.mock import MagicMock
        fake_intent = MagicMock()
        fake_intent.client_secret = 'pi_test_secret'
        fake_intent.id = 'pi_test_id'
        fake_intent.amount = 10000
        fake_intent.status = 'requires_payment_method'
        with patch('app.routes.payments.stripe.PaymentIntent.create', return_value=fake_intent) as create_call:
            response = client.post(
                '/create-season-payment-intent',
                json={
                    'season_id': closed_season.id,
                    'email': 'invited@example.com',
                    'name': 'Invited Person',
                    'invite': token,
                },
            )
        assert response.status_code == 200, response.data
        assert create_call.called, 'Stripe PaymentIntent.create should be reached when the invite bypass applies.'
        body = response.get_json()
        assert body['clientSecret'] == 'pi_test_secret'

    def test_payment_intent_blocked_with_wrong_email_invite(self, app, client, closed_season):
        with app.app_context():
            token = generate(closed_season.id, 'someone@example.com')
        response = client.post(
            '/create-season-payment-intent',
            json={
                'season_id': closed_season.id,
                'email': 'different@example.com',
                'name': 'Different',
                'invite': token,
            },
        )
        assert response.status_code == 400
        assert b'not currently open' in response.data
