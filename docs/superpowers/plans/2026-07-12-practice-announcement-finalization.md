# Practice Announcement Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make practice announcements accurate, accessible, resilient, and configurable, including reusable Practice Plan reactions, safe shared-post lifecycle handling, and a readable calendar-week summary.

**Architecture:** Activity and Workout Type settings own reusable Plan-reaction defaults; every Practice stores the resolved, editable snapshot used by Slack. Pure Block Kit and fallback-text builders consume `PracticeInfo` plus one gathered `AnnouncementConditions` object, while posting/orchestration owns Slack calls and Details lifecycle. Combined posts remain a defensive edge case and persist each session's reaction so cancellation or deletion cannot remap survivors.

**Tech Stack:** Python 3.12+, Flask, SQLAlchemy, Flask-Migrate/Alembic, PostgreSQL, Slack Bolt and Slack SDK, Jinja, browser JavaScript, Astral, PyYAML, pytest.

**Reference spec:** `docs/superpowers/specs/2026-07-12-practice-announcement-finalization-design.md`

**Known-good baseline:**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_announcement_blocks.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_refresh.py
```

Expected before implementation: `35 passed`.

## Global Constraints

- Preserve the existing standalone hierarchy; do not redesign it from scratch.
- Routine forecast, wind, parking, gear, trails, and AQI below 101 stay in Details.
- Only active weather alerts, AQI 101 or higher, headlamp requirements, and immediate time/location changes are promoted into the hero.
- Never render `No alerts` after a failed or empty lookup.
- Missing workout copy is exactly `Workout details coming soon.`
- Standalone RSVP copy begins `Bop ✅ if you're coming.`
- Supplemental copy uses the heading `Your Practice Plan:`; never label it `Optional:` or treat it as the RSVP.
- A maximum of four Plan reactions is allowed; labels are at most 80 characters.
- `workout_description` and `logistics_notes` edits are at most 2,500 characters.
- Slack limits are enforced centrally: header 150, section body 3,000, section field 2,000, context 2,000, fallback 4,000 characters.
- Plan reactions never create, update, or remove `PracticeRSVP`; only ✅ or a saved combined-session reaction does.
- Combined sessions are uncommon. Do not add a combined-group table, emoji picker, dynamic Slack modal updates, or per-member Plan-reaction persistence.
- Settings changes affect newly created practices only; existing Practice snapshots change only through explicit edit or Restore defaults.
- All sibling queries use both `slack_channel_id` and `slack_message_ts`.
- All automated tests run through `env/bin/pytest` with a path under `tests/`; never run bare `pytest`.
- Never expose or use real Slack credentials during automated tests. Clear Slack environment variables in test commands that import the Bolt app.
- Live validation posts only to `C07G9RTMRT3`, strips `<!channel>`, uses synthetic data, records timestamps immediately, and tears down every test message.
- Preserve unrelated worktree changes. Execution should start in an isolated worktree created by the selected Superpowers execution skill.

---

## File Structure

### Create

- `app/practices/plan_reactions.py`: domain normalization, validation, merging, parsing, and formatting.
- `app/slack/blocks/text.py`: shared Slack length guards; surface-specific fallback builders stay beside their Block Kit builders.
- `app/slack/practices/reactions.py`: attendance-reaction routing for add/remove events.
- `app/static/plan_reactions.js`: reusable inline Plan-reaction row editor for Settings and Practice editor pages.
- `migrations/versions/c4f1a8e2d9b7_add_practice_plan_reactions.py`: three JSON fields plus stable combined-session emoji.
- `tests/practices/test_plan_reactions.py`: pure domain tests.
- `tests/practices/test_plan_reaction_contracts.py`: model-to-interface mapping tests.
- `tests/practices/test_plan_reaction_migration.py`: isolated-schema evergreen backfill and downgrade coverage.
- `tests/routes/test_admin_practice_plan_reactions.py`: Settings and per-practice route behavior.
- `tests/routes/test_admin_practice_delete.py`: shared-post delete/cancel route gating.
- `tests/slack/test_slack_text.py`: length and fallback tests.
- `tests/integrations/test_daylight.py`: local-calendar daylight regression.
- `tests/slack/test_reaction_rsvp.py`: add/remove and supplemental-reaction isolation.
- `tests/slack/test_combined_announcements.py`: combined rendering and lifecycle tests.
- `tests/test_scheduler_practice_announcements.py`: compatible Strength grouping.
- `tests/slack/test_weekly_summary_blocks.py`: pure weekly layout and fallback tests.
- `tests/slack/test_practice_edit_full.py`: active full-edit modal limits and change context.
- `tests/agent/test_weekly_summary.py`: scheduled Monday-through-Sunday behavior.
- `tests/scripts/test_validate_announcement.py`: test-channel and teardown guardrails.

### Modify

- `app/practices/models.py`: default/snapshot JSON fields and `slack_session_emoji`.
- `app/practices/interfaces.py`: defaults, snapshot, session emoji, and `AnnouncementConditions` contracts.
- `app/practices/service.py`: map the new fields.
- `app/routes/admin_practices.py`: Settings CRUD, practice resolution/override, limits, change notice, and delete gating.
- `app/templates/admin/practices/config.html`: inline defaults on Activity and Type records.
- `app/templates/admin/practices/detail.html`: per-practice Plan reactions and authoring limits.
- `app/templates/admin/practices/_detail_script.js`: derived defaults, customization state, Restore defaults, and payload.
- `app/static/practice_editor.js`: optional tag-selection callback.
- `app/slack/modals.py`: prefilled editable Plan reactions and 2,500-character inputs.
- `app/slack/bolt_app.py`: create-modal persistence and thin reaction event delegation.
- `app/integrations/daylight.py`: Astral timezone argument.
- `app/slack/practices/_config.py`: read the configured 90-minute default duration.
- `app/slack/blocks/announcements.py`: standalone, Details, urgent exceptions, Practice Plan, and combined grammar.
- `app/slack/blocks/cancellations.py`: cancellation fallback text and length guards.
- `app/slack/blocks/summary.py`: explicit calendar week and one section per day.
- `app/slack/blocks/__init__.py`: re-export new public builders.
- `app/slack/practices/announcements.py`: one condition gather, complete fallback, Details deletion, reaction seeds, and stable combined updates.
- `app/slack/practices/cancellations.py`: shared-post-aware cancellation.
- `app/slack/practices/refresh.py`: refresh context, safe delete gating, cancelled weekly rows, and no weekly RSVP refresh.
- `app/slack/practices/rsvp.py`: preserve modern roots and update only a legacy going-count block when present.
- `app/slack/client.py`: persisted session-emoji assignment helpers.
- `app/scheduler.py`: compatible Strength groups and no duplicate weather fetch.
- `app/agent/routines/weekly_summary.py`: upcoming Monday bounds, cancellations, and complete fallback.
- `scripts/validate_announcement.py`: full guarded live scenario matrix.
- Existing targeted tests under `tests/slack/` and `tests/routes/`: update expectations and add regressions next to current coverage.

---

### Task 1: Build the Plan-reaction domain module

**Files:**

- Create: `app/practices/plan_reactions.py`
- Create: `tests/practices/test_plan_reactions.py`

**Interfaces:**

- Produces: `PlanReactionValidationError`, `EVERGREEN_PLAN_REACTION`, `normalize_plan_reactions()`, `resolve_default_plan_reactions()`, `parse_plan_reaction_lines()`, `format_plan_reaction_lines()`, `format_plan_reaction_legend()`, and `plan_reaction_names()`.
- Consumed by: migrations, Settings routes, practice routes, Slack modals, block builders, and reaction seeding.

- [ ] **Step 1: Write the failing domain tests**

Create `tests/practices/test_plan_reactions.py` with these cases:

```python
from types import SimpleNamespace

import pytest

from app.practices.plan_reactions import (
    PlanReactionValidationError,
    format_plan_reaction_legend,
    format_plan_reaction_lines,
    normalize_plan_reactions,
    parse_plan_reaction_lines,
    resolve_default_plan_reactions,
)


def source(name, options):
    return SimpleNamespace(name=name, default_plan_reactions=options)


def test_parse_and_format_colon_wrapped_lines():
    parsed = parse_plan_reaction_lines(
        ":evergreen_tree: Endurance instead of intervals\n:athletic_shoe: Run"
    )
    assert parsed == [
        {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"},
        {"emoji": "athletic_shoe", "label": "Run"},
    ]
    assert format_plan_reaction_lines(parsed).splitlines()[0].startswith(":evergreen_tree:")
    assert format_plan_reaction_legend(parsed) == (
        ":evergreen_tree: Endurance instead of intervals · :athletic_shoe: Run"
    )


def test_legend_escapes_member_supplied_slack_markup():
    assert format_plan_reaction_legend([
        {"emoji": "evergreen_tree", "label": "Easy < 60 min & social > speed"}
    ]) == ":evergreen_tree: Easy &lt; 60 min &amp; social &gt; speed"


def test_resolver_orders_types_then_activities_and_deduplicates_identical_pair():
    duplicate = [{"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}]
    result = resolve_default_plan_reactions(
        [source("Intervals", duplicate)],
        [source("Rollerski", duplicate + [{"emoji": "hatching_chick", "label": "New to rollerskiing"}])],
    )
    assert result == duplicate + [{"emoji": "hatching_chick", "label": "New to rollerskiing"}]


def test_resolver_rejects_same_emoji_with_two_labels():
    with pytest.raises(PlanReactionValidationError, match="conflicting labels") as error:
        resolve_default_plan_reactions(
            [source("Intervals", [{"emoji": "evergreen_tree", "label": "Endurance"}])],
            [source("Rollerski", [{"emoji": "evergreen_tree", "label": "New skier"}])],
        )
    assert "Workout Type Intervals" in str(error.value)
    assert "Activity Rollerski" in str(error.value)


@pytest.mark.parametrize("emoji", ["white_check_mark", "six", "ballot_box_with_check"])
def test_reserved_attendance_emoji_is_rejected(emoji):
    with pytest.raises(PlanReactionValidationError, match="reserved"):
        normalize_plan_reactions([{"emoji": emoji, "label": "Not allowed"}])


def test_more_than_four_and_multiline_label_are_rejected():
    with pytest.raises(PlanReactionValidationError, match="at most 4"):
        normalize_plan_reactions([
            {"emoji": f"custom_{index}", "label": f"Choice {index}"}
            for index in range(5)
        ])
    with pytest.raises(PlanReactionValidationError, match="single line"):
        normalize_plan_reactions([{"emoji": "evergreen_tree", "label": "One\nTwo"}])


def test_bare_shortcode_empty_and_four_value_boundaries():
    assert parse_plan_reaction_lines("evergreen_tree Endurance") == [
        {"emoji": "evergreen_tree", "label": "Endurance"}
    ]
    assert parse_plan_reaction_lines("") == []
    assert len(normalize_plan_reactions([
        {"emoji": f"choice_{index}", "label": f"Choice {index}"}
        for index in range(4)
    ])) == 4


def test_label_length_and_shortcode_wrapping_boundaries():
    assert normalize_plan_reactions([
        {"emoji": "evergreen_tree", "label": "L" * 80}
    ])[0]["label"] == "L" * 80
    with pytest.raises(PlanReactionValidationError, match="80 characters"):
        normalize_plan_reactions([
            {"emoji": "evergreen_tree", "label": "L" * 81}
        ])
    for invalid in (":evergreen_tree Endurance", "evergreen_tree: Endurance"):
        with pytest.raises(PlanReactionValidationError, match="Line 1"):
            parse_plan_reaction_lines(invalid)


def test_resolver_sorts_sources_and_rejects_effective_overflow():
    ordered = resolve_default_plan_reactions(
        [source("Zulu", [{"emoji": "z", "label": "Zulu"}]),
         source("Alpha", [{"emoji": "a", "label": "Alpha"}])],
        [source("Beta", [{"emoji": "b", "label": "Beta"}])],
    )
    assert [item["emoji"] for item in ordered] == ["a", "z", "b"]
    with pytest.raises(PlanReactionValidationError, match="more than 4"):
        resolve_default_plan_reactions(
            [source("Type", [
                {"emoji": f"type_{index}", "label": f"Type {index}"}
                for index in range(3)
            ])],
            [source("Activity", [
                {"emoji": f"activity_{index}", "label": f"Activity {index}"}
                for index in range(2)
            ])],
        )
```

- [ ] **Step 2: Run the tests and verify the module is missing**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q tests/practices/test_plan_reactions.py
```

Expected: collection fails with `ModuleNotFoundError: No module named 'app.practices.plan_reactions'`.

- [ ] **Step 3: Implement the domain module**

Create `app/practices/plan_reactions.py` with these exact public boundaries:

```python
"""Validation and formatting for supplemental practice-plan reactions."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

MAX_PLAN_REACTIONS = 4
MAX_PLAN_REACTION_LABEL = 80
EMOJI_RE = re.compile(r"^[a-z0-9_+\-]+$")
LINE_RE = re.compile(
    r"^\s*(?::(?P<wrapped>[a-z0-9_+\-]+):|(?P<bare>[a-z0-9_+\-]+))"
    r"\s+(?P<label>.+?)\s*$"
)

EVERGREEN_PLAN_REACTION = {
    "emoji": "evergreen_tree",
    "label": "Endurance instead of intervals",
}

RESERVED_ATTENDANCE_EMOJIS = frozenset({
    "white_check_mark", "ballot_box_with_check", "heavy_check_mark",
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "keycap_ten",
})


class PlanReactionValidationError(ValueError):
    """Raised when a Plan-reaction definition cannot be rendered safely."""


def _normalize_emoji(value: object, source: str) -> str:
    emoji = str(value or "").strip().lower()
    if emoji.startswith(":") and emoji.endswith(":") and len(emoji) > 2:
        emoji = emoji[1:-1]
    if not emoji or not EMOJI_RE.fullmatch(emoji):
        raise PlanReactionValidationError(f"{source}: enter a Slack emoji shortcode")
    if emoji in RESERVED_ATTENDANCE_EMOJIS:
        raise PlanReactionValidationError(f"{source}: :{emoji}: is reserved for attendance")
    return emoji


def normalize_plan_reactions(value: object, *, source: str = "Plan reactions") -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PlanReactionValidationError(f"{source}: expected a list")
    if len(value) > MAX_PLAN_REACTIONS:
        raise PlanReactionValidationError(f"{source}: use at most {MAX_PLAN_REACTIONS} reactions")

    normalized = []
    seen = set()
    for index, item in enumerate(value, start=1):
        item_source = f"{source} row {index}"
        if not isinstance(item, Mapping):
            raise PlanReactionValidationError(f"{item_source}: expected emoji and label")
        emoji = _normalize_emoji(item.get("emoji"), item_source)
        label = str(item.get("label") or "").strip()
        if not label:
            raise PlanReactionValidationError(f"{item_source}: label is required")
        if "\n" in label or "\r" in label:
            raise PlanReactionValidationError(f"{item_source}: label must be a single line")
        if len(label) > MAX_PLAN_REACTION_LABEL:
            raise PlanReactionValidationError(
                f"{item_source}: label must be {MAX_PLAN_REACTION_LABEL} characters or fewer"
            )
        if emoji in seen:
            raise PlanReactionValidationError(f"{source}: :{emoji}: appears more than once")
        seen.add(emoji)
        normalized.append({"emoji": emoji, "label": label})
    return normalized


def resolve_default_plan_reactions(practice_types: Iterable, activities: Iterable) -> list[dict[str, str]]:
    sources = [
        (f"Workout Type {item.name}", item)
        for item in sorted(practice_types or [], key=lambda item: item.name.lower())
    ] + [
        (f"Activity {item.name}", item)
        for item in sorted(activities or [], key=lambda item: item.name.lower())
    ]
    merged: list[dict[str, str]] = []
    by_emoji: dict[str, tuple[str, str]] = {}
    for source_name, item in sources:
        options = normalize_plan_reactions(
            getattr(item, "default_plan_reactions", None) or [], source=source_name
        )
        for option in options:
            previous = by_emoji.get(option["emoji"])
            if previous and previous[0] != option["label"]:
                raise PlanReactionValidationError(
                    f":{option['emoji']}: has conflicting labels in {previous[1]} and {source_name}"
                )
            if previous:
                continue
            by_emoji[option["emoji"]] = (option["label"], source_name)
            merged.append(option)
    if len(merged) > MAX_PLAN_REACTIONS:
        raise PlanReactionValidationError(
            f"Selected Activities and Workout Types produce more than {MAX_PLAN_REACTIONS} reactions"
        )
    return merged


def parse_plan_reaction_lines(text: str) -> list[dict[str, str]]:
    rows = []
    for line_number, line in enumerate((text or "").splitlines(), start=1):
        if not line.strip():
            continue
        match = LINE_RE.fullmatch(line)
        if not match:
            raise PlanReactionValidationError(
                f"Line {line_number}: use :emoji: Member-facing label"
            )
        rows.append({
            "emoji": match.group("wrapped") or match.group("bare"),
            "label": match.group("label"),
        })
    return normalize_plan_reactions(rows, source="Plan reactions")


def format_plan_reaction_lines(reactions: Iterable[Mapping[str, str]]) -> str:
    normalized = normalize_plan_reactions(list(reactions or []))
    return "\n".join(f":{item['emoji']}: {item['label']}" for item in normalized)


def format_plan_reaction_legend(reactions: Iterable[Mapping[str, str]]) -> str:
    normalized = normalize_plan_reactions(list(reactions or []))
    def escape_label(label: str) -> str:
        return label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return " · ".join(
        f":{item['emoji']}: {escape_label(item['label'])}" for item in normalized
    )


def plan_reaction_names(reactions: Iterable[Mapping[str, str]]) -> list[str]:
    return [item["emoji"] for item in normalize_plan_reactions(list(reactions or []))]
```

- [ ] **Step 4: Run the domain tests**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q tests/practices/test_plan_reactions.py
```

Expected: all tests pass.

- [ ] **Step 5: Commit the domain module**

```bash
git add app/practices/plan_reactions.py tests/practices/test_plan_reactions.py
git commit -m "feat(practices): add plan reaction domain rules"
```

### Task 2: Persist defaults, per-practice snapshots, and stable session reactions

**Files:**

- Modify: `app/practices/models.py:62-90,116-148`
- Modify: `app/practices/interfaces.py:85-101,126-167`
- Modify: `app/practices/service.py:64-82,155-199`
- Create: `migrations/versions/c4f1a8e2d9b7_add_practice_plan_reactions.py`
- Create: `tests/practices/test_plan_reaction_contracts.py`
- Create: `tests/practices/test_plan_reaction_migration.py`

**Interfaces:**

- Produces: `PracticeActivity.default_plan_reactions`, `PracticeType.default_plan_reactions`, `Practice.plan_reactions`, and nullable `Practice.slack_session_emoji`.
- Produces matching `PracticeActivityInfo`, `PracticeTypeInfo`, and `PracticeInfo` fields.
- `slack_session_emoji is None` means standalone. A stored value means the practice belongs to a combined-post lifecycle, including a one-survivor post.

- [ ] **Step 1: Write failing conversion tests**

Create `tests/practices/test_plan_reaction_contracts.py`:

```python
from types import SimpleNamespace

from app.practices.service import convert_activity_to_info, convert_type_to_info


def test_activity_and_type_info_include_default_plan_reactions():
    reactions = [{"emoji": "athletic_shoe", "label": "Run"}]
    activity = SimpleNamespace(
        id=1, name="Rollerski", gear_required=[], default_plan_reactions=reactions,
        airtable_id=None,
    )
    practice_type = SimpleNamespace(
        id=2, name="Intervals", fitness_goals=[], has_intervals=True,
        default_plan_reactions=reactions, airtable_id=None,
    )
    assert convert_activity_to_info(activity).default_plan_reactions == reactions
    assert convert_type_to_info(practice_type).default_plan_reactions == reactions
```

Extend the file with a minimal model-like Practice fixture and assert `convert_practice_to_info()` returns both `plan_reactions` and `slack_session_emoji` unchanged.

```python
from datetime import datetime

from app.practices.service import convert_practice_to_info


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
```

- [ ] **Step 2: Verify the contract tests fail**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q tests/practices/test_plan_reaction_contracts.py
```

Expected: failure because the dataclasses do not accept the new fields.

- [ ] **Step 3: Add model and interface fields**

Add these columns with callable Python defaults:

```python
class PracticeActivity(db.Model):
    default_plan_reactions = db.Column(db.JSON, nullable=False, default=list)


class PracticeType(db.Model):
    default_plan_reactions = db.Column(db.JSON, nullable=False, default=list)


class Practice(db.Model):
    plan_reactions = db.Column(db.JSON, nullable=False, default=list)
    slack_session_emoji = db.Column(db.String(80))
```

Add matching dataclass fields:

```python
class PracticeActivityInfo:
    default_plan_reactions: list[dict[str, str]] = field(default_factory=list)


class PracticeTypeInfo:
    default_plan_reactions: list[dict[str, str]] = field(default_factory=list)


class PracticeInfo:
    plan_reactions: list[dict[str, str]] = field(default_factory=list)
    slack_session_emoji: Optional[str] = None
```

Place fields after their related activity/type/workout and Slack fields so dataclass non-default ordering remains valid.

Also add the write-contract fields so `None` means derive/unchanged and `[]` remains an explicit empty list:

```python
class PracticeCreate:
    plan_reactions: Optional[list[dict[str, str]]] = None


class PracticeUpdate:
    plan_reactions: Optional[list[dict[str, str]]] = None
```

- [ ] **Step 4: Map the fields in service conversions**

Update the three converter return values:

```python
default_plan_reactions=activity.default_plan_reactions or [],
default_plan_reactions=practice_type.default_plan_reactions or [],
plan_reactions=practice.plan_reactions or [],
slack_session_emoji=practice.slack_session_emoji,
```

- [ ] **Step 5: Create the exact migration**

Create `migrations/versions/c4f1a8e2d9b7_add_practice_plan_reactions.py`:

```python
"""add practice plan reactions

Revision ID: c4f1a8e2d9b7
Revises: e36bbec59bde
Create Date: 2026-07-12
"""

import json

from alembic import op
import sqlalchemy as sa

revision = "c4f1a8e2d9b7"
down_revision = "e36bbec59bde"
branch_labels = None
depends_on = None

EVERGREEN = json.dumps([
    {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}
])


def upgrade():
    op.add_column(
        "practice_activities",
        sa.Column("default_plan_reactions", sa.JSON(), nullable=False,
                  server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "practice_types",
        sa.Column("default_plan_reactions", sa.JSON(), nullable=False,
                  server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "practices",
        sa.Column("plan_reactions", sa.JSON(), nullable=False,
                  server_default=sa.text("'[]'::json")),
    )
    op.add_column("practices", sa.Column("slack_session_emoji", sa.String(80)))

    op.execute(sa.text("""
        UPDATE practice_types
        SET default_plan_reactions = CAST(:evergreen AS JSON)
        WHERE has_intervals IS TRUE
    """).bindparams(evergreen=EVERGREEN))
    op.execute(sa.text("""
        UPDATE practices AS p
        SET plan_reactions = CAST(:evergreen AS JSON)
        WHERE EXISTS (
            SELECT 1
            FROM practice_types_junction AS j
            JOIN practice_types AS t ON t.id = j.type_id
            WHERE j.practice_id = p.id AND t.has_intervals IS TRUE
        )
    """).bindparams(evergreen=EVERGREEN))


def downgrade():
    op.drop_column("practices", "slack_session_emoji")
    op.drop_column("practices", "plan_reactions")
    op.drop_column("practice_types", "default_plan_reactions")
    op.drop_column("practice_activities", "default_plan_reactions")
```

- [ ] **Step 6: Test the migration and backfill in an isolated PostgreSQL schema**

Create `tests/practices/test_plan_reaction_migration.py`:

```python
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect

from app import create_app
from app.models import db
from migrations.versions import c4f1a8e2d9b7_add_practice_plan_reactions as revision


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db


def _column_names(connection, table, schema):
    return {item["name"] for item in inspect(connection).get_columns(table, schema=schema)}


def test_upgrade_backfills_intervals_and_downgrade_removes_columns(
    db_session, monkeypatch
):
    schema = f"plan_reaction_{uuid4().hex}"
    connection = db_session.engine.connect()
    transaction = connection.begin()
    try:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        connection.exec_driver_sql(
            "CREATE TABLE practice_activities (id INTEGER PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE practice_types ("
            "id INTEGER PRIMARY KEY, has_intervals BOOLEAN NOT NULL)"
        )
        connection.exec_driver_sql("CREATE TABLE practices (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql(
            "CREATE TABLE practice_types_junction ("
            "practice_id INTEGER NOT NULL, type_id INTEGER NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO practice_activities VALUES (1)")
        connection.exec_driver_sql(
            "INSERT INTO practice_types VALUES (10, TRUE), (20, FALSE)"
        )
        connection.exec_driver_sql("INSERT INTO practices VALUES (100), (200)")
        connection.exec_driver_sql(
            "INSERT INTO practice_types_junction VALUES (100, 10), (200, 20)"
        )

        context = MigrationContext.configure(connection)
        monkeypatch.setattr(revision, "op", Operations(context))
        revision.upgrade()

        type_rows = dict(connection.exec_driver_sql(
            "SELECT id, default_plan_reactions FROM practice_types ORDER BY id"
        ).all())
        practice_rows = dict(connection.exec_driver_sql(
            "SELECT id, plan_reactions FROM practices ORDER BY id"
        ).all())
        evergreen = [
            {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}
        ]
        assert type_rows == {10: evergreen, 20: []}
        assert practice_rows == {100: evergreen, 200: []}
        assert "default_plan_reactions" in _column_names(
            connection, "practice_activities", schema
        )
        assert "slack_session_emoji" in _column_names(
            connection, "practices", schema
        )

        revision.downgrade()
        assert "default_plan_reactions" not in _column_names(
            connection, "practice_activities", schema
        )
        assert "default_plan_reactions" not in _column_names(
            connection, "practice_types", schema
        )
        assert "plan_reactions" not in _column_names(connection, "practices", schema)
        assert "slack_session_emoji" not in _column_names(
            connection, "practices", schema
        )
    finally:
        transaction.rollback()
        connection.close()
```

Run:

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/practices/test_plan_reaction_migration.py
```

Expected: the upgrade/backfill/downgrade test passes.

- [ ] **Step 7: Apply the migration to a disposable clone and inspect it**

Before changing the local application database, clone its current `e36bbec59bde` state into a disposable database (for example `tcsc_practice_announcement_migration`). Point `DATABASE_URL` at that clone and run with Slack credentials cleared:

```bash
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips \
  SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= env/bin/flask db current
PGPASSWORD=tcsc createdb -h localhost -U tcsc \
  -T tcsc_trips tcsc_practice_announcement_migration
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_practice_announcement_migration \
  SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/flask db upgrade
```

Expected: the source reports `e36bbec59bde`, then upgrade `e36bbec59bde -> c4f1a8e2d9b7` succeeds on the clone. Query one interval type and one linked practice in the clone's Flask shell; both contain the evergreen pair. Non-interval records contain `[]`. Do not use a fresh empty database: `create_app()` calls `db.create_all()`, so a clone of the real pre-migration schema is required for an honest Alembic check.

- [ ] **Step 8: Run contract and existing service tests**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/practices/test_plan_reaction_contracts.py \
  tests/practices/test_plan_reaction_migration.py \
  tests/practices/test_service_leads.py
```

Expected: all pass.

- [ ] **Step 9: Commit the schema boundary**

```bash
git add app/practices/models.py app/practices/interfaces.py app/practices/service.py \
  migrations/versions/c4f1a8e2d9b7_add_practice_plan_reactions.py \
  tests/practices/test_plan_reaction_contracts.py \
  tests/practices/test_plan_reaction_migration.py
git commit -m "feat(practices): persist plan reaction defaults and snapshots"
```

### Task 3: Add reusable defaults to Activity and Workout Type Settings

**Files:**

- Modify: `app/routes/admin_practices.py:431-461,746-930`
- Modify: `app/templates/admin/practices/config.html:1058-1314,1439-1460`
- Create: `app/static/plan_reactions.js`
- Create: `tests/routes/test_admin_practice_plan_reactions.py`

**Interfaces:**

- Consumes: `normalize_plan_reactions()` from Task 1.
- Produces: Activity/Type JSON records with `default_plan_reactions` and a reusable `window.PlanReactionEditor` UI helper.

- [ ] **Step 1: Write failing Settings route tests**

Create `tests/routes/test_admin_practice_plan_reactions.py` using the existing authenticated-admin fixture pattern from `tests/routes/test_admin_practices_routes.py`. Add these assertions:

```python
def test_create_activity_persists_default_plan_reactions(admin_client, db_session):
    response = admin_client.post("/admin/practices/activities/create", json={
        "name": "Plan Reaction Test Rollerski",
        "gear_required": [],
        "default_plan_reactions": [
            {"emoji": ":hatching_chick:", "label": "New to rollerskiing"}
        ],
    })
    assert response.status_code == 200
    assert response.get_json()["activity"]["default_plan_reactions"] == [
        {"emoji": "hatching_chick", "label": "New to rollerskiing"}
    ]


def test_create_interval_type_uses_explicit_reactions(admin_client, db_session):
    response = admin_client.post("/admin/practices/types/create", json={
        "name": "Plan Reaction Test Intervals",
        "fitness_goals": [],
        "has_intervals": True,
        "default_plan_reactions": [
            {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}
        ],
    })
    assert response.status_code == 200
    assert response.get_json()["type"]["default_plan_reactions"][0]["emoji"] == "evergreen_tree"


def test_settings_reject_reserved_emoji(admin_client, db_session):
    response = admin_client.post("/admin/practices/types/create", json={
        "name": "Plan Reaction Test Invalid",
        "default_plan_reactions": [
            {"emoji": "white_check_mark", "label": "Wrong"}
        ],
    })
    assert response.status_code == 400
    assert response.get_json()["field"] == "default_plan_reactions"


def test_edit_can_clear_defaults(admin_client, db_session, activity_with_plan_reactions):
    response = admin_client.post(
        f"/admin/practices/activities/{activity_with_plan_reactions.id}/edit",
        json={"default_plan_reactions": []},
    )
    assert response.status_code == 200
    assert response.get_json()["activity"]["default_plan_reactions"] == []


def test_interval_type_without_explicit_reactions_stays_empty(admin_client):
    response = admin_client.post("/admin/practices/types/create", json={
        "name": "Plan Reaction Test No Hidden Default",
        "fitness_goals": [],
        "has_intervals": True,
    })
    assert response.status_code == 200
    assert response.get_json()["type"]["default_plan_reactions"] == []
```

Give fixtures unique names and delete their records during teardown so the local PostgreSQL database is left clean.

- [ ] **Step 2: Verify Settings tests fail on missing response fields**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/routes/test_admin_practice_plan_reactions.py
```

Expected: assertions fail because the endpoints ignore `default_plan_reactions`.

- [ ] **Step 3: Normalize defaults in every Activity/Type endpoint**

Add one route-local serializer per entity so create, edit, and data responses cannot drift:

```python
def _activity_json(activity):
    return {
        "id": activity.id,
        "name": activity.name,
        "gear_required": activity.gear_required or [],
        "default_plan_reactions": activity.default_plan_reactions or [],
        "practice_count": len(activity.practices),
    }


def _type_json(practice_type):
    return {
        "id": practice_type.id,
        "name": practice_type.name,
        "fitness_goals": practice_type.fitness_goals or [],
        "has_intervals": practice_type.has_intervals,
        "default_plan_reactions": practice_type.default_plan_reactions or [],
        "practice_count": len(practice_type.practices),
    }
```

Before mutating either model, validate only when the key is supplied:

```python
from app.practices.plan_reactions import (
    PlanReactionValidationError,
    normalize_plan_reactions,
)

try:
    if "default_plan_reactions" in request.json:
        defaults = normalize_plan_reactions(
            request.json["default_plan_reactions"], source="Plan reactions"
        )
    else:
        defaults = []
except PlanReactionValidationError as exc:
    return jsonify({"error": str(exc), "field": "default_plan_reactions"}), 400
```

Assign `default_plan_reactions=defaults` during create. During edit, leave the stored list unchanged when the key is absent and assign the normalized list when it is present. Explicit `[]` remains empty even when `has_intervals` is true. The migration is the only `has_intervals → evergreen` bridge; new or edited Settings records use the visible Plan-reactions field like every other Activity/Type.

- [ ] **Step 4: Create the shared browser row editor**

Create `app/static/plan_reactions.js` with this public API:

```javascript
window.PlanReactionEditor = (() => {
  const MAX = 4;

  function row(option, callbacks = {}) {
    const onChange = callbacks.onChange || (() => {});
    const onCommit = callbacks.onCommit || (() => {});
    const changed = (commit = false) => {
      onChange();
      if (commit) onCommit();
    };
    const wrap = document.createElement('div');
    wrap.className = 'plan-reaction-row';

    const emoji = document.createElement('input');
    emoji.type = 'text';
    emoji.className = 'plan-reaction-emoji cfg-field';
    emoji.maxLength = 82;
    emoji.placeholder = ':emoji:';
    emoji.setAttribute('aria-label', 'Slack emoji shortcode');
    emoji.value = option.emoji ? `:${option.emoji}:` : '';

    const label = document.createElement('input');
    label.type = 'text';
    label.className = 'plan-reaction-label cfg-field cfg-field-wide';
    label.maxLength = 80;
    label.placeholder = 'What this reaction means';
    label.setAttribute('aria-label', 'Member-facing reaction label');
    label.value = option.label || '';

    const up = document.createElement('button');
    up.type = 'button';
    up.textContent = 'Up';
    up.setAttribute('aria-label', 'Move reaction up');
    up.onclick = () => {
      if (wrap.previousElementSibling) wrap.parentNode.insertBefore(wrap, wrap.previousElementSibling);
      changed(true);
    };

    const down = document.createElement('button');
    down.type = 'button';
    down.textContent = 'Down';
    down.setAttribute('aria-label', 'Move reaction down');
    down.onclick = () => {
      if (wrap.nextElementSibling) wrap.parentNode.insertBefore(wrap.nextElementSibling, wrap);
      changed(true);
    };

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = 'Remove';
    remove.setAttribute('aria-label', 'Remove reaction');
    remove.onclick = () => { wrap.remove(); changed(true); };

    for (const button of [up, down, remove]) {
      button.className = 'plan-reaction-action';
    }

    emoji.addEventListener('input', onChange);
    label.addEventListener('input', onChange);
    emoji.addEventListener('change', onCommit);
    label.addEventListener('change', onCommit);
    wrap.append(emoji, label, up, down, remove);
    return wrap;
  }

  function set(container, options, callbacks = {}) {
    container.replaceChildren();
    (options || []).forEach(option => container.appendChild(row(option, callbacks)));
  }

  function get(container) {
    return Array.from(container.querySelectorAll('.plan-reaction-row')).map(item => ({
      emoji: item.querySelector('.plan-reaction-emoji').value.trim(),
      label: item.querySelector('.plan-reaction-label').value.trim(),
    }));
  }

  function add(container, callbacks = {}) {
    if (container.querySelectorAll('.plan-reaction-row').length >= MAX) return false;
    container.appendChild(row({emoji: '', label: ''}, callbacks));
    (callbacks.onChange || (() => {}))();
    return true;
  }

  return {MAX, set, get, add};
})();
```

Use `textContent` and DOM properties only; do not interpolate labels into HTML. `onChange` supports the Practice editor's derived/custom state, while `onCommit` lets Settings follow its existing autosave behavior without sending a request for every keystroke.

- [ ] **Step 5: Mount the editor inside Activity and Type cards**

Load `plan_reactions.js` before the page's inline script. Keep the existing name/gear/goal `doSave` functions unchanged; because the serializers now return `default_plan_reactions`, their rerenders preserve the value. Under each existing fields row, mount the component returned by this helper:

```html
<div class="plan-reaction-defaults">
  <span class="text-xs font-medium text-gray-600">Plan reactions</span>
  <span class="text-xs text-gray-500">Added automatically when this activity or workout type is selected.</span>
  <div class="plan-reaction-rows"></div>
  <button type="button" class="tbl-btn tbl-btn-secondary">Add reaction</button>
  <span class="plan-reaction-status" role="status" aria-live="polite"></span>
</div>
```

```javascript
function cfgBuildPlanReactionDefaults(record, entityKey, responseKey) {
    const rows = AdminUI.el('div', {
        class: 'plan-reaction-rows',
        role: 'group',
        'aria-label': 'Plan reaction defaults'
    }, []);
    const status = AdminUI.el('span', {
        class: 'plan-reaction-status',
        role: 'status',
        'aria-live': 'polite'
    }, []);
    const addButton = AdminUI.el('button', {
        type: 'button',
        class: 'tbl-btn tbl-btn-secondary'
    }, ['Add reaction']);

    function setStatus(message, isError) {
        status.textContent = message || '';
        status.classList.toggle('cfg-field-error-text', Boolean(isError));
    }

    function updateAddState() {
        const count = rows.querySelectorAll('.plan-reaction-row').length;
        addButton.disabled = !record.id || count >= PlanReactionEditor.MAX;
        if (!record.id) {
            setStatus('Save the Activity or Workout Type name first.', false);
        } else if (count >= PlanReactionEditor.MAX) {
            setStatus('Maximum of 4 reactions.', false);
        } else if (!status.classList.contains('cfg-field-error-text')) {
            setStatus('', false);
        }
    }

    function firstIncompleteRow() {
        return Array.from(rows.querySelectorAll('.plan-reaction-row')).find(row => {
            const emoji = row.querySelector('.plan-reaction-emoji').value.trim();
            const label = row.querySelector('.plan-reaction-label').value.trim();
            return !emoji || !label;
        }) || null;
    }

    function savePlanReactions() {
        if (!record.id) return;
        const incomplete = firstIncompleteRow();
        if (incomplete) {
            setStatus('Complete both fields or remove the unfinished reaction.', true);
            const emoji = incomplete.querySelector('.plan-reaction-emoji');
            const label = incomplete.querySelector('.plan-reaction-label');
            (!emoji.value.trim() ? emoji : label).focus();
            return;
        }

        setStatus('Saving…', false);
        AdminUI.mutate(
            `/admin/practices/${entityKey}/${record.id}/edit`,
            {default_plan_reactions: PlanReactionEditor.get(rows)}
        ).then(result => {
            record.default_plan_reactions =
                result[responseKey].default_plan_reactions || [];
            PlanReactionEditor.set(rows, record.default_plan_reactions, callbacks);
            setStatus('Saved.', false);
            updateAddState();
        }).catch(error => {
            setStatus(error.message, true);
        });
    }

    const callbacks = {
        onChange: updateAddState,
        onCommit: savePlanReactions
    };
    PlanReactionEditor.set(rows, record.default_plan_reactions || [], callbacks);

    addButton.addEventListener('click', () => {
        if (PlanReactionEditor.add(rows, callbacks)) {
            rows.querySelector(
                '.plan-reaction-row:last-child .plan-reaction-emoji'
            ).focus();
        }
        updateAddState();
    });
    updateAddState();

    return AdminUI.el('div', {class: 'plan-reaction-defaults'}, [
        AdminUI.el('span', {
            class: 'text-xs font-medium text-gray-600'
        }, ['Plan reactions']),
        AdminUI.el('span', {
            class: 'text-xs text-gray-500'
        }, ['Added automatically when this activity or workout type is selected.']),
        rows,
        addButton,
        status
    ]);
}
```

Append `cfgBuildPlanReactionDefaults(record, 'activities', 'activity')` to the Activity `fieldsDiv` children and `cfgBuildPlanReactionDefaults(record, 'types', 'type')` to the Type children. Extend draft records exactly:

```javascript
activities: { emptyRecord: { name: '', gear_required: [], default_plan_reactions: [] } },
types: { emptyRecord: { name: '', fitness_goals: [], has_intervals: false, default_plan_reactions: [] } },
```

Add exact local styles without introducing another card or modal:

```css
.plan-reaction-defaults{flex:1 0 100%;display:flex;flex-direction:column;gap:6px;padding-top:8px;border-top:1px solid rgba(28,44,68,.08)}
.plan-reaction-rows{display:flex;flex-direction:column;gap:6px}
.plan-reaction-row{display:grid;grid-template-columns:minmax(120px,180px) minmax(220px,1fr) auto auto auto;gap:6px;align-items:center}
.plan-reaction-action{min-height:32px;padding:0 8px;border:1px solid rgba(28,44,68,.12);border-radius:4px;background:#fff;color:#1c2c44;cursor:pointer}
.plan-reaction-action:focus-visible{outline:2px solid #1c2c44;outline-offset:1px}
.plan-reaction-status{min-height:18px;font-size:.75rem;color:#64748b}
.cfg-field-error-text{color:#dc2626}
@media(max-width:767px){
  .plan-reaction-row{grid-template-columns:repeat(3,1fr)}
  .plan-reaction-emoji,.plan-reaction-label{grid-column:1/-1;width:100%}
  .plan-reaction-action{min-height:44px}
}
```

For a brand-new draft card, the helper disables **Add reaction** until the existing name autosave returns its ID. Do not derive a hidden evergreen value from the Intervals toggle. Existing interval types receive their visible default from the migration and can then be edited normally.

- [ ] **Step 6: Run route tests and manually smoke-test Settings**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/routes/test_admin_practice_plan_reactions.py
```

Then open `/admin/practices/config`, test Activity and Type add/edit/clear, keyboard ordering, four-row limit, a reserved shortcode error, and a narrow mobile viewport.

- [ ] **Step 7: Commit Settings defaults**

```bash
git add app/routes/admin_practices.py app/templates/admin/practices/config.html \
  app/static/plan_reactions.js tests/routes/test_admin_practice_plan_reactions.py
git commit -m "feat(practices): configure plan reaction defaults"
```

### Task 4: Resolve and override Plan reactions in the web Practice editor

**Files:**

- Modify: `app/routes/admin_practices.py:152-348`
- Modify: `app/templates/admin/practices/detail.html:247-298,347-351`
- Modify: `app/templates/admin/practices/_detail_script.js:1-111`
- Modify: `app/static/practice_editor.js:15-37`
- Extend: `tests/routes/test_admin_practice_plan_reactions.py`

**Interfaces:**

- Consumes: selected Activity/Type defaults and `normalize_plan_reactions()`.
- Produces: saved `Practice.plan_reactions` snapshots with an explicit derived, saved-snapshot, customized, or Restore-defaults mode.

- [ ] **Step 1: Add failing create/edit route tests**

Add tests that post directly to the JSON routes:

```python
def test_create_without_plan_key_resolves_selected_defaults(
    admin_client, db_session, activity_with_plan_reactions, location
):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-07-14T18:15",
        "location_id": location.id,
        "activity_ids": [activity_with_plan_reactions.id],
        "type_ids": [],
    })
    practice = db_session.session.get(Practice, response.get_json()["practice_id"])
    assert practice.plan_reactions == activity_with_plan_reactions.default_plan_reactions


def test_create_explicit_empty_suppresses_defaults(
    admin_client, db_session, activity_with_plan_reactions, location
):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-07-14T18:15",
        "location_id": location.id,
        "activity_ids": [activity_with_plan_reactions.id],
        "type_ids": [],
        "plan_reactions": [],
    })
    practice = db_session.session.get(Practice, response.get_json()["practice_id"])
    assert practice.plan_reactions == []


def test_editing_tags_without_plan_key_preserves_snapshot(
    admin_client, db_session, practice_with_plan_reactions, second_activity
):
    original = list(practice_with_plan_reactions.plan_reactions)
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={"activity_ids": [second_activity.id]},
    )
    assert response.status_code == 200
    db_session.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.plan_reactions == original


def test_restore_defaults_resolves_current_selected_sources(
    admin_client, db_session, practice_with_plan_reactions, activity_with_plan_reactions
):
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={
            "activity_ids": [activity_with_plan_reactions.id],
            "type_ids": [],
            "restore_plan_reaction_defaults": True,
        },
    )
    assert response.status_code == 200
    db_session.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.plan_reactions == (
        activity_with_plan_reactions.default_plan_reactions
    )
```

Also assert create/edit return HTTP 400 for workout or Notes longer than 2,500 characters, and that two selected Settings sources with the same emoji/different labels return a source-named `plan_reactions` error when the client leaves defaults derived.

- [ ] **Step 2: Run the route tests to verify failures**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/routes/test_admin_practice_plan_reactions.py
```

Expected: snapshot assertions fail and oversized content is accepted.

- [ ] **Step 3: Resolve or normalize the snapshot server-side**

For create, load selected objects once before constructing `Practice`, then resolve the value:

```python
activity_ids = data.get("activity_ids") or []
type_ids = data.get("type_ids") or []
selected_activities = (
    PracticeActivity.query.filter(PracticeActivity.id.in_(activity_ids)).all()
    if activity_ids else []
)
selected_types = (
    PracticeType.query.filter(PracticeType.id.in_(type_ids)).all()
    if type_ids else []
)

try:
    plan_reactions = (
        normalize_plan_reactions(data["plan_reactions"])
        if "plan_reactions" in data
        else resolve_default_plan_reactions(selected_types, selected_activities)
    )
except PlanReactionValidationError as exc:
    return jsonify({"error": str(exc), "field": "plan_reactions"}), 400
```

Pass `plan_reactions=plan_reactions` to `Practice`, then assign `practice.activities = selected_activities` and `practice.practice_types = selected_types`.

For edit, use saved relationships when a tag key is absent, then preserve the snapshot by default, normalize an explicit value, or resolve the current sources for Restore:

```python
selected_activities = (
    PracticeActivity.query.filter(
        PracticeActivity.id.in_(data["activity_ids"])
    ).all()
    if data.get("activity_ids") else []
) if "activity_ids" in data else list(practice.activities)

selected_types = (
    PracticeType.query.filter(
        PracticeType.id.in_(data["type_ids"])
    ).all()
    if data.get("type_ids") else []
) if "type_ids" in data else list(practice.practice_types)

try:
    if data.get("restore_plan_reaction_defaults") is True:
        practice.plan_reactions = resolve_default_plan_reactions(
            selected_types, selected_activities
        )
    elif "plan_reactions" in data:
        practice.plan_reactions = normalize_plan_reactions(data["plan_reactions"])
except PlanReactionValidationError as exc:
    return jsonify({"error": str(exc), "field": "plan_reactions"}), 400
```

When their keys are present, assign `practice.activities = selected_activities` and `practice.practice_types = selected_types` after successful validation. This preserves partial API edits and makes Restore use exactly the submitted/current selections.

Reject oversized fields before assignment:

```python
for field, label in (("workout_description", "Workout"), ("logistics_notes", "Notes / Logistics")):
    value = data.get(field)
    if value is not None and len(value) > 2500:
        return jsonify({"error": f"{label} must be 2,500 characters or fewer", "field": field}), 400
```

Keep the existing refresh call unchanged in this task. Task 9 adds previous-snapshot and time/location context once the announcement refresh interface supports it, so this commit remains independently green.

- [ ] **Step 4: Make tag pills notify the Plan editor**

Change the existing signature without breaking current callers:

```javascript
function peRenderTagPills(containerId, data, selectedIds, onChange = null) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.replaceChildren();
    if (!data || data.length === 0) {
        const empty = document.createElement('span');
        empty.className = 'pe-empty';
        empty.textContent = 'None defined';
        container.appendChild(empty);
        return;
    }
    for (const item of data) {
        const label = document.createElement('button');
        const selected = selectedIds.includes(item.id);
        label.type = 'button';
        label.className = 'pe-pill' + (selected ? ' selected' : '');
        label.dataset.value = item.id;
        label.setAttribute('aria-pressed', selected ? 'true' : 'false');
        label.textContent = item.name;
        label.onclick = () => {
            const on = label.classList.toggle('selected');
            label.setAttribute('aria-pressed', on ? 'true' : 'false');
            if (onChange) onChange();
        };
        container.appendChild(label);
    }
}
```

- [ ] **Step 5: Add the per-practice editor markup**

Load `plan_reactions.js` before `practice_editor.js`. Add after Workout Plan:

```html
<section class="card">
  <div class="section-head">
    <h2 class="section-label">Plan reactions</h2>
    <button type="button" id="restore-plan-reactions" class="btn-ghost btn-sm">Restore defaults</button>
  </div>
  <p class="field-hint">✅ is attendance. These reactions describe a member's practice plan.</p>
  <div id="plan-reaction-rows"></div>
  <button type="button" id="add-plan-reaction" class="btn-ghost btn-sm">Add reaction</button>
  <span id="plan-reaction-status" role="status" aria-live="polite"></span>
</section>
```

Load scripts in this order:

```html
<script src="{{ url_for('static', filename='plan_reactions.js') }}"></script>
<script src="{{ url_for('static', filename='practice_editor.js') }}"></script>
```

Add `maxlength="2500"` to both workout and Notes textareas and add page-scoped styles:

```css
#workout-editor .plan-reaction-rows{display:flex;flex-direction:column;gap:8px;margin:12px 0}
#workout-editor .plan-reaction-row{display:grid;grid-template-columns:160px minmax(220px,1fr) auto auto auto;gap:8px;align-items:center}
#workout-editor .plan-reaction-action{min-height:40px;padding:0 10px;border:1.5px solid #e5e7eb;border-radius:8px;background:#fff;color:#475569;cursor:pointer}
#workout-editor .plan-reaction-action:focus-visible{outline:2px solid #1c2c44;outline-offset:2px}
#workout-editor #plan-reaction-status{display:block;min-height:18px;font-size:12px;color:#64748b}
#workout-editor #plan-reaction-status.field-error{color:#c53030}
@media(max-width:767px){
  #workout-editor .plan-reaction-row{grid-template-columns:repeat(3,1fr)}
  #workout-editor .plan-reaction-emoji,#workout-editor .plan-reaction-label{grid-column:1/-1;width:100%}
  #workout-editor .plan-reaction-action{min-height:44px}
}
```

- [ ] **Step 6: Implement derived/customized state in `_detail_script.js`**

Inject and manage these values:

```javascript
const savedPlanReactions = {{ (practice.plan_reactions or []) | tojson if practice else '[]' }};
let activitiesData = [];
let typesData = [];
let planReactionMode = practiceId ? 'snapshot' : 'derived';
let planReactionError = null;

function setPlanReactionError(message) {
  planReactionError = message || null;
  const status = document.getElementById('plan-reaction-status');
  status.textContent = planReactionError || '';
  status.classList.toggle('field-error', Boolean(planReactionError));
}

function selectedTagIds(containerId) {
  return peCollectIds(containerId);
}

function resolveCurrentDefaults() {
    const sources = [
    ...typesData
      .filter(item => selectedTagIds('types-pills').includes(item.id))
      .sort((left, right) => left.name.localeCompare(right.name))
      .map(item => ({...item, sourceLabel: `Workout Type ${item.name}`})),
    ...activitiesData
      .filter(item => selectedTagIds('activities-pills').includes(item.id))
      .sort((left, right) => left.name.localeCompare(right.name))
      .map(item => ({...item, sourceLabel: `Activity ${item.name}`})),
  ];
  const seen = new Map();
  const merged = [];
  for (const source of sources) {
    for (const option of (source.default_plan_reactions || [])) {
      const previous = seen.get(option.emoji);
      if (previous && previous.label !== option.label) {
        return {
          reactions: [],
          error: `:${option.emoji}: conflicts between ${previous.source} and ${source.sourceLabel}`,
        };
      }
      if (!previous) {
        seen.set(option.emoji, {label: option.label, source: source.sourceLabel});
        merged.push({...option});
      }
    }
  }
  if (merged.length > PlanReactionEditor.MAX) {
    return {reactions: [], error: 'Selected defaults produce more than 4 reactions'};
  }
  return {reactions: merged, error: null};
}

function refreshDerivedPlanReactions() {
  if (planReactionMode === 'derived' || planReactionMode === 'restore') {
    const resolved = resolveCurrentDefaults();
    setPlanReactionError(resolved.error);
    PlanReactionEditor.set(
      document.getElementById('plan-reaction-rows'),
      resolved.reactions,
      planReactionCallbacks(),
    );
  }
}

function markCustomized() {
  planReactionMode = 'custom';
  setPlanReactionError(null);
}

function planReactionCallbacks() {
  return {
    onChange() {
      markCustomized();
      updatePlanReactionAddState();
    }
  };
}

function updatePlanReactionAddState() {
  const rows = document.getElementById('plan-reaction-rows');
  const add = document.getElementById('add-plan-reaction');
  const count = rows.querySelectorAll('.plan-reaction-row').length;
  add.disabled = count >= PlanReactionEditor.MAX;
  if (count >= PlanReactionEditor.MAX && !planReactionError) {
    document.getElementById('plan-reaction-status').textContent =
      'Maximum of 4 reactions.';
  } else if (!planReactionError) {
    document.getElementById('plan-reaction-status').textContent = '';
  }
}

function initializePlanReactionEditor() {
  const rows = document.getElementById('plan-reaction-rows');
  if (practiceId) {
    PlanReactionEditor.set(rows, savedPlanReactions, planReactionCallbacks());
  } else {
    refreshDerivedPlanReactions();
  }

  document.getElementById('add-plan-reaction').addEventListener('click', () => {
    if (PlanReactionEditor.add(rows, planReactionCallbacks())) {
      rows.querySelector(
        '.plan-reaction-row:last-child .plan-reaction-emoji'
      ).focus();
    }
    updatePlanReactionAddState();
  });
  document.getElementById('restore-plan-reactions').addEventListener('click', () => {
    planReactionMode = practiceId ? 'restore' : 'derived';
    refreshDerivedPlanReactions();
  });
  updatePlanReactionAddState();
}
```

At the end of `refreshDerivedPlanReactions()`, call `updatePlanReactionAddState()`. In `loadFormData()`, replace the two tag calls with:

```javascript
activitiesData = acts.activities || [];
typesData = types.types || [];
peRenderTagPills(
  'activities-pills', activitiesData, selActivities, refreshDerivedPlanReactions
);
peRenderTagPills(
  'types-pills', typesData, selTypes, refreshDerivedPlanReactions
);
initializePlanReactionEditor();
```

For new practices, this mounts resolved defaults after reference data loads. Existing practices mount `savedPlanReactions` and do not recalculate when tags change. Restore recalculates through the current selections.

Immediately before adding `form-loading` in the submit handler, validate the visible rows and build the payload conditionally:

```javascript
if (
  (planReactionMode === 'derived' || planReactionMode === 'restore') &&
  planReactionError
) {
  showToast(planReactionError, 'error');
  return;
}

if (planReactionMode === 'custom') {
  const reactions = PlanReactionEditor.get(
    document.getElementById('plan-reaction-rows')
  );
  const incomplete = reactions.find(item => !item.emoji || !item.label);
  if (incomplete) {
    setPlanReactionError('Complete both fields or remove the unfinished reaction.');
    const row = Array.from(document.querySelectorAll(
      '#plan-reaction-rows .plan-reaction-row'
    )).find(item => {
      const emoji = item.querySelector('.plan-reaction-emoji').value.trim();
      const label = item.querySelector('.plan-reaction-label').value.trim();
      return !emoji || !label;
    });
    if (row) {
      const emoji = row.querySelector('.plan-reaction-emoji');
      const label = row.querySelector('.plan-reaction-label');
      (!emoji.value.trim() ? emoji : label).focus();
    }
    return;
  }
  payload.plan_reactions = reactions;
} else if (planReactionMode === 'restore') {
  payload.restore_plan_reaction_defaults = true;
}
```

Omitting the key for a new untouched derived list makes the server resolver authoritative and preserves source-named conflict errors. Omitting it for an existing untouched snapshot preserves that snapshot. A customized empty list is submitted as `[]` and remains intentionally empty.

- [ ] **Step 7: Run route tests and complete the browser checklist**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/routes/test_admin_practice_plan_reactions.py \
  tests/routes/test_admin_practices_routes.py
```

Manually verify new-practice defaults, changes before customization, customization freeze, explicit clear, Restore defaults, edit/reload persistence, keyboard ordering, and 375px layout.

- [ ] **Step 8: Commit the web authoring flow**

```bash
git add app/routes/admin_practices.py app/templates/admin/practices/detail.html \
  app/templates/admin/practices/_detail_script.js app/static/practice_editor.js \
  tests/routes/test_admin_practice_plan_reactions.py
git commit -m "feat(practices): apply and override plan reactions per practice"
```

### Task 5: Prefill and edit Plan reactions in the Slack creation modal

**Files:**

- Modify: `app/slack/modals.py:433-818`
- Modify: `app/slack/bolt_app.py:631-990,1438-1455`
- Modify: `tests/slack/test_practice_create_modal.py`
- Create: `tests/slack/test_practice_edit_full.py`

**Interfaces:**

- Consumes: `resolve_default_plan_reactions()`, `format_plan_reaction_lines()`, and `parse_plan_reaction_lines()`.
- Adds keyword `initial_plan_reactions=None` to `build_practice_create_modal` and persists `Practice.plan_reactions` from the visible modal value.
- Keeps both active Slack workout authoring surfaces within the 2,500-character input limit.

- [ ] **Step 1: Add failing modal-builder tests**

Append:

```python
def test_create_modal_prefills_plan_reactions_and_limits_workout():
    modal = build_practice_create_modal(
        datetime(2026, 7, 14, 18, 15),
        "18:15",
        locations=[(10, "Theodore Wirth")],
        initial_plan_reactions=[
            {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}
        ],
    )
    blocks = _blocks_by_id(modal)
    field = blocks["plan_reactions_block"]
    assert field["label"]["text"] == "Plan reactions"
    assert field["element"]["initial_value"] == (
        ":evergreen_tree: Endurance instead of intervals"
    )
    assert "Defaults loaded from Settings" in field["hint"]["text"]
    assert blocks["workout_block"]["element"]["max_length"] == 2500
```

In the same test file, import `_parse_practice_authoring_values` and add:

```python
def _authoring_values(workout="", plan_text=""):
    return {
        "workout_block": {"workout_description": {"value": workout}},
        "plan_reactions_block": {"plan_reactions": {"value": plan_text}},
    }


def test_create_submission_uses_edited_visible_plan_value():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(
            workout="5 x 4 minutes",
            plan_text=":athletic_shoe: Run instead",
        ),
        include_plan_reactions=True,
    )
    assert errors == {}
    assert fields == {
        "workout_description": "5 x 4 minutes",
        "plan_reactions": [{"emoji": "athletic_shoe", "label": "Run instead"}],
    }


def test_create_submission_can_clear_prefilled_plan_value():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(plan_text=""), include_plan_reactions=True
    )
    assert errors == {}
    assert fields["plan_reactions"] == []


def test_create_submission_maps_invalid_plan_to_its_slack_block():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(
            plan_text=":evergreen_tree Endurance instead of intervals"
        ),
        include_plan_reactions=True,
    )
    assert "plan_reactions" not in fields
    assert errors == {
        "plan_reactions_block": "Line 1: use :emoji: Member-facing label"
    }


def test_authoring_rejects_tampered_oversized_workout():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(workout="x" * 2501), include_plan_reactions=False
    )
    assert len(fields["workout_description"]) == 2501
    assert errors == {
        "workout_block": "Workout must be 2,500 characters or fewer"
    }
```

Create `tests/slack/test_practice_edit_full.py`:

```python
from datetime import datetime

from app.practices.interfaces import PracticeInfo, PracticeStatus
from app.slack.modals import build_practice_edit_full_modal


def test_full_edit_modal_limits_workout_to_2500_characters():
    practice = PracticeInfo(
        id=42,
        date=datetime(2026, 7, 14, 18, 15),
        day_of_week="Tuesday",
        status=PracticeStatus.SCHEDULED,
        workout_description="5 x 4 minutes",
    )
    modal = build_practice_edit_full_modal(practice)
    blocks = {
        block["block_id"]: block
        for block in modal["blocks"]
        if "block_id" in block
    }
    assert blocks["workout_block"]["element"]["max_length"] == 2500
```

- [ ] **Step 2: Verify the builder test fails**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py
```

Expected: missing `initial_plan_reactions` argument or block.

- [ ] **Step 3: Extend the modal builder**

Add `initial_plan_reactions: list[dict[str, str]] | None = None` to the signature. Add `max_length: 2500` to the workout input and append this input after Activities and Types:

```python
plan_element = {
    "type": "plain_text_input",
    "action_id": "plan_reactions",
    "multiline": True,
    "max_length": 1000,
    "placeholder": {"type": "plain_text", "text": ":emoji: What it means"},
}
formatted = format_plan_reaction_lines(initial_plan_reactions or [])
if formatted:
    plan_element["initial_value"] = formatted
blocks.append({
    "type": "input",
    "block_id": "plan_reactions_block",
    "optional": True,
    "label": {"type": "plain_text", "text": "Plan reactions"},
    "hint": {
        "type": "plain_text",
        "text": "Defaults loaded from Settings. Edit as needed for this practice, one reaction per line.",
    },
    "element": plan_element,
})
```

- [ ] **Step 4: Resolve slot defaults before opening the modal**

In `handle_create_practice_from_summary`, load the configured IDs and resolve them:

```python
from app.practices.models import PracticeActivity, PracticeType
from app.practices.plan_reactions import (
    PlanReactionValidationError,
    resolve_default_plan_reactions,
)

activity_ids = (slot_defaults or {}).get("activity_ids", [])
type_ids = (slot_defaults or {}).get("type_ids", [])
activities = PracticeActivity.query.filter(PracticeActivity.id.in_(activity_ids)).all() if activity_ids else []
practice_types = PracticeType.query.filter(PracticeType.id.in_(type_ids)).all() if type_ids else []
try:
    initial_plan_reactions = resolve_default_plan_reactions(practice_types, activities)
except PlanReactionValidationError as exc:
    client.chat_postEphemeral(
        channel=body["channel"]["id"], user=user_id,
        text=f":warning: Plan reaction defaults need attention: {exc}",
    )
    return
```

Pass `initial_plan_reactions=initial_plan_reactions` into the modal builder.

- [ ] **Step 5: Parse both active authoring surfaces before acknowledgment**

Add after `_safe_get()` in `app/slack/bolt_app.py`:

```python
def _parse_practice_authoring_values(
    values: dict,
    *,
    include_plan_reactions: bool,
) -> tuple[dict, dict[str, str]]:
    from app.practices.plan_reactions import (
        PlanReactionValidationError,
        parse_plan_reaction_lines,
    )

    fields = {
        "workout_description": _safe_get(
            values, "workout_block", "workout_description", "value", default=""
        )
    }
    errors = {}
    if len(fields["workout_description"]) > 2500:
        errors["workout_block"] = "Workout must be 2,500 characters or fewer"

    if include_plan_reactions:
        plan_text = _safe_get(
            values, "plan_reactions_block", "plan_reactions", "value", default=""
        )
        try:
            fields["plan_reactions"] = parse_plan_reaction_lines(plan_text)
        except PlanReactionValidationError as exc:
            errors["plan_reactions_block"] = str(exc)
    return fields, errors
```

In the create listener, call the helper immediately after reading `values`; acknowledge and return on errors. Remove the duplicate workout extraction and pass `**authoring` to the `Practice` constructor so the visible Plan value is persisted. Keep plain success `ack()` after commit. Do not add this field to dead `practice_edit` or `workout_entry` modal builders.

```python
authoring, errors = _parse_practice_authoring_values(
    values, include_plan_reactions=True
)
if errors:
    ack(response_action="errors", errors=errors)
    return

practice = Practice(
    date=practice_datetime,
    day_of_week=practice_datetime.strftime("%A"),
    status="scheduled",
    location_id=int(location_id) if location_id else None,
    social_location_id=social_location_id,
    is_dark_practice=is_dark_practice,
    slack_coach_summary_ts=message_ts,
    **authoring,
)
```

- [ ] **Step 6: Enforce the same limit in the active full-edit modal**

Add `max_length: 2500` to `build_practice_edit_full_modal()`'s workout input. In its handler, read `values`, call `_parse_practice_authoring_values(values, include_plan_reactions=False)`, return a field-error acknowledgment when needed, and otherwise call plain `ack()` once before entering the app context. Replace its later workout extraction with `practice.workout_description = authoring["workout_description"]`. Do not alter the dead small edit/workout modal builders.

```python
values = _safe_get(view, "state", "values", default={})
authoring, errors = _parse_practice_authoring_values(
    values, include_plan_reactions=False
)
if errors:
    ack(response_action="errors", errors=errors)
    return
ack()
```

- [ ] **Step 7: Remove credential-bearing Bolt diagnostics**

Replace the token-slicing startup print near the top of `app/slack/bolt_app.py` and its adjacent startup prints with `logger.info()` calls that report only enabled/disabled mode and boolean configuration state. No log or print may include any token substring. Verify:

```bash
! rg '_bot_token\[' app/slack/bolt_app.py
```

Expected: `rg` finds no token slicing.

- [ ] **Step 8: Run modal and parser tests**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/practices/test_plan_reactions.py
```

Expected: all pass.

- [ ] **Step 9: Commit the Slack creation flow**

```bash
git add app/slack/modals.py app/slack/bolt_app.py \
  tests/slack/test_practice_create_modal.py tests/slack/test_practice_edit_full.py
git commit -m "feat(slack): prefill practice plan reactions at creation"
```

---

### Task 6: Add central Slack text guards

**Files:**

- Create: `app/slack/blocks/text.py`
- Create: `tests/slack/test_slack_text.py`
- Modify: `app/slack/blocks/__init__.py`

**Interfaces:**

- Produces: `truncate_slack_text()`, `guard_slack_blocks()`, and `guard_fallback_text()`.
- Every public announcement, Details, cancellation, combined, and weekly builder must return guarded blocks; every Slack `text=` fallback must use the fallback guard.

- [ ] **Step 1: Write failing guard tests**

Create `tests/slack/test_slack_text.py`:

```python
import logging

from app.slack.blocks.text import (
    FALLBACK_TEXT_MAX,
    guard_fallback_text,
    guard_slack_blocks,
    truncate_slack_text,
)


def test_guard_truncates_each_supported_block_field(caplog):
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "H" * 151}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "S" * 3001}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": "F" * 3001},
        ]},
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": "C" * 2001},
            {"type": "image", "image_url": "https://example.test/icon.png", "alt_text": "icon"},
        ]},
    ]

    with caplog.at_level(logging.WARNING):
        guarded = guard_slack_blocks(blocks, surface="practice", practice_id=42)

    assert len(guarded[0]["text"]["text"]) == 150
    assert len(guarded[1]["text"]["text"]) == 3000
    assert len(guarded[2]["fields"][0]["text"]) == 2000
    assert len(guarded[3]["elements"][0]["text"]) == 2000
    assert guarded[3]["elements"][1]["alt_text"] == "icon"
    assert "practice" in caplog.text and "42" in caplog.text


def test_guards_do_not_mutate_the_input_and_preserve_short_text():
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Short"}}]
    assert guard_slack_blocks(blocks, surface="test") == blocks
    assert guard_slack_blocks(blocks, surface="test") is not blocks
    assert blocks[0]["text"]["text"] == "Short"


def test_fallback_text_is_nonempty_and_bounded():
    assert guard_fallback_text("", surface="practice") == "Practice details unavailable"
    result = guard_fallback_text("A" * 5000, surface="practice")
    assert len(result) == FALLBACK_TEXT_MAX
    assert result.endswith("…")


def test_named_source_is_logged_without_member_content(caplog):
    secret_member_text = "private workout detail " * 200
    with caplog.at_level(logging.WARNING):
        truncate_slack_text(
            secret_member_text,
            100,
            field="workout_description",
            surface="practice",
            practice_id=42,
        )
    assert "workout_description" in caplog.text
    assert "42" in caplog.text
    assert secret_member_text[:20] not in caplog.text
```

- [ ] **Step 2: Verify the tests fail because the module is missing**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q tests/slack/test_slack_text.py
```

Expected: collection fails with `ModuleNotFoundError: No module named 'app.slack.blocks.text'`.

- [ ] **Step 3: Implement immutable, field-aware guards**

Create `app/slack/blocks/text.py` with these boundaries:

```python
"""Slack Block Kit and notification-fallback text limits."""

from __future__ import annotations

import copy
import logging

logger = logging.getLogger(__name__)

HEADER_TEXT_MAX = 150
SECTION_TEXT_MAX = 3000
SECTION_FIELD_TEXT_MAX = 2000
CONTEXT_TEXT_MAX = 2000
FALLBACK_TEXT_MAX = 4000


def _guard_text_object(value, max_chars, field, surface, practice_id):
    if not isinstance(value, dict) or "text" not in value:
        return
    value["text"] = truncate_slack_text(
        value["text"],
        max_chars,
        field=field,
        surface=surface,
        practice_id=practice_id,
    )


def truncate_slack_text(text, max_chars, *, field, surface, practice_id=None):
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    logger.warning(
        "Truncated Slack %s on %s for practice #%s from %s to %s characters",
        field, surface, practice_id, len(value), max_chars,
    )
    return value[: max_chars - 1].rstrip() + "…"


def guard_slack_blocks(blocks, *, surface, practice_id=None):
    guarded = copy.deepcopy(blocks)
    for block in guarded:
        if block.get("type") == "header":
            _guard_text_object(block.get("text"), HEADER_TEXT_MAX, "header", surface, practice_id)
        elif block.get("type") == "section":
            _guard_text_object(block.get("text"), SECTION_TEXT_MAX, "section", surface, practice_id)
            for field in block.get("fields", []):
                _guard_text_object(
                    field, SECTION_FIELD_TEXT_MAX, "section field", surface, practice_id
                )
        elif block.get("type") == "context":
            for element in block.get("elements", []):
                if element.get("type") in {"mrkdwn", "plain_text"}:
                    _guard_text_object(element, CONTEXT_TEXT_MAX, "context", surface, practice_id)
    return guarded


def guard_fallback_text(text, *, surface, practice_id=None):
    value = str(text or "").strip() or "Practice details unavailable"
    return truncate_slack_text(
        value, FALLBACK_TEXT_MAX, field="fallback", surface=surface,
        practice_id=practice_id,
    )
```

Do not silently catch malformed blocks; these guards bound valid builder output, not replace schema validation.

- [ ] **Step 4: Re-export the guard functions**

Add the three public functions and five constants to `app/slack/blocks/__init__.py` so orchestrators do not import a private file path. The separate 2,000-character field cap follows Slack's current [section block contract](https://docs.slack.dev/reference/block-kit/blocks/section-block/).

- [ ] **Step 5: Run the focused tests**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q tests/slack/test_slack_text.py
```

Expected: all pass.

- [ ] **Step 6: Commit the safety primitive**

```bash
git add app/slack/blocks/text.py app/slack/blocks/__init__.py \
  tests/slack/test_slack_text.py
git commit -m "feat(slack): guard Block Kit text limits"
```

---

### Task 7: Gather one timezone-correct conditions snapshot

**Files:**

- Modify: `app/integrations/daylight.py`
- Modify: `app/practices/interfaces.py`
- Modify: `app/slack/practices/_config.py`
- Modify: `app/slack/practices/announcements.py`
- Create: `tests/integrations/test_daylight.py`
- Modify: `tests/slack/test_details_reply_wiring.py`

**Interfaces:**

- Adds immutable `AnnouncementConditions` to the practice contract.
- Changes `_gather_conditions(practice, *, weather=None, trail_conditions=None)` to return that object and never fetch an injected dependency again.

- [ ] **Step 1: Add the July local-calendar regression test**

Create the test package directory first with `mkdir -p tests/integrations`.

Create `tests/integrations/test_daylight.py` with a real Minneapolis location and a Central-time practice:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.integrations.daylight import get_daylight_info


def test_daylight_uses_the_practice_local_calendar_date():
    starts_at = datetime(2026, 7, 7, 18, 15)  # production stores naive Central
    daylight = get_daylight_info(
        lat=44.9778,
        lon=-93.2650,
        date=starts_at,
    )

    sunset_local = daylight.sunset.replace(tzinfo=ZoneInfo("UTC")).astimezone(
        ZoneInfo("America/Chicago")
    )
    assert sunset_local.date() == starts_at.date()
    assert sunset_local.hour == 21
    assert daylight.sunset.tzinfo is None
```

The current implementation should fail because Astral calculates the UTC calendar date; the exact signature remains `get_daylight_info(lat, lon, date)`.

- [ ] **Step 2: Add snapshot and dependency-injection tests**

Extend `tests/slack/test_details_reply_wiring.py` to assert:

```python
def test_gather_conditions_uses_injected_weather_without_refetch(
    self, monkeypatch, app_context
):
    from app.slack.practices.announcements import _gather_conditions

    practice = self._practice_with_coords()
    supplied = object()
    monkeypatch.setattr(
        "app.integrations.weather.get_weather_for_location",
        lambda *args, **kwargs: pytest.fail("weather was fetched twice"),
    )
    conditions = _gather_conditions(practice, weather=supplied)
    assert conditions.weather is supplied
    assert conditions.duration_minutes == 90


def test_gather_conditions_does_not_refetch_explicit_none(
    self, monkeypatch, app_context
):
    from app.slack.practices.announcements import _gather_conditions

    practice = self._practice_with_coords()
    monkeypatch.setattr(
        "app.integrations.weather.get_weather_for_location",
        lambda *args, **kwargs: pytest.fail("explicit None was refetched"),
    )
    assert _gather_conditions(practice, weather=None).weather is None


def test_gather_conditions_accepts_zero_coordinates(self, monkeypatch, app_context):
    from app.slack.practices.announcements import _gather_conditions

    practice = self._practice_with_coords(lat=0.0, lon=0.0)
    called = []
    monkeypatch.setattr(
        "app.integrations.weather.get_weather_for_location",
        lambda *args, **kwargs: called.append(args) or None,
    )
    _gather_conditions(practice)
    assert called
```

- [ ] **Step 3: Run the new tests and observe both regressions**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/integrations/test_daylight.py \
  tests/slack/test_details_reply_wiring.py
```

Expected: the July sunset assertion and new conditions contract fail.

- [ ] **Step 4: Fix Astral's timezone input without changing the stored contract**

In `app/integrations/daylight.py`, pass the `LocationInfo` timezone into Astral without changing the function signature:

```python
s = sun(
    location.observer,
    date=date.date(),
    tzinfo=location.timezone,
)
```

Convert the result back to the same naive-UTC shape currently stored in `DaylightInfo`, so existing consumers do not receive a surprise aware/naive contract change. Do not reuse `is_after_dark`; it checks dusk and assumes a different datetime shape.

- [ ] **Step 5: Define and populate the immutable snapshot**

Add to `app/practices/interfaces.py` immediately after `DaylightInfo`:

```python
@dataclass(frozen=True)
class AnnouncementConditions:
    weather: Optional[WeatherConditions] = None
    daylight: Optional[DaylightInfo] = None
    air_quality: Optional[int] = None
    trail_conditions: Optional[TrailCondition] = None
    duration_minutes: int = 90
```

Keep AQI as the integer already returned by `_gather_conditions()`; do not move the integration's `AirQualityInfo` type into shared practice contracts. Add this separate cache to `app/slack/practices/_config.py`:

```python
_practice_config_cache = None


def _load_practice_config():
    global _practice_config_cache
    if _practice_config_cache is None:
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "config", "practices.yaml"
        )
        with open(path, "r", encoding="utf-8") as handle:
            _practice_config_cache = yaml.safe_load(handle) or {}
    return _practice_config_cache


def get_default_duration_minutes():
    try:
        value = int(
            _load_practice_config()
            .get("practices", {})
            .get("default_duration_minutes", 90)
        )
        if value <= 0:
            raise ValueError("duration must be positive")
        return value
    except (TypeError, ValueError) as exc:
        current_app.logger.warning("Invalid practice duration; using 90 minutes: %s", exc)
        return 90
```

Update `reload_config()` to set both `_config_cache` and `_practice_config_cache` to `None` before returning `_load_config()`. Add a focused test that monkeypatches `_practice_config_cache` to `{"practices": {"default_duration_minutes": 105}}` and expects `105`, then to `{"practices": {"default_duration_minutes": 0}}` and expects/logs the fallback `90`.

Refactor `_gather_conditions()` to:

```python
_UNSET = object()


def _gather_conditions(practice, *, weather=_UNSET, trail_conditions=_UNSET):
    """Fetch each external condition at most once for one render."""
    has_coordinates = bool(
        practice.location
        and practice.location.latitude is not None
        and practice.location.longitude is not None
    )
    resolved_weather = None if weather is _UNSET else weather
    resolved_trails = None if trail_conditions is _UNSET else trail_conditions
    daylight = None
    aqi = None
    if has_coordinates:
        lat = practice.location.latitude
        lon = practice.location.longitude
        if weather is _UNSET:
            try:
                from app.integrations.weather import get_weather_for_location
                resolved_weather = get_weather_for_location(lat, lon, practice.date)
            except Exception as exc:
                current_app.logger.warning(
                    "weather fetch failed for practice #%s: %s", practice.id, exc
                )
        try:
            from app.integrations.daylight import get_daylight_info
            daylight = get_daylight_info(lat, lon, practice.date)
        except Exception as exc:
            current_app.logger.warning(
                "daylight fetch failed for practice #%s: %s", practice.id, exc
            )
        try:
            from app.integrations.air_quality import get_air_quality
            air_info = get_air_quality(lat, lon)
            aqi = air_info.aqi if air_info else None
        except Exception as exc:
            current_app.logger.warning(
                "AQI fetch failed for practice #%s: %s", practice.id, exc
            )
    return AnnouncementConditions(
        weather=resolved_weather,
        daylight=daylight,
        air_quality=aqi,
        trail_conditions=resolved_trails,
        duration_minutes=get_default_duration_minutes(),
    )
```

Keep provider failures fail-open and logged, as today. This task changes only collection and contracts; rendering changes in Task 8.

- [ ] **Step 6: Run the snapshot tests and related baseline**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/integrations/test_daylight.py \
  tests/slack/test_details_reply_wiring.py \
  tests/slack/test_announcement_blocks.py
```

Expected: all pass with existing block output unchanged.

- [ ] **Step 7: Commit the conditions boundary**

```bash
git add app/integrations/daylight.py app/practices/interfaces.py \
  app/slack/practices/_config.py app/slack/practices/announcements.py \
  tests/integrations/test_daylight.py tests/slack/test_details_reply_wiring.py
git commit -m "fix(slack): gather timezone-correct practice conditions"
```

---

### Task 8: Finalize standalone announcement and Details grammar

**Files:**

- Modify: `app/slack/blocks/announcements.py`
- Modify: `app/slack/blocks/__init__.py`
- Modify: `tests/slack/test_announcement_blocks.py`

**Interfaces:**

- `build_practice_announcement_blocks(practice, conditions, *, announcement_notice=None)`
- `build_practice_details_blocks(practice, conditions)`; an empty list means no Details reply should exist.
- `build_practice_fallback_text(practice, conditions, *, announcement_notice=None)`
- `build_practice_details_fallback_text(practice, conditions)`
- `_requires_headlamp(practice, daylight, duration_minutes)` compares practice end—not start—to local sunset.

- [ ] **Step 1: Replace the standalone block expectations with approved behavior**

Add focused tests before changing the builder:

```python
def test_summer_practice_ending_before_sunset_has_no_headlamp(practice_info, conditions):
    conditions = replace(
        conditions,
        daylight=daylight_for(practice_info.date, 20, 59),
    )
    text = rendered_text(build_practice_announcement_blocks(practice_info, conditions))
    assert "headlamp" not in text.lower()


def test_practice_ending_after_sunset_promotes_headlamp(practice_info, conditions):
    conditions = replace(
        conditions,
        daylight=daylight_for(practice_info.date, 16, 53),
    )
    text = rendered_text(build_practice_announcement_blocks(practice_info, conditions))
    assert "Headlamp required" in text


def test_explicit_dark_practice_requires_headlamp_without_daylight(practice_info, conditions):
    practice_info.is_dark_practice = True
    conditions = replace(conditions, daylight=None)
    assert "Headlamp required" in rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
```

Add three separate urgent-promotion tests using the same fixtures: an alert-bearing weather snapshot contains `Heat Advisory` in the hero; `air_quality=121` contains `Air quality 121`; and `announcement_notice="📍 Location changed"` contains that notice. For each case, assert the text appears before the location/workout section.

```python
def test_routine_conditions_stay_out_of_the_hero(practice_info, conditions):
    text = rendered_text(build_practice_announcement_blocks(practice_info, conditions))
    assert "Parking" not in text
    assert "Wind" not in text
    assert "Trail" not in text
    assert "No alerts" not in text


def test_empty_details_returns_no_blocks(practice_info, empty_conditions):
    assert build_practice_details_blocks(practice_info, empty_conditions) == []
```

Add exact grammar regressions that:

- clear `workout_description`, assert `Workout details coming soon.`, and walk adjacent block pairs to prove no two dividers touch;
- set the evergreen snapshot, assert `Bop ✅ if you're coming.`, `Your Practice Plan:`, and `:evergreen_tree: Endurance instead of intervals`, and assert `Optional:` is absent;
- use one coach and one lead fixture, assert both contexts remain after the Plan legend, and inspect block indexes to prove no divider sits between RSVP and Practice Plan.

Update the existing `_practice()` helper in this test file to include `id=42`, `status=PracticeStatus.SCHEDULED`, `is_dark_practice=False`, and `plan_reactions=[]`. Construct `conditions` as the real `AnnouncementConditions` dataclass so `dataclasses.replace()` is used only on that immutable snapshot, not on the existing `SimpleNamespace` practice fixture.

Replace the test file's fixed-December `_daylight()` helper with one that accepts the practice's Central date/time and desired Central sunset, attaches `ZoneInfo("America/Chicago")`, converts to UTC, and stores the result as naive UTC. This prevents a test fixture from recreating the production calendar-date bug.

```python
def daylight_for(practice_date, sunset_hour, sunset_minute):
    sunset_local = practice_date.replace(
        hour=sunset_hour,
        minute=sunset_minute,
        tzinfo=ZoneInfo("America/Chicago"),
    )
    sunset_utc = sunset_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return SimpleNamespace(
        sunset=sunset_utc,
        civil_twilight_end=sunset_utc + timedelta(hours=1),
    )
```

Also add cases for alert-fetch absence, AQI 100 versus 101, location/time notice placement, labels containing `&<>`, and a 4,000-character workout being truncated by the central guard.

- [ ] **Step 2: Run the standalone tests and capture the expected failures**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q tests/slack/test_announcement_blocks.py
```

Expected: new tests fail against the current tuple arguments, start-time headlamp rule, hard-coded evergreen copy, fixed dividers, and header-only Details output.

- [ ] **Step 3: Implement pure urgency and headlamp helpers**

In `app/slack/blocks/announcements.py`, add four fetch-free private helpers: `_practice_end(practice, duration_minutes)` returns the naive Central end datetime; `_sunset_local(daylight)` converts the stored naive UTC sunset to naive Central; `_requires_headlamp(practice, daylight, duration_minutes)` returns a boolean; and `_urgent_exception_lines(practice, conditions, announcement_notice=None)` returns the ordered member-facing lines.

Rules:

- Compare the calculated practice end against sunset in `America/Chicago`; current Practice/Daylight contracts are Central-time specific.
- `is_dark_practice=True` always requires a headlamp. Otherwise, return no inferred headlamp line when daylight data is absent; uncertainty is not a false warning.
- Treat an expected end exactly at sunset as requiring a headlamp.
- Promote active weather alert names, AQI `>= 101`, headlamp requirement, and an explicit `announcement_notice` only.
- An AQI value below 101 may appear in Details but not the hero.
- Never infer `No alerts` from `None` or an empty provider response.

Add `timedelta`, `AnnouncementConditions`, `format_plan_reaction_legend`, and the text-guard imports, then use these concrete helpers:

```python
from datetime import timedelta

from app.practices.interfaces import AnnouncementConditions
from app.practices.plan_reactions import format_plan_reaction_legend
from app.slack.blocks.text import (
    SECTION_TEXT_MAX,
    guard_fallback_text,
    guard_slack_blocks,
    truncate_slack_text,
)
```

```python
_SPACER = "\n\u200b"


def _join_block_groups(groups):
    blocks = []
    for group in groups:
        if not group:
            continue
        if blocks:
            blocks.append({"type": "divider"})
        blocks.extend(group)
    return blocks


def _practice_end(practice, duration_minutes):
    return practice.date + timedelta(minutes=duration_minutes)


def _sunset_local(daylight):
    sunset = getattr(daylight, "sunset", None) if daylight else None
    return utc_naive_to_central_naive(sunset) if sunset else None


def _requires_headlamp(practice, daylight, duration_minutes):
    if getattr(practice, "is_dark_practice", False):
        return True
    sunset_local = _sunset_local(daylight)
    return bool(
        sunset_local
        and _practice_end(practice, duration_minutes) >= sunset_local
    )


def _urgent_exception_lines(practice, conditions, announcement_notice=None):
    lines = []
    if announcement_notice:
        lines.append(announcement_notice)

    for alert in (getattr(conditions.weather, "alerts", None) or []):
        headline = getattr(alert, "headline", None) or getattr(alert, "event", None)
        if headline:
            lines.append(f"⚠️ {headline}")

    if conditions.air_quality is not None and conditions.air_quality >= 101:
        lines.append(f"🌫️ Air quality {conditions.air_quality}")

    if _requires_headlamp(
        practice, conditions.daylight, conditions.duration_minutes
    ):
        sunset_local = _sunset_local(conditions.daylight)
        lines.append(
            f"🔦 Headlamp required · Sunset {sunset_local.strftime('%-I:%M %p')}"
            if sunset_local else "🔦 Headlamp required"
        )
    return lines
```

- [ ] **Step 4: Build the hero from semantic groups**

Retain the current hierarchy, assembling three major groups and inserting dividers only between nonempty major groups:

1. Header, urgent exceptions when present, then time/location/address.
2. Workout or `Workout details coming soon.`, followed by Notes/Social when present.
3. One contiguous ending group: `Bop ✅ if you're coming.`, then `Your Practice Plan:` plus the escaped legend when configured, then the existing coach/lead context.

Within the ending group, separate RSVP and Practice Plan with a blank line, not a divider. Preserve the existing coach/lead mention logic and keep it after the member choices.

The RSVP sentence is exactly `Bop ✅ if you're coming.` Do not retain the old long interval legend, `Running late?` sentence, or root-level `<!channel>` mention in this ending; the generated Plan legend is the only supplemental choice copy.

Replace the public builder with this shape:

```python
def build_practice_announcement_blocks(
    practice,
    conditions: AnnouncementConditions,
    *,
    announcement_notice=None,
):
    header_group = [{
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": (
                f"{practice.date:%A} · {_activity_label(practice.activities)} at "
                f"{practice.date.strftime('%-I:%M %p')}"
            ),
            "emoji": True,
        },
    }]

    urgent = _urgent_exception_lines(
        practice, conditions, announcement_notice=announcement_notice
    )
    if urgent:
        header_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(urgent) + _SPACER},
        })

    location_name = practice.location.name if practice.location else "TBD"
    spot = (
        practice.location.spot
        if practice.location and practice.location.spot else None
    )
    where_text = f"*Where:* {location_name + (' - ' + spot if spot else '')}"
    address = _address_link(practice.location) if practice.location else None
    if address:
        where_text += f"\n📍 {address}"
    header_group.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": where_text + _SPACER},
    })

    type_names = ", ".join(
        item.name for item in (practice.practice_types or [])
    )
    workout_label = f"*Workout · {type_names}*" if type_names else "*Workout*"
    workout_prefix = f"{workout_label}\n"
    workout = (
        str(practice.workout_description).strip()
        if getattr(practice, "workout_description", None)
        else "Workout details coming soon."
    )
    workout = truncate_slack_text(
        workout,
        SECTION_TEXT_MAX - len(workout_prefix) - len(_SPACER),
        field="workout_description",
        surface="practice_announcement",
        practice_id=practice.id,
    )
    workout_group = [{
        "type": "section",
        "text": {"type": "mrkdwn", "text": workout_prefix + workout + _SPACER},
    }]

    if getattr(practice, "logistics_notes", None):
        notes_prefix = "*📌 Notes*\n"
        notes = truncate_slack_text(
            practice.logistics_notes,
            SECTION_TEXT_MAX - len(notes_prefix) - len(_SPACER),
            field="logistics_notes",
            surface="practice_announcement",
            practice_id=practice.id,
        )
        workout_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": notes_prefix + notes + _SPACER},
        })

    if practice.has_social:
        social = getattr(practice, "social_location", None)
        social_text = (
            f"🍹 *Social after at {social.name}*"
            if social and getattr(social, "name", None)
            else "🍹 *Social after!*"
        )
        workout_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": social_text + _SPACER},
        })

    rsvp_lines = ["Bop ✅ if you're coming."]
    if getattr(practice, "plan_reactions", None):
        rsvp_lines.extend([
            "",
            "*Your Practice Plan:*",
            format_plan_reaction_legend(practice.plan_reactions),
        ])
    ending_group = [{
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "\n".join(rsvp_lines)}],
    }]

    coaches, leads = [], []
    for lead in (practice.leads or []):
        mention = (
            f"<@{lead.slack_user_id}>"
            if lead.slack_user_id else lead.display_name or "Unknown"
        )
        role_name = getattr(lead.role, "name", str(lead.role)).upper()
        if role_name == "COACH":
            coaches.append(mention)
        elif role_name in {"LEAD", "ASSIST"}:
            leads.append(mention)
    lead_parts = []
    if coaches:
        lead_parts.append(f"👨‍🏫 Coach {', '.join(coaches)}")
    if leads:
        lead_parts.append(f"🧑‍🤝‍🧑 Leads {', '.join(leads)}")
    if lead_parts:
        ending_group.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": " · ".join(lead_parts)}],
        })

    return guard_slack_blocks(
        _join_block_groups([header_group, workout_group, ending_group]),
        surface="practice_announcement",
        practice_id=practice.id,
    )
```

Use `format_plan_reaction_legend()` for the Plan line and return `guard_slack_blocks(blocks, surface="practice_announcement", practice_id=practice.id)` at the public boundary. Remove the `has_intervals`/evergreen special case entirely.

Before adding `workout_description` or `logistics_notes` to a labeled section, call `truncate_slack_text()` with enough room for that label and pass the exact source field name. The final structural guard remains the last defense. This makes truncation logs identify the actionable database field without logging member content.

- [ ] **Step 5: Make Details genuinely conditional**

`build_practice_details_blocks()` should include only available routine information: forecast/temperature/wind, neutral sunset time, AQI 50–100, parking, gear, and trail conditions. Return `[]` if every section is empty. Add the `Practice Details` header only after at least one detail exists, then guard the final blocks.

Do not duplicate active alert or headlamp lines in Details. Do not emit `No alerts` anywhere.

Use one normalized helper for both blocks and fallback:

```python
def _details_content(practice, conditions):
    parking = practice.location.parking_notes if practice.location else None
    gear = _gear_list(practice)
    block_conditions = []
    plain_conditions = []

    weather = conditions.weather
    if weather:
        temperature = f"🌡️ {weather.temperature_f:.0f}°F"
        feels_like = getattr(weather, "feels_like_f", None)
        if feels_like is not None and abs(feels_like - weather.temperature_f) > 3:
            temperature += f" (feels {feels_like:.0f}°)"
        if getattr(weather, "conditions_summary", None):
            temperature += f", {weather.conditions_summary}"
        block_conditions.append(temperature)
        plain_conditions.append(temperature)

        if getattr(weather, "wind_speed_mph", None):
            direction = getattr(weather, "wind_direction", None)
            wind = (
                f"💨 Wind {direction + ' ' if direction else ''}"
                f"{weather.wind_speed_mph:.0f} mph"
            )
            block_conditions.append(wind)
            plain_conditions.append(wind)

    sunset_local = _sunset_local(conditions.daylight)
    if sunset_local:
        sunset = f"☀️ Sunset {sunset_local.strftime('%-I:%M %p')}"
        block_conditions.append(sunset)
        plain_conditions.append(sunset)

    if conditions.air_quality is not None and 50 <= conditions.air_quality <= 100:
        air = f"🌫️ AQI {conditions.air_quality}"
        block_conditions.append(air)
        plain_conditions.append(air)

    trail = conditions.trail_conditions
    if trail:
        trail_block = f"🎿 Trails: {trail.ski_quality.replace('_', ' ').title()}"
        trail_plain = trail_block
        if trail.groomed:
            trail_block += ", Groomed"
            trail_plain += ", Groomed"
        if getattr(trail, "report_url", None):
            trail_block += f" · <{trail.report_url}|Trail report>"
            trail_plain += f" · Trail report: {trail.report_url}"
        block_conditions.append(trail_block)
        plain_conditions.append(trail_plain)

    return {
        "parking": parking,
        "gear": gear,
        "block_conditions": block_conditions,
        "plain_conditions": plain_conditions,
    }


def build_practice_details_blocks(practice, conditions):
    content = _details_content(practice, conditions)
    sections = []
    logistics = []
    if content["parking"]:
        logistics.append(f"*Parking*\n{content['parking']}")
    if content["gear"]:
        logistics.append(f"*Gear*\n{', '.join(content['gear'])}")
    if logistics:
        sections.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n\n".join(logistics)},
        })
    if content["block_conditions"]:
        sections.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Conditions*\n" + "\n".join(content["block_conditions"]),
            },
        })
    if not sections:
        return []

    blocks = [{
        "type": "header",
        "text": {"type": "plain_text", "text": "Practice Details", "emoji": True},
    }]
    for index, section in enumerate(sections):
        if index:
            blocks.append({"type": "divider"})
        blocks.append(section)
    return guard_slack_blocks(
        blocks, surface="practice_details", practice_id=practice.id
    )
```

- [ ] **Step 6: Add complete standalone fallback text**

`build_practice_fallback_text()` must cover, in plain scannable lines:

- status/date;
- start time and location;
- workout or placeholder;
- urgent exceptions and `announcement_notice`;
- RSVP instruction;
- Plan-reaction choices.

It intentionally omits routine thread-only details. End with `guard_fallback_text(fallback, surface="practice_announcement", practice_id=practice.id)`.

Build `build_practice_details_fallback_text()` from the same normalized parking/gear/conditions data as the Details blocks. Start with the practice date, include only rendered values, replace Slack links with their plain URL, and return the guarded fallback. Re-export both fallback builders from `app/slack/blocks/__init__.py` in this task.

```python
def build_practice_fallback_text(
    practice,
    conditions,
    *,
    announcement_notice=None,
):
    location = practice.location.name if practice.location else "TBD"
    workout = (
        str(practice.workout_description).strip()
        if getattr(practice, "workout_description", None)
        else "Workout details coming soon."
    )
    workout = truncate_slack_text(
        workout,
        2500,
        field="workout_description",
        surface="practice_fallback",
        practice_id=practice.id,
    )
    parts = [
        (
            f"{practice.date.strftime('%A, %B %-d')} at "
            f"{practice.date.strftime('%-I:%M %p')} at {location}."
        ),
        f"Workout: {workout}",
    ]
    urgent = _urgent_exception_lines(
        practice, conditions, announcement_notice=announcement_notice
    )
    if urgent:
        parts.append(" ".join(urgent))
    parts.append("RSVP with ✅.")
    if getattr(practice, "plan_reactions", None):
        parts.append(
            "Your Practice Plan: "
            + format_plan_reaction_legend(practice.plan_reactions)
            + "."
        )
    fallback = " ".join(parts)
    return guard_fallback_text(
        fallback,
        surface="practice_announcement",
        practice_id=practice.id,
    )


def build_practice_details_fallback_text(practice, conditions):
    content = _details_content(practice, conditions)
    parts = [f"Practice details for {practice.date.strftime('%A, %B %-d')}."]
    if content["parking"]:
        parts.append(f"Parking: {content['parking']}.")
    if content["gear"]:
        parts.append(f"Gear: {', '.join(content['gear'])}.")
    if content["plain_conditions"]:
        parts.append("Conditions: " + " ".join(content["plain_conditions"]) + ".")
    return guard_fallback_text(
        " ".join(parts),
        surface="practice_details",
        practice_id=practice.id,
    )
```

- [ ] **Step 7: Run focused block tests**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/practices/test_plan_reactions.py \
  tests/slack/test_slack_text.py \
  tests/slack/test_announcement_blocks.py
```

Expected: all pass.

- [ ] **Step 8: Commit the standalone grammar**

```bash
git add app/slack/blocks/announcements.py app/slack/blocks/__init__.py \
  tests/slack/test_announcement_blocks.py
git commit -m "feat(slack): finalize standalone practice blocks"
```

---

### Task 9: Wire complete fallbacks, Details cleanup, and reaction seeds

**Files:**

- Modify: `app/slack/practices/announcements.py`
- Modify: `app/slack/practices/refresh.py`
- Modify: `app/routes/admin_practices.py`
- Modify: `app/slack/bolt_app.py`
- Modify: `app/scheduler.py`
- Modify: `tests/slack/test_details_reply_wiring.py`
- Modify: `tests/slack/test_refresh.py`
- Modify: `tests/routes/test_admin_practice_plan_reactions.py`
- Create: `tests/test_scheduler_practice_announcements.py`

**Interfaces:**

- `post_practice_announcement()` and every update gather one `AnnouncementConditions` and use the same object for hero, fallback, and Details.
- `_upsert_details_reply(client, practice, practice_info, conditions)` deletes a stale reply when the rebuilt Details list is empty.
- Consumes `build_practice_details_fallback_text(practice, conditions)` from Task 8 for every Details Slack write.
- `refresh_practice_posts(practice, change_type="edit", actor_slack_id=None, notify=True, announcement_notice=None, previous_plan_reactions=None)` carries ephemeral change context without persisting it.

- [ ] **Step 1: Add orchestration regressions**

Write tests for these observable behaviors using the existing `_make_practice`, fake client, and patch helpers in `test_details_reply_wiring.py`:

- initial post calls `_gather_conditions` exactly once, passes the identical object to hero/fallback/Details builders, and sends the complete expected fallback;
- both `update_practice_announcement()` and `update_practice_post()` use that same complete expected fallback rather than `Practice on ...`;
- empty rebuilt Details with `slack_details_ts="222.333"` calls `chat_delete(channel="CTEST", ts="222.333")`, clears the field, and commits once;
- the same delete raising `SlackApiError` keeps `slack_details_ts="222.333"` and does not commit the clear;
- changing `old_choice` to `new_choice` calls `reactions_remove(channel="CTEST", timestamp="1234.5678", name="old_choice")` and the parallel `reactions_add` call for `new_choice`;
- a date or location change passes one temporary hero notice, while a workout-only edit passes `None`;
- a time/location edit posts exactly one root-thread safety note even with `notify=False`;
- the scheduler calls `post_practice_announcement` with the same `practice` and `channel_override` it received, without fetching weather first.

- [ ] **Step 2: Run the wiring tests and verify current failures**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_details_reply_wiring.py \
  tests/slack/test_refresh.py \
  tests/routes/test_admin_practice_plan_reactions.py \
  tests/test_scheduler_practice_announcements.py
```

- [ ] **Step 3: Gather once on every standalone post/update path**

Collapse `update_practice_announcement()`, `update_practice_post()`, and their smart dispatcher onto one implementation that:

```python
def _conditions_for_render(practice, weather=None, trail_conditions=None):
    overrides = {}
    if weather is not None:
        overrides["weather"] = weather
    if trail_conditions is not None:
        overrides["trail_conditions"] = trail_conditions
    return _gather_conditions(practice, **overrides)


conditions = _conditions_for_render(
    practice, weather=weather, trail_conditions=trail_conditions
)
practice_info = convert_practice_to_info(practice)
blocks = build_practice_announcement_blocks(
    practice_info, conditions, announcement_notice=announcement_notice,
)
fallback = build_practice_fallback_text(
    practice_info, conditions, announcement_notice=announcement_notice,
)
```

Pass the same `conditions` to `_upsert_details_reply()`. Remove the scheduler's prefetch of weather/trails before calling `post_practice_announcement()` so the provider is called in only one layer.

The adapter is intentional: public posting functions already use `None` as their default for “not supplied,” so they must omit that argument and allow `_gather_conditions` to fetch. Direct callers/tests may still pass explicit `None` to `_gather_conditions` to mean “lookup already attempted and unavailable.”

Initial posting uses the complete fallback, then saves the root before best-effort secondary work:

```python
response = client.chat_postMessage(
    channel=channel_id,
    blocks=blocks,
    text=fallback,
    unfurl_links=False,
    unfurl_media=False,
)
practice.slack_channel_id = channel_id
practice.slack_message_ts = response["ts"]
db.session.commit()
details_result = _upsert_details_reply(
    client, practice, practice_info, conditions
)
_seed_plan_reactions(client, practice)
```

Collapse standalone updates onto this function:

```python
def update_practice_announcement(
    practice,
    weather=None,
    trail_conditions=None,
    *,
    announcement_notice=None,
    previous_plan_reactions=None,
):
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {"success": False, "error": "No Slack message to update"}

    client = get_slack_client()
    conditions = _conditions_for_render(
        practice, weather=weather, trail_conditions=trail_conditions
    )
    practice_info = convert_practice_to_info(practice)
    blocks = build_practice_announcement_blocks(
        practice_info,
        conditions,
        announcement_notice=announcement_notice,
    )
    fallback = build_practice_fallback_text(
        practice_info,
        conditions,
        announcement_notice=announcement_notice,
    )
    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=fallback,
        )
        _reconcile_plan_reactions(
            client,
            practice,
            previous_plan_reactions=previous_plan_reactions,
        )
        details_result = _upsert_details_reply(
            client, practice, practice_info, conditions
        )
        return {"success": True, "details": details_result}
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        current_app.logger.error(
            "Error updating practice announcement: %s", error
        )
        return {"success": False, "error": error}


def update_practice_post(
    practice,
    *,
    announcement_notice=None,
    previous_plan_reactions=None,
):
    return update_practice_announcement(
        practice,
        announcement_notice=announcement_notice,
        previous_plan_reactions=previous_plan_reactions,
    )
```

Update the smart dispatcher without changing the combined call until Task 11:

```python
def update_practice_slack_post(
    practice,
    *,
    announcement_notice=None,
    previous_plan_reactions=None,
):
    if not practice.slack_message_ts:
        return {"success": False, "error": "No Slack post to update"}
    if is_combined_lift_practice(practice):
        return update_combined_lift_post(practice)
    return update_practice_post(
        practice,
        announcement_notice=announcement_notice,
        previous_plan_reactions=previous_plan_reactions,
    )
```

- [ ] **Step 4: Implement the empty Details lifecycle**

In `_upsert_details_reply()`:

- nonempty blocks + no timestamp: `chat_postMessage` in the root thread and persist its timestamp;
- nonempty blocks + timestamp: `chat_update` with a complete Details fallback;
- empty blocks + timestamp: `chat_delete`, then clear and commit the timestamp only after Slack succeeds;
- empty blocks + no timestamp: return a successful no-op;
- on Slack failure, retain the timestamp and return/log the failure so the next refresh can retry.

Use Task 8's `build_practice_details_fallback_text()` for create and update; it enumerates available labels/values instead of saying only `Practice details`.

```python
def _upsert_details_reply(client, practice, practice_info, conditions):
    original_ts = practice.slack_details_ts
    try:
        blocks = build_practice_details_blocks(practice_info, conditions)
        if not blocks:
            if not original_ts:
                return {"success": True, "skipped": "no_details"}
            client.chat_delete(
                channel=practice.slack_channel_id,
                ts=original_ts,
            )
            practice.slack_details_ts = None
            db.session.commit()
            return {"success": True, "deleted": True}

        fallback = build_practice_details_fallback_text(
            practice_info, conditions
        )
        if original_ts:
            client.chat_update(
                channel=practice.slack_channel_id,
                ts=original_ts,
                blocks=blocks,
                text=fallback,
            )
            return {"success": True, "updated": True}

        reply = client.chat_postMessage(
            channel=practice.slack_channel_id,
            thread_ts=practice.slack_message_ts,
            blocks=blocks,
            text=fallback,
            reply_broadcast=False,
            unfurl_links=False,
            unfurl_media=False,
        )
        details_ts = reply.get("ts")
        if not details_ts:
            return {
                "success": False,
                "error": "Slack did not return a Details timestamp",
            }
        practice.slack_details_ts = details_ts
        db.session.commit()
        return {"success": True, "message_ts": details_ts}
    except Exception as exc:
        practice.slack_details_ts = original_ts
        current_app.logger.warning(
            "Could not sync practice Details reply for #%s: %s",
            practice.id,
            exc,
        )
        return {"success": False, "error": str(exc)}
```

- [ ] **Step 5: Seed and reconcile supplemental reactions**

Import `plan_reaction_names` from `app.practices.plan_reactions`, then add `_seed_plan_reactions(client, practice)` and `_reconcile_plan_reactions(client, practice, *, previous_plan_reactions)` as private orchestration helpers.

```python
def _reaction_error_name(exc):
    response = getattr(exc, "response", None)
    return response.get("error") if response else None


def _seed_plan_reactions(client, practice):
    names = ["white_check_mark"] + plan_reaction_names(
        practice.plan_reactions or []
    )
    for name in names:
        try:
            client.reactions_add(
                channel=practice.slack_channel_id,
                timestamp=practice.slack_message_ts,
                name=name,
            )
        except Exception as exc:
            if _reaction_error_name(exc) != "already_reacted":
                current_app.logger.warning(
                    "Could not seed :%s: on practice #%s: %s",
                    name,
                    practice.id,
                    exc,
                )


def _reconcile_plan_reactions(
    client,
    practice,
    *,
    previous_plan_reactions=None,
):
    previous = set(plan_reaction_names(previous_plan_reactions or []))
    current = set(plan_reaction_names(practice.plan_reactions or []))
    for name in sorted(previous - current):
        try:
            client.reactions_remove(
                channel=practice.slack_channel_id,
                timestamp=practice.slack_message_ts,
                name=name,
            )
        except Exception as exc:
            if _reaction_error_name(exc) != "no_reaction":
                current_app.logger.warning(
                    "Could not remove :%s: from practice #%s: %s",
                    name,
                    practice.id,
                    exc,
                )
    for name in sorted(current - previous):
        try:
            client.reactions_add(
                channel=practice.slack_channel_id,
                timestamp=practice.slack_message_ts,
                name=name,
            )
        except Exception as exc:
            if _reaction_error_name(exc) != "already_reacted":
                current_app.logger.warning(
                    "Could not add :%s: to practice #%s: %s",
                    name,
                    practice.id,
                    exc,
                )
```

After a successful initial root post, add every configured Plan emoji plus the standalone `white_check_mark`. For updates, diff emoji names from the explicit previous snapshot, remove bot-owned obsolete seeds, and add missing new seeds. Treat `already_reacted` and `no_reaction` as idempotent success; log other failures without rolling back the database edit or successful message update.

- [ ] **Step 6: Pass temporary change context from the authoring surfaces**

Add `build_announcement_change_notice()` to `app/slack/practices/announcements.py`. Before applying an admin edit, retain the previous start datetime, location ID, and Plan snapshot. After commit:

```python
def build_announcement_change_notice(*, previous_date, previous_location_id, practice):
    time_changed = previous_date != practice.date
    location_changed = previous_location_id != practice.location_id
    if time_changed and location_changed:
        return "🕒 Date/time and location updated, check the heading and Where below."
    if time_changed:
        return "🕒 Date or time updated, check the heading above."
    if location_changed:
        return "📍 Location updated, check Where below."
    return None


announcement_notice = build_announcement_change_notice(
    previous_date=previous_date,
    previous_location_id=previous_location_id,
    practice=practice,
)
refresh_practice_posts(
    practice,
    change_type="edit",
    announcement_notice=announcement_notice,
    previous_plan_reactions=previous_plan_reactions,
)
```

Use the same change-context call from the active full Slack edit handler. The notice copy should be one concise line describing only changed time/location and exists for this refresh only; do not persist it on `Practice`. Do not put Plan reactions into the legacy small workout-entry modal.

After a successful root refresh, post that same safety notice once in the announcement thread even when the general `notify` checkbox is false or the web edit has no Slack actor. When a safety note is posted, skip the generic announcement-thread edit log to avoid duplicate member notifications; coach-summary and collab logs may still follow their existing `notify` behavior.

- [ ] **Step 7: Extend refresh context without breaking surfaces**

Add a small immutable refresh context or keyword arguments to `PracticeSurface.refresh()` and `refresh_practice_posts()`. The announcement surface consumes `announcement_notice` and `previous_plan_reactions`; the post-pass uses `announcement_notice` for the one thread safety note; other surfaces ignore them. Keep existing call sites valid through keyword defaults.

```python
def refresh(self, practice, change_type, **context):
    if not self.is_present(practice):
        return {"skipped": "absent"}
    if change_type not in self.applies_to:
        return {"skipped": "not_applicable"}
    return self._refresh_fn(practice, change_type, **context)


def refresh_practice_posts(
    practice,
    change_type="edit",
    actor_slack_id=None,
    notify=True,
    announcement_notice=None,
    previous_plan_reactions=None,
):
    context = {
        "announcement_notice": announcement_notice,
        "previous_plan_reactions": previous_plan_reactions,
    }
    results = {
        surface.name: surface.refresh(practice, change_type, **context)
        for surface in PRACTICE_SURFACES
    }

    safety_note_posted = False
    announcement_result = results.get("announcement", {})
    if (
        announcement_notice
        and announcement_result.get("success") is True
        and practice.slack_message_ts
        and practice.slack_channel_id
    ):
        from app.slack.practices.rsvp import post_thread_reply
        note_result = post_thread_reply(
            practice,
            announcement_notice,
            user_mention=actor_slack_id,
        )
        results["announcement_change_note"] = note_result
        safety_note_posted = note_result.get("success") is True

    if notify and actor_slack_id and change_type in {"edit", "workout"}:
        results["edit_logs"] = _post_edit_logs(
            practice,
            actor_slack_id,
            skip_announcement=safety_note_posted,
        )
    _log_refresh_results(practice, change_type, results)
    return results
```

Change `_refresh_announcement` to accept the two named keywords plus `**_context` and forward them only on the edit/workout/create branch:

```python
return update_practice_slack_post(
    practice,
    announcement_notice=announcement_notice,
    previous_plan_reactions=previous_plan_reactions,
)
```

Add `**_context` to `_refresh_collab`, `_refresh_coach_summary`, and `_refresh_weekly_summary`. Change `_post_edit_logs(practice, actor_slack_id, *, skip_announcement=False)` and guard its announcement-log block with `if practice.slack_message_ts and not skip_announcement:`; leave coach-summary and collab logging unchanged.

- [ ] **Step 8: Run focused orchestration tests**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_announcement_blocks.py \
  tests/slack/test_details_reply_wiring.py \
  tests/slack/test_refresh.py \
  tests/routes/test_admin_practice_plan_reactions.py \
  tests/test_scheduler_practice_announcements.py
```

Expected: all pass.

- [ ] **Step 9: Commit the standalone orchestration**

```bash
git add app/slack/practices/announcements.py app/slack/practices/refresh.py \
  app/routes/admin_practices.py app/slack/bolt_app.py app/scheduler.py \
  tests/slack/test_details_reply_wiring.py tests/slack/test_refresh.py \
  tests/routes/test_admin_practice_plan_reactions.py \
  tests/test_scheduler_practice_announcements.py
git commit -m "feat(slack): keep practice posts and details in sync"
```

---

### Task 10: Make attendance reaction handling explicit and reversible

**Files:**

- Create: `app/slack/practices/reactions.py`
- Modify: `app/slack/bolt_app.py`
- Modify: `app/slack/practices/rsvp.py`
- Modify: `app/slack/practices/__init__.py`
- Create: `tests/slack/test_reaction_rsvp.py`
- Modify: `tests/slack/test_refresh.py`

**Interfaces:**

- `handle_attendance_reaction(*, channel, message_ts, reaction, slack_user_id, removed=False)` owns routing and persistence.
- Bolt's `reaction_added` and `reaction_removed` listeners validate the event envelope and delegate only.
- `update_practice_rsvp_counts()` updates a legacy count block only when one exists; otherwise native Slack reactions are the visible count.

- [ ] **Step 1: Write failing reaction-routing tests**

Create `tests/slack/test_reaction_rsvp.py` with database-backed cases that assert:

- `white_check_mark` on one standalone root creates one `going` RSVP for the linked user;
- removing that reaction deletes the matching `going` RSVP;
- each of `evergreen_tree`, `athletic_shoe`, `question`, `thumbsup`, and `x` returns `ignored="not_attendance"` and leaves the RSVP table unchanged;
- `six` routes only to the combined practice whose saved value is `six`, not its `seven` sibling;
- the other session emoji and every Plan emoji are ignored for the wrong practice;
- cancelled practices, a same-timestamp practice in another channel, and an unlinked Slack user produce no write.

For removal, create a `going` RSVP for the same linked user and assert it is deleted. Also test that removal leaves a non-going RSVP untouched; a reaction event may only reverse the exact `going` state it created.

- [ ] **Step 2: Add the legacy-root no-op regression**

Extend the RSVP tests with two mocked-history cases. A modern root without the legacy going-count context returns `{"success": True, "skipped": "no_legacy_count_block"}` and never calls `chat_update`. A root containing that legacy context updates the count block and passes through the exact existing top-level text `Complete accessible fallback`.

- [ ] **Step 3: Run the tests and confirm current broad mappings fail**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_reaction_rsvp.py \
  tests/slack/test_refresh.py
```

Expected: the new module is missing, removal is unhandled, and current broad emoji mappings incorrectly write RSVPs.

- [ ] **Step 4: Implement narrow routing in a dedicated module**

Create `app/slack/practices/reactions.py`. Query candidates with both keys:

```python
siblings = Practice.query.filter_by(
    slack_channel_id=channel,
    slack_message_ts=message_ts,
).order_by(Practice.date, Practice.id).all()
```

Select the practice using these rules only:

- standalone lifecycle (`slack_session_emoji is None` and one sibling): reaction must be `white_check_mark`;
- combined lifecycle: reaction must exactly equal one practice's persisted `slack_session_emoji`;
- cancelled practice: ignore;
- Plan reaction, legacy thumbs-up/maybe/no emoji, or unmatched emoji: ignore before the user lookup and before any write.

On add, create or update one `PracticeRSVP(status="going")`. On remove, delete only a matching existing `going` RSVP. Resolve the user through the current Slack-account join. Commit once, then call only the legacy root-count updater best-effort. Do not call `update_going_list_thread()`: one generic thread per shared root cannot represent two combined sessions safely. Return structured results such as `{"success": True, "ignored": "not_attendance"}` for testability.

Until Task 11 introduces persisted lazy assignment for pre-migration combined roots, preserve the current inferred routing only when there are multiple scoped siblings and every `slack_session_emoji` is blank. Task 11 replaces that compatibility bridge with one-time persistence; never infer a one-survivor combined mapping.

Implement the module with this core:

```python
import logging
from datetime import datetime

from app.models import User, db
from app.practices.interfaces import PracticeStatus, RSVPStatus
from app.practices.models import Practice, PracticeRSVP

logger = logging.getLogger(__name__)


def _select_attendance_practice(siblings, reaction):
    if len(siblings) == 1 and not siblings[0].slack_session_emoji:
        return siblings[0] if reaction == "white_check_mark" else None
    persisted = {
        practice.slack_session_emoji: practice
        for practice in siblings
        if practice.slack_session_emoji
    }
    if persisted:
        return persisted.get(reaction)
    if len(siblings) > 1:
        from app.slack.client import get_combined_practice_emojis
        inferred = get_combined_practice_emojis(siblings)
        return dict(zip(inferred, siblings)).get(reaction)
    return None


def handle_attendance_reaction(
    *, channel, message_ts, reaction, slack_user_id, removed=False
):
    if not all((channel, message_ts, reaction, slack_user_id)):
        return {"success": True, "ignored": "invalid_event"}

    siblings = Practice.query.filter_by(
        slack_channel_id=channel,
        slack_message_ts=message_ts,
    ).order_by(Practice.date, Practice.id).all()
    if not siblings:
        return {"success": True, "ignored": "message_not_linked"}

    practice = _select_attendance_practice(siblings, reaction)
    if practice is None:
        return {"success": True, "ignored": "not_attendance"}
    if practice.status == PracticeStatus.CANCELLED.value:
        return {"success": True, "ignored": "cancelled"}

    user = (
        User.query.join(User.slack_user)
        .filter_by(slack_uid=slack_user_id)
        .first()
    )
    if user is None:
        return {"success": True, "ignored": "unlinked_user"}

    rsvp = PracticeRSVP.query.filter_by(
        practice_id=practice.id,
        user_id=user.id,
    ).first()
    if removed:
        if rsvp is None or rsvp.status != RSVPStatus.GOING.value:
            return {"success": True, "ignored": "no_matching_going_rsvp"}
        db.session.delete(rsvp)
        action = "removed"
    else:
        if rsvp is None:
            rsvp = PracticeRSVP(
                practice_id=practice.id,
                user_id=user.id,
                slack_user_id=slack_user_id,
            )
            db.session.add(rsvp)
        rsvp.status = RSVPStatus.GOING.value
        rsvp.slack_user_id = slack_user_id
        rsvp.responded_at = datetime.utcnow()
        action = "upserted"

    db.session.commit()
    try:
        from app.slack.practices.rsvp import update_practice_rsvp_counts
        update_practice_rsvp_counts(practice)
    except Exception:
        logger.warning(
            "Attendance saved but legacy count refresh failed for practice #%s",
            practice.id,
            exc_info=True,
        )
    return {"success": True, "action": action, "practice_id": practice.id}
```

- [ ] **Step 5: Make both Bolt event handlers thin**

Replace the large `reaction_added` map with:

```python
def _delegate_reaction(event, *, removed):
    item = event.get("item", {})
    if item.get("type") != "message":
        return
    with get_app_context():
        handle_attendance_reaction(
            channel=item.get("channel"),
            message_ts=item.get("ts"),
            reaction=event.get("reaction"),
            slack_user_id=event.get("user"),
            removed=removed,
        )


@bolt_app.event("reaction_added")
def handle_reaction_added(event, logger):
    _delegate_reaction(event, removed=False)


@bolt_app.event("reaction_removed")
def handle_reaction_removed(event, logger):
    _delegate_reaction(event, removed=True)
```

Delete `_process_reaction_rsvp()` after its covered behavior lives in the new module. Do not use Plan labels or JSON to decide attendance.

- [ ] **Step 6: Stop modern reaction events from rewriting fallback text**

In `update_practice_rsvp_counts()`, locate the existing legacy going-count context block first. If absent, return the successful skip without `chat_update`. If present, update it and pass through `messages[0]["text"]`; never replace it with the former generic date-only fallback.

```python
if going_context_idx is None:
    return {"success": True, "skipped": "no_legacy_count_block"}

client.chat_update(
    channel=practice.slack_channel_id,
    ts=practice.slack_message_ts,
    blocks=current_blocks,
    text=messages[0].get("text") or "Practice details unavailable",
)
```

- [ ] **Step 7: Run the focused reaction suite**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_reaction_rsvp.py \
  tests/slack/test_refresh.py
```

Expected: all pass.

- [ ] **Step 8: Commit the reaction lifecycle**

```bash
git add app/slack/practices/reactions.py app/slack/practices/__init__.py \
  app/slack/practices/rsvp.py app/slack/bolt_app.py \
  tests/slack/test_reaction_rsvp.py tests/slack/test_refresh.py
git commit -m "fix(slack): make reaction attendance reversible"
```

---

### Task 11: Finish compatible combined Strength announcements

**Files:**

- Modify: `app/slack/client.py`
- Modify: `app/slack/blocks/announcements.py`
- Modify: `app/slack/blocks/__init__.py`
- Modify: `app/slack/practices/announcements.py`
- Modify: `app/slack/practices/reactions.py`
- Modify: `app/scheduler.py`
- Create: `tests/slack/test_combined_announcements.py`
- Modify: `tests/test_scheduler_practice_announcements.py`
- Modify: `tests/slack/test_details_reply_wiring.py`

**Interfaces:**

- `combined_compatibility_key(practice)` groups only sessions whose member-facing shared content is identical.
- `group_strength_announcements(practices)` returns combined groups of two or three; every other practice remains standalone.
- `assign_combined_session_emojis(practices)` persists a stable, unique emoji on every combined practice.
- `get_announcement_siblings(practice, *, exclude_practice_id=None)` always scopes by channel and timestamp.
- `update_combined_lift_post(practice, *, exclude_practice_id=None, previous_plan_reactions=None)` preserves the combined grammar even with one survivor and reconciles the bot's shared Plan seeds.

- [ ] **Step 1: Write compatibility and grouping tests**

In `tests/test_scheduler_practice_announcements.py`, assert two compatible Strength sessions produce one combined call; changing location, workout, Notes, social destination/state, or an ordered Plan pair separates them; Strength detected through either Activity or Workout Type follows the same path; one session posts standalone; four compatible sessions each post standalone; and two independent compatible pairs produce two combined calls with no repeated practice ID.

The compatibility key contains exactly:

- `location_id`;
- normalized workout description, logistics notes, and social destination/state;
- sorted Activity IDs/names and Workout Type IDs/names;
- ordered `(emoji, label)` Plan-reaction pairs.

Do not include date/time; those are the intentional differences between sessions.

- [ ] **Step 2: Write combined rendering and stability tests**

Create `tests/slack/test_combined_announcements.py` and assert:

- rendered text contains `Choose a session:` and `Your Practice Plan:`, never `Optional:` or pipe-separated session metadata;
- initial post commits two unique saved session emojis before seeding those exact attendance names plus the shared Plan-reaction names;
- reversing database/display order does not change either saved value;
- a legacy root with two blank values assigns once, and a reaction event persists the same mapping before routing;
- duplicate persisted values fail an existing-root rebuild without changing either value;
- a failed no-root combined attempt followed by standalone posting clears the stale value;
- cancelled rows stay visible, a one-survivor rebuild keeps combined grammar/value, and same-timestamp rows in another channel are excluded;
- complete fallback text names every session's date/time, status, location, and attendance reaction.
- changing one session to a different Plan snapshot hides the shared legend and removes only the bot's obsolete seed; member reactions remain Slack-owned history.
- an unposted group whose reaction assignment fails validation is posted standalone in the same scheduler run after clearing stale session values; an ambiguous Slack/network failure is never followed by standalone posts that could duplicate a root.
- a post-creation edit that makes workouts, Notes, or Social differ keeps every sibling's content visible under its saved session reaction.

Start the pure rendering coverage with this concrete fixture; add the mocked database/Slack orchestration assertions from the list above in the same file:

```python
from datetime import datetime
from types import SimpleNamespace

from app.practices.interfaces import PracticeStatus
from app.slack.blocks import (
    build_combined_fallback_text,
    build_combined_lift_blocks,
)


def combined_practice(
    practice_id,
    day,
    hour,
    emoji,
    *,
    status=PracticeStatus.SCHEDULED,
    reason=None,
    workout="3 x 8 strength circuit",
    plan=None,
):
    return SimpleNamespace(
        id=practice_id,
        date=datetime(2026, 7, day, hour, 15),
        status=status,
        slack_session_emoji=emoji,
        location=SimpleNamespace(id=10, name="Balance Fitness", spot=None),
        activities=[SimpleNamespace(id=1, name="Strength")],
        practice_types=[SimpleNamespace(id=2, name="Strength")],
        workout_description=workout,
        logistics_notes="Bring indoor shoes",
        has_social=False,
        social_location=None,
        plan_reactions=list(plan or []),
        leads=[],
        cancellation_reason=reason,
    )


def rendered_text(blocks):
    parts = []
    for block in blocks:
        if block["type"] in {"header", "section"}:
            parts.append(block["text"]["text"])
        elif block["type"] == "context":
            parts.extend(item["text"] for item in block["elements"])
    return "\n".join(parts)


def test_combined_uses_saved_session_map_and_shared_plan_grammar():
    plan = [{"emoji": "evergreen_tree", "label": "Endurance instead"}]
    practices = [
        combined_practice(1, 14, 18, "six", plan=plan),
        combined_practice(2, 15, 19, "seven", plan=plan),
    ]
    text = rendered_text(build_combined_lift_blocks(practices))
    assert "Strength practices · July 14–15" in text
    assert "Choose a session:" in text
    assert ":six: *Tuesday" in text
    assert ":seven: *Wednesday" in text
    assert "Your Practice Plan:" in text
    assert ":evergreen_tree: Endurance instead" in text
    assert "Optional:" not in text
    assert " | " not in text


def test_cancelled_slot_and_fallback_keep_every_session_distinct():
    practices = [
        combined_practice(1, 14, 18, "six"),
        combined_practice(
            2,
            15,
            19,
            "seven",
            status=PracticeStatus.CANCELLED,
            reason="Facility closed",
        ),
    ]
    text = rendered_text(build_combined_lift_blocks(practices))
    fallback = build_combined_fallback_text(practices)
    assert "CANCELLED" in text and "Facility closed" in text
    for value in (
        "Tuesday", "6:15 PM", "Balance Fitness", ":six:",
        "Wednesday", "7:15 PM", "CANCELLED", "Facility closed", ":seven:",
    ):
        assert value in fallback


def test_one_survivor_keeps_combined_grammar_and_saved_reaction():
    text = rendered_text(build_combined_lift_blocks([
        combined_practice(2, 15, 19, "seven")
    ]))
    assert "Choose a session:" in text
    assert ":seven: *Wednesday" in text
    assert "✅" not in text


def test_post_creation_workout_divergence_keeps_both_values_visible():
    text = rendered_text(build_combined_lift_blocks([
        combined_practice(1, 14, 18, "six", workout="Session A circuit"),
        combined_practice(2, 15, 19, "seven", workout="Session B circuit"),
    ]))
    assert "Session A circuit" in text
    assert "Session B circuit" in text
```

- [ ] **Step 3: Run combined tests and see current inference failures**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_combined_announcements.py \
  tests/test_scheduler_practice_announcements.py \
  tests/slack/test_details_reply_wiring.py
```

- [ ] **Step 4: Persist session emoji assignment**

Replace position-only inference in `app/slack/client.py` with assignment that respects existing values:

1. Sort practices by `(date, id)` only for assigning previously blank values.
2. Reserve every nonblank `slack_session_emoji` first; duplicate persisted values are an error and are never silently remapped on an existing root.
3. Prefer a unique hour emoji for a blank practice.
4. Fall back through the current checkmark sequence, skipping reserved values.
5. If three unique values cannot be assigned, return a validation failure and post those practices standalone.
6. Commit the assignments before posting/seeding Slack so retries use the same mapping.

For a duplicate/corrupt saved value on an existing Slack root, fail the rebuild and leave the message untouched. For unposted candidates, clear the invalid values and post those practices standalone instead of inventing a remap.

```python
def assign_combined_session_emojis(practices):
    from app.models import db

    ordered = sorted(practices, key=lambda item: (item.date, item.id))
    assignments = {}
    used = {}
    for practice in ordered:
        saved = (practice.slack_session_emoji or "").strip()
        if not saved:
            continue
        if saved in used:
            return {
                "success": False,
                "error": (
                    f"Duplicate combined-session emoji :{saved}: on "
                    f"practices #{used[saved]} and #{practice.id}"
                ),
            }
        used[saved] = practice.id
        assignments[practice.id] = saved

    for practice in ordered:
        if practice.id in assignments:
            continue
        candidates = []
        preferred = _hour_emoji_for(practice.date)
        if preferred:
            candidates.append(preferred)
        candidates.extend(COMBINED_PRACTICE_FALLBACK_EMOJIS)
        choice = next((name for name in candidates if name not in used), None)
        if choice is None:
            return {
                "success": False,
                "error": "Could not assign unique combined-session reactions",
            }
        assignments[practice.id] = choice
        used[choice] = practice.id

    try:
        for practice in ordered:
            practice.slack_session_emoji = assignments[practice.id]
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return {"success": False, "error": str(exc)}
    return {"success": True, "emojis": assignments}


def get_lead_confirmation_emoji_for_practice(practice) -> list[str]:
    return [practice.slack_session_emoji or "white_check_mark"]
```

`get_lead_confirmation_emoji_for_practice(practice) -> list[str]` must preserve its existing list contract, returning `[practice.slack_session_emoji]` when present and `["white_check_mark"]` otherwise. It must not re-derive the mapping from sibling order.

Before posting a practice standalone when it has no Slack root, clear any stale `slack_session_emoji` left by a failed/abandoned combined attempt and commit that reset with the standalone timestamp. Add the regression above so ✅ routing cannot inherit a failed combined state.

- [ ] **Step 5: Add one scoped sibling helper and use it everywhere**

In `app/slack/practices/announcements.py`:

```python
def get_announcement_siblings(practice, *, exclude_practice_id=None):
    query = Practice.query.filter_by(
        slack_channel_id=practice.slack_channel_id,
        slack_message_ts=practice.slack_message_ts,
    )
    if exclude_practice_id is not None:
        query = query.filter(Practice.id != exclude_practice_id)
    return query.order_by(Practice.date, Practice.id).all()
```

Use it in combined detection, rendering updates, Details updates, lead-confirmation lookup, and later cancellation/deletion code. `is_combined_lift_practice()` returns true when `slack_session_emoji` is nonblank, even if only one database row survives. For a pre-migration root with blank values, more than one scoped sibling also means combined; assign and commit their stable values before rebuilding or cancelling.

In `handle_attendance_reaction()`, when multiple scoped siblings have blank legacy values, call `assign_combined_session_emojis()` once before matching the event. This removes Task 10's temporary inference bridge and makes the first post-deploy reaction stable.

```python
if len(siblings) > 1:
    saved = [item.slack_session_emoji for item in siblings if item.slack_session_emoji]
    if len(saved) != len(set(saved)):
        return {"success": True, "ignored": "invalid_combined_mapping"}
    if any(not item.slack_session_emoji for item in siblings):
        assignment = assign_combined_session_emojis(siblings)
        if not assignment["success"]:
            return {"success": True, "ignored": "invalid_combined_mapping"}
```

- [ ] **Step 6: Rebuild combined blocks with the approved hierarchy**

`build_combined_lift_blocks()` should use:

1. Strength header and calendar range.
2. The exact heading `Choose a session:`.
3. One clearly separated session row per practice: weekday/date, time, status, saved emoji, and location.
4. Shared workout or intentional placeholder.
5. Notes/Social when present.
6. One attendance instruction mapping each saved emoji to its session.
7. `Your Practice Plan:` plus supplemental choices only when every surviving session has the same ordered saved list.

Cancelled sessions remain in place with explicit `CANCELLED` styling. A one-survivor defensive rebuild still uses this grammar and saved session emoji so an existing member reaction is never remapped. Combined Strength remains condition-fetch-free (these are indoor sessions); do not add per-session weather/daylight orchestration to this defensive path. Guard blocks and add `build_combined_fallback_text()` with all session distinctions.

Compatibility is enforced only when a new group is created. If a later edit makes saved siblings differ, retain the shared root and render the differing workout, Notes, or Social values under their saved session emoji; never display only the first sibling's content. Common values still render once to keep the normal combined post compact.

Use the stored `slack_session_emoji` directly in both builders; neither builder may call an inference helper. Keep coach/lead ownership visible inside each session row, and use the same semantic-group helper introduced for standalone posts so optional shared content cannot produce adjacent dividers:

```python
def _status_value(practice):
    return getattr(practice.status, "value", practice.status)


def _is_cancelled(practice):
    return _status_value(practice) == PracticeStatus.CANCELLED.value


def _combined_date_label(practices):
    first = practices[0].date.date()
    last = practices[-1].date.date()
    if first == last:
        return f"{first:%B} {first.day}"
    if first.year == last.year and first.month == last.month:
        return f"{first:%B} {first.day}–{last.day}"
    if first.year == last.year:
        return f"{first:%B} {first.day}–{last:%B} {last.day}"
    return (
        f"{first:%B} {first.day}, {first.year}–"
        f"{last:%B} {last.day}, {last.year}"
    )


def _shared_plan_reactions(practices):
    snapshots = [
        tuple((item["emoji"], item["label"]) for item in (p.plan_reactions or []))
        for p in practices
    ]
    if not snapshots or any(snapshot != snapshots[0] for snapshot in snapshots[1:]):
        return []
    return [
        {"emoji": emoji, "label": label}
        for emoji, label in snapshots[0]
    ]


def _same_value(practices, getter):
    values = [getter(practice) for practice in practices]
    return all(value == values[0] for value in values[1:]), values[0]


def _social_value(practice):
    social = getattr(practice, "social_location", None)
    return (
        bool(practice.has_social),
        getattr(social, "id", None),
        getattr(social, "name", None),
    )


def _social_line(practice):
    if not practice.has_social:
        return None
    social = getattr(practice, "social_location", None)
    return (
        f"🍹 *Social after at {social.name}*"
        if social and social.name else "🍹 *Social after!*"
    )


def _combined_lead_line(practice):
    coaches, leads = [], []
    for lead in (practice.leads or []):
        mention = (
            f"<@{lead.slack_user_id}>"
            if lead.slack_user_id else lead.display_name or "Unknown"
        )
        role_name = getattr(lead.role, "name", str(lead.role)).upper()
        if role_name == "COACH":
            coaches.append(mention)
        elif role_name in {"LEAD", "ASSIST"}:
            leads.append(mention)
    parts = []
    if coaches:
        parts.append(f"Coach {', '.join(coaches)}")
    if leads:
        parts.append(f"Leads {', '.join(leads)}")
    return " · ".join(parts)


def _combined_session_text(practice):
    emoji = f":{practice.slack_session_emoji}:"
    when = (
        f"{practice.date.strftime('%A, %B %-d')} · "
        f"{practice.date.strftime('%-I:%M %p')}"
    )
    first_line = (
        f"{emoji} *CANCELLED · {when}*"
        if _is_cancelled(practice) else f"{emoji} *{when}*"
    )
    location = practice.location.name if practice.location else "TBD"
    spot = (
        practice.location.spot
        if practice.location and practice.location.spot else None
    )
    lines = [first_line, location + (f" - {spot}" if spot else "")]
    if _is_cancelled(practice):
        lines.append(f"Reason: {practice.cancellation_reason or 'Cancelled'}")
    lead_line = _combined_lead_line(practice)
    if lead_line:
        lines.append(lead_line)
    return "\n".join(lines)


def build_combined_lift_blocks(practices, *, announcement_notice=None):
    ordered = sorted(practices, key=lambda item: (item.date, item.id))
    if not ordered:
        return []
    if any(not item.slack_session_emoji for item in ordered):
        raise ValueError("Combined builders require persisted session reactions")

    header_group = [{
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"Strength practices · {_combined_date_label(ordered)}",
            "emoji": True,
        },
    }]
    if announcement_notice:
        header_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": announcement_notice + _SPACER},
        })
    session_group = [{
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*Choose a session:*"},
    }]
    session_group.extend({
        "type": "section",
        "text": {"type": "mrkdwn", "text": _combined_session_text(practice)},
    } for practice in ordered)

    representative = ordered[0]
    same_workout, shared_workout = _same_value(
        ordered,
        lambda item: str(item.workout_description or "").strip(),
    )
    same_notes, shared_notes = _same_value(
        ordered,
        lambda item: str(item.logistics_notes or "").strip(),
    )
    same_social, _ = _same_value(ordered, _social_value)
    workout_group = []

    workout_rows = [(representative, shared_workout)] if same_workout else [
        (practice, str(practice.workout_description or "").strip())
        for practice in ordered
    ]
    for owner, value in workout_rows:
        type_names = ", ".join(item.name for item in (owner.practice_types or []))
        owner_label = (
            ""
            if same_workout else
            f":{owner.slack_session_emoji}: {owner.date.strftime('%A at %-I:%M %p')} · "
        )
        workout_label = (
            f"*{owner_label}Workout · {type_names}*"
            if type_names else f"*{owner_label}Workout*"
        )
        workout_prefix = f"{workout_label}\n"
        workout = truncate_slack_text(
            value or "Workout details coming soon.",
            SECTION_TEXT_MAX - len(workout_prefix),
            field="workout_description",
            surface="combined_practice_announcement",
            practice_id=owner.id,
        )
        workout_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": workout_prefix + workout},
        })

    notes_rows = [(representative, shared_notes)] if same_notes else [
        (practice, str(practice.logistics_notes or "").strip())
        for practice in ordered
    ]
    for owner, value in notes_rows:
        if not value:
            continue
        owner_label = (
            ""
            if same_notes else
            f":{owner.slack_session_emoji}: {owner.date.strftime('%A at %-I:%M %p')} · "
        )
        notes_prefix = f"*📌 {owner_label}Notes*\n"
        notes = truncate_slack_text(
            value,
            SECTION_TEXT_MAX - len(notes_prefix),
            field="logistics_notes",
            surface="combined_practice_announcement",
            practice_id=owner.id,
        )
        workout_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": notes_prefix + notes},
        })

    social_rows = [representative] if same_social else ordered
    for owner in social_rows:
        social_text = _social_line(owner)
        if not social_text:
            continue
        prefix = (
            ""
            if same_social else
            f":{owner.slack_session_emoji}: {owner.date.strftime('%A at %-I:%M %p')} · "
        )
        workout_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": prefix + social_text},
        })

    mappings = []
    for practice in ordered:
        status = " · CANCELLED" if _is_cancelled(practice) else ""
        mappings.append(
            f":{practice.slack_session_emoji}: "
            f"{practice.date.strftime('%A at %-I:%M %p')}{status}"
        )
    ending_lines = [
        "Bop the reaction for your session if you're coming.",
        " · ".join(mappings),
    ]
    shared_plan = _shared_plan_reactions(ordered)
    if shared_plan:
        ending_lines.extend([
            "",
            "*Your Practice Plan:*",
            format_plan_reaction_legend(shared_plan),
        ])
    ending_group = [{
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "\n".join(ending_lines)}],
    }]

    return guard_slack_blocks(
        _join_block_groups([
            header_group, session_group, workout_group, ending_group,
        ]),
        surface="combined_practice_announcement",
        practice_id=representative.id,
    )


def build_combined_fallback_text(practices, *, announcement_notice=None):
    ordered = sorted(practices, key=lambda item: (item.date, item.id))
    if not ordered:
        return guard_fallback_text(
            "Strength practice details unavailable.",
            surface="combined_practice_announcement",
        )
    lines = [f"Strength practices · {_combined_date_label(ordered)}."]
    if announcement_notice:
        lines.append(announcement_notice)
    for practice in ordered:
        location = practice.location.name if practice.location else "TBD"
        status = (
            f"CANCELLED: {practice.cancellation_reason or 'Cancelled'}"
            if _is_cancelled(practice) else "Active"
        )
        lines.append(
            f"{practice.date.strftime('%A, %B %-d at %-I:%M %p')}; "
            f"{status}; {location}; attend with "
            f":{practice.slack_session_emoji}:."
        )
    representative = ordered[0]
    same_workout, shared_workout = _same_value(
        ordered,
        lambda item: str(item.workout_description or "").strip()
        or "Workout details coming soon.",
    )
    if same_workout:
        lines.append(f"Workout: {shared_workout}")
    else:
        lines.extend(
            f"{practice.date.strftime('%A at %-I:%M %p')} workout: "
            f"{str(practice.workout_description or '').strip() or 'Workout details coming soon.'}"
            for practice in ordered
        )
    same_notes, shared_notes = _same_value(
        ordered,
        lambda item: str(item.logistics_notes or "").strip(),
    )
    if same_notes and shared_notes:
        lines.append(f"Notes: {shared_notes}")
    elif not same_notes:
        lines.extend(
            f"{practice.date.strftime('%A at %-I:%M %p')} notes: {practice.logistics_notes}"
            for practice in ordered if practice.logistics_notes
        )
    shared_plan = _shared_plan_reactions(ordered)
    if shared_plan:
        lines.append(
            "Your Practice Plan: " + format_plan_reaction_legend(shared_plan) + "."
        )
    return guard_fallback_text(
        " ".join(lines),
        surface="combined_practice_announcement",
        practice_id=representative.id,
    )
```

Pass `build_combined_fallback_text()` to `text=` on both initial `chat_postMessage` and every combined `chat_update`; never retain the generic `TCSC Lift - days` fallback.

After the combined root posts successfully, seed each saved session emoji and each shared Plan emoji best-effort. Do not seed standalone `white_check_mark` unless it is itself one session's persisted attendance value.

On update, compute the shared Plan list only when every ordered snapshot is identical. Reconcile bot seeds from the union of current sibling Plan names plus `previous_plan_reactions`: add the shared desired names and remove names that are no longer shared. Slack's `reactions_remove` removes only the bot's own reaction, so historical member reactions are not deleted.

Refactor `_upsert_combined_details_reply()` to use the same nonempty-create/nonempty-update/empty-delete lifecycle from Task 9. Store the canonical Details timestamp on every sibling after create; after a successful empty delete clear it on every sibling; retain all timestamps when deletion fails.

Wire the post/update paths around one ordered sibling set and the builders above:

```python
def _combined_infos(practices):
    return [convert_practice_to_info(item) for item in practices]


def post_combined_lift_announcement(practices, channel_override=None):
    if not 2 <= len(practices) <= 3:
        return {"success": False, "error": "Combined posts require 2 or 3 practices"}
    ordered = sorted(practices, key=lambda item: (item.date, item.id))
    assignment = assign_combined_session_emojis(ordered)
    if not assignment["success"]:
        return {**assignment, "safe_to_fallback": True}

    channel_id = (
        get_channel_id_by_name(channel_override.lstrip("#"))
        if channel_override else _get_announcement_channel()
    )
    if not channel_id:
        return {"success": False, "error": "Could not find announcement channel"}
    infos = _combined_infos(ordered)
    blocks = build_combined_lift_blocks(infos)
    fallback = build_combined_fallback_text(infos)
    client = get_slack_client()
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=fallback,
            unfurl_links=False,
            unfurl_media=False,
        )
        message_ts = response.get("ts")
        if not message_ts:
            return {
                "success": False,
                "error": "Slack did not return a message timestamp",
            }
        for practice in ordered:
            practice.slack_channel_id = channel_id
            practice.slack_message_ts = message_ts
        db.session.commit()
        details = _upsert_combined_details_reply(client, ordered)
        _seed_combined_reactions(client, ordered)
        return {
            "success": True,
            "message_ts": message_ts,
            "channel_id": channel_id,
            "details": details,
        }
    except SlackApiError as exc:
        return {"success": False, "error": exc.response.get("error", str(exc))}


def update_combined_lift_post(
    practice,
    *,
    exclude_practice_id=None,
    previous_plan_reactions=None,
    announcement_notice=None,
):
    all_siblings = get_announcement_siblings(practice)
    if not all_siblings:
        return {"success": False, "error": "No practices found for this message"}
    assignment = assign_combined_session_emojis(all_siblings)
    if not assignment["success"]:
        return assignment
    removed = next(
        (item for item in all_siblings if item.id == exclude_practice_id),
        None,
    )
    siblings = [
        item for item in all_siblings if item.id != exclude_practice_id
    ]
    if not siblings:
        return {"success": False, "error": "No surviving practices for this message"}

    infos = _combined_infos(siblings)
    blocks = build_combined_lift_blocks(
        infos, announcement_notice=announcement_notice,
    )
    fallback = build_combined_fallback_text(
        infos, announcement_notice=announcement_notice,
    )
    client = get_slack_client()
    details = None
    if exclude_practice_id is not None:
        details = _upsert_combined_details_reply(client, siblings)
        if not details.get("success"):
            return {
                "success": False,
                "error": "Combined Details did not sync; root was not changed",
                "details": details,
            }
    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=fallback,
        )
        if details is None:
            details = _upsert_combined_details_reply(client, siblings)
        _reconcile_combined_plan_reactions(
            client,
            siblings,
            previous_plan_reactions=previous_plan_reactions,
        )
        if removed and removed.slack_session_emoji:
            _remove_combined_seed(
                client, siblings, removed.slack_session_emoji,
            )
        return {"success": True, "details": details}
    except SlackApiError as exc:
        return {"success": False, "error": exc.response.get("error", str(exc))}
```

The exclusion branch intentionally syncs remaining Details before changing the root. If that secondary write fails, the root and database row both remain intact for retry. For ordinary edit/cancel updates, the root remains primary and a Details failure is returned only in the nested `details` result.

Update `update_practice_slack_post()` from Task 9 so its combined branch forwards both `announcement_notice` and `previous_plan_reactions`. The same temporary date/location notice appears once near the combined header and once in the safety thread note; it is never persisted.

Implement the shared reaction helpers explicitly. They operate only on the bot's own reactions; `reactions_remove` does not erase members' historical reactions:

```python
def _shared_plan_names(practices):
    infos = _combined_infos(practices)
    return plan_reaction_names(_shared_plan_reactions(infos))


def _seed_combined_reactions(client, practices):
    names = [item.slack_session_emoji for item in practices]
    names.extend(_shared_plan_names(practices))
    for name in dict.fromkeys(names):
        try:
            client.reactions_add(
                channel=practices[0].slack_channel_id,
                timestamp=practices[0].slack_message_ts,
                name=name,
            )
        except Exception as exc:
            if _reaction_error_name(exc) != "already_reacted":
                current_app.logger.warning(
                    "Could not seed :%s: on combined root %s: %s",
                    name,
                    practices[0].slack_message_ts,
                    exc,
                )


def _remove_combined_seed(client, practices, name):
    try:
        client.reactions_remove(
            channel=practices[0].slack_channel_id,
            timestamp=practices[0].slack_message_ts,
            name=name,
        )
    except Exception as exc:
        if _reaction_error_name(exc) != "no_reaction":
            current_app.logger.warning(
                "Could not remove :%s: from combined root %s: %s",
                name,
                practices[0].slack_message_ts,
                exc,
            )


def _reconcile_combined_plan_reactions(
    client,
    practices,
    *,
    previous_plan_reactions=None,
):
    desired = set(_shared_plan_names(practices))
    known = set(plan_reaction_names(previous_plan_reactions or []))
    for practice in practices:
        known.update(plan_reaction_names(practice.plan_reactions or []))
    for name in sorted(known - desired):
        _remove_combined_seed(client, practices, name)
    for name in sorted(desired):
        try:
            client.reactions_add(
                channel=practices[0].slack_channel_id,
                timestamp=practices[0].slack_message_ts,
                name=name,
            )
        except Exception as exc:
            if _reaction_error_name(exc) != "already_reacted":
                current_app.logger.warning(
                    "Could not add :%s: to combined root %s: %s",
                    name,
                    practices[0].slack_message_ts,
                    exc,
                )
```

Replace `_upsert_combined_details_reply()` with the same structured lifecycle as standalone Details, using an empty `AnnouncementConditions()` because this path deliberately performs no provider fetch. When every sibling has identical parking/gear content, render it once; if a later location/activity edit makes Details diverge, label each nonempty payload with its saved session reaction so no sibling's logistics are hidden:

```python
def _combined_details_payload(practices):
    conditions = AnnouncementConditions()
    rendered = []
    for practice in practices:
        info = convert_practice_to_info(practice)
        child_blocks = build_practice_details_blocks(info, conditions)
        if not child_blocks:
            continue
        content_blocks = [
            block for block in child_blocks if block.get("type") != "header"
        ]
        rendered.append((
            practice,
            content_blocks,
            build_practice_details_fallback_text(info, conditions),
        ))
    if not rendered:
        return [], ""

    common = (
        len(rendered) == len(practices)
        and all(item[1] == rendered[0][1] for item in rendered[1:])
    )
    if common:
        practice, content, fallback = rendered[0]
        blocks = [{
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Practice Details",
                "emoji": True,
            },
        }] + content
        return (
            guard_slack_blocks(
                blocks,
                surface="combined_practice_details",
                practice_id=practice.id,
            ),
            fallback,
        )

    groups = []
    fallback_parts = ["Combined practice details."]
    for practice, content, fallback in rendered:
        groups.append([{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*:{practice.slack_session_emoji}: "
                    f"{practice.date.strftime('%A at %-I:%M %p')}*"
                ),
            },
        }] + content)
        fallback_parts.append(
            f":{practice.slack_session_emoji}: {fallback}"
        )
    blocks = [{
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Practice Details",
            "emoji": True,
        },
    }]
    for group in groups:
        if len(blocks) > 1:
            blocks.append({"type": "divider"})
        blocks.extend(group)
    return (
        guard_slack_blocks(
            blocks,
            surface="combined_practice_details",
            practice_id=practices[0].id,
        ),
        guard_fallback_text(
            " ".join(fallback_parts),
            surface="combined_practice_details",
            practice_id=practices[0].id,
        ),
    )


def _upsert_combined_details_reply(client, practices):
    if not practices:
        return {"success": True, "skipped": "no_practices"}
    representative = practices[0]
    original = {
        practice.id: practice.slack_details_ts for practice in practices
    }
    existing = next((value for value in original.values() if value), None)
    blocks, fallback = _combined_details_payload(practices)
    try:
        if not blocks:
            if not existing:
                return {"success": True, "skipped": "no_details"}
            client.chat_delete(
                channel=representative.slack_channel_id,
                ts=existing,
            )
            for practice in practices:
                practice.slack_details_ts = None
            db.session.commit()
            return {"success": True, "deleted": True}

        if existing:
            client.chat_update(
                channel=representative.slack_channel_id,
                ts=existing,
                blocks=blocks,
                text=fallback,
            )
            for practice in practices:
                practice.slack_details_ts = existing
            db.session.commit()
            return {"success": True, "updated": True}

        response = client.chat_postMessage(
            channel=representative.slack_channel_id,
            thread_ts=representative.slack_message_ts,
            blocks=blocks,
            text=fallback,
            reply_broadcast=False,
            unfurl_links=False,
            unfurl_media=False,
        )
        details_ts = response.get("ts")
        if not details_ts:
            return {"success": False, "error": "Slack returned no Details timestamp"}
        for practice in practices:
            practice.slack_details_ts = details_ts
        db.session.commit()
        return {"success": True, "message_ts": details_ts}
    except Exception as exc:
        for practice in practices:
            practice.slack_details_ts = original[practice.id]
        db.session.rollback()
        return {"success": False, "error": str(exc)}
```

The smart dispatcher becomes:

```python
def update_practice_slack_post(
    practice,
    *,
    announcement_notice=None,
    previous_plan_reactions=None,
):
    if not practice.slack_message_ts:
        return {"success": False, "error": "No Slack post to update"}
    if is_combined_lift_practice(practice):
        return update_combined_lift_post(
            practice,
            announcement_notice=announcement_notice,
            previous_plan_reactions=previous_plan_reactions,
        )
    return update_practice_post(
        practice,
        announcement_notice=announcement_notice,
        previous_plan_reactions=previous_plan_reactions,
    )
```

- [ ] **Step 7: Group Strength posts conservatively**

Add pure `combined_compatibility_key()` and `group_strength_announcements()` helpers in `app/scheduler.py`. Partition the seven-day unannounced Strength candidates by compatibility. Only groups with length two or three call `post_combined_lift_announcement()`; singleton and groups over three flow through `post_practice_announcement()` individually.

When the scheduler's current announcement window contains one member of a compatible group, it may include its compatible next-seven-day siblings as today. It must mark/skip every posted ID so no practice is posted twice in the same run.

```python
def _normalized_shared_text(value):
    return " ".join(str(value or "").split())


def _tag_key(items):
    pairs = [
        (getattr(item, "id", None), _normalized_shared_text(item.name))
        for item in (items or [])
    ]
    return tuple(sorted(
        pairs, key=lambda pair: (pair[1].casefold(), pair[0] or -1)
    ))


def combined_compatibility_key(practice):
    social = getattr(practice, "social_location", None)
    reactions = tuple(
        (item["emoji"], item["label"])
        for item in (practice.plan_reactions or [])
    )
    return (
        practice.location_id,
        _normalized_shared_text(practice.workout_description),
        _normalized_shared_text(practice.logistics_notes),
        bool(practice.has_social),
        getattr(practice, "social_location_id", None),
        _normalized_shared_text(getattr(social, "name", None)),
        _tag_key(practice.activities),
        _tag_key(practice.practice_types),
        reactions,
    )


def group_strength_announcements(practices, *, in_window_ids):
    buckets = {}
    for practice in sorted(practices, key=lambda item: (item.date, item.id)):
        buckets.setdefault(combined_compatibility_key(practice), []).append(practice)

    combined, standalone = [], []
    for group in buckets.values():
        if not any(item.id in in_window_ids for item in group):
            continue
        if 2 <= len(group) <= 3:
            combined.append(group)
        else:
            standalone.extend(item for item in group if item.id in in_window_ids)
    return combined, standalone
```

Use the current-window IDs so a singleton or four-item bucket does not announce future practices early:

```python
window_ids = {practice.id for practice in strength_in_window}
combined_groups, standalone_strength = group_strength_announcements(
    all_strength,
    in_window_ids=window_ids,
)
handled = set()
for group in combined_groups:
    result = post_combined_lift_announcement(
        group, channel_override=channel_override
    )
    if result.get("success"):
        announced += len(group)
    elif result.get("safe_to_fallback"):
        for practice in group:
            practice.slack_session_emoji = None
        db.session.commit()
        for practice in group:
            fallback = post_practice_announcement(
                practice, channel_override=channel_override
            )
            if fallback.get("success"):
                announced += 1
            else:
                errors += 1
    else:
        errors += len(group)
    handled.update(practice.id for practice in group)

for practice in standalone_strength:
    if practice.id in handled:
        continue
    practice.slack_session_emoji = None
    result = post_practice_announcement(
        practice, channel_override=channel_override
    )
    if result.get("success"):
        announced += 1
    else:
        errors += 1
```

- [ ] **Step 8: Run combined and scheduler tests**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_combined_announcements.py \
  tests/slack/test_details_reply_wiring.py \
  tests/test_scheduler_practice_announcements.py
```

Expected: all pass.

- [ ] **Step 9: Commit the completed combined format**

```bash
git add app/slack/client.py app/slack/blocks/announcements.py \
  app/slack/blocks/__init__.py \
  app/slack/practices/announcements.py app/slack/practices/reactions.py \
  app/scheduler.py \
  tests/slack/test_combined_announcements.py \
  tests/slack/test_details_reply_wiring.py \
  tests/test_scheduler_practice_announcements.py
git commit -m "feat(slack): finish safe combined strength posts"
```

---

### Task 12: Make shared cancellation and deletion safe

**Files:**

- Modify: `app/slack/blocks/cancellations.py`
- Modify: `app/slack/practices/cancellations.py`
- Modify: `app/slack/practices/announcements.py`
- Modify: `app/slack/practices/refresh.py`
- Modify: `app/routes/admin_practices.py`
- Modify: `tests/slack/test_refresh.py`
- Modify: `tests/slack/test_refresh_delete_exclusion.py`
- Modify: `tests/slack/test_combined_announcements.py`
- Create: `tests/routes/test_admin_practice_delete.py`

**Interfaces:**

- `remove_practice_from_announcement(practice)` rebuilds survivors or deletes only the final root.
- Cancellation refresh always rebuilds a shared post; it never replaces that root with a standalone cancellation card.
- The admin delete route commits deletion only after the announcement surface reports success or a legitimate no-post skip.

- [ ] **Step 1: Write failing shared-lifecycle tests**

Add regressions that assert:

- cancelling one combined session calls the combined rebuild, leaves the active sibling in root blocks, and never calls the standalone cancellation updater;
- deleting one session rebuilds with `exclude_practice_id` equal to only that row, while deleting the final session deletes Details then root;
- a root rebuild/delete Slack failure returns an error and leaves the database row present;
- a survivor Details failure occurs before `chat_update`, returns an error, and leaves both the root and database row present;
- a practice with no announcement remains deletable;
- a same timestamp in another channel is never treated as a sibling;
- cancellation refresh failure returns the saved-but-unsynced 502 response while the database status remains cancelled.

Assert that a failed survivor rebuild keeps the database row, timestamps, and original root available for retry.

- [ ] **Step 2: Run the lifecycle tests and reproduce destructive behavior**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_refresh.py \
  tests/slack/test_refresh_delete_exclusion.py \
  tests/slack/test_combined_announcements.py \
  tests/routes/test_admin_practice_delete.py
```

Expected: current code calls `chat_delete` or a standalone cancellation replacement for the shared timestamp.

- [ ] **Step 3: Guard standalone cancellation output and fallback**

Move the standalone cancelled blocks into the existing cancellation block builder, call `guard_slack_blocks()`, and add `build_cancelled_practice_fallback_text()` containing date, time, location, cancellation status, reason, and member direction. Both `post_cancellation_notice()` and `update_practice_as_cancelled()` must pass this complete fallback into their Slack write.

- [ ] **Step 4: Branch cancellation on persisted lifecycle**

In `_refresh_announcement()`:

```python
if not practice.slack_message_ts:
    return {"success": True, "skipped": "absent"}
if not practice.slack_channel_id:
    return {"success": False, "error": "Slack message has no channel"}

if change_type == "cancel":
    if is_combined_lift_practice(practice):
        result = update_combined_lift_post(practice)
        if result.get("success"):
            notice = post_combined_cancellation_thread_notice(practice)
            if not notice.get("success"):
                logger.warning(
                    "Combined cancellation root updated but thread note failed "
                    "for #%s: %s",
                    practice.id,
                    notice,
                )
        return result
    return update_practice_as_cancelled(practice, "Admin")

if change_type == "delete":
    return remove_practice_from_announcement(practice)
```

The thread notice names the cancelled session's weekday/time and reason. Post it only after the root rebuild succeeds. It may fail best-effort without reverting the safe root.

```python
def post_combined_cancellation_thread_notice(practice):
    text = (
        f":x: {practice.date.strftime('%A at %-I:%M %p')} was cancelled: "
        f"{practice.cancellation_reason or 'Cancelled'}. "
        "Other sessions in this announcement are unchanged."
    )
    try:
        get_slack_client().chat_postMessage(
            channel=practice.slack_channel_id,
            thread_ts=practice.slack_message_ts,
            text=guard_fallback_text(
                text,
                surface="combined_cancellation_thread",
                practice_id=practice.id,
            ),
            reply_broadcast=False,
        )
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
```

- [ ] **Step 5: Implement delete-as-rebuild**

`remove_practice_from_announcement()` must:

- return a successful skip if no Slack root exists;
- load siblings through `get_announcement_siblings(practice, exclude_practice_id=practice.id)`;
- when survivors exist, rebuild/update the root and Details using those survivors without mutating their saved emojis;
- when no survivor exists, delete Details first (when present), then the root;
- clear affected Slack timestamps only after the corresponding Slack operation succeeds;
- return `{"success": False, "error": str(exc)}` on any root operation failure.

The delete refresh invokes this helper instead of unconditional `chat_delete`.

Use an idempotent delete primitive and implement the helper exactly around the root safety boundary:

```python
def _delete_slack_message(client, *, channel, ts):
    try:
        client.chat_delete(channel=channel, ts=ts)
        return {"success": True}
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        if error == "message_not_found":
            return {"success": True, "skipped": "already_absent"}
        return {"success": False, "error": error}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def remove_practice_from_announcement(practice):
    if not practice.slack_message_ts:
        return {"success": True, "skipped": "absent"}
    if not practice.slack_channel_id:
        return {"success": False, "error": "Slack message has no channel"}

    survivors = get_announcement_siblings(
        practice,
        exclude_practice_id=practice.id,
    )
    if survivors:
        return update_combined_lift_post(
            practice,
            exclude_practice_id=practice.id,
            previous_plan_reactions=practice.plan_reactions or [],
        )

    client = get_slack_client()
    if practice.slack_details_ts:
        details_result = _delete_slack_message(
            client,
            channel=practice.slack_channel_id,
            ts=practice.slack_details_ts,
        )
        if not details_result["success"]:
            return details_result
        practice.slack_details_ts = None
        db.session.commit()

    root_result = _delete_slack_message(
        client,
        channel=practice.slack_channel_id,
        ts=practice.slack_message_ts,
    )
    if not root_result["success"]:
        return root_result
    practice.slack_message_ts = None
    practice.slack_channel_id = None
    db.session.commit()
    return {"success": True}
```

A Details delete failure returns before `chat_delete` is called for the root. `message_not_found` is idempotent success for either timestamp. When a survivor rebuild succeeds, Task 11 removes the excluded session's bot-owned attendance seed and reconciles the deleted row's Plan seed; member reaction history is untouched.

Short-circuit the remaining delete surfaces only when a posted announcement failed to rebuild/delete. This prevents coach/weekly summaries from hiding a row while its shared root still contains it:

```python
results = {}
had_announcement = bool(practice.slack_message_ts)
for index, surface in enumerate(PRACTICE_SURFACES):
    result = surface.refresh(practice, change_type, **context)
    results[surface.name] = result
    if (
        change_type == "delete"
        and surface.name == "announcement"
        and had_announcement
        and result.get("success") is not True
    ):
        for blocked in PRACTICE_SURFACES[index + 1:]:
            results[blocked.name] = {"skipped": "blocked_by_announcement"}
        break
```

Retain the Task 9 safety-note and edit-log post-pass after this loop for non-delete changes. Once announcement cleanup succeeds, later coach/weekly failures remain nonblocking; the member-facing shared root is the irreversible-delete gate.

- [ ] **Step 6: Gate the irreversible database delete**

In `delete_practice()`, call `refresh_practice_posts(practice, change_type="delete")` while the row is still queryable. Inspect `results["announcement"]`:

- allow deletion for `success: True`, `skipped: True`, or `skipped: "absent"` only when the practice has no announcement timestamp;
- return an error response and leave the row untouched for `success: False` or an unexplained absent result while a timestamp exists;
- commit the database delete only after that gate passes.

Do not let failures refreshing weekly/coach summaries block deletion; the safety concern is the member-facing root shared by another practice.

For `cancel_practice()`, the database cancellation remains authoritative once committed. Inspect the announcement result: when Slack refresh fails, return HTTP 502 with `{"success": False, "practice_cancelled": True, "error": "Practice was cancelled, but its Slack announcement did not update"}` so the coordinator sees that a retry is required. Do not roll the status back to active and do not claim a fully successful cancellation.

Capture the pre-refresh root state because a successful final delete clears the timestamp:

```python
def delete_practice(practice_id):
    practice = Practice.query.get_or_404(practice_id)
    had_root = bool(practice.slack_message_ts)
    try:
        results = refresh_practice_posts(practice, change_type="delete")
        announcement = results.get("announcement") or {}
        safe = announcement.get("success") is True
        if not had_root:
            safe = safe or announcement.get("skipped") in {True, "absent"}
        if not safe:
            return jsonify({
                "success": False,
                "error": (
                    "Slack announcement could not be updated; "
                    "practice was not deleted"
                ),
            }), 502

        db.session.delete(practice)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Practice deleted successfully",
        })
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500


def cancel_practice(practice_id):
    practice = Practice.query.get_or_404(practice_id)
    data = request.get_json() or {}
    had_root = bool(practice.slack_message_ts)
    try:
        practice.status = PracticeStatus.CANCELLED.value
        practice.cancellation_reason = data.get("reason") or "Cancelled by admin"
        db.session.commit()

        results = refresh_practice_posts(practice, change_type="cancel")
        announcement = results.get("announcement") or {}
        if had_root and announcement.get("success") is not True:
            return jsonify({
                "success": False,
                "practice_cancelled": True,
                "error": (
                    "Practice was cancelled, but its Slack announcement "
                    "did not update"
                ),
            }), 502
        return jsonify({
            "success": True,
            "message": "Practice cancelled successfully",
        })
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500
```

- [ ] **Step 7: Run cancellation and deletion suites**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_refresh.py \
  tests/slack/test_refresh_delete_exclusion.py \
  tests/slack/test_combined_announcements.py \
  tests/routes/test_admin_practice_delete.py
```

Expected: all pass.

- [ ] **Step 8: Commit the shared-post safety fix**

```bash
git add app/slack/blocks/cancellations.py app/slack/practices/cancellations.py \
  app/slack/practices/announcements.py app/slack/practices/refresh.py \
  app/routes/admin_practices.py tests/slack/test_refresh.py \
  tests/slack/test_refresh_delete_exclusion.py \
  tests/slack/test_combined_announcements.py \
  tests/routes/test_admin_practice_delete.py
git commit -m "fix(slack): preserve shared posts on cancel and delete"
```

---

### Task 13: Simplify the weekly summary around a real calendar week

**Files:**

- Modify: `app/slack/blocks/summary.py`
- Modify: `app/slack/blocks/__init__.py`
- Modify: `app/agent/routines/weekly_summary.py`
- Modify: `app/slack/practices/refresh.py`
- Create: `tests/slack/test_weekly_summary_blocks.py`
- Create: `tests/agent/test_weekly_summary.py`
- Modify: `tests/slack/test_refresh.py`
- Modify: `tests/slack/test_refresh_delete_exclusion.py`

**Interfaces:**

- `build_weekly_summary_blocks(practices, *, week_start, weather_data=None)`
- `build_weekly_summary_fallback_text(practices, *, week_start, weather_data=None)`
- `run_weekly_summary(channel_override=None, *, week_start=None)`; omitted `week_start` resolves to the coming Monday in Central time.

- [ ] **Step 1: Write pure layout tests with exact copy**

Create `tests/slack/test_weekly_summary_blocks.py` with exact-copy assertions:

- a July 13 Monday produces `Practices this week · July 13–19` even when the first/last practices occupy fewer days;
- July 27 produces `Practices this week · July 27–August 2`, and December 28, 2026 produces `Practices this week · December 28, 2026–January 3, 2027`;
- fixtures for Tuesday Run intervals and two Thursday Strength sessions produce exactly these two day sections:

  ```text
  *Tuesday, July 14 · 6:15 PM*
  Run intervals · Theodore Wirth
  Forecast: 78°F, partly cloudy

  *Thursday, July 16*
  6:05 PM · Strength · Balance Fitness
  7:20 PM · Strength · Balance Fitness
  ```

- a cancelled fixture contains `CANCELLED · Heat warning` and omits its supplied weather;
- Tuesday/Thursday/Saturday active fixtures contain `Daily details posted Tue, Thu, and Sat. · <!channel>` and never `Tue–Thu`;
- fallback text contains the full range plus every active or cancelled row.

Use an empty-week case too: preserve the full date heading and show `No practices scheduled this week.` without an empty footer.

- [ ] **Step 2: Write scheduled-routine and refresh tests**

Create the test package directory first with `mkdir -p tests/agent`.

Create `tests/agent/test_weekly_summary.py` to verify:

- Sunday, July 12 targets Monday, July 13 through Sunday, July 19;
- an explicitly supplied `week_start` makes tests deterministic;
- scheduled, confirmed, and cancelled practices are queried; unrelated statuses are not;
- weather is fetched only for active practices with non-`None` coordinates;
- the post uses the complete fallback and saves its timestamp to every included practice;
- a dry run performs no Slack write.

Extend refresh tests to assert a cancelled row stays in the rebuilt summary, a deleted row is excluded, the same `week_start` is passed to both builders, and `change_type="rsvp"` skips the weekly surface.

- [ ] **Step 3: Run the weekly tests and capture current failures**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_weekly_summary_blocks.py \
  tests/agent/test_weekly_summary.py \
  tests/slack/test_refresh.py \
  tests/slack/test_refresh_delete_exclusion.py
```

- [ ] **Step 4: Implement deterministic range formatting**

In `app/slack/blocks/summary.py`, normalize a `date` or `datetime` to its calendar date, require Monday, and derive `week_end = week_start + timedelta(days=6)`. Add a pure `_format_week_range()` that handles:

- same month/year: `July 13–19`;
- cross-month same year: `July 27–August 2`;
- cross-year: `December 28, 2026–January 3, 2027`.

Never derive the title range from the first and last practice.

- [ ] **Step 5: Render one semantic section per date**

For each represented day:

- one practice: put weekday, date, and time on the first line, then `Activity/type · Location` and optional forecast;
- multiple practices: put weekday/date once, then one `time · Activity/type · Location` line per session;
- cancellation: include `CANCELLED` and its reason in the correct chronological position;
- no weather on cancelled rows;
- no pipe-separated metadata.

Build the footer from unique non-cancelled weekdays in chronological order using abbreviated day names and natural-language commas. Preserve the existing production mention with exact copy such as `Daily details posted Tue, Thu, and Sat. · <!channel>`, isolated in the footer so the validation harness can strip it. Guard the final blocks.

Replace the existing builder with these pure helpers and public boundary:

```python
from datetime import date, datetime, timedelta
from itertools import groupby

from app.practices.interfaces import PracticeStatus
from app.slack.blocks.text import guard_fallback_text, guard_slack_blocks


def _week_date(value):
    result = value.date() if isinstance(value, datetime) else value
    if not isinstance(result, date) or result.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    return result


def _format_week_range(week_start):
    start = _week_date(week_start)
    end = start + timedelta(days=6)
    if start.year == end.year and start.month == end.month:
        return f"{start:%B} {start.day}–{end.day}"
    if start.year == end.year:
        return f"{start:%B} {start.day}–{end:%B} {end.day}"
    return (
        f"{start:%B} {start.day}, {start.year}–"
        f"{end:%B} {end.day}, {end.year}"
    )


def _status_value(practice):
    return getattr(practice.status, "value", practice.status)


def _is_cancelled(practice):
    return _status_value(practice) == PracticeStatus.CANCELLED.value


def _practice_kind(practice):
    activities = [item.name for item in (practice.activities or [])]
    types = [item.name for item in (practice.practice_types or [])]
    if len(activities) == 1 and len(types) == 1:
        if activities[0].casefold() == types[0].casefold():
            return activities[0]
        return f"{activities[0]} {types[0].lower()}"
    names = []
    seen = set()
    for name in activities + types:
        if name.casefold() not in seen:
            names.append(name)
            seen.add(name.casefold())
    return " · ".join(names) or "Practice"


def _location_name(practice):
    return practice.location.name if practice.location else "TBD"


def _forecast_line(practice, weather_data):
    if _is_cancelled(practice):
        return None
    weather = (weather_data or {}).get(practice.id)
    if not weather:
        return None
    temperature = weather.get("temp_f", weather.get("temperature_f"))
    conditions = weather.get("conditions", weather.get("conditions_summary"))
    values = []
    if temperature is not None:
        values.append(f"{round(temperature):.0f}°F")
    if conditions:
        values.append(str(conditions))
    return "Forecast: " + ", ".join(values) if values else None


def _natural_days(values):
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _weekly_day_text(day_practices, weather_data):
    first = day_practices[0]
    if len(day_practices) == 1:
        lines = [
            f"*{first.date.strftime('%A, %B %-d')} · "
            f"{first.date.strftime('%-I:%M %p')}*"
        ]
        if _is_cancelled(first):
            lines.append(
                f"CANCELLED · {first.cancellation_reason or 'Cancelled'}"
            )
            lines.append(f"{_practice_kind(first)} · {_location_name(first)}")
        else:
            lines.append(f"{_practice_kind(first)} · {_location_name(first)}")
            forecast = _forecast_line(first, weather_data)
            if forecast:
                lines.append(forecast)
        return "\n".join(lines)

    lines = [f"*{first.date.strftime('%A, %B %-d')}*"]
    for practice in day_practices:
        if _is_cancelled(practice):
            lines.append(
                f"{practice.date.strftime('%-I:%M %p')} · CANCELLED · "
                f"{practice.cancellation_reason or 'Cancelled'} · "
                f"{_practice_kind(practice)} · {_location_name(practice)}"
            )
        else:
            lines.append(
                f"{practice.date.strftime('%-I:%M %p')} · "
                f"{_practice_kind(practice)} · {_location_name(practice)}"
            )
            forecast = _forecast_line(practice, weather_data)
            if forecast:
                lines.append(forecast)
    return "\n".join(lines)


def build_weekly_summary_blocks(
    practices,
    *,
    week_start,
    weather_data=None,
):
    start = _week_date(week_start)
    ordered = sorted(practices, key=lambda item: (item.date, item.id))
    heading = f"Practices this week · {_format_week_range(start)}"
    blocks = [{
        "type": "header",
        "text": {"type": "plain_text", "text": heading, "emoji": True},
    }]
    if not ordered:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No practices scheduled this week.",
            },
        })
        return guard_slack_blocks(blocks, surface="weekly_summary")

    for _, day_items in groupby(ordered, key=lambda item: item.date.date()):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": _weekly_day_text(list(day_items), weather_data),
            },
        })

    active_days = []
    for practice in ordered:
        abbreviation = practice.date.strftime("%a")
        if not _is_cancelled(practice) and abbreviation not in active_days:
            active_days.append(abbreviation)
    if active_days:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": (
                    f"Daily details posted {_natural_days(active_days)}. "
                    "· <!channel>"
                ),
            }],
        })
    return guard_slack_blocks(blocks, surface="weekly_summary")
```

- [ ] **Step 6: Add complete weekly fallback text**

The fallback starts with the same heading and includes one plain-text line per practice with weekday/date, time, activity/type, location, and cancellation reason or forecast. It must remain useful when screen readers ignore all interior blocks. Pass it through `guard_fallback_text()`.

```python
def build_weekly_summary_fallback_text(
    practices,
    *,
    week_start,
    weather_data=None,
):
    start = _week_date(week_start)
    ordered = sorted(practices, key=lambda item: (item.date, item.id))
    lines = [f"Practices this week · {_format_week_range(start)}."]
    if not ordered:
        lines.append("No practices scheduled this week.")
    for practice in ordered:
        prefix = (
            f"{practice.date.strftime('%A, %B %-d at %-I:%M %p')} — "
            f"{_practice_kind(practice)} at {_location_name(practice)}"
        )
        if _is_cancelled(practice):
            lines.append(
                f"{prefix} — CANCELLED: "
                f"{practice.cancellation_reason or 'Cancelled'}."
            )
        else:
            forecast = _forecast_line(practice, weather_data)
            lines.append(prefix + (f" — {forecast}." if forecast else "."))
    return guard_fallback_text(
        " ".join(lines),
        surface="weekly_summary",
    )
```

- [ ] **Step 7: Query the coming Monday through Sunday**

In `app/agent/routines/weekly_summary.py`, import `date`, `datetime`, `time`, and `timedelta`; import `db` from `app.models`; import `now_central_naive` from `app.utils`; import `_get_announcement_channel`; and import both weekly block/fallback builders, then add:

```python
from datetime import date, datetime, time, timedelta

from app.models import db
from app.slack.blocks import (
    build_weekly_summary_blocks,
    build_weekly_summary_fallback_text,
)
from app.slack.practices._config import _get_announcement_channel
from app.utils import now_central_naive


def _upcoming_monday(now):
    days_ahead = (-now.weekday()) % 7
    return (now + timedelta(days=days_ahead)).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )


def _normalize_week_start(value):
    start = value if isinstance(value, datetime) else datetime.combine(value, time.min)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    if start.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    return start


def run_weekly_summary(channel_override=None, *, week_start=None):
    start = _normalize_week_start(week_start or _upcoming_monday(now_central_naive()))
    end = start + timedelta(days=7)
```

Include `SCHEDULED`, `CONFIRMED`, and `CANCELLED` in the database query. Do not fetch weather or participation counts for cancelled practices. Pass `week_start=start.date()` to both block and fallback builders and use the complete fallback in `chat_postMessage`.

Replace the current seven-days-from-now loop, participation summary, and generic Slack fallback with this core:

```python
def run_weekly_summary(channel_override=None, *, week_start=None):
    start = _normalize_week_start(
        week_start or _upcoming_monday(now_central_naive())
    )
    end = start + timedelta(days=7)
    config = load_skipper_config()
    dry_run = config.get("agent", {}).get("dry_run", True)
    practices = Practice.query.filter(
        Practice.date >= start,
        Practice.date < end,
        Practice.status.in_([
            PracticeStatus.SCHEDULED.value,
            PracticeStatus.CONFIRMED.value,
            PracticeStatus.CANCELLED.value,
        ]),
    ).order_by(Practice.date, Practice.id).all()

    weather_data = {}
    for practice in practices:
        if practice.status == PracticeStatus.CANCELLED.value:
            continue
        location = practice.location
        if not (
            location
            and location.latitude is not None
            and location.longitude is not None
        ):
            continue
        try:
            weather = get_weather_for_location(
                lat=location.latitude,
                lon=location.longitude,
                target_datetime=practice.date,
            )
            weather_data[practice.id] = {
                "temp_f": weather.temperature_f,
                "conditions": weather.conditions_summary,
            }
        except Exception as exc:
            logger.warning(
                "Weekly weather fetch failed for practice #%s: %s",
                practice.id,
                exc,
            )

    infos = [convert_practice_to_info(practice) for practice in practices]
    blocks = build_weekly_summary_blocks(
        infos,
        week_start=start.date(),
        weather_data=weather_data,
    )
    fallback = build_weekly_summary_fallback_text(
        infos,
        week_start=start.date(),
        weather_data=weather_data,
    )
    result = {
        "dry_run": dry_run,
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "practice_count": len(practices),
        "fallback": fallback,
    }
    if dry_run:
        return result

    channel_id = (
        get_channel_id_by_name(channel_override.lstrip("#"))
        if channel_override else _get_announcement_channel()
    )
    if not channel_id:
        return {**result, "slack_posted": False, "slack_error": "Channel not found"}
    try:
        response = get_slack_client().chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=fallback,
        )
        message_ts = response.get("ts")
        if not message_ts:
            return {
                **result,
                "slack_posted": False,
                "slack_error": "Slack returned no message timestamp",
            }
        for practice in practices:
            practice.slack_weekly_summary_ts = message_ts
        db.session.commit()
        return {
            **result,
            "slack_posted": True,
            "slack_message_ts": message_ts,
        }
    except Exception as exc:
        return {**result, "slack_posted": False, "slack_error": str(exc)}
```

Remove the now-unused `evaluate_practice` import and re-export `build_weekly_summary_fallback_text` from `app/slack/blocks/__init__.py`.

- [ ] **Step 8: Make refresh use the same builder contract**

In `_refresh_weekly_summary()`, query the same three statuses, continue excluding the pending deleted ID, derive Monday via `_week_bounds()`, and call both builders with that explicit date. Remove `rsvp` from the weekly `PracticeSurface.applies_to` set; native attendance reaction changes do not alter this summary.

Applicability must be checked before timestamp presence so an RSVP on a practice that was not in a weekly post returns `not_applicable`, not a noisy `absent`:

```python
def refresh(self, practice, change_type, **context):
    if change_type not in self.applies_to:
        return {"skipped": "not_applicable"}
    if not self.is_present(practice):
        return {"skipped": "absent"}
    return self._refresh_fn(practice, change_type, **context)


WEEKLY_CHANGE_TYPES = tuple(
    change_type for change_type in ALL_CHANGE_TYPES if change_type != "rsvp"
)

# Registry entry:
PracticeSurface(
    "weekly_summary",
    "slack_weekly_summary_ts",
    WEEKLY_CHANGE_TYPES,
    _refresh_weekly_summary,
)
```

Inside `_refresh_weekly_summary()`, use the same status/coordinate rules and complete fallback as the scheduled routine:

```python
week_start, week_end = _week_bounds(practice.date)
query = Practice.query.filter(
    Practice.date >= week_start,
    Practice.date < week_end,
    Practice.status.in_([
        PracticeStatus.SCHEDULED.value,
        PracticeStatus.CONFIRMED.value,
        PracticeStatus.CANCELLED.value,
    ]),
)
if change_type == "delete":
    query = query.filter(Practice.id != practice.id)
practices_for_week = query.order_by(Practice.date, Practice.id).all()

weather_data = {}
for item in practices_for_week:
    location = item.location
    if (
        item.status != PracticeStatus.CANCELLED.value
        and location
        and location.latitude is not None
        and location.longitude is not None
    ):
        try:
            weather = get_weather_for_location(
                lat=location.latitude,
                lon=location.longitude,
                target_datetime=item.date,
            )
            weather_data[item.id] = {
                "temp_f": weather.temperature_f,
                "conditions": weather.conditions_summary,
            }
        except Exception as exc:
            logger.warning(
                "Weekly weather refresh failed for practice #%s: %s",
                item.id,
                exc,
            )

infos = [convert_practice_to_info(item) for item in practices_for_week]
blocks = build_weekly_summary_blocks(
    infos,
    week_start=week_start.date(),
    weather_data=weather_data,
)
fallback = build_weekly_summary_fallback_text(
    infos,
    week_start=week_start.date(),
    weather_data=weather_data,
)
client.chat_update(
    channel=channel_id,
    ts=practice.slack_weekly_summary_ts,
    blocks=blocks,
    text=fallback,
)
```

- [ ] **Step 9: Run all weekly summary tests**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/slack/test_weekly_summary_blocks.py \
  tests/agent/test_weekly_summary.py \
  tests/slack/test_refresh.py \
  tests/slack/test_refresh_delete_exclusion.py
```

Expected: all pass.

- [ ] **Step 10: Commit the weekly summary**

```bash
git add app/slack/blocks/summary.py app/slack/blocks/__init__.py \
  app/agent/routines/weekly_summary.py app/slack/practices/refresh.py \
  tests/slack/test_weekly_summary_blocks.py tests/agent/test_weekly_summary.py \
  tests/slack/test_refresh.py tests/slack/test_refresh_delete_exclusion.py
git commit -m "feat(slack): simplify calendar-week practice summary"
```

---

### Task 14: Harden the live harness and pass the release gate

**Files:**

- Modify: `scripts/validate_announcement.py`
- Create: `tests/scripts/test_validate_announcement.py`

**Interfaces:**

- `env/bin/python scripts/validate_announcement.py post` posts synthetic scenarios only to `C07G9RTMRT3`.
- `env/bin/python scripts/validate_announcement.py teardown` removes every timestamp recorded for the active run.
- No production-channel live validation occurs in this plan.

- [ ] **Step 1: Write guardrail tests before changing the harness**

Create the test package directory first with `mkdir -p tests/scripts`.

Create `tests/scripts/test_validate_announcement.py`:

```python
def test_test_channel_is_hard_coded():
    assert validate.TEST_CHANNEL == "C07G9RTMRT3"


def test_sanitize_blocks_removes_channel_mentions_recursively():
    blocks = [{
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "Details <!channel>"}],
    }]
    assert "<!channel>" not in str(validate._sanitize_for_test(blocks))


def test_every_required_synthetic_scenario_is_registered():
    assert set(validate.SCENARIOS) >= {
        "routine", "july_no_false_headlamp", "after_sunset", "weather_alert",
        "aqi_101", "missing_workout", "no_details", "interval_evergreen",
        "multiple_plan_reactions", "overridden_plan", "empty_plan",
        "long_boundaries", "weekly_cross_month_cancelled",
        "combined_strength", "combined_mixed_cancelled",
}
```

Add these state and CLI tests beside the assertions above:

```python
import json
from types import SimpleNamespace


def test_each_successful_post_is_persisted_before_the_next_slack_call(tmp_path):
    state_path = tmp_path / "state.json"
    state = {"run_id": "test-run", "records": []}
    calls = []

    def chat_post_message(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            saved = json.loads(state_path.read_text())
            assert saved["records"] == [{
                "channel": validate.TEST_CHANNEL,
                "ts": "100.1",
                "thread_ts": None,
            }]
        return {"ts": f"100.{len(calls)}"}

    client = SimpleNamespace(chat_postMessage=chat_post_message)
    validate._post_recorded(
        client,
        state,
        state_path=state_path,
        channel=validate.TEST_CHANNEL,
        text="first",
    )
    validate._post_recorded(
        client,
        state,
        state_path=state_path,
        channel=validate.TEST_CHANNEL,
        text="second",
    )


def test_teardown_deletes_reply_before_root_and_removes_state(
    tmp_path, monkeypatch
):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "run_id": "test-run",
        "records": [
            {"channel": validate.TEST_CHANNEL, "ts": "100.1", "thread_ts": None},
            {"channel": validate.TEST_CHANNEL, "ts": "100.2", "thread_ts": "100.1"},
        ],
    }))
    deleted = []
    client = SimpleNamespace(
        chat_delete=lambda **kwargs: deleted.append(kwargs["ts"])
    )
    monkeypatch.setattr(validate, "get_slack_client", lambda: client)

    assert validate.teardown(state_path=state_path) == {"success": True}
    assert deleted == ["100.2", "100.1"]
    assert not state_path.exists()


def test_unknown_cli_command_never_runs_teardown(monkeypatch):
    monkeypatch.setattr(
        validate,
        "teardown",
        lambda: (_ for _ in ()).throw(AssertionError("teardown called")),
    )
    assert validate.main(["unknown"]) == 2
```

- [ ] **Step 2: Run the harness tests and confirm the old script fails them**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q tests/scripts/test_validate_announcement.py
```

- [ ] **Step 3: Rebuild the scenario registry around final public builders**

Use only `SimpleNamespace`/dataclass synthetic records; never query `Practice`. Give every run a visible UTC run ID. Cover the full matrix in the test above, including standalone hero/Details, weekly blocks, and combined active/mixed-cancelled blocks. Use `AnnouncementConditions` rather than old positional weather/daylight/AQI arguments.

Do not exercise admin routes or mutate production practice rows from the harness. Reaction seeding uses only the synthetic message timestamps it just created.

- [ ] **Step 4: Make a wrong destination impossible**

At startup and immediately before every Slack write:

```python
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from slack_sdk.errors import SlackApiError


TEST_CHANNEL = "C07G9RTMRT3"
STATE_FILE = Path(__file__).resolve().parents[1] / "validate_posted_ts.json"
MENTIONS = ("<!channel>", "<!here>", "<!everyone>")


def _sanitize_for_test(value):
    if isinstance(value, dict):
        return {key: _sanitize_for_test(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_test(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_for_test(item) for item in value)
    if isinstance(value, str):
        for mention in MENTIONS:
            value = value.replace(mention, "")
    return value


def _assert_test_channel(channel):
    if channel != TEST_CHANNEL:
        raise RuntimeError(f"Refusing live validation outside {TEST_CHANNEL}")


def _write_state(state, path=STATE_FILE):
    path = Path(path)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _load_state(path=STATE_FILE):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def _new_state():
    started = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {"run_id": f"{started}-{uuid4().hex[:8]}", "records": []}


def _post_recorded(client, state, *, state_path=STATE_FILE, **kwargs):
    _assert_test_channel(kwargs.get("channel"))
    if "blocks" in kwargs:
        kwargs["blocks"] = _sanitize_for_test(kwargs["blocks"])
    kwargs["text"] = _sanitize_for_test(kwargs.get("text", ""))
    response = client.chat_postMessage(**kwargs)
    state["records"].append({
        "channel": kwargs["channel"],
        "ts": response["ts"],
        "thread_ts": kwargs.get("thread_ts"),
    })
    _write_state(state, state_path)
    return response
```

Do not accept a channel CLI option or environment override. Recursively sanitize every block and fallback string to remove `<!channel>`, `<!here>`, and `<!everyone>` before posting.

- [ ] **Step 5: Make cleanup survive interrupted runs**

Store a JSON object with run ID and an ordered list of `{channel, ts, thread_ts}` records. After every successful post, append and atomically replace the state file before making the next Slack call. Teardown reads the file, deletes records in reverse order (thread replies before roots), retains failed records for retry, and removes the state file only when every delete succeeds.

If a previous state file contains undeleted timestamps, `post` refuses to begin and instructs the operator to run teardown first.

`ts` is always the timestamp of the message that teardown deletes; `thread_ts` is parent metadata used only to order replies before roots. Persist the empty state before the first Slack call, then route every scenario root and Details reply through `_post_recorded()`:

```python
def post(*, state_path=STATE_FILE):
    state_path = Path(state_path)
    if state_path.exists():
        raise RuntimeError(
            f"Validation state exists at {state_path}; run teardown first"
        )
    state = _new_state()
    _write_state(state, state_path)
    client = get_slack_client()
    for name, scenario in SCENARIOS.items():
        root_blocks, root_fallback, details = build_scenario(name, scenario)
        root = _post_recorded(
            client,
            state,
            state_path=state_path,
            channel=TEST_CHANNEL,
            blocks=root_blocks,
            text=f"[{state['run_id']}] {root_fallback}",
            unfurl_links=False,
            unfurl_media=False,
        )
        if details:
            details_blocks, details_fallback = details
            _post_recorded(
                client,
                state,
                state_path=state_path,
                channel=TEST_CHANNEL,
                thread_ts=root["ts"],
                blocks=details_blocks,
                text=f"[{state['run_id']}] {details_fallback}",
                reply_broadcast=False,
            )
        seed_scenario_reactions(client, scenario, root["ts"])
        _assert_test_channel(TEST_CHANNEL)
        permalink = client.chat_getPermalink(
            channel=TEST_CHANNEL,
            message_ts=root["ts"],
        )["permalink"]
        print(f"{name}: {permalink}")
```

`build_scenario()` is a local dispatcher over the named `SCENARIOS` registry: standalone entries return the final standalone/Details builders, `weekly_cross_month_cancelled` returns the weekly builder with `week_start=date(2026, 7, 27)`, and the two combined entries return the combined builder. It returns `(root_blocks, complete_root_fallback, details_or_none)` in all cases; there is no generic test-only fallback.

Make teardown idempotent and incremental. Stop on the first real delete failure so a parent root is never removed while a failed reply remains:

```python
def _delete_record(client, record):
    _assert_test_channel(record["channel"])
    try:
        client.chat_delete(channel=record["channel"], ts=record["ts"])
        return {"success": True}
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        if error == "message_not_found":
            return {"success": True, "skipped": "already_absent"}
        return {"success": False, "error": error}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def teardown(*, state_path=STATE_FILE):
    state_path = Path(state_path)
    if not state_path.exists():
        return {"success": True, "skipped": "no_state"}
    state = _load_state(state_path)
    records = state.get("records", [])
    replies = [item for item in reversed(records) if item.get("thread_ts")]
    roots = [item for item in reversed(records) if not item.get("thread_ts")]
    client = get_slack_client()
    for record in replies + roots:
        result = _delete_record(client, record)
        if not result["success"]:
            _write_state(state, state_path)
            return {"success": False, "record": record, **result}
        state["records"].remove(record)
        if state["records"]:
            _write_state(state, state_path)
        else:
            state_path.unlink(missing_ok=True)
    if state_path.exists():
        state_path.unlink()
    return {"success": True}
```

Use strict CLI dispatch; a missing or unknown command must exit nonzero and must never default to teardown:

```python
def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"post", "teardown"}:
        print(
            "Usage: env/bin/python scripts/validate_announcement.py "
            "{post|teardown}",
            file=sys.stderr,
        )
        return 2
    app = create_app()
    with app.app_context():
        (post if args[0] == "post" else teardown)()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Seed only the displayed synthetic reactions**

For each standalone root add `white_check_mark` and its Plan reactions. For each combined root add its saved session emojis and Plan reactions. Treat `already_reacted` as success and record/log other failures without losing cleanup state.

Call `_assert_test_channel(TEST_CHANNEL)` immediately before every `reactions_add`; scenario data supplies only displayed reaction names. A reaction error never removes or overwrites the already-persisted root record.

- [ ] **Step 7: Run all focused automated suites**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q \
  tests/practices/test_plan_reactions.py \
  tests/practices/test_plan_reaction_contracts.py \
  tests/practices/test_plan_reaction_migration.py \
  tests/routes/test_admin_practice_plan_reactions.py \
  tests/routes/test_admin_practice_delete.py \
  tests/integrations/test_daylight.py \
  tests/slack/test_slack_text.py \
  tests/slack/test_announcement_blocks.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_details_reply_wiring.py \
  tests/slack/test_reaction_rsvp.py \
  tests/slack/test_combined_announcements.py \
  tests/slack/test_refresh.py \
  tests/slack/test_refresh_delete_exclusion.py \
  tests/slack/test_weekly_summary_blocks.py \
  tests/agent/test_weekly_summary.py \
  tests/test_scheduler_practice_announcements.py \
  tests/scripts/test_validate_announcement.py
```

Expected: all pass.

- [ ] **Step 8: Run the full automated test suite**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q tests
```

Expected: all pass. If an unrelated pre-existing failure appears, record its exact command and output separately; do not weaken or delete a relevant assertion.

- [ ] **Step 9: Verify the migration on a disposable local database**

Use only the disposable `tcsc_practice_announcement_migration` clone created in Task 2. With real Slack credentials still cleared, inspect the interval/non-interval backfill, then downgrade and upgrade once:

```bash
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_practice_announcement_migration \
  SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/flask db downgrade e36bbec59bde
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_practice_announcement_migration \
  SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/flask db upgrade
```

Expected: all commands succeed and the final schema is at `c4f1a8e2d9b7`. Never run the downgrade against shared or production data.

- [ ] **Step 10: Commit the validation harness**

```bash
git add scripts/validate_announcement.py tests/scripts/test_validate_announcement.py
git commit -m "test(slack): harden announcement live validation"
```

- [ ] **Step 11: Configure and verify Slack event delivery**

In the Slack app dashboard, add `reaction_removed` beside the existing `reaction_added` bot event and confirm the app retains `reactions:read`, `reactions:write`, and message-history scopes already used by this flow. Reinstall only if Slack reports a scope/event change requiring it.

This is a manual deployment prerequisite; no manifest is tracked in this repository.

- [ ] **Step 12: Run the guarded live review only after automated green**

```bash
! rg '_bot_token\[' app/slack/bolt_app.py
env/bin/python scripts/validate_announcement.py post
```

Expected: the script prints one permalink per synthetic scenario and every message appears only in `C07G9RTMRT3`. Review desktop, mobile, notification preview, and a screen reader for:

- scan order and dividers;
- no July false headlamp warning;
- urgent exception placement;
- exact `Your Practice Plan:` copy and seeded emoji;
- empty Details omission;
- combined mixed cancellation and stable session mapping;
- weekly cross-month heading and visible cancellation;
- complete top-level fallback text.

Then clean up:

```bash
env/bin/python scripts/validate_announcement.py teardown
```

Expected: all test roots and replies are deleted and the state file is removed.

- [ ] **Step 13: Stop for product-owner sign-off**

Do not post, backfill, or refresh anything in `#announcements-practices` until the product owner explicitly approves the test-channel screenshots/messages. If changes are requested, add a failing automated regression first, implement the smallest correction, rerun Steps 7–12, and request review again.

---

## Definition of Done

- The four agreed correctness/safety fixes are covered by automated regressions.
- Activity and Workout Type Settings own reusable Plan-reaction defaults.
- Web admin create/edit and the authorized Slack creation modal prefill those defaults and permit a per-practice override or explicit empty list.
- Standalone announcements use the approved hierarchy, urgent promotion rules, intentional missing-workout state, complete fallback, conditional Details, and guarded lengths.
- Attendance add/remove behavior is limited to ✅ or a persisted combined-session emoji; Plan reactions never write RSVPs.
- Compatible two- or three-session Strength posts have stable session reactions; cancellation and deletion cannot hide a surviving practice.
- Weekly summaries cover an explicit Monday-through-Sunday week, group by day, retain cancellations, and generate their footer from active days.
- Focused and full tests pass, the migration round-trip succeeds on disposable data, and the live matrix is reviewed and removed from `C07G9RTMRT3`.
- Production announcement use remains gated on explicit product-owner approval.
