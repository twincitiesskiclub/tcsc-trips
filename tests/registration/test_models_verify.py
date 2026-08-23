from datetime import datetime

import pytest

from app import create_app
from app.models import db, User, VerificationCode, VerificationAttempt


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db
        db.session.rollback()
        for email in ("verify-a@test.com", "verify-b@test.com"):
            u = User.query.filter_by(email=email).one_or_none()
            if u:
                db.session.delete(u)
        VerificationCode.query.filter(
            VerificationCode.email.like("verify-%@test.com")).delete(
            synchronize_session=False)
        VerificationAttempt.query.filter(
            VerificationAttempt.target.like("+1612555%")).delete(
            synchronize_session=False)
        db.session.commit()


def test_two_users_can_share_phone_e164(db_session):
    a = User(email="verify-a@test.com", first_name="A", last_name="One",
             phone_e164="+16125550101")
    b = User(email="verify-b@test.com", first_name="B", last_name="Two",
             phone_e164="+16125550101")
    db.session.add_all([a, b])
    db.session.commit()  # must NOT raise — phone_e164 is not unique
    assert [u.email for u in User.get_by_phone("+16125550101")] == [
        "verify-a@test.com", "verify-b@test.com"]


def test_verification_code_row_roundtrip(db_session):
    code = VerificationCode(
        email="verify-a@test.com", code_hash="a" * 64,
        expires_at=datetime.utcnow())
    db.session.add(code)
    db.session.commit()
    assert code.attempts == 0 and code.consumed_at is None
