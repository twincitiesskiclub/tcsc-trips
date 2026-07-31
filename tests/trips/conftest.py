import pytest

from app import create_app
from app.models import db, Payment, Trip, User
from app.trips.models import TripProfile, TripRegistration, TripSeries

TEST_TRIP_SLUGS = (
    "test-trip-models",
    "test-trip-models-2027",
    "test-trip-service",
    "test-trip-service-2027",
    "test-trip-routes",
    "test-trip-routes-2027",
    "test-trip-admin",
    "test-trip-admin-2027",
    "test-trip-admin-2028",
    "test-trip-admin-2100",
    "test-trip-webhook",
    "test-trip-webhook-2027",
)
TEST_USER_EMAILS = (
    "trip-member@example.com",
    "trip-inactive@example.com",
    "trip-second@example.com",
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
        yield db
        db.session.rollback()


def _delete_test_trips():
    series_rows = TripSeries.query.filter(
        TripSeries.slug.in_(TEST_TRIP_SLUGS)
    ).all()
    edition_ids = []
    for series in series_rows:
        edition_ids.extend(e.id for e in series.editions)
    orphan_editions = Trip.query.filter(Trip.slug.in_(TEST_TRIP_SLUGS)).all()
    edition_ids.extend(e.id for e in orphan_editions)
    if edition_ids:
        Payment.query.filter(Payment.trip_id.in_(edition_ids)).delete(
            synchronize_session=False
        )
        TripRegistration.query.filter(
            TripRegistration.trip_id.in_(edition_ids)
        ).delete(synchronize_session=False)
        Trip.query.filter(Trip.id.in_(edition_ids)).delete(
            synchronize_session=False
        )
    for series in series_rows:
        db.session.delete(series)
    users = User.query.filter(User.email.in_(TEST_USER_EMAILS)).all()
    for user in users:
        TripProfile.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )
        db.session.delete(user)
    db.session.commit()


@pytest.fixture(autouse=True)
def cleanup_trip_records(db_session):
    _delete_test_trips()
    yield
    db_session.session.rollback()
    _delete_test_trips()
