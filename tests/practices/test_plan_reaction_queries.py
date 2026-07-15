from datetime import datetime
from uuid import uuid4

import pytest

from app import create_app
from app.models import db
from app.practices.models import PracticeActivity
from app.practices.plan_reaction_queries import (
    PlanReactionSourceSelectionError,
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
