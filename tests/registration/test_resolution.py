from datetime import datetime, timedelta, date

import pytest

from app import create_app
from app.constants import UserSeasonStatus, UserStatus
from app.models import db, Season, User, UserSeason
from app.seasons import resolution

PHONE_A = "+16125550301"
PHONE_B = "+16125550302"


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def ctx(app):
    with app.app_context():
        yield


@pytest.fixture
def season(ctx):
    now = datetime.utcnow()
    s = Season(name="Resolution Test", year=2098, price_cents=15000,
               season_type='winter',
               start_date=date(2098, 11, 1), end_date=date(2099, 3, 1),
               returning_start=now - timedelta(days=1),
               returning_end=now + timedelta(days=30),
               new_start=now - timedelta(days=1),
               new_end=now + timedelta(days=30))
    db.session.add(s)
    db.session.commit()
    yield s
    UserSeason.query.filter_by(season_id=s.id).delete()
    db.session.delete(Season.query.get(s.id))
    db.session.commit()


def make_user(email, phone, first="Test"):
    u = User(email=email, first_name=first, last_name="Case",
             status=UserStatus.PENDING, phone_e164=phone,
             phone="612-555-0301", date_of_birth=date(1990, 1, 1),
             tshirt_size="M", emergency_contact_name="Em",
             emergency_contact_relation="friend",
             emergency_contact_phone="612-555-0999",
             emergency_contact_email="em@test.com")
    db.session.add(u)
    db.session.commit()
    return u


def ident(phone, user_id=None):
    return {'phone_e164': phone, 'user_id': user_id,
            'ts': datetime.utcnow().isoformat()}


def cleanup(*users):
    for u in users:
        UserSeason.query.filter_by(user_id=u.id).delete()
        db.session.delete(u)
    db.session.commit()


def test_no_identity_asks_for_phone(season):
    outcome, ctxd = resolution.resolve_registration_step(
        None, season, datetime.utcnow())
    assert outcome == resolution.VERIFY_PHONE


def test_verified_phone_no_match_is_new(season):
    outcome, ctxd = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow())
    assert outcome == resolution.WIZARD_NEW
    assert ctxd['member_type'] == 'new'
    assert ctxd['first_name'] is None


def test_shared_phone_needs_email(season):
    a = make_user("share-a@test.com", PHONE_B, "Jane")
    b = make_user("share-b@test.com", PHONE_B, "Sam")
    try:
        outcome, ctxd = resolution.resolve_registration_step(
            ident(PHONE_B), season, datetime.utcnow())
        assert outcome == resolution.NEED_EMAIL
    finally:
        cleanup(a, b)


def test_resolved_active_history_is_returning(season):
    u = make_user("ret@test.com", PHONE_A, "Rita")
    past = Season(name="Past", year=2097, price_cents=1000,
                  season_type='winter',
                  start_date=date(2097, 11, 1), end_date=date(2098, 3, 1))
    db.session.add(past)
    db.session.commit()
    db.session.add(UserSeason(user_id=u.id, season_id=past.id,
                              registration_type='new',
                              registration_date=date(2097, 10, 1),
                              status=UserSeasonStatus.ACTIVE))
    db.session.commit()
    try:
        outcome, ctxd = resolution.resolve_registration_step(
            ident(PHONE_A, u.id), season, datetime.utcnow())
        assert outcome == resolution.WIZARD_RETURNING
        assert ctxd['first_name'] == "Rita"
    finally:
        UserSeason.query.filter_by(user_id=u.id).delete()
        db.session.commit()
        cleanup(u)
        db.session.delete(Season.query.get(past.id))
        db.session.commit()


def test_resolved_without_active_history_is_new(season):
    """Registered last year, lost the lottery. Known row, new pricing."""
    u = make_user("lost@test.com", PHONE_A, "Lou")
    try:
        outcome, ctxd = resolution.resolve_registration_step(
            ident(PHONE_A, u.id), season, datetime.utcnow())
        assert outcome == resolution.WIZARD_NEW
        assert ctxd['first_name'] == "Lou"
    finally:
        cleanup(u)


def test_already_registered_stops_before_the_form(season):
    u = make_user("dupe@test.com", PHONE_A, "Dana")
    db.session.add(UserSeason(user_id=u.id, season_id=season.id,
                              registration_type='new',
                              registration_date=date.today(),
                              status=UserSeasonStatus.PENDING_LOTTERY))
    db.session.commit()
    try:
        outcome, ctxd = resolution.resolve_registration_step(
            ident(PHONE_A, u.id), season, datetime.utcnow())
        assert outcome == resolution.ALREADY_REGISTERED
        assert ctxd['status'] == UserSeasonStatus.PENDING_LOTTERY
        assert ctxd['season_name'] == season.name
    finally:
        cleanup(u)


def test_dropped_registration_does_not_block(season):
    u = make_user("dropped@test.com", PHONE_A, "Drew")
    db.session.add(UserSeason(user_id=u.id, season_id=season.id,
                              registration_type='new',
                              registration_date=date.today(),
                              status=UserSeasonStatus.DROPPED_LOTTERY))
    db.session.commit()
    try:
        outcome, _ = resolution.resolve_registration_step(
            ident(PHONE_A, u.id), season, datetime.utcnow())
        assert outcome == resolution.WIZARD_NEW
    finally:
        cleanup(u)


def test_window_not_yet_open_carries_the_date(season):
    season.new_start = datetime.utcnow() + timedelta(days=4)
    season.new_end = datetime.utcnow() + timedelta(days=40)
    db.session.commit()
    outcome, ctxd = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow())
    assert outcome == resolution.WINDOW_NOT_YET_OPEN
    assert ctxd['member_type'] == 'new'
    assert ctxd['opens_at'] == season.new_start


def test_window_ended_carries_the_date(season):
    season.new_start = datetime.utcnow() - timedelta(days=40)
    season.new_end = datetime.utcnow() - timedelta(days=4)
    db.session.commit()
    outcome, ctxd = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow())
    assert outcome == resolution.WINDOW_ENDED
    assert ctxd['closed_at'] == season.new_end


def test_unconfigured_window_reads_as_not_yet_open(season):
    season.new_start = None
    season.new_end = None
    db.session.commit()
    outcome, ctxd = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow())
    assert outcome == resolution.WINDOW_NOT_YET_OPEN
    assert ctxd['opens_at'] is None


def test_valid_invite_bypasses_a_closed_window(season):
    season.new_start = datetime.utcnow() - timedelta(days=40)
    season.new_end = datetime.utcnow() - timedelta(days=4)
    db.session.commit()
    outcome, _ = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow(),
        invite_payload={'season_id': season.id, 'email': 'x@test.com'})
    assert outcome == resolution.WIZARD_NEW


def test_invite_for_another_season_does_not_bypass(season):
    season.new_start = datetime.utcnow() - timedelta(days=40)
    season.new_end = datetime.utcnow() - timedelta(days=4)
    db.session.commit()
    outcome, _ = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow(),
        invite_payload={'season_id': season.id + 9999, 'email': 'x@test.com'})
    assert outcome == resolution.WINDOW_ENDED


def test_already_registered_beats_a_closed_window(season):
    """Precedence: 'you're already in' is more useful than 'you're too late'."""
    u = make_user("both@test.com", PHONE_A, "Bo")
    db.session.add(UserSeason(user_id=u.id, season_id=season.id,
                              registration_type='new',
                              registration_date=date.today(),
                              status=UserSeasonStatus.PENDING_LOTTERY))
    season.new_start = datetime.utcnow() - timedelta(days=40)
    season.new_end = datetime.utcnow() - timedelta(days=4)
    db.session.commit()
    try:
        outcome, _ = resolution.resolve_registration_step(
            ident(PHONE_A, u.id), season, datetime.utcnow())
        assert outcome == resolution.ALREADY_REGISTERED
    finally:
        cleanup(u)


def test_shared_phone_beats_already_registered(season):
    """Unresolved multi-match cannot claim anyone's registration."""
    a = make_user("multi-a@test.com", PHONE_B, "Jane")
    b = make_user("multi-b@test.com", PHONE_B, "Sam")
    db.session.add(UserSeason(user_id=a.id, season_id=season.id,
                              registration_type='new',
                              registration_date=date.today(),
                              status=UserSeasonStatus.PENDING_LOTTERY))
    db.session.commit()
    try:
        outcome, _ = resolution.resolve_registration_step(
            ident(PHONE_B), season, datetime.utcnow())
        assert outcome == resolution.NEED_EMAIL
    finally:
        cleanup(a, b)


def test_stale_user_id_falls_back_to_phone_match(season):
    """A session pointing at a deleted account must not crash."""
    outcome, _ = resolution.resolve_registration_step(
        ident(PHONE_A, 99999999), season, datetime.utcnow())
    assert outcome == resolution.WIZARD_NEW
