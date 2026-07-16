from datetime import date, datetime
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
TEST_WEEK_STARTS = (date(2026, 7, 13), date(2026, 7, 20))


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture(autouse=True)
def clear_summary_registry(app):
    def clear_rows():
        db.session.rollback()
        PracticeSummaryPost.query.filter(
            PracticeSummaryPost.week_start.in_(TEST_WEEK_STARTS)
        ).delete(synchronize_session=False)
        Practice.query.filter_by(
            airtable_id=TEST_PRACTICE_AIRTABLE_ID
        ).delete()
        db.session.commit()

    with app.app_context():
        clear_rows()
    try:
        yield
    finally:
        with app.app_context():
            clear_rows()


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
        (date(2026, 7, 13), date(2026, 7, 13)),
        (date(2026, 7, 19), date(2026, 7, 13)),
        (datetime(2026, 7, 16, 18, 5), date(2026, 7, 13)),
    ],
)
def test_week_start_date_is_monday(value, expected):
    assert week_start_date(value) == expected


def test_stage_summary_post_upserts_identity_and_legacy_links(app):
    with app.app_context():
        practice = make_practice(datetime(2026, 7, 14, 18, 15))
        record = stage_summary_post(
            value=practice.date,
            surface=WEEKLY_SUMMARY,
            channel_id="C-WEEK",
            message_ts="100.1",
            practices=[practice],
        )
        db.session.commit()
        assert record.week_start == date(2026, 7, 13)
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
            value=date(2026, 7, 20),
            surface=COACH_SUMMARY,
            channel_id="C-COACH",
            message_ts="200.1",
            practices=[],
        )
        db.session.flush()

        assert find_summary_post(date(2026, 7, 26), COACH_SUMMARY) is record


@pytest.mark.parametrize("surface", ["", "other_summary"])
def test_find_summary_post_rejects_unknown_surfaces(app, surface):
    with app.app_context():
        with pytest.raises(
            ValueError,
            match=f"Unknown practice summary surface: {surface}",
        ):
            find_summary_post(date(2026, 7, 13), surface)


def test_stage_summary_post_rejects_unknown_surfaces(app):
    with app.app_context():
        with pytest.raises(
            ValueError,
            match="Unknown practice summary surface: other_summary",
        ):
            stage_summary_post(
                value=date(2026, 7, 13),
                surface="other_summary",
                channel_id="C-OTHER",
                message_ts="300.1",
            )


def test_stage_summary_post_never_commits(app):
    with app.app_context(), patch.object(db.session, "commit") as commit:
        stage_summary_post(
            value=date(2026, 7, 13),
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
