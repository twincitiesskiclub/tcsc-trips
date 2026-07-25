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
        found = published_practices().filter(Practice.date >= soon).all()
        assert [p.id for p in found] == [live.id]
    finally:
        db_session.delete(draft)
        db_session.delete(live)
        db_session.commit()


def test_no_member_facing_query_uses_bare_practice_query():
    """Guard the rule itself: these modules must go through the helper."""
    import pathlib

    watched = [
        "app/scheduler.py",
        "app/slack/practices/refresh.py",
        "app/agent/routines/morning_check.py",
        "app/agent/routines/lead_verification.py",
        "app/agent/routines/weekly_summary.py",
        "app/agent/routines/pre_practice.py",
    ]
    offenders = []
    for rel in watched:
        text = pathlib.Path(rel).read_text()
        for num, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            code = line.split("#", 1)[0]
            if "Practice.query" in code and "published_practices" not in code:
                offenders.append(f"{rel}:{num}")
    assert not offenders, (
        "these lines read Practice.query directly, which would include draft "
        "practices on a member-visible surface; replace with "
        f"published_practices() from app.practices.service: {offenders}"
    )
