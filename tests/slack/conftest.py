"""Shared fixtures for tests/slack/.

Provides a bare Flask ``app`` fixture for tests that only need
``app.app_context()`` (e.g. to reach ``current_app.logger``) without touching
the database. Per-file fixtures of the same name take precedence over this
one (pytest fixture resolution favors the closer scope), so existing test
files that hand-roll their own ``app`` fixture keep working unchanged.

Also provides ``db_session`` for tests that read/write the database. This
mirrors tests/practices/conftest.py: the database behind it is the REAL
LOCAL DEVELOPMENT DATABASE, not a throwaway test database, so
``db.create_all()``/``db.drop_all()`` are forbidden here -- the schema
already exists. Callers are responsible for their own cleanup (year-2099
dates, a "TEST"-prefixed marker, and a try/finally that rolls back first).
"""

import pytest

from app import create_app
from app.models import db


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session
