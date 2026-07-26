"""Readiness gating — the poll must not open against incomplete drafts."""

import uuid
from datetime import datetime

import pytest

from app import create_app
from app.models import db
from app.practices.drafting import is_ready, missing_fields, readiness_summary
from app.practices.models import Practice, PracticeLocation, PracticeType

# Far enough out that no real seeded/dev practice data could ever land here —
# the local dev DB already has real Tuesday/Thursday practices in the near
# future, and colliding with one made an earlier pass at this test corrupt
# real data (see _cleanup below for how that's now avoided).
_SLOT_A = datetime(2099, 1, 6, 18, 15)
_SLOT_B = datetime(2099, 1, 8, 18, 15)
_SLOT_C = datetime(2099, 1, 10, 18, 15)


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session


def _location():
    # Name deliberately distinct from real dev data ("Theodore Wirth" already
    # exists locally) — PracticeLocation.name has no unique constraint, so a
    # collision wouldn't error, but it would leave an indistinguishable
    # duplicate of real data behind.
    loc = PracticeLocation(name=f"TEST Readiness Location {uuid.uuid4().hex[:8]}")
    db.session.add(loc)
    db.session.flush()
    return loc


def _type():
    # Same reasoning as _location(): "Intervals" already exists in the local
    # dev database, and practice_types.name IS unique there — reusing it
    # raises IntegrityError instead of just duplicating.
    #
    # The uuid suffix matters beyond that: with a FIXED name, one leaked row
    # made this file permanently unrunnable. _cleanup used to skip its
    # rollback, so a poisoned session left the type behind, and every
    # subsequent run then died at this flush with IntegrityError until
    # somebody deleted the row by hand.
    t = PracticeType(name=f"TEST Readiness Type {uuid.uuid4().hex[:8]}")
    db.session.add(t)
    db.session.flush()
    return t


def _cleanup(practice_ids, location_ids, type_ids):
    """Scoped cleanup keyed on ids captured before the call under test.

    Practices are fetched and deleted through the ORM (not a bulk
    `.query.delete()`) so SQLAlchemy also clears the matching rows out of the
    `practice_types_junction` secondary table — a bulk delete bypasses that
    relationship bookkeeping and leaves the junction row behind, which then
    blocks deleting the PracticeType with a FK violation. Practices must be
    removed before their location/type so nothing is ever left referencing a
    row this function already deleted.

    Rolls back FIRST. Without it, a failing assertion above left the
    transaction aborted and this function's own first query raised
    PendingRollbackError — so the cleanup that exists to prevent debris was
    itself the thing that leaked it.

    Callers pass plain ints captured before the `try`, never `obj.id`
    evaluated at the finally site: Python evaluates the arguments before
    calling, so on a poisoned session that attribute access hits SQLAlchemy's
    expired-attribute refresh and raises before the rollback below can run.
    """
    db.session.rollback()
    for pid in practice_ids:
        practice = db.session.get(Practice, pid)
        if practice is not None:
            db.session.delete(practice)
    db.session.flush()
    if type_ids:
        PracticeType.query.filter(PracticeType.id.in_(type_ids)).delete(synchronize_session=False)
    if location_ids:
        PracticeLocation.query.filter(PracticeLocation.id.in_(location_ids)).delete(synchronize_session=False)
    db.session.commit()


def test_bare_draft_is_not_ready(db_session):
    p = Practice(date=_SLOT_A, day_of_week="Tuesday", is_draft=True)
    db_session.add(p)
    db_session.commit()
    practice_ids = [p.id]

    try:
        assert is_ready(p) is False
        assert missing_fields(p) == ["location", "type"]
    finally:
        _cleanup(practice_ids, [], [])


def test_draft_with_location_and_type_is_ready(db_session):
    loc = _location()
    typ = _type()
    p = Practice(date=_SLOT_A, day_of_week="Tuesday", is_draft=True)
    p.location_id = loc.id
    p.practice_types = [typ]
    db_session.add(p)
    db_session.commit()
    practice_ids, location_ids, type_ids = [p.id], [loc.id], [typ.id]

    try:
        assert is_ready(p) is True
        assert missing_fields(p) == []
    finally:
        _cleanup(practice_ids, location_ids, type_ids)


def test_summary_counts_and_lists_incomplete(db_session):
    loc = _location()
    typ = _type()
    ready = Practice(date=_SLOT_A, day_of_week="Tuesday", is_draft=True)
    ready.location_id = loc.id
    ready.practice_types = [typ]
    bare = Practice(date=_SLOT_B, day_of_week="Thursday", is_draft=True)
    db_session.add_all([ready, bare])
    db_session.commit()
    practice_ids, location_ids, type_ids = [ready.id, bare.id], [loc.id], [typ.id]

    try:
        summary = readiness_summary([ready, bare])
        assert summary["total"] == 2
        assert summary["ready"] == 1
        assert [p.id for p, _ in summary["incomplete"]] == [bare.id]
        assert summary["incomplete"][0][1] == ["location", "type"]
    finally:
        _cleanup(practice_ids, location_ids, type_ids)


def test_incomplete_is_sorted_by_date_not_creation_order(db_session):
    # Created deliberately out of chronological order (middle, latest,
    # earliest) so a passing test can only mean readiness_summary() actually
    # sorts by date rather than happening to preserve insertion/query order.
    middle = Practice(date=_SLOT_B, day_of_week="Thursday", is_draft=True)
    latest = Practice(date=_SLOT_C, day_of_week="Saturday", is_draft=True)
    earliest = Practice(date=_SLOT_A, day_of_week="Tuesday", is_draft=True)
    db_session.add_all([middle, latest, earliest])
    db_session.commit()
    practice_ids = [middle.id, latest.id, earliest.id]

    try:
        summary = readiness_summary([middle, latest, earliest])
        assert [p.id for p, _ in summary["incomplete"]] == [
            earliest.id,
            middle.id,
            latest.id,
        ]
    finally:
        _cleanup(practice_ids, [], [])
