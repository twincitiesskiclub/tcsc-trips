"""Deleting a practice must not leave its dead Edit button in the rebuilt
weekly summaries.

The admin delete route calls refresh_practice_posts(change_type='delete')
*before* committing the delete, so the row is still queryable when the summary
is rebuilt. Without an explicit exclusion the deleted practice (and its now
dead Edit button) gets rendered back into the post, and the next click hits
"Practice not found". These tests pin the exclusion.
"""

from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.models import db
from app.practices.models import (
    Practice,
    PracticeLocation,
    PracticeSummaryPost,
)
from app.slack.practices import refresh as refreshmod
from app.slack.practices._config import (
    COACH_SUMMARY_FALLBACK_CHANNEL_ID,
    COLLAB_CHANNEL_ID,
)
from app.slack.practices.summary_posts import (
    COACH_SUMMARY,
    WEEKLY_SUMMARY,
)


WEEK_START = date(2126, 6, 10)
WEEK_END = WEEK_START + timedelta(days=7)
COACH_CHANNEL = "C-REGISTERED-COACH"
COACH_TS = "coach-registered-ts"
WEEKLY_CHANNEL = "C-REGISTERED-WEEKLY"
WEEKLY_TS = "weekly-registered-ts"


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips'
    )
    return app


def _reserved_practices():
    start = datetime.combine(WEEK_START, time.min)
    end = datetime.combine(WEEK_END, time.min)
    return (
        Practice.query.filter(Practice.date >= start, Practice.date < end)
        .order_by(Practice.id)
        .all()
    )


def _reserved_summary_posts():
    return (
        PracticeSummaryPost.query.filter_by(week_start=WEEK_START)
        .order_by(PracticeSummaryPost.id)
        .all()
    )


def _refuse_if_reserved_week_occupied():
    practices = _reserved_practices()
    summary_posts = _reserved_summary_posts()
    if practices or summary_posts:
        pytest.fail(
            "Reserved 2126 delete-exclusion test week contains existing rows; "
            "refusing to mutate persistent local PostgreSQL "
            f"(practice_ids={[row.id for row in practices]}, "
            f"summary_post_ids={[row.id for row in summary_posts]})"
        )


def _assert_fixture_owns_reserved_week(location_id, summary_post_ids):
    practices = _reserved_practices()
    summary_posts = _reserved_summary_posts()
    ambient_practices = [
        row for row in practices if row.location_id != location_id
    ]
    ambient_summary_posts = [
        row for row in summary_posts if row.id not in summary_post_ids
    ]
    if ambient_practices or ambient_summary_posts:
        pytest.fail(
            "Reserved 2126 delete-exclusion test week contains rows not owned "
            "by this fixture; refusing teardown deletion "
            f"(practice_ids={[row.id for row in ambient_practices]}, "
            "summary_post_ids="
            f"{[row.id for row in ambient_summary_posts]})"
        )
    return practices, summary_posts


@pytest.fixture
def week(app):
    """Two scheduled practices and canonical summary identities for the week."""
    with app.app_context():
        db.session.rollback()
        _refuse_if_reserved_week_occupied()
        # Create our own location: the test DB may be empty and this test
        # must not depend on ambient dev data.
        loc = PracticeLocation(name='Delete Exclusion Test Park')
        db.session.add(loc)
        db.session.commit()
        coach_record = PracticeSummaryPost(
            week_start=WEEK_START,
            surface=COACH_SUMMARY,
            channel_id=COACH_CHANNEL,
            message_ts=COACH_TS,
        )
        weekly_record = PracticeSummaryPost(
            week_start=WEEK_START,
            surface=WEEKLY_SUMMARY,
            channel_id=WEEKLY_CHANNEL,
            message_ts=WEEKLY_TS,
        )
        keep = Practice(date=datetime(2126, 6, 11, 18, 15), day_of_week='Tuesday',
                        status='scheduled', location_id=loc.id,
                        slack_coach_summary_ts='stale-coach-row-ts',
                        slack_weekly_summary_ts='stale-weekly-row-ts',
                        slack_channel_id='C1')
        dup = Practice(date=datetime(2126, 6, 11, 18, 15), day_of_week='Tuesday',
                       status='scheduled', location_id=loc.id,
                       slack_coach_summary_ts='other-stale-coach-row-ts',
                       slack_weekly_summary_ts='other-stale-weekly-row-ts',
                       slack_channel_id='C1')
        db.session.add_all([coach_record, weekly_record, keep, dup])
        db.session.commit()
        location_id = loc.id
        summary_post_ids = {coach_record.id, weekly_record.id}
        yield SimpleNamespace(
            keep=keep,
            dup=dup,
            coach_record=coach_record,
            weekly_record=weekly_record,
        )
        db.session.rollback()
        practices, summary_posts = _assert_fixture_owns_reserved_week(
            location_id,
            summary_post_ids,
        )
        for summary_post in summary_posts:
            db.session.delete(summary_post)
        for practice in practices:
            db.session.delete(practice)
        db.session.commit()
        loc_obj = db.session.get(PracticeLocation, location_id)
        if loc_obj:
            db.session.delete(loc_obj)
        db.session.commit()


def _capture_refresh(builder_path, target, change_type):
    captured = {}
    client = MagicMock()

    def fake_build(infos, *a, **k):
        captured['ids'] = [getattr(i, 'id', None) for i in infos]
        return [{"type": "section", "text": {"type": "mrkdwn", "text": "x"}}]

    with patch(builder_path, side_effect=fake_build), \
            patch('app.slack.blocks.build_weekly_summary_fallback_text',
                  return_value='weekly fallback'), \
            patch('app.slack.client.get_slack_client', return_value=client), \
            patch(
                'app.slack.practices._config._get_announcement_channel',
                return_value='C-LEGACY-CONFIGURED-WEEKLY',
            ), \
            patch('app.integrations.weather.get_weather_for_location',
                  side_effect=Exception("skip weather")):
        result = target(change_type)
    return SimpleNamespace(
        ids=captured.get('ids', []),
        client=client,
        result=result,
    )


def test_coach_summary_excludes_deleted_practice(app, week):
    with app.app_context():
        dup_obj = db.session.get(Practice, week.dup.id)
        outcome = _capture_refresh(
            'app.slack.blocks.build_coach_weekly_summary_blocks',
            lambda ct: refreshmod._refresh_coach_summary(dup_obj, ct),
            'delete',
        )
        assert week.dup.id not in outcome.ids, (
            "deleted practice must be excluded from coach summary"
        )
        assert week.keep.id in outcome.ids, "surviving practice must remain"


def test_coach_summary_edit_keeps_all(app, week):
    with app.app_context():
        keep_obj = db.session.get(Practice, week.keep.id)
        outcome = _capture_refresh(
            'app.slack.blocks.build_coach_weekly_summary_blocks',
            lambda ct: refreshmod._refresh_coach_summary(keep_obj, ct),
            'edit',
        )
        assert week.keep.id in outcome.ids
        assert week.dup.id in outcome.ids


def test_weekly_summary_excludes_deleted_practice(app, week):
    with app.app_context():
        dup_obj = db.session.get(Practice, week.dup.id)
        outcome = _capture_refresh(
            'app.slack.blocks.build_weekly_summary_blocks',
            lambda ct: refreshmod._refresh_weekly_summary(dup_obj, ct),
            'delete',
        )
        assert week.dup.id not in outcome.ids, (
            "deleted practice must be excluded from weekly summary"
        )
        assert week.keep.id in outcome.ids, "surviving practice must remain"


def test_registered_channel_and_timestamp_override_legacy_row_mirrors(app, week):
    with app.app_context():
        keep_obj = db.session.get(Practice, week.keep.id)

        coach = _capture_refresh(
            'app.slack.blocks.build_coach_weekly_summary_blocks',
            lambda ct: refreshmod._refresh_coach_summary(keep_obj, ct),
            'edit',
        )
        weekly = _capture_refresh(
            'app.slack.blocks.build_weekly_summary_blocks',
            lambda ct: refreshmod._refresh_weekly_summary(keep_obj, ct),
            'edit',
        )

        assert keep_obj.slack_coach_summary_ts != COACH_TS
        assert keep_obj.slack_weekly_summary_ts != WEEKLY_TS
        assert coach.client.chat_update.call_args.kwargs["channel"] == COACH_CHANNEL
        assert coach.client.chat_update.call_args.kwargs["ts"] == COACH_TS
        assert weekly.client.chat_update.call_args.kwargs["channel"] == WEEKLY_CHANNEL
        assert weekly.client.chat_update.call_args.kwargs["ts"] == WEEKLY_TS


def test_weekly_summary_keeps_cancellation_and_uses_shared_builder_contract(
    app, week,
):
    with app.app_context():
        keep_obj = db.session.get(Practice, week.keep.id)
        cancelled = Practice(
            date=datetime(2126, 6, 13, 18, 15),
            day_of_week='Thursday',
            status='cancelled',
            cancellation_reason='Heat warning',
            location_id=keep_obj.location_id,
            slack_weekly_summary_ts='cancelled-stale-row-ts',
            slack_channel_id='C1',
        )
        db.session.add(cancelled)
        db.session.commit()
        cancelled_id = cancelled.id
        captured = {}
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "week"}}
        ]
        fallback = "Complete weekly fallback including cancellation"

        def fake_blocks(infos, *, week_start, weather_data):
            captured['block_ids'] = [info.id for info in infos]
            captured['block_week_start'] = week_start
            captured['block_weather'] = weather_data
            return blocks

        def fake_fallback(infos, *, week_start, weather_data):
            captured['fallback_ids'] = [info.id for info in infos]
            captured['fallback_week_start'] = week_start
            captured['fallback_weather'] = weather_data
            return fallback

        client = MagicMock()
        with patch(
            'app.slack.blocks.build_weekly_summary_blocks',
            side_effect=fake_blocks,
        ), patch(
            'app.slack.blocks.build_weekly_summary_fallback_text',
            side_effect=fake_fallback,
            create=True,
        ), patch(
            'app.slack.client.get_slack_client', return_value=client,
        ), patch(
            'app.slack.practices._config._get_announcement_channel',
            return_value='C-WEEKLY-ANNOUNCEMENTS',
        ):
            result = refreshmod._refresh_weekly_summary(keep_obj, 'edit')

        assert result == {'success': True}
        assert cancelled_id in captured['block_ids']
        assert captured['block_ids'] == captured['fallback_ids']
        assert captured['block_week_start'] == WEEK_START
        assert captured['fallback_week_start'] == captured['block_week_start']
        assert captured['block_weather'] == captured['fallback_weather'] == {}
        client.chat_update.assert_called_once_with(
            channel=WEEKLY_CHANNEL,
            ts=WEEKLY_TS,
            blocks=blocks,
            text=fallback,
        )

        db.session.delete(db.session.get(Practice, cancelled_id))
        db.session.commit()


def test_weekly_summary_refresh_fails_without_configured_channel(app, week):
    with app.app_context():
        keep_obj = db.session.get(Practice, week.keep.id)
        weekly_record = db.session.get(
            PracticeSummaryPost,
            week.weekly_record.id,
        )
        weekly_record.channel_id = None
        db.session.commit()
        client = MagicMock()

        with patch(
            'app.slack.practices.summary_posts._get_announcement_channel',
            return_value=None,
        ), patch(
            'app.slack.practices._config._get_announcement_channel',
            return_value=None,
        ), patch(
            'app.slack.client.get_slack_client', return_value=client,
        ):
            result = refreshmod._refresh_weekly_summary(keep_obj, 'edit')

        assert result == {
            'success': False,
            'error': 'Announcement channel is not configured',
        }
        client.chat_update.assert_not_called()


def test_legacy_null_coach_channel_persists_successful_fallback_only(app, week):
    with app.app_context():
        keep_obj = db.session.get(Practice, week.keep.id)
        coach_record = db.session.get(
            PracticeSummaryPost,
            week.coach_record.id,
        )
        coach_record.channel_id = None
        db.session.commit()

        keep_obj.day_of_week = "UNCOMMITTED MUTATION"
        client = MagicMock()
        client.chat_update.side_effect = [
            RuntimeError("not in primary coach channel"),
            None,
        ]

        with patch(
            'app.slack.blocks.build_coach_weekly_summary_blocks',
            return_value=[],
        ), patch(
            'app.slack.client.get_slack_client',
            return_value=client,
        ):
            result = refreshmod._refresh_coach_summary(keep_obj, 'edit')

        assert result == {'success': True}
        assert [
            call.kwargs['channel'] for call in client.chat_update.call_args_list
        ] == [COLLAB_CHANNEL_ID, COACH_SUMMARY_FALLBACK_CHANNEL_ID]

        db.session.rollback()
        db.session.expire_all()
        persisted_record = db.session.get(
            PracticeSummaryPost,
            week.coach_record.id,
        )
        persisted_practice = db.session.get(Practice, week.keep.id)
        assert persisted_record.channel_id == COACH_SUMMARY_FALLBACK_CHANNEL_ID
        assert persisted_practice.day_of_week == 'Tuesday'


def test_migrated_null_public_channel_stays_bound_after_config_change(
    app,
    week,
):
    with app.app_context():
        keep_obj = db.session.get(Practice, week.keep.id)
        weekly_record = db.session.get(
            PracticeSummaryPost,
            week.weekly_record.id,
        )
        weekly_record.channel_id = None
        db.session.commit()

        keep_obj.day_of_week = "UNCOMMITTED MUTATION"
        client = MagicMock()

        with patch(
            'app.slack.blocks.build_weekly_summary_blocks',
            return_value=[],
        ), patch(
            'app.slack.blocks.build_weekly_summary_fallback_text',
            return_value='weekly fallback',
        ), patch(
            'app.slack.client.get_slack_client',
            return_value=client,
        ):
            with patch(
                'app.slack.practices.summary_posts._get_announcement_channel',
                return_value='C-PUBLIC-A',
            ) as configured_a:
                first_result = refreshmod._refresh_weekly_summary(
                    keep_obj,
                    'edit',
                )
            with patch(
                'app.slack.practices.summary_posts._get_announcement_channel',
                return_value='C-PUBLIC-B',
            ) as configured_b:
                second_result = refreshmod._refresh_weekly_summary(
                    keep_obj,
                    'edit',
                )

        assert first_result == second_result == {'success': True}
        assert [
            call.kwargs['channel'] for call in client.chat_update.call_args_list
        ] == ['C-PUBLIC-A', 'C-PUBLIC-A']
        configured_a.assert_called_once_with()
        configured_b.assert_not_called()

        db.session.rollback()
        db.session.expire_all()
        persisted_record = db.session.get(
            PracticeSummaryPost,
            week.weekly_record.id,
        )
        persisted_practice = db.session.get(Practice, week.keep.id)
        assert persisted_record.channel_id == 'C-PUBLIC-A'
        assert persisted_practice.day_of_week == 'Tuesday'
