"""Stats builder for the daily season registration recap.

House fixture style: real Postgres dev DB, far-future season years and
@recap-test.com emails so nothing collides with real data, cleanup in
fixture teardown.
"""
from datetime import date, datetime, timedelta

import pytest

from app import create_app
from app.constants import UserSeasonStatus
from app.models import db, Season, User, UserSeason


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


# The recap covers the prior Central day; tests pin it to a fixed date so
# nothing depends on the clock. Windows are stored as naive UTC datetimes;
# noon UTC converts to the same Central calendar date, which keeps the
# expected day math readable.
FOR_DATE = date(2098, 1, 10)


def _utc_noon(d):
    return datetime(d.year, d.month, d.day, 12, 0, 0)


def _make_season(name, year, *, window_start, window_end, season_type="winter",
                 registration_limit=None, new_window=None):
    """new_window: optional (start_date, end_date) for the new-member window;
    window_start/end are the returning window."""
    s = Season(
        name=name, year=year, season_type=season_type,
        price_cents=15000, registration_limit=registration_limit,
        start_date=date(year, 11, 1), end_date=date(year + 1, 3, 1),
        returning_start=_utc_noon(window_start),
        returning_end=_utc_noon(window_end),
        new_start=_utc_noon(new_window[0]) if new_window else None,
        new_end=_utc_noon(new_window[1]) if new_window else None,
    )
    db.session.add(s)
    db.session.commit()
    return s


_user_seq = 0


def _make_reg(season, reg_date, *, reg_type="new",
              status=UserSeasonStatus.PENDING_LOTTERY, phone=None,
              interests=None, committees=None, needs_review=False):
    global _user_seq
    _user_seq += 1
    u = User(
        first_name="Recap", last_name=f"Tester{_user_seq}",
        email=f"recap-{_user_seq}@recap-test.com",
        phone_e164=phone,
    )
    db.session.add(u)
    db.session.flush()
    us = UserSeason(
        user_id=u.id, season_id=season.id, registration_type=reg_type,
        registration_date=reg_date, status=status, needs_review=needs_review,
        volunteer_interests=interests, volunteer_committees=committees,
    )
    db.session.add(us)
    db.session.commit()
    return us


@pytest.fixture
def clean(app):
    """Delete every row the tests created, newest tables first."""
    with app.app_context():
        yield
        seasons = Season.query.filter(Season.year >= 2097).all()
        for s in seasons:
            UserSeason.query.filter_by(season_id=s.id).delete()
        User.query.filter(User.email.like("%@recap-test.com")).delete(
            synchronize_session=False)
        for s in seasons:
            db.session.delete(s)
        db.session.commit()


@pytest.fixture
def season(app, clean):
    with app.app_context():
        yield _make_season(
            "Recap Winter 2098", 2098,
            window_start=FOR_DATE - timedelta(days=4),
            window_end=FOR_DATE + timedelta(days=16),
            registration_limit=200,
        )


def test_yesterday_split_and_season_totals(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE, reg_type="new")
        _make_reg(season, FOR_DATE, reg_type="new")
        _make_reg(season, FOR_DATE, reg_type="returning",
                  status=UserSeasonStatus.ACTIVE)
        _make_reg(season, FOR_DATE - timedelta(days=1), reg_type="new")
        stats = build_recap(season, FOR_DATE)
    assert stats["yesterday"] == {"new": 2, "returning": 1, "total": 3}
    assert stats["previous_day_total"] == 1
    assert stats["season_totals"]["total"] == 4
    assert stats["season_totals"]["new"] == 3
    assert stats["season_totals"]["returning"] == 1
    assert stats["season_totals"]["registration_limit"] == 200
    assert stats["season_totals"]["pct_of_limit"] == 2  # 4/200
    assert stats["season_id"] == season.id
    assert stats["for_date"] == FOR_DATE


def test_dropped_registrations_do_not_count(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE)
        _make_reg(season, FOR_DATE, status=UserSeasonStatus.DROPPED_VOLUNTARY)
        _make_reg(season, FOR_DATE, status=UserSeasonStatus.DROPPED_LOTTERY)
        stats = build_recap(season, FOR_DATE)
    assert stats["yesterday"]["total"] == 1
    assert stats["season_totals"]["total"] == 1


def test_no_limit_means_no_percentage(app, clean):
    from app.seasons.recap import build_recap
    with app.app_context():
        s = _make_season("Recap NoLimit 2098", 2098,
                         window_start=FOR_DATE - timedelta(days=4),
                         window_end=FOR_DATE + timedelta(days=16))
        stats = build_recap(s, FOR_DATE)
    assert stats["season_totals"]["registration_limit"] is None
    assert stats["season_totals"]["pct_of_limit"] is None
