from datetime import datetime
from uuid import uuid4

import pytest

from app import create_app
from app.models import db
from app.practices.models import PracticeActivity, PracticeType
from app.practices.plan_reaction_queries import (
    PlanReactionSourceSelectionError,
    load_all_plan_reaction_sources,
    load_selected_plan_reaction_sources,
)


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture
def activity_id(app):
    name = f"Plan Reaction Query Test {uuid4().hex}"
    with app.app_context():
        timestamp = datetime(2026, 7, 15)
        run = PracticeActivity(
            name=name,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.session.add(run)
        db.session.commit()
        saved_id = run.id
    try:
        yield saved_id
    finally:
        with app.app_context():
            db.session.rollback()
            PracticeActivity.query.filter_by(id=saved_id).delete()
            db.session.commit()


@pytest.fixture
def source_record_ids(app):
    token = uuid4().hex
    timestamp = datetime(2026, 7, 15)
    activities = (
        PracticeActivity(
            name=f"Plan Reaction Query Test {token} Zulu Activity",
            default_plan_reactions=[],
            created_at=timestamp,
            updated_at=timestamp,
        ),
        PracticeActivity(
            name=f"Plan Reaction Query Test {token} Alpha Activity",
            default_plan_reactions=[],
            created_at=timestamp,
            updated_at=timestamp,
        ),
    )
    practice_types = (
        PracticeType(
            name=f"Plan Reaction Query Test {token} Zulu Type",
            has_intervals=False,
            default_plan_reactions=[],
            created_at=timestamp,
            updated_at=timestamp,
        ),
        PracticeType(
            name=f"Plan Reaction Query Test {token} Alpha Type",
            has_intervals=False,
            default_plan_reactions=[],
            created_at=timestamp,
            updated_at=timestamp,
        ),
    )
    with app.app_context():
        db.session.add_all([*activities, *practice_types])
        db.session.commit()
        ids = {
            "activities": tuple(item.id for item in activities),
            "types": tuple(item.id for item in practice_types),
        }
    try:
        yield ids
    finally:
        with app.app_context():
            db.session.rollback()
            PracticeActivity.query.filter(
                PracticeActivity.id.in_(ids["activities"])
            ).delete(synchronize_session=False)
            PracticeType.query.filter(
                PracticeType.id.in_(ids["types"])
            ).delete(synchronize_session=False)
            db.session.commit()


def test_loader_deduplicates_ids_before_multisport_count(app, activity_id):
    with app.app_context():
        selected = load_selected_plan_reaction_sources(
            db.session,
            activity_ids=[str(activity_id), activity_id, activity_id],
            type_ids=[],
        )
        assert [item.id for item in selected.activities] == [activity_id]


@pytest.mark.parametrize(
    "bad_ids",
    [False, True, 0, 1, "12", {"id": 1}],
)
def test_loader_rejects_malformed_id_collections(app, bad_ids):
    with app.app_context(), pytest.raises(
        PlanReactionSourceSelectionError,
        match="^Activity IDs: invalid ID$",
    ) as error:
        load_selected_plan_reaction_sources(
            db.session,
            activity_ids=bad_ids,
            type_ids=[],
        )
    assert error.value.field == "activities"


@pytest.mark.parametrize("bad_id", [True, "", "abc", "1.5", None])
def test_loader_rejects_malformed_ids(app, bad_id):
    with app.app_context(), pytest.raises(
        PlanReactionSourceSelectionError, match="Activity IDs"
    ):
        load_selected_plan_reaction_sources(
            db.session, activity_ids=[bad_id], type_ids=[]
        )


def test_loader_rejects_unknown_ids_instead_of_returning_partial_selection(
    app,
    activity_id,
):
    with app.app_context():
        highest_id = (
            db.session.query(PracticeActivity.id)
            .order_by(PracticeActivity.id.desc())
            .limit(1)
            .scalar()
            or 0
        )
        unknown_id = highest_id + 1
        assert db.session.get(PracticeActivity, unknown_id) is None
        with pytest.raises(
            PlanReactionSourceSelectionError,
            match=f"^Unknown Activity ID: {unknown_id}$",
        ) as error:
            load_selected_plan_reaction_sources(
                db.session,
                activity_ids=[activity_id, unknown_id],
                type_ids=[],
            )
        assert error.value.field == "activities"


def test_loader_preserves_requested_type_order_and_deduplicates_ids(
    app,
    source_record_ids,
):
    zulu_id, alpha_id = source_record_ids["types"]
    with app.app_context():
        selected = load_selected_plan_reaction_sources(
            db.session,
            activity_ids=[],
            type_ids=[str(alpha_id), zulu_id, alpha_id],
        )
        assert [item.id for item in selected.practice_types] == [
            alpha_id,
            zulu_id,
        ]


@pytest.mark.parametrize("bad_id", [True, "", "abc", "1.5", None])
def test_loader_rejects_malformed_type_ids_with_type_field(app, bad_id):
    with app.app_context(), pytest.raises(
        PlanReactionSourceSelectionError,
        match="Workout Type IDs",
    ) as error:
        load_selected_plan_reaction_sources(
            db.session,
            activity_ids=[],
            type_ids=[bad_id],
        )
    assert error.value.field == "types"


def test_loader_rejects_unknown_type_ids_instead_of_partial_selection(
    app,
    source_record_ids,
):
    known_id = source_record_ids["types"][0]
    with app.app_context():
        highest_id = (
            db.session.query(PracticeType.id)
            .order_by(PracticeType.id.desc())
            .limit(1)
            .scalar()
            or 0
        )
        unknown_id = highest_id + 1
        assert db.session.get(PracticeType, unknown_id) is None
        with pytest.raises(
            PlanReactionSourceSelectionError,
            match=f"^Unknown Workout Type ID: {unknown_id}$",
        ) as error:
            load_selected_plan_reaction_sources(
                db.session,
                activity_ids=[],
                type_ids=[known_id, unknown_id],
            )
        assert error.value.field == "types"


def test_load_all_sources_returns_complete_name_ordered_model_tuples(
    app,
    source_record_ids,
):
    with app.app_context():
        selected = load_all_plan_reaction_sources(db.session)
        expected_activities = tuple(
            PracticeActivity.query.order_by(PracticeActivity.name).all()
        )
        expected_types = tuple(
            PracticeType.query.order_by(PracticeType.name).all()
        )

        assert isinstance(selected.activities, tuple)
        assert isinstance(selected.practice_types, tuple)
        assert all(
            isinstance(item, PracticeActivity) for item in selected.activities
        )
        assert all(
            isinstance(item, PracticeType) for item in selected.practice_types
        )
        assert [item.id for item in selected.activities] == [
            item.id for item in expected_activities
        ]
        assert [item.id for item in selected.practice_types] == [
            item.id for item in expected_types
        ]
        assert set(source_record_ids["activities"]).issubset(
            {item.id for item in selected.activities}
        )
        assert set(source_record_ids["types"]).issubset(
            {item.id for item in selected.practice_types}
        )
