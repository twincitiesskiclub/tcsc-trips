"""Deleting a practice must not leave its dead Edit button in the rebuilt
weekly summaries.

The admin delete route calls refresh_practice_posts(change_type='delete')
*before* committing the delete, so the row is still queryable when the summary
is rebuilt. Without an explicit exclusion the deleted practice (and its now
dead Edit button) gets rendered back into the post, and the next click hits
"Practice not found". These tests pin the exclusion.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.models import db
from app.practices.models import Practice, PracticeLocation
from app.slack.practices import refresh as refreshmod


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips'
    )
    return app


@pytest.fixture
def week(app):
    """Two scheduled practices in the same week, both linked to the summary."""
    with app.app_context():
        # Create our own location: the test DB may be empty and this test
        # must not depend on ambient dev data.
        loc = PracticeLocation(name='Delete Exclusion Test Park')
        db.session.add(loc)
        db.session.commit()
        ts = '1780837200.000001'
        keep = Practice(date=datetime(2026, 6, 9, 18, 15), day_of_week='Tuesday',
                        status='scheduled', location_id=loc.id,
                        slack_coach_summary_ts=ts, slack_weekly_summary_ts=ts,
                        slack_channel_id='C1')
        dup = Practice(date=datetime(2026, 6, 9, 18, 15), day_of_week='Tuesday',
                       status='scheduled', location_id=loc.id,
                       slack_coach_summary_ts=ts, slack_weekly_summary_ts=ts,
                       slack_channel_id='C1')
        db.session.add_all([keep, dup])
        db.session.commit()
        yield keep, dup
        for p in (keep, dup):
            obj = db.session.get(Practice, p.id)
            if obj:
                db.session.delete(obj)
        db.session.commit()
        loc_obj = db.session.get(PracticeLocation, loc.id)
        if loc_obj:
            db.session.delete(loc_obj)
        db.session.commit()


def _capture_ids(builder_path, target, change_type):
    captured = {}

    def fake_build(infos, *a, **k):
        captured['ids'] = [getattr(i, 'id', None) for i in infos]
        return [{"type": "section", "text": {"type": "mrkdwn", "text": "x"}}]

    with patch(builder_path, side_effect=fake_build), \
            patch('app.slack.client.get_slack_client', return_value=MagicMock()), \
            patch(
                'app.slack.practices._config._get_announcement_channel',
                return_value='C-WEEKLY-ANNOUNCEMENTS',
            ), \
            patch('app.integrations.weather.get_weather_for_location',
                  side_effect=Exception("skip weather")):
        target(change_type)
    return captured.get('ids', [])


def test_coach_summary_excludes_deleted_practice(app, week):
    keep, dup = week
    with app.app_context():
        dup_obj = db.session.get(Practice, dup.id)
        ids = _capture_ids(
            'app.slack.blocks.build_coach_weekly_summary_blocks',
            lambda ct: refreshmod._refresh_coach_summary(dup_obj, ct),
            'delete',
        )
        assert dup.id not in ids, "deleted practice must be excluded from coach summary"
        assert keep.id in ids, "surviving practice must remain"


def test_coach_summary_edit_keeps_all(app, week):
    keep, dup = week
    with app.app_context():
        keep_obj = db.session.get(Practice, keep.id)
        ids = _capture_ids(
            'app.slack.blocks.build_coach_weekly_summary_blocks',
            lambda ct: refreshmod._refresh_coach_summary(keep_obj, ct),
            'edit',
        )
        assert keep.id in ids and dup.id in ids, "edit rebuilds the full week"


def test_weekly_summary_excludes_deleted_practice(app, week):
    keep, dup = week
    with app.app_context():
        dup_obj = db.session.get(Practice, dup.id)
        ids = _capture_ids(
            'app.slack.blocks.build_weekly_summary_blocks',
            lambda ct: refreshmod._refresh_weekly_summary(dup_obj, ct),
            'delete',
        )
        assert dup.id not in ids, "deleted practice must be excluded from weekly summary"
        assert keep.id in ids, "surviving practice must remain"


def test_weekly_summary_keeps_cancellation_and_uses_shared_builder_contract(
    app, week,
):
    keep, _dup = week
    with app.app_context():
        keep_obj = db.session.get(Practice, keep.id)
        cancelled = Practice(
            date=datetime(2026, 6, 11, 18, 15),
            day_of_week='Thursday',
            status='cancelled',
            cancellation_reason='Heat warning',
            location_id=keep_obj.location_id,
            slack_weekly_summary_ts=keep_obj.slack_weekly_summary_ts,
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
        assert captured['block_week_start'] == datetime(2026, 6, 8).date()
        assert captured['fallback_week_start'] == captured['block_week_start']
        assert captured['block_weather'] == captured['fallback_weather'] == {}
        client.chat_update.assert_called_once_with(
            channel='C-WEEKLY-ANNOUNCEMENTS',
            ts=keep_obj.slack_weekly_summary_ts,
            blocks=blocks,
            text=fallback,
        )

        db.session.delete(db.session.get(Practice, cancelled_id))
        db.session.commit()


def test_weekly_summary_refresh_fails_without_configured_channel(app, week):
    keep, _dup = week
    with app.app_context():
        keep_obj = db.session.get(Practice, keep.id)
        client = MagicMock()

        with patch(
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
