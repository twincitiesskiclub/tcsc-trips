"""Registered weekly summaries follow practices across calendar weeks."""

from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.models import db
from app.practices.models import Practice, PracticeSummaryPost
from app.slack.practices import refresh as refreshmod
from app.slack.practices.summary_posts import (
    COACH_SUMMARY,
    WEEKLY_SUMMARY,
)


SOURCE_WEEK = date(2126, 7, 8)
DESTINATION_WEEK = date(2126, 7, 15)
RESERVED_WEEK_STARTS = (SOURCE_WEEK, DESTINATION_WEEK)
TEST_AIRTABLE_PREFIX = "cross-week-summary-refresh-"
TEST_SUMMARY_IDENTITIES = {
    (SOURCE_WEEK, COACH_SUMMARY, "C-coach-A", "coach-A"),
    (SOURCE_WEEK, WEEKLY_SUMMARY, "C-public-A", "public-A"),
    (DESTINATION_WEEK, COACH_SUMMARY, "C-coach-B", "coach-B"),
    (DESTINATION_WEEK, WEEKLY_SUMMARY, "C-public-B", "public-B"),
}


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture(autouse=True)
def clear_cross_week_rows(app):
    with app.app_context():
        db.session.rollback()
        _refuse_if_reserved_weeks_occupied()
    try:
        yield
    finally:
        with app.app_context():
            db.session.rollback()
            practices, summary_posts = _assert_reserved_rows_owned()
            for summary_post in summary_posts:
                db.session.delete(summary_post)
            for practice in practices:
                db.session.delete(practice)
            db.session.commit()


def _reserved_practices():
    start = datetime.combine(SOURCE_WEEK, time.min)
    end = datetime.combine(DESTINATION_WEEK + timedelta(days=7), time.min)
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


def _refuse_if_reserved_weeks_occupied():
    practices = _reserved_practices()
    summary_posts = _reserved_summary_posts()
    if practices or summary_posts:
        pytest.fail(
            "Reserved 2126 cross-week test weeks contain existing rows; "
            "refusing to mutate persistent local PostgreSQL "
            f"(practice_ids={[row.id for row in practices]}, "
            f"summary_post_ids={[row.id for row in summary_posts]})"
        )


def _assert_reserved_rows_owned():
    practices = _reserved_practices()
    summary_posts = _reserved_summary_posts()
    ambient_practices = [
        row
        for row in practices
        if not (row.airtable_id or "").startswith(TEST_AIRTABLE_PREFIX)
    ]
    ambient_summary_posts = [
        row
        for row in summary_posts
        if (
            row.week_start,
            row.surface,
            row.channel_id,
            row.message_ts,
        )
        not in TEST_SUMMARY_IDENTITIES
    ]
    if ambient_practices or ambient_summary_posts:
        pytest.fail(
            "Reserved 2126 cross-week test weeks contain rows not owned by "
            "this fixture; refusing teardown deletion "
            f"(practice_ids={[row.id for row in ambient_practices]}, "
            "summary_post_ids="
            f"{[row.id for row in ambient_summary_posts]})"
        )
    return practices, summary_posts


def make_practice(label, value):
    practice = Practice(
        date=value,
        day_of_week=value.strftime("%A"),
        status="scheduled",
        airtable_id=f"{TEST_AIRTABLE_PREFIX}{label}",
    )
    db.session.add(practice)
    return practice


def register_week(week_start, suffix):
    records = [
        PracticeSummaryPost(
            week_start=week_start,
            surface=COACH_SUMMARY,
            channel_id=f"C-coach-{suffix}",
            message_ts=f"coach-{suffix}",
        ),
        PracticeSummaryPost(
            week_start=week_start,
            surface=WEEKLY_SUMMARY,
            channel_id=f"C-public-{suffix}",
            message_ts=f"public-{suffix}",
        ),
    ]
    db.session.add_all(records)
    return records


def run_refresh(practice, *, previous_date):
    updates = {}
    client = MagicMock()

    def build_blocks(infos, *_args, **_kwargs):
        return [{"practice_ids": [info.id for info in infos]}]

    def capture_update(**kwargs):
        updates[kwargs["ts"]] = kwargs["blocks"][0]["practice_ids"]

    client.chat_update.side_effect = capture_update
    with patch(
        "app.slack.blocks.build_coach_weekly_summary_blocks",
        side_effect=build_blocks,
    ), patch(
        "app.slack.blocks.build_weekly_summary_blocks",
        side_effect=build_blocks,
    ), patch(
        "app.slack.blocks.build_weekly_summary_fallback_text",
        return_value="weekly fallback",
    ), patch(
        "app.slack.client.get_slack_client",
        return_value=client,
    ), patch(
        "app.integrations.weather.get_weather_for_location",
        side_effect=AssertionError("weather must not run without coordinates"),
    ):
        results = refreshmod.refresh_practice_posts(
            practice,
            change_type="edit",
            previous_date=previous_date,
        )

    return SimpleNamespace(results=results, updates=updates, client=client)


def move_to_destination(practice):
    practice.date = datetime(2126, 7, 18, 18, 15)
    practice.day_of_week = "Thursday"
    db.session.commit()


def test_cross_week_edit_refreshes_registered_source_and_destination(app):
    with app.app_context():
        remaining_a = make_practice(
            "remaining-a", datetime(2126, 7, 9, 18, 15)
        )
        moved = make_practice("moved", datetime(2126, 7, 11, 18, 15))
        existing_b = make_practice(
            "existing-b", datetime(2126, 7, 16, 18, 15)
        )
        register_week(SOURCE_WEEK, "A")
        register_week(DESTINATION_WEEK, "B")
        db.session.commit()
        move_to_destination(moved)

        outcome = run_refresh(
            moved,
            previous_date=datetime(2126, 7, 9, 18, 15),
        )

        assert outcome.updates["coach-A"] == [remaining_a.id]
        assert outcome.updates["public-A"] == [remaining_a.id]
        assert outcome.updates["coach-B"] == [existing_b.id, moved.id]
        assert outcome.updates["public-B"] == [existing_b.id, moved.id]
        assert outcome.results["previous_coach_summary"]["success"] is True
        assert outcome.results["previous_weekly_summary"]["success"] is True
        assert outcome.client.chat_update.call_count == 4


@pytest.mark.parametrize(
    ("registered_week", "expected_updates", "destination_present"),
    [
        (
            "source",
            {"coach-A": ["remaining"], "public-A": ["remaining"]},
            False,
        ),
        (
            "destination",
            {"coach-B": ["existing", "moved"],
             "public-B": ["existing", "moved"]},
            True,
        ),
    ],
)
def test_cross_week_edit_refreshes_whichever_week_is_registered(
    app,
    registered_week,
    expected_updates,
    destination_present,
):
    with app.app_context():
        practices = {
            "remaining": make_practice(
                "remaining", datetime(2126, 7, 9, 18, 15)
            ),
            "moved": make_practice(
                "moved", datetime(2126, 7, 11, 18, 15)
            ),
            "existing": make_practice(
                "existing", datetime(2126, 7, 16, 18, 15)
            ),
        }
        if registered_week == "source":
            register_week(SOURCE_WEEK, "A")
        else:
            register_week(DESTINATION_WEEK, "B")
        db.session.commit()
        move_to_destination(practices["moved"])

        outcome = run_refresh(
            practices["moved"],
            previous_date=datetime(2126, 7, 9, 18, 15),
        )

        expected_ids = {
            timestamp: [practices[label].id for label in labels]
            for timestamp, labels in expected_updates.items()
        }
        assert outcome.updates == expected_ids
        assert (
            outcome.results["coach_summary"].get("success") is True
        ) is destination_present
        assert (
            outcome.results["weekly_summary"].get("success") is True
        ) is destination_present
        assert (
            outcome.results["previous_coach_summary"].get("success") is True
        ) is (not destination_present)
        assert (
            outcome.results["previous_weekly_summary"].get("success") is True
        ) is (not destination_present)


def test_cross_week_edit_updates_empty_source_without_deleting_registry(app):
    with app.app_context():
        moved = make_practice("moved", datetime(2126, 7, 11, 18, 15))
        existing_b = make_practice(
            "existing-b", datetime(2126, 7, 16, 18, 15)
        )
        source_records = register_week(SOURCE_WEEK, "A")
        register_week(DESTINATION_WEEK, "B")
        db.session.commit()
        source_record_ids = [record.id for record in source_records]
        move_to_destination(moved)

        outcome = run_refresh(
            moved,
            previous_date=datetime(2126, 7, 9, 18, 15),
        )

        assert outcome.updates["coach-A"] == []
        assert outcome.updates["public-A"] == []
        assert outcome.updates["coach-B"] == [existing_b.id, moved.id]
        assert outcome.updates["public-B"] == [existing_b.id, moved.id]
        assert [
            db.session.get(PracticeSummaryPost, record_id).message_ts
            for record_id in source_record_ids
        ] == ["coach-A", "public-A"]


def test_independent_refresh_accepts_canonical_monday_date(app):
    with app.app_context():
        practice = make_practice(
            "source-only", datetime(2126, 7, 9, 18, 15)
        )
        register_week(SOURCE_WEEK, "A")
        db.session.commit()

        outcome = run_refresh_for_week(SOURCE_WEEK)

        assert outcome.results == {
            "coach_summary": {"success": True},
            "weekly_summary": {"success": True},
        }
        assert outcome.updates == {
            "coach-A": [practice.id],
            "public-A": [practice.id],
        }


def run_refresh_for_week(value):
    updates = {}
    client = MagicMock()

    def build_blocks(infos, *_args, **_kwargs):
        return [{"practice_ids": [info.id for info in infos]}]

    client.chat_update.side_effect = lambda **kwargs: updates.__setitem__(
        kwargs["ts"], kwargs["blocks"][0]["practice_ids"]
    )
    with patch(
        "app.slack.blocks.build_coach_weekly_summary_blocks",
        side_effect=build_blocks,
    ), patch(
        "app.slack.blocks.build_weekly_summary_blocks",
        side_effect=build_blocks,
    ), patch(
        "app.slack.blocks.build_weekly_summary_fallback_text",
        return_value="weekly fallback",
    ), patch(
        "app.slack.client.get_slack_client", return_value=client
    ):
        results = refreshmod.refresh_registered_practice_summaries(value)

    return SimpleNamespace(results=results, updates=updates)
