"""Draft practices must never reach a member-visible surface."""

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


def _make(is_draft, when):
    p = Practice(
        date=when,
        day_of_week=when.strftime("%A"),
        status=PracticeStatus.SCHEDULED.value,
        is_draft=is_draft,
    )
    db.session.add(p)
    return p


def test_published_practices_excludes_drafts(db_session):
    soon = datetime.utcnow() + timedelta(days=2)
    draft = _make(True, soon)
    live = _make(False, soon + timedelta(hours=1))
    db_session.commit()

    try:
        found = {p.id for p in published_practices().all()}
        assert live.id in found
        assert draft.id not in found, "a draft practice leaked into published_practices()"
    finally:
        db_session.delete(draft)
        db_session.delete(live)
        db_session.commit()


def test_published_practices_is_chainable(db_session):
    soon = datetime.utcnow() + timedelta(days=2)
    draft = _make(True, soon)
    live = _make(False, soon)
    db_session.commit()

    try:
        # Membership assertions rather than exact list equality: this runs
        # against the real local dev database, which may already contain
        # unrelated practices in this date range. Exact equality would fail
        # spuriously for any developer who has run ./scripts/dev.sh and
        # created practices of their own.
        ids = [p.id for p in published_practices().filter(Practice.date >= soon).all()]
        assert live.id in ids
        assert draft.id not in ids, "a draft practice leaked through a chained filter"
    finally:
        db_session.delete(draft)
        db_session.delete(live)
        db_session.commit()


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
