from datetime import date

import pytest

from app import create_app
from app.models import db, Season, User, UserSeason
from app.constants import UserSeasonStatus

EMAILS = ("rev-flagged@test.com", "rev-dupe-new@test.com", "rev-dupe-old@test.com")


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user"] = {"email": "admin@twincitiesskiclub.org"}  # match ALLOWED_EMAIL_DOMAIN
    return c


@pytest.fixture
def fixtures(app):
    with app.app_context():
        s = Season(name="Rev Test", year=2097, price_cents=15000, season_type="winter",
                   start_date=date(2097, 11, 1), end_date=date(2098, 3, 1))
        old = Season(name="Rev Old", year=2087, price_cents=15000, season_type="winter",
                     start_date=date(2087, 11, 1), end_date=date(2088, 3, 1))
        flagged = User(email=EMAILS[0], first_name="Flag", last_name="Ged")
        dupe_new = User(email=EMAILS[1], first_name="Dana", last_name="Dupe",
                        date_of_birth=date(1990, 5, 5))
        dupe_old = User(email=EMAILS[2], first_name="Dana", last_name="Dupe",
                        date_of_birth=date(1990, 5, 5))
        db.session.add_all([s, old, flagged, dupe_new, dupe_old])
        db.session.commit()
        db.session.add_all([
            UserSeason(user_id=flagged.id, season_id=s.id,
                       registration_type="new", registration_date=date.today(),
                       status=UserSeasonStatus.PENDING_LOTTERY, needs_review=True,
                       review_note="no verified phone"),
            UserSeason(user_id=dupe_new.id, season_id=s.id,
                       registration_type="new", registration_date=date.today(),
                       status=UserSeasonStatus.PENDING_LOTTERY),
            UserSeason(user_id=dupe_old.id, season_id=old.id,
                       registration_type="new", registration_date=date(2087, 10, 1),
                       status=UserSeasonStatus.ACTIVE),
        ])
        db.session.commit()
        yield s.id
        UserSeason.query.filter(UserSeason.user_id.in_(
            [flagged.id, dupe_new.id, dupe_old.id])).delete(synchronize_session='fetch')
        db.session.expire_all()
        for e in EMAILS:
            db.session.delete(User.query.filter_by(email=e).one())
        db.session.delete(Season.query.get(s.id))
        db.session.delete(Season.query.get(old.id))
        db.session.commit()


def test_review_page_lists_flagged_and_fuzzy_dupes(client, fixtures):
    resp = client.get(f"/admin/registration-review?season_id={fixtures}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "rev-flagged@test.com" in html      # needs_review list
    assert "no verified phone" in html         # review_note explains the flag
    assert "rev-dupe-new@test.com" in html     # fuzzy-match list
    assert "rev-dupe-old@test.com" in html     # shown as the possible match
