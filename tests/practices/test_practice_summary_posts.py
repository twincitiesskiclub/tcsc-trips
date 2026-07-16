from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.models import db
from app.practices import PracticeSummaryPost


UNIQUE_CONSTRAINT_WEEK = date(2126, 1, 7)
SURFACE_CONSTRAINT_WEEK = date(2126, 1, 14)
FIXTURE_PROBE_WEEK = date(2126, 1, 21)
RESERVED_WEEK_STARTS = (
    UNIQUE_CONSTRAINT_WEEK,
    SURFACE_CONSTRAINT_WEEK,
    FIXTURE_PROBE_WEEK,
)
FIXTURE_SUMMARY_IDENTITIES = {
    (
        UNIQUE_CONSTRAINT_WEEK,
        "coach_summary",
        "C-COACH",
        "100.1",
    ),
    (
        UNIQUE_CONSTRAINT_WEEK,
        "weekly_summary",
        "C-PUBLIC",
        "100.2",
    ),
}
PROBE_AMBIENT_IDENTITY = (
    FIXTURE_PROBE_WEEK,
    "coach_summary",
    "C-AMBIENT-PROBE",
    "fixture-probe-ambient-ts",
)


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture(autouse=True)
def clear_summary_posts(app):
    with app.app_context():
        db.session.rollback()
        _refuse_if_reserved_weeks_occupied()
    try:
        yield
    finally:
        with app.app_context():
            db.session.rollback()
            summary_posts = _assert_fixture_owns_reserved_rows()
            for summary_post in summary_posts:
                db.session.delete(summary_post)
            db.session.commit()


def _reserved_summary_posts():
    return (
        PracticeSummaryPost.query.filter(
            PracticeSummaryPost.week_start.in_(RESERVED_WEEK_STARTS)
        )
        .order_by(PracticeSummaryPost.id)
        .all()
    )


def _summary_identity(summary_post):
    return (
        summary_post.week_start,
        summary_post.surface,
        summary_post.channel_id,
        summary_post.message_ts,
    )


def _refuse_if_reserved_weeks_occupied():
    summary_posts = _reserved_summary_posts()
    if summary_posts:
        pytest.fail(
            "Reserved 2126 model-test weeks contain existing summary rows; "
            "refusing to mutate persistent local PostgreSQL "
            f"(summary_post_ids={[row.id for row in summary_posts]})"
        )


def _assert_fixture_owns_reserved_rows():
    summary_posts = _reserved_summary_posts()
    ambient_summary_posts = [
        row
        for row in summary_posts
        if _summary_identity(row) not in FIXTURE_SUMMARY_IDENTITIES
    ]
    if ambient_summary_posts:
        pytest.fail(
            "Reserved 2126 model-test weeks contain summary rows not owned "
            "by this fixture; refusing teardown deletion "
            f"(summary_post_ids={[row.id for row in ambient_summary_posts]})"
        )
    return summary_posts


def test_summary_identity_is_unique_per_week_and_surface(app):
    with app.app_context():
        coach = PracticeSummaryPost(
            week_start=UNIQUE_CONSTRAINT_WEEK,
            surface="coach_summary",
            channel_id="C-COACH",
            message_ts="100.1",
        )
        public = PracticeSummaryPost(
            week_start=UNIQUE_CONSTRAINT_WEEK,
            surface="weekly_summary",
            channel_id="C-PUBLIC",
            message_ts="100.2",
        )
        db.session.add_all([coach, public])
        db.session.commit()

        db.session.add(PracticeSummaryPost(
            week_start=UNIQUE_CONSTRAINT_WEEK,
            surface="weekly_summary",
            channel_id="C-OTHER",
            message_ts="100.3",
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_summary_surface_is_restricted(app):
    with app.app_context():
        db.session.add(PracticeSummaryPost(
            week_start=SURFACE_CONSTRAINT_WEEK,
            surface="other_summary",
            channel_id="C-OTHER",
            message_ts="200.1",
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_fixture_refuses_ambient_reserved_row_without_deleting_it(app):
    teardown_probe = clear_summary_posts.__wrapped__(app)
    next(teardown_probe)

    with app.app_context():
        ambient = PracticeSummaryPost(
            week_start=PROBE_AMBIENT_IDENTITY[0],
            surface=PROBE_AMBIENT_IDENTITY[1],
            channel_id=PROBE_AMBIENT_IDENTITY[2],
            message_ts=PROBE_AMBIENT_IDENTITY[3],
        )
        db.session.add(ambient)
        db.session.commit()
        ambient_id = ambient.id

        try:
            setup_probe = clear_summary_posts.__wrapped__(app)
            with pytest.raises(
                pytest.fail.Exception,
                match="existing summary rows; refusing to mutate",
            ):
                next(setup_probe)
            with pytest.raises(
                pytest.fail.Exception,
                match="rows not owned by this fixture; refusing teardown",
            ):
                next(teardown_probe)

            db.session.expire_all()
            surviving_ambient = db.session.get(
                PracticeSummaryPost,
                ambient_id,
            )
            assert surviving_ambient is not None
            assert _summary_identity(surviving_ambient) == PROBE_AMBIENT_IDENTITY
        finally:
            db.session.rollback()
            surviving_ambient = db.session.get(
                PracticeSummaryPost,
                ambient_id,
            )
            if surviving_ambient is not None:
                assert (
                    _summary_identity(surviving_ambient)
                    == PROBE_AMBIENT_IDENTITY
                )
                db.session.delete(surviving_ambient)
                db.session.commit()
