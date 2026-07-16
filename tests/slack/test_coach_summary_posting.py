"""Coach weekly-summary posting and compensation contracts."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

import app.models as models
import app.slack.practices.coach_review as coach_review
from app.practices.models import Practice


WEEK_START = datetime(2026, 7, 13)
MESSAGE_TS = "1783980000.000200"


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_criteria):
        return self

    def order_by(self, *_columns):
        return self

    def all(self):
        return self.rows


def practice(practice_id, when):
    return SimpleNamespace(
        id=practice_id,
        date=when,
        slack_coach_summary_ts=None,
    )


def run_coach_summary(
    practices,
    *,
    channel_override=None,
    post_response=None,
    commit_effects=None,
    cleanup_error=None,
):
    client = MagicMock()
    client.chat_postMessage.return_value = (
        {"ts": MESSAGE_TS} if post_response is None else post_response
    )
    if cleanup_error is not None:
        client.chat_delete.side_effect = cleanup_error

    fake_db = SimpleNamespace(session=MagicMock())
    if commit_effects is not None:
        fake_db.session.commit.side_effect = commit_effects

    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "week"}}]
    channel_lookup = MagicMock(return_value="C-OVERRIDE")
    logger = MagicMock()
    app_config = SimpleNamespace(get=MagicMock(return_value=[]))
    tag_model = SimpleNamespace(
        name=object(),
        query=FakeQuery([]),
    )
    practice_model = SimpleNamespace(
        query=FakeQuery(practices),
        date=Practice.date,
    )

    def stage_summary(*, message_ts, practices, **_kwargs):
        for practice_item in practices:
            practice_item.slack_coach_summary_ts = message_ts

    with patch.object(coach_review, "Practice", practice_model), patch.object(
        coach_review, "current_app", SimpleNamespace(logger=logger)
    ), patch.object(
        coach_review, "get_slack_client", return_value=client
    ), patch.object(
        coach_review, "get_channel_id_by_name", channel_lookup
    ), patch.object(
        coach_review, "db", fake_db
    ), patch.object(
        coach_review,
        "stage_summary_post",
        side_effect=stage_summary,
        create=True,
    ) as stage_summary_post, patch.object(
        models, "AppConfig", app_config
    ), patch.object(
        models, "Tag", tag_model
    ), patch.object(
        models, "db", fake_db
    ), patch(
        "app.practices.service.convert_practice_to_info",
        side_effect=lambda item: item,
    ), patch(
        "app.slack.blocks.build_coach_weekly_summary_blocks",
        return_value=blocks,
    ) as build_blocks:
        result = coach_review.post_coach_weekly_summary(
            WEEK_START,
            channel_override=channel_override,
        )

    return SimpleNamespace(
        result=result,
        client=client,
        db=fake_db,
        stage_summary_post=stage_summary_post,
        build_blocks=build_blocks,
        blocks=blocks,
        channel_lookup=channel_lookup,
        logger=logger,
    )


def test_empty_production_week_registers_coach_refresh_identity():
    outcome = run_coach_summary([])

    outcome.client.chat_postMessage.assert_called_once_with(
        channel=coach_review.COLLAB_CHANNEL_ID,
        blocks=outcome.blocks,
        text="Coach Review: Week of July 13",
        unfurl_links=False,
        unfurl_media=False,
    )
    outcome.stage_summary_post.assert_called_once_with(
        value=WEEK_START,
        surface="coach_summary",
        channel_id=coach_review.COLLAB_CHANNEL_ID,
        message_ts=MESSAGE_TS,
        practices=[],
    )
    assert outcome.result == {
        "success": True,
        "message_ts": MESSAGE_TS,
        "channel_id": coach_review.COLLAB_CHANNEL_ID,
        "refresh_linked": True,
    }
    outcome.db.session.commit.assert_called_once_with()


def test_non_empty_production_week_registers_coach_refresh_identity():
    practices = [
        practice(1, datetime(2026, 7, 14, 18, 15)),
        practice(2, datetime(2026, 7, 16, 18, 5)),
    ]

    outcome = run_coach_summary(practices)

    outcome.stage_summary_post.assert_called_once_with(
        value=WEEK_START,
        surface="coach_summary",
        channel_id=coach_review.COLLAB_CHANNEL_ID,
        message_ts=MESSAGE_TS,
        practices=practices,
    )
    assert [item.slack_coach_summary_ts for item in practices] == [
        MESSAGE_TS,
        MESSAGE_TS,
    ]
    assert outcome.result["refresh_linked"] is True
    outcome.db.session.commit.assert_called_once_with()


def test_channel_override_posts_coach_preview_without_persisting():
    practices = [practice(1, datetime(2026, 7, 14, 18, 15))]

    outcome = run_coach_summary(
        practices,
        channel_override="#coach-preview",
    )

    outcome.channel_lookup.assert_called_once_with("coach-preview")
    outcome.client.chat_postMessage.assert_called_once_with(
        channel="C-OVERRIDE",
        blocks=outcome.blocks,
        text="Coach Review: Week of July 13",
        unfurl_links=False,
        unfurl_media=False,
    )
    assert outcome.result == {
        "success": True,
        "message_ts": MESSAGE_TS,
        "channel_id": "C-OVERRIDE",
        "refresh_linked": False,
    }
    assert practices[0].slack_coach_summary_ts is None
    outcome.stage_summary_post.assert_not_called()
    outcome.db.session.commit.assert_not_called()


def test_missing_coach_timestamp_does_not_stage_or_commit():
    practices = [practice(1, datetime(2026, 7, 14, 18, 15))]

    outcome = run_coach_summary(practices, post_response={})

    assert outcome.result == {
        "success": False,
        "error": "Slack returned no message timestamp",
        "refresh_linked": False,
    }
    assert practices[0].slack_coach_summary_ts is None
    outcome.stage_summary_post.assert_not_called()
    outcome.db.session.commit.assert_not_called()


@pytest.mark.parametrize(
    ("cleanup_fails", "commit_effects", "expected_outcome"),
    [
        (False, [RuntimeError("database commit failed")], "cleaned"),
        (
            True,
            [RuntimeError("database commit failed"), None],
            "recovered",
        ),
        (
            True,
            [
                RuntimeError("database commit failed"),
                RuntimeError("recovery commit failed"),
            ],
            "ambiguous",
        ),
    ],
)
def test_coach_link_commit_failure_compensates_or_recovers_once(
    cleanup_fails,
    commit_effects,
    expected_outcome,
):
    practices = [
        practice(1, datetime(2026, 7, 14, 18, 15)),
        practice(2, datetime(2026, 7, 16, 18, 5)),
    ]
    cleanup_error = (
        RuntimeError("cleanup failed") if cleanup_fails else None
    )

    outcome = run_coach_summary(
        practices,
        commit_effects=commit_effects,
        cleanup_error=cleanup_error,
    )

    recovered = expected_outcome == "recovered"
    assert outcome.result["success"] is recovered
    assert outcome.result["refresh_linked"] is recovered
    assert outcome.result["cleanup"]["success"] is (not cleanup_fails)
    if recovered:
        assert outcome.result["recovered"] is True
        assert outcome.result["message_ts"] == MESSAGE_TS
        assert outcome.result["channel_id"] == coach_review.COLLAB_CHANNEL_ID
        assert [item.slack_coach_summary_ts for item in practices] == [
            MESSAGE_TS,
            MESSAGE_TS,
        ]
    else:
        assert "database commit failed" in outcome.result["error"]
        assert [item.slack_coach_summary_ts for item in practices] == [None, None]
    if expected_outcome == "ambiguous":
        assert "recovery commit failed" in outcome.result["error"]
        assert outcome.result["ambiguous_orphan"] == {
            "channel_id": coach_review.COLLAB_CHANNEL_ID,
            "message_ts": MESSAGE_TS,
        }
        outcome.logger.critical.assert_called_once()
    else:
        assert "ambiguous_orphan" not in outcome.result

    expected_stage_calls = 2 if cleanup_fails else 1
    assert outcome.stage_summary_post.call_count == expected_stage_calls
    assert outcome.stage_summary_post.call_args_list == [
        call(
            value=WEEK_START,
            surface="coach_summary",
            channel_id=coach_review.COLLAB_CHANNEL_ID,
            message_ts=MESSAGE_TS,
            practices=practices,
        )
    ] * expected_stage_calls
    assert outcome.db.session.commit.call_count == expected_stage_calls
    assert outcome.db.session.rollback.call_count == (
        2 if expected_outcome == "ambiguous" else 1
    )
    outcome.client.chat_delete.assert_called_once_with(
        channel=coach_review.COLLAB_CHANNEL_ID,
        ts=MESSAGE_TS,
    )
