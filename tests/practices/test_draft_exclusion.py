"""Draft practices must never reach a member-visible surface.

Year 2099 dates and a "TEST " marker per tests/practices/conftest.py. These
rows used to sit at `utcnow() + 2 days` with cleanup that never rolled back
first, which is specifically dangerous on this branch: check the branch out,
run the suite before `flask db upgrade`, and published_practices() filters on
a not-yet-existing Practice.is_draft column -> UndefinedColumn -> aborted
transaction. Both practices were already committed by then, so the cleanup
raised PendingRollbackError and both leaked -- including a phantom
member-visible practice two days out.
"""

from datetime import datetime, timedelta

import pytest

from app import create_app
from app.models import db
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice
from app.practices.service import published_practices


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session


# Reserved for this module: no other suite uses November 2099 or 21:35.
_SLOT = datetime(2099, 11, 10, 21, 35)


def _make(is_draft, when):
    p = Practice(
        date=when,
        day_of_week=when.strftime("%A"),
        status=PracticeStatus.SCHEDULED.value,
        is_draft=is_draft,
        logistics_notes="TEST draft exclusion",
    )
    db.session.add(p)
    return p


def _cleanup(practice_ids):
    """Rollback FIRST — see the module docstring for the specific way this
    suite's session gets poisoned before cleanup runs.
    """
    db.session.rollback()
    for practice_id in practice_ids:
        stored = db.session.get(Practice, practice_id)
        if stored is not None:
            db.session.delete(stored)
    db.session.commit()


def test_published_practices_excludes_drafts(db_session):
    draft = _make(True, _SLOT)
    live = _make(False, _SLOT + timedelta(hours=1))
    db_session.commit()
    ids = [draft.id, live.id]
    draft_id, live_id = ids

    try:
        found = {p.id for p in published_practices().all()}
        assert live_id in found
        assert draft_id not in found, "a draft practice leaked into published_practices()"
    finally:
        _cleanup(ids)


def test_published_practices_is_chainable(db_session):
    soon = _SLOT
    draft = _make(True, soon)
    live = _make(False, soon)
    db_session.commit()
    ids = [draft.id, live.id]
    draft_id, live_id = ids

    try:
        # Membership assertions rather than exact list equality: this runs
        # against the real local dev database, which may already contain
        # unrelated practices in this date range. Exact equality would fail
        # spuriously for any developer who has run ./scripts/dev.sh and
        # created practices of their own.
        found = [p.id for p in published_practices().filter(Practice.date >= soon).all()]
        assert live_id in found
        assert draft_id not in found, "a draft practice leaked through a chained filter"
    finally:
        _cleanup(ids)


def test_no_member_facing_query_uses_bare_practice_query():
    """Guard the rule itself: these modules must go through the helper.

    Flags any use of `Practice.query.` that is NOT immediately followed by
    `get(` or `get_or_404(`. Fetching one specific practice by id (e.g. to
    RSVP against it, or to render an admin detail page) is not a member-visible
    listing and must not be forced through published_practices(). This is why
    app/slack/commands.py can be watched even though it also contains a
    legitimate `Practice.query.get(practice_id)` lookup in `_handle_rsvp_command`
    — that line doesn't match (ends in get(), which is allowed). Any listing
    query shape (filter, filter_by, order_by, options, all) must go through
    published_practices() to exclude draft practices.
    """
    import pathlib
    import re

    watched = [
        "app/scheduler.py",
        "app/slack/practices/refresh.py",
        "app/agent/routines/morning_check.py",
        "app/agent/routines/lead_verification.py",
        "app/agent/routines/weekly_summary.py",
        "app/agent/routines/pre_practice.py",
        "app/slack/commands.py",
        "app/slack/practices/app_home.py",
        "app/slack/practices/coach_review.py",
    ]
    offenders = []
    for rel in watched:
        text = pathlib.Path(rel).read_text()
        for num, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            code = line.split("#", 1)[0]
            # Flag Practice.query.X where X is NOT get( or get_or_404(
            # This catches all listing patterns: filter, filter_by, order_by, options, all, etc.
            if "Practice.query." in code and "published_practices" not in code:
                # Check if it's a safe single-by-id lookup
                if not re.search(r"Practice\.query\.(get|get_or_404)\(", code):
                    offenders.append(f"{rel}:{num}")
    assert not offenders, (
        "these lines read Practice.query.* directly in a way that would include "
        "draft practices on a member-visible surface; replace with "
        "published_practices() from app.practices.service: "
        f"{offenders}"
    )
