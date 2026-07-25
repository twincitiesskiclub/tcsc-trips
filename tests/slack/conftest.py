"""Shared fixtures for tests/slack/.

Provides a bare Flask ``app`` fixture for tests that only need
``app.app_context()`` (e.g. to reach ``current_app.logger``) without touching
the database. Per-file fixtures of the same name take precedence over this
one (pytest fixture resolution favors the closer scope), so existing test
files that hand-roll their own ``app`` fixture keep working unchanged.
"""

import pytest

from app import create_app


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application
