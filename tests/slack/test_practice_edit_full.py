import logging
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app import create_app
from app.models import db
from app.practices.interfaces import PracticeInfo, PracticeStatus
from app.practices.models import (
    Practice,
    PracticeActivity,
    PracticeLocation,
    PracticeType,
)
import app.slack.bolt_app as bolt_module
from app.slack.modals import build_practice_edit_full_modal


TEST_PREFIX = "Slack Full Edit Test"


class AckRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


def _blocks_by_id(modal):
    return {
        block["block_id"]: block
        for block in modal["blocks"]
        if "block_id" in block
    }


def _full_edit_values(
    *,
    workout="5 x 4 minutes",
    notes="Meet by the flagpole",
    plan_text=":athletic_shoe: Saved custom option",
    location_id=None,
    activity_ids=None,
    type_ids=None,
    is_dark=False,
):
    values = {
        "workout_block": {"workout_description": {"value": workout}},
        "notes_block": {"logistics_notes": {"value": notes}},
        "plan_reactions_block": {"plan_reactions": {"value": plan_text}},
        "flags_block": {
            "practice_flags": {
                "selected_options": (
                    [{"value": "is_dark_practice"}] if is_dark else []
                )
            }
        },
    }
    if location_id is not None:
        values["location_block"] = {
            "location_id": {"selected_option": {"value": str(location_id)}}
        }
    if activity_ids is not None:
        values["activities_block"] = {
            "activity_ids": {
                "selected_options": [
                    {"value": str(activity_id)} for activity_id in activity_ids
                ]
            }
        }
    if type_ids is not None:
        values["types_block"] = {
            "type_ids": {
                "selected_options": [
                    {"value": str(type_id)} for type_id in type_ids
                ]
            }
        }
    return values


def _submit(practice, values, ack):
    return bolt_module._handle_practice_edit_full_submission(
        ack=ack,
        body={"user": {"id": "U-FULL-EDIT-TEST"}},
        view={
            "private_metadata": str(practice.id),
            "state": {"values": values},
        },
        logger=logging.getLogger(__name__),
    )


def _cleanup_test_records():
    for practice in Practice.query.filter(
        Practice.airtable_id.like(f"{TEST_PREFIX}%")
    ).all():
        db.session.delete(practice)
    db.session.flush()
    for model in (PracticeActivity, PracticeType, PracticeLocation):
        for record in model.query.filter(model.name.startswith(TEST_PREFIX)).all():
            db.session.delete(record)
    db.session.commit()


@pytest.fixture
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return flask_app


@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        _cleanup_test_records()
        yield db
        db.session.rollback()
        _cleanup_test_records()


@pytest.fixture
def source_records(db_session):
    current_location = PracticeLocation(name=f"{TEST_PREFIX} Current Location")
    replacement_location = PracticeLocation(
        name=f"{TEST_PREFIX} Replacement Location"
    )
    current_activity = PracticeActivity(
        name=f"{TEST_PREFIX} Current Activity",
        default_plan_reactions=[
            {"emoji": "evergreen_tree", "label": "Current activity default"}
        ],
    )
    replacement_activity = PracticeActivity(
        name=f"{TEST_PREFIX} Replacement Activity",
        default_plan_reactions=[
            {"emoji": "snowflake", "label": "Replacement activity default"}
        ],
    )
    current_type = PracticeType(
        name=f"{TEST_PREFIX} Current Type",
        default_plan_reactions=[
            {"emoji": "cyclist", "label": "Current type default"}
        ],
    )
    replacement_type = PracticeType(
        name=f"{TEST_PREFIX} Replacement Type",
        default_plan_reactions=[
            {"emoji": "mountain", "label": "Replacement type default"}
        ],
    )
    records = {
        "current_location": current_location,
        "replacement_location": replacement_location,
        "current_activity": current_activity,
        "replacement_activity": replacement_activity,
        "current_type": current_type,
        "replacement_type": replacement_type,
    }
    db.session.add_all(records.values())
    db.session.commit()
    return records


@pytest.fixture
def practice_record(db_session, source_records):
    practice = Practice(
        date=datetime(2026, 7, 14, 18, 15),
        day_of_week="Tuesday",
        status="scheduled",
        location_id=source_records["current_location"].id,
        workout_description="Original workout",
        logistics_notes="Original notes",
        plan_reactions=[
            {"emoji": "athletic_shoe", "label": "Saved custom option"}
        ],
        airtable_id=f"{TEST_PREFIX} Practice",
    )
    practice.activities = [source_records["current_activity"]]
    practice.practice_types = [source_records["current_type"]]
    db.session.add(practice)
    db.session.commit()
    return practice


@pytest.fixture
def refresh_calls(monkeypatch):
    calls = []

    def record_refresh(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts", record_refresh
    )
    return calls


def _practice_info():
    return PracticeInfo(
        id=42,
        date=datetime(2026, 7, 14, 18, 15),
        day_of_week="Tuesday",
        status=PracticeStatus.SCHEDULED,
        workout_description="5 x 4 minutes",
        logistics_notes="Meet by the flagpole",
        plan_reactions=[
            {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}
        ],
    )


def test_full_edit_modal_limits_all_authoring_fields():
    blocks = _blocks_by_id(build_practice_edit_full_modal(_practice_info()))

    assert blocks["workout_block"]["element"]["max_length"] == 2500
    assert blocks["notes_block"]["element"]["max_length"] == 2500
    assert blocks["plan_reactions_block"]["element"]["max_length"] == 1000


def test_full_edit_modal_prefills_saved_notes_and_plan_snapshot():
    blocks = _blocks_by_id(build_practice_edit_full_modal(_practice_info()))

    assert blocks["notes_block"]["element"]["initial_value"] == (
        "Meet by the flagpole"
    )
    assert blocks["plan_reactions_block"]["element"]["initial_value"] == (
        ":evergreen_tree: Endurance instead of intervals"
    )


def test_full_edit_modal_wraps_skin_tone_name_once():
    practice = _practice_info()
    practice.plan_reactions = [{
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    }]
    field = _blocks_by_id(
        build_practice_edit_full_modal(practice)
    )["plan_reactions_block"]
    assert field["element"]["initial_value"] == (
        ":older_adult::skin-tone-4: experienced rollerskier"
    )


@pytest.mark.parametrize(
    ("plan_text", "expected"),
    [
        (
            ":snowflake: Choose the shorter route",
            [{"emoji": "snowflake", "label": "Choose the shorter route"}],
        ),
        ("", []),
    ],
)
def test_full_edit_submission_persists_plan_edit_or_explicit_clear(
    db_session, practice_record, refresh_calls, plan_text, expected
):
    ack = AckRecorder()

    _submit(
        practice_record,
        _full_edit_values(plan_text=plan_text),
        ack,
    )

    db.session.refresh(practice_record)
    assert ack.calls == [{}]
    assert practice_record.plan_reactions == expected
    assert len(refresh_calls) == 1


@pytest.mark.parametrize(
    ("notes", "expected"),
    [("Updated trail conditions", "Updated trail conditions"), ("", None)],
)
def test_full_edit_submission_updates_or_clears_notes(
    db_session, practice_record, refresh_calls, notes, expected
):
    ack = AckRecorder()

    _submit(practice_record, _full_edit_values(notes=notes), ack)

    db.session.refresh(practice_record)
    assert ack.calls == [{}]
    assert practice_record.logistics_notes == expected
    assert len(refresh_calls) == 1


@pytest.mark.parametrize(
    ("overrides", "expected_errors"),
    [
        (
            {"workout": "x" * 2501},
            {"workout_block": "Workout must be 2,500 characters or fewer"},
        ),
        (
            {"notes": "x" * 2501},
            {"notes_block": "Notes / Logistics must be 2,500 characters or fewer"},
        ),
        (
            {"plan_text": ":evergreen_tree Missing closing colon"},
            {
                "plan_reactions_block": (
                    "Line 1: use :emoji: Member-facing label"
                )
            },
        ),
    ],
)
def test_full_edit_invalid_authoring_returns_field_errors_without_side_effects(
    db_session,
    practice_record,
    source_records,
    refresh_calls,
    overrides,
    expected_errors,
):
    ack = AckRecorder()
    values = _full_edit_values(
        location_id=source_records["replacement_location"].id,
        activity_ids=[source_records["replacement_activity"].id],
        type_ids=[source_records["replacement_type"].id],
        is_dark=True,
        **overrides,
    )

    _submit(practice_record, values, ack)

    db.session.refresh(practice_record)
    assert ack.calls == [
        {"response_action": "errors", "errors": expected_errors}
    ]
    assert practice_record.location_id == source_records["current_location"].id
    assert practice_record.workout_description == "Original workout"
    assert practice_record.logistics_notes == "Original notes"
    assert practice_record.plan_reactions == [
        {"emoji": "athletic_shoe", "label": "Saved custom option"}
    ]
    assert practice_record.is_dark_practice is False
    assert {item.id for item in practice_record.activities} == {
        source_records["current_activity"].id
    }
    assert {item.id for item in practice_record.practice_types} == {
        source_records["current_type"].id
    }
    assert refresh_calls == []


def test_full_edit_source_changes_preserve_submitted_plan_snapshot(
    db_session, practice_record, source_records, refresh_calls
):
    ack = AckRecorder()
    original_snapshot = list(practice_record.plan_reactions)

    _submit(
        practice_record,
        _full_edit_values(
            activity_ids=[source_records["replacement_activity"].id],
            type_ids=[source_records["replacement_type"].id],
        ),
        ack,
    )

    db.session.refresh(practice_record)
    assert ack.calls == [{}]
    assert practice_record.plan_reactions == original_snapshot
    assert {item.id for item in practice_record.activities} == {
        source_records["replacement_activity"].id
    }
    assert {item.id for item in practice_record.practice_types} == {
        source_records["replacement_type"].id
    }
    assert len(refresh_calls) == 1


def test_posted_full_edit_returns_saved_but_unsynced_result_and_dms_user(
    db_session, practice_record, monkeypatch
):
    practice_record.slack_channel_id = "C-POSTED"
    practice_record.slack_message_ts = "root.1"
    db.session.commit()
    refresh_result = {
        "announcement": {"success": False, "error": "Slack failed"},
    }
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *_args, **_kwargs: refresh_result,
    )
    ack = AckRecorder()
    client = MagicMock()

    result = bolt_module._handle_practice_edit_full_submission(
        ack=ack,
        body={"user": {"id": "U-FULL-EDIT-TEST"}},
        view={
            "private_metadata": str(practice_record.id),
            "state": {"values": _full_edit_values(workout="Saved workout")},
        },
        client=client,
        logger=logging.getLogger(__name__),
    )

    db.session.refresh(practice_record)
    assert ack.calls == [{}]
    assert practice_record.workout_description == "Saved workout"
    assert result == {
        "success": False,
        "practice_updated": True,
        "error": (
            "Practice changes were saved, but the Slack announcement was not "
            "updated. Retry the edit or refresh the announcement."
        ),
        "refresh_results": refresh_result,
    }
    client.chat_postMessage.assert_called_once_with(
        channel="U-FULL-EDIT-TEST",
        text=(
            ":warning: Your practice changes were saved, but the Slack "
            "announcement was not updated. Retry the edit or refresh the "
            "announcement."
        ),
    )


def test_full_edit_dm_failure_does_not_undo_saved_database_edit(
    db_session, practice_record, monkeypatch, caplog
):
    practice_record.slack_channel_id = "C-POSTED"
    practice_record.slack_message_ts = "root.1"
    db.session.commit()
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *_args, **_kwargs: {
            "announcement": {"success": False, "error": "Slack failed"},
        },
    )
    client = MagicMock()
    client.chat_postMessage.side_effect = RuntimeError("DM failed")

    with caplog.at_level(logging.WARNING):
        result = bolt_module._handle_practice_edit_full_submission(
            ack=AckRecorder(),
            body={"user": {"id": "U-FULL-EDIT-TEST"}},
            view={
                "private_metadata": str(practice_record.id),
                "state": {
                    "values": _full_edit_values(workout="Still saved")
                },
            },
            client=client,
            logger=logging.getLogger(__name__),
        )

    db.session.refresh(practice_record)
    assert result["practice_updated"] is True
    assert result["success"] is False
    assert practice_record.workout_description == "Still saved"
    assert "Could not DM saved-but-unsynced practice edit" in caplog.text


def test_unposted_full_edit_returns_structured_success_without_dm(
    db_session, practice_record, monkeypatch
):
    refresh_result = {
        "announcement": {"success": False, "error": "No root"},
    }
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *_args, **_kwargs: refresh_result,
    )
    client = MagicMock()

    result = bolt_module._handle_practice_edit_full_submission(
        ack=AckRecorder(),
        body={"user": {"id": "U-FULL-EDIT-TEST"}},
        view={
            "private_metadata": str(practice_record.id),
            "state": {"values": _full_edit_values()},
        },
        client=client,
        logger=logging.getLogger(__name__),
    )

    assert result == {
        "success": True,
        "practice_updated": True,
        "refresh_results": refresh_result,
    }
    client.chat_postMessage.assert_not_called()
