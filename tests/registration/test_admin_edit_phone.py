"""Admin phone edits keep phone_e164 in step and never leave a stale
phone_verified_at on a changed number."""
from datetime import datetime

import pytest

from app import create_app
from app.models import db, User

EMAIL = "admin-phone-edit@test.com"
VERIFIED_AT = datetime(2026, 1, 1, 12, 0, 0)


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
def user_id(app):
    with app.app_context():
        u = User(email=EMAIL, first_name="Phone", last_name="Edit",
                 phone="(612) 555-0100", phone_e164="+16125550100",
                 phone_verified_at=VERIFIED_AT)
        db.session.add(u)
        db.session.commit()
        uid = u.id
        yield uid
        db.session.expire_all()
        db.session.delete(User.query.get(uid))
        db.session.commit()


def _post_phone(client, user_id, phone):
    return client.post(f"/admin/users/{user_id}/edit",
                       data={"form_type": "full", "phone": phone})


def test_changed_number_normalizes_and_clears_verified(client, app, user_id):
    resp = _post_phone(client, user_id, "651-555-0199")
    assert resp.status_code == 302
    with app.app_context():
        u = User.query.get(user_id)
        assert u.phone == "651-555-0199"
        assert u.phone_e164 == "+16515550199"
        assert u.phone_verified_at is None  # a new number is unproven


def test_same_number_reformatted_keeps_verified(client, app, user_id):
    resp = _post_phone(client, user_id, "612.555.0100")
    assert resp.status_code == 302
    with app.app_context():
        u = User.query.get(user_id)
        assert u.phone == "612.555.0100"
        assert u.phone_e164 == "+16125550100"
        assert u.phone_verified_at == VERIFIED_AT  # same number stays proven


def test_junk_number_stored_permissively_with_no_e164(client, app, user_id):
    resp = _post_phone(client, user_id, "carrier pigeon")
    assert resp.status_code == 302  # admin path rejects nothing
    with app.app_context():
        u = User.query.get(user_id)
        assert u.phone == "carrier pigeon"
        assert u.phone_e164 is None
        assert u.phone_verified_at is None
