from datetime import datetime, timedelta, date
from unittest.mock import patch

import pytest
from sqlalchemy import event

from app import create_app
from app.constants import UserSeasonStatus, UserStatus
from app.models import db, Payment, Season, User, UserSeason

EMAIL = "reg-verified@test.com"
PHONE = "+16125550188"
OWNER_PHONE = "+16125559999"


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
        Payment.query.filter_by(season_id=s.id).delete()
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


def _plant_payment_owner_with_active_history(app, season, user_status):
    with app.app_context():
        past_season = Season(
            name=f"Webhook Owner Past {user_status}",
            year=2084,
            price_cents=15000,
            season_type="winter",
            start_date=date(2084, 11, 1),
            end_date=date(2085, 3, 1),
        )
        sam = User(
            email=EMAIL,
            first_name="Sam",
            last_name="Member",
            status=user_status,
            phone_e164=OWNER_PHONE,
        )
        db.session.add_all([past_season, sam])
        db.session.flush()
        db.session.add(UserSeason(
            user_id=sam.id,
            season_id=past_season.id,
            registration_type="new",
            registration_date=date(2084, 10, 1),
            status=UserSeasonStatus.ACTIVE,
        ))
        db.session.add(Payment(
            payment_intent_id=FORM["payment_intent_id"],
            email=EMAIL,
            name="Reg Verified",
            amount=15000,
            status="requires_capture",
            payment_type="season",
            season_id=season,
            user_id=sam.id,
        ))
        db.session.commit()
        return sam.id, past_season.id


def _delete_payment_owner(app, user_id, past_season_id):
    with app.app_context():
        Payment.query.filter_by(
            payment_intent_id=FORM["payment_intent_id"]
        ).delete()
        UserSeason.query.filter_by(user_id=user_id).delete()
        user = User.query.get(user_id)
        if user is not None:
            db.session.delete(user)
        past_season = Season.query.get(past_season_id)
        if past_season is not None:
            db.session.delete(past_season)
        db.session.commit()


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
        owner_phone = "+16125559999"
        owner_verified_at = datetime(2090, 1, 2, 3, 4, 5)
        u = User(
            email=EMAIL,
            first_name="Old",
            last_name="Returner",
            phone_e164=owner_phone,
            phone_verified_at=owner_verified_at,
        )
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
            assert user.phone_e164 == owner_phone
            assert user.phone_verified_at == owner_verified_at
            assert f"from verified phone {PHONE}" in us.review_note
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


@patch("app.routes.registration.send_sms", return_value=True)
def test_disclaimed_shared_number_registration_records_review_note(
        mock_sms, client, app, season):
    shared_email = "shared-number-owner@test.com"
    with app.app_context():
        shared_user = User(
            email=shared_email,
            first_name="Shared",
            last_name="Owner",
            phone_e164=PHONE,
        )
        db.session.add(shared_user)
        db.session.commit()
        shared_user_id = shared_user.id

    try:
        with client.session_transaction() as sess:
            sess['verified_identity'] = {
                'phone_e164': PHONE,
                'user_id': None,
                'disclaimed_user_id': shared_user_id,
                'ts': datetime.utcnow().isoformat(),
            }

        response = client.post(
            f'/seasons/{season}/register', data=dict(FORM),
            follow_redirects=False,
        )

        assert response.status_code == 200
        with app.app_context():
            user = User.query.filter_by(email=EMAIL).one()
            user_season = UserSeason.get_for_user_season(user.id, season)
            assert user_season.needs_review is True
            assert "shared number with Shared Owner" in user_season.review_note
            assert f"(id {shared_user_id})" in user_season.review_note
        assert mock_sms.call_args.args[1] == "confirmation_lottery"
    finally:
        with app.app_context():
            shared_user = User.query.get(shared_user_id)
            if shared_user is not None:
                db.session.delete(shared_user)
                db.session.commit()


@patch("app.routes.registration.send_sms", return_value=True)
def test_disclaimed_deleted_account_registration_records_review_note(
        mock_sms, client, app, season):
    with app.app_context():
        deleted_user_id = (db.session.query(db.func.max(User.id)).scalar() or 0) + 1

    with client.session_transaction() as sess:
        sess['verified_identity'] = {
            'phone_e164': PHONE,
            'user_id': None,
            'disclaimed_user_id': deleted_user_id,
            'ts': datetime.utcnow().isoformat(),
        }

    response = client.post(
        f'/seasons/{season}/register', data=dict(FORM),
        follow_redirects=False,
    )

    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email=EMAIL).one()
        user_season = UserSeason.get_for_user_season(user.id, season)
        assert user_season.needs_review is True
        assert user_season.review_note == (
            f"shared number with a deleted account (id {deleted_user_id})"
        )
    assert mock_sms.call_args.args[1] == "confirmation_lottery"


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


def test_unverified_row_reuse_keeps_claimed_email(client, app, season):
    claimed_email = "keep-me@test.com"
    with app.app_context():
        existing = User(email=claimed_email, first_name="Reg",
                        last_name="Verified", status=UserStatus.ACTIVE,
                        phone_e164="+16125550199",
                        date_of_birth=date(1994, 1, 15),
                        tshirt_size="M", emergency_contact_name="Em",
                        emergency_contact_relation="friend",
                        emergency_contact_phone="612-555-0189",
                        emergency_contact_email="em@example.com")
        db.session.add(existing)
        db.session.commit()
        uid = existing.id

    email_writes = []

    def record_email_write(target, value, oldvalue, initiator):
        if target.id == uid:
            email_writes.append((oldvalue, value))

    try:
        with client.session_transaction() as sess:
            sess.pop('verified_identity', None)
        event.listen(User.email, "set", record_email_write)
        try:
            response = client.post(
                f'/seasons/{season}/register',
                data=dict(FORM, continue_unverified='1',
                          email=claimed_email),
                follow_redirects=True,
            )
        finally:
            event.remove(User.email, "set", record_email_write)

        assert response.status_code == 200
        with app.app_context():
            user = User.query.get(uid)
            assert user.email == claimed_email
            assert user.phone_e164 == "+16125550199"
            user_season = UserSeason.get_for_user_season(uid, season)
            assert (
                "from unverified phone +16125550188"
                in user_season.review_note
            )
        assert email_writes == []
    finally:
        with app.app_context():
            UserSeason.query.filter_by(user_id=uid).delete()
            db.session.delete(User.query.get(uid))
            db.session.commit()


@patch("app.routes.registration.send_sms", return_value=True)
def test_post_adopts_webhook_first_stub_for_verified_new_member(
        mock_sms, client, app, season):
    with app.app_context():
        user = User(
            email=EMAIL,
            first_name="Webhook",
            last_name="Stub",
            status=UserStatus.PENDING,
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(UserSeason(
            user_id=user.id,
            season_id=season,
            registration_type="NEW",
            registration_date=date(2099, 10, 1),
            status=UserSeasonStatus.PENDING_LOTTERY,
        ))
        db.session.add(Payment(
            payment_intent_id=FORM["payment_intent_id"],
            email=EMAIL,
            name="Reg Verified",
            amount=15000,
            status="requires_capture",
            payment_type="season",
            season_id=season,
            user_id=user.id,
        ))
        db.session.commit()
        user_id = user.id

    _set_identity(client, user_id=None)
    response = client.post(
        f"/seasons/{season}/register",
        data=FORM,
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b'id="registration-success"' in response.data
    with app.app_context():
        user = User.query.get(user_id)
        assert User.query.filter_by(email=EMAIL).count() == 1
        assert user.first_name == FORM["firstName"]
        assert user.last_name == FORM["lastName"]
        assert user.date_of_birth == date(1994, 1, 15)
        assert user.phone_e164 == PHONE
        user_season = UserSeason.get_for_user_season(user_id, season)
        assert user_season.needs_review is False
        assert user_season.review_note is None
    assert mock_sms.call_args.args[1] == "confirmation_lottery"


@patch("app.routes.registration.send_sms", return_value=True)
def test_payment_link_does_not_adopt_existing_active_member(
        mock_sms, client, app, season):
    user_id, past_season_id = _plant_payment_owner_with_active_history(
        app, season, UserStatus.ACTIVE)

    try:
        _set_identity(client, user_id=None)
        response = client.post(
            f"/seasons/{season}/register",
            data={**FORM, "continue_unverified": "0"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert b'id="registration-success"' not in response.data
        with app.app_context():
            sam = User.query.get(user_id)
            assert sam.first_name == "Sam"
            assert sam.phone_e164 == OWNER_PHONE
            assert UserSeason.get_for_user_season(user_id, season) is None
        mock_sms.assert_not_called()
    finally:
        _delete_payment_owner(app, user_id, past_season_id)


@patch("app.routes.registration.send_sms", return_value=True)
def test_payment_link_uses_flagged_reuse_for_pending_member_with_active_history(
        mock_sms, client, app, season):
    user_id, past_season_id = _plant_payment_owner_with_active_history(
        app, season, UserStatus.PENDING)

    try:
        _set_identity(client, user_id=None)
        response = client.post(
            f"/seasons/{season}/register",
            data={**FORM, "continue_unverified": "1"},
            follow_redirects=False,
        )

        assert response.status_code == 200
        assert b'id="registration-success"' in response.data
        with app.app_context():
            sam = User.query.get(user_id)
            user_season = UserSeason.get_for_user_season(user_id, season)
            assert sam.phone_e164 == OWNER_PHONE
            assert user_season.needs_review is True
            assert EMAIL in user_season.review_note
            assert PHONE in user_season.review_note
        assert mock_sms.call_args.args[1] == "confirmation_lottery"
    finally:
        _delete_payment_owner(app, user_id, past_season_id)


@patch("app.routes.registration.send_sms", return_value=True)
def test_post_reconciles_webhook_created_registration_for_own_payment(
        mock_sms, client, app, season):
    with app.app_context():
        user = User(email=EMAIL, first_name="Webhook", last_name="First")
        db.session.add(user)
        db.session.flush()
        db.session.add(UserSeason(
            user_id=user.id,
            season_id=season,
            registration_type="NEW",
            registration_date=date(2099, 10, 1),
            status=UserSeasonStatus.PENDING_LOTTERY,
        ))
        db.session.add(Payment(
            payment_intent_id=FORM["payment_intent_id"],
            email=EMAIL,
            name="Reg Verified",
            amount=15000,
            status="requires_capture",
            payment_type="season",
            season_id=season,
            user_id=user.id,
        ))
        db.session.commit()
        user_id = user.id

    _set_identity(client, user_id=user_id)
    response = client.post(f"/seasons/{season}/register", data=FORM)

    assert response.status_code == 200
    with app.app_context():
        user_season = UserSeason.get_for_user_season(user_id, season)
        assert user_season.volunteer_interests == ["event_volunteer"]
        assert user_season.needs_review is False
        assert user_season.review_note is None
    assert mock_sms.call_args.args[1] == "confirmation_lottery"


@patch("app.routes.registration.send_sms", return_value=True)
def test_post_does_not_reconcile_another_users_payment(
        mock_sms, client, app, season):
    owner_email = "payment-owner-a@test.com"
    with app.app_context():
        owner = User(
            email=owner_email,
            first_name="Payment",
            last_name="Owner",
            phone_e164="+16125550177",
        )
        registrant = User(
            email=EMAIL,
            first_name="Already",
            last_name="Registered",
            phone_e164=PHONE,
        )
        db.session.add_all([owner, registrant])
        db.session.flush()
        owner_season = UserSeason(
            user_id=owner.id,
            season_id=season,
            registration_type="new",
            registration_date=date(2099, 10, 1),
            status=UserSeasonStatus.PENDING_LOTTERY,
            needs_review=True,
            review_note="leave owner unchanged",
            volunteer_interests=["committee"],
        )
        registrant_season = UserSeason(
            user_id=registrant.id,
            season_id=season,
            registration_type="returning",
            registration_date=date(2099, 10, 2),
            status=UserSeasonStatus.ACTIVE,
            needs_review=True,
            review_note="leave registrant unchanged",
            volunteer_interests=["practice_lead"],
        )
        db.session.add_all([owner_season, registrant_season])
        db.session.add(Payment(
            payment_intent_id="pi_a",
            email=owner_email,
            name="Payment Owner",
            amount=15000,
            status="requires_capture",
            payment_type="season",
            season_id=season,
            user_id=owner.id,
        ))
        db.session.commit()
        owner_id = owner.id
        registrant_id = registrant.id
        owner_before = (
            owner_season.registration_type,
            owner_season.registration_date,
            owner_season.status,
            owner_season.needs_review,
            owner_season.review_note,
            owner_season.volunteer_interests,
        )
        registrant_before = (
            registrant_season.registration_type,
            registrant_season.registration_date,
            registrant_season.status,
            registrant_season.needs_review,
            registrant_season.review_note,
            registrant_season.volunteer_interests,
        )

    try:
        _set_identity(client, user_id=registrant_id)
        response = client.post(
            f"/seasons/{season}/register",
            data={**FORM, "payment_intent_id": "pi_a"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        with app.app_context():
            owner_after = UserSeason.get_for_user_season(owner_id, season)
            registrant_after = UserSeason.get_for_user_season(
                registrant_id, season)
            assert UserSeason.query.filter_by(
                user_id=registrant_id, season_id=season).count() == 1
            assert (
                owner_after.registration_type,
                owner_after.registration_date,
                owner_after.status,
                owner_after.needs_review,
                owner_after.review_note,
                owner_after.volunteer_interests,
            ) == owner_before
            assert (
                registrant_after.registration_type,
                registrant_after.registration_date,
                registrant_after.status,
                registrant_after.needs_review,
                registrant_after.review_note,
                registrant_after.volunteer_interests,
            ) == registrant_before
            assert Payment.get_by_payment_intent("pi_a").user_id == owner_id
        mock_sms.assert_not_called()
    finally:
        with app.app_context():
            Payment.query.filter_by(payment_intent_id="pi_a").delete()
            UserSeason.query.filter(
                UserSeason.user_id.in_([owner_id, registrant_id])).delete(
                    synchronize_session=False)
            for user_id in (owner_id, registrant_id):
                user = User.query.get(user_id)
                if user is not None:
                    db.session.delete(user)
            db.session.commit()


@patch("app.routes.registration.send_sms", return_value=True)
def test_verified_returning_member_is_rejected_when_window_ended(
        mock_sms, client, app, season):
    with app.app_context():
        now = datetime.utcnow()
        current_season = Season.query.get(season)
        current_season.returning_start = now - timedelta(days=30)
        current_season.returning_end = now - timedelta(days=1)
        past = Season(
            name="Verify Window Past",
            year=2085,
            price_cents=1000,
            season_type="winter",
            start_date=date(2085, 11, 1),
            end_date=date(2086, 3, 1),
        )
        user = User(
            email=EMAIL,
            first_name="Window",
            last_name="Closed",
            phone_e164=PHONE,
        )
        db.session.add_all([past, user])
        db.session.commit()
        db.session.add(UserSeason(
            user_id=user.id,
            season_id=past.id,
            registration_type="new",
            registration_date=date(2085, 10, 1),
            status=UserSeasonStatus.ACTIVE,
        ))
        db.session.commit()
        user_id, past_id = user.id, past.id

    # The fixture keeps an outer app context whose cached Season predates the
    # update above. Expire it so the request reads the committed window.
    db.session.expire_all()
    assert User.query.get(user_id).is_returning is True
    assert Season.query.get(season).is_returning_open(now) is False

    try:
        _set_identity(client, user_id=user_id)
        response = client.post(
            f"/seasons/{season}/register", data=FORM,
            follow_redirects=False,
        )

        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert (
                "error",
                "Sorry, the registration window for returning members is currently closed.",
            ) in sess.get("_flashes", [])
        with app.app_context():
            assert UserSeason.get_for_user_season(user_id, season) is None
        mock_sms.assert_not_called()
    finally:
        with app.app_context():
            UserSeason.query.filter_by(user_id=user_id).delete()
            db.session.commit()
            db.session.delete(User.query.get(user_id))
            db.session.delete(Season.query.get(past_id))
            db.session.commit()


def test_register_page_offers_the_club_sms_number(client, season):
    """The closed-window panel tells the member to text someone, so the
    page has to say who: a tappable club number."""
    response = client.get(f"/seasons/{season}/register")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'href="mailto:club@tcsc.ski"' in body
    assert "club@tcsc.ski" in body
    assert "Text an organizer" not in body


@patch("app.routes.registration.send_sms", return_value=True)
def test_invited_returning_member_survives_webhook_first(
        mock_sms, client, app, season):
    """Invited returning member: automatic capture, and the succeeded
    webhook created the ACTIVE row before this POST landed. The row is
    bound to the payment being confirmed, so it is theirs to complete,
    not evidence that the link was already used."""
    from app.late_link import generate
    user_id, past_season_id = _plant_payment_owner_with_active_history(
        app, season, UserStatus.ACTIVE)
    with app.app_context():
        db.session.add(UserSeason(
            user_id=user_id,
            season_id=season,
            registration_type="returning",
            registration_date=date(2099, 10, 1),
            status=UserSeasonStatus.ACTIVE,
        ))
        db.session.commit()
        token = generate(season, EMAIL)

    try:
        _set_identity(client, user_id=user_id)
        response = client.post(
            f"/seasons/{season}/register?invite={token}", data=FORM,
            follow_redirects=False,
        )

        assert response.status_code == 200
        assert b'id="registration-success"' in response.data
        with app.app_context():
            user_season = UserSeason.get_for_user_season(user_id, season)
            assert user_season.status == UserSeasonStatus.ACTIVE
            assert user_season.registration_type == "returning"
            assert user_season.volunteer_interests == ["event_volunteer"]
            assert user_season.needs_review is False
        assert mock_sms.call_args.args[1] == "confirmation_returning"
    finally:
        _delete_payment_owner(app, user_id, past_season_id)


@patch("app.routes.registration.send_sms", return_value=True)
def test_invited_member_with_registration_and_no_bound_payment_is_bounced(
        mock_sms, client, app, season):
    """The genuine already-used case: a registration that holds a spot
    and no payment binding it to this POST."""
    from app.late_link import generate
    with app.app_context():
        user = User(email=EMAIL, first_name="Used", last_name="Link",
                    status=UserStatus.ACTIVE, phone_e164=PHONE)
        db.session.add(user)
        db.session.flush()
        db.session.add(UserSeason(
            user_id=user.id,
            season_id=season,
            registration_type="returning",
            registration_date=date(2099, 10, 1),
            status=UserSeasonStatus.ACTIVE,
        ))
        db.session.commit()
        token = generate(season, EMAIL)
        user_id = user.id

    _set_identity(client, user_id=user_id)
    response = client.post(
        f"/seasons/{season}/register?invite={token}", data=FORM,
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as sess:
        flashes = sess.get("_flashes", [])
    assert any("already been used" in message for _, message in flashes), flashes
    with app.app_context():
        user_season = UserSeason.get_for_user_season(user_id, season)
        assert user_season.volunteer_interests in (None, [])
    mock_sms.assert_not_called()
