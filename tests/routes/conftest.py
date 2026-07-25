"""Shared fixtures for tests/routes/.

The database these tests run against is the real local development database
(``postgresql://tcsc:tcsc@localhost:5432/tcsc_trips``), not a throwaway test
database — the same convention documented in ``tests/practices/conftest.py``.
Do not call ``db.create_all()`` / ``db.drop_all()`` here.

Per-file fixtures of the same name take precedence over these (pytest
fixture resolution favors the closer scope), so existing test files in this
package that hand-roll their own ``app``/``client``/``db_session``/
``admin_client`` keep working unchanged. New test files get these for free.
"""

import pytest

from app import create_app
from app.models import db


@pytest.fixture
def app():
    application = create_app()
    application.config.update(
        TESTING=True,
        SECRET_KEY='test-secret-key',
        SQLALCHEMY_DATABASE_URI=(
            'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips'
        ),
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session


@pytest.fixture
def admin_client(client):
    """A test client with an authenticated admin session."""
    with client.session_transaction() as sess:
        sess['user'] = {
            'email': 'tester@twincitiesskiclub.org',
            'name': 'Tester',
        }
    return client
