"""One-shot compensation after an ambiguous practice delete commit."""

from contextlib import contextmanager
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.models import db
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice


ORIGINAL_WEEK_START = date(2026, 7, 13)
ORIGINAL_CHANNEL = "C-DELETE-RECOVERY-ORIGINAL"
ORIGINAL_ROOT = "delete-recovery-root.1"
TEST_PREFIX = "test-delete-recovery-task-1-"


def _healthy_summaries():
    return {
        "coach_summary": {"success": True},
        "weekly_summary": {"success": True},
    }


def _cleanup_test_practices():
    rows = Practice.query.filter(
        Practice.airtable_id.like(f"{TEST_PREFIX}%")
    ).all()
    for row in rows:
        db.session.delete(row)
    db.session.commit()


@pytest.fixture
def app():
    application = create_app()
    application.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        SQLALCHEMY_DATABASE_URI=(
            "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
        ),
    )
    return application


@pytest.fixture
def db_context(app):
    with app.app_context():
        db.session.rollback()
        _cleanup_test_practices()
        yield
        db.session.rollback()
        _cleanup_test_practices()


@pytest.fixture
def practice_factory(db_context):
    created = 0

    def create(**values):
        nonlocal created
        created += 1
        defaults = {
            "date": datetime(2026, 7, 14, 18, 15),
            "day_of_week": "Tuesday",
            "status": PracticeStatus.SCHEDULED.value,
            "airtable_id": f"{TEST_PREFIX}{created}",
        }
        defaults.update(values)
        practice = Practice(**defaults)
        db.session.add(practice)
        db.session.commit()
        return practice

    return create


@pytest.fixture
def standalone_practice(practice_factory):
    return practice_factory(
        slack_channel_id=ORIGINAL_CHANNEL,
        slack_message_ts=ORIGINAL_ROOT,
        slack_details_ts="delete-recovery-details.1",
    )


@pytest.fixture
def shared_practices(practice_factory):
    target = practice_factory(
        slack_channel_id=ORIGINAL_CHANNEL,
        slack_message_ts=ORIGINAL_ROOT,
        slack_details_ts="delete-recovery-shared-details.1",
        slack_session_emoji="six",
    )
    sibling = practice_factory(
        date=datetime(2026, 7, 15, 19, 15),
        day_of_week="Wednesday",
        slack_channel_id=ORIGINAL_CHANNEL,
        slack_message_ts=ORIGINAL_ROOT,
        slack_details_ts="delete-recovery-shared-details.1",
        slack_session_emoji="seven",
    )
    return target, sibling


@contextmanager
def recovery_harness():
    from app.slack.practices import delete_recovery as recovery

    update_root = MagicMock(return_value={"success": True})
    post_root = MagicMock(
        return_value={
            "success": True,
            "message_ts": "delete-recovery-reposted.1",
            "channel_id": ORIGINAL_CHANNEL,
        }
    )
    refresh_summaries = MagicMock(return_value=_healthy_summaries())
    with patch.object(
        recovery, "update_practice_slack_post", update_root
    ), patch.object(
        recovery, "post_practice_announcement", post_root
    ), patch.object(
        recovery,
        "refresh_registered_practice_summaries",
        refresh_summaries,
    ):
        yield SimpleNamespace(
            module=recovery,
            update_root=update_root,
            post_root=post_root,
            refresh_summaries=refresh_summaries,
        )


def assert_one_shot(calls):
    assert calls.update_root.call_count <= 1
    assert calls.post_root.call_count <= 1
    assert calls.refresh_summaries.call_count <= 1


def recover(calls, practice_id, **overrides):
    arguments = {
        "original_channel_id": ORIGINAL_CHANNEL,
        "original_message_ts": ORIGINAL_ROOT,
        "original_week_start": ORIGINAL_WEEK_START,
    }
    arguments.update(overrides)
    return calls.module.recover_failed_practice_delete(
        practice_id,
        **arguments,
    )


def test_reload_absent_reports_delete_committed_without_slack_writes():
    session = MagicMock()
    session.get.return_value = None

    with recovery_harness() as calls, patch.object(
        calls.module,
        "db",
        SimpleNamespace(session=session),
    ):
        result = recover(calls, 987654321)

    assert result == {
        "success": True,
        "outcome": "deleted",
        "practice_deleted": True,
    }
    session.rollback.assert_called_once_with()
    session.get.assert_called_once_with(
        Practice, 987654321, populate_existing=True
    )
    calls.update_root.assert_not_called()
    calls.post_root.assert_not_called()
    calls.refresh_summaries.assert_not_called()
    assert_one_shot(calls)


def test_reload_failure_reports_structured_incomplete_without_slack_writes():
    session = MagicMock()
    session.get.side_effect = RuntimeError("database unavailable")

    with recovery_harness() as calls, patch.object(
        calls.module,
        "db",
        SimpleNamespace(session=session),
    ):
        result = recover(calls, 987654321)

    assert result == {
        "success": False,
        "outcome": "incomplete",
        "practice_deleted": False,
        "practice_restored": False,
        "recovery_incomplete": True,
        "announcement": None,
        "summaries": None,
        "error": "Could not reload practice: database unavailable",
    }
    session.rollback.assert_called_once_with()
    session.get.assert_called_once_with(
        Practice, 987654321, populate_existing=True
    )
    calls.update_root.assert_not_called()
    calls.post_root.assert_not_called()
    calls.refresh_summaries.assert_not_called()
    assert_one_shot(calls)


def test_linked_original_root_is_rebuilt_then_summaries_include_row(
    shared_practices,
):
    shared, _sibling = shared_practices

    with recovery_harness() as calls:
        result = recover(calls, shared.id)

    calls.update_root.assert_called_once_with(shared)
    calls.post_root.assert_not_called()
    calls.refresh_summaries.assert_called_once_with(
        ORIGINAL_WEEK_START, exclude_practice_id=None
    )
    assert result == {
        "success": True,
        "outcome": "restored",
        "practice_deleted": False,
        "practice_restored": True,
        "announcement": {"success": True, "action": "rebuilt"},
        "summaries": _healthy_summaries(),
    }
    assert_one_shot(calls)


def test_cleared_standalone_root_is_reposted_once_to_exact_channel(
    standalone_practice,
):
    practice = standalone_practice
    practice.slack_channel_id = None
    practice.slack_message_ts = None
    practice.slack_details_ts = None
    db.session.commit()

    with recovery_harness() as calls:
        result = recover(calls, practice.id)

    calls.update_root.assert_not_called()
    calls.post_root.assert_called_once_with(
        practice,
        channel_id_override=ORIGINAL_CHANNEL,
        create_log_thread=False,
    )
    calls.refresh_summaries.assert_called_once_with(
        ORIGINAL_WEEK_START, exclude_practice_id=None
    )
    assert result["outcome"] == "restored"
    assert result["announcement"]["action"] == "reposted"
    assert_one_shot(calls)


def test_message_not_found_on_standalone_clears_identity_then_reposts_once(
    standalone_practice,
):
    practice = standalone_practice

    with recovery_harness() as calls:
        calls.update_root.return_value = {
            "success": False,
            "error": "message_not_found",
        }
        result = recover(calls, practice.id)

    calls.update_root.assert_called_once_with(practice)
    calls.post_root.assert_called_once_with(
        practice,
        channel_id_override=ORIGINAL_CHANNEL,
        create_log_thread=False,
    )
    calls.refresh_summaries.assert_called_once_with(
        ORIGINAL_WEEK_START, exclude_practice_id=None
    )
    assert (
        practice.slack_channel_id,
        practice.slack_message_ts,
        practice.slack_details_ts,
    ) == (None, None, None)
    assert result["outcome"] == "restored"
    assert result["announcement"]["action"] == "reposted"
    assert_one_shot(calls)


def test_message_not_found_on_shared_identity_never_posts_split_root(
    shared_practices,
):
    shared, _sibling = shared_practices

    with recovery_harness() as calls:
        calls.update_root.return_value = {
            "success": False,
            "error": "message_not_found",
        }
        result = recover(calls, shared.id)

    calls.update_root.assert_called_once_with(shared)
    calls.post_root.assert_not_called()
    calls.refresh_summaries.assert_called_once_with(
        ORIGINAL_WEEK_START, exclude_practice_id=None
    )
    assert (
        shared.slack_channel_id,
        shared.slack_message_ts,
        shared.slack_details_ts,
    ) == (
        ORIGINAL_CHANNEL,
        ORIGINAL_ROOT,
        "delete-recovery-shared-details.1",
    )
    assert result["outcome"] == "incomplete"
    assert result["practice_restored"] is False
    assert_one_shot(calls)


@pytest.mark.parametrize(
    ("root_result", "summary_result", "expected_outcome"),
    [
        (
            {"success": False, "error": "root failed"},
            _healthy_summaries(),
            "incomplete",
        ),
        (
            {"success": True},
            {
                "coach_summary": {"success": False, "error": "coach failed"},
                "weekly_summary": {"success": True},
            },
            "incomplete",
        ),
        (
            {"success": True},
            {
                "coach_summary": {"skipped": "absent"},
                "weekly_summary": {"success": True},
            },
            "restored",
        ),
    ],
    ids=["root-failure", "summary-failure", "absent-summary-is-healthy"],
)
def test_root_and_registered_summary_results_determine_structured_outcome(
    standalone_practice,
    root_result,
    summary_result,
    expected_outcome,
):
    with recovery_harness() as calls:
        calls.update_root.return_value = root_result
        calls.refresh_summaries.return_value = summary_result
        result = recover(calls, standalone_practice.id)

    calls.update_root.assert_called_once_with(standalone_practice)
    calls.post_root.assert_not_called()
    calls.refresh_summaries.assert_called_once_with(
        ORIGINAL_WEEK_START, exclude_practice_id=None
    )
    assert result["outcome"] == expected_outcome
    assert result["success"] is (expected_outcome == "restored")
    assert result["practice_restored"] is (expected_outcome == "restored")
    if expected_outcome == "incomplete":
        assert result["recovery_incomplete"] is True
        assert set(result) == {
            "success",
            "outcome",
            "practice_deleted",
            "practice_restored",
            "recovery_incomplete",
            "announcement",
            "summaries",
            "error",
        }
    assert_one_shot(calls)


def test_root_exception_does_not_prevent_one_summary_repair(
    standalone_practice,
):
    with recovery_harness() as calls:
        calls.update_root.side_effect = RuntimeError("root exploded")
        result = recover(calls, standalone_practice.id)

    calls.update_root.assert_called_once_with(standalone_practice)
    calls.post_root.assert_not_called()
    calls.refresh_summaries.assert_called_once_with(
        ORIGINAL_WEEK_START, exclude_practice_id=None
    )
    assert result["outcome"] == "incomplete"
    assert "root exploded" in result["error"]
    assert_one_shot(calls)


def test_summary_exception_reports_incomplete_after_one_root_repair(
    standalone_practice,
):
    with recovery_harness() as calls:
        calls.refresh_summaries.side_effect = RuntimeError("summary exploded")
        result = recover(calls, standalone_practice.id)

    calls.update_root.assert_called_once_with(standalone_practice)
    calls.post_root.assert_not_called()
    calls.refresh_summaries.assert_called_once_with(
        ORIGINAL_WEEK_START, exclude_practice_id=None
    )
    assert result["outcome"] == "incomplete"
    assert "summary exploded" in result["error"]
    assert_one_shot(calls)


def test_changed_nonempty_identity_is_not_overwritten(standalone_practice):
    practice = standalone_practice
    practice.slack_channel_id = "C-NEW"
    practice.slack_message_ts = "new-root.1"
    db.session.commit()

    with recovery_harness() as calls:
        result = recover(calls, practice.id)

    calls.update_root.assert_not_called()
    calls.post_root.assert_not_called()
    calls.refresh_summaries.assert_called_once_with(
        ORIGINAL_WEEK_START, exclude_practice_id=None
    )
    assert result["outcome"] == "incomplete"
    assert "changed" in result["error"].lower()
    assert_one_shot(calls)


def test_cleared_shared_identity_is_not_split(shared_practices):
    shared, _sibling = shared_practices
    shared.slack_channel_id = None
    shared.slack_message_ts = None
    shared.slack_details_ts = None
    shared.slack_session_emoji = None
    db.session.commit()

    with recovery_harness() as calls:
        result = recover(calls, shared.id)

    calls.update_root.assert_not_called()
    calls.post_root.assert_not_called()
    calls.refresh_summaries.assert_called_once_with(
        ORIGINAL_WEEK_START, exclude_practice_id=None
    )
    assert result["outcome"] == "incomplete"
    assert "shared" in result["error"].lower()
    assert_one_shot(calls)


def test_sibling_lookup_requires_exact_channel_and_root(practice_factory):
    target = practice_factory(
        slack_channel_id=None,
        slack_message_ts=None,
        slack_details_ts=None,
    )
    practice_factory(
        date=datetime(2026, 7, 15, 18, 15),
        day_of_week="Wednesday",
        slack_channel_id="C-DIFFERENT",
        slack_message_ts=ORIGINAL_ROOT,
    )
    practice_factory(
        date=datetime(2026, 7, 16, 18, 15),
        day_of_week="Thursday",
        slack_channel_id=ORIGINAL_CHANNEL,
        slack_message_ts="different-root.1",
    )

    with recovery_harness() as calls:
        result = recover(calls, target.id)

    calls.update_root.assert_not_called()
    calls.post_root.assert_called_once_with(
        target,
        channel_id_override=ORIGINAL_CHANNEL,
        create_log_thread=False,
    )
    assert result["outcome"] == "restored"
    assert_one_shot(calls)


def test_originally_unposted_row_skips_root_but_repairs_summaries(
    standalone_practice,
):
    with recovery_harness() as calls:
        result = recover(
            calls,
            standalone_practice.id,
            original_channel_id=None,
            original_message_ts=None,
        )

    calls.update_root.assert_not_called()
    calls.post_root.assert_not_called()
    calls.refresh_summaries.assert_called_once_with(
        ORIGINAL_WEEK_START, exclude_practice_id=None
    )
    assert result["outcome"] == "restored"
    assert result["announcement"] == {
        "success": True,
        "action": "not_posted",
    }
    assert_one_shot(calls)


def test_missing_original_channel_is_incomplete_but_repairs_summaries(
    standalone_practice,
):
    with recovery_harness() as calls:
        result = recover(
            calls,
            standalone_practice.id,
            original_channel_id=None,
        )

    calls.update_root.assert_not_called()
    calls.post_root.assert_not_called()
    calls.refresh_summaries.assert_called_once_with(
        ORIGINAL_WEEK_START, exclude_practice_id=None
    )
    assert result["outcome"] == "incomplete"
    assert result["announcement"] == {
        "success": False,
        "error": "Original Slack channel is missing",
    }
    assert_one_shot(calls)
