"""Shared fixtures for tests/practices/.

CRITICAL — read before writing a new test in this package:

1. The database these tests run against is the REAL LOCAL DEVELOPMENT
   DATABASE (postgresql://tcsc:tcsc@localhost:5432/tcsc_trips), not a
   throwaway test database. `db.create_all()` and `db.drop_all()` are
   FORBIDDEN anywhere in this package — they would wipe or recreate schema
   against real, currently-in-use data.

2. Every row a test creates must be deleted in a `try/finally` around the
   assertions, so cleanup runs even when an assertion fails. A test that
   only cleans up on the happy path leaves debris in the dev database the
   moment it starts failing — which is exactly how past debris ("Theodore
   Wirth" / "Intervals" orphan rows, an orphan draft Practice) got left
   behind and mistaken for real seeded data by later work.

3. Test data must be unmistakably fake:
   - Dates must use year 2099 (or later), never a real near-term date —
     the dev DB has real practices scheduled in the near future, and a
     collision has previously corrupted real data.
   - Names/strings must carry an unmistakable prefix, e.g. `"TEST "`, so a
     leaked row is immediately recognizable as test debris rather than
     something a human might have entered.

4. Queries in assertions must be scoped to the rows the test itself
   created (filter by id, by the test's own name prefix, etc.). An
   unscoped `Model.query.count()` will pass or fail depending on whatever
   else happens to be sitting in the dev database at the time — it is not
   a reliable assertion and has caused false failures before.

This conftest provides the `app` / `db_session` fixture pair that most
files in this package already hand-roll individually. Per-file fixtures of
the same name take precedence over these (pytest fixture resolution favors
the closer scope), so existing test files keep working unchanged. New
tests that don't define their own `app`/`db_session` get these for free.
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
