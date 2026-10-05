"""Fixtures for the interest list tests.

Uses whatever DATABASE_URL the run exported (the scratch DB, see the plan),
unlike tests/routes/conftest.py which hardcodes the dev DB. Every row these
tests write uses TEST_DOMAIN and is wiped before and after each test.
"""
import pytest

from app import create_app
from app.interest.models import InterestSignup
from app.models import User, db

TEST_DOMAIN = '@interest-test.example'


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as sess:
        sess['user'] = {'email': 'tester@twincitiesskiclub.org', 'name': 'Tester'}
    return client


@pytest.fixture(autouse=True)
def _wipe(app):
    def wipe():
        with app.app_context():
            InterestSignup.query.filter(
                InterestSignup.email.like(f'%{TEST_DOMAIN}')
            ).delete(synchronize_session=False)
            User.query.filter(
                db.func.lower(User.email).like(f'%{TEST_DOMAIN}')
            ).delete(synchronize_session=False)
            db.session.commit()
    wipe()
    yield
    wipe()
