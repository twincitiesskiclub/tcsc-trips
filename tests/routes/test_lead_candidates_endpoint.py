"""Lead candidates endpoint."""

from datetime import datetime
from unittest.mock import patch

import pytest

from app.models import db, User
from app.practices.models import Practice, PracticeLead

# Reserved test moment, owned solely by this module. Year 2099 per
# tests/practices/conftest.py: the sweep below deletes every practice at this
# exact timestamp regardless of who created it, which is only safe on a moment
# no real practice can occupy. It previously read 2026-08-04 18:15 -- a real
# Tuesday in the near future, at the exact time every other availability suite
# uses as "the club's practice slot" -- so a local bootstrap draft or a
# hand-created practice at that slot was deleted, with its lead assignments,
# three times per run. April 2099 and the 19:45 time are unused by any other
# suite, so even a same-date collision can't reach this module's rows.
_TEST_DATE = datetime(2099, 4, 7, 19, 45)


_TEST_EMAIL_PREFIX = "test.lead-candidates-endpoint-"


@pytest.fixture(autouse=True)
def cleanup_test_practices(db_session):
    # Pre-flight: the teardown below is an unconditional sweep of this exact
    # timestamp, so refuse to run at all if anything already occupies it
    # rather than deleting a row this suite didn't create.
    collisions = Practice.query.filter(Practice.date == _TEST_DATE).count()
    assert collisions == 0, (
        "Reserved test moment for lead-candidates tests already has "
        f"{collisions} practice(s); refusing to run against unexpected "
        "dev-db state"
    )
    yield
    db.session.rollback()
    for practice in Practice.query.filter(Practice.date == _TEST_DATE).all():
        PracticeLead.query.filter_by(practice_id=practice.id).delete()
        db.session.delete(practice)
    User.query.filter(User.email.like(f"{_TEST_EMAIL_PREFIX}%")).delete(
        synchronize_session=False
    )
    db.session.commit()


def _practice():
    p = Practice(date=_TEST_DATE, day_of_week="Tuesday",
                 leads_needed=3)
    db.session.add(p)
    db.session.commit()
    return p


def test_returns_ranked_candidates_and_capacity(admin_client, db_session):
    practice = _practice()
    fake = [{
        "user_id": 1, "name": "Ada L", "available": True, "responded": True,
        "stale": False, "led_in_block": 0, "led_last_90d": 2,
    }]

    with patch("app.routes.admin_practices.lead_candidates", return_value=fake):
        response = admin_client.get(f"/admin/practices/{practice.id}/lead-candidates")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["leads_needed"] == 3
    assert payload["candidates"] == fake


def test_reports_who_is_already_assigned(admin_client, db_session):
    # The brief's original test hardcodes user_id=7 (lead) / user_id=8
    # (coach), but practice_leads.user_id carries a real FK to users.id and
    # the local dev DB's users table doesn't have rows at those ids -- an
    # unscoped insert would 500 on a ForeignKeyViolation rather than
    # exercising the endpoint. Real TEST-prefixed users stand in for 7/8 so
    # the FK is satisfied; the assertion below still checks the same thing
    # the brief cares about: only the role='lead' row is reported assigned.
    lead_user = User(
        first_name="TEST", last_name="Lead",
        email=f"{_TEST_EMAIL_PREFIX}lead@example.invalid", status="ACTIVE",
    )
    coach_user = User(
        first_name="TEST", last_name="Coach",
        email=f"{_TEST_EMAIL_PREFIX}coach@example.invalid", status="ACTIVE",
    )
    db_session.add_all([lead_user, coach_user])
    db_session.flush()

    practice = _practice()
    db_session.add(PracticeLead(practice_id=practice.id, user_id=lead_user.id, role="lead"))
    db_session.add(PracticeLead(practice_id=practice.id, user_id=coach_user.id, role="coach"))
    db_session.commit()

    with patch("app.routes.admin_practices.lead_candidates", return_value=[]):
        response = admin_client.get(f"/admin/practices/{practice.id}/lead-candidates")

    assert response.get_json()["assigned"] == [lead_user.id], "coaches are not leads"


def test_unknown_practice_is_404(admin_client):
    with patch("app.routes.admin_practices.lead_candidates", return_value=[]):
        assert admin_client.get("/admin/practices/999999/lead-candidates").status_code == 404
