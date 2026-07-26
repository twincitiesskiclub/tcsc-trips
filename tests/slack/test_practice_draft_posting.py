"""Readiness digest posting."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models import db
from app.practices.models import PracticeSummaryPost
from app.slack.practices.summary_posts import READINESS_DIGEST

# Far-future block anchors so these rows can never collide with real data in
# the shared local dev database (see tests/practices/conftest.py conventions).
THREADED_BLOCK_START = date(2099, 8, 1)
FALLBACK_BLOCK_START = date(2099, 9, 1)


def _practice(day):
    # readiness_summary() (Task 4) reads location_id/practice_types/activities
    # off the practice, not `location` — using the real attribute names here
    # so post_readiness_digest's call into it doesn't AttributeError.
    return SimpleNamespace(
        id=day, date=datetime(2026, 8, day, 18, 15),
        location_id=None, practice_types=[], activities=[],
    )


def _digest_records(block_start):
    return PracticeSummaryPost.query.filter_by(
        week_start=block_start, surface=READINESS_DIGEST
    ).all()


def _delete_digest_records(block_start):
    for record in _digest_records(block_start):
        db.session.delete(record)
    db.session.commit()


def test_posts_to_the_coaches_channel(app):
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.return_value = {"ok": True, "ts": "1785000000.1"}

    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([_practice(4)], "Jul 21", "Aug 13")

    assert result["success"] is True
    assert result["ts"] == "1785000000.1"
    kwargs = client.chat_postMessage.call_args.kwargs
    from app.slack.practices._config import COLLAB_CHANNEL_ID
    assert kwargs["channel"] == COLLAB_CHANNEL_ID
    assert kwargs["blocks"], "digest must carry blocks"
    assert kwargs["text"], "fallback text is required for notifications and screen readers"


def test_slack_failure_is_reported_not_raised(app):
    from slack_sdk.errors import SlackApiError

    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.side_effect = SlackApiError(
        "boom", response={"error": "channel_not_found"}
    )

    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([_practice(4)], "Jul 21", "Aug 13")

    assert result["success"] is False
    assert result["error"] == "channel_not_found"


def test_non_slack_failure_is_reported_not_raised(app):
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.side_effect = TimeoutError("connection timed out")

    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([_practice(4)], "Jul 21", "Aug 13")

    assert result["success"] is False
    assert "connection timed out" in result["error"]


def test_response_without_ts_is_reported_not_raised(app):
    """A malformed Slack response must come back as a failure dict, not a
    KeyError escaping the never-raises contract."""
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.return_value = {"ok": True}  # no "ts"

    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([_practice(4)], "Jul 21", "Aug 13")

    assert result["success"] is False


def test_digest_lookup_failure_is_reported_not_raised(app):
    """A DB error while resolving the recorded digest must come back as a
    failure dict, not raise out of the never-raises contract."""
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    with patch(
        "app.slack.practices.drafts.get_slack_client", return_value=client
    ), patch(
        "app.slack.practices.drafts.find_readiness_digest_post",
        side_effect=RuntimeError("TEST db unavailable"),
    ):
        with app.app_context():
            result = post_readiness_digest(
                [_practice(4)], "Jul 21", "Aug 13",
                block_start=THREADED_BLOCK_START,
            )

    assert result["success"] is False
    assert "TEST db unavailable" in result["error"]
    client.chat_postMessage.assert_not_called()


def test_nudge_threads_onto_the_recorded_digest(app):
    """A recorded digest identity turns the daily nudge into a thread reply."""
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.return_value = {"ok": True, "ts": "1785000099.2"}

    with app.app_context():
        assert not _digest_records(THREADED_BLOCK_START), (
            "reserved 2099 block anchor already occupied in the dev database"
        )
        record = PracticeSummaryPost(
            week_start=THREADED_BLOCK_START,
            surface=READINESS_DIGEST,
            channel_id="C-TEST-DIGEST",
            message_ts="1785000000.42",
        )
        db.session.add(record)
        db.session.commit()
        try:
            with patch(
                "app.slack.practices.drafts.get_slack_client", return_value=client
            ):
                result = post_readiness_digest(
                    [_practice(4)], "Jul 21", "Aug 13",
                    block_start=THREADED_BLOCK_START,
                )

            assert result["success"] is True
            kwargs = client.chat_postMessage.call_args.kwargs
            assert kwargs["channel"] == "C-TEST-DIGEST"
            assert kwargs["thread_ts"] == "1785000000.42"
            assert len(_digest_records(THREADED_BLOCK_START)) == 1, (
                "threading must reuse the recorded identity, not create another"
            )
        finally:
            db.session.rollback()
            _delete_digest_records(THREADED_BLOCK_START)


def test_nudge_without_a_recorded_digest_posts_top_level_and_records(app):
    """No digest on record → post top-level, remember it, thread the next day."""
    from app.slack.practices._config import COLLAB_CHANNEL_ID
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.return_value = {"ok": True, "ts": "1785000001.7"}

    with app.app_context():
        assert not _digest_records(FALLBACK_BLOCK_START), (
            "reserved 2099 block anchor already occupied in the dev database"
        )
        try:
            with patch(
                "app.slack.practices.drafts.get_slack_client", return_value=client
            ):
                result = post_readiness_digest(
                    [_practice(4)], "Jul 21", "Aug 13",
                    block_start=FALLBACK_BLOCK_START,
                )

            assert result["success"] is True
            kwargs = client.chat_postMessage.call_args.kwargs
            assert kwargs["channel"] == COLLAB_CHANNEL_ID
            assert "thread_ts" not in kwargs, "fallback must be a top-level post"

            records = _digest_records(FALLBACK_BLOCK_START)
            assert len(records) == 1
            assert records[0].channel_id == COLLAB_CHANNEL_ID
            assert records[0].message_ts == "1785000001.7"

            # The very next day's nudge threads onto the recorded fallback.
            client.chat_postMessage.return_value = {"ok": True, "ts": "1785000002.9"}
            with patch(
                "app.slack.practices.drafts.get_slack_client", return_value=client
            ):
                post_readiness_digest(
                    [_practice(4)], "Jul 22", "Aug 13",
                    block_start=FALLBACK_BLOCK_START,
                )
            kwargs = client.chat_postMessage.call_args.kwargs
            assert kwargs["thread_ts"] == "1785000001.7"
        finally:
            db.session.rollback()
            _delete_digest_records(FALLBACK_BLOCK_START)


def test_deleted_thread_parent_clears_the_record_and_reposts_top_level(app):
    """If the recorded digest post was deleted in Slack, every later nudge
    would thread onto a dead ts, fail, and only log — silently stopping the
    chase for the rest of the block. The record is only a cache of where to
    thread: on message_not_found, drop it, post top-level, and record the
    new post so tomorrow's nudge threads onto IT."""
    from slack_sdk.errors import SlackApiError

    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.side_effect = [
        SlackApiError("boom", response={"error": "message_not_found"}),
        {"ok": True, "ts": "1785000020.5"},
    ]

    with app.app_context():
        assert not _digest_records(THREADED_BLOCK_START), (
            "reserved 2099 block anchor already occupied in the dev database"
        )
        record = PracticeSummaryPost(
            week_start=THREADED_BLOCK_START,
            surface=READINESS_DIGEST,
            channel_id="C-TEST-DIGEST",
            message_ts="1785000000.42",  # deleted in Slack
        )
        db.session.add(record)
        db.session.commit()
        try:
            with patch(
                "app.slack.practices.drafts.get_slack_client", return_value=client
            ):
                result = post_readiness_digest(
                    [_practice(4)], "Jul 21", "Aug 13",
                    block_start=THREADED_BLOCK_START,
                )

            assert result["success"] is True
            assert result["ts"] == "1785000020.5"

            first, second = client.chat_postMessage.call_args_list
            assert first.kwargs["thread_ts"] == "1785000000.42"
            assert "thread_ts" not in second.kwargs, (
                "the retry must be a top-level post, not another dead thread"
            )

            records = _digest_records(THREADED_BLOCK_START)
            assert len(records) == 1, "the dead record must be replaced, not kept"
            assert records[0].message_ts == "1785000020.5", (
                "the new top-level post must become the block's digest identity"
            )
        finally:
            db.session.rollback()
            _delete_digest_records(THREADED_BLOCK_START)


def test_other_slack_errors_while_threading_keep_the_record(app):
    """Only a dead parent means the record is stale. A transient failure
    (ratelimited, outage) must not delete the identity — tomorrow's nudge
    should still thread onto the same post."""
    from slack_sdk.errors import SlackApiError

    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.side_effect = SlackApiError(
        "boom", response={"error": "ratelimited"}
    )

    with app.app_context():
        assert not _digest_records(THREADED_BLOCK_START), (
            "reserved 2099 block anchor already occupied in the dev database"
        )
        record = PracticeSummaryPost(
            week_start=THREADED_BLOCK_START,
            surface=READINESS_DIGEST,
            channel_id="C-TEST-DIGEST",
            message_ts="1785000000.42",
        )
        db.session.add(record)
        db.session.commit()
        try:
            with patch(
                "app.slack.practices.drafts.get_slack_client", return_value=client
            ):
                result = post_readiness_digest(
                    [_practice(4)], "Jul 21", "Aug 13",
                    block_start=THREADED_BLOCK_START,
                )

            assert result["success"] is False
            assert result["error"] == "ratelimited"
            client.chat_postMessage.assert_called_once(), "no retry on transient errors"

            records = _digest_records(THREADED_BLOCK_START)
            assert len(records) == 1
            assert records[0].message_ts == "1785000000.42", (
                "a transient error must not destroy the digest identity"
            )
        finally:
            db.session.rollback()
            _delete_digest_records(THREADED_BLOCK_START)


def test_recording_failure_still_reports_a_successful_post(app):
    """The message went out; a bookkeeping failure must not turn that into an
    error (or raise) — tomorrow's nudge just falls back to top-level again."""
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.return_value = {"ok": True, "ts": "1785000003.1"}

    with app.app_context():
        try:
            with patch(
                "app.slack.practices.drafts.get_slack_client", return_value=client
            ), patch(
                "app.slack.practices.drafts.stage_readiness_digest_post",
                side_effect=RuntimeError("TEST boom"),
            ):
                result = post_readiness_digest(
                    [_practice(4)], "Jul 21", "Aug 13",
                    block_start=FALLBACK_BLOCK_START,
                )

            assert result["success"] is True
            assert not _digest_records(FALLBACK_BLOCK_START)
        finally:
            db.session.rollback()
            _delete_digest_records(FALLBACK_BLOCK_START)


def test_empty_practice_list_posts_nothing(app):
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([], "Jul 21", "Aug 13")

    assert result["success"] is False
    client.chat_postMessage.assert_not_called()
