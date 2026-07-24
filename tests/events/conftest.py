"""Database fixtures for event model tests."""

import pytest

from app import create_app
from app.models import db


TEST_EVENT_SLUGS = (
    "admin-grid-test",
    "admin-registration-test",
    "admin-duplicate-test",
    "admin-duplicate-test-copy",
    "admin-delete-test",
    "dry-tri-2026",
    "migration-home-both",
    "migration-home-draft",
    "migration-home-expired",
    "migration-home-external",
    "migration-home-internal",
    "migration-registration-shape",
    "payment-link-test",
    "registration-service-test",
    "registration-service-other",
)


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
def db_session(app):
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()


def _delete_test_events():
    from app.events.models import Event, EventParticipant, EventPriceOption
    from app.events.models import EventRegistration
    from app.models import Payment

    event_ids = [
        event_id
        for event_id, in db.session.query(Event.id)
        .filter(Event.slug.in_(TEST_EVENT_SLUGS))
        .all()
    ]
    if not event_ids:
        return

    registration_ids = [
        registration_id
        for registration_id, in db.session.query(EventRegistration.id)
        .filter(EventRegistration.event_id.in_(event_ids))
        .all()
    ]
    if registration_ids:
        Payment.query.filter(
            Payment.event_registration_id.in_(registration_ids)
        ).delete(synchronize_session=False)
        EventParticipant.query.filter(
            EventParticipant.registration_id.in_(registration_ids)
        ).delete(synchronize_session=False)
        EventRegistration.query.filter(
            EventRegistration.id.in_(registration_ids)
        ).delete(synchronize_session=False)

    EventPriceOption.query.filter(
        EventPriceOption.event_id.in_(event_ids)
    ).delete(synchronize_session=False)
    Event.query.filter(Event.id.in_(event_ids)).delete(
        synchronize_session=False
    )
    db.session.commit()


@pytest.fixture(autouse=True)
def cleanup_event_model_records(db_session):
    _delete_test_events()
    yield
    db.session.rollback()
    _delete_test_events()
