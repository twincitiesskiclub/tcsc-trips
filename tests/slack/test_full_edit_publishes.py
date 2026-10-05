"""The Slack full edit modal's post-save step makes a complete practice visible."""

from datetime import datetime
from unittest.mock import MagicMock

from app.models import db
from app.practices.models import Practice, PracticeLocation, PracticeType
from app.slack import bolt_app


def test_full_edit_post_save_publishes(db_session, monkeypatch):
    db.session.rollback()
    location = PracticeLocation(name="TEST A2 Slack Location")
    ptype = PracticeType(name="TEST A2 Slack Type")
    practice = Practice(date=datetime(2099, 4, 9, 18, 5), day_of_week="Thursday",
                        is_draft=True, leads_needed=2)
    practice.practice_types = [ptype]
    db.session.add_all([location, ptype, practice])
    db.session.flush()
    practice.location_id = location.id
    db.session.commit()
    ids = (practice.id, location.id, ptype.id)
    monkeypatch.setattr("app.slack.practices.refresh_practice_posts",
                        lambda *a, **k: {"announcement": {"skipped": "absent"}})
    try:
        bolt_app._run_practice_edit_full_post_save(
            practice_id=ids[0], user_id="U0TEST", should_notify=False,
            had_root=False, previous_date=practice.date, previous_location_id=None,
            previous_plan_reactions=None, client=MagicMock(), logger=MagicMock(),
        )
        db.session.expire_all()
        assert db.session.get(Practice, ids[0]).is_draft is False
    finally:
        db.session.rollback()
        p = db.session.get(Practice, ids[0])
        if p is not None:
            db.session.delete(p)
        db.session.commit()
        for model, row_id in ((PracticeLocation, ids[1]), (PracticeType, ids[2])):
            row = db.session.get(model, row_id)
            if row is not None:
                db.session.delete(row)
        db.session.commit()
