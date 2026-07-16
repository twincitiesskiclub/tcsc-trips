"""Admin practice deletion and cancellation Slack safety gates."""

import logging
from contextlib import nullcontext
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.models import db
from app.practices.interfaces import CancellationStatus, PracticeStatus
from app.practices.models import CancellationRequest, Practice
import app.slack.bolt_app as bolt_module


ORIGINAL_WEEK_START = date(2026, 7, 13)
RESTORED_RECOVERY = {
    'success': True,
    'outcome': 'restored',
    'practice_deleted': False,
    'practice_restored': True,
}
INCOMPLETE_RECOVERY = {
    'success': False,
    'outcome': 'incomplete',
    'practice_deleted': False,
    'practice_restored': False,
    'recovery_incomplete': True,
}
RESTORED_RESPONSE = {
    'success': False,
    'practice_deleted': False,
    'practice_restored': True,
    'error': (
        'Practice was not deleted. Its Slack posts were restored; '
        'review and retry the delete.'
    ),
}
INCOMPLETE_RESPONSE = {
    'success': False,
    'practice_deleted': False,
    'practice_restored': False,
    'recovery_incomplete': True,
    'error': (
        'Practice was not deleted, and Slack recovery is incomplete. '
        'Manual reconciliation is required.'
    ),
}


@pytest.fixture
def app():
    application = create_app()
    application.config.update(
        TESTING=True,
        SECRET_KEY='test-secret-key',
        SQLALCHEMY_DATABASE_URI=(
            'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips'
        ),
    )
    return application


@pytest.fixture
def admin_client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session['user'] = {
            'email': 'tester@twincitiesskiclub.org',
            'name': 'Tester',
        }
    return client


@pytest.fixture
def practice_factory(app):
    ids = []

    def create(**values):
        with app.app_context():
            practice = Practice(
                date=datetime(2026, 7, 14, 18, 15),
                day_of_week='Tuesday',
                status=PracticeStatus.SCHEDULED.value,
                **values,
            )
            db.session.add(practice)
            db.session.commit()
            ids.append(practice.id)
            return practice.id

    yield create

    with app.app_context():
        db.session.rollback()
        CancellationRequest.query.filter(
            CancellationRequest.practice_id.in_(ids)
        ).delete(synchronize_session=False)
        for practice_id in ids:
            practice = db.session.get(Practice, practice_id)
            if practice is not None:
                db.session.delete(practice)
        db.session.commit()


def practice_exists(app, practice_id):
    with app.app_context():
        return db.session.get(Practice, practice_id) is not None


def rollback_then(result):
    def recover(*_args, **_kwargs):
        db.session.rollback()
        return result

    return recover


def assert_recovery_log(
    caplog,
    *,
    practice_id,
    cause,
    outcome,
    level,
):
    records = [record for record in caplog.records if record.levelno == level]
    message = '\n'.join(record.getMessage() for record in records)
    assert str(practice_id) in message
    assert 'C-ONE' in message
    assert 'root.1' in message
    assert '2026-07-13' in message
    assert cause in message
    assert outcome in message


def cancellation_proposal(app, practice_factory, *, posted=True):
    practice_id = practice_factory(
        slack_channel_id='C-POSTED' if posted else None,
        slack_message_ts='root.1' if posted else None,
    )
    with app.app_context():
        proposal = CancellationRequest(
            practice_id=practice_id,
            reason_type='weather',
            reason_summary='Unsafe heat',
        )
        db.session.add(proposal)
        db.session.commit()
        return practice_id, proposal.id


def test_unposted_practice_remains_deletable(
    app, admin_client, practice_factory
):
    practice_id = practice_factory()

    with patch(
        'app.slack.practices.recover_failed_practice_delete'
    ) as recover_delete:
        response = admin_client.post(f'/admin/practices/{practice_id}/delete')

    assert response.status_code == 200
    assert response.get_json() == {
        'success': True,
        'message': 'Practice deleted successfully',
    }
    assert practice_exists(app, practice_id) is False
    recover_delete.assert_not_called()


@pytest.mark.parametrize(
    ('details_ts', 'error'),
    [
        (None, 'root failed'),
        ('details.1', 'Combined Details did not sync; root was not changed'),
    ],
)
def test_partial_slack_cleanup_restores_post_and_keeps_database_row(
    app, admin_client, practice_factory, details_ts, error,
):
    practice_id = practice_factory(
        slack_message_ts='root.1',
        slack_details_ts=details_ts,
        slack_channel_id='C-ONE',
    )
    with patch(
        'app.slack.practices.refresh_practice_posts',
        return_value={
            'announcement': {'success': False, 'error': error},
        },
    ), patch(
        'app.slack.practices.recover_failed_practice_delete',
        side_effect=rollback_then(RESTORED_RECOVERY),
    ) as recover_delete:
        response = admin_client.post(
            f'/admin/practices/{practice_id}/delete'
        )

    assert response.status_code == 502
    assert response.get_json() == RESTORED_RESPONSE
    recover_delete.assert_called_once_with(
        practice_id,
        original_channel_id='C-ONE',
        original_message_ts='root.1',
        original_week_start=ORIGINAL_WEEK_START,
    )
    with app.app_context():
        practice = db.session.get(Practice, practice_id)
        assert practice.slack_message_ts == 'root.1'
        assert practice.slack_details_ts == details_ts
        assert practice.slack_channel_id == 'C-ONE'


def test_missing_channel_for_posted_root_keeps_database_row(
    app, admin_client, practice_factory
):
    practice_id = practice_factory(slack_message_ts='root.1')

    with patch(
        'app.slack.practices.refresh_practice_posts',
        return_value={
            'announcement': {
                'success': False,
                'error': 'Original Slack channel is missing',
            },
        },
    ), patch(
        'app.slack.practices.recover_failed_practice_delete',
        side_effect=rollback_then(INCOMPLETE_RECOVERY),
    ) as recover_delete:
        response = admin_client.post(f'/admin/practices/{practice_id}/delete')

    assert response.status_code == 502
    assert response.get_json() == INCOMPLETE_RESPONSE
    assert practice_exists(app, practice_id) is True
    recover_delete.assert_called_once_with(
        practice_id,
        original_channel_id=None,
        original_message_ts='root.1',
        original_week_start=ORIGINAL_WEEK_START,
    )


def test_partial_slack_cleanup_uses_immutable_original_snapshot(
    app, admin_client, practice_factory
):
    practice_id = practice_factory(
        slack_message_ts='root.1', slack_channel_id='C-ONE'
    )

    def partial_cleanup(practice, **_kwargs):
        practice.slack_channel_id = 'C-MUTATED'
        practice.slack_message_ts = None
        practice.date = datetime(2026, 7, 21, 18, 15)
        return {
            'announcement': {
                'success': False,
                'error': 'root cleanup was partial',
            },
        }

    with patch(
        'app.slack.practices.refresh_practice_posts',
        side_effect=partial_cleanup,
    ), patch(
        'app.slack.practices.recover_failed_practice_delete',
        side_effect=rollback_then(RESTORED_RECOVERY),
    ) as recover_delete:
        response = admin_client.post(
            f'/admin/practices/{practice_id}/delete'
        )

    assert response.status_code == 502
    assert response.get_json() == RESTORED_RESPONSE
    assert practice_exists(app, practice_id) is True
    recover_delete.assert_called_once_with(
        practice_id,
        original_channel_id='C-ONE',
        original_message_ts='root.1',
        original_week_start=ORIGINAL_WEEK_START,
    )


@pytest.mark.parametrize('shared_root', [False, True], ids=['standalone', 'shared'])
def test_failed_final_database_delete_restores_original_slack_root(
    app,
    admin_client,
    practice_factory,
    shared_root,
    caplog,
):
    practice_id = practice_factory(
        slack_channel_id='C-ONE',
        slack_message_ts='root.1',
        slack_session_emoji='six' if shared_root else None,
    )
    if shared_root:
        practice_factory(
            slack_channel_id='C-ONE',
            slack_message_ts='root.1',
            slack_session_emoji='seven',
        )

    with caplog.at_level(logging.WARNING), patch(
        'app.slack.practices.refresh_practice_posts',
        return_value={'announcement': {'success': True}},
    ), patch(
        'app.slack.practices.recover_failed_practice_delete',
        side_effect=rollback_then(RESTORED_RECOVERY),
    ) as recover_delete, patch.object(
        db.session,
        'commit',
        side_effect=RuntimeError('database commit failed'),
    ):
        response = admin_client.post(f'/admin/practices/{practice_id}/delete')

    assert response.status_code == 500
    assert response.get_json() == RESTORED_RESPONSE
    assert 'database commit failed' not in response.get_data(as_text=True)
    assert practice_exists(app, practice_id) is True
    recover_delete.assert_called_once_with(
        practice_id,
        original_channel_id='C-ONE',
        original_message_ts='root.1',
        original_week_start=ORIGINAL_WEEK_START,
    )
    assert_recovery_log(
        caplog,
        practice_id=practice_id,
        cause='database commit failed',
        outcome='restored',
        level=logging.WARNING,
    )


def test_failed_final_database_delete_recovers_cleanup_exception_once(
    app,
    admin_client,
    practice_factory,
):
    practice_id = practice_factory(
        slack_channel_id='C-ONE',
        slack_message_ts='root.1',
    )
    with patch(
        'app.slack.practices.refresh_practice_posts',
        side_effect=RuntimeError('Slack cleanup transport failed'),
    ), patch(
        'app.slack.practices.recover_failed_practice_delete',
        side_effect=rollback_then(RESTORED_RECOVERY),
    ) as recover_delete:
        response = admin_client.post(f'/admin/practices/{practice_id}/delete')

    assert response.status_code == 500
    assert response.get_json() == RESTORED_RESPONSE
    recover_delete.assert_called_once_with(
        practice_id,
        original_channel_id='C-ONE',
        original_message_ts='root.1',
        original_week_start=ORIGINAL_WEEK_START,
    )


def test_commit_exception_with_missing_row_reports_delete_committed(
    app,
    admin_client,
    practice_factory,
    caplog,
):
    practice_id = practice_factory(
        slack_channel_id='C-ONE',
        slack_message_ts='root.1',
    )
    real_commit = db.session.commit

    def commit_then_raise():
        real_commit()
        raise RuntimeError('database acknowledgement was lost')

    deleted_recovery = {
        'success': True,
        'outcome': 'deleted',
        'practice_deleted': True,
    }
    with caplog.at_level(logging.WARNING), patch(
        'app.slack.practices.refresh_practice_posts',
        return_value={'announcement': {'success': True}},
    ), patch(
        'app.slack.practices.recover_failed_practice_delete',
        return_value=deleted_recovery,
    ) as recover_delete, patch.object(
        db.session,
        'commit',
        side_effect=commit_then_raise,
    ):
        response = admin_client.post(f'/admin/practices/{practice_id}/delete')

    assert response.status_code == 200
    assert response.get_json() == {
        'success': True,
        'practice_deleted': True,
        'message': 'Practice deleted successfully',
    }
    assert practice_exists(app, practice_id) is False
    recover_delete.assert_called_once_with(
        practice_id,
        original_channel_id='C-ONE',
        original_message_ts='root.1',
        original_week_start=ORIGINAL_WEEK_START,
    )
    assert_recovery_log(
        caplog,
        practice_id=practice_id,
        cause='database acknowledgement was lost',
        outcome='deleted',
        level=logging.WARNING,
    )


@pytest.mark.parametrize(
    ('failure_kind', 'expected_status'),
    [('unsafe-result', 502), ('commit-exception', 500)],
)
def test_incomplete_delete_recovery_requires_manual_reconciliation(
    app,
    admin_client,
    practice_factory,
    failure_kind,
    expected_status,
    caplog,
):
    practice_id = practice_factory(
        slack_channel_id='C-ONE',
        slack_message_ts='root.1',
    )
    if failure_kind == 'unsafe-result':
        announcement = {
            'success': False,
            'error': 'root cleanup failed after deleting Details',
        }
        commit_failure = nullcontext()
        cause = 'root cleanup failed after deleting Details'
    else:
        announcement = {'success': True}
        commit_failure = patch.object(
            db.session,
            'commit',
            side_effect=RuntimeError('database commit failed'),
        )
        cause = 'database commit failed'

    with caplog.at_level(logging.CRITICAL), patch(
        'app.slack.practices.refresh_practice_posts',
        return_value={'announcement': announcement},
    ), patch(
        'app.slack.practices.recover_failed_practice_delete',
        side_effect=rollback_then(INCOMPLETE_RECOVERY),
    ) as recover_delete, commit_failure:
        response = admin_client.post(f'/admin/practices/{practice_id}/delete')

    assert response.status_code == expected_status
    assert response.get_json() == INCOMPLETE_RESPONSE
    assert cause not in response.get_data(as_text=True)
    assert practice_exists(app, practice_id) is True
    recover_delete.assert_called_once_with(
        practice_id,
        original_channel_id='C-ONE',
        original_message_ts='root.1',
        original_week_start=ORIGINAL_WEEK_START,
    )
    assert_recovery_log(
        caplog,
        practice_id=practice_id,
        cause=cause,
        outcome='incomplete',
        level=logging.CRITICAL,
    )


def test_incomplete_delete_recovery_when_recovery_raises_is_one_shot(
    app,
    admin_client,
    practice_factory,
):
    practice_id = practice_factory(
        slack_channel_id='C-ONE',
        slack_message_ts='root.1',
    )
    with patch(
        'app.slack.practices.refresh_practice_posts',
        return_value={
            'announcement': {
                'success': False,
                'error': 'partial Slack cleanup',
            },
        },
    ), patch(
        'app.slack.practices.recover_failed_practice_delete',
        side_effect=RuntimeError('recovery implementation failed'),
    ) as recover_delete:
        response = admin_client.post(f'/admin/practices/{practice_id}/delete')

    assert response.status_code == 502
    assert response.get_json() == INCOMPLETE_RESPONSE
    assert 'recovery implementation failed' not in response.get_data(
        as_text=True
    )
    assert practice_exists(app, practice_id) is True
    recover_delete.assert_called_once_with(
        practice_id,
        original_channel_id='C-ONE',
        original_message_ts='root.1',
        original_week_start=ORIGINAL_WEEK_START,
    )


def test_incomplete_delete_recovery_for_invalid_result_is_one_shot(
    app,
    admin_client,
    practice_factory,
):
    practice_id = practice_factory(
        slack_channel_id='C-ONE',
        slack_message_ts='root.1',
    )
    with patch(
        'app.slack.practices.refresh_practice_posts',
        return_value={
            'announcement': {
                'success': False,
                'error': 'partial Slack cleanup',
            },
        },
    ), patch(
        'app.slack.practices.recover_failed_practice_delete',
        side_effect=[None, INCOMPLETE_RECOVERY],
    ) as recover_delete:
        response = admin_client.post(f'/admin/practices/{practice_id}/delete')

    assert response.status_code == 502
    assert response.get_json() == INCOMPLETE_RESPONSE
    assert practice_exists(app, practice_id) is True
    recover_delete.assert_called_once_with(
        practice_id,
        original_channel_id='C-ONE',
        original_message_ts='root.1',
        original_week_start=ORIGINAL_WEEK_START,
    )


def test_later_summary_failure_does_not_block_delete_after_root_success(
    app, admin_client, practice_factory
):
    practice_id = practice_factory(
        slack_message_ts='root.1', slack_channel_id='C-ONE'
    )
    with patch(
        'app.slack.practices.refresh_practice_posts',
        return_value={
            'announcement': {'success': True},
            'coach_summary': {'success': False, 'error': 'coach failed'},
            'weekly_summary': {'success': False, 'error': 'weekly failed'},
        },
    ), patch(
        'app.slack.practices.recover_failed_practice_delete'
    ) as recover_delete:
        response = admin_client.post(
            f'/admin/practices/{practice_id}/delete'
        )

    assert response.status_code == 200
    assert response.get_json() == {
        'success': True,
        'message': 'Practice deleted successfully',
    }
    assert practice_exists(app, practice_id) is False
    recover_delete.assert_not_called()


def test_cancel_refresh_failure_is_saved_but_unsynced(
    app, admin_client, practice_factory
):
    practice_id = practice_factory(
        slack_message_ts='root.1', slack_channel_id='C-ONE'
    )
    with patch(
        'app.slack.practices.refresh_practice_posts',
        return_value={
            'announcement': {'success': False, 'error': 'root failed'},
        },
    ):
        response = admin_client.post(
            f'/admin/practices/{practice_id}/cancel',
            json={'reason': 'Facility closed'},
        )

    assert response.status_code == 502
    assert response.get_json() == {
        'success': False,
        'practice_cancelled': True,
        'error': (
            'Practice was cancelled, but its Slack announcement did not update'
        ),
    }
    with app.app_context():
        practice = db.session.get(Practice, practice_id)
        assert practice.status == PracticeStatus.CANCELLED.value
        assert practice.cancellation_reason == 'Facility closed'


def test_unposted_practice_cancellation_does_not_claim_unsynced(
    app, admin_client, practice_factory
):
    practice_id = practice_factory()

    response = admin_client.post(
        f'/admin/practices/{practice_id}/cancel', json={}
    )

    assert response.status_code == 200
    with app.app_context():
        practice = db.session.get(Practice, practice_id)
        assert practice.status == PracticeStatus.CANCELLED.value
        assert practice.cancellation_reason == 'Cancelled by admin'


def test_slack_approval_reports_saved_but_unsynced_cancellation(
    app, practice_factory
):
    practice_id, proposal_id = cancellation_proposal(app, practice_factory)
    refresh_results = {
        'announcement': {'success': False, 'error': 'Slack failed'},
    }
    with app.app_context(), patch(
        'app.slack.practices.refresh_practice_posts',
        return_value=refresh_results,
    ):
        result = bolt_module._process_cancellation_decision(
            proposal_id, True, 'U-COORDINATOR', 'Coordinator'
        )
        practice = db.session.get(Practice, practice_id)
        proposal = db.session.get(CancellationRequest, proposal_id)
        assert practice.status == PracticeStatus.CANCELLED.value
        assert practice.cancellation_reason == 'Unsafe heat'
        assert proposal.status == CancellationStatus.APPROVED.value

    assert result == {
        'success': False,
        'practice_cancelled': True,
        'error': (
            'Practice was cancelled, but its Slack announcement did not update'
        ),
        'refresh_results': refresh_results,
    }


def test_slack_unposted_approval_succeeds_and_rejection_skips_refresh(
    app, practice_factory
):
    _practice_id, proposal_id = cancellation_proposal(
        app, practice_factory, posted=False
    )
    with app.app_context(), patch(
        'app.slack.practices.refresh_practice_posts',
        return_value={'announcement': {'success': False}},
    ):
        approved = bolt_module._process_cancellation_decision(
            proposal_id, True, 'U-COORDINATOR', 'Coordinator'
        )
    assert approved['success'] is True
    assert approved['practice_cancelled'] is True

    practice_id, proposal_id = cancellation_proposal(app, practice_factory)
    with app.app_context(), patch(
        'app.slack.practices.refresh_practice_posts'
    ) as refresh_posts:
        rejected = bolt_module._process_cancellation_decision(
            proposal_id, False, 'U-COORDINATOR', 'Coordinator'
        )
        assert db.session.get(Practice, practice_id).status == (
            PracticeStatus.SCHEDULED.value
        )
        assert db.session.get(CancellationRequest, proposal_id).status == (
            CancellationStatus.REJECTED.value
        )
    assert rejected == {'success': True, 'practice_cancelled': False}
    refresh_posts.assert_not_called()


@pytest.mark.parametrize(
    ('result', 'approved', 'expected'),
    [
        ({'success': True}, True, 'Decision recorded. Cancellation approved.'),
        (
            {'success': False, 'practice_cancelled': True},
            True,
            ':warning: Cancellation was saved, but the Slack announcement was '
            'not updated. Retry the announcement refresh.',
        ),
        (
            {'success': False, 'error': 'Proposal not found'},
            True,
            'Cancellation proposal not found. No decision was recorded.',
        ),
        (
            {'success': False, 'error': 'Already decided'},
            False,
            'Cancellation proposal was already decided. No new decision was '
            'recorded.',
        ),
    ],
)
def test_cancellation_feedback_distinguishes_result(result, approved, expected):
    assert bolt_module._cancellation_decision_feedback(result, approved) == expected


def test_cancellation_action_delegates_and_posts_feedback():
    result = {'success': False, 'practice_cancelled': True}
    ack, client = MagicMock(), MagicMock()
    with patch.object(
        bolt_module, 'get_app_context', return_value=nullcontext()
    ), patch.object(
        bolt_module, '_process_cancellation_decision', return_value=result
    ) as process:
        returned = bolt_module._handle_cancellation_decision_action(
            ack,
            {
                'user': {'id': 'U-COORDINATOR', 'name': 'Coordinator'},
                'channel': {'id': 'C-CORE'},
            },
            {'action_id': 'cancellation_approve', 'value': '42'},
            client,
        )

    assert returned == result
    ack.assert_called_once_with()
    process.assert_called_once_with(42, True, 'U-COORDINATOR', 'Coordinator')
    assert 'saved, but the Slack announcement was not updated' in (
        client.chat_postEphemeral.call_args.kwargs['text']
    )
