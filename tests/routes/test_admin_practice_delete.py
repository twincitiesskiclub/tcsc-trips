"""Admin practice deletion and cancellation Slack safety gates."""

from datetime import datetime
from unittest.mock import patch

import pytest

from app import create_app
from app.models import db
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice


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
        for practice_id in ids:
            practice = db.session.get(Practice, practice_id)
            if practice is not None:
                db.session.delete(practice)
        db.session.commit()


def practice_exists(app, practice_id):
    with app.app_context():
        return db.session.get(Practice, practice_id) is not None


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
