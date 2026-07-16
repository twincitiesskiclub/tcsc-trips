from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import create_app
from app.models import db
from app.practices import Practice, PracticeSummaryPost
from app.slack.practices.summary_posts import (
    COACH_SUMMARY,
    WEEKLY_SUMMARY,
    find_summary_post,
    stage_summary_post,
    summary_post_channel,
    week_start_date,
)


TEST_PRACTICE_AIRTABLE_ID = "summary-registry-test-practice"
REGISTRY_WEEK_START = date(2126, 2, 4)
EMPTY_WEEK_START = date(2126, 2, 11)
FIXTURE_PROBE_WEEK = date(2126, 2, 18)
RESERVED_WEEK_STARTS = (
    REGISTRY_WEEK_START,
    EMPTY_WEEK_START,
    FIXTURE_PROBE_WEEK,
)
TEST_PRACTICE_DATE = datetime(2126, 2, 5, 18, 15)
FIXTURE_PRACTICE_IDENTITIES = {
    (
        TEST_PRACTICE_DATE,
        "Tuesday",
        "scheduled",
        TEST_PRACTICE_AIRTABLE_ID,
        None,
        "100.1",
    ),
}
FIXTURE_SUMMARY_IDENTITIES = {
    (
        REGISTRY_WEEK_START,
        WEEKLY_SUMMARY,
        "C-WEEK",
        "100.1",
    ),
}
PROBE_AMBIENT_IDENTITY = (
    FIXTURE_PROBE_WEEK,
    COACH_SUMMARY,
    "C-AMBIENT-PROBE",
    "summary-registry-fixture-probe-ts",
)


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture(autouse=True)
def clear_summary_registry(app):
    with app.app_context():
        db.session.rollback()
        _refuse_if_reserved_weeks_occupied()
    try:
        yield
    finally:
        with app.app_context():
            db.session.rollback()
            practices, summary_posts = _assert_fixture_owns_reserved_rows()
            for summary_post in summary_posts:
                db.session.delete(summary_post)
            for practice in practices:
                db.session.delete(practice)
            db.session.commit()


def _reserved_practices():
    start = datetime.combine(RESERVED_WEEK_STARTS[0], time.min)
    end = datetime.combine(
        RESERVED_WEEK_STARTS[-1] + timedelta(days=7),
        time.min,
    )
    return (
        Practice.query.filter(Practice.date >= start, Practice.date < end)
        .order_by(Practice.id)
        .all()
    )


def _reserved_summary_posts():
    return (
        PracticeSummaryPost.query.filter(
            PracticeSummaryPost.week_start.in_(RESERVED_WEEK_STARTS)
        )
        .order_by(PracticeSummaryPost.id)
        .all()
    )


def _practice_identity(practice):
    return (
        practice.date,
        practice.day_of_week,
        practice.status,
        practice.airtable_id,
        practice.slack_coach_summary_ts,
        practice.slack_weekly_summary_ts,
    )


def _summary_identity(summary_post):
    return (
        summary_post.week_start,
        summary_post.surface,
        summary_post.channel_id,
        summary_post.message_ts,
    )


def _refuse_if_reserved_weeks_occupied():
    practices = _reserved_practices()
    summary_posts = _reserved_summary_posts()
    if practices or summary_posts:
        pytest.fail(
            "Reserved 2126 summary-registry test weeks contain existing "
            "rows; refusing to mutate persistent local PostgreSQL "
            f"(practice_ids={[row.id for row in practices]}, "
            f"summary_post_ids={[row.id for row in summary_posts]})"
        )


def _assert_fixture_owns_reserved_rows():
    practices = _reserved_practices()
    summary_posts = _reserved_summary_posts()
    ambient_practices = [
        row
        for row in practices
        if _practice_identity(row) not in FIXTURE_PRACTICE_IDENTITIES
    ]
    ambient_summary_posts = [
        row
        for row in summary_posts
        if _summary_identity(row) not in FIXTURE_SUMMARY_IDENTITIES
    ]
    if ambient_practices or ambient_summary_posts:
        pytest.fail(
            "Reserved 2126 summary-registry test weeks contain rows not "
            "owned by this fixture; refusing teardown deletion "
            f"(practice_ids={[row.id for row in ambient_practices]}, "
            "summary_post_ids="
            f"{[row.id for row in ambient_summary_posts]})"
        )
    return practices, summary_posts


def make_practice(value):
    practice = Practice(
        date=value,
        day_of_week=value.strftime("%A"),
        status="scheduled",
        airtable_id=TEST_PRACTICE_AIRTABLE_ID,
    )
    db.session.add(practice)
    return practice


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (REGISTRY_WEEK_START, REGISTRY_WEEK_START),
        (date(2126, 2, 10), REGISTRY_WEEK_START),
        (datetime(2126, 2, 7, 18, 5), REGISTRY_WEEK_START),
    ],
)
def test_week_start_date_is_monday(value, expected):
    assert week_start_date(value) == expected


def test_stage_summary_post_upserts_identity_and_legacy_links(app):
    with app.app_context():
        practice = make_practice(TEST_PRACTICE_DATE)
        record = stage_summary_post(
            value=practice.date,
            surface=WEEKLY_SUMMARY,
            channel_id="C-WEEK",
            message_ts="100.1",
            practices=[practice],
        )
        db.session.commit()
        assert record.week_start == REGISTRY_WEEK_START
        assert record.channel_id == "C-WEEK"
        assert practice.slack_weekly_summary_ts == "100.1"

        same = stage_summary_post(
            value=practice.date,
            surface=WEEKLY_SUMMARY,
            channel_id="C-WEEK",
            message_ts="100.2",
            practices=[practice],
        )
        assert same.id == record.id
        assert same.message_ts == "100.2"


def test_stage_summary_post_with_no_practices_creates_registry_row(app):
    with app.app_context():
        record = stage_summary_post(
            value=EMPTY_WEEK_START,
            surface=COACH_SUMMARY,
            channel_id="C-COACH",
            message_ts="200.1",
            practices=[],
        )
        db.session.flush()

        assert find_summary_post(date(2126, 2, 17), COACH_SUMMARY) is record


@pytest.mark.parametrize("surface", ["", "other_summary"])
def test_find_summary_post_rejects_unknown_surfaces(app, surface):
    with app.app_context():
        with pytest.raises(
            ValueError,
            match=f"Unknown practice summary surface: {surface}",
        ):
            find_summary_post(REGISTRY_WEEK_START, surface)


def test_stage_summary_post_rejects_unknown_surfaces(app):
    with app.app_context():
        with pytest.raises(
            ValueError,
            match="Unknown practice summary surface: other_summary",
        ):
            stage_summary_post(
                value=REGISTRY_WEEK_START,
                surface="other_summary",
                channel_id="C-OTHER",
                message_ts="300.1",
            )


def test_stage_summary_post_never_commits(app):
    with app.app_context(), patch.object(db.session, "commit") as commit:
        stage_summary_post(
            value=REGISTRY_WEEK_START,
            surface=COACH_SUMMARY,
            channel_id="C-COACH",
            message_ts="400.1",
        )

        commit.assert_not_called()


def test_summary_post_channel_prefers_registered_channel():
    record = SimpleNamespace(
        surface=WEEKLY_SUMMARY,
        channel_id="C-REGISTERED",
    )
    with patch(
        "app.slack.practices.summary_posts._get_announcement_channel"
    ) as configured_channel:
        assert summary_post_channel(record) == "C-REGISTERED"
    configured_channel.assert_not_called()


def test_summary_post_channel_resolves_legacy_coach_channel():
    record = SimpleNamespace(surface=COACH_SUMMARY, channel_id=None)

    assert summary_post_channel(record) == "C04AUHEDBSR"


def test_summary_post_channel_resolves_configured_legacy_public_channel():
    record = SimpleNamespace(surface=WEEKLY_SUMMARY, channel_id=None)
    with patch(
        "app.slack.practices.summary_posts._get_announcement_channel",
        return_value="C-CONFIGURED",
    ) as configured_channel:
        assert summary_post_channel(record) == "C-CONFIGURED"
    configured_channel.assert_called_once_with()


def test_summary_post_channel_rejects_unknown_legacy_surface():
    record = SimpleNamespace(surface="other_summary", channel_id=None)
    with patch(
        "app.slack.practices.summary_posts._get_announcement_channel"
    ) as configured_channel:
        with pytest.raises(
            ValueError,
            match="Unknown practice summary surface: other_summary",
        ):
            summary_post_channel(record)
    configured_channel.assert_not_called()


def test_fixture_refuses_ambient_reserved_row_without_deleting_it(app):
    teardown_probe = clear_summary_registry.__wrapped__(app)
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
            setup_probe = clear_summary_registry.__wrapped__(app)
            with pytest.raises(
                pytest.fail.Exception,
                match="existing rows; refusing to mutate",
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
