# Draft Practices & Monthly Readiness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Draft the next four weeks of practices automatically each month and nudge coaches and directors to fill in location, type and time — so that lead availability can later be collected against real practice details.

**Architecture:** A new `is_draft` flag on `Practice` marks rows that exist but are invisible to members. A single `published_practices()` query helper keeps drafts out of every announcement, summary and Skipper path. A monthly scheduler job generates drafts idempotently from the existing `practice_days` config, and a readiness digest posted to `#coord-coaches-practices` reports what is still missing.

**Tech Stack:** Flask, SQLAlchemy, Alembic, APScheduler, slack-sdk / slack-bolt, pytest with PostgreSQL fixtures.

This is Plan 1 of 3 from `docs/superpowers/specs/2026-07-25-lead-availability-design.md`. Plan 2 covers the availability poll; Plan 3 covers picker integration. This plan ships and is useful on its own — it is the monthly cadence change, and per the spec it runs live rather than shadowed.

## Global Constraints

- Python 3.12+. All new code type-annotated in the style of the surrounding module.
- Status fields are **plain strings**, not Python Enums. `UserStatus` / `UserSeasonStatus` are simple classes — never call `.value` on them. `PracticeStatus` **is** a `str, Enum`, so `PracticeStatus.SCHEDULED.value` is correct.
- `PracticeStatus` gains **no** `DRAFT` member. Draft-ness is the separate `is_draft` boolean.
- Timestamps are UTC in the database, displayed in US Central. Use `now_central_naive()` / `today_central()` from `app/utils.py`, never `datetime.now()`.
- All scheduler times are `America/Chicago`.
- Migration head at the time of writing is `d4e7f9a1b2c3`. Verify with `flask db heads` before writing the migration and use the actual head as `down_revision`.
- Tests run against a local PostgreSQL pinned by `tests/conftest.py`. Never set `DATABASE_URL` in a test.
- Run the suite with `pytest`, not `python -m pytest`.

---

### Task 1: Schema — `is_draft` and `leads_needed`

**Files:**
- Modify: `app/practices/models.py` (the `Practice` class, near the `is_dark_practice` flag ~line 172)
- Create: `migrations/versions/<generated>_add_practice_draft_and_leads_needed.py`
- Test: `tests/practices/test_practice_draft_schema.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Practice.is_draft: bool` (not null, default `False`), `Practice.leads_needed: int` (not null, default `2`). Every later task depends on both.

- [ ] **Step 1: Write the failing test**

Create `tests/practices/test_practice_draft_schema.py`:

```python
"""Practice draft flag and lead count defaults."""

from datetime import datetime

from app.practices.models import Practice


def test_new_practice_defaults_to_published_with_two_leads(db_session):
    practice = Practice(
        date=datetime(2026, 8, 4, 18, 15),
        day_of_week="Tuesday",
    )
    db_session.add(practice)
    db_session.commit()

    assert practice.is_draft is False, "practices must be published unless explicitly drafted"
    assert practice.leads_needed == 2


def test_draft_flag_round_trips(db_session):
    practice = Practice(
        date=datetime(2026, 8, 6, 18, 15),
        day_of_week="Thursday",
        is_draft=True,
        leads_needed=3,
    )
    db_session.add(practice)
    db_session.commit()
    db_session.expire(practice)

    assert practice.is_draft is True
    assert practice.leads_needed == 3
```

`tests/practices/` has no shared conftest — each file defines its own fixtures.
Follow the existing pattern exactly (see `tests/practices/test_plan_reaction_migration.py`):

```python
import pytest

from app import create_app
from app.models import db


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db
```

**Never call `db.create_all()` or `db.drop_all()` in a test.** `tests/_db_guard.py`
pins the suite to `postgresql://tcsc:tcsc@localhost:5432/tcsc_trips`, which is the
real local development database — `drop_all()` would destroy local data. No
existing test does this. Tables already exist via migrations; clean up rows you
create instead.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/practices/test_practice_draft_schema.py -v`
Expected: FAIL — `TypeError: 'is_draft' is an invalid keyword argument for Practice`

- [ ] **Step 3: Add the columns to the model**

In `app/practices/models.py`, inside `class Practice`, directly beneath the existing `is_dark_practice` column:

```python
    is_dark_practice = db.Column(db.Boolean, default=False, nullable=False)

    # Drafts exist so availability can be collected against real details before
    # members ever see the practice. Deliberately NOT a PracticeStatus member —
    # cancellation logic reads status, and overloading it would couple the two.
    is_draft = db.Column(db.Boolean, default=False, nullable=False)

    # How many leads this practice wants. 1-3, validated at the route layer.
    leads_needed = db.Column(db.Integer, default=2, nullable=False)
```

- [ ] **Step 4: Generate and edit the migration**

Run: `flask db heads` and note the current head. Then:

Run: `flask db migrate -m "add practice draft flag and leads_needed"`

Open the generated file and ensure `upgrade()` backfills existing rows so the `NOT NULL` constraint holds:

```python
def upgrade():
    op.add_column('practices', sa.Column('is_draft', sa.Boolean(), nullable=True))
    op.add_column('practices', sa.Column('leads_needed', sa.Integer(), nullable=True))
    # Existing practices are all published and historically wanted 2 leads.
    op.execute("UPDATE practices SET is_draft = FALSE WHERE is_draft IS NULL")
    op.execute("UPDATE practices SET leads_needed = 2 WHERE leads_needed IS NULL")
    op.alter_column('practices', 'is_draft', nullable=False,
                    server_default=sa.text('false'))
    op.alter_column('practices', 'leads_needed', nullable=False,
                    server_default=sa.text('2'))


def downgrade():
    op.drop_column('practices', 'leads_needed')
    op.drop_column('practices', 'is_draft')
```

- [ ] **Step 5: Apply the migration and run the test**

Run: `flask db upgrade && pytest tests/practices/test_practice_draft_schema.py -v`
Expected: PASS, 2 passed

- [ ] **Step 6: Commit**

```bash
git add app/practices/models.py migrations/versions/ tests/practices/test_practice_draft_schema.py tests/practices/conftest.py
git commit -m "feat(practices): add is_draft and leads_needed to Practice

Drafts let availability be collected against real practice details before
members see anything. Kept off PracticeStatus deliberately — cancellation
logic reads status and overloading it would couple the two concerns."
```

---

### Task 2: `published_practices()` helper and draft guards

**Files:**
- Modify: `app/practices/service.py` (add helper at module level)
- Modify: `app/scheduler.py:463`, `:522`, `:543`
- Modify: `app/slack/practices/refresh.py:331`, `:414`
- Modify: `app/agent/routines/morning_check.py:64`, `lead_verification.py:134`, `weekly_summary.py:63`, `pre_practice.py:49`, `:152`
- Test: `tests/practices/test_draft_exclusion.py`

**Interfaces:**
- Consumes: `Practice.is_draft` from Task 1.
- Produces: `published_practices() -> Query` — a `Practice` query pre-filtered to `is_draft == False`. Every task and all future practice-reading code uses this instead of `Practice.query`.

Ten call sites read practices for member-visible purposes. Editing each filter by hand invites missing one now and forgetting the rule later, so route them all through one helper and assert the rule in a test.

- [ ] **Step 1: Write the failing test**

Create `tests/practices/test_draft_exclusion.py`:

```python
"""Draft practices must never reach a member-visible surface."""

from datetime import datetime, timedelta

from app.models import db
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice
from app.practices.service import published_practices


def _make(is_draft, when):
    p = Practice(
        date=when,
        day_of_week=when.strftime("%A"),
        status=PracticeStatus.SCHEDULED.value,
        is_draft=is_draft,
    )
    db.session.add(p)
    return p


def test_published_practices_excludes_drafts(db_session):
    soon = datetime.utcnow() + timedelta(days=2)
    draft = _make(True, soon)
    live = _make(False, soon + timedelta(hours=1))
    db_session.commit()

    found = {p.id for p in published_practices().all()}
    assert live.id in found
    assert draft.id not in found, "a draft practice leaked into published_practices()"


def test_published_practices_is_chainable(db_session):
    soon = datetime.utcnow() + timedelta(days=2)
    _make(True, soon)
    live = _make(False, soon)
    db_session.commit()

    found = published_practices().filter(Practice.date >= soon).all()
    assert [p.id for p in found] == [live.id]


def test_no_member_facing_query_uses_bare_practice_query():
    """Guard the rule itself: these modules must go through the helper."""
    import pathlib

    watched = [
        "app/scheduler.py",
        "app/slack/practices/refresh.py",
        "app/agent/routines/morning_check.py",
        "app/agent/routines/lead_verification.py",
        "app/agent/routines/weekly_summary.py",
        "app/agent/routines/pre_practice.py",
    ]
    offenders = []
    for rel in watched:
        text = pathlib.Path(rel).read_text()
        for num, line in enumerate(text.splitlines(), 1):
            if "Practice.query" in line and "published_practices" not in line:
                offenders.append(f"{rel}:{num}")
    assert not offenders, (
        "these read practices directly and would include drafts; "
        f"use published_practices(): {offenders}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/practices/test_draft_exclusion.py -v`
Expected: FAIL — `ImportError: cannot import name 'published_practices'`

- [ ] **Step 3: Add the helper**

At the end of `app/practices/service.py`:

```python
def published_practices():
    """Practice query excluding drafts.

    Drafts exist so availability can be collected against real details before
    members see anything, so every member-visible read must go through here.
    Returns a Query, so callers keep chaining .filter()/.order_by() as before.
    """
    from app.practices.models import Practice

    return Practice.query.filter(Practice.is_draft.is_(False))
```

- [ ] **Step 4: Replace each call site**

In each of the ten locations, swap `Practice.query.filter(` for `published_practices().filter(` and add the import. For example, in `app/scheduler.py` around line 463:

```python
    from app.practices.service import published_practices

    practices = published_practices().filter(
        Practice.date >= now,
        Practice.date <= week_end,
        Practice.status.in_([
            PracticeStatus.SCHEDULED.value,
            PracticeStatus.CONFIRMED.value
        ]),
        Practice.slack_message_ts.is_(None)  # Not yet announced
    ).order_by(Practice.date).all()
```

Apply the identical transformation at `app/scheduler.py:522` and `:543`, `app/slack/practices/refresh.py:331` and `:414`, `app/agent/routines/morning_check.py:64`, `app/agent/routines/lead_verification.py:134`, `app/agent/routines/weekly_summary.py:63`, and `app/agent/routines/pre_practice.py:49` and `:152`. Keep every existing filter argument exactly as it is — only the leading query object changes.

- [ ] **Step 5: Run the tests**

Run: `pytest tests/practices/test_draft_exclusion.py -v`
Expected: PASS, 3 passed

Run: `pytest tests/ -q`
Expected: PASS — no regressions. Existing practice tests must be unaffected, because `is_draft` defaults to `False`.

- [ ] **Step 6: Commit**

```bash
git add app/practices/service.py app/scheduler.py app/slack/practices/refresh.py app/agent/routines/ tests/practices/test_draft_exclusion.py
git commit -m "feat(practices): route member-visible reads through published_practices()

Ten call sites read practices for announcements, summaries and Skipper.
Hand-editing ten filters invites missing one now and forgetting the rule
later, so they share one helper and a test that guards the rule itself."
```

---

### Task 3: Idempotent draft generation

**Files:**
- Create: `app/practices/drafting.py`
- Test: `tests/practices/test_drafting.py`

**Interfaces:**
- Consumes: `Practice.is_draft`, `Practice.leads_needed` (Task 1).
- Produces:
  - `generate_draft_block(start_date: date, weeks: int = 4) -> list[Practice]` — creates and commits missing draft practices, returns only newly created ones.
  - `expected_slots(start_date: date, weeks: int) -> list[datetime]` — the datetimes `practice_days` implies over the window.

Idempotency is the hazard here. A redeploy, a manual trigger, or the scheduler's misfire grace all re-run this job, and a second set of practices for the same dates would be visible chaos.

- [ ] **Step 1: Write the failing test**

Create `tests/practices/test_drafting.py`:

```python
"""Draft block generation — idempotency is the point."""

from datetime import date, datetime

import pytest

from app.models import AppConfig, db
from app.practices.drafting import expected_slots, generate_draft_block
from app.practices.models import Practice


@pytest.fixture()
def practice_days(db_session):
    AppConfig.set(
        key="practice_days",
        value=[
            {"day": "tuesday", "time": "18:15", "active": True},
            {"day": "thursday", "time": "18:15", "active": True},
            {"day": "thursday", "time": "19:20", "active": True},
            {"day": "sunday", "time": "09:00", "active": False},
        ],
        description="test",
        category="practices",
    )
    db.session.commit()


def test_expected_slots_covers_active_days_only(practice_days):
    slots = expected_slots(date(2026, 8, 3), weeks=1)  # Mon Aug 3
    assert slots == [
        datetime(2026, 8, 4, 18, 15),
        datetime(2026, 8, 6, 18, 15),
        datetime(2026, 8, 6, 19, 20),
    ], "inactive days must be skipped and times honoured"


def test_generate_creates_drafts(practice_days):
    created = generate_draft_block(date(2026, 8, 3), weeks=2)
    assert len(created) == 6
    assert all(p.is_draft is True for p in created)
    assert all(p.leads_needed == 2 for p in created)


def test_generate_is_idempotent(practice_days):
    first = generate_draft_block(date(2026, 8, 3), weeks=2)
    second = generate_draft_block(date(2026, 8, 3), weeks=2)

    assert len(first) == 6
    assert second == [], "re-running must create nothing"
    assert Practice.query.count() == 6


def test_generate_skips_slots_that_already_have_a_real_practice(practice_days):
    existing = Practice(
        date=datetime(2026, 8, 4, 18, 15),
        day_of_week="Tuesday",
        is_draft=False,
    )
    db.session.add(existing)
    db.session.commit()

    created = generate_draft_block(date(2026, 8, 3), weeks=1)
    assert len(created) == 2, "must not duplicate an already-published practice"
    assert Practice.query.filter_by(date=datetime(2026, 8, 4, 18, 15)).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/practices/test_drafting.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.practices.drafting'`

- [ ] **Step 3: Implement the module**

Create `app/practices/drafting.py`:

```python
"""Generate draft practices from the practice_days schedule.

Drafts are invisible to members (see published_practices()) and exist so
coaches and directors can fill in location, type and time before lead
availability is collected against them.
"""

from datetime import date, datetime, timedelta

from flask import current_app

from app.models import AppConfig, db
from app.practices.models import Practice

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

DEFAULT_PRACTICE_DAYS = [
    {"day": "tuesday", "time": "18:00", "active": True},
    {"day": "thursday", "time": "18:00", "active": True},
]


def expected_slots(start_date: date, weeks: int = 4) -> list[datetime]:
    """Datetimes the practice_days config implies over the window."""
    config = AppConfig.get("practice_days", DEFAULT_PRACTICE_DAYS) or []
    slots: list[datetime] = []

    for week in range(weeks):
        week_start = start_date + timedelta(days=7 * week)
        # Normalise to the Monday of that week so the window is stable.
        week_start -= timedelta(days=week_start.weekday())
        for entry in config:
            if not entry.get("active", True):
                continue
            weekday = WEEKDAYS.get(str(entry.get("day", "")).lower())
            if weekday is None:
                continue
            raw_time = str(entry.get("time", "18:00"))
            try:
                hour, minute = (int(part) for part in raw_time.split(":", 1))
            except ValueError:
                current_app.logger.warning(
                    "practice_days entry has unparseable time %r; skipping", raw_time
                )
                continue
            day = week_start + timedelta(days=weekday)
            slots.append(datetime(day.year, day.month, day.day, hour, minute))

    return sorted(slots)


def generate_draft_block(start_date: date, weeks: int = 4) -> list[Practice]:
    """Create draft practices for any slot that has none. Returns new rows only.

    Idempotent: the job re-runs on redeploy, manual trigger and APScheduler
    misfire grace, and duplicated practices would be visible chaos.
    """
    slots = expected_slots(start_date, weeks)
    if not slots:
        return []

    taken = {
        row.date
        for row in Practice.query.with_entities(Practice.date)
        .filter(Practice.date.in_(slots))
        .all()
    }

    created: list[Practice] = []
    for slot in slots:
        if slot in taken:
            continue
        practice = Practice(
            date=slot,
            day_of_week=slot.strftime("%A"),
            is_draft=True,
            leads_needed=2,
        )
        db.session.add(practice)
        created.append(practice)

    if created:
        db.session.commit()
        current_app.logger.info(
            "Drafted %d practices for %s (+%d weeks)", len(created), start_date, weeks
        )
    return created
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/practices/test_drafting.py -v`
Expected: PASS, 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/practices/drafting.py tests/practices/test_drafting.py
git commit -m "feat(practices): idempotent draft block generation

Re-running on redeploy, manual trigger or misfire grace must create
nothing — a second set of practices for the same dates would be visible
chaos, so slot collision is checked before insert."
```

---

### Task 4: Readiness evaluation

**Files:**
- Modify: `app/practices/drafting.py`
- Test: `tests/practices/test_readiness.py`

**Interfaces:**
- Consumes: `generate_draft_block` (Task 3).
- Produces:
  - `is_ready(practice: Practice) -> bool`
  - `missing_fields(practice: Practice) -> list[str]` — human-readable, e.g. `["location", "type"]`
  - `readiness_summary(practices: list[Practice]) -> dict` with keys `total`, `ready`, `incomplete` (list of `(Practice, list[str])`).

A draft is ready when it has the three things the spec says determine whether someone can lead: location, activity/workout type, and a date/time.

- [ ] **Step 1: Write the failing test**

Create `tests/practices/test_readiness.py`:

```python
"""Readiness gating — the poll must not open against incomplete drafts."""

from datetime import datetime

from app.models import db
from app.practices.drafting import is_ready, missing_fields, readiness_summary
from app.practices.models import Practice, PracticeLocation, PracticeType


def _location():
    loc = PracticeLocation(name="Theodore Wirth")
    db.session.add(loc)
    db.session.flush()
    return loc


def _type():
    t = PracticeType(name="Intervals")
    db.session.add(t)
    db.session.flush()
    return t


def test_bare_draft_is_not_ready(db_session):
    p = Practice(date=datetime(2026, 8, 4, 18, 15), day_of_week="Tuesday", is_draft=True)
    db_session.add(p)
    db_session.commit()

    assert is_ready(p) is False
    assert missing_fields(p) == ["location", "type"]


def test_draft_with_location_and_type_is_ready(db_session):
    p = Practice(date=datetime(2026, 8, 4, 18, 15), day_of_week="Tuesday", is_draft=True)
    p.location_id = _location().id
    p.practice_types = [_type()]
    db_session.add(p)
    db_session.commit()

    assert is_ready(p) is True
    assert missing_fields(p) == []


def test_summary_counts_and_lists_incomplete(db_session):
    ready = Practice(date=datetime(2026, 8, 4, 18, 15), day_of_week="Tuesday", is_draft=True)
    ready.location_id = _location().id
    ready.practice_types = [_type()]
    bare = Practice(date=datetime(2026, 8, 6, 18, 15), day_of_week="Thursday", is_draft=True)
    db_session.add_all([ready, bare])
    db_session.commit()

    summary = readiness_summary([ready, bare])
    assert summary["total"] == 2
    assert summary["ready"] == 1
    assert [p.id for p, _ in summary["incomplete"]] == [bare.id]
    assert summary["incomplete"][0][1] == ["location", "type"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/practices/test_readiness.py -v`
Expected: FAIL — `ImportError: cannot import name 'is_ready'`

- [ ] **Step 3: Implement**

Append to `app/practices/drafting.py`:

```python
def missing_fields(practice: Practice) -> list[str]:
    """Which of the details that decide whether someone can lead are unset.

    Location, type and time are exactly the three things the spec identifies as
    determining availability, so they are what gate the poll.
    """
    missing: list[str] = []
    if not practice.location_id:
        missing.append("location")
    if not practice.practice_types and not practice.activities:
        missing.append("type")
    if not practice.date:
        missing.append("time")
    return missing


def is_ready(practice: Practice) -> bool:
    """True when a draft has enough detail for someone to judge availability."""
    return not missing_fields(practice)


def readiness_summary(practices: list[Practice]) -> dict:
    """Counts plus the incomplete drafts and what each is missing."""
    incomplete = [(p, missing_fields(p)) for p in practices if not is_ready(p)]
    return {
        "total": len(practices),
        "ready": len(practices) - len(incomplete),
        "incomplete": sorted(incomplete, key=lambda pair: pair[0].date),
    }
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/practices/test_readiness.py -v`
Expected: PASS, 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/practices/drafting.py tests/practices/test_readiness.py
git commit -m "feat(practices): readiness evaluation for draft practices

Location, type and time are what decide whether someone can lead, so they
are what gate opening the availability poll."
```

---

### Task 5: Readiness digest Block Kit

**Files:**
- Create: `app/slack/blocks/practice_drafts.py`
- Modify: `app/slack/blocks/__init__.py` (re-export, matching the existing barrel pattern)
- Test: `tests/slack/test_practice_draft_blocks.py`

**Interfaces:**
- Consumes: `readiness_summary` (Task 4).
- Produces: `build_readiness_digest_blocks(summary: dict, start_label: str, end_label: str) -> list[dict]`

- [ ] **Step 1: Write the failing test**

Create `tests/slack/test_practice_draft_blocks.py`:

```python
"""Readiness digest blocks."""

import json
from datetime import datetime
from types import SimpleNamespace

from app.slack.blocks.practice_drafts import build_readiness_digest_blocks


def _practice(day, hour, minute):
    return SimpleNamespace(
        id=day, date=datetime(2026, 8, day, hour, minute),
        location=None, practice_types=[], activities=[],
    )


def test_digest_reports_ready_count_and_blocks_poll():
    summary = {
        "total": 12, "ready": 8,
        "incomplete": [(_practice(11, 18, 15), ["location", "type"])],
    }
    blocks = build_readiness_digest_blocks(summary, "Jul 21", "Aug 13")
    text = json.dumps(blocks)

    assert "8 of 12 ready" in text
    assert "Tue 8/11" in text
    assert "location" in text and "type" in text


def test_fully_ready_digest_says_poll_can_open():
    summary = {"total": 12, "ready": 12, "incomplete": []}
    blocks = build_readiness_digest_blocks(summary, "Jul 21", "Aug 13")
    text = json.dumps(blocks)

    assert "12 of 12 ready" in text
    assert "ready to send" in text.lower()


def test_each_incomplete_row_opens_the_existing_edit_modal():
    summary = {
        "total": 12, "ready": 10,
        "incomplete": [(_practice(11, 18, 15), ["location"]),
                       (_practice(13, 19, 20), ["type"])],
    }
    blocks = build_readiness_digest_blocks(summary, "Jul 21", "Aug 13")
    buttons = [b["accessory"] for b in blocks if b.get("accessory")]

    assert len(buttons) == 2
    assert all(b["action_id"] == "edit_practice_full" for b in buttons), \
        "reuse the existing handler rather than adding a new one"
    assert [b["value"] for b in buttons] == ["11", "13"], \
        "the handler reads the practice id from action['value']"


def test_digest_stays_within_slack_block_limit():
    incomplete = [(_practice(4 + i % 20, 18, 15), ["location"]) for i in range(40)]
    summary = {"total": 60, "ready": 20, "incomplete": incomplete}
    blocks = build_readiness_digest_blocks(summary, "Jul 21", "Aug 13")

    assert len(blocks) <= 50, "Slack rejects messages over 50 blocks"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/slack/test_practice_draft_blocks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.slack.blocks.practice_drafts'`

- [ ] **Step 3: Implement**

Create `app/slack/blocks/practice_drafts.py`:

```python
"""Block Kit for the monthly draft readiness digest."""

# Each incomplete draft gets its own section so it can carry an edit button.
# Budget: header + summary + MAX_LISTED rows + 2 context blocks, well under 50.
MAX_LISTED = 12


def _row_text(practice, missing: list[str]) -> str:
    when = practice.date.strftime("%a %-m/%-d · %-I:%M%p").replace("PM", "p").replace("AM", "a")
    return f":red_circle: *{when}* — _no {', no '.join(missing)}_"


def build_readiness_digest_blocks(summary: dict, start_label: str, end_label: str) -> list[dict]:
    """Digest posted to the coaches/directors channel after drafting a block.

    Each incomplete row carries a button wired to the existing
    ``edit_practice_full`` action, which reads the practice id from
    ``action["value"]`` — so no new interaction handler is needed.
    """
    total = summary["total"]
    ready = summary["ready"]
    incomplete = summary["incomplete"]

    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text",
         "text": f"{total} practices drafted · {start_label} – {end_label}", "emoji": True}},
    ]

    if not incomplete:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{ready} of {total} ready* — the availability poll is *ready to send*."}})
        return blocks

    blocks.append({"type": "section", "text": {"type": "mrkdwn",
        "text": f"*{ready} of {total} ready* · {len(incomplete)} still need details. "
                "The availability poll unlocks once all of them are set."}})

    for practice, missing in incomplete[:MAX_LISTED]:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": _row_text(practice, missing)},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Fill in", "emoji": True},
                "action_id": "edit_practice_full",
                "value": str(practice.id),
            },
        })

    if len(incomplete) > MAX_LISTED:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"_+{len(incomplete) - MAX_LISTED} more not shown._"}]})

    blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
        "text": ":bulb: Leads pick availability from location, type and time — "
                "these are what's blocking the poll."}]})
    return blocks
```

Then add to `app/slack/blocks/__init__.py`, following the existing re-export style:

```python
from app.slack.blocks.practice_drafts import build_readiness_digest_blocks
```

and add `"build_readiness_digest_blocks"` to that module's `__all__`.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/slack/test_practice_draft_blocks.py -v`
Expected: PASS, 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/slack/blocks/practice_drafts.py app/slack/blocks/__init__.py tests/slack/test_practice_draft_blocks.py
git commit -m "feat(slack): readiness digest blocks for drafted practice blocks"
```

---

### Task 6: Digest posting

**Files:**
- Create: `app/slack/practices/drafts.py`
- Modify: `app/slack/practices/__init__.py` (barrel re-export + `__all__`)
- Test: `tests/slack/test_practice_draft_posting.py`

**Interfaces:**
- Consumes: `build_readiness_digest_blocks` (Task 5), `readiness_summary` (Task 4).
- Produces: `post_readiness_digest(practices: list, start_label: str, end_label: str) -> dict` returning `{"success": bool, "ts": str}` or `{"success": False, "error": str}`.

- [ ] **Step 1: Write the failing test**

Create `tests/slack/test_practice_draft_posting.py`:

```python
"""Readiness digest posting."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _practice(day):
    return SimpleNamespace(
        id=day, date=datetime(2026, 8, day, 18, 15),
        location=None, practice_types=[], activities=[],
    )


def test_posts_to_the_coaches_channel(app):
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.return_value = {"ok": True, "ts": "1785000000.1"}

    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([_practice(4)], "Jul 21", "Aug 13")

    assert result["success"] is True
    assert result["ts"] == "1785000000.1"
    kwargs = client.chat_postMessage.call_args.kwargs
    from app.slack.practices._config import COLLAB_CHANNEL_ID
    assert kwargs["channel"] == COLLAB_CHANNEL_ID
    assert kwargs["blocks"], "digest must carry blocks"
    assert kwargs["text"], "fallback text is required for notifications and screen readers"


def test_slack_failure_is_reported_not_raised(app):
    from slack_sdk.errors import SlackApiError

    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.side_effect = SlackApiError(
        "boom", response={"error": "channel_not_found"}
    )

    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([_practice(4)], "Jul 21", "Aug 13")

    assert result["success"] is False
    assert result["error"] == "channel_not_found"


def test_empty_practice_list_posts_nothing(app):
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([], "Jul 21", "Aug 13")

    assert result["success"] is False
    client.chat_postMessage.assert_not_called()
```

If `tests/slack/` has no `app` fixture, reuse the one added in Task 1 by creating `tests/slack/conftest.py` with the same contents.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/slack/test_practice_draft_posting.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.slack.practices.drafts'`

- [ ] **Step 3: Implement**

Create `app/slack/practices/drafts.py`:

```python
"""Posting the monthly draft readiness digest."""

from flask import current_app
from slack_sdk.errors import SlackApiError

from app.practices.drafting import readiness_summary
from app.slack.blocks.practice_drafts import build_readiness_digest_blocks
from app.slack.client import get_slack_client
from app.slack.practices._config import COLLAB_CHANNEL_ID


def post_readiness_digest(practices: list, start_label: str, end_label: str) -> dict:
    """Post the digest to the coaches/directors channel.

    Never raises — a Slack outage must not fail the drafting job that produced
    perfectly good practices.
    """
    if not practices:
        return {"success": False, "error": "no practices to report"}

    summary = readiness_summary(practices)
    blocks = build_readiness_digest_blocks(summary, start_label, end_label)
    fallback = (
        f"{summary['total']} practices drafted for {start_label} – {end_label}: "
        f"{summary['ready']} ready, {len(summary['incomplete'])} need details"
    )

    try:
        response = get_slack_client().chat_postMessage(
            channel=COLLAB_CHANNEL_ID,
            blocks=blocks,
            text=fallback,
        )
        return {"success": True, "ts": response["ts"]}
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        current_app.logger.error("Readiness digest failed to post: %s", error)
        return {"success": False, "error": error}
```

Add to `app/slack/practices/__init__.py`, matching the existing barrel style:

```python
from app.slack.practices.drafts import post_readiness_digest
```

and append `"post_readiness_digest"` to `__all__`.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/slack/test_practice_draft_posting.py -v`
Expected: PASS, 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/slack/practices/drafts.py app/slack/practices/__init__.py tests/slack/test_practice_draft_posting.py
git commit -m "feat(slack): post monthly draft readiness digest

Failures are reported, never raised — a Slack outage must not fail the
drafting job that already produced perfectly good practices."
```

---

### Task 7: Scheduler jobs

**Files:**
- Modify: `app/scheduler.py` (job functions near the other `run_*_job` definitions; registration inside `init_scheduler`)
- Test: `tests/test_scheduler_draft_jobs.py`

**Interfaces:**
- Consumes: `generate_draft_block` (Task 3), `readiness_summary` / `is_ready` (Task 4), `post_readiness_digest` (Task 6).
- Produces: `run_practice_block_bootstrap_job(app)`, `run_practice_readiness_nudge_job(app)`, and registered job ids `practice_block_bootstrap` and `practice_block_readiness_nudge`.

The nudge job must stay quiet when there is nothing to say — a daily "all good" post trains people to ignore the channel.

- [ ] **Step 1: Write the failing test**

Create `tests/test_scheduler_draft_jobs.py`:

```python
"""Draft bootstrap and readiness nudge jobs."""

from datetime import datetime
from unittest.mock import patch

from app.models import db
from app.practices.models import Practice


def test_bootstrap_drafts_and_posts_digest(app):
    from app.scheduler import run_practice_block_bootstrap_job

    with patch("app.scheduler.generate_draft_block") as gen, \
         patch("app.scheduler.post_readiness_digest") as post:
        gen.return_value = [
            Practice(date=datetime(2026, 8, 4, 18, 15), day_of_week="Tuesday", is_draft=True)
        ]
        run_practice_block_bootstrap_job(app)

    gen.assert_called_once()
    post.assert_called_once()


def test_bootstrap_skips_digest_when_nothing_was_drafted(app):
    from app.scheduler import run_practice_block_bootstrap_job

    with patch("app.scheduler.generate_draft_block", return_value=[]), \
         patch("app.scheduler.post_readiness_digest") as post:
        run_practice_block_bootstrap_job(app)

    post.assert_not_called(), "a no-op run must not post"


def test_readiness_nudge_is_silent_when_all_drafts_are_ready(app):
    from app.scheduler import run_practice_readiness_nudge_job

    with app.app_context():
        ready = Practice(date=datetime(2026, 8, 4, 18, 15), day_of_week="Tuesday",
                         is_draft=True, location_id=None)
        db.session.add(ready)
        db.session.commit()

    with patch("app.scheduler.post_readiness_digest") as post, \
         patch("app.scheduler.is_ready", return_value=True):
        run_practice_readiness_nudge_job(app)

    post.assert_not_called(), "a daily all-clear post trains people to ignore the channel"


def test_both_jobs_are_registered():
    from app.scheduler import init_scheduler

    with patch("app.scheduler.scheduler") as sched, \
         patch("app.scheduler.is_main_worker", return_value=True):
        sched.running = False
        from flask import Flask
        init_scheduler(Flask(__name__))

    registered = {call.kwargs.get("id") for call in sched.add_job.call_args_list}
    assert "practice_block_bootstrap" in registered
    assert "practice_block_readiness_nudge" in registered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler_draft_jobs.py -v`
Expected: FAIL — `ImportError: cannot import name 'run_practice_block_bootstrap_job'`

- [ ] **Step 3: Add the job functions**

In `app/scheduler.py`, alongside the other `run_*_job` functions, add the imports at module level:

```python
from app.practices.drafting import generate_draft_block, is_ready
from app.slack.practices.drafts import post_readiness_digest
```

and the jobs:

```python
DRAFT_BLOCK_WEEKS = 4


def run_practice_block_bootstrap_job(app):
    """Monthly: draft the next four weeks and report what still needs details."""
    with app.app_context():
        from app.utils import today_central

        start = today_central()
        created = generate_draft_block(start, weeks=DRAFT_BLOCK_WEEKS)
        if not created:
            app.logger.info("Draft bootstrap: nothing to create, block already drafted")
            return

        end = max(p.date for p in created)
        result = post_readiness_digest(
            created,
            start.strftime("%b %-d"),
            end.strftime("%b %-d"),
        )
        if not result.get("success"):
            app.logger.warning(
                "Drafted %d practices but the digest failed: %s",
                len(created), result.get("error"),
            )


def run_practice_readiness_nudge_job(app):
    """Daily: re-post the digest only while drafts are still incomplete."""
    with app.app_context():
        from datetime import timedelta

        from app.practices.models import Practice
        from app.utils import today_central

        start = today_central()
        horizon = start + timedelta(weeks=DRAFT_BLOCK_WEEKS)
        drafts = Practice.query.filter(
            Practice.is_draft.is_(True),
            Practice.date >= start,
            Practice.date <= horizon,
        ).order_by(Practice.date).all()

        if not drafts or all(is_ready(p) for p in drafts):
            app.logger.info("Readiness nudge: nothing outstanding, staying quiet")
            return

        end = max(p.date for p in drafts)
        post_readiness_digest(drafts, start.strftime("%b %-d"), end.strftime("%b %-d"))
```

- [ ] **Step 4: Register the jobs**

Inside `init_scheduler`, alongside the existing `scheduler.add_job` calls:

```python
    # Monthly: draft the next 4 weeks of practices on the 1st at 8:00 AM
    scheduler.add_job(
        func=run_practice_block_bootstrap_job,
        args=[app],
        trigger=CronTrigger(
            day=1,
            hour=8,
            minute=0,
            timezone='America/Chicago'
        ),
        id='practice_block_bootstrap',
        name='Practice Block Bootstrap',
        replace_existing=True,
        misfire_grace_time=7200  # 2 hour grace; generation is idempotent
    )

    # Daily: nudge coaches/directors while drafted practices lack details
    scheduler.add_job(
        func=run_practice_readiness_nudge_job,
        args=[app],
        trigger=CronTrigger(
            hour=9,
            minute=0,
            timezone='America/Chicago'
        ),
        id='practice_block_readiness_nudge',
        name='Practice Readiness Nudge',
        replace_existing=True,
        misfire_grace_time=3600
    )
```

- [ ] **Step 5: Run the tests**

Run: `pytest tests/test_scheduler_draft_jobs.py -v`
Expected: PASS, 4 passed

Run: `pytest tests/ -q`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add app/scheduler.py tests/test_scheduler_draft_jobs.py
git commit -m "feat(scheduler): monthly draft bootstrap and daily readiness nudge

Bootstrap carries a 2h misfire grace because generation is idempotent.
The nudge stays silent when every draft is ready — a daily all-clear post
trains people to ignore the channel."
```

---

### Task 8: Admin form — `leads_needed`, and retire assists

**Files:**
- Modify: `app/routes/admin_practices.py` (`create_practice` ~line 318, `edit_practice` ~line 447)
- Modify: `app/templates/admin/practices/detail.html` and the practice create/edit form template
- Test: `tests/routes/test_admin_practice_leads_needed.py`

**Interfaces:**
- Consumes: `Practice.leads_needed` (Task 1).
- Produces: `create_practice` and `edit_practice` accept and validate `leads_needed`; `assist_ids` is no longer written.

Existing `role='assist'` rows stay readable so history is intact; the role simply stops being offered and stops being written.

- [ ] **Step 1: Write the failing test**

Create `tests/routes/test_admin_practice_leads_needed.py`:

```python
"""leads_needed validation and assists retirement."""

import pytest

from app.practices.models import Practice, PracticeLead


@pytest.mark.parametrize("value", [0, 4, -1, "two"])
def test_invalid_leads_needed_is_rejected(admin_client, value):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-08-04T18:15:00",
        "location_id": 1,
        "leads_needed": value,
    })
    assert response.status_code == 400
    assert "leads_needed" in response.get_json()["error"].lower()


def test_valid_leads_needed_is_stored(admin_client, db_session):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-08-04T18:15:00",
        "location_id": 1,
        "leads_needed": 3,
    })
    assert response.status_code == 200
    practice = Practice.query.get(response.get_json()["practice_id"])
    assert practice.leads_needed == 3


def test_leads_needed_defaults_to_two_when_omitted(admin_client):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-08-04T18:15:00",
        "location_id": 1,
    })
    assert response.status_code == 200
    practice = Practice.query.get(response.get_json()["practice_id"])
    assert practice.leads_needed == 2


def test_assist_ids_are_ignored(admin_client):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-08-04T18:15:00",
        "location_id": 1,
        "assist_ids": [1, 2],
    })
    assert response.status_code == 200
    practice_id = response.get_json()["practice_id"]
    assists = PracticeLead.query.filter_by(practice_id=practice_id, role="assist").count()
    assert assists == 0, "the assist role is retired; no new assist rows may be written"
```

`admin_client` must be a test client with an authenticated admin session. If `tests/routes/` has no such fixture, add one to `tests/routes/conftest.py` following whatever session-stubbing pattern the existing route tests in that directory already use.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/routes/test_admin_practice_leads_needed.py -v`
Expected: FAIL — invalid values are accepted (200 instead of 400) and assist rows are created.

- [ ] **Step 3: Validate and store `leads_needed`; drop assist writes**

In `app/routes/admin_practices.py`, add near the other validation in `create_practice`, after the `location_id` check:

```python
    leads_needed = data.get('leads_needed', 2)
    if not isinstance(leads_needed, int) or isinstance(leads_needed, bool) \
            or not 1 <= leads_needed <= 3:
        return jsonify({
            'error': 'leads_needed must be a whole number from 1 to 3',
            'field': 'leads_needed',
        }), 400
```

Pass it into the constructor:

```python
        practice = Practice(
            date=date,
            day_of_week=date.strftime('%A'),
            location_id=data['location_id'],
            social_location_id=data.get('social_location_id'),
            status=PracticeStatus.SCHEDULED.value,
            workout_description=data.get('workout_description'),
            logistics_notes=data.get('logistics_notes') or None,
            plan_reactions=plan_reactions,
            is_dark_practice=data.get('is_dark_practice', False),
            leads_needed=leads_needed,
        )
```

Delete the assists block entirely:

```python
        # Assists are retired. Historical role='assist' rows stay readable, but
        # no new ones are written and the role is no longer offered in the UI.
```

Apply the same validation and assignment in `edit_practice`, and remove its assist handling too.

- [ ] **Step 4: Update the templates**

In the practice create/edit form, remove the assists picker and add a leads-needed selector beside the leads picker:

```html
<label for="leads-needed">Leads needed</label>
<select id="leads-needed" name="leads_needed">
  <option value="1">1</option>
  <option value="2" selected>2</option>
  <option value="3">3</option>
</select>
```

Ensure the JS that builds the create/edit payload sends `leads_needed` as a number and no longer sends `assist_ids`.

- [ ] **Step 5: Run the tests**

Run: `pytest tests/routes/test_admin_practice_leads_needed.py -v`
Expected: PASS, 7 passed

Run: `pytest tests/ -q`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add app/routes/admin_practices.py app/templates/admin/practices/ tests/routes/test_admin_practice_leads_needed.py
git commit -m "feat(admin): leads_needed 1-3 on practices, retire the assist role

Historical role='assist' rows stay readable so past schedules still render;
the role is simply no longer offered or written."
```

---

## Verification

After all tasks:

```bash
pytest tests/ -q
flask db upgrade
```

Then confirm the drafting path end to end against the local database:

```bash
flask shell
>>> from app.practices.drafting import generate_draft_block, readiness_summary
>>> from datetime import date
>>> created = generate_draft_block(date.today(), weeks=4)
>>> len(created)
>>> readiness_summary(created)
>>> generate_draft_block(date.today(), weeks=4)   # must return []
```

The second call returning `[]` is the idempotency guarantee the whole job rests on.

## What this plan deliberately does not do

- No availability poll, reaction capture, or nudging (Plan 2)
- No lead picker changes, load counts, or staleness (Plan 3)
- No coverage thread reply — cut during Phase 0 review
- No shadow mode — per the spec, the director-facing bootstrap and digest run live from day one, because adapting to a monthly cadence is a behavior change that cannot be rehearsed in a shadow channel
