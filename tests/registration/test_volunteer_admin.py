"""Volunteer answers surface to admins: season CSV export + users grid JSON."""
import csv
import io
from datetime import date

import pytest

from app import create_app
from app.constants import UserSeasonStatus
from app.models import db, Season, User, UserSeason

EMAIL = "vol-admin@test.com"


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
        sess["user"] = {"email": "admin@twincitiesskiclub.org"}
    return c


@pytest.fixture
def fixtures(app):
    with app.app_context():
        s = Season(name="Vol Admin Test", year=2096, price_cents=15000,
                   season_type="winter",
                   start_date=date(2096, 11, 1), end_date=date(2097, 3, 1))
        u = User(email=EMAIL, first_name="Vola", last_name="Dmin")
        db.session.add_all([s, u])
        db.session.commit()
        us = UserSeason(user_id=u.id, season_id=s.id,
                        registration_type="new",
                        registration_date=date(2096, 10, 1),
                        status=UserSeasonStatus.ACTIVE,
                        volunteer_interests=["event_volunteer", "committee"],
                        volunteer_committees=["social"])
        db.session.add(us)
        db.session.commit()
        yield {"season_id": s.id, "user_id": u.id}
        db.session.rollback()
        UserSeason.query.filter_by(season_id=s.id).delete()
        db.session.delete(User.query.get(u.id))
        db.session.delete(Season.query.get(s.id))
        db.session.commit()


def test_csv_export_includes_volunteer_columns(client, fixtures):
    resp = client.get(f"/admin/seasons/{fixtures['season_id']}/export")
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
    header = rows[0]
    assert "Volunteer Interests" in header
    assert "Volunteer Committees" in header
    row = next(r for r in rows[1:] if EMAIL in r)
    interests = row[header.index("Volunteer Interests")]
    committees = row[header.index("Volunteer Committees")]
    assert "Volunteer at an event" in interests
    assert "Join a committee" in interests
    assert "Social" in committees


def test_users_data_includes_volunteer_map_and_labels(client, fixtures):
    resp = client.get("/admin/users/data")
    assert resp.status_code == 200
    data = resp.get_json()

    opts = data["volunteer_options"]
    assert opts["interests"]["practice_lead"] == "Lead a group at practice"
    assert "social" in opts["committees"]

    user = next(u for u in data["users"] if u["email"] == EMAIL)
    season_key = str(fixtures["season_id"])
    assert user["volunteer"][season_key] == {
        "interests": ["event_volunteer", "committee"],
        "committees": ["social"],
    }


def test_user_detail_renders_volunteer_answer(client, fixtures):
    resp = client.get(f"/admin/users/{fixtures['user_id']}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Volunteer at an event" in html
    assert "Join a committee" in html
    assert "Social (community events)" in html


def test_users_data_omits_unanswered_seasons(client, fixtures, app):
    with app.app_context():
        us = UserSeason.get_for_user_season(
            fixtures["user_id"], fixtures["season_id"])
        us.volunteer_interests = None
        us.volunteer_committees = None
        db.session.commit()

    resp = client.get("/admin/users/data")
    user = next(u for u in resp.get_json()["users"] if u["email"] == EMAIL)
    assert user["volunteer"] == {}
