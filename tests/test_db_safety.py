"""Tests for the suite-wide local-DB safety guard (``tests/conftest.py``)."""
import os

import pytest

from tests._db_guard import LOCAL_TEST_DB, bypass_enabled, db_host, is_local_db


def test_db_host_parses_remote():
    assert db_host("postgresql://u:p@prod.example.com:5432/app") == "prod.example.com"


def test_db_host_parses_local():
    assert db_host(LOCAL_TEST_DB) == "localhost"


def test_remote_url_is_not_local():
    assert not is_local_db("postgresql://u:p@db.internal.render.com:5432/app")


def test_local_url_is_local():
    assert is_local_db(LOCAL_TEST_DB)


def test_live_database_url_is_local():
    """The load-bearing guarantee: even if DATABASE_URL was exported pointing at
    a remote/prod host, pytest_configure must have pinned it back to a local host
    before any test runs."""
    if bypass_enabled():
        pytest.skip("guard intentionally bypassed via TCSC_ALLOW_NONLOCAL_TEST_DB")
    url = os.environ.get("DATABASE_URL", "")
    assert is_local_db(url), (
        f"DATABASE_URL resolved to non-local host {db_host(url)!r} ({url!r})"
    )
