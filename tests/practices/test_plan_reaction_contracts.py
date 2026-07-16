from datetime import datetime
from types import SimpleNamespace

from app.practices.interfaces import PracticeCreate, PracticeUpdate
from app.practices.models import Practice, PracticeActivity, PracticeType
from app.practices.service import (
    convert_activity_to_info,
    convert_practice_to_info,
    convert_type_to_info,
)


def test_activity_and_type_info_include_default_plan_reactions():
    reactions = [{"emoji": "athletic_shoe", "label": "Run"}]
    activity = SimpleNamespace(
        id=1,
        name="Rollerski",
        gear_required=[],
        default_plan_reactions=reactions,
        airtable_id=None,
    )
    practice_type = SimpleNamespace(
        id=2,
        name="Intervals",
        fitness_goals=[],
        has_intervals=True,
        default_plan_reactions=reactions,
        airtable_id=None,
    )
    assert convert_activity_to_info(activity).default_plan_reactions == reactions
    assert convert_type_to_info(practice_type).default_plan_reactions == reactions


def test_practice_info_includes_snapshot_and_session_emoji():
    practice = SimpleNamespace(
        id=3,
        date=datetime(2026, 7, 14, 18, 15),
        day_of_week="Tuesday",
        status="scheduled",
        location=None,
        social_location=None,
        activities=[],
        practice_types=[],
        leads=[],
        warmup_description=None,
        workout_description="Easy distance",
        cooldown_description=None,
        logistics_notes=None,
        slack_details_ts=None,
        has_social=False,
        is_dark_practice=False,
        slack_message_ts="100.200",
        slack_channel_id="CTEST",
        cancellation_reason=None,
        airtable_id=None,
        created_at=None,
        updated_at=None,
        plan_reactions=[{"emoji": "athletic_shoe", "label": "Run"}],
        slack_session_emoji="six",
    )
    info = convert_practice_to_info(practice)
    assert info.plan_reactions == [{"emoji": "athletic_shoe", "label": "Run"}]
    assert info.slack_session_emoji == "six"


def test_models_define_callable_reaction_defaults_and_nullable_session_emoji():
    for model, field_name in (
        (PracticeActivity, "default_plan_reactions"),
        (PracticeType, "default_plan_reactions"),
        (Practice, "plan_reactions"),
    ):
        column = model.__table__.c[field_name]
        assert column.nullable is False
        assert column.default.is_callable

    session_column = Practice.__table__.c.slack_session_emoji
    assert session_column.nullable is True
    assert session_column.type.length == 80


def test_write_contract_distinguishes_derived_or_unchanged_from_explicit_empty():
    create_default = PracticeCreate(
        date=datetime(2026, 7, 14, 18, 15), location_id=1
    )
    create_empty = PracticeCreate(
        date=datetime(2026, 7, 14, 18, 15), location_id=1, plan_reactions=[]
    )
    update_default = PracticeUpdate(id=3)
    update_empty = PracticeUpdate(id=3, plan_reactions=[])

    assert create_default.plan_reactions is None
    assert update_default.plan_reactions is None
    assert create_empty.plan_reactions == []
    assert update_empty.plan_reactions == []
