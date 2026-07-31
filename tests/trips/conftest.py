import pytest

from app import create_app
from app.models import db, Payment, SlackUser, Trip, User
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
    "test-trip-slack",
    "test-trip-slack-2027",
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
    # Scalar-ID queries only: loading ORM instances (e.g. series.editions)
    # and then bulk-deleting the children makes the later parent delete
    # raise StaleDataError. Mirrors the events fixture pattern.
    series_ids = [
        sid for (sid,) in db.session.query(TripSeries.id).filter(
            TripSeries.slug.in_(TEST_TRIP_SLUGS))
    ]
    edition_filter = Trip.slug.in_(TEST_TRIP_SLUGS)
    if series_ids:
        edition_filter = db.or_(edition_filter, Trip.series_id.in_(series_ids))
    edition_ids = [
        tid for (tid,) in db.session.query(Trip.id).filter(edition_filter)
    ]
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
    if series_ids:
        TripSeries.query.filter(TripSeries.id.in_(series_ids)).delete(
            synchronize_session=False
        )
    user_ids = [
        uid for (uid,) in db.session.query(User.id).filter(
            User.email.in_(TEST_USER_EMAILS))
    ]
    if user_ids:
        TripProfile.query.filter(
            TripProfile.user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        User.query.filter(User.id.in_(user_ids)).delete(
            synchronize_session=False
        )
    SlackUser.query.filter(
        SlackUser.slack_uid == "U_TEST_TRIP"
    ).delete(synchronize_session=False)
    db.session.commit()
    db.session.expire_all()


@pytest.fixture(autouse=True)
def cleanup_trip_records(db_session):
    _delete_test_trips()
    yield
    db_session.session.rollback()
    _delete_test_trips()
