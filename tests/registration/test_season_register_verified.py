from datetime import datetime, timedelta, date
from unittest.mock import patch

import pytest

from app import create_app
from app.constants import UserSeasonStatus, UserStatus
from app.models import db, Season, User, UserSeason

EMAIL = "reg-verified@test.com"
PHONE = "+16125550188"


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
    return app.test_client()


@pytest.fixture
def season(app):
    with app.app_context():
        now = datetime.utcnow()
        s = Season(name="Verify Test", year=2099, price_cents=15000,
                   season_type='winter',
                   start_date=date(2099, 11, 1), end_date=date(2100, 3, 1),
                   returning_start=now - timedelta(days=1),
                   returning_end=now + timedelta(days=30),
                   new_start=now - timedelta(days=1),
                   new_end=now + timedelta(days=30))
        db.session.add(s)
        db.session.commit()
        yield s.id
        UserSeason.query.filter_by(season_id=s.id).delete()
        u = User.query.filter_by(email=EMAIL).one_or_none()
        if u:
            db.session.delete(u)
        db.session.delete(Season.query.get(s.id))
        db.session.commit()


FORM = dict(
    firstName="Reg", lastName="Verified", email=EMAIL, pronouns="",
    dob="1994-01-15", phone="612-555-0188", technique="skate",
    tshirtSize="M", experience="3-7", emergencyName="Em Contact",
    emergencyRelation="friend", emergencyPhone="612-555-0189",
    emergencyEmail="em@example.com", payment_intent_id="pi_test_verify",
    volunteerInterests="event_volunteer",
)


def _set_identity(client, user_id=None):
    with client.session_transaction() as sess:
        sess["verified_identity"] = {
            "phone_e164": PHONE, "user_id": user_id,
            "ts": datetime.utcnow().isoformat()}


@patch("app.routes.registration.send_sms", return_value=True)
def test_verified_new_member_gets_e164_and_lottery_sms(mock_sms, client, app, season):
    _set_identity(client)
    resp = client.post(f"/seasons/{season}/register", data=FORM)
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email=EMAIL).one()
        assert user.phone_e164 == PHONE
        assert user.phone_verified_at is not None
        us = UserSeason.get_for_user_season(user.id, season)
        assert us.needs_review is False
    assert mock_sms.call_args.args[1] == "confirmation_lottery"


@patch("app.routes.registration.send_sms", return_value=True)
def test_unverified_flags_needs_review(mock_sms, client, app, season):
    # no session identity at all + explicit continue_unverified
    resp = client.post(f"/seasons/{season}/register",
                       data={**FORM, "continue_unverified": "1"})
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email=EMAIL).one()
        us = UserSeason.get_for_user_season(user.id, season)
        assert us.needs_review is True
        assert user.phone_verified_at is None
        assert user.phone_e164 == "+16125550188"  # normalized, but unverified


def test_unverified_without_flag_is_rejected(client, app, season):
    resp = client.post(f"/seasons/{season}/register", data=FORM,
                       follow_redirects=False)
    assert resp.status_code == 302  # bounced back with flash error


@patch("app.routes.registration.send_sms", return_value=True)
def test_new_email_collision_without_flag_rejected(mock_sms, client, app, season):
    with app.app_context():
        db.session.add(User(email=EMAIL, first_name="Old", last_name="Row"))
        db.session.commit()
    _set_identity(client)  # verified phone, but user_id None -> "new" path
    resp = client.post(f"/seasons/{season}/register", data=FORM,
                       follow_redirects=False)
    assert resp.status_code == 302  # collision guard fired


@patch("app.routes.registration.send_sms", return_value=True)
def test_verified_returning_member_updates_own_row(mock_sms, client, app, season):
    with app.app_context():
        u = User(email=EMAIL, first_name="Old", last_name="Name")
        db.session.add(u)
        db.session.commit()
        uid = u.id
    _set_identity(client, user_id=uid)
    resp = client.post(f"/seasons/{season}/register", data=FORM)
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.get(uid)
        assert user.first_name == "Reg"  # updated in place, no duplicate row
        assert User.query.filter_by(email=EMAIL).count() == 1


@patch("app.routes.registration.send_sms", return_value=True)
def test_verified_phone_but_unmatched_collision_flag_stays_new_and_reviewed(
        mock_sms, client, app, season):
    """A phone verified via OTP this session (identity present) but with no
    user_id match must NOT unlock returning pricing just because the typed
    email happens to collide with someone else's returning-member row. The
    collision guard is bypassed via continue_unverified, so the reused row
    is priced as new/manual and flagged for admin review — pricing is
    earned only by a verified *account link*, not merely a verified phone.
    """
    with app.app_context():
        now = datetime.utcnow()
        old_season = Season(
            name="Verify Test Old", year=2088, price_cents=15000,
            season_type='winter',
            start_date=date(2088, 11, 1), end_date=date(2089, 3, 1))
        db.session.add(old_season)
        db.session.commit()
        u = User(email=EMAIL, first_name="Old", last_name="Returner")
        db.session.add(u)
        db.session.commit()
        db.session.add(UserSeason(
            user_id=u.id, season_id=old_season.id,
            registration_type="new",
            registration_date=date(2088, 10, 1),
            status=UserSeasonStatus.ACTIVE,
        ))
        db.session.commit()
        old_season_id = old_season.id

    try:
        _set_identity(client, user_id=None)  # verified phone, unmatched
        resp = client.post(f"/seasons/{season}/register",
                           data={**FORM, "continue_unverified": "1"})
        assert resp.status_code == 200
        with app.app_context():
            user = User.query.filter_by(email=EMAIL).one()
            us = UserSeason.get_for_user_season(user.id, season)
            assert us.registration_type == "new"
            assert us.status == UserSeasonStatus.PENDING_LOTTERY
            assert us.needs_review is True
        assert mock_sms.call_args.args[1] == "confirmation_lottery"
    finally:
        with app.app_context():
            UserSeason.query.filter_by(season_id=old_season_id).delete()
            db.session.delete(Season.query.get(old_season_id))
            db.session.commit()


@patch("app.routes.registration.send_sms", return_value=True)
def test_disclaimed_identity_never_binds_to_verified_row(
        mock_sms, client, app, season):
    """Session verified into returning account A, then the registrant took
    the "Not [name]?" path and exited through an unverified escape hatch
    (continue_unverified=1) with a brand-new email. The POST must create a
    fresh flagged lottery row and leave A's row completely untouched."""
    a_email = "reg-account-a@test.com"
    with app.app_context():
        old_season = Season(
            name="Verify Test Old A", year=2086, price_cents=15000,
            season_type='winter',
            start_date=date(2086, 11, 1), end_date=date(2087, 3, 1))
        db.session.add(old_season)
        db.session.commit()
        a = User(email=a_email, first_name="Alice", last_name="Owner",
                 phone_e164=PHONE)
        db.session.add(a)
        db.session.commit()
        db.session.add(UserSeason(
            user_id=a.id, season_id=old_season.id,
            registration_type="new",
            registration_date=date(2086, 10, 1),
            status=UserSeasonStatus.ACTIVE,
        ))
        db.session.commit()
        a_id, old_season_id = a.id, old_season.id

    try:
        _set_identity(client, user_id=a_id)  # phone matched A this session
        resp = client.post(f"/seasons/{season}/register",
                           data={**FORM, "continue_unverified": "1"})
        assert resp.status_code == 200
        with app.app_context():
            a = User.query.get(a_id)
            assert a.first_name == "Alice"      # A's row untouched
            assert a.email == a_email
            assert UserSeason.get_for_user_season(a_id, season) is None
            b = User.query.filter_by(email=EMAIL).one()
            assert b.id != a_id                 # fresh row, not A
            us = UserSeason.get_for_user_season(b.id, season)
            assert us.registration_type == "new"
            assert us.status == UserSeasonStatus.PENDING_LOTTERY
            assert us.needs_review is True      # disclaimed match: eyeball it
        assert mock_sms.call_args.args[1] == "confirmation_lottery"
    finally:
        with app.app_context():
            UserSeason.query.filter_by(user_id=a_id).delete()
            db.session.commit()
            db.session.delete(User.query.get(a_id))
            db.session.delete(Season.query.get(old_season_id))
            db.session.commit()


def test_unverified_registration_records_why(client, app, season):
    with client.session_transaction() as sess:
        sess.pop('verified_identity', None)
    form = dict(FORM, continue_unverified='1')
    client.post(f'/seasons/{season}/register', data=form,
                follow_redirects=True)
    with app.app_context():
        u = User.query.filter_by(email=EMAIL).one_or_none()
        assert u is not None
        us = UserSeason.get_for_user_season(u.id, season)
        assert us.needs_review is True
        assert us.review_note == "no verified phone"


def test_disclaimed_identity_does_not_get_returning_pricing(client, app, season):
    """'Not Jane?' must not be priced as Jane.

    The session still carries Jane's user_id at this point, so the route
    has to scrub it before the resolver sees it.
    """
    with app.app_context():
        jane = User(email="jane-disclaim@test.com", first_name="Jane",
                    last_name="Owner", status=UserStatus.ACTIVE,
                    phone_e164=PHONE, date_of_birth=date(1990, 1, 1),
                    tshirt_size="M", emergency_contact_name="Em",
                    emergency_contact_relation="friend",
                    emergency_contact_phone="612-555-0999",
                    emergency_contact_email="em@test.com")
        db.session.add(jane)
        db.session.commit()
        past = Season(name="Disclaim Past", year=2087, price_cents=1000,
                      season_type='winter', start_date=date(2087, 11, 1),
                      end_date=date(2088, 3, 1))
        db.session.add(past)
        db.session.commit()
        db.session.add(UserSeason(user_id=jane.id, season_id=past.id,
                                  registration_type='new',
                                  registration_date=date(2087, 10, 1),
                                  status=UserSeasonStatus.ACTIVE))
        db.session.commit()
        jane_id, past_id = jane.id, past.id
    with client.session_transaction() as sess:
        sess['verified_identity'] = {
            'phone_e164': PHONE, 'user_id': jane_id,
            'ts': datetime.utcnow().isoformat()}
    # EMAIL differs from Jane's, plus continue_unverified: the disclaim flow.
    client.post(f'/seasons/{season}/register',
                data=dict(FORM, continue_unverified='1'),
                follow_redirects=True)
    try:
        with app.app_context():
            u = User.query.filter_by(email=EMAIL).one_or_none()
            us = UserSeason.get_for_user_season(u.id, season)
            assert us.registration_type == 'new'
            assert us.status == UserSeasonStatus.PENDING_LOTTERY
            assert us.needs_review is True
            assert "Jane Owner" in us.review_note
    finally:
        with app.app_context():
            UserSeason.query.filter_by(user_id=jane_id).delete()
            db.session.commit()
            db.session.delete(User.query.get(jane_id))
            db.session.delete(Season.query.get(past_id))
            db.session.commit()


def test_verified_new_member_is_not_flagged(client, app, season):
    with client.session_transaction() as sess:
        sess['verified_identity'] = {
            'phone_e164': PHONE, 'user_id': None,
            'ts': datetime.utcnow().isoformat()}
    client.post(f'/seasons/{season}/register', data=dict(FORM),
                follow_redirects=True)
    with app.app_context():
        u = User.query.filter_by(email=EMAIL).one_or_none()
        us = UserSeason.get_for_user_season(u.id, season)
        assert us.needs_review is False
        assert us.review_note is None
        assert us.registration_type == 'new'
        assert u.phone_verified_at is not None


def test_resolved_member_can_move_their_email(client, app, season):
    with app.app_context():
        existing = User(email="old-address@test.com", first_name="Reg",
                        last_name="Verified", status=UserStatus.ACTIVE,
                        phone_e164=PHONE, date_of_birth=date(1994, 1, 15),
                        tshirt_size="M", emergency_contact_name="Em",
                        emergency_contact_relation="friend",
                        emergency_contact_phone="612-555-0189",
                        emergency_contact_email="em@example.com")
        db.session.add(existing)
        db.session.commit()
        uid = existing.id
    with client.session_transaction() as sess:
        sess['verified_identity'] = {
            'phone_e164': PHONE, 'user_id': uid,
            'ts': datetime.utcnow().isoformat()}
    client.post(f'/seasons/{season}/register', data=dict(FORM),
                follow_redirects=True)
    with app.app_context():
        assert User.query.get(uid).email == EMAIL
