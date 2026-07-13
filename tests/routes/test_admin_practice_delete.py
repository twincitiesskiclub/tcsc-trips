"""Admin practice deletion and cancellation Slack safety gates."""

from contextlib import nullcontext
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.models import db
from app.practices.interfaces import CancellationStatus, PracticeStatus
from app.practices.models import CancellationRequest, Practice
import app.slack.bolt_app as bolt_module


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

    response = admin_client.post(f'/admin/practices/{practice_id}/delete')

    assert response.status_code == 200
    assert response.get_json()['success'] is True
    assert practice_exists(app, practice_id) is False


@pytest.mark.parametrize(
    ('details_ts', 'error'),
    [
        (None, 'root failed'),
        ('details.1', 'Combined Details did not sync; root was not changed'),
    ],
)
def test_announcement_failure_keeps_row_and_original_retry_timestamps(
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
    ):
        response = admin_client.post(
            f'/admin/practices/{practice_id}/delete'
        )

    assert response.status_code == 502
    assert response.get_json()['error'] == (
        'Slack announcement could not be updated; practice was not deleted'
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

    response = admin_client.post(f'/admin/practices/{practice_id}/delete')

    assert response.status_code == 502
    assert practice_exists(app, practice_id) is True


def test_had_root_is_captured_before_refresh_clears_timestamp(
    app, admin_client, practice_factory
):
    practice_id = practice_factory(
        slack_message_ts='root.1', slack_channel_id='C-ONE'
    )

    def unexplained_skip(practice, **_kwargs):
        practice.slack_message_ts = None
        return {'announcement': {'skipped': 'absent'}}

    with patch(
        'app.slack.practices.refresh_practice_posts',
        side_effect=unexplained_skip,
    ):
        response = admin_client.post(
            f'/admin/practices/{practice_id}/delete'
        )

    assert response.status_code == 502
    assert practice_exists(app, practice_id) is True


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
    ):
        response = admin_client.post(
            f'/admin/practices/{practice_id}/delete'
        )

    assert response.status_code == 200
    assert practice_exists(app, practice_id) is False


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
