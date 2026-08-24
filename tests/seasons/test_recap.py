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


def _make_season(name, year, *, window_start, window_end, season_type="recaptest",
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


def test_window_day_math(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        stats = build_recap(season, FOR_DATE)
    w = stats["windows"]["returning"]
    # Window opened 4 days before FOR_DATE: day 5 of 21, 16 days left.
    assert w["is_open"] is True
    assert w["day_number"] == 5
    assert w["days_remaining"] == 16
    assert w["length_days"] == 21
    assert stats["windows"]["new"] is None


def test_should_post_gate(app, clean):
    from app.seasons.recap import should_post
    with app.app_context():
        s = _make_season(
            "Recap Gate 2098", 2098,
            window_start=date(2098, 1, 6), window_end=date(2098, 1, 20),
            new_window=(date(2098, 1, 13), date(2098, 1, 27)),
        )
        assert should_post(s, date(2098, 1, 5)) is False   # before any window
        assert should_post(s, date(2098, 1, 6)) is True    # first day
        assert should_post(s, date(2098, 1, 22)) is True   # new window open
        assert should_post(s, date(2098, 2, 3)) is True    # 7 days after last end
        assert should_post(s, date(2098, 2, 4)) is False   # 8 days after


def test_should_post_false_without_windows(app, clean):
    from app.seasons.recap import should_post
    with app.app_context():
        s = Season(name="Recap Bare 2097", year=2097, season_type="winter",
                   price_cents=15000,
                   start_date=date(2097, 11, 1), end_date=date(2098, 3, 1))
        db.session.add(s)
        db.session.commit()
        assert should_post(s, date(2097, 12, 1)) is False


def test_prior_season_comparison_at_same_day_offset(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        prior = _make_season(
            "Recap Winter 2097", 2097,
            window_start=date(2097, 1, 6), window_end=date(2097, 1, 26))
        # Prior season: 2 regs inside the first 5 window days, 1 later.
        _make_reg(prior, date(2097, 1, 6))
        _make_reg(prior, date(2097, 1, 10))
        _make_reg(prior, date(2097, 1, 20))
        _make_reg(season, FOR_DATE)
        stats = build_recap(season, FOR_DATE)
    # FOR_DATE is day 5 of the current window (offset 4 from its anchor):
    # cutoff in the prior season is Jan 10, so 2 of its 3 count.
    assert stats["prior_season"] == {
        "name": "Recap Winter 2097",
        "count_at_same_point": 2,
        "final_count": 3,
    }


def test_prior_season_requires_same_type(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        other = _make_season(
            "Recap Summer 2097", 2097, season_type="recaptest-other",
            window_start=date(2097, 1, 6), window_end=date(2097, 1, 26))
        _make_reg(other, date(2097, 1, 6))
        stats = build_recap(season, FOR_DATE)
    assert stats["prior_season"] is None


def test_prior_season_skips_empty_seasons(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_season("Recap Empty 2097", 2097,
                     window_start=date(2097, 6, 1), window_end=date(2097, 6, 20))
        older = _make_season(
            "Recap Older 2097", 2097,
            window_start=date(2097, 1, 6), window_end=date(2097, 1, 26))
        _make_reg(older, date(2097, 1, 6))
        stats = build_recap(season, FOR_DATE)
    # The empty nearer season is skipped; the older one with data is used.
    assert stats["prior_season"]["name"] == "Recap Older 2097"


def test_volunteer_summary_counts_yesterday_only(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE,
                  interests=["practice_lead", "committee"],
                  committees=["social"])
        _make_reg(season, FOR_DATE, interests=["practice_lead"])
        _make_reg(season, FOR_DATE, interests=[])          # declined
        _make_reg(season, FOR_DATE - timedelta(days=1),
                  interests=["event_volunteer"])           # not yesterday
        stats = build_recap(season, FOR_DATE)
    v = stats["volunteer"]
    assert v["answered"] == 2
    assert v["of"] == 3
    assert v["interests"] == {
        "Lead a group at practice": 2, "Join a committee": 1}
    assert v["committees"] == {"Social (community events)": 1}


def test_needs_review_counts_whole_season(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE - timedelta(days=3), needs_review=True)
        _make_reg(season, FOR_DATE, needs_review=True)
        _make_reg(season, FOR_DATE)
        stats = build_recap(season, FOR_DATE)
    assert stats["needs_review"] == 2


def test_highlight_record_day(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE - timedelta(days=2))
        _make_reg(season, FOR_DATE)
        _make_reg(season, FOR_DATE)
        stats = build_recap(season, FOR_DATE)
    assert any("Biggest day" in line for line in stats["highlights"])


def test_no_record_highlight_for_single_registration(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE)
        stats = build_recap(season, FOR_DATE)
    assert not any("Biggest day" in line for line in stats["highlights"])


def test_highlight_milestone_crossed(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        for _ in range(48):
            _make_reg(season, FOR_DATE - timedelta(days=2))
        for _ in range(3):
            _make_reg(season, FOR_DATE)
        stats = build_recap(season, FOR_DATE)
    assert any("50" in line and "Crossed" in line
               for line in stats["highlights"])


def test_highlight_household(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE, phone="+16125550190")
        _make_reg(season, FOR_DATE, phone="+16125550190")
        _make_reg(season, FOR_DATE, phone="+16125550191")
        stats = build_recap(season, FOR_DATE)
    assert any("household" in line for line in stats["highlights"])


def test_no_highlights_on_quiet_day(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        stats = build_recap(season, FOR_DATE)
    assert stats["highlights"] == []
