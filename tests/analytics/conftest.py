"""Fixtures for tests/analytics.

Run against the scratch DB, never the shared dev DB:
    DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/analytics
DB tests roll back; nothing here commits. The repo is public: fixtures are
hand-written and contain no real Slack content or member IDs.
"""
import json
import os
from pathlib import Path

import pytest

from app import create_app
from app.models import db
from tests._db_guard import LOCAL_TEST_DB

FIXTURES = Path(__file__).parent / "fixtures"
DUMP_DIR = Path(os.environ.get(
    "TCSC_ANALYTICS_DUMP_DIR",
    "/workspace/tcsc-trips/.superpowers/analytics-slack-dump"))


@pytest.fixture
def app():
    os.environ.setdefault("TCSC_MIGRATION_ONLY", "1")  # no scheduler in tests
    application = create_app()
    application.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", LOCAL_TEST_DB),
    )
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        try:
            yield db.session
        finally:
            db.session.rollback()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as sess:
        sess["user"] = {"email": "tester@twincitiesskiclub.org", "name": "Tester"}
    return client


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())
