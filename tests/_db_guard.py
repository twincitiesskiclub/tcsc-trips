"""Helpers for the test-suite database safety guard.

See ``tests/conftest.py`` for how these are used. Kept in a separate module so
both the conftest and the guard's own tests can import them.
"""
import os
from urllib.parse import urlparse

# The only database the test suite is allowed to touch.
LOCAL_TEST_DB = "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"

# Hosts considered local. "" covers unix-socket URLs (inherently local).
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}

# Deliberate escape hatch for the rare case of a non-localhost CI host.
BYPASS_ENV = "TCSC_ALLOW_NONLOCAL_TEST_DB"


def db_host(url):
    """Return the lowercased hostname from a DB URL ('?' if unparseable)."""
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return "?"


def is_local_db(url):
    """True if the URL points at a local database host."""
    return db_host(url) in LOCAL_HOSTS


def bypass_enabled():
    """True if the operator has explicitly opted out of the guard."""
    return os.environ.get(BYPASS_ENV) == "1"
