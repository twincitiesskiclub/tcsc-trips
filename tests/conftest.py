"""Suite-wide safety net: never let the tests touch a non-local database.

``app/config.py`` binds SQLAlchemy to the ``DATABASE_URL`` environment variable,
and ``create_app()`` requires it. The per-file ``app`` fixtures override the URI
to a localhost DB, but only *after* ``create_app()`` — so a ``DATABASE_URL``
pointed at prod (e.g. left exported in the shell after running a prod script)
could leak test writes into production. That actually happened once: newsletter
fixtures created ``*@test.com`` users in the prod database.

This conftest closes the hole for the whole suite by pinning ``DATABASE_URL`` to
the local test DB before any app is created, and asserting every test stays
local. It also supplies a throwaway ``FLASK_SECRET_KEY`` so the suite runs with
no exported env at all (removing the temptation to export risky values).

Escape hatch: set ``TCSC_ALLOW_NONLOCAL_TEST_DB=1`` to bypass (e.g. a CI host
that isn't literally ``localhost``).
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from tests._db_guard import (
    BYPASS_ENV,
    LOCAL_TEST_DB,
    bypass_enabled,
    db_host,
    is_local_db,
)


def pytest_configure(config):
    """Pin a safe local DB (and a test secret) before any app is created."""
    os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key")
    if bypass_enabled():
        return
    current = os.environ.get("DATABASE_URL")
    if not current or not is_local_db(current):
        os.environ["DATABASE_URL"] = LOCAL_TEST_DB


@pytest.fixture(autouse=True)
def _enforce_local_db():
    """Fail loudly if any test ever resolves to a non-local database."""
    if bypass_enabled():
        yield
        return
    url = os.environ.get("DATABASE_URL", "")
    assert is_local_db(url), (
        f"Refusing to run tests against non-local database host {db_host(url)!r} "
        f"({url!r}). Tests must use a localhost DB; set {BYPASS_ENV}=1 only if "
        f"you truly intend otherwise."
    )
    yield


@pytest.fixture(autouse=True)
def _no_outbound_providers():
    """Never let a test reach Twilio or Resend.

    Every outbound provider call (verify start/check, SMS send, Resend email)
    goes through ``requests.post`` in ``app/verify/providers.py``, and
    ``.env`` carries live credentials. Five registration tests posted a form
    without patching ``send_sms`` and each suite run sent five real texts to
    555 numbers (180 undelivered messages on the Twilio bill by 9/3). Stub the
    one choke point for the whole suite; a test that wants to assert on the
    provider's own behavior patches ``app.verify.providers.requests.post``
    itself, and that inner patch wins.

    The stub answers like a happy Twilio: 200, ``{"status": "approved"}``, so
    ``twilio_verify_check`` reads as a correct code and ``send_sms`` returns
    True. Tests that need a failure patch the provider explicitly.

    Uses ``mock.patch`` rather than the ``monkeypatch`` fixture on purpose:
    depending on ``monkeypatch`` here would pull it earlier in every test's
    fixture order, so it would tear down after DB fixtures. A test that
    monkeypatches ``db.session.commit`` to raise then blows up in its own
    DB teardown.
    """
    fake = MagicMock(name="providers.requests.post[stubbed]")
    fake.return_value = MagicMock(
        status_code=200, json=lambda: {"status": "approved"})
    with patch("app.verify.providers.requests.post", fake):
        yield fake
