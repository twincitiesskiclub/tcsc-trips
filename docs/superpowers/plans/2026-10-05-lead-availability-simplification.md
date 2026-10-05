# Lead Availability Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the practices team's side of lead availability so every two weeks the team opens a poll, sees coverage and assigns leads from one Slack post, and bot-created practices become member-visible on their own once they have a location and a type.

**Architecture:** Replace, don't adapt: v1 never ran (0 polls in prod). Delete the monthly drafting job, readiness digest, publish buttons and shadow mode. Add one daily block job, one live block post per two-week block in #collab-coaches-practices, an Assign modal, and `publish_if_ready()` on every save path. New code lives in `app/practices/blocks.py` (logic, Slack calls) and `app/slack/blocks/block_post.py` (pure Block Kit). Everything else is small edits to existing files.

**Tech Stack:** Flask, SQLAlchemy, Alembic (Flask-Migrate), PostgreSQL 18, APScheduler, Slack Bolt + slack_sdk, pytest, node:test + jsdom.

**Spec:** `docs/superpowers/specs/2026-10-05-lead-availability-simplification-design.md` (read it before starting; this plan argues from it).

## Global Constraints

- Build principles (spec): replace, don't adapt; no backward compatibility, no data backfill, no feature flags; reuse `generate_draft_block`, `poll_rows`, the reaction handler, `reconcile_poll`, the nudge rules, `refresh_practice_posts`, the full edit modal; polls keep three statuses `draft`, `open`, `closed`; concurrency uses a database row lock; each phase removes about as much code as it adds.
- Blocks: two weeks, Monday to Sunday, anchored on `2026-10-26`, AppConfig key `lead_availability.block_anchor`. Never create a block starting before the anchor.
- Visibility: a bot-created practice becomes visible when `publish_blockers()` is empty (location, a practice type or activity, not cancelled). One way. Hand-created practices keep today's behavior (visible immediately).
- Coaches are shown on block post rows and never counted toward `leads_needed`.
- All Slack copy: no em dashes. Use "hidden from members", never "draft", in team-facing copy.
- Every Slack call follows the never-raise pattern and logs at WARNING or above on failure (Render shows only WARNING+).
- Timestamps: `now_central_naive()` / `today_central()` from `app/utils.py`, never `datetime.now()`.
- Tests: read `tests/practices/conftest.py` first. Real local DB, year 2099+ dates, `"TEST "` prefixes, `try/finally` cleanup with `db.session.rollback()` first, ids captured as plain ints before the `try`, ORM deletes only, save/restore any `AppConfig` row touched. No `create_all`/`drop_all`.
- Slack IDs: `COLLAB_CHANNEL_ID = "C04AUHEDBSR"` (#collab-coaches-practices), `COORD_CHANNEL_ID = "C02J4DGCFL2"` (#coord-practices-leads-assists), both in `app/slack/practices/_config.py`.
- Each phase is its own PR, stacked: Phase A on `lead-availability-simplify`, Phase B on `lead-availability-blocks` (branched from A), Phase C on `lead-availability-assign` (branched from B). Nothing merges until Rob has seen the demo (Task C5). Phase B must be deployed before Mon 2026-10-19 09:00 Central, or the block job run by hand that day.

## Review Focus

- **The first Monday after deploy.** Prod already has drafts through Nov 26 (ids 121-142). The block job must still create the poll row and post the block post when `generate_draft_block` returns `[]`. Pinned in Task B3.
- **Two people press Open poll within a second.** Exactly one leads poll may post; the second clicker gets a clear message. Pinned in Task B3 (lock test and second-open test).
- **A session filled in on its own day.** A Tuesday 18:15 session completed at 10:00 Tuesday must be announced immediately, with strength sessions still combined. Pinned in Task A1.
- **A practice deleted from an open poll, then a new one added.** The new session must never reuse the deleted session's letter. Pinned in Task C1.
- **Deploy lands mid-block (Oct 12 to 25).** The block job must not create an Oct 12 block with an Open poll button; that block is created only by the cutover script as a never-posted closed poll. Pinned in Task B3 (anchor test) and Task C4.

---

## Task 0: Worktree environment

**Files:** none committed.

- [ ] **Step 1: Copy local env files into the worktree**

```bash
cd /workspace/tcsc-trips/.worktrees/lead-availability-simplify
cp /workspace/tcsc-trips/.env .env
cp /workspace/tcsc-trips/.env.uiaudit .env.uiaudit 2>/dev/null || true
git status --short   # both must be ignored (no output for them)
```

- [ ] **Step 2: Check the local database and its migration head**

```bash
ss -tln | grep 5432 || echo "no postgres on 5432: start it (see memory note pgforward-safe-relay) before continuing"
docker exec tcsc-postgres psql -U tcsc -d tcsc_trips -tAc "select version_num from alembic_version"
grep -n "HEAD_REVISION =" tests/practices/test_practice_migration_release.py
```

Expected: the dev DB revision. If it is not `7a1c5e9d3b20` (main's head), the dev DB is on another branch's schema (open PR #237 hand-migrated it). In that case run every test command in this plan with `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test` and bring that database to head first:

```bash
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test TCSC_MIGRATION_ONLY=1 SLACK_APP_TOKEN= /workspace/tcsc-trips/.venv/bin/flask db upgrade
```

Write the chosen URL down; this plan calls it `$TEST_DB`. Test commands below are written as `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest ...`.

- [ ] **Step 3: Record the baseline**

```bash
export TEST_DB=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips   # or tcsc_trips_test per Step 2
DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices tests/slack tests/routes tests/test_scheduler_lead_availability.py tests/test_scheduler_draft_jobs.py -q -x --ignore=tests/wix_scrape 2>&1 | tail -5
npm run test:practice-reactions 2>&1 | tail -5
```

Expected: record pass/fail counts. Any failure here is pre-existing; note it so later tasks don't chase it.

---

# Phase A: Visible when ready, and removals

Branch: `lead-availability-simplify` (already checked out in this worktree).

### Task A1: `publish_if_ready` and late announcements

**Files:**
- Modify: `app/practices/publishing.py` (rewrite)
- Modify: `app/scheduler.py` (`run_practice_announcements_job` signature and `now`)
- Test: `tests/practices/test_publishing.py` (rewrite)

**Interfaces:**
- Produces: `publish_blockers(practice) -> list[str]` (unchanged), `announcement_run_time(practice_date: datetime) -> datetime`, `publish_if_ready(practice, *, now: datetime | None = None) -> bool`.
- Produces: `run_practice_announcements_job(app, channel_override=None, now_override: datetime | None = None)`.

- [ ] **Step 1: Write the failing tests**

Replace `tests/practices/test_publishing.py` entirely with:

```python
"""A bot-created practice becomes member-visible on its own once it has a
location and a type. There is no publish button.

Read tests/practices/conftest.py before adding to this file: this runs
against the real local dev database.
"""

from datetime import datetime

import pytest

from app.models import db
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice, PracticeLocation, PracticeType
from app.practices.publishing import (
    announcement_run_time,
    publish_blockers,
    publish_if_ready,
)
from app.practices.service import published_practices

_PREFIX = "TEST publishing"


@pytest.fixture()
def location(db_session):
    db.session.rollback()
    row = PracticeLocation(name=f"{_PREFIX} Location")
    db.session.add(row)
    db.session.commit()
    row_id = row.id
    yield row
    db.session.rollback()
    stale = db.session.get(PracticeLocation, row_id)
    if stale is not None:
        db.session.delete(stale)
    db.session.commit()


@pytest.fixture()
def practice_type(db_session):
    db.session.rollback()
    row = PracticeType.query.filter_by(name=f"{_PREFIX} Type").first()
    if row is None:
        row = PracticeType(name=f"{_PREFIX} Type")
        db.session.add(row)
        db.session.commit()
    row_id = row.id
    yield row
    db.session.rollback()
    stale = db.session.get(PracticeType, row_id)
    if stale is not None:
        db.session.delete(stale)
    db.session.commit()


def _make_hidden(location=None, practice_type=None, *, when=None):
    when = when or datetime(2099, 3, 3, 18, 15)
    practice = Practice(
        date=when,
        day_of_week=when.strftime("%A"),
        is_draft=True,
        leads_needed=2,
        location_id=location.id if location else None,
        logistics_notes=f"{_PREFIX} row",
    )
    if practice_type is not None:
        practice.practice_types = [practice_type]
    db.session.add(practice)
    db.session.commit()
    return practice


def _delete_practice(practice_id):
    db.session.rollback()
    practice = db.session.get(Practice, practice_id)
    if practice is not None:
        db.session.delete(practice)
    db.session.commit()


@pytest.fixture(autouse=True)
def announce_calls(monkeypatch):
    """Never post from these tests; record late-announcement requests."""
    calls = []

    def fake_job(app, channel_override=None, now_override=None):
        calls.append(now_override)

    monkeypatch.setattr("app.scheduler.run_practice_announcements_job", fake_job)
    return calls


def test_a_complete_hidden_practice_becomes_member_visible(db_session, location, practice_type):
    practice = _make_hidden(location, practice_type)
    practice_id = practice.id
    try:
        assert published_practices().filter(Practice.id == practice_id).first() is None
        assert publish_if_ready(practice) is True
        assert published_practices().filter(Practice.id == practice_id).first() is not None
    finally:
        _delete_practice(practice_id)


def test_missing_location_stays_hidden(db_session, practice_type):
    practice = _make_hidden(None, practice_type)
    practice_id = practice.id
    try:
        assert publish_if_ready(practice) is False
        assert db.session.get(Practice, practice_id).is_draft is True
    finally:
        _delete_practice(practice_id)


def test_missing_type_stays_hidden(db_session, location):
    practice = _make_hidden(location, None)
    practice_id = practice.id
    try:
        assert publish_if_ready(practice) is False
        assert publish_blockers(practice) == ["type"]
    finally:
        _delete_practice(practice_id)


def test_cancelled_stays_hidden(db_session, location, practice_type):
    practice = _make_hidden(location, practice_type)
    practice_id = practice.id
    try:
        practice.status = PracticeStatus.CANCELLED.value
        db.session.commit()
        assert publish_if_ready(practice) is False
        assert db.session.get(Practice, practice_id).is_draft is True
    finally:
        _delete_practice(practice_id)


def test_visibility_is_one_way(db_session, location, practice_type):
    practice = _make_hidden(location, practice_type)
    practice_id = practice.id
    try:
        publish_if_ready(practice)
        practice.location_id = None
        db.session.commit()
        assert publish_if_ready(practice) is False
        assert db.session.get(Practice, practice_id).is_draft is False
    finally:
        _delete_practice(practice_id)


def test_already_visible_is_a_no_op(db_session, location, practice_type):
    practice = _make_hidden(location, practice_type)
    practice_id = practice.id
    try:
        practice.is_draft = False
        db.session.commit()
        assert publish_if_ready(practice) is False
    finally:
        _delete_practice(practice_id)


def test_announcement_run_time_evening_and_morning():
    assert announcement_run_time(datetime(2099, 3, 3, 18, 15)) == datetime(2099, 3, 3, 8, 0)
    assert announcement_run_time(datetime(2099, 3, 3, 12, 0)) == datetime(2099, 3, 3, 8, 0)
    assert announcement_run_time(datetime(2099, 3, 3, 9, 0)) == datetime(2099, 3, 2, 20, 0)


def test_filled_on_its_own_day_is_announced_now(db_session, location, practice_type, announce_calls):
    practice = _make_hidden(location, practice_type, when=datetime(2099, 3, 3, 18, 15))
    practice_id = practice.id
    try:
        publish_if_ready(practice, now=datetime(2099, 3, 3, 10, 0))
        assert announce_calls == [datetime(2099, 3, 3, 8, 0)]
    finally:
        _delete_practice(practice_id)


def test_filled_before_its_run_is_left_to_the_job(db_session, location, practice_type, announce_calls):
    practice = _make_hidden(location, practice_type, when=datetime(2099, 3, 3, 18, 15))
    practice_id = practice.id
    try:
        publish_if_ready(practice, now=datetime(2099, 3, 3, 7, 59))
        assert announce_calls == []
    finally:
        _delete_practice(practice_id)


def test_morning_practice_filled_after_the_evening_run_is_announced(db_session, location, practice_type, announce_calls):
    practice = _make_hidden(location, practice_type, when=datetime(2099, 3, 3, 9, 0))
    practice_id = practice.id
    try:
        publish_if_ready(practice, now=datetime(2099, 3, 2, 21, 0))
        assert announce_calls == [datetime(2099, 3, 2, 20, 0)]
    finally:
        _delete_practice(practice_id)


def test_a_past_practice_is_never_announced(db_session, location, practice_type, announce_calls):
    practice = _make_hidden(location, practice_type, when=datetime(2099, 3, 3, 18, 15))
    practice_id = practice.id
    try:
        publish_if_ready(practice, now=datetime(2099, 3, 3, 20, 0))
        assert announce_calls == []
    finally:
        _delete_practice(practice_id)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices/test_publishing.py -q`
Expected: FAIL with `ImportError: cannot import name 'announcement_run_time'`.

- [ ] **Step 3: Rewrite `app/practices/publishing.py`**

```python
"""Bot-created practices become member-visible on their own.

The block job drafts sessions with `is_draft=True` ("hidden from members").
`publish_if_ready()` flips that flag the moment a practice has the details
members need, from every save path (admin edit, Slack full edit, the Sunday
coach summary sweep). There is no publish button: a manual publish step
silently held back the Sep 1, 3 and 10 practices.

Visibility is one way. Clearing a location later never hides a practice again.
"""

from datetime import datetime, timedelta

from flask import current_app

from app.models import db
from app.practices.drafting import missing_fields
from app.practices.interfaces import PracticeStatus
from app.utils import now_central_naive

_CANCELLED_BLOCKER = "not cancelled"


def publish_blockers(practice) -> list[str]:
    """What still keeps this practice hidden from members."""
    blockers = missing_fields(practice)
    if practice.status == PracticeStatus.CANCELLED.value:
        blockers.append(_CANCELLED_BLOCKER)
    return blockers


def announcement_run_time(practice_date: datetime) -> datetime:
    """When the announcement job picks this practice up.

    Mirrors run_practice_announcements_job: practices at or after 12:00 are
    announced by the 08:00 run that day, earlier ones by the 20:00 run the
    day before.
    """
    if practice_date.hour >= 12:
        return practice_date.replace(hour=8, minute=0, second=0, microsecond=0)
    day_before = practice_date - timedelta(days=1)
    return day_before.replace(hour=20, minute=0, second=0, microsecond=0)


def publish_if_ready(practice, *, now: datetime | None = None) -> bool:
    """Make a hidden practice visible if nothing blocks it. True if it flipped."""
    if not practice.is_draft or publish_blockers(practice):
        return False

    practice.is_draft = False
    db.session.commit()
    current_app.logger.info("Practice #%s is now visible to members", practice.id)

    now = now or now_central_naive()
    if (
        practice.slack_message_ts is None
        and practice.date > now
        and now >= announcement_run_time(practice.date)
    ):
        _announce_late(practice)
    return True


def _announce_late(practice) -> None:
    """Re-run the announcement job's window for this practice.

    Going through the job (instead of posting directly) keeps strength
    sessions combined. The job only posts practices with no slack_message_ts,
    so re-running a window is safe.
    """
    try:
        from app import scheduler

        scheduler.run_practice_announcements_job(
            current_app._get_current_object(),
            now_override=announcement_run_time(practice.date),
        )
    except Exception:
        current_app.logger.exception(
            "Practice #%s became visible after its announcement run, and the "
            "late announcement failed",
            practice.id,
        )
```

Note: `scheduler.run_practice_announcements_job` is looked up on the module at call time so the test's monkeypatch on `app.scheduler.run_practice_announcements_job` takes effect.

- [ ] **Step 4: Add `now_override` to the announcement job**

In `app/scheduler.py`, change the signature and the `now` line of `run_practice_announcements_job`:

```python
def run_practice_announcements_job(app: Flask, channel_override: str = None, now_override=None):
```

and replace

```python
        now = now_central.replace(tzinfo=None)  # Naive datetime in Central time
```

with

```python
        # now_override lets publish_if_ready() replay a window that already
        # ran, for a practice that became visible after its run.
        now = now_override or now_central.replace(tzinfo=None)  # Naive Central
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices/test_publishing.py -q`
Expected: PASS (11 tests).

- [ ] **Step 6: Commit**

```bash
git add app/practices/publishing.py app/scheduler.py tests/practices/test_publishing.py
git commit -m "feat(practices): publish_if_ready makes complete practices visible"
```

### Task A2: Call `publish_if_ready` from both save paths, remove publish routes

**Files:**
- Modify: `app/routes/admin_practices.py` (edit route ~line 695; delete `publish_practices_route` ~366-400; import line 29)
- Modify: `app/routes/admin_availability.py` (delete `publish_poll_block`, `_publish_counts`, `_poll_practices`; trim imports)
- Modify: `app/slack/bolt_app.py` (`_run_practice_edit_full_post_save` ~line 2780)
- Test: `tests/routes/test_admin_practices_routes.py`, `tests/slack/test_full_edit_publishes.py` (create)

**Interfaces:**
- Consumes: `publish_if_ready(practice)` from Task A1.

- [ ] **Step 1: Write the failing tests**

Append to `tests/routes/test_admin_practices_routes.py` (reuse the module's existing app/client/admin-login fixtures; read the top of the file and match how existing edit tests post to `/admin/practices/<id>/edit`):

```python
def test_admin_edit_publishes_a_hidden_practice_once_complete(
    db_session, monkeypatch, admin_client
):
    """Filling in location and type on the edit page makes it member-visible."""
    from app.practices.models import Practice, PracticeLocation, PracticeType

    db.session.rollback()
    location = PracticeLocation(name="TEST A2 Location")
    ptype = PracticeType(name="TEST A2 Type")
    practice = Practice(date=datetime(2099, 4, 7, 18, 15), day_of_week="Tuesday",
                        is_draft=True, leads_needed=2)
    db.session.add_all([location, ptype, practice])
    db.session.commit()
    ids = (practice.id, location.id, ptype.id)
    monkeypatch.setattr("app.slack.practices.refresh_practice_posts",
                        lambda *a, **k: {"announcement": {"skipped": "absent"}})
    try:
        response = admin_client.post(
            f"/admin/practices/{ids[0]}/edit",
            json={"date": "2099-04-07T18:15", "location_id": ids[1],
                  "practice_type_ids": [ids[2]]},
        )
        assert response.status_code == 200, response.get_json()
        assert db.session.get(Practice, ids[0]).is_draft is False
    finally:
        db.session.rollback()
        p = db.session.get(Practice, ids[0])
        if p is not None:
            db.session.delete(p)
        db.session.commit()
        for model, row_id in ((PracticeLocation, ids[1]), (PracticeType, ids[2])):
            row = db.session.get(model, row_id)
            if row is not None:
                db.session.delete(row)
        db.session.commit()


def test_publish_routes_are_gone(admin_client):
    assert admin_client.post("/admin/practices/publish", json={}).status_code == 404
    assert admin_client.post("/admin/availability/polls/1/publish").status_code == 404
```

If the file has no `admin_client` fixture, use whatever fixture the existing edit tests use to post as an admin, and match the edit payload keys the existing edit tests send (the route reads the same JSON keys as the admin form; check `edit_practice()` for `location_id` and the practice-type key name before running).

Create `tests/slack/test_full_edit_publishes.py`:

```python
"""The Slack full edit modal's post-save step makes a complete practice visible."""

from datetime import datetime
from unittest.mock import MagicMock

from app.models import db
from app.practices.models import Practice, PracticeLocation, PracticeType
from app.slack import bolt_app


def test_full_edit_post_save_publishes(db_session, monkeypatch):
    db.session.rollback()
    location = PracticeLocation(name="TEST A2 Slack Location")
    ptype = PracticeType(name="TEST A2 Slack Type")
    practice = Practice(date=datetime(2099, 4, 9, 18, 5), day_of_week="Thursday",
                        is_draft=True, leads_needed=2)
    practice.practice_types = [ptype]
    db.session.add_all([location, ptype, practice])
    db.session.flush()
    practice.location_id = location.id
    db.session.commit()
    ids = (practice.id, location.id, ptype.id)
    monkeypatch.setattr("app.slack.practices.refresh_practice_posts",
                        lambda *a, **k: {"announcement": {"skipped": "absent"}})
    try:
        bolt_app._run_practice_edit_full_post_save(
            practice_id=ids[0], user_id="U0TEST", should_notify=False,
            had_root=False, previous_date=practice.date, previous_location_id=None,
            previous_plan_reactions=None, client=MagicMock(), logger=MagicMock(),
        )
        db.session.expire_all()
        assert db.session.get(Practice, ids[0]).is_draft is False
    finally:
        db.session.rollback()
        p = db.session.get(Practice, ids[0])
        if p is not None:
            db.session.delete(p)
        db.session.commit()
        for model, row_id in ((PracticeLocation, ids[1]), (PracticeType, ids[2])):
            row = db.session.get(model, row_id)
            if row is not None:
                db.session.delete(row)
        db.session.commit()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/routes/test_admin_practices_routes.py -k "publishes_a_hidden or publish_routes_are_gone" tests/slack/test_full_edit_publishes.py -q`
Expected: FAIL (practice still `is_draft`; publish routes return 200/400, not 404).

- [ ] **Step 3: Wire the admin edit route**

In `app/routes/admin_practices.py`, change the import on line 29 to:

```python
from ..practices.publishing import publish_blockers, publish_if_ready
```

In `edit_practice()`, right after

```python
        db.session.commit()
        practice_updated = True
```

add:

```python
        # A bot-created session goes live the moment it has a location and a
        # type. Runs before the refresh below so every post sees it visible.
        publish_if_ready(practice)
```

Delete the whole `publish_practices_route` function and its `@admin_practices_bp.route('/publish', ...)` decorator.

- [ ] **Step 4: Wire the Slack full edit post-save**

In `app/slack/bolt_app.py`, `_run_practice_edit_full_post_save`, in the `else:` branch (practice reloaded), add as the first lines before `announcement_notice = ...`:

```python
            from app.practices.publishing import publish_if_ready

            publish_if_ready(practice)
```

- [ ] **Step 5: Remove the block publish route**

In `app/routes/admin_availability.py`: delete `publish_poll_block`, `_publish_counts`, `_poll_practices`, the `**_publish_counts(p)` line in `dashboard()`, and the import `from ..practices.publishing import publish_blockers, publish_practices`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/routes/test_admin_practices_routes.py tests/routes/test_admin_availability.py tests/slack/test_full_edit_publishes.py -q`
Expected: the two new tests PASS. Tests in `tests/routes/test_admin_availability.py` that assert `unpublished`/`publishable` counts or call the publish route now fail: delete those tests (they cover removed behavior). Re-run until green.

- [ ] **Step 7: Commit**

```bash
git add app/routes/admin_practices.py app/routes/admin_availability.py app/slack/bolt_app.py tests/routes tests/slack/test_full_edit_publishes.py
git commit -m "feat(practices): save paths publish complete practices; drop publish routes"
```

### Task A3: Sunday coach summary sweeps and says "hidden from members"

**Files:**
- Modify: `app/slack/practices/coach_review.py` (`post_coach_weekly_summary`, ~line 450)
- Modify: `app/slack/blocks/coach_review.py` (row badge ~line 135; footer ~line 280)
- Test: `tests/slack/test_coach_summary_drafts.py`

**Interfaces:**
- Consumes: `publish_if_ready` (Task A1).

- [ ] **Step 1: Update the tests first**

In `tests/slack/test_coach_summary_drafts.py`, replace these tests' assertions:

```python
def test_a_draft_is_labelled_as_not_yet_visible():
    blocks = build_coach_weekly_summary_blocks(
        [_practice(5, is_draft=True, missing=["location"])], _EXPECTED_DAYS, _WEEK_START)
    text = json.dumps(blocks)
    assert "HIDDEN" in text
    assert "Hidden from members until it has a location" in text
    assert "Draft" not in text


def test_a_published_practice_is_not_labelled_a_draft():
    blocks = build_coach_weekly_summary_blocks([_practice(5)], _EXPECTED_DAYS, _WEEK_START)
    assert "HIDDEN" not in json.dumps(blocks)


def test_a_draft_missing_details_says_what_it_needs():
    blocks = build_coach_weekly_summary_blocks(
        [_practice(5, is_draft=True, missing=["location", "type"])], _EXPECTED_DAYS, _WEEK_START)
    assert "until it has a location and a type" in json.dumps(blocks)


def test_a_lingering_draft_is_flagged_in_the_footer():
    blocks = build_coach_weekly_summary_blocks(
        [_practice(5, is_draft=True, missing=["location"])], _EXPECTED_DAYS, _WEEK_START)
    footer = blocks[-1]["elements"][0]["text"]
    assert "1 practice this week is hidden from members" in footer
    assert "availability block" not in footer


def test_a_week_with_no_drafts_says_nothing_about_drafts():
    blocks = build_coach_weekly_summary_blocks([_practice(5)], _EXPECTED_DAYS, _WEEK_START)
    footer = blocks[-1]["elements"][0]["text"]
    assert "hidden" not in footer.lower()
```

Keep `_practice()` and the other tests as they are. Read the existing `_practice()` helper first and match its signature if it differs from the calls above.

In `tests/slack/test_coach_summary_posting.py`, the `practice()` helper builds `SimpleNamespace` stand-ins and its `FakeQuery` returns them for every query, so the new sweep will see them. Give the helper an `is_draft` field so the sweep can read it:

```python
def practice(practice_id, when, is_draft=False):
    return SimpleNamespace(
        id=practice_id,
        date=when,
        slack_coach_summary_ts=None,
        is_draft=is_draft,
    )
```

and add:

```python
def test_summary_sweeps_hidden_practices_through_publish_if_ready():
    hidden = practice(41, datetime(2026, 7, 14, 18, 15), is_draft=True)
    swept = []
    with patch("app.practices.publishing.publish_if_ready",
               lambda p, **k: swept.append(p.id) or False):
        run_coach_summary([hidden])
    assert 41 in swept
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_coach_summary_drafts.py tests/slack/test_coach_summary_posting.py -q`
Expected: FAIL on the new copy and the sweep.

- [ ] **Step 3: Change the row copy**

In `app/slack/blocks/coach_review.py`, replace the `if getattr(practice, 'is_draft', False):` block (~line 138) with:

```python
            # Hidden practices are what coaches are here to fill in. Say what
            # keeps each one hidden, in words the team uses.
            if getattr(practice, 'is_draft', False):
                missing = [m for m in (getattr(practice, 'missing_details', []) or [])
                           if m in ("location", "type", "time")]
                header_text += "  `HIDDEN`"
                if missing:
                    needs = " and ".join(f"a {m}" for m in missing)
                    header_text += f"\n:warning: _Hidden from members until it has {needs}_"
                else:
                    header_text += "\n_Hidden from members_"
```

- [ ] **Step 4: Change the footer**

Replace the comment and footer block at the end of `build_coach_weekly_summary_blocks` (~line 280) with:

```python
    # ==========================================================================
    # FOOTER
    # ==========================================================================
    hidden = [p for p in practices if getattr(p, 'is_draft', False)]

    footer = (
        ":bulb: Click *Edit* to update workout details. Changes will notify "
        "this thread unless unchecked."
    )
    if hidden:
        n = len(hidden)
        footer += (
            f"\n:warning: {n} {'practice' if n == 1 else 'practices'} this week "
            f"{'is' if n == 1 else 'are'} hidden from members until "
            f"{'its' if n == 1 else 'their'} details are filled in."
        )
```

(keep the `blocks.append({... footer ...})` and `return blocks` that follow).

- [ ] **Step 5: Sweep before building**

In `app/slack/practices/coach_review.py` add a module-level helper:

```python
def _publish_ready_hidden(week_start, week_end) -> None:
    """Catch anything a script or missed save path left hidden while complete."""
    from app.practices import publishing
    from app.practices.service import coach_visible_practices

    for hidden in coach_visible_practices().filter(
        Practice.is_draft.is_(True),
        Practice.date >= week_start,
        Practice.date < week_end,
    ).all():
        if getattr(hidden, "is_draft", False):
            publishing.publish_if_ready(hidden)
```

and in `post_coach_weekly_summary`, after `week_end = week_start + timedelta(days=7)` and before the `practices = coach_visible_practices()...` query, call `_publish_ready_hidden(week_start, week_end)`. (The `getattr` re-check matters only for the posting tests' fake query, which ignores filters.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_coach_summary_drafts.py tests/slack/test_coach_summary_posting.py tests/slack/test_coach_summary_includes_drafts.py -q`
Expected: PASS. If `test_coach_summary_includes_drafts.py` asserts the old "Draft" copy, update those assertions to "HIDDEN" / "Hidden from members".

- [ ] **Step 7: Commit**

```bash
git add app/slack/practices/coach_review.py app/slack/blocks/coach_review.py tests/slack
git commit -m "feat(practices): Sunday coach summary sweeps and says hidden from members"
```

### Task A4: Remove the monthly drafting job and the readiness digest

**Files:**
- Delete: `app/slack/practices/drafts.py`, `app/slack/blocks/practice_drafts.py`, `tests/test_scheduler_draft_jobs.py`, `tests/slack/test_practice_draft_posting.py`, `tests/slack/test_practice_draft_blocks.py`, `tests/practices/test_readiness.py`
- Modify: `app/scheduler.py`, `app/practices/drafting.py`, `app/slack/practices/summary_posts.py`, `app/slack/practices/__init__.py`, `app/slack/blocks/__init__.py`, `tests/practices/test_drafting.py`

- [ ] **Step 1: Delete the modules and their tests**

```bash
git rm app/slack/practices/drafts.py app/slack/blocks/practice_drafts.py \
  tests/test_scheduler_draft_jobs.py tests/slack/test_practice_draft_posting.py \
  tests/slack/test_practice_draft_blocks.py tests/practices/test_readiness.py
```

- [ ] **Step 2: Remove the exports**

In `app/slack/practices/__init__.py` delete the `from app.slack.practices.drafts import (post_readiness_digest,)` import and the `"post_readiness_digest"` entry (and its `# drafts` comment) in `__all__`. In `app/slack/blocks/__init__.py` delete the `from app.slack.blocks.practice_drafts import (build_readiness_digest_blocks,)` import and its `__all__` entry and comment.

- [ ] **Step 3: Remove the scheduler jobs**

In `app/scheduler.py`:
- delete the imports `from app.practices.drafting import (drafted_practices_in_window, end_of_next_month, ...)` entries for those two names (keep any other names that import still brings in and that the file still uses; if the import becomes empty, delete it) and `from app.slack.practices.drafts import post_readiness_digest`
- delete `_block_anchor`, `run_practice_block_bootstrap_job`, `run_practice_readiness_nudge_job`
- delete both `scheduler.add_job(...)` blocks with ids `practice_block_bootstrap` and `practice_block_readiness_nudge`, and the "Practice Availability Drafting" banner comment above them
- delete the line `- 8:00 AM on the 1st: Draft practices through the end of next month, post readiness digest` from the module docstring

- [ ] **Step 4: Trim `drafting.py`**

In `app/practices/drafting.py` delete `end_of_next_month`, `drafted_practices_in_window`, `undrafted_next_month`, `readiness_summary`, `is_ready`. Keep `WEEKDAYS`, `DEFAULT_PRACTICE_DAYS`, `default_practice_days`, `expected_slots`, `generate_draft_block`, `missing_fields`. Rewrite the module docstring:

```python
"""Draft sessions from the practice_days schedule.

The block job (app/practices/blocks.py) calls generate_draft_block() for each
two-week block. Drafted sessions are hidden from members (see
published_practices()) until publish_if_ready() finds a location and a type.
"""
```

In `generate_draft_block`'s docstring replace the sentence about "consecutive monthly runs deliberately overlap by a whole month (see end_of_next_month)" with "and the block job re-runs daily". In `expected_slots`'s docstring delete the "(see end_of_next_month above)" reference.

Then check `is_ready` has no other callers:

```bash
grep -rn "is_ready\|end_of_next_month\|undrafted_next_month\|readiness_summary\|drafted_practices_in_window" app scripts
```

Expected: only `app/practices/availability.py` (`is_ready` in `build_poll`). Leave that until Task B2, which rewrites `build_poll`; for now change the import there to keep the file importable:

```python
from app.practices.drafting import missing_fields
```

and in `build_poll` replace `if not is_ready(p)` with `if missing_fields(p)`.

- [ ] **Step 5: Remove the digest bookkeeping helpers**

In `app/slack/practices/summary_posts.py` delete `find_readiness_digest_post` and `stage_readiness_digest_post`. Keep `READINESS_DIGEST = "readiness_digest"` and change its comment to:

```python
# No longer written. Kept so the cutover cleanup script can find the three
# digest posts (Aug 1, Sep 1, Oct 1 2026) and delete them from Slack.
READINESS_DIGEST = "readiness_digest"
```

- [ ] **Step 6: Trim `tests/practices/test_drafting.py`**

Delete every test that references `end_of_next_month`, `undrafted_next_month` or `drafted_practices_in_window`:

```bash
grep -n "def test_\|end_of_next_month\|undrafted_next_month\|drafted_practices_in_window" tests/practices/test_drafting.py
```

Remove those test functions and the now-unused imports.

- [ ] **Step 7: Run the suite slice**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices tests/slack tests/test_scheduler_lead_availability.py -q`
Expected: PASS except tests that import removed names; fix each by deleting the test if it only covered removed behavior. Also run `/workspace/tcsc-trips/.venv/bin/python -c "import app.scheduler"`; expected: no error.

- [ ] **Step 8: Commit**

```bash
git add -A app tests
git commit -m "refactor(practices): remove monthly drafting job and readiness digest"
```

### Task A5: Delete shadow mode

**Files:**
- Modify: `app/practices/availability.py`, `app/routes/admin_availability.py`, `app/static/admin_practices.js`
- Delete: `tests/practices/test_shadow_nudge_containment.py`
- Modify tests: `tests/practices/test_availability_nudge.py`, `tests/practices/test_availability_service.py`, `tests/routes/test_admin_availability.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/practices/test_availability_service.py`:

```python
def test_polls_always_target_the_leads_channel(db_session):
    from app.slack.practices._config import COORD_CHANNEL_ID

    practices = [_ready_practice(4)]
    poll = None
    try:
        poll = build_poll(_START, _END)
        assert poll.channel_id == COORD_CHANNEL_ID
        assert poll.is_shadow is False
    finally:
        _cleanup_practices(practices, poll)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices/test_availability_service.py::test_polls_always_target_the_leads_channel -q`
Expected: FAIL (with no `shadow_mode` row in the test DB, `build_poll` targets the shadow channel; or it passes if `is_shadow` defaults False, in which case proceed: the deletion below is still required).

- [ ] **Step 3: Delete the shadow code in `availability.py`**

- delete `shadow_roster_leads()`
- replace `_target_channel()` with nothing; in `build_poll`, drop the `is_shadow` parameter and set `channel_id=COORD_CHANNEL_ID`, `is_shadow=False`; add `from app.slack.practices._config import COORD_CHANNEL_ID` at the top
- in `sync_participants`: `pool = eligible_leads()` and delete the shadow paragraph from its docstring
- in `participants_to_nudge`: `may_be_asked = {user.id for user in eligible_leads()}` and delete the shadow sentences from its docstring (keep the ALUMNI explanation)

- [ ] **Step 4: Delete the shadow code in the admin route and JS**

`app/routes/admin_availability.py`: delete `_shadow_mode()`, the `"shadow_mode"` key in `dashboard()`, and the module docstring paragraph about shadow mode; `create_poll` calls `build_poll(starts_on, ends_on)`. In its JSON response drop `is_shadow`.

`app/static/admin_practices.js`: delete `AVAILABILITY_CHANNEL_NAMES` and `describeAvailabilityChannel`; in `openAvailabilityPoll` replace the `channelLabel`/`confirm` lines with

```javascript
    const proceed = confirm('This will post the availability poll to #coord-practices-leads-assists. Continue?');
```

and use `'#coord-practices-leads-assists'` in the success toast. (Task B7 deletes this function entirely.)

- [ ] **Step 5: Delete shadow tests**

```bash
git rm tests/practices/test_shadow_nudge_containment.py
grep -n "shadow" tests/practices/test_availability_nudge.py tests/practices/test_availability_service.py tests/routes/test_admin_availability.py tests/test_scheduler_lead_availability.py
```

Delete each test whose subject is shadow mode; in the rest, remove `is_shadow=` arguments and any `AppConfig` save/restore of `lead_availability.shadow_*` keys.

- [ ] **Step 6: Run the tests**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices tests/routes/test_admin_availability.py tests/test_scheduler_lead_availability.py -q && grep -rn "shadow" app --include=*.py --include=*.js | grep -v is_shadow`
Expected: PASS; grep prints nothing.

- [ ] **Step 7: Commit**

```bash
git add -A app tests
git commit -m "refactor(availability): delete shadow mode; polls always post to the leads channel"
```

### Task A6: Admin list page drops publish controls

**Files:**
- Modify: `app/static/admin_practices.js` (`rowHtml` ~line 180, `draftPublishHtml`, `publishOnePractice`, `pollCardHtml`, `publishPollBlock`, `publishResultMessage`, `attachEventListeners`, `populateDrawer` ~line 336)
- Modify: `app/templates/admin/practices/list.html` (comment above `#pl-polls`)
- Test: `tests/js/draft_publish.test.js` (rewrite)

- [ ] **Step 1: Rewrite the JS test**

Replace the tests in `tests/js/draft_publish.test.js` after the `READY/BLOCKED/PUBLISHED` constants (keep `load()`, but change its export list to `{draftPublishHtml, rowHtml, pollCardHtml, flashPendingAvailabilityWarning, _setPractices: ...}`) with:

```javascript
test('a hidden row is badged so it is not mistaken for a live practice', () => {
  const {rowHtml} = load();
  const html = rowHtml(BLOCKED, false);
  assert.match(html, /Hidden/);
  assert.match(html, /pl-row-draft/);
  assert.match(html, /needs location, type/);
});

test('a visible row carries no hidden badge', () => {
  const {rowHtml} = load();
  assert.doesNotMatch(rowHtml(PUBLISHED, false), /Hidden/);
});

test('the drawer explains what keeps a practice hidden, with no button', () => {
  const {draftPublishHtml} = load();
  const html = draftPublishHtml(BLOCKED);
  assert.match(html, /Hidden from members until it has a location and a type/);
  assert.doesNotMatch(html, /<button/);
});

test('a visible practice gets no hidden notice in the drawer', () => {
  const {draftPublishHtml} = load();
  assert.equal(draftPublishHtml(PUBLISHED), '');
});

test('no publish control exists anywhere on the page', () => {
  assert.doesNotMatch(SOURCE, /pl-publish/);
  assert.doesNotMatch(SOURCE, /\/publish'/);
  assert.doesNotMatch(SOURCE, /publishPollBlock|publishOnePractice/);
});

test('a poll card shows range, status and session count, and no publish button', () => {
  const {pollCardHtml} = load();
  const html = pollCardHtml({id: 7, starts_on: '2099-05-04', ends_on: '2099-05-17',
    status: 'closed', sessions: 6});
  assert.match(html, /6 sessions/);
  assert.match(html, /Closed/);
  assert.doesNotMatch(html, /Publish/);
});
```

Keep the two `flashPendingAvailabilityWarning` tests for now (Task C1 removes them with the warning).

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test tests/js/draft_publish.test.js`
Expected: FAIL (old "Draft" copy, publish button present).

- [ ] **Step 3: Change the JS**

In `app/static/admin_practices.js`:

Row badge (in `rowHtml`):

```javascript
  const draftBadge = p.is_draft
    ? `<span class="pl-draft">Hidden${missing.length ? ` · needs ${esc(missing.join(', '))}` : ''}</span>`
    : '';
```

and in the same function change `', draft, not visible to members'` to `', hidden from members'`.

Replace the "drafts → published" comment, `draftPublishHtml` and `publishOnePractice` with:

```javascript
/* ---------- hidden practices ----------
   Bot-created sessions stay hidden from members until they have a location
   and a type, then go live on their own (publish_if_ready). Nothing to click. */

function draftPublishHtml(p) {
  if (!p.is_draft) return '';
  const missing = (p.missing_details || []).filter(m => m !== 'not cancelled');
  if (!missing.length) return '<div class="pl-draft-note">Hidden from members.</div>';
  const needs = missing.map(m => `a ${m}`).join(' and ');
  return `<div class="pl-draft-note">Hidden from members until it has ${esc(needs)}.</div>`;
}
```

In `populateDrawer` (~line 336) delete the `const publishOne = ...` lookup and its listener.

Replace `pollCardHtml` with:

```javascript
function pollCardHtml(poll) {
  const st = poll.status || 'draft';
  const n = (c, w) => `${c} ${w}${c === 1 ? '' : 's'}`;
  return `<div class="pl-poll">`
    + `<span class="pl-poll-range">${esc(pollRangeLabel(poll))}</span>`
    + `<span class="pl-poll-status is-${esc(st)}">${esc(POLL_STATUS_LABEL[st] || st)}</span>`
    + `<span class="pl-poll-sessions">${n(poll.sessions, 'session')}</span></div>`;
}
```

Delete `practiceName`, `publishResultMessage`, `publishPollBlock`, and in `attachEventListeners` the `pl-polls` click listener. Delete the "block-level publish (per availability poll)" comment header (keep `POLL_STATUS_LABEL`, `loadAvailabilityPolls`, `pollRangeLabel`, `renderPolls`).

In `app/templates/admin/practices/list.html` replace the comment above `#pl-polls` with `<!-- Recent lead polls, one per two-week block. -->`.

- [ ] **Step 4: Run the JS tests**

Run: `npm run test:practice-reactions`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/static/admin_practices.js app/templates/admin/practices/list.html tests/js/draft_publish.test.js
git commit -m "feat(admin): practices list says hidden from members, no publish controls"
```

### Task A7: Phase A PR

- [ ] **Step 1: Full verification**

```bash
DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape 2>&1 | tail -5
npm run test:practice-reactions
git diff --stat origin/main...HEAD -- app | tail -1
```

Expected: no new failures against the Task 0 baseline. The app diff should be net negative (removals outweigh additions).

- [ ] **Step 2: Push and open the PR (do not merge)**

```bash
git push -u origin lead-availability-simplify
gh pr create --draft --title "Lead availability v2, part A: visible when ready, removals" --body "$(cat <<'EOF'
Part A of docs/superpowers/specs/2026-10-05-lead-availability-simplification-design.md.

- publish_if_ready(): bot-created practices go live once they have a location and a type, from the admin edit page, the Slack full edit modal and the Sunday coach summary sweep. Late fills are announced right away, with strength sessions still combined.
- Removed: monthly drafting job, daily readiness digest, publish buttons and routes, shadow mode.
- Sunday coach summary and the admin list say "hidden from members" instead of "draft".

Draft until Rob has seen the demo (part C). Merge order: A, B, C.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

# Phase B: Block cycle

Branch: create from Phase A.

```bash
git switch -c lead-availability-blocks
```

### Task B1: Migration and model columns

**Files:**
- Create: `migrations/versions/9b2e6d4f1a37_lead_availability_block_posts.py`
- Modify: `app/practices/availability_models.py`
- Modify: `tests/practices/test_practice_migration_release.py:28`
- Test: `tests/practices/test_availability_schema.py`

**Interfaces:**
- Produces on `LeadAvailabilityPoll`: `block_post_ts: str | None`, `opened_by_slack_uid: str | None`, `wednesday_reminder_sent_at: datetime | None`, `next_position: int` (default 0).

- [ ] **Step 1: Write the failing test**

Append to `tests/practices/test_availability_schema.py`:

```python
def test_poll_has_block_post_columns(db_session):
    from sqlalchemy import inspect

    columns = {c["name"] for c in inspect(db.engine).get_columns("lead_availability_polls")}
    assert {"block_post_ts", "opened_by_slack_uid",
            "wednesday_reminder_sent_at", "next_position"} <= columns
```

(Add `from app.models import db` to the imports if the file lacks it.)

- [ ] **Step 2: Run it to verify it fails**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices/test_availability_schema.py::test_poll_has_block_post_columns -q`
Expected: FAIL (columns missing).

- [ ] **Step 3: Write the migration**

First confirm the head: `grep -n "HEAD_REVISION =" tests/practices/test_practice_migration_release.py` (expected `7a1c5e9d3b20`; if it differs, use that value as `down_revision`).

`migrations/versions/9b2e6d4f1a37_lead_availability_block_posts.py`:

```python
"""Lead availability block posts: block post ts, opener, Wednesday reminder,
monotonic letter position.

Revision ID: 9b2e6d4f1a37
Revises: 7a1c5e9d3b20
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa

revision = "9b2e6d4f1a37"
down_revision = "7a1c5e9d3b20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lead_availability_polls") as batch:
        batch.add_column(sa.Column("block_post_ts", sa.String(50)))
        batch.add_column(sa.Column("opened_by_slack_uid", sa.String(50)))
        batch.add_column(sa.Column("wednesday_reminder_sent_at", sa.DateTime()))
        batch.add_column(sa.Column(
            "next_position", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("lead_availability_polls") as batch:
        batch.drop_column("next_position")
        batch.drop_column("wednesday_reminder_sent_at")
        batch.drop_column("opened_by_slack_uid")
        batch.drop_column("block_post_ts")
```

Set `HEAD_REVISION = "9b2e6d4f1a37"` in `tests/practices/test_practice_migration_release.py`.

- [ ] **Step 4: Add the model columns**

In `LeadAvailabilityPoll` (`app/practices/availability_models.py`), after `closed_at`:

```python
    # The team's block post in #collab-coaches-practices (always that
    # channel, so only the ts is stored).
    block_post_ts = db.Column(db.String(50))
    # Who pressed Open poll, as a Slack id so an unlinked clicker still renders.
    opened_by_slack_uid = db.Column(db.String(50))
    wednesday_reminder_sent_at = db.Column(db.DateTime)
    # Letters only count up: a deleted session's letter keeps its reactions
    # on the message, so it must never be handed to a new session.
    next_position = db.Column(db.Integer, nullable=False, default=0, server_default="0")
```

- [ ] **Step 5: Apply and run**

```bash
DATABASE_URL=$TEST_DB TCSC_MIGRATION_ONLY=1 SLACK_APP_TOKEN= /workspace/tcsc-trips/.venv/bin/flask db upgrade
DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices/test_availability_schema.py tests/practices/test_practice_migration_release.py -q
```

Expected: PASS. (If `$TEST_DB` is the shared dev DB on another branch's schema, Task 0 said to use `tcsc_trips_test`; do not upgrade the shared dev DB.)

- [ ] **Step 6: Commit**

```bash
git add migrations/versions/9b2e6d4f1a37_lead_availability_block_posts.py app/practices/availability_models.py tests/practices
git commit -m "feat(availability): poll columns for block posts"
```

### Task B2: Replace `build_poll` with `create_block_poll` + `map_sessions`

**Files:**
- Modify: `app/practices/availability.py`
- Modify: `app/routes/admin_availability.py` (`create_poll` imports `build_poll`; Task B7 deletes the route, for now switch it)
- Modify: `tests/practices/test_availability_service.py`, `tests/routes/test_admin_availability.py`
- Create: `tests/practices/poll_helpers.py`

**Interfaces:**
- Produces: `create_block_poll(starts_on: date, ends_on: date) -> LeadAvailabilityPoll` (DRAFT, no mappings, idempotent on the exact range, commits).
- Produces: `block_practices(starts_on: date, ends_on: date) -> list[Practice]` (every practice in range, cancelled included, ordered by date).
- Produces: `map_sessions(poll) -> None` (DRAFT only; replaces mappings with every non-cancelled practice in range, sets `next_position`; flushes, does not commit; raises `PollNotReadyError` when the range is empty, `EmojiSupplyError` past 22).
- Removes: `build_poll`, `DuplicatePollError`, `poll_rows`' callers unchanged.

- [ ] **Step 1: Add the test helper**

`tests/practices/poll_helpers.py`:

```python
"""Build a mapped DRAFT poll the way open_block_poll does, for tests."""

from app.models import db
from app.practices.availability import create_block_poll, map_sessions


def make_mapped_poll(starts_on, ends_on):
    poll = create_block_poll(starts_on, ends_on)
    map_sessions(poll)
    db.session.commit()
    return poll
```

- [ ] **Step 2: Write the failing tests**

In `tests/practices/test_availability_service.py`:
- change the import block to import `PollNotReadyError, create_block_poll, eligible_leads, map_sessions, open_poll` and add `from tests.practices.poll_helpers import make_mapped_poll`
- replace every `build_poll(_START, _END)` call with `make_mapped_poll(_START, _END)`
- delete these tests (they cover removed behavior): `test_build_poll_refuses_incomplete_drafts`, `test_build_poll_targets_channel_by_shadow_flag` (if still present), `test_build_poll_replaces_an_abandoned_draft_over_the_same_range`, `test_build_poll_refuses_a_partially_overlapping_open_poll`, `test_build_poll_allows_a_new_poll_once_the_old_one_is_closed`, `test_build_poll_covers_only_unpublished_practices`, `test_a_published_practice_missing_details_cannot_block_a_poll`
- rename remaining `test_build_poll_*` to `test_map_sessions_*`
- add:

```python
def _bare_practice(day, *, is_draft=True, status=None):
    p = Practice(date=datetime(2099, 8, day, 18, 15), day_of_week="Tuesday",
                 is_draft=is_draft)
    if status:
        p.status = status
    db.session.add(p)
    db.session.flush()
    return p


def test_map_sessions_needs_only_date_and_time(db_session):
    practices = [_bare_practice(4), _bare_practice(6)]
    poll = None
    try:
        poll = make_mapped_poll(_START, _END)
        assert [m.practice_id for m in poll.practices] == [p.id for p in practices]
    finally:
        _cleanup_practices(practices, poll)


def test_map_sessions_includes_visible_and_hidden_practices(db_session):
    practices = [_bare_practice(4, is_draft=False), _bare_practice(6, is_draft=True)]
    poll = None
    try:
        poll = make_mapped_poll(_START, _END)
        assert len(poll.practices) == 2
        assert poll.next_position == 2
    finally:
        _cleanup_practices(practices, poll)


def test_map_sessions_skips_cancelled(db_session):
    practices = [_bare_practice(4), _bare_practice(6, status=PracticeStatus.CANCELLED.value)]
    poll = None
    try:
        poll = make_mapped_poll(_START, _END)
        assert [m.practice_id for m in poll.practices] == [practices[0].id]
    finally:
        _cleanup_practices(practices, poll)


def test_map_sessions_refuses_an_empty_range(db_session):
    poll = None
    try:
        poll = create_block_poll(date(2099, 9, 1), date(2099, 9, 14))
        with pytest.raises(PollNotReadyError):
            map_sessions(poll)
    finally:
        _cleanup_practices([], poll)


def test_create_block_poll_is_idempotent_on_the_range(db_session):
    poll = None
    try:
        poll = create_block_poll(date(2099, 9, 1), date(2099, 9, 14))
        again = create_block_poll(date(2099, 9, 1), date(2099, 9, 14))
        assert again.id == poll.id
        assert poll.status == PollStatus.DRAFT
        assert poll.practices == []
    finally:
        _cleanup_practices([], poll)


def test_map_sessions_replaces_a_draft_mapping(db_session):
    practices = [_bare_practice(4)]
    poll = None
    try:
        poll = make_mapped_poll(_START, _END)
        practices.append(_bare_practice(6))
        map_sessions(poll)
        db.session.commit()
        assert [m.position for m in poll.practices] == [0, 1]
        assert [m.emoji for m in poll.practices] == ["letter_a", "letter_b"]
    finally:
        _cleanup_practices(practices, poll)
```

(`_cleanup_practices([], poll)` works for a poll with no practices: it deletes the poll and skips the rest. `_bare_practice` rows have no location/type, which `_cleanup_practices` already tolerates.)

In `tests/routes/test_admin_availability.py` replace `build_poll` patches/calls with `create_block_poll`/`make_mapped_poll` the same way, and delete tests about the readiness gate or overlap.

- [ ] **Step 3: Run them to verify they fail**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices/test_availability_service.py -q`
Expected: FAIL with `ImportError: cannot import name 'create_block_poll'`.

- [ ] **Step 4: Implement in `app/practices/availability.py`**

Delete `DuplicatePollError` and `build_poll` (and the `missing_fields` import if nothing else uses it). Add:

```python
def create_block_poll(starts_on: date, ends_on: date) -> LeadAvailabilityPoll:
    """The block's poll row, created when its block post goes up.

    DRAFT with no letters: sessions can still be added or cancelled during
    the week before someone presses Open poll, so letters are assigned then
    (map_sessions). Idempotent on the exact range.
    """
    poll = LeadAvailabilityPoll.query.filter_by(
        starts_on=starts_on, ends_on=ends_on).first()
    if poll is not None:
        return poll
    poll = LeadAvailabilityPoll(
        starts_on=starts_on,
        ends_on=ends_on,
        status=PollStatus.DRAFT,
        is_shadow=False,
        channel_id=COORD_CHANNEL_ID,
        # Snapshot, so a config edit mid-poll can't change what counts as done.
        done_emoji=done_emoji(),
    )
    db.session.add(poll)
    db.session.commit()
    return poll


def block_practices(starts_on: date, ends_on: date) -> list[Practice]:
    """Every practice in the range, cancelled included, in date order."""
    return (
        Practice.query
        .filter(Practice.date >= datetime.combine(starts_on, datetime.min.time()),
                Practice.date <= datetime.combine(ends_on, datetime.max.time()))
        .order_by(Practice.date, Practice.id)
        .all()
    )


def map_sessions(poll: LeadAvailabilityPoll) -> None:
    """Give every non-cancelled practice in the poll's range a letter.

    DRAFT polls only. Nothing has been posted yet, so the previous mapping
    (if any) is replaced outright. Hidden and visible practices are both
    mapped: the team may have filled some in already. Flushes, never commits.
    """
    if poll.status != PollStatus.DRAFT:
        raise PollNotReadyError(f"poll {poll.id} is {poll.status}, not draft")
    practices = [
        p for p in block_practices(poll.starts_on, poll.ends_on)
        if p.status != PracticeStatus.CANCELLED.value
    ]
    if not practices:
        raise PollNotReadyError(
            f"no practices between {poll.starts_on} and {poll.ends_on}")
    names = letter_emoji(len(practices))

    poll.practices.clear()
    # Flush the deletes before inserting: uq_poll_emoji would otherwise trip
    # on the same letters being re-added in one flush.
    db.session.flush()
    for position, (practice, name) in enumerate(zip(practices, names)):
        poll.practices.append(LeadAvailabilityPollPractice(
            practice_id=practice.id, emoji=name, position=position))
    poll.next_position = len(practices)
    db.session.flush()
```

Make sure `COORD_CHANNEL_ID` is imported at the top (Task A5 added it) and `date` is imported (`from datetime import date, datetime, timedelta` already is).

In `app/routes/admin_availability.py`, `create_poll` becomes (temporary until Task B7):

```python
    try:
        poll = create_block_poll(starts_on, ends_on)
        map_sessions(poll)
        db.session.commit()
    except (PollNotReadyError, EmojiSupplyError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
```

with imports `from ..models import db` and `from ..practices.availability import PollNotReadyError, create_block_poll, map_sessions, open_poll`.

- [ ] **Step 5: Run the tests**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices tests/routes/test_admin_availability.py tests/slack/test_availability_poll_refresh.py -q && grep -rn "build_poll\b" app scripts tests`
Expected: PASS; grep prints nothing (the `build_poll_blocks` function name is a different symbol and is fine).

- [ ] **Step 6: Commit**

```bash
git add -A app tests
git commit -m "refactor(availability): create_block_poll + map_sessions replace build_poll"
```

### Task B3: The block job and `open_block_poll`

**Files:**
- Create: `app/practices/blocks.py`
- Test: `tests/practices/test_blocks.py` (create)

**Interfaces:**
- Consumes: `create_block_poll`, `block_practices`, `map_sessions`, `open_poll` (Task B2), `generate_draft_block` (drafting).
- Produces: `BLOCK_DAYS = 14`, `DEFAULT_ANCHOR = date(2026, 10, 26)`, `block_anchor() -> date`, `block_start_for(day: date, anchor: date) -> date`, `blocks_due(today: date, anchor: date) -> list[date]`, `poll_for_date(day: date) -> LeadAvailabilityPoll | None`, `ensure_block(start: date, today: date) -> dict`, `run_block_job(today: date | None = None) -> list[dict]`, `open_block_poll(poll_id: int, opened_by_slack_uid: str | None) -> dict`.
- Calls (defined in Task B5, stubbed here as module functions so tests can patch them): `post_block_post(poll) -> bool`, `refresh_block_post(poll, *, exclude_practice_id=None) -> bool`, `post_wednesday_reply(poll) -> bool`.

- [ ] **Step 1: Write the failing tests**

`tests/practices/test_blocks.py`:

```python
"""Two-week blocks: anchor math, the daily block job, opening a poll.

Real local DB; year 2099 dates; see tests/practices/conftest.py.
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from app.models import AppConfig, db
from app.practices import blocks
from app.practices.availability_models import LeadAvailabilityPoll, PollStatus
from app.practices.models import Practice

ANCHOR = date(2099, 1, 5)  # a Monday


def test_block_start_for_is_stable_across_dst_and_new_year():
    anchor = date(2026, 10, 26)
    assert blocks.block_start_for(date(2026, 11, 1), anchor) == date(2026, 10, 26)   # DST ends
    assert blocks.block_start_for(date(2026, 11, 9), anchor) == date(2026, 11, 9)
    assert blocks.block_start_for(date(2027, 1, 3), anchor) == date(2026, 12, 21)
    assert blocks.block_start_for(date(2027, 1, 4), anchor) == date(2027, 1, 4)


def test_blocks_due_from_the_post_day_on():
    anchor = date(2026, 10, 26)
    assert blocks.blocks_due(date(2026, 10, 18), anchor) == []                       # Sun before post day
    assert blocks.blocks_due(date(2026, 10, 19), anchor) == [date(2026, 10, 26)]     # post day
    assert blocks.blocks_due(date(2026, 10, 20), anchor) == [date(2026, 10, 26)]     # missed Monday
    assert blocks.blocks_due(date(2026, 11, 2), anchor) == [date(2026, 10, 26), date(2026, 11, 9)]


def test_no_block_before_the_anchor():
    """Deploy lands mid Oct 12-25: that block is the cutover script's job."""
    assert blocks.blocks_due(date(2026, 10, 14), date(2026, 10, 26)) == []


def test_block_anchor_reads_appconfig_and_falls_back(db_session):
    original = AppConfig.get("lead_availability.block_anchor")
    try:
        AppConfig.set("lead_availability.block_anchor", "2099-01-05")
        assert blocks.block_anchor() == date(2099, 1, 5)
        AppConfig.set("lead_availability.block_anchor", "not a date")
        assert blocks.block_anchor() == blocks.DEFAULT_ANCHOR
    finally:
        AppConfig.set("lead_availability.block_anchor", original)


def _practice(day, hour=18, minute=15, *, is_draft=True):
    p = Practice(date=datetime(2099, 1, day, hour, minute),
                 day_of_week=datetime(2099, 1, day).strftime("%A"),
                 is_draft=is_draft, leads_needed=2, logistics_notes="TEST blocks")
    db.session.add(p)
    db.session.commit()
    return p.id


def _cleanup(practice_ids=(), starts_on=None):
    db.session.rollback()
    if starts_on is not None:
        for poll in LeadAvailabilityPoll.query.filter_by(starts_on=starts_on).all():
            db.session.delete(poll)
        db.session.commit()
    for pid in practice_ids:
        p = db.session.get(Practice, pid)
        if p is not None:
            db.session.delete(p)
    db.session.commit()


@pytest.fixture()
def slack_posts(monkeypatch):
    calls = {"post": [], "wed": []}

    def fake_post(poll):
        calls["post"].append(poll.id)
        poll.block_post_ts = "1.000"
        db.session.commit()
        return True

    def fake_wed(poll):
        calls["wed"].append(poll.id)
        poll.wednesday_reminder_sent_at = datetime(2099, 1, 1)
        db.session.commit()
        return True

    monkeypatch.setattr(blocks, "post_block_post", fake_post)
    monkeypatch.setattr(blocks, "post_wednesday_reply", fake_wed)
    monkeypatch.setattr(blocks, "refresh_block_post", lambda poll, **k: True)
    monkeypatch.setattr(blocks, "generate_draft_block", lambda s, e: [])
    return calls


def test_existing_drafts_still_get_a_block_post(db_session, slack_posts):
    """generate_draft_block returns [] when sessions already exist (prod on Oct 19)."""
    start = date(2099, 1, 19)
    pid = _practice(20)
    try:
        result = blocks.ensure_block(start, today=date(2099, 1, 12))
        poll = LeadAvailabilityPoll.query.filter_by(starts_on=start).one()
        assert poll.status == PollStatus.DRAFT
        assert poll.block_post_ts == "1.000"
        assert result["posted"] is True
    finally:
        _cleanup([pid], start)


def test_ensure_block_is_idempotent(db_session, slack_posts):
    start = date(2099, 1, 19)
    pid = _practice(20)
    try:
        blocks.ensure_block(start, today=date(2099, 1, 12))
        blocks.ensure_block(start, today=date(2099, 1, 13))
        assert len(slack_posts["post"]) == 1
        assert LeadAvailabilityPoll.query.filter_by(starts_on=start).count() == 1
    finally:
        _cleanup([pid], start)


def test_failed_block_post_is_retried_next_run(db_session, slack_posts, monkeypatch):
    start = date(2099, 1, 19)
    pid = _practice(20)
    try:
        monkeypatch.setattr(blocks, "post_block_post", lambda poll: False)
        blocks.ensure_block(start, today=date(2099, 1, 12))
        assert LeadAvailabilityPoll.query.filter_by(starts_on=start).one().block_post_ts is None
        monkeypatch.undo()
        calls = []
        monkeypatch.setattr(blocks, "post_block_post", lambda poll: calls.append(poll.id) or True)
        monkeypatch.setattr(blocks, "generate_draft_block", lambda s, e: [])
        monkeypatch.setattr(blocks, "post_wednesday_reply", lambda poll: True)
        blocks.ensure_block(start, today=date(2099, 1, 13))
        assert calls
    finally:
        _cleanup([pid], start)


def test_no_sessions_means_no_post(db_session, slack_posts):
    start = date(2099, 2, 2)
    try:
        result = blocks.ensure_block(start, today=date(2099, 1, 26))
        assert result.get("skipped") == "no_sessions"
        assert LeadAvailabilityPoll.query.filter_by(starts_on=start).count() == 0
    finally:
        _cleanup((), start)


def test_wednesday_reply_once_and_after_a_missed_wednesday(db_session, slack_posts):
    start = date(2099, 1, 19)
    pid = _practice(20)
    try:
        blocks.ensure_block(start, today=date(2099, 1, 12))      # Mon: post only
        assert slack_posts["wed"] == []
        blocks.ensure_block(start, today=date(2099, 1, 15))      # Thu: missed Wed, still sent
        blocks.ensure_block(start, today=date(2099, 1, 16))      # Fri: not again
        assert len(slack_posts["wed"]) == 1
    finally:
        _cleanup([pid], start)


def test_no_wednesday_reply_once_opened(db_session, slack_posts):
    start = date(2099, 1, 19)
    pid = _practice(20)
    try:
        blocks.ensure_block(start, today=date(2099, 1, 12))
        poll = LeadAvailabilityPoll.query.filter_by(starts_on=start).one()
        poll.status = PollStatus.OPEN
        db.session.commit()
        blocks.ensure_block(start, today=date(2099, 1, 14))
        assert slack_posts["wed"] == []
    finally:
        _cleanup([pid], start)


@pytest.fixture()
def fake_open(monkeypatch):
    def fake(poll):
        poll.status = PollStatus.OPEN
        poll.message_ts = "2.000"
        db.session.commit()
        return {"success": True, "poll_id": poll.id, "ts": "2.000"}

    monkeypatch.setattr(blocks, "open_poll", fake)
    monkeypatch.setattr(blocks, "refresh_block_post", lambda poll, **k: True)


def test_open_block_poll_maps_and_records_the_opener(db_session, fake_open):
    start = date(2099, 1, 19)
    pids = [_practice(20), _practice(22, is_draft=False)]
    try:
        poll = blocks.create_block_poll(start, date(2099, 2, 1))
        result = blocks.open_block_poll(poll.id, "U0OPENER")
        assert result["success"] is True
        db.session.expire_all()
        poll = db.session.get(LeadAvailabilityPoll, poll.id)
        assert poll.opened_by_slack_uid == "U0OPENER"
        assert [m.practice_id for m in poll.practices] == pids
    finally:
        _cleanup(pids, start)


def test_second_open_is_refused_and_names_the_opener(db_session, fake_open):
    start = date(2099, 1, 19)
    pids = [_practice(20)]
    try:
        poll = blocks.create_block_poll(start, date(2099, 2, 1))
        blocks.open_block_poll(poll.id, "U0FIRST")
        again = blocks.open_block_poll(poll.id, "U0SECOND")
        assert again["success"] is False
        assert "<@U0FIRST>" in again["error"]
    finally:
        _cleanup(pids, start)


def test_open_while_another_open_holds_the_lock_is_refused(db_session, fake_open):
    start = date(2099, 1, 19)
    pids = [_practice(20)]
    try:
        poll = blocks.create_block_poll(start, date(2099, 2, 1))
        poll_id = poll.id
        with db.engine.connect() as other:
            trans = other.begin()
            other.execute(text(
                "SELECT id FROM lead_availability_polls WHERE id = :id FOR UPDATE"),
                {"id": poll_id})
            result = blocks.open_block_poll(poll_id, "U0SECOND")
            trans.rollback()
        assert result["success"] is False
        assert db.session.get(LeadAvailabilityPoll, poll_id).status == PollStatus.DRAFT
    finally:
        _cleanup(pids, start)


def test_failed_open_leaves_the_poll_draft(db_session, monkeypatch):
    start = date(2099, 1, 19)
    pids = [_practice(20)]
    monkeypatch.setattr(blocks, "open_poll", lambda poll: {"success": False, "error": "boom"})
    monkeypatch.setattr(blocks, "refresh_block_post", lambda poll, **k: True)
    try:
        poll = blocks.create_block_poll(start, date(2099, 2, 1))
        result = blocks.open_block_poll(poll.id, "U0X")
        assert result == {"success": False, "error": "boom"}
        db.session.expire_all()
        poll = db.session.get(LeadAvailabilityPoll, poll.id)
        assert poll.status == PollStatus.DRAFT
        assert poll.practices == []
    finally:
        _cleanup(pids, start)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices/test_blocks.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.practices.blocks'`.

- [ ] **Step 3: Implement `app/practices/blocks.py`**

```python
"""Two-week practice blocks.

Every other Monday, a week before a block starts, the block job creates the
block's sessions and its poll row (DRAFT) and posts the block post in
#collab-coaches-practices. Someone on the practices team presses Open poll,
which posts the leads poll. The block post then shows coverage and an Assign
button per session.

The job acts on state, not on the day it runs, so a missed Monday is caught
the next morning. It never creates a block that starts before the anchor:
the block running at cutover (Oct 12 to 25) is made by the cutover script.
"""

from datetime import date, timedelta

from flask import current_app
from sqlalchemy.exc import OperationalError

from app.models import AppConfig, db
from app.practices.availability import (
    PollNotReadyError,
    block_practices,
    create_block_poll,
    map_sessions,
    open_poll,
)
from app.practices.availability_emoji import EmojiSupplyError
from app.practices.availability_models import LeadAvailabilityPoll, PollStatus
from app.practices.drafting import generate_draft_block
from app.utils import today_central

BLOCK_DAYS = 14
DEFAULT_ANCHOR = date(2026, 10, 26)
POST_DAYS_AHEAD = 7       # block post goes up the Monday before
REMINDER_DAYS_AHEAD = 5   # Wednesday of the post week


def block_anchor() -> date:
    raw = AppConfig.get("lead_availability.block_anchor")
    if not raw:
        return DEFAULT_ANCHOR
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        current_app.logger.warning(
            "lead_availability.block_anchor %r is not an ISO date; using %s",
            raw, DEFAULT_ANCHOR)
        return DEFAULT_ANCHOR


def block_start_for(day: date, anchor: date) -> date:
    """Monday that starts the block containing `day`. Pure date math, so DST
    and year boundaries cannot shift it."""
    return day - timedelta(days=(day - anchor).days % BLOCK_DAYS)


def blocks_due(today: date, anchor: date) -> list[date]:
    """Block starts the job should handle today: the current block, and the
    next one from its post day on. Never a block before the anchor."""
    current = block_start_for(today, anchor)
    upcoming = current + timedelta(days=BLOCK_DAYS)
    due = [current]
    if today >= upcoming - timedelta(days=POST_DAYS_AHEAD):
        due.append(upcoming)
    return [start for start in due if start >= anchor]


def poll_for_date(day: date):
    """The block poll whose range covers `day`, if one exists."""
    return (
        LeadAvailabilityPoll.query
        .filter(LeadAvailabilityPoll.starts_on <= day,
                LeadAvailabilityPoll.ends_on >= day)
        .order_by(LeadAvailabilityPoll.created_at.desc())
        .first()
    )


def ensure_block(start: date, today: date) -> dict:
    """Bring one block up to date: sessions, poll row, block post, reminder."""
    end = start + timedelta(days=BLOCK_DAYS - 1)
    poll = LeadAvailabilityPoll.query.filter_by(starts_on=start, ends_on=end).first()
    if poll is None:
        generate_draft_block(start, end)
        if not block_practices(start, end):
            current_app.logger.error(
                "Block %s..%s has no practices and practice_days yields no "
                "slots for it; no block post", start, end)
            return {"start": start, "skipped": "no_sessions"}
        poll = create_block_poll(start, end)

    posted = False
    if poll.block_post_ts is None:
        posted = post_block_post(poll)

    reminded = False
    if (
        poll.status == PollStatus.DRAFT
        and poll.block_post_ts
        and poll.wednesday_reminder_sent_at is None
        and today >= start - timedelta(days=REMINDER_DAYS_AHEAD)
    ):
        reminded = post_wednesday_reply(poll)

    return {"start": start, "poll_id": poll.id, "posted": posted, "reminded": reminded}


def run_block_job(today: date | None = None) -> list[dict]:
    today = today or today_central()
    return [ensure_block(start, today) for start in blocks_due(today, block_anchor())]


def open_block_poll(poll_id: int, opened_by_slack_uid: str | None) -> dict:
    """Post the leads poll for a block. Exactly one caller wins.

    The row lock is held through the Slack post and released by open_poll's
    commit (or our rollback). A second click while the first is in flight
    fails NOWAIT; a click after it sees status open. A crash mid-open rolls
    the transaction back, so nothing gets stuck.
    """
    try:
        poll = (
            LeadAvailabilityPoll.query
            .filter_by(id=poll_id)
            .with_for_update(nowait=True)
            .one()
        )
    except OperationalError:
        db.session.rollback()
        return {"success": False, "error": "Someone is opening this poll right now."}

    if poll.status != PollStatus.DRAFT:
        who = f"<@{poll.opened_by_slack_uid}>" if poll.opened_by_slack_uid else "Someone"
        db.session.rollback()
        return {"success": False, "already_open": True,
                "error": f"{who} already opened this poll."}

    try:
        map_sessions(poll)
    except (PollNotReadyError, EmojiSupplyError) as exc:
        db.session.rollback()
        return {"success": False, "error": str(exc)}

    poll.opened_by_slack_uid = opened_by_slack_uid
    result = open_poll(poll)
    if not result.get("success"):
        db.session.rollback()
        return result

    refresh_block_post(poll)
    return result


# --- Slack side: implemented in Task B5. Module-level so tests can patch. ---

def post_block_post(poll) -> bool:
    raise NotImplementedError


def refresh_block_post(poll, *, exclude_practice_id=None) -> bool:
    raise NotImplementedError


def post_wednesday_reply(poll) -> bool:
    raise NotImplementedError
```

Also re-export `create_block_poll` for the tests (`blocks.create_block_poll` is already importable through the `from app.practices.availability import ...` line).

- [ ] **Step 4: Run the tests**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices/test_blocks.py -q`
Expected: PASS (15 tests).

- [ ] **Step 5: Commit**

```bash
git add app/practices/blocks.py tests/practices/test_blocks.py
git commit -m "feat(blocks): daily block job and locked open_block_poll"
```

### Task B4: Block post Block Kit

**Files:**
- Create: `app/slack/blocks/block_post.py`
- Modify: `app/practices/blocks.py` (add `block_post_rows`, `footer_text`)
- Test: `tests/slack/test_block_post_blocks.py` (create), `tests/practices/test_blocks.py` (append)

**Interfaces:**
- Produces in `blocks.py`: `block_post_rows(poll, *, exclude_practice_id=None) -> list[dict]` where each dict is `{"practice_id": int, "emoji": str | None, "when": datetime, "where": str, "cancelled": bool, "leads": list[str], "coaches": list[str], "leads_needed": int, "available": int}`; `reminder_days(opened_at: datetime, ends_on: date, today: date) -> list[date]`; `footer_text(poll, today: date) -> str | None`.
- Produces in `block_post.py`: `block_range_label(starts_on, ends_on) -> str`, `where_label(practice) -> str`, `session_text(when, where) -> str`, `short_name(user) -> str`, `build_block_post(poll, rows, *, permalink: str | None, footer: str | None) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

`tests/slack/test_block_post_blocks.py` (pure, no DB):

```python
import json
from datetime import date, datetime
from types import SimpleNamespace

from app.slack.blocks.block_post import block_range_label, build_block_post


def _poll(status="draft", message_ts=None, opened_by=None, closed_at=None, pid=7):
    return SimpleNamespace(id=pid, starts_on=date(2099, 1, 19), ends_on=date(2099, 2, 1),
                           status=status, message_ts=message_ts,
                           opened_by_slack_uid=opened_by, opened_at=None,
                           closed_at=closed_at)


def _row(pid, *, emoji="letter_a", where="TEST Wirth · Bounding", leads=(), coaches=(),
         needed=2, available=0, cancelled=False, day=20):
    return {"practice_id": pid, "emoji": emoji, "when": datetime(2099, 1, day, 18, 15),
            "where": where, "cancelled": cancelled, "leads": list(leads),
            "coaches": list(coaches), "leads_needed": needed, "available": available}


def _text(blocks):
    return json.dumps(blocks)


def test_range_label():
    assert block_range_label(date(2026, 10, 26), date(2026, 11, 8)) == "Oct 26 – Nov 8"


def test_before_opening_lists_sessions_with_open_and_edit():
    blocks = build_block_post(_poll(), [_row(1), _row(2, where="location TBD", day=22)],
                              permalink=None, footer=None)
    text = _text(blocks)
    assert "Lead poll · Jan 19 – Feb 1" in text
    assert "location TBD" in text
    assert '"action_id": "block_poll_open"' in text
    assert '"action_id": "edit_practice_full"' in text
    assert "<#C02J4DGCFL2>" in text
    assert "Assign" not in text
    assert "—" not in text


def test_before_opening_omits_cancelled_sessions():
    blocks = build_block_post(_poll(), [_row(1), _row(2, cancelled=True, day=22)],
                              permalink=None, footer=None)
    assert "Thu 1/22" not in _text(blocks)


def test_open_rows_have_dot_letter_leads_and_assign():
    rows = [
        _row(1, leads=["Katrin S"], available=2),                       # yellow, needs 1 more
        _row(2, emoji="letter_b", leads=["Ellie T", "Jacob D"], day=22),  # green
        _row(3, emoji="letter_c", day=22),                              # red
    ]
    blocks = build_block_post(_poll("open", "2.0", "U0CHRIS"), rows,
                              permalink="https://x/p", footer="31 of 60 leads have answered.")
    text = _text(blocks)
    assert "Opened by <@U0CHRIS>" in text and "<https://x/p|see the poll>" in text
    assert ":large_yellow_circle: :letter_a:" in text
    assert "Leads: Katrin S · needs 1 more" in text
    assert ":large_green_circle: :letter_b:" in text
    assert ":red_circle: :letter_c:" in text and "No leads yet" in text
    assert text.count('"action_id": "block_assign"') == 3
    assert "31 of 60 leads have answered." in text
    assert "block_poll_open" not in text


def test_coaches_are_shown_not_counted():
    blocks = build_block_post(_poll("open", "2.0"), [_row(1, coaches=["KJ"])],
                              permalink=None, footer=None)
    text = _text(blocks)
    assert "Coach: KJ · No leads yet" in text
    assert ":red_circle:" in text


def test_leads_needed_one_and_three():
    one = _text(build_block_post(_poll("open", "2.0"), [_row(1, leads=["A B"], needed=1)],
                                 permalink=None, footer=None))
    three = _text(build_block_post(_poll("open", "2.0"), [_row(1, leads=["A B"], needed=3)],
                                   permalink=None, footer=None))
    assert ":large_green_circle:" in one and "needs" not in one
    assert "needs 2 more" in three


def test_cancelled_after_opening_is_struck_through_without_assign():
    blocks = build_block_post(_poll("open", "2.0"), [_row(1, cancelled=True)],
                              permalink=None, footer=None)
    text = _text(blocks)
    assert "~" in text and "Cancelled" in text
    assert "block_assign" not in text


def test_closed_drops_footer_keeps_assign():
    blocks = build_block_post(_poll("closed", "2.0", closed_at=datetime(2099, 2, 2, 8, 30)),
                              [_row(1)], permalink=None, footer=None)
    text = _text(blocks)
    assert "Poll closed Mon 2/2" in text
    assert "block_assign" in text


def test_never_posted_block_reads_collected_outside_the_app():
    blocks = build_block_post(_poll("closed", None), [_row(1, emoji=None)],
                              permalink=None, footer=None)
    text = _text(blocks)
    assert "Availability collected outside the app" in text
    assert ":letter_" not in text
    assert "block_assign" in text
```

Append to `tests/practices/test_blocks.py`:

```python
def test_reminder_days_follow_the_nudge_rules():
    opened = datetime(2099, 1, 12, 19, 0)  # Mon evening
    assert blocks.reminder_days(opened, date(2099, 2, 1), date(2099, 1, 12)) == [
        date(2099, 1, 15), date(2099, 1, 17), date(2099, 1, 19)]
    assert blocks.reminder_days(opened, date(2099, 2, 1), date(2099, 1, 17)) == [
        date(2099, 1, 19)]
    assert blocks.reminder_days(opened, date(2099, 2, 1), date(2099, 1, 19)) == []
    # A Wednesday open
    wed = datetime(2099, 1, 14, 9, 0)
    assert blocks.reminder_days(wed, date(2099, 2, 1), date(2099, 1, 14)) == [
        date(2099, 1, 17), date(2099, 1, 19), date(2099, 1, 21)]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_blocks.py tests/practices/test_blocks.py -q`
Expected: FAIL (module missing, `reminder_days` missing).

- [ ] **Step 3: Implement `app/slack/blocks/block_post.py`**

```python
"""Block Kit for the team's block post. Pure functions over plain data."""

from app.slack.practices._config import COORD_CHANNEL_ID


def block_range_label(starts_on, ends_on) -> str:
    return f"{starts_on.strftime('%b %-d')} – {ends_on.strftime('%b %-d')}"


def _time(when) -> str:
    return when.strftime("%-I:%M%p").replace("PM", "p").replace("AM", "a")


def session_text(when, where) -> str:
    return f"*{when.strftime('%a %-m/%-d')}* · {_time(when)} · {where}"


def where_label(practice) -> str:
    if not practice.location:
        return "location TBD"
    kinds = [t.name for t in practice.practice_types] or [a.name for a in practice.activities]
    name = practice.location.name
    return f"{name} · {', '.join(kinds)}" if kinds else name


def short_name(user) -> str:
    last = (user.last_name or "").strip()
    return f"{user.first_name} {last[:1]}".strip()


def _dot(row) -> str:
    if len(row["leads"]) >= row["leads_needed"]:
        return ":large_green_circle:"
    if row["leads"] or row["available"]:
        return ":large_yellow_circle:"
    return ":red_circle:"


def _leads_line(row) -> str:
    parts = []
    if row["coaches"]:
        parts.append(f"Coach: {', '.join(row['coaches'])}")
    if row["leads"]:
        line = f"Leads: {', '.join(row['leads'])}"
        short = row["leads_needed"] - len(row["leads"])
        if short > 0:
            line += f" · needs {short} more"
        parts.append(line)
    else:
        parts.append("No leads yet")
    return " · ".join(parts)


def _header(poll) -> dict:
    return {"type": "header", "text": {"type": "plain_text",
            "text": f"Lead poll · {block_range_label(poll.starts_on, poll.ends_on)}"}}


def _context(text) -> dict:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text}]}


def _before_opening(poll, rows) -> list[dict]:
    live = [r for r in rows if not r["cancelled"]]
    lines = "\n".join(session_text(r["when"], r["where"]) for r in live) or "_No sessions yet._"
    actions = [{"type": "button", "style": "primary", "action_id": "block_poll_open",
                "value": str(poll.id), "text": {"type": "plain_text", "text": "Open poll"}}]
    if live:
        actions.append({
            "type": "static_select", "action_id": "edit_practice_full",
            "placeholder": {"type": "plain_text", "text": "Edit a session"},
            "options": [{"text": {"type": "plain_text",
                                  "text": f"{r['when'].strftime('%a %-m/%-d')} {_time(r['when'])}"},
                         "value": str(r["practice_id"])} for r in live][:100],
        })
    return [
        _header(poll),
        {"type": "section", "text": {"type": "mrkdwn", "text": lines}},
        _context(f"Opening posts this list to <#{COORD_CHANNEL_ID}> for leads to react to. "
                 "Missing details are fine; the poll updates when you fill them in."),
        {"type": "actions", "elements": actions},
    ]


def _row_section(row) -> dict:
    letter = f":{row['emoji']}:  " if row["emoji"] else ""
    if row["cancelled"]:
        return {"type": "section", "text": {"type": "mrkdwn",
                "text": f"{letter}~{session_text(row['when'], row['where'])}~  Cancelled"}}
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text":
                 f"{_dot(row)} {letter}{session_text(row['when'], row['where'])}\n{_leads_line(row)}"},
        "accessory": {"type": "button", "action_id": "block_assign",
                      "value": str(row["practice_id"]),
                      "text": {"type": "plain_text", "text": "Assign"}},
    }


def _status_line(poll, permalink) -> str:
    if poll.status == "closed" and not poll.message_ts:
        return "Availability collected outside the app"
    if poll.status == "closed":
        when = poll.closed_at.strftime("%a %-m/%-d") if poll.closed_at else ""
        return f"Poll closed {when}".strip()
    opener = f"Opened by <@{poll.opened_by_slack_uid}>" if poll.opened_by_slack_uid else "Opened"
    return f"{opener} · <{permalink}|see the poll>" if permalink else opener


def build_block_post(poll, rows, *, permalink, footer) -> list[dict]:
    if poll.status == "draft":
        return _before_opening(poll, rows)
    blocks = [_header(poll), _context(_status_line(poll, permalink))]
    blocks.extend(_row_section(r) for r in rows[:40])
    if footer and poll.status == "open":
        blocks.append(_context(footer))
    return blocks
```

- [ ] **Step 4: Add the data side to `app/practices/blocks.py`**

```python
from datetime import datetime  # add to the existing datetime import line

from app.practices.availability import eligible_leads  # add to the existing import
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityResponse,
    ParticipantStatus,
)
from app.practices.interfaces import PracticeStatus

FIRST_NUDGE_AFTER_DAYS = 3
MIN_DAYS_BETWEEN_NUDGES = 2
MAX_NUDGES = 3


def block_post_rows(poll, *, exclude_practice_id=None) -> list[dict]:
    from app.slack.blocks.block_post import short_name, where_label

    letters = {m.practice_id: m.emoji for m in poll.practices}
    available = {}
    if poll.message_ts:
        for row in LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).all():
            available[row.practice_id] = available.get(row.practice_id, 0) + 1

    rows = []
    for practice in block_practices(poll.starts_on, poll.ends_on):
        if practice.id == exclude_practice_id:
            continue
        leads = [l.user for l in practice.leads if l.role == "lead" and l.user]
        coaches = [l.user for l in practice.leads if l.role == "coach" and l.user]
        rows.append({
            "practice_id": practice.id,
            "emoji": letters.get(practice.id),
            "when": practice.date,
            "where": where_label(practice),
            "cancelled": practice.status == PracticeStatus.CANCELLED.value,
            "leads": [short_name(u) for u in leads],
            "coaches": [short_name(u) for u in coaches],
            "leads_needed": practice.leads_needed or 2,
            "available": available.get(practice.id, 0),
        })
    return rows


def reminder_days(opened_at: datetime, ends_on: date, today: date) -> list[date]:
    """Days the remaining nudges go out, per participants_to_nudge's rules."""
    first = opened_at.date() + timedelta(days=FIRST_NUDGE_AFTER_DAYS)
    days = [first + timedelta(days=MIN_DAYS_BETWEEN_NUDGES * i) for i in range(MAX_NUDGES)]
    return [d for d in days if today < d <= ends_on]


def footer_text(poll, today: date) -> str | None:
    if poll.status != PollStatus.OPEN or not poll.opened_at:
        return None
    pool = {u.id for u in eligible_leads()}
    answered = sum(
        1 for p in LeadAvailabilityParticipant.query.filter_by(poll_id=poll.id).all()
        if p.user_id in pool and p.status != ParticipantStatus.PENDING
    )
    text = f"{answered} of {len(pool)} leads have answered."
    days = reminder_days(poll.opened_at, poll.ends_on, today)
    if days:
        names = [d.strftime("%a") for d in days]
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        text += f" Reminders go to the rest {joined}."
    return text
```

Check that `PracticeLead` has a `user` relationship (`grep -n "user = " app/practices/models.py` near `class PracticeLead`); if it is named differently, use that name.

- [ ] **Step 5: Run the tests**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_blocks.py tests/practices/test_blocks.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/slack/blocks/block_post.py app/practices/blocks.py tests/slack/test_block_post_blocks.py tests/practices/test_blocks.py
git commit -m "feat(blocks): block post Block Kit and row data"
```

### Task B5: Slack side: post, refresh, Wednesday reply, buttons

**Files:**
- Modify: `app/practices/blocks.py` (implement the three Slack functions)
- Modify: `app/slack/practices/refresh.py` (new `block_post` surface)
- Modify: `app/slack/bolt_app.py` (`block_poll_open` action; `edit_practice_full` reads a select)
- Test: `tests/slack/test_block_post_slack.py` (create)

**Interfaces:**
- Produces: `post_block_post(poll) -> bool`, `refresh_block_post(poll, *, exclude_practice_id=None) -> bool`, `post_wednesday_reply(poll) -> bool`.

- [ ] **Step 1: Write the failing tests**

`tests/slack/test_block_post_slack.py`:

```python
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from app.models import db
from app.practices import blocks
from app.practices.availability_models import LeadAvailabilityPoll, PollStatus
from app.practices.models import Practice
from app.slack.practices._config import COLLAB_CHANNEL_ID


@pytest.fixture()
def block(db_session):
    db.session.rollback()
    practice = Practice(date=datetime(2099, 1, 20, 18, 15), day_of_week="Tuesday",
                        is_draft=True, leads_needed=2, logistics_notes="TEST b5")
    db.session.add(practice)
    db.session.commit()
    poll = blocks.create_block_poll(date(2099, 1, 19), date(2099, 2, 1))
    ids = (practice.id, poll.id)
    yield poll
    db.session.rollback()
    stored = db.session.get(LeadAvailabilityPoll, ids[1])
    if stored is not None:
        db.session.delete(stored)
    db.session.commit()
    p = db.session.get(Practice, ids[0])
    if p is not None:
        db.session.delete(p)
    db.session.commit()


@pytest.fixture()
def client(monkeypatch):
    fake = MagicMock()
    fake.chat_postMessage.return_value = {"ts": "9.000"}
    monkeypatch.setattr("app.practices.blocks.get_slack_client", lambda: fake)
    return fake


def test_post_block_post_records_the_ts(block, client):
    assert blocks.post_block_post(block) is True
    assert block.block_post_ts == "9.000"
    assert client.chat_postMessage.call_args.kwargs["channel"] == COLLAB_CHANNEL_ID


def test_post_block_post_never_raises(block, client):
    client.chat_postMessage.side_effect = RuntimeError("slack down")
    assert blocks.post_block_post(block) is False
    assert block.block_post_ts is None


def test_refresh_updates_in_place(block, client):
    block.block_post_ts = "9.000"
    db.session.commit()
    assert blocks.refresh_block_post(block) is True
    assert client.chat_update.call_args.kwargs["ts"] == "9.000"


def test_refresh_without_a_post_is_a_no_op(block, client):
    assert blocks.refresh_block_post(block) is False
    client.chat_update.assert_not_called()


def test_wednesday_reply_threads_and_marks_sent(block, client):
    block.block_post_ts = "9.000"
    db.session.commit()
    assert blocks.post_wednesday_reply(block) is True
    kwargs = client.chat_postMessage.call_args.kwargs
    assert kwargs["thread_ts"] == "9.000"
    assert "Nobody has opened the lead poll for *Jan 19 – Feb 1* yet" in str(kwargs["blocks"])
    assert block.wednesday_reminder_sent_at is not None


def test_practice_edit_refreshes_its_block_post(block, client):
    from app.slack.practices.refresh import PRACTICE_SURFACES, _refresh_block_post

    block.block_post_ts = "9.000"
    db.session.commit()
    practice = Practice.query.filter_by(logistics_notes="TEST b5").one()
    assert _refresh_block_post(practice, "edit") == {"success": True}
    assert "block_post" in {surface.name for surface in PRACTICE_SURFACES}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_slack.py -q`
Expected: FAIL (`NotImplementedError`, no `get_slack_client` in blocks).

- [ ] **Step 3: Implement the Slack functions in `blocks.py`**

Replace the three `NotImplementedError` stubs with:

```python
from app.slack.client import get_slack_client           # top of module
from app.slack.practices._config import COLLAB_CHANNEL_ID
from app.utils import now_central_naive


def _render(poll, *, exclude_practice_id=None) -> tuple[list[dict], str]:
    from app.slack.blocks.block_post import block_range_label, build_block_post
    from app.slack.practices.availability_nudge import poll_permalink

    permalink = poll_permalink(poll) if poll.message_ts else None
    rows = block_post_rows(poll, exclude_practice_id=exclude_practice_id)
    blocks = build_block_post(poll, rows, permalink=permalink,
                              footer=footer_text(poll, today_central()))
    return blocks, f"Lead poll {block_range_label(poll.starts_on, poll.ends_on)}"


def post_block_post(poll) -> bool:
    try:
        blocks, text = _render(poll)
        response = get_slack_client().chat_postMessage(
            channel=COLLAB_CHANNEL_ID, blocks=blocks, text=text)
    except Exception as exc:  # noqa: BLE001 - never raise; the job retries tomorrow
        current_app.logger.warning("Block post for poll %s failed: %s", poll.id, exc)
        return False
    poll.block_post_ts = response["ts"]
    db.session.commit()
    return True


def refresh_block_post(poll, *, exclude_practice_id=None) -> bool:
    if not poll.block_post_ts:
        return False
    try:
        blocks, text = _render(poll, exclude_practice_id=exclude_practice_id)
        get_slack_client().chat_update(
            channel=COLLAB_CHANNEL_ID, ts=poll.block_post_ts, blocks=blocks, text=text)
    except Exception as exc:  # noqa: BLE001 - never raise; next edit or morning repairs it
        current_app.logger.warning("Block post refresh for poll %s failed: %s", poll.id, exc)
        return False
    return True


def post_wednesday_reply(poll) -> bool:
    from app.slack.blocks.block_post import block_range_label, session_text

    rows = [r for r in block_post_rows(poll) if not r["cancelled"]]
    first = f" The first practice is {session_text(rows[0]['when'], '').rstrip(' ·').replace('*', '')}." if rows else ""
    label = block_range_label(poll.starts_on, poll.ends_on)
    blocks = [{
        "type": "section",
        "text": {"type": "mrkdwn",
                 "text": f"Nobody has opened the lead poll for *{label}* yet.{first}"},
        "accessory": {"type": "button", "style": "primary", "action_id": "block_poll_open",
                      "value": str(poll.id), "text": {"type": "plain_text", "text": "Open poll"}},
    }]
    kwargs = {"channel": COLLAB_CHANNEL_ID, "blocks": blocks,
              "text": f"Nobody has opened the lead poll for {label} yet."}
    if poll.block_post_ts:
        kwargs["thread_ts"] = poll.block_post_ts
    try:
        get_slack_client().chat_postMessage(**kwargs)
    except Exception as exc:  # noqa: BLE001 - never raise
        current_app.logger.warning("Wednesday reply for poll %s failed: %s", poll.id, exc)
        return False
    poll.wednesday_reminder_sent_at = now_central_naive()
    db.session.commit()
    return True
```

Simplify the `first` line if it reads awkwardly once rendered: the target copy is "The first practice is Tue 10/27." Use `rows[0]['when'].strftime('%a %-m/%-d')` directly:

```python
    first = f" The first practice is {rows[0]['when'].strftime('%a %-m/%-d')}." if rows else ""
```

- [ ] **Step 4: Register the refresh surface**

In `app/slack/practices/refresh.py`, before `WEEKLY_CHANGE_TYPES`:

```python
def _refresh_block_post(practice, change_type, **_context):
    """Re-render the team's block post for the block covering this practice."""
    try:
        from app.practices.blocks import poll_for_date, refresh_block_post

        poll = poll_for_date(practice.date.date())
        if poll is None or not poll.block_post_ts:
            return {"skipped": "no_block_post"}
        exclude = practice.id if change_type == "delete" else None
        ok = refresh_block_post(poll, exclude_practice_id=exclude)
        return {"success": True} if ok else {"success": False, "error": "refresh failed"}
    except Exception as exc:
        logger.warning("Block post refresh for practice #%s failed: %s", practice.id, exc)
        return {"success": False, "error": str(exc)}


BLOCK_POST_CHANGE_TYPES = ("edit", "cancel", "delete", "create")
```

and add to `PRACTICE_SURFACES`:

```python
    PracticeSurface(
        "block_post",
        None,
        BLOCK_POST_CHANGE_TYPES,
        _refresh_block_post,
    ),
```

- [ ] **Step 5: Wire the Slack actions**

In `app/slack/bolt_app.py`, in `handle_edit_practice_full`, replace `practice_id = int(action["value"])` with:

```python
        # Fill in buttons send a value; the block post's "Edit a session"
        # select sends the chosen option.
        raw = action.get("value") or (action.get("selected_option") or {}).get("value")
        practice_id = int(raw)
```

Add a new action next to it:

```python
    @bolt_app.action("block_poll_open")
    def handle_block_poll_open(ack, body, action, client, logger):
        """Open poll on the block post, its Wednesday reply or the Sunday summary."""
        ack()
        user_id = body["user"]["id"]
        with get_app_context():
            from app.practices.blocks import open_block_poll

            result = open_block_poll(int(action["value"]), user_id)
        if not result.get("success"):
            channel = (body.get("channel") or {}).get("id")
            if channel:
                client.chat_postEphemeral(channel=channel, user=user_id,
                                          text=f":warning: {result.get('error')}")
```

- [ ] **Step 6: Run the tests**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_slack.py tests/practices/test_blocks.py tests/slack -q`
Expected: PASS. Existing refresh tests that assert the exact set of surface names need `block_post` added.

- [ ] **Step 7: Commit**

```bash
git add app/practices/blocks.py app/slack/practices/refresh.py app/slack/bolt_app.py tests/slack
git commit -m "feat(blocks): post, refresh and remind on the block post; Open poll action"
```

### Task B6: Scheduler wiring

**Files:**
- Modify: `app/scheduler.py`, `app/practices/availability.py` (`close_poll`)
- Test: `tests/test_scheduler_lead_availability.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scheduler_lead_availability.py` (match its existing app fixture):

```python
def test_block_job_is_registered_daily_at_nine():
    from apscheduler.schedulers.background import BackgroundScheduler
    from app import scheduler as sched_module
    import inspect

    source = inspect.getsource(sched_module)
    assert "id='lead_block_job'" in source
    assert "practice_block_bootstrap" not in source
    assert "practice_block_readiness_nudge" not in source


def test_close_job_closes_unopened_drafts(app, monkeypatch):
    from datetime import date
    from app.models import db
    from app.practices.availability_models import LeadAvailabilityPoll, PollStatus
    from app.scheduler import run_close_expired_polls_job

    monkeypatch.setattr("app.practices.blocks.refresh_block_post", lambda poll, **k: True)
    with app.app_context():
        db.session.rollback()
        poll = LeadAvailabilityPoll(starts_on=date(2000, 1, 3), ends_on=date(2000, 1, 16),
                                    status=PollStatus.DRAFT, channel_id="C0TEST")
        db.session.add(poll)
        db.session.commit()
        poll_id = poll.id
        try:
            run_close_expired_polls_job(app)
            db.session.expire_all()
            assert db.session.get(LeadAvailabilityPoll, poll_id).status == PollStatus.CLOSED
        finally:
            db.session.rollback()
            stored = db.session.get(LeadAvailabilityPoll, poll_id)
            if stored is not None:
                db.session.delete(stored)
            db.session.commit()
```

(Year 2000 is safe here: it is in the past, so no real poll can collide, and the close job only closes past `ends_on`.)

- [ ] **Step 2: Run them to verify they fail**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/test_scheduler_lead_availability.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `app/practices/availability.py`, `close_poll`: skip the reconcile for a poll that never posted:

```python
    reconcile_result = reconcile_poll(poll) if poll.message_ts else {}
```

In `app/scheduler.py`:

```python
def run_lead_block_job(app: Flask):
    """Daily 09:00: create, post and remind for two-week lead blocks."""
    with app.app_context():
        from app.practices.blocks import run_block_job

        try:
            results = run_block_job()
            app.logger.info(f"Lead block job: {results}")
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Lead block job failed: {e}", exc_info=True)
```

Register it where the removed drafting jobs were:

```python
    # Daily: two-week lead blocks (block post, Wednesday reminder)
    scheduler.add_job(
        func=run_lead_block_job,
        args=[app],
        trigger=CronTrigger(hour=9, minute=0, timezone='America/Chicago'),
        id='lead_block_job',
        name='Lead Block Job',
        replace_existing=True,
        misfire_grace_time=3600,
    )
```

In `run_lead_availability_nudge_job`, after the `app.logger.info(f"Poll {poll.id} nudges: ...")` line inside the `try`:

```python
                from app.practices.blocks import refresh_block_post
                refresh_block_post(poll)
```

In `run_close_expired_polls_job`, change the filter to `LeadAvailabilityPoll.status.in_([PollStatus.OPEN, PollStatus.DRAFT])`, and after `close_poll(poll)`:

```python
                from app.practices.blocks import refresh_block_post
                refresh_block_post(poll)
```

- [ ] **Step 4: Run the tests**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/test_scheduler_lead_availability.py tests/practices/test_poll_closing.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/scheduler.py app/practices/availability.py tests/test_scheduler_lead_availability.py
git commit -m "feat(scheduler): daily lead block job; nudge and close refresh the block post"
```

### Task B7: Admin page: Open poll on the card, Run block job now

**Files:**
- Modify: `app/routes/admin_availability.py` (rewrite routes)
- Modify: `app/static/admin_practices.js`, `app/templates/admin/practices/list.html`
- Test: `tests/routes/test_admin_availability.py`, `tests/js/draft_publish.test.js`

**Interfaces:**
- Routes: `GET /admin/availability/` returns `{"polls": [{"id", "starts_on", "ends_on", "status", "sessions", "posted": bool}]}`; `POST /admin/availability/polls/<id>/open` calls `open_block_poll(id, None)`; `POST /admin/availability/block-job/run` calls `run_block_job()`. `POST /admin/availability/polls/create` is deleted.

- [ ] **Step 1: Write the failing tests**

In `tests/routes/test_admin_availability.py`, delete tests of `create_poll` and add (matching the file's admin client fixture):

```python
def test_create_route_is_gone(admin_client):
    assert admin_client.post("/admin/availability/polls/create", json={}).status_code == 404


def test_open_route_uses_open_block_poll(admin_client, monkeypatch):
    calls = []
    monkeypatch.setattr("app.routes.admin_availability.open_block_poll",
                        lambda pid, who: calls.append((pid, who)) or {"success": True})
    response = admin_client.post("/admin/availability/polls/42/open")
    assert response.status_code == 200
    assert calls == [(42, None)]


def test_run_block_job_route(admin_client, monkeypatch):
    monkeypatch.setattr("app.routes.admin_availability.run_block_job", lambda: [{"start": "x"}])
    response = admin_client.post("/admin/availability/block-job/run")
    assert response.status_code == 200
    assert response.get_json()["results"] == [{"start": "x"}]
```

Add to `tests/js/draft_publish.test.js` (and add `pollCardHtml` to the export list if missing):

```javascript
test('an unopened block offers Open poll on its card', () => {
  const {pollCardHtml} = load();
  const html = pollCardHtml({id: 9, starts_on: '2099-05-04', ends_on: '2099-05-17',
    status: 'draft', sessions: 6, posted: false});
  assert.match(html, /pl-poll-open/);
  assert.match(html, /data-poll-id="9"/);
});

test('a block that never had a poll reads Assign only', () => {
  const {pollCardHtml} = load();
  const html = pollCardHtml({id: 9, starts_on: '2099-05-04', ends_on: '2099-05-17',
    status: 'closed', sessions: 6, posted: false});
  assert.match(html, /Assign only/);
});

test('the date-range poll toolbar is gone', () => {
  assert.doesNotMatch(SOURCE, /pl-poll-start|openAvailabilityPoll/);
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/routes/test_admin_availability.py -q; node --test tests/js/draft_publish.test.js`
Expected: FAIL.

- [ ] **Step 3: Rewrite `app/routes/admin_availability.py`**

```python
"""Admin fallback for two-week lead blocks.

The main path is the block post in #collab-coaches-practices. This page lists
recent blocks, offers Open poll on an unopened one, and can run the block job
by hand (useful on deploy day).
"""

from flask import Blueprint, jsonify

from ..auth import admin_required
from ..practices.availability_models import LeadAvailabilityPoll
from ..practices.blocks import open_block_poll, run_block_job

admin_availability_bp = Blueprint(
    "admin_availability", __name__, url_prefix="/admin/availability")


@admin_availability_bp.route("/")
@admin_required
def dashboard():
    from ..practices.availability import block_practices

    polls = LeadAvailabilityPoll.query.order_by(
        LeadAvailabilityPoll.starts_on.desc()).limit(6).all()
    return jsonify({"polls": [{
        "id": p.id,
        "starts_on": p.starts_on.isoformat(),
        "ends_on": p.ends_on.isoformat(),
        "status": p.status,
        "sessions": len(block_practices(p.starts_on, p.ends_on)),
        "posted": bool(p.message_ts),
    } for p in polls]})


@admin_availability_bp.route("/polls/<int:poll_id>/open", methods=["POST"])
@admin_required
def open_poll_route(poll_id):
    result = open_block_poll(poll_id, None)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "could not open poll")}), 400
    return jsonify(result)


@admin_availability_bp.route("/block-job/run", methods=["POST"])
@admin_required
def run_block_job_route():
    results = run_block_job()
    return jsonify({"results": [{k: str(v) for k, v in r.items()} for r in results]})
```

The test expects `results` passed through; since the monkeypatched value is `[{"start": "x"}]` the `str()` mapping leaves it equal.

- [ ] **Step 4: Change the admin JS and template**

`app/templates/admin/practices/list.html`: replace the whole `<div class="pl-toolbar" style="margin-top:-10px">...</div>` (date inputs and Open Availability Poll button) with:

```html
  <div class="pl-toolbar" style="margin-top:-10px">
    <span style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.04em">Lead polls</span>
    <button type="button" id="pl-block-job-btn" class="pl-btn pl-btn-ghost">Run block job now</button>
  </div>
```

and add CSS next to `.pl-poll-publish` rules (rename them): replace `pl-poll-publish` with `pl-poll-open` in the three CSS rules.

`app/static/admin_practices.js`:
- delete `openAvailabilityPoll` and its comment header
- in `attachEventListeners` replace the `pl-poll-btn` listener with:

```javascript
  document.getElementById('pl-block-job-btn').addEventListener('click', runBlockJob);
  document.getElementById('pl-polls').addEventListener('click', (e) => {
    const btn = e.target.closest('.pl-poll-open');
    if (btn) openBlockPoll(parseInt(btn.dataset.pollId));
  });
```

- set `const POLL_STATUS_LABEL = {draft: 'Not opened', open: 'Open', closed: 'Closed'};`
- replace `pollCardHtml` with:

```javascript
function pollCardHtml(poll) {
  const st = poll.status || 'draft';
  const n = (c, w) => `${c} ${w}${c === 1 ? '' : 's'}`;
  let act = '';
  if (st === 'draft') {
    act = `<button type="button" class="pl-poll-open" data-poll-id="${esc(poll.id)}">Open poll</button>`;
  } else if (st === 'closed' && !poll.posted) {
    act = '<span class="pl-poll-note">Assign only</span>';
  }
  return `<div class="pl-poll">`
    + `<span class="pl-poll-range">${esc(pollRangeLabel(poll))}</span>`
    + `<span class="pl-poll-status is-${esc(st)}">${esc(POLL_STATUS_LABEL[st] || st)}</span>`
    + `<span class="pl-poll-sessions">${n(poll.sessions, 'session')}</span>`
    + `<span class="pl-poll-act">${act}</span></div>`;
}

async function openBlockPoll(pollId) {
  const btn = document.querySelector(`.pl-poll-open[data-poll-id="${pollId}"]`);
  if (btn) { btn.disabled = true; btn.textContent = 'Opening…'; }
  try {
    const r = await fetch(`/admin/availability/polls/${pollId}/open`, {method: 'POST'});
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || ('HTTP ' + r.status));
    showToast('Lead poll posted to #coord-practices-leads-assists', 'success');
  } catch (e) {
    showToast(e.message || 'Could not open the poll', 'error');
  } finally {
    await loadAvailabilityPolls();
    renderPolls();
  }
}

async function runBlockJob() {
  const btn = document.getElementById('pl-block-job-btn');
  btn.disabled = true;
  try {
    const r = await fetch('/admin/availability/block-job/run', {method: 'POST'});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    showToast('Block job ran', 'success');
  } catch (e) {
    showToast('Block job failed', 'error');
  } finally {
    btn.disabled = false;
    await loadAvailabilityPolls();
    renderPolls();
  }
}
```

- [ ] **Step 5: Run the tests**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/routes/test_admin_availability.py -q && npm run test:practice-reactions`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routes/admin_availability.py app/static/admin_practices.js app/templates/admin/practices/list.html tests
git commit -m "feat(admin): block cards with Open poll; Run block job now"
```

### Task B8: Open poll button in the Sunday coach summary

**Files:**
- Modify: `app/slack/blocks/coach_review.py` (`build_coach_weekly_summary_blocks` signature and footer)
- Modify: `app/slack/practices/coach_review.py` (`post_coach_weekly_summary`)
- Test: `tests/slack/test_coach_summary_drafts.py`

- [ ] **Step 1: Write the failing test**

```python
def test_unopened_block_poll_offers_open_poll():
    blocks = build_coach_weekly_summary_blocks(
        [_practice(5)], _EXPECTED_DAYS, _WEEK_START, open_poll_id=12)
    text = json.dumps(blocks)
    assert '"action_id": "block_poll_open"' in text
    assert '"value": "12"' in text
    assert "Publish" not in text


def test_no_open_poll_button_by_default():
    blocks = build_coach_weekly_summary_blocks([_practice(5)], _EXPECTED_DAYS, _WEEK_START)
    assert "block_poll_open" not in json.dumps(blocks)
```

- [ ] **Step 2: Run to verify failure**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_coach_summary_drafts.py -q`
Expected: FAIL (`unexpected keyword argument 'open_poll_id'`).

- [ ] **Step 3: Implement**

Signature: `def build_coach_weekly_summary_blocks(practices, expected_days, week_start, open_poll_id=None) -> list[dict]:`. Just before the footer `blocks.append(...)`:

```python
    if open_poll_id is not None:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn",
                     "text": ":ballot_box_with_ballot: The lead poll for this week's block hasn't been opened."},
            "accessory": {"type": "button", "style": "primary", "action_id": "block_poll_open",
                          "value": str(open_poll_id),
                          "text": {"type": "plain_text", "text": "Open poll"}},
        })
```

In `app/slack/practices/coach_review.py` add:

```python
def _unopened_block_poll_id(week_start):
    """The poll id for this week's block if nobody has opened it yet."""
    from app.practices.availability_models import PollStatus
    from app.practices.blocks import poll_for_date

    poll = poll_for_date(week_start.date())
    return poll.id if poll is not None and poll.status == PollStatus.DRAFT else None
```

and in `post_coach_weekly_summary` replace the existing `blocks = build_coach_weekly_summary_blocks(...)` line with:

```python
    blocks = build_coach_weekly_summary_blocks(
        practice_infos, expected_days, week_start,
        open_poll_id=_unopened_block_poll_id(week_start))
```

In `tests/slack/test_coach_summary_posting.py`, `run_coach_summary`, add `patch.object(coach_review, "_unopened_block_poll_id", return_value=None)` to its `with` chain (those tests run without a database), and add:

```python
def test_summary_passes_the_unopened_poll_to_the_blocks():
    with patch.object(coach_review, "build_coach_weekly_summary_blocks",
                      return_value=[]) as build, \
         patch.object(coach_review, "_unopened_block_poll_id", return_value=12):
        run_coach_summary([])
    assert build.call_args.kwargs["open_poll_id"] == 12
```

If `run_coach_summary` already patches `build_coach_weekly_summary_blocks` itself, assert on that patch's call args instead of nesting a second patch.

- [ ] **Step 4: Run the tests**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/slack tests/slack
git commit -m "feat(practices): Sunday summary offers Open poll for an unopened block"
```

### Task B9: Phase B PR

- [ ] **Step 1: Full verification**

```bash
DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape 2>&1 | tail -5
npm run test:practice-reactions
```

Expected: no new failures against the baseline.

- [ ] **Step 2: Push and open a draft PR based on part A**

```bash
git push -u origin lead-availability-blocks
gh pr create --draft --base lead-availability-simplify --title "Lead availability v2, part B: two-week block cycle" --body "$(cat <<'EOF'
Part B of docs/superpowers/specs/2026-10-05-lead-availability-simplification-design.md.

- Daily lead block job (09:00): creates each block's sessions, its poll row and the block post in #collab-coaches-practices a week ahead; Wednesday reminder if unopened. Acts on state, so a missed day is caught next morning. Never creates a block before the anchor (2026-10-26).
- Open poll from the block post, its Wednesday reply, the Sunday summary or the admin card. A row lock makes sure one poll posts.
- Block post renders before opening, open (dot, letter, leads, Assign) and closed.
- Migration adds four poll columns.

Stacked on part A. Must be live before Mon Oct 19 09:00, or run the block job by hand that day.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

# Phase C: Assign, letters, cutover, demo

Branch:

```bash
git switch -c lead-availability-assign
```

### Task C1: Late sessions get the next letter

**Files:**
- Modify: `app/slack/practices/refresh.py` (`_refresh_availability_poll`, `AVAILABILITY_POLL_CHANGE_TYPES`)
- Modify: `app/practices/availability.py` (add `append_session`)
- Modify: `app/routes/admin_practices.py` (delete `_uncovered_by_open_poll_warning` and its two call sites and `availability_warning` payloads)
- Modify: `app/templates/admin/practices/_detail_script.js` (delete the stash), `app/static/admin_practices.js` (delete `flashPendingAvailabilityWarning` and its call)
- Modify spec: `docs/superpowers/specs/2026-10-05-lead-availability-simplification-design.md` (the 22-cap sentence)
- Test: `tests/slack/test_availability_poll_refresh.py`, `tests/routes/test_admin_practices_routes.py`, `tests/js/draft_publish.test.js`

**Interfaces:**
- Produces: `append_session(poll, practice) -> str | None` (returns the new emoji name, or None when out of letters; commits).

- [ ] **Step 1: Write the failing tests**

Append to `tests/slack/test_availability_poll_refresh.py` (it already has `_practice`, `_poll`, `_capture`, `_cleanup`):

```python
def test_a_practice_created_inside_an_open_poll_gets_the_next_letter(db_session):
    db.session.rollback()
    practices = [_practice(4, "TEST C1 Loc A", "TEST C1 Type A"),
                 _practice(6, "TEST C1 Loc B", "TEST C1 Type B")]
    poll = _poll(practices, PollStatus.OPEN, "1.000")
    poll.next_position = 2
    new = Practice(date=datetime(2099, 8, 11, 18, 15), day_of_week="Tuesday", is_draft=True)
    db.session.add(new)
    db.session.commit()
    new_id, poll_id = new.id, poll.id
    ids = _capture(practices + [new], [poll])
    client = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=client), \
             patch("app.practices.availability.get_slack_client", return_value=client):
            _refresh_availability_poll(new, "create")
        mapping = LeadAvailabilityPollPractice.query.filter_by(
            poll_id=poll_id, practice_id=new_id).one()
        assert (mapping.emoji, mapping.position) == ("letter_c", 2)
        client.reactions_add.assert_any_call(
            channel="TEST_C_POLL", timestamp="1.000", name="letter_c")
    finally:
        _cleanup(ids)


def test_a_deleted_sessions_letter_is_never_reused(db_session):
    db.session.rollback()
    practices = [_practice(4, "TEST C1 Loc C", "TEST C1 Type C"),
                 _practice(6, "TEST C1 Loc D", "TEST C1 Type D")]
    poll = _poll(practices, PollStatus.OPEN, "1.000")
    poll.next_position = 2
    db.session.commit()
    ids = _capture(practices, [poll])
    poll_id = poll.id
    client = MagicMock()
    try:
        db.session.delete(practices[1])      # held letter_b; its pill stays on Slack
        new = Practice(date=datetime(2099, 8, 11, 18, 15), day_of_week="Tuesday", is_draft=True)
        db.session.add(new)
        db.session.commit()
        ids["practice_ids"].append(new.id)
        with patch("app.slack.client.get_slack_client", return_value=client), \
             patch("app.practices.availability.get_slack_client", return_value=client):
            _refresh_availability_poll(new, "create")
        mapping = LeadAvailabilityPollPractice.query.filter_by(
            poll_id=poll_id, practice_id=new.id).one()
        assert mapping.emoji == "letter_c"
    finally:
        _cleanup(ids)


def test_poll_rows_say_location_tbd(db_session):
    from app.practices.availability import poll_rows

    db.session.rollback()
    bare = Practice(date=datetime(2099, 8, 4, 18, 15), day_of_week="Tuesday", is_draft=True)
    db.session.add(bare)
    db.session.flush()
    poll = _poll([bare], PollStatus.OPEN, "1.000")
    ids = _capture([bare], [poll])
    try:
        assert poll_rows(poll)[0]["location"] == "Location TBD"
    finally:
        _cleanup(ids)
```

In `tests/routes/test_admin_practices_routes.py` delete `open_poll_covering_create_date` and every test that asserts `availability_warning`. In `tests/js/draft_publish.test.js` delete the two `flashPendingAvailabilityWarning` tests and remove it from `load()`'s export list, and add:

```javascript
test('the open-poll warning handoff is gone', () => {
  assert.doesNotMatch(SOURCE, /tcsc-availability-warning|flashPendingAvailabilityWarning/);
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_availability_poll_refresh.py -q; node --test tests/js/draft_publish.test.js`
Expected: FAIL.

- [ ] **Step 3: Implement `append_session`**

In `app/practices/availability.py`:

```python
def append_session(poll, practice) -> str | None:
    """Give a practice added to an OPEN poll's range the next letter.

    Letters only count up (poll.next_position): a deleted session's pill and
    reactions stay on the message, so its letter is never handed out again.
    Returns the new emoji name, or None when the poll is out of letters.
    """
    try:
        name = letter_emoji(poll.next_position + 1)[-1]
    except EmojiSupplyError:
        current_app.logger.error(
            "Poll %s is out of letters; practice %s (%s) collects no availability. "
            "Assign its leads by hand.", poll.id, practice.id, practice.date)
        return None
    db.session.add(LeadAvailabilityPollPractice(
        poll_id=poll.id, practice_id=practice.id, emoji=name, position=poll.next_position))
    poll.next_position += 1
    db.session.commit()
    try:
        get_slack_client().reactions_add(
            channel=poll.channel_id, timestamp=poll.message_ts, name=name)
    except Exception as exc:  # noqa: BLE001 - the letter still works without the seed
        current_app.logger.warning("Could not seed :%s: on poll %s: %s", name, poll.id, exc)
    return name
```

Add `EmojiSupplyError` to the `availability_emoji` import at the top of the file.

- [ ] **Step 4: Find polls by range in the refresh surface**

In `app/slack/practices/refresh.py`:

```python
AVAILABILITY_POLL_CHANGE_TYPES = ("edit", "cancel", "delete", "create")
```

In `_refresh_availability_poll`, replace the `polls = (... .all())` query and the `if not polls:` block with:

```python
        from app.practices.availability import append_session
        from app.practices.interfaces import PracticeStatus

        mapped = (
            LeadAvailabilityPoll.query
            .join(LeadAvailabilityPollPractice,
                  LeadAvailabilityPollPractice.poll_id == LeadAvailabilityPoll.id)
            .filter(LeadAvailabilityPoll.status == PollStatus.OPEN,
                    LeadAvailabilityPollPractice.practice_id == practice.id)
            .all()
        )
        if not mapped and change_type in ("create", "edit") \
                and practice.status != PracticeStatus.CANCELLED.value:
            day = practice.date.date()
            covering = LeadAvailabilityPoll.query.filter(
                LeadAvailabilityPoll.status == PollStatus.OPEN,
                LeadAvailabilityPoll.starts_on <= day,
                LeadAvailabilityPoll.ends_on >= day,
            ).all()
            for poll in covering:
                if append_session(poll, practice):
                    mapped.append(poll)
        polls = mapped
        if not polls:
            return {"skipped": "no_poll"}
```

Update the function's docstring: it now also appends a letter for a practice created in, or moved into, an open poll's range.

- [ ] **Step 4b: "Location TBD" in the leads poll**

In `app/practices/availability.py`, `poll_rows`, change `practice.location.name if practice.location else "TBD"` to `practice.location.name if practice.location else "Location TBD"`.

- [ ] **Step 5: Remove the old warning**

`app/routes/admin_practices.py`: delete `_uncovered_by_open_poll_warning`, the `availability_warning = _uncovered_by_open_poll_warning(practice)` lines in `create_practice` and `edit_practice` (with their comments), and the `if availability_warning: payload['availability_warning'] = ...` lines. Remove now-unused imports from `..practices.availability_models` if nothing else in the file uses them.

`app/templates/admin/practices/_detail_script.js`: delete the `if (result.availability_warning) { ... sessionStorage ... }` block (~line 165).

`app/static/admin_practices.js`: delete `flashPendingAvailabilityWarning`, its comment header, and the `flashPendingAvailabilityWarning();` call in the `DOMContentLoaded` handler.

In the spec, change "If no letter is left (22 cap), keep the warning." to "If no letter is left (22 cap), log an error; the session's leads are assigned by hand."

- [ ] **Step 6: Run the tests**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack tests/routes -q && npm run test:practice-reactions`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A app tests docs/superpowers/specs
git commit -m "feat(availability): late sessions get the next letter; drop the uncovered warning"
```

### Task C2: Assign modal data and Block Kit

**Files:**
- Modify: `app/practices/blocks.py` (add `assign_modal_data`, `save_assigned_leads`)
- Modify: `app/slack/blocks/block_post.py` (add `build_assign_modal`)
- Test: `tests/practices/test_blocks.py`, `tests/slack/test_block_post_blocks.py`

**Interfaces:**
- Produces: `assign_modal_data(practice_id: int) -> dict | None` with keys `practice_id`, `title`, `detail`, `available_text` (str or None), `available` (list of `(user_id, name)`), `others` (list of `(user_id, name)`), `initial_ids` (list of int).
- Produces: `save_assigned_leads(practice_id: int, user_ids: list[int]) -> None`.
- Produces: `build_assign_modal(data: dict) -> dict` (a Slack view with `callback_id="block_assign_submit"`, block_id `leads`, action_id `leads_select`, `private_metadata=str(practice_id)`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/slack/test_block_post_blocks.py`:

```python
from app.slack.blocks.block_post import build_assign_modal


def _data(**over):
    data = {"practice_id": 5, "title": "Assign leads · Tue 10/27",
            "detail": "6:15p · TEST Wirth · Bounding · needs 2",
            "available_text": "Available: Katrin S, Micah R",
            "available": [(1, "Katrin S"), (2, "Micah R")],
            "others": [(3, "Augie L")], "initial_ids": [1]}
    data.update(over)
    return data


def test_assign_modal_shows_available_line_and_grouped_dropdown():
    view = build_assign_modal(_data())
    text = json.dumps(view)
    assert view["callback_id"] == "block_assign_submit"
    assert view["private_metadata"] == "5"
    assert "Available: Katrin S, Micah R" in text
    select = view["blocks"][-1]["element"]
    assert [g["label"]["text"] for g in select["option_groups"]] == ["Available", "Everyone else"]
    assert select["initial_options"][0]["value"] == "1"
    assert "max_selected_items" not in select


def test_assign_modal_with_no_poll_has_no_available_line_and_skips_empty_group():
    view = build_assign_modal(_data(available_text=None, available=[], initial_ids=[]))
    select = view["blocks"][-1]["element"]
    assert [g["label"]["text"] for g in select["option_groups"]] == ["Everyone else"]
    assert "initial_options" not in select
    assert "Available:" not in json.dumps(view)
```

Append to `tests/practices/test_blocks.py`:

```python
def test_save_assigned_leads_replaces_only_lead_rows(db_session, monkeypatch):
    from app.models import User
    from app.practices.models import PracticeLead

    monkeypatch.setattr("app.slack.practices.refresh_practice_posts", lambda *a, **k: {})
    db.session.rollback()
    users = [User(first_name=f"TEST C2 {i}", last_name="Assign",
                  email=f"test-c2-{i}@example.invalid") for i in range(3)]
    db.session.add_all(users)
    db.session.commit()
    user_ids = [u.id for u in users]
    pid = _practice(20)
    try:
        practice = db.session.get(Practice, pid)
        practice.leads.append(PracticeLead(user_id=user_ids[0], role="coach"))
        practice.leads.append(PracticeLead(user_id=user_ids[1], role="lead"))
        db.session.commit()
        blocks.save_assigned_leads(pid, [user_ids[2]])
        db.session.expire_all()
        roles = sorted((l.user_id, l.role) for l in db.session.get(Practice, pid).leads)
        assert roles == sorted([(user_ids[0], "coach"), (user_ids[2], "lead")])
    finally:
        _cleanup([pid])
        db.session.rollback()
        for uid in user_ids:
            u = db.session.get(User, uid)
            if u is not None:
                db.session.delete(u)
        db.session.commit()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_blocks.py tests/practices/test_blocks.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `build_assign_modal`**

In `app/slack/blocks/block_post.py`:

```python
def _option(user_id, name) -> dict:
    return {"text": {"type": "plain_text", "text": name[:75]}, "value": str(user_id)}


def build_assign_modal(data: dict) -> dict:
    groups = []
    if data["available"]:
        groups.append({"label": {"type": "plain_text", "text": "Available"},
                       "options": [_option(*p) for p in data["available"]]})
    others = data["others"][: 100 - len(data["available"])]
    if others:
        groups.append({"label": {"type": "plain_text", "text": "Everyone else"},
                       "options": [_option(*p) for p in others]})
    names = dict(data["available"] + data["others"])
    select = {"type": "multi_static_select", "action_id": "leads_select",
              "placeholder": {"type": "plain_text", "text": "Choose leads"},
              "option_groups": groups}
    initial = [_option(uid, names[uid]) for uid in data["initial_ids"] if uid in names]
    if initial:
        select["initial_options"] = initial

    blocks = [{"type": "context", "elements": [{"type": "mrkdwn", "text": data["detail"]}]}]
    if data["available_text"]:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                       "text": f"*{data['available_text'].split(':')[0]}:*{data['available_text'].split(':', 1)[1]}"}})
    blocks.append({"type": "input", "block_id": "leads", "optional": True,
                   "label": {"type": "plain_text", "text": "Leads"}, "element": select})
    return {
        "type": "modal",
        "callback_id": "block_assign_submit",
        "private_metadata": str(data["practice_id"]),
        "title": {"type": "plain_text", "text": "Assign leads"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [{"type": "header", "text": {"type": "plain_text", "text": data["title"][:150]}}] + blocks,
    }
```

- [ ] **Step 4: Implement the data functions in `blocks.py`**

```python
def assign_modal_data(practice_id: int) -> dict | None:
    from app.models import User
    from app.practices.models import Practice
    from app.slack.blocks.block_post import short_name, where_label

    practice = db.session.get(Practice, practice_id)
    if practice is None:
        return None
    poll = poll_for_date(practice.date.date())

    available_users = []
    if poll is not None and poll.message_ts:
        ids = [r.user_id for r in LeadAvailabilityResponse.query.filter_by(
            poll_id=poll.id, practice_id=practice.id).all()]
        available_users = User.query.filter(User.id.in_(ids)).order_by(User.first_name).all() if ids else []

    if poll is None or (poll.status == PollStatus.CLOSED and not poll.message_ts):
        available_text = None
    elif poll.status == PollStatus.DRAFT:
        available_text = "Available: poll not opened yet"
    elif available_users:
        available_text = "Available: " + ", ".join(short_name(u) for u in available_users)
    else:
        available_text = "Available: nobody yet"

    current = [l.user for l in practice.leads if l.role == "lead" and l.user]
    available_ids = {u.id for u in available_users}
    pool = [u for u in eligible_leads() if u.id not in available_ids]
    outside = [u for u in current if u.id not in available_ids and u.id not in {p.id for p in pool}]
    others = sorted(pool + outside, key=lambda u: (u.first_name or "", u.last_name or ""))

    when = practice.date
    return {
        "practice_id": practice.id,
        "title": f"Assign leads · {when.strftime('%a %-m/%-d')}",
        "detail": f"{when.strftime('%-I:%M%p').replace('PM', 'p').replace('AM', 'a')} · "
                  f"{where_label(practice)} · needs {practice.leads_needed or 2}",
        "available_text": available_text,
        "available": [(u.id, short_name(u)) for u in available_users],
        "others": [(u.id, short_name(u)) for u in others],
        "initial_ids": [u.id for u in current],
    }


def save_assigned_leads(practice_id: int, user_ids: list[int]) -> None:
    from app.practices.models import Practice, PracticeLead
    from app.slack.practices import refresh_practice_posts

    practice = db.session.get(Practice, practice_id)
    if practice is None:
        return
    for lead in [l for l in practice.leads if l.role == "lead"]:
        practice.leads.remove(lead)
    for user_id in dict.fromkeys(user_ids):
        practice.leads.append(PracticeLead(user_id=user_id, role="lead"))
    db.session.commit()
    refresh_practice_posts(practice, change_type="edit", notify=False)
```

Simplify `build_assign_modal`'s bold-label line to plain text if it renders oddly in the demo: `{"type": "section", "text": {"type": "mrkdwn", "text": data["available_text"]}}` is acceptable and simpler; prefer it.

- [ ] **Step 5: Run the tests**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_blocks.py tests/practices/test_blocks.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/practices/blocks.py app/slack/blocks/block_post.py tests
git commit -m "feat(blocks): Assign modal data and view"
```

### Task C3: Assign handlers

**Files:**
- Modify: `app/slack/bolt_app.py`
- Test: `tests/slack/test_block_assign_handlers.py` (create)

- [ ] **Step 1: Write the failing test**

```python
"""The Assign button opens the modal; submitting saves the chosen leads."""

from unittest.mock import MagicMock

from app.slack import bolt_app


def test_assign_submission_saves_selected_leads(monkeypatch, app):
    saved = []
    monkeypatch.setattr("app.practices.blocks.save_assigned_leads",
                        lambda pid, ids: saved.append((pid, ids)))
    view = {"private_metadata": "5", "state": {"values": {"leads": {"leads_select": {
        "selected_options": [{"value": "1"}, {"value": "3"}]}}}}}
    bolt_app._save_block_assign(view)
    assert saved == [(5, [1, 3])]


def test_assign_submission_with_nothing_selected_clears_leads(monkeypatch, app):
    saved = []
    monkeypatch.setattr("app.practices.blocks.save_assigned_leads",
                        lambda pid, ids: saved.append((pid, ids)))
    view = {"private_metadata": "5", "state": {"values": {"leads": {"leads_select": {}}}}}
    bolt_app._save_block_assign(view)
    assert saved == [(5, [])]
```

- [ ] **Step 2: Run to verify failure**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_assign_handlers.py -q`
Expected: FAIL (`_save_block_assign` missing).

- [ ] **Step 3: Implement**

Module-level helper in `app/slack/bolt_app.py` (near the other `_run_*` helpers):

```python
def _save_block_assign(view) -> None:
    """Persist an Assign modal submission."""
    practice_id = int(view["private_metadata"])
    selected = (view["state"]["values"]["leads"]["leads_select"].get("selected_options") or [])
    with get_app_context():
        from app.practices import blocks

        blocks.save_assigned_leads(practice_id, [int(o["value"]) for o in selected])
```

Inside the registration function, next to `block_poll_open`:

```python
    @bolt_app.action("block_assign")
    def handle_block_assign(ack, body, action, client, logger):
        ack()
        with get_app_context():
            from app.practices.blocks import assign_modal_data
            from app.slack.blocks.block_post import build_assign_modal

            data = assign_modal_data(int(action["value"]))
        if data is None:
            channel = (body.get("channel") or {}).get("id")
            if channel:
                client.chat_postEphemeral(channel=channel, user=body["user"]["id"],
                                          text=":warning: That practice no longer exists.")
            return
        client.views_open(trigger_id=body["trigger_id"], view=build_assign_modal(data))

    @bolt_app.view("block_assign_submit")
    def handle_block_assign_submit(ack, body, view, client, logger):
        ack()
        _save_block_assign(view)
```

- [ ] **Step 4: Run the tests**

Run: `DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/slack/bolt_app.py tests/slack/test_block_assign_handlers.py
git commit -m "feat(blocks): Assign button and modal submission"
```

### Task C4: Cutover script

**Files:**
- Create: `scripts/lead_blocks_cutover.py`

The script runs against prod by hand (Rob, at deploy). It is not part of the test suite; keep it small.

- [ ] **Step 1: Write the script**

```python
"""One-off cutover for lead availability v2. Run by hand at deploy.

    TCSC_MIGRATION_ONLY=1 SLACK_APP_TOKEN= DATABASE_URL=<prod> \
      python scripts/lead_blocks_cutover.py manual-block 2026-10-12
    ... digest-cleanup            # list what would be deleted
    ... digest-cleanup --delete   # delete it (after Rob's OK)

manual-block: creates the block's poll row as closed with no message (Chris
collected availability by hand), and posts its assignment-only block post.
digest-cleanup: finds the readiness digest posts from their summary-post
records (never by scanning the channel, where coach summaries are bot posts
too) and deletes each parent and its thread replies.
"""

import sys
from datetime import date, timedelta

from app import create_app


def manual_block(start: date) -> None:
    from app.models import db
    from app.practices.availability import create_block_poll
    from app.practices.availability_models import PollStatus
    from app.practices.blocks import post_block_post
    from app.utils import now_central_naive

    poll = create_block_poll(start, start + timedelta(days=13))
    if poll.block_post_ts:
        print(f"poll {poll.id} already has a block post ({poll.block_post_ts}); nothing to do")
        return
    poll.status = PollStatus.CLOSED
    poll.closed_at = now_central_naive()
    db.session.commit()
    print("posted" if post_block_post(poll) else "POST FAILED", "for poll", poll.id)


def digest_cleanup(delete: bool) -> None:
    from app.practices.models import PracticeSummaryPost
    from app.slack.client import get_slack_client
    from app.slack.practices.summary_posts import READINESS_DIGEST

    client = get_slack_client()
    for record in PracticeSummaryPost.query.filter_by(surface=READINESS_DIGEST).all():
        replies = client.conversations_replies(channel=record.channel_id, ts=record.message_ts,
                                               limit=200).get("messages", [])
        print(f"{record.week_start} parent {record.message_ts}: {len(replies)} messages incl. parent")
        if not delete:
            continue
        for message in reversed(replies):  # replies first, parent last
            try:
                client.chat_delete(channel=record.channel_id, ts=message["ts"])
            except Exception as exc:  # noqa: BLE001
                print("  could not delete", message["ts"], exc)


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        command = sys.argv[1] if len(sys.argv) > 1 else ""
        if command == "manual-block":
            manual_block(date.fromisoformat(sys.argv[2]))
        elif command == "digest-cleanup":
            digest_cleanup("--delete" in sys.argv)
        else:
            print(__doc__)
            sys.exit(1)
```

Note: `conversations_replies` needs the bot in #collab-coaches-practices (it posts there daily, so it is) and the `channels:history` scope (or `groups:history` if private). If the call fails with `missing_scope`, use `SLACK_USER_TOKEN` for the read only; the delete must use the bot token, since only the bot can delete its own messages.

- [ ] **Step 2: Dry check against the local DB**

```bash
DATABASE_URL=$TEST_DB TCSC_MIGRATION_ONLY=1 SLACK_APP_TOKEN= /workspace/tcsc-trips/.venv/bin/python scripts/lead_blocks_cutover.py
```

Expected: prints the usage docstring and exits 1. Do not run `manual-block` or `digest-cleanup` locally against Slack.

- [ ] **Step 3: Commit**

```bash
git add scripts/lead_blocks_cutover.py
git commit -m "chore(blocks): cutover script for the Oct 12-25 block and digest cleanup"
```

### Task C5: Demo for Rob

**Files:**
- Create: `scripts/preview_lead_blocks.py`
- Delete: `scripts/preview_lead_availability_ui.py` (previews the July surfaces, most of which are gone)

- [ ] **Step 1: Write the demo script**

It DMs Rob (`U02JS0R7ZG8`) every surface, built from the real builders with example data. Buttons are inert in a DM (they route to the real handlers but the values point at nothing, so they answer with a warning); say so in each label.

```python
"""DM Rob every lead-availability v2 surface, from the real builders.

    python scripts/preview_lead_blocks.py           # post
    python scripts/preview_lead_blocks.py --clean   # delete what it posted
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from dotenv import dotenv_values
from slack_sdk import WebClient

ROOT = Path(__file__).resolve().parent.parent
ROB = "U02JS0R7ZG8"
STATE = ROOT / "scripts" / "output" / "preview_lead_blocks_ts.json"
client = WebClient(token=dotenv_values(ROOT / ".env")["SLACK_BOT_TOKEN"])

from app.slack.blocks.availability import build_nudge_blocks, build_poll_blocks  # noqa: E402
from app.slack.blocks.block_post import build_assign_modal, build_block_post  # noqa: E402
from app.slack.blocks.coach_review import build_coach_weekly_summary_blocks  # noqa: E402

S, E = date(2026, 10, 26), date(2026, 11, 8)
ROWS = [
    ("letter_a", datetime(2026, 10, 27, 18, 15), "Theodore Wirth · Bounding", ["Katrin S"], [], 2),
    ("letter_b", datetime(2026, 10, 29, 18, 5), "Balance Fitness Studio · Strength", ["Ellie T"], ["KJ"], 1),
    ("letter_c", datetime(2026, 10, 29, 19, 20), "Balance Fitness Studio · Strength", [], [], 0),
    ("letter_d", datetime(2026, 11, 3, 18, 15), "location TBD", [], [], 1),
    ("letter_e", datetime(2026, 11, 5, 18, 5), "Balance Fitness Studio · Strength", ["Jacob D", "Dana P"], [], 0),
    ("letter_f", datetime(2026, 11, 5, 19, 20), "Balance Fitness Studio · Strength", [], [], 2),
]


def rows(with_letters=True):
    return [{"practice_id": i + 1, "emoji": e if with_letters else None, "when": w, "where": wh,
             "cancelled": False, "leads": l, "coaches": c, "leads_needed": 2, "available": a}
            for i, (e, w, wh, l, c, a) in enumerate(ROWS)]


def poll(status, message_ts=None, opened_by=None, closed_at=None):
    return SimpleNamespace(id=0, starts_on=S, ends_on=E, status=status, message_ts=message_ts,
                           opened_by_slack_uid=opened_by, opened_at=None, closed_at=closed_at)


def label(text):
    return {"type": "context", "elements": [{"type": "mrkdwn",
            "text": f":construction: *DEMO* · {text} · example data, buttons do nothing here"}]}


def surfaces():
    yield "block post, before opening", build_block_post(poll("draft"), rows(), permalink=None, footer=None)
    yield "block post, open", build_block_post(
        poll("open", "1.0", "U0555FLT01E"), rows(), permalink="https://slack.com",
        footer="31 of 60 leads have answered. Reminders go to the rest Thu, Sat and Mon.")
    yield "block post, closed", build_block_post(
        poll("closed", "1.0", closed_at=datetime(2026, 11, 9, 8, 30)), rows(), permalink=None, footer=None)
    yield "Oct 12-25 assignment post (no poll)", build_block_post(
        poll("closed"), rows(with_letters=False), permalink=None, footer=None)
    modal = build_assign_modal({"practice_id": 1, "title": "Assign leads · Tue 10/27",
                                "detail": "6:15p · Theodore Wirth · Bounding · needs 2",
                                "available_text": "Available: Katrin S, Micah R, Dana P",
                                "available": [(1, "Katrin S"), (2, "Micah R"), (3, "Dana P")],
                                "others": [(4, "Augie L"), (5, "Chris F")], "initial_ids": [1]})
    yield "Assign modal (shown as a message)", modal["blocks"]
    leads = [{"emoji": e, "date": w, "location": wh.split(" · ")[0] if "TBD" not in wh else "Location TBD",
              "kind": wh.split(" · ")[1] if " · " in wh else "Practice",
              "week_label": f"Week of {('Oct 26' if w.day >= 26 else 'Nov 2')}"} for e, w, wh, *_ in ROWS]
    yield "leads poll in #coord-practices-leads-assists", build_poll_blocks(leads, "October 26", "Nov 8")
    yield "nudge DM to a lead", build_nudge_blocks("Oct 26", "Nov 8", "C02J4DGCFL2", "https://slack.com")


def post():
    dm = client.conversations_open(users=ROB)["channel"]["id"]
    posted = []
    for title, blocks in surfaces():
        resp = client.chat_postMessage(channel=dm, blocks=[label(title)] + blocks[:49], text=f"Demo: {title}")
        posted.append(resp["ts"])
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({"channel": dm, "ts": posted}))
    print(f"posted {len(posted)} to {dm}")


def clean():
    data = json.loads(STATE.read_text())
    for ts in data["ts"]:
        client.chat_delete(channel=data["channel"], ts=ts)
    STATE.unlink()


if __name__ == "__main__":
    clean() if "--clean" in sys.argv else post()
```

The Sunday summary changes (HIDDEN badge, footer copy, Open poll button) are shown by also posting `build_coach_weekly_summary_blocks(...)` with one hidden `PracticeInfo` and `open_poll_id=1`; build the `PracticeInfo` the way `tests/slack/test_coach_summary_drafts.py::_practice` does and add it as an eighth `yield`.

- [ ] **Step 2: Post the demo and screenshot the admin page**

```bash
git rm scripts/preview_lead_availability_ui.py
/workspace/tcsc-trips/.venv/bin/python scripts/preview_lead_blocks.py
```

Expected: `posted 8 to D...`. Then screenshot `/admin/practices/` (block cards, Run block job now, a hidden practice's drawer) per the memory note "headless-chromium-screenshots", running the app with `./scripts/dev.sh` in a herdr pane on this project's port block.

- [ ] **Step 3: Draft the leads heads-up note** and send it to Rob in chat (not Slack) for Chris to post before Oct 19:

> Heads-up: starting Mon Oct 19 the lead poll comes from the TCSC bot every other Monday instead of a post from Chris. React with the letter for each session you can lead, and hit ✅ when you're done, even if you can't lead any. (Here ✅ means "done answering", not "confirm the schedule".) If you haven't reacted by Thursday you'll get a reminder DM; reacting stops them.

- [ ] **Step 4: Wait for Rob's feedback.** Apply changes as new commits on the branch that owns the surface (A, B or C), re-post the demo, repeat until Rob approves. Then `--clean`.

- [ ] **Step 5: Commit**

```bash
git add scripts/preview_lead_blocks.py
git commit -m "chore(blocks): demo script for every v2 surface"
```

### Task C6: Phase C PR, skill doc, cutover runbook

- [ ] **Step 1: Full verification and PR**

```bash
DATABASE_URL=$TEST_DB /workspace/tcsc-trips/.venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape 2>&1 | tail -5
npm run test:practice-reactions
git push -u origin lead-availability-assign
gh pr create --draft --base lead-availability-blocks --title "Lead availability v2, part C: Assign, letters, cutover" --body "$(cat <<'EOF'
Part C of docs/superpowers/specs/2026-10-05-lead-availability-simplification-design.md.

- Assign button on each block post row opens a small modal: who's available, one leads dropdown.
- A session added to an open poll's range gets the next letter; letters only count up.
- scripts/lead_blocks_cutover.py: Oct 12-25 assignment post, readiness digest cleanup.
- scripts/preview_lead_blocks.py: the demo Rob reviewed.

Stacked on part B.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Update the lead-availability skill**

Edit `/home/node/.claude/skills/lead-availability/SKILL.md` (outside the repo) to describe v2: block job, block post, Assign, visible when ready. Replace the "Publishing does not post the announcement ... no week-level or automatic publish" invariant and the shadow-mode invariant with the v2 rules (one-way visibility, letters only count up, row lock on open, never a block before the anchor). Keep the letter-emoji, double-post and draft-visibility invariants.

- [ ] **Step 3: Hand Rob the merge and cutover runbook** (Rob runs it; nothing here is automatic):

1. Merge A, then B, then C (each PR retargets to `main` after the previous merges). Render deploys each; migrations run in the release phase.
2. Run the cutover against prod (`render-log-access` memory has `PROD_DATABASE_URL`; `prod-one-off-scripts` memory has the env):
   `TCSC_MIGRATION_ONLY=1 SLACK_APP_TOKEN= DATABASE_URL=$PROD_DATABASE_URL python scripts/lead_blocks_cutover.py manual-block 2026-10-12`
3. `... digest-cleanup`, show Rob the list, then `... digest-cleanup --delete` after his OK.
4. Rob or Chris deletes stale drafts 111-115 from `/admin/practices/`.
5. Delete the dead AppConfig rows `lead_availability.shadow_roster` (and `shadow_mode` / `shadow_channel_id` if present) with a prod one-off or SQL.
6. Chris posts the heads-up note in #coord-practices-leads-assists before Oct 19.
7. Mon Oct 19 09:00: confirm the Oct 26 to Nov 8 block post appeared in #collab-coaches-practices (or press Run block job now on `/admin/practices/`).
8. Write the explainer artifact for Chris, Ellie and Jacob against the live build.
