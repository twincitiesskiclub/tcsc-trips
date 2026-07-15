from __future__ import annotations

import ast
import copy
import inspect
import json
import os
from datetime import datetime
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, event, insert, select, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from scripts import seed_practice_plan_reaction_defaults as seed


MANIFEST_PATH = (
    Path(__file__).parents[2]
    / "scripts/data/2026-07-15-practice-plan-reaction-history.json"
)
SCRIPT_PATH = Path(__file__).parents[2] / "scripts/seed_practice_plan_reaction_defaults.py"
APPROVED_NAMES = {
    "Run",
    "Bike",
    "Mountain Bike",
    "Classic Rollerski",
    "Skate Rollerski",
    "Skate/Classic Rollerski",
}
EVERGREEN = {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}


def _source(source_id, name, defaults):
    return {"id": source_id, "name": name, "default_plan_reactions": defaults}


@pytest.fixture
def seed_engine(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'seed.sqlite'}")
    seed.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def complete_targets(seed_engine):
    with seed_engine.begin() as connection:
        connection.execute(insert(seed.practice_types), [
            {
                "id": 1,
                "name": "Not Named Intervals",
                "has_intervals": True,
                "default_plan_reactions": [],
            },
            {
                "id": 2,
                "name": "Intervals by name only",
                "has_intervals": False,
                "default_plan_reactions": [],
            },
        ])
        connection.execute(insert(seed.practice_activities), [
            {
                "id": index + 10,
                "name": name,
                "default_plan_reactions": [],
            }
            for index, name in enumerate(seed.APPROVED_ACTIVITY_NAMES)
        ])
    return {
        row["name"]: row["id"]
        for row in (
            {"name": "Not Named Intervals", "id": 1},
            *(
                {"name": name, "id": index + 10}
                for index, name in enumerate(seed.APPROVED_ACTIVITY_NAMES)
            ),
        )
    }


@pytest.fixture
def seed_session(seed_engine, complete_targets):
    with Session(seed_engine) as session:
        yield session


def _insert_upcoming_multisport(engine, *, status="scheduled", practice_id=100):
    with engine.begin() as connection:
        connection.execute(insert(seed.practices), {
            "id": practice_id,
            "date": datetime(2099, 7, 20, 18, 0),
            "status": status,
            "plan_reactions": [EVERGREEN],
        })
        connection.execute(insert(seed.practice_activities_junction), [
            {"practice_id": practice_id, "activity_id": 10},
            {"practice_id": practice_id, "activity_id": 11},
        ])
        connection.execute(insert(seed.practice_types_junction), {
            "practice_id": practice_id,
            "type_id": 1,
        })


def _reference_values(engine):
    with engine.connect() as connection:
        return {
            "types": [dict(row) for row in connection.execute(
                select(seed.practice_types).order_by(seed.practice_types.c.id)
            ).mappings()],
            "activities": [dict(row) for row in connection.execute(
                select(seed.practice_activities).order_by(seed.practice_activities.c.id)
            ).mappings()],
            "practices": [dict(row) for row in connection.execute(
                select(seed.practices).order_by(seed.practices.c.id)
            ).mappings()],
        }


def test_manifest_records_exact_reviewed_scope():
    manifest = seed.load_manifest(MANIFEST_PATH)

    assert manifest["extraction"] == {
        "channel_id": "C042G463AQ1",
        "channel_name": "announcements-practices",
        "extracted_at_utc": "2026-07-15T17:05:15Z",
        "history_pages": 6,
        "returned_messages": 1097,
        "raw_extract_sha256": (
            "cec3462bc1a7cb4aa2e09b66a26b0c6ec5aaa5448f5f3498a1f42ee22d19674e"
        ),
    }
    assert manifest["review"] == {
        "state": "approved",
        "reviewed_on": "2026-07-15",
        "reviewer": "announcement-format design review",
        "note": (
            "Approved normalization follows the current 2026 reaction grammar; "
            "observations are never promoted at runtime."
        ),
    }
    assert len(manifest["evidence"]) == 8
    assert len(manifest["approved_targets"]) == 7
    assert {
        target["name"]
        for target in manifest["approved_targets"]
        if target["kind"] == "activity"
    } == APPROVED_NAMES


def test_manifest_rejects_duplicate_evidence_and_unknown_references():
    manifest = seed.load_manifest(MANIFEST_PATH)
    duplicate = copy.deepcopy(manifest)
    duplicate["evidence"].append(copy.deepcopy(duplicate["evidence"][0]))
    with pytest.raises(seed.SeedPlanError, match="unique evidence"):
        seed.validate_manifest(duplicate)

    unknown = copy.deepcopy(manifest)
    unknown["approved_targets"][0]["evidence_ids"] = ["missing-evidence"]
    with pytest.raises(seed.SeedPlanError, match="evidence reference"):
        seed.validate_manifest(unknown)

    duplicate_reference = copy.deepcopy(manifest)
    duplicate_reference["approved_targets"][0]["evidence_ids"] = [
        "interval-practice-2026-02-03",
        "interval-practice-2026-02-03",
    ]
    with pytest.raises(seed.SeedPlanError, match="unique evidence references"):
        seed.validate_manifest(duplicate_reference)


def test_manifest_requires_exact_json_types_and_target_fields():
    manifest = seed.load_manifest(MANIFEST_PATH)
    manifest["schema_version"] = True
    with pytest.raises(seed.SeedPlanError, match="schema version"):
        seed.validate_manifest(manifest)

    manifest = seed.load_manifest(MANIFEST_PATH)
    manifest["extraction"]["history_pages"] = True
    with pytest.raises(seed.SeedPlanError, match="extraction scope"):
        seed.validate_manifest(manifest)

    manifest = seed.load_manifest(MANIFEST_PATH)
    manifest["approved_targets"][1]["unexpected"] = "ignored"
    with pytest.raises(seed.SeedPlanError, match="target fields"):
        seed.validate_manifest(manifest)

    manifest = seed.load_manifest(MANIFEST_PATH)
    manifest["approved_targets"][1]["name"] = ["Run"]
    with pytest.raises(seed.SeedPlanError, match="six exact Activity"):
        seed.validate_manifest(manifest)

    manifest = seed.load_manifest(MANIFEST_PATH)
    manifest["approved_targets"][1]["evidence_ids"] = [{}]
    with pytest.raises(seed.SeedPlanError, match="evidence reference"):
        seed.validate_manifest(manifest)


@pytest.mark.parametrize("selector", [{"has_intervals": 1}, {"has_intervals": False}, {}])
def test_manifest_requires_one_exact_boolean_interval_selector(selector):
    manifest = seed.load_manifest(MANIFEST_PATH)
    manifest["approved_targets"][0]["selector"] = selector

    with pytest.raises(seed.SeedPlanError, match="interval selector"):
        seed.validate_manifest(manifest)


def test_manifest_rejects_activity_scope_or_nonnormalized_defaults():
    manifest = seed.load_manifest(MANIFEST_PATH)
    manifest["approved_targets"][1]["name"] = "Rollerski"
    with pytest.raises(seed.SeedPlanError, match="six exact Activity"):
        seed.validate_manifest(manifest)

    manifest = seed.load_manifest(MANIFEST_PATH)
    manifest["approved_targets"][1]["defaults"][0]["emoji"] = ":ATHLETIC_SHOE:"
    with pytest.raises(seed.SeedPlanError, match="normalized"):
        seed.validate_manifest(manifest)


def test_only_approved_targets_are_consumed(seed_session, complete_targets):
    manifest = seed.load_manifest(MANIFEST_PATH)
    manifest["evidence"].append({
        "id": "unapproved",
        "normalized_pairs": [{"emoji": "fire", "label": "fast"}],
        "review_state": "observation",
    })

    plan = seed.build_seed_plan(seed_session, manifest, lock=False)

    assert "fire" not in json.dumps(plan.to_dict())


def test_local_normalization_accepts_approved_skin_tone_and_rejects_bad_emoji():
    assert seed.normalize_plan_reactions([
        {"emoji": ":OLDER_ADULT::skin-tone-4:", "label": " experienced rollerskier "}
    ]) == [
        {"emoji": "older_adult::skin-tone-4", "label": "experienced rollerskier"}
    ]
    for emoji in ("white_check_mark", "bad emoji", "older_adult::skin-tone-9"):
        with pytest.raises(seed.SeedPlanError):
            seed.normalize_plan_reactions([{"emoji": emoji, "label": "member"}])


def test_local_normalization_enforces_four_unique_single_line_rows():
    with pytest.raises(seed.SeedPlanError, match="at most 4"):
        seed.normalize_plan_reactions([
            {"emoji": f"choice_{index}", "label": str(index)}
            for index in range(5)
        ])
    with pytest.raises(seed.SeedPlanError, match="appears more than once"):
        seed.normalize_plan_reactions([
            {"emoji": "bike", "label": "bike"},
            {"emoji": "bike", "label": "again"},
        ])
    with pytest.raises(seed.SeedPlanError, match="single line"):
        seed.normalize_plan_reactions([{"emoji": "bike", "label": "two\nlines"}])
    with pytest.raises(seed.SeedPlanError, match="label is required"):
        seed.normalize_plan_reactions([{"emoji": "bike", "label": "..."}])


def test_local_resolution_applies_types_always_and_activities_only_for_multisport():
    interval = _source(1, "Intervals", [EVERGREEN])
    run = _source(10, "Run", [{"emoji": "athletic_shoe", "label": "runner"}])
    bike = _source(11, "Bike", [{"emoji": "bike", "label": "bike"}])

    single = seed.resolve_default_plan_reactions([interval], [run])
    duplicate = seed.resolve_default_plan_reactions([interval], [run, run])
    multisport = seed.resolve_default_plan_reactions([interval], [run, bike])

    assert single == duplicate == (EVERGREEN,)
    assert multisport == (
        EVERGREEN,
        {"emoji": "bike", "label": "bike"},
        {"emoji": "athletic_shoe", "label": "runner"},
    )


def test_local_resolution_rejects_conflicts_and_union_overflow():
    left = _source(10, "Left", [{"emoji": "bike", "label": "bike"}])
    right = _source(11, "Right", [{"emoji": "bike", "label": "mountain biker"}])
    with pytest.raises(seed.SeedPlanError, match="conflicting labels"):
        seed.resolve_default_plan_reactions([], [left, right])

    workout = _source(1, "Workout", [
        {"emoji": f"workout_{index}", "label": str(index)} for index in range(3)
    ])
    activity_a = _source(10, "A", [{"emoji": "activity_a", "label": "a"}])
    activity_b = _source(11, "B", [{"emoji": "activity_b", "label": "b"}])
    with pytest.raises(seed.SeedPlanError, match="more than 4"):
        seed.resolve_default_plan_reactions([workout], [activity_a, activity_b])


def test_dry_run_classifies_empty_exact_and_conflict_without_mutation(
    seed_session,
    complete_targets,
):
    seed_session.execute(update(seed.practice_activities).where(
        seed.practice_activities.c.name == "Bike"
    ).values(default_plan_reactions=[{"emoji": "bike", "label": "bike"}]))
    seed_session.execute(update(seed.practice_activities).where(
        seed.practice_activities.c.name == "Run"
    ).values(default_plan_reactions=[{"emoji": "shoe", "label": "custom admin value"}]))
    seed_session.commit()
    before = _reference_values(seed_session.bind)

    plan = seed.build_seed_plan(seed_session, seed.load_manifest(MANIFEST_PATH), lock=False)

    assert plan.has_conflicts is True
    assert plan.change_for("Run").status == "conflict"
    assert plan.change_for("Bike").status == "exact"
    assert plan.change_for("Mountain Bike").status == "fill"
    assert _reference_values(seed_session.bind) == before


def test_target_name_or_count_drift_aborts(
    seed_session,
    complete_targets,
):
    seed_session.execute(seed.practice_activities.delete().where(
        seed.practice_activities.c.name == "Classic Rollerski"
    ))
    seed_session.commit()
    with pytest.raises(seed.SeedPlanError, match="expected 6 exact Activity targets"):
        seed.build_seed_plan(seed_session, seed.load_manifest(MANIFEST_PATH), lock=False)


def test_missing_interval_type_aborts(seed_session, complete_targets):
    seed_session.execute(seed.practice_types.update().values(has_intervals=False))
    seed_session.commit()
    with pytest.raises(seed.SeedPlanError, match="at least one has_intervals"):
        seed.build_seed_plan(seed_session, seed.load_manifest(MANIFEST_PATH), lock=False)


def test_interval_types_are_selected_by_boolean_not_name(seed_session, complete_targets):
    plan = seed.build_seed_plan(seed_session, seed.load_manifest(MANIFEST_PATH), lock=False)

    assert plan.change_for("Not Named Intervals").desired == (EVERGREEN,)
    assert plan.change_for("Intervals by name only") is None


def test_upcoming_multisport_uses_both_junctions_and_never_changes_snapshot(
    seed_engine,
    complete_targets,
):
    _insert_upcoming_multisport(seed_engine)
    before = _reference_values(seed_engine)["practices"]

    with Session(seed_engine) as session:
        plan = seed.build_seed_plan(session, seed.load_manifest(MANIFEST_PATH), lock=False)

    assert plan.upcoming_snapshot_mismatches == ({
        "practice_id": 100,
        "date": "2099-07-20T18:00:00",
        "current": [EVERGREEN],
        "resolved": [
            EVERGREEN,
            {"emoji": "bike", "label": "bike"},
            {"emoji": "athletic_shoe", "label": "runner"},
        ],
    },)
    assert _reference_values(seed_engine)["practices"] == before


def test_cancelled_or_single_activity_upcoming_practice_is_not_reported(
    seed_engine,
    complete_targets,
):
    _insert_upcoming_multisport(seed_engine, status="cancelled", practice_id=101)
    with seed_engine.begin() as connection:
        connection.execute(insert(seed.practices), {
            "id": 102,
            "date": datetime(2099, 7, 21, 18, 0),
            "status": "scheduled",
            "plan_reactions": [],
        })
        connection.execute(insert(seed.practice_activities_junction), {
            "practice_id": 102,
            "activity_id": 10,
        })

    with Session(seed_engine) as session:
        plan = seed.build_seed_plan(session, seed.load_manifest(MANIFEST_PATH), lock=False)

    assert plan.upcoming_snapshot_mismatches == ()


def test_locked_target_selects_use_for_update():
    manifest = seed.load_manifest(MANIFEST_PATH)
    statements = seed._target_selects(manifest, lock=True)

    assert len(statements) == 2
    assert all(
        "FOR UPDATE" in str(statement.compile(dialect=postgresql.dialect()))
        for statement in statements
    )


def test_render_is_deterministic_and_digest_is_bound_to_environment(
    seed_session,
    complete_targets,
):
    plan = seed.build_seed_plan(seed_session, seed.load_manifest(MANIFEST_PATH), lock=False)

    local_a = seed.render_seed_plan(plan, environment="local")
    local_b = seed.render_seed_plan(plan, environment="local")
    production = seed.render_seed_plan(plan, environment="production")

    assert local_a == local_b
    assert local_a.digest != production.digest
    payload = json.loads(local_a.canonical_json)
    assert payload["environment"] == "local"
    assert payload["extraction_sha256"] == (
        "cec3462bc1a7cb4aa2e09b66a26b0c6ec5aaa5448f5f3498a1f42ee22d19674e"
    )
    assert "changes" in payload and "conflicts" in payload


def test_digest_and_commit_require_an_explicit_environment():
    assert (
        inspect.signature(seed.render_seed_plan)
        .parameters["environment"]
        .default
        is inspect.Parameter.empty
    )
    assert (
        inspect.signature(seed.commit_seed_plan)
        .parameters["environment"]
        .default
        is inspect.Parameter.empty
    )


def test_commit_requires_exact_fresh_environment_digest(seed_engine, complete_targets):
    manifest = seed.load_manifest(MANIFEST_PATH)
    with Session(seed_engine) as session:
        plan = seed.build_seed_plan(session, manifest, lock=False)
    local_digest = seed.render_seed_plan(plan, environment="local").digest

    with pytest.raises(seed.SeedPlanError, match="approval digest"):
        seed.commit_seed_plan(
            seed_engine,
            manifest,
            approved_digest="wrong",
            environment="test",
        )
    with pytest.raises(seed.SeedPlanError, match="approval digest"):
        seed.commit_seed_plan(
            seed_engine,
            manifest,
            approved_digest=local_digest,
            environment="production",
        )


def test_nonempty_conflict_aborts_every_fill(seed_engine, complete_targets):
    manifest = seed.load_manifest(MANIFEST_PATH)
    with seed_engine.begin() as connection:
        connection.execute(update(seed.practice_activities).where(
            seed.practice_activities.c.name == "Run"
        ).values(default_plan_reactions=[{"emoji": "shoe", "label": "custom"}]))
    before = _reference_values(seed_engine)
    with Session(seed_engine) as session:
        plan = seed.build_seed_plan(session, manifest, lock=False)
    digest = seed.render_seed_plan(plan, environment="test").digest

    with pytest.raises(seed.SeedPlanError, match="different non-empty"):
        seed.commit_seed_plan(
            seed_engine,
            manifest,
            approved_digest=digest,
            environment="test",
        )

    assert _reference_values(seed_engine) == before


def test_value_drift_after_dry_run_is_caught_by_locked_recheck(
    seed_engine,
    complete_targets,
):
    manifest = seed.load_manifest(MANIFEST_PATH)
    with Session(seed_engine) as session:
        plan = seed.build_seed_plan(session, manifest, lock=False)
    digest = seed.render_seed_plan(plan, environment="test").digest
    with seed_engine.begin() as connection:
        connection.execute(update(seed.practice_activities).where(
            seed.practice_activities.c.name == "Run"
        ).values(default_plan_reactions=[{"emoji": "shoe", "label": "concurrent"}]))

    with pytest.raises(seed.SeedPlanError, match="approval digest"):
        seed.commit_seed_plan(
            seed_engine,
            manifest,
            approved_digest=digest,
            environment="test",
        )


def test_commit_uses_only_reference_updates_and_preserves_practice_snapshots(
    seed_engine,
    complete_targets,
):
    manifest = seed.load_manifest(MANIFEST_PATH)
    _insert_upcoming_multisport(seed_engine)
    before_practices = _reference_values(seed_engine)["practices"]
    statements = []

    @event.listens_for(seed_engine, "before_cursor_execute")
    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    with Session(seed_engine) as session:
        plan = seed.build_seed_plan(session, manifest, lock=False)
    digest = seed.render_seed_plan(plan, environment="test").digest
    result = seed.commit_seed_plan(
        seed_engine,
        manifest,
        approved_digest=digest,
        environment="test",
    )
    event.remove(seed_engine, "before_cursor_execute", capture)

    update_statements = [
        item.lower()
        for item in statements
        if item.lstrip().lower().startswith("update")
    ]
    assert update_statements
    assert all(
        statement.startswith("update practice_types")
        or statement.startswith("update practice_activities")
        for statement in update_statements
    )
    assert result.verified is True
    assert all(change.status == "exact" for change in result.plan.changes)
    assert _reference_values(seed_engine)["practices"] == before_practices


def test_repeat_after_commit_is_idempotent_but_snapshot_mismatch_remains_report_only(
    seed_engine,
    complete_targets,
):
    manifest = seed.load_manifest(MANIFEST_PATH)
    _insert_upcoming_multisport(seed_engine)
    with Session(seed_engine) as session:
        plan = seed.build_seed_plan(session, manifest, lock=False)
    result = seed.commit_seed_plan(
        seed_engine,
        manifest,
        approved_digest=seed.render_seed_plan(plan, environment="test").digest,
        environment="test",
    )

    with Session(seed_engine) as session:
        repeat = seed.build_seed_plan(session, manifest, lock=False)

    assert result.verified
    assert all(change.status == "exact" for change in repeat.changes)
    assert repeat.upcoming_snapshot_mismatches


def test_import_and_help_never_initialize_app_or_slack_modules():
    common = f"""
import builtins
import sys
real_import = builtins.__import__
def guarded(name, *args, **kwargs):
    forbidden = ('app.', 'slack_sdk', 'slack_bolt')
    if name == 'app' or name.startswith(forbidden):
        raise AssertionError('forbidden import: ' + name)
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded
sys.path.insert(0, {str(SCRIPT_PATH.parent)!r})
"""
    env = os.environ.copy()
    env.update({"SLACK_BOT_TOKEN": "fake", "SLACK_SIGNING_SECRET": "fake"})
    imported = subprocess.run(
        [sys.executable, "-c", common + "\nimport seed_practice_plan_reaction_defaults\n"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    helped = subprocess.run(
        [
            sys.executable,
            "-c",
            common
            + "\nimport seed_practice_plan_reaction_defaults as seed\n"
            + "sys.argv = ['seed', '--help']\n"
            + "try:\n    seed.main()\nexcept SystemExit as exc:\n    assert exc.code == 0\n",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert imported.returncode == 0, imported.stderr
    assert helped.returncode == 0, helped.stderr
    assert "--environment" in helped.stdout


def test_source_has_no_app_slack_dynamic_import_or_practice_snapshot_write():
    source = SCRIPT_PATH.read_text()
    tree = ast.parse(source)
    forbidden_roots = {"app", "slack_sdk", "slack_bolt", "importlib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden_roots for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden_roots
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "__import__"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "values":
                assert all(keyword.arg != "plan_reactions" for keyword in node.keywords)
    assert "create_app" not in source
    assert "conversations_history" not in source


def test_cli_sqlite_dry_run_is_repeatable_and_performs_zero_writes(
    seed_engine,
    complete_targets,
):
    _insert_upcoming_multisport(seed_engine)
    before = _reference_values(seed_engine)
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": str(seed_engine.url),
        "SLACK_BOT_TOKEN": "fake",
        "SLACK_SIGNING_SECRET": "fake",
    })
    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--environment",
        "local",
        "--dry-run",
    ]

    first = subprocess.run(command, text=True, capture_output=True, env=env, check=False)
    second = subprocess.run(command, text=True, capture_output=True, env=env, check=False)

    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    first_digest = next(
        line
        for line in first.stdout.splitlines()
        if line.startswith("Approval digest:")
    )
    second_digest = next(
        line
        for line in second.stdout.splitlines()
        if line.startswith("Approval digest:")
    )
    assert first_digest == second_digest
    assert _reference_values(seed_engine) == before
