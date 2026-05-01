"""Tests for app.routes.payments."""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from app import create_app
from app.models import db, Season


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
