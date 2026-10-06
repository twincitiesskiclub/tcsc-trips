# Dry Tri live page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store event times in UTC so tcsc.ski shows the right race time, then make twincitiesskiclub.org/dry-tri show the current Dry Tri from a public event API.

**Architecture:** PR 1 converts event datetimes to UTC on admin save and migrates existing rows. PR 2 adds `GET /api/events/dry-tri` (selection and shaping in pure modules, thin route), and the Astro page bakes that JSON at build time and re-renders the band in the browser from one pure render function.

**Tech Stack:** Flask, SQLAlchemy, Alembic, pytest on PostgreSQL; Astro 7, Tailwind 4, TypeScript run directly by Node 24 (`node --test`), jsdom.

**Spec:** `docs/superpowers/specs/2026-10-06-dry-tri-live-page-design.md`

## Global Constraints

- Event datetimes are naive UTC in the database. Admins type Central; convert on save, convert back for display.
- `app/events/seeds.py` stays in Central. Seed migration `d4e7f9a1b2c3` calls it before the conversion migration runs.
- The public payload never contains `member_price_cents`, `discount_code`, `capacity`, or registration counts.
- The API returns no open/closed state. The state rule lives only in `site/src/lib/eventState.ts`.
- The marketing build never fails because the API is down. It falls back and stamps `data-event-source="fallback"`.
- No em dashes or en dashes in any copy, code comment, commit message or PR text.
- Copy voice: friendly, short, plain. Exact strings: "Registration opens {Weekday, Month D}", "Register", "Registration closes {Weekday, Month D}.", "Registration is closed. See you at the start.", "Dates, entries and registration: tcsc.ski/tri", "Full race details", "Latest results".
- Every API timestamp is `YYYY-MM-DDTHH:MM:SSZ`, produced by `app.seasons.payload._iso`.
- Dates on the site format in `America/Chicago`.
- PR 1 runs on branch `event-times-utc` (worktree `.worktrees/event-times-utc`, already holds the spec commit). PR 2 runs on branch `dry-tri-live-page`, created from `origin/main` after PR 1 merges.

Test commands used below:

```bash
# Python (events and routes). tcsc_trips_test, not the dev DB: the dev DB carries PR #237's schema.
export PYTEST="env DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test FLASK_SECRET_KEY=test-secret-key /workspace/tcsc-trips/.venv-linux/bin/python -m pytest --ignore=tests/wix_scrape"
# localhost:5432 must be forwarded (ss -tln | grep 5432). If not, see memory note pgforward-safe-relay.
# Site (from <worktree>/site, after npm ci)
node --test tests/<file>.test.mjs
```

## Review Focus

1. A description saved from the admin textarea has `\r\n` line endings, blank lines, and lines with and without `- `. The band must show paragraphs and a list, never literal `\r` or one run-on line. (Task 9 test `description handles CRLF and mixed blocks`.)
2. An admin types `<script>` or `&` into the description, location or an entry name. The marketing page must show the text, not execute or mangle it. (Task 9 test `escapes HTML in every field`.)
3. The browser fetch fails, or returns `{"event": null}`, after a good build. A failed fetch keeps the baked band; a null event switches to the fallback line without throwing. (Task 10 tests.)
4. Signup ends at 11:59 PM Central on Oct 22 and race day ends at midnight Central. At 11:30 PM Central on race day (04:30Z next day) the state is still `closed`, not `past`; across DST the end of day is still Central midnight. (Task 8 tests.)
5. The January Pickleball row is CST (+6h), not CDT (+5h). The migration converts each value with its own offset and the downgrade restores it exactly. (Task 3 tests.)

---

## PR 1: event times are UTC

### Task 1: Central-to-UTC helper shared by seasons and events

**Files:**
- Modify: `app/utils.py` (after `utc_naive_to_central_naive`, around line 65)
- Modify: `app/routes/admin.py:80-84`
- Test: `tests/test_central_time_helpers.py` (create)

**Interfaces:**
- Produces: `app.utils.central_naive_to_utc_naive(dt: datetime | None) -> datetime | None`

- [ ] **Step 1: Write the failing test**

```python
"""Admins type Central wall time; the database stores naive UTC."""
from datetime import datetime

from app.utils import central_naive_to_utc_naive, utc_naive_to_central_naive


def test_cdt_value_gains_five_hours():
    assert central_naive_to_utc_naive(datetime(2026, 10, 24, 9, 0)) == datetime(2026, 10, 24, 14, 0)


def test_cst_value_gains_six_hours():
    assert central_naive_to_utc_naive(datetime(2026, 1, 19, 12, 0)) == datetime(2026, 1, 19, 18, 0)


def test_late_evening_crosses_into_the_next_utc_day():
    assert central_naive_to_utc_naive(datetime(2026, 10, 22, 23, 59)) == datetime(2026, 10, 23, 4, 59)


def test_none_passes_through():
    assert central_naive_to_utc_naive(None) is None


def test_round_trips_with_the_existing_inverse():
    value = datetime(2026, 3, 9, 7, 30)
    assert utc_naive_to_central_naive(central_naive_to_utc_naive(value)) == value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PYTEST tests/test_central_time_helpers.py -v`
Expected: FAIL with `ImportError: cannot import name 'central_naive_to_utc_naive'`

- [ ] **Step 3: Write minimal implementation**

In `app/utils.py`, directly after `utc_naive_to_central_naive`:

```python
def central_naive_to_utc_naive(dt: datetime) -> datetime:
    """Convert a naive Central datetime to naive UTC for storage.

    Admin forms use datetime-local inputs, which admins fill in Central time.
    The inverse of utc_naive_to_central_naive.
    """
    if dt is None:
        return None
    return CENTRAL_TZ.localize(dt).astimezone(pytz.utc).replace(tzinfo=None)
```

In `app/routes/admin.py`, replace the body of the nested `_parse_central_to_utc` so seasons use the shared helper:

```python
        def _parse_central_to_utc(value):
            if not value:
                return None
            return central_naive_to_utc_naive(datetime.strptime(value, DATETIME_FORMAT))
```

and add `central_naive_to_utc_naive` to `admin.py`'s existing `from ..utils import ...` line (grep for it; add the import if `admin.py` has none).

- [ ] **Step 4: Run tests to verify they pass**

Run: `$PYTEST tests/test_central_time_helpers.py tests/seasons -q`
Expected: PASS (seasons tests prove the admin refactor kept behavior)

- [ ] **Step 5: Commit**

```bash
git add app/utils.py app/routes/admin.py tests/test_central_time_helpers.py
git commit -m "Share the Central-to-UTC helper between seasons and events"
```

### Task 2: Admin event form saves UTC, every reader shows Central

**Files:**
- Modify: `app/routes/admin_events.py` (imports; `_parse_event_form` after the `try` that parses the three dates, around line 92; list JSON around line 358)
- Modify: `app/templates/admin/event_form.html:95,101,107`
- Modify: `app/templates/index.html:108-109`
- Test: `tests/events/test_admin.py`, `tests/events/test_routes.py`

**Interfaces:**
- Consumes: `central_naive_to_utc_naive` from Task 1.
- Produces: `/admin/events/data` rows carry `event_date` as `...Z`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/events/test_admin.py`:

```python
def _central_form(slug, event_date, signup_start, signup_end):
    return {
        "slug": slug,
        "name": "Timezone Event",
        "description": "",
        "location": "Carver Park Reserve",
        "event_date": event_date,
        "signup_start": signup_start,
        "signup_end": signup_end,
        "capacity": "",
        "status": EventStatus.DRAFT,
        "audience": "both",
        "details_url": "",
        "discount_code": "",
    }


def test_create_stores_central_input_as_utc_in_cdt_and_cst(admin_client, db_session):
    response = admin_client.post(
        "/admin/events/new",
        data=_central_form(
            "admin-grid-test", "2026-10-24T09:00", "2026-01-10T08:00", "2026-10-22T23:59"
        ),
    )

    assert response.status_code == 302
    event = Event.query.filter_by(slug="admin-grid-test").one()
    assert event.event_date == datetime(2026, 10, 24, 14, 0)
    assert event.signup_start == datetime(2026, 1, 10, 14, 0)
    assert event.signup_end == datetime(2026, 10, 23, 4, 59)


def test_edit_form_prefills_central_wall_time(admin_client, db_session):
    event = _event("admin-delete-test")
    event.event_date = datetime(2026, 10, 24, 14, 0)
    db_session.session.add(event)
    db_session.session.commit()

    html = admin_client.get(f"/admin/events/{event.id}/edit").get_data(as_text=True)

    assert 'value="2026-10-24T09:00"' in html


def test_saving_the_edit_form_unchanged_keeps_the_time(admin_client, db_session):
    event = _event("admin-delete-test")
    event.event_date = datetime(2026, 10, 24, 14, 0)
    event.signup_start = datetime(2026, 7, 25, 5, 0)
    event.signup_end = datetime(2026, 10, 23, 4, 59)
    db_session.session.add(event)
    db_session.session.commit()

    form = _edit_form(event, "[]", "[]")
    form.update(
        event_date="2026-10-24T09:00",
        signup_start="2026-07-25T00:00",
        signup_end="2026-10-22T23:59",
    )
    admin_client.post(f"/admin/events/{event.id}/edit", data=form)

    db_session.session.refresh(event)
    assert event.event_date == datetime(2026, 10, 24, 14, 0)
    assert event.signup_end == datetime(2026, 10, 23, 4, 59)
```

`_event` builds one price option; posting `"[]"` for price options is allowed when that option has no registrations (the "cannot be removed" test only fails because it adds one). If the edit returns 400 for another validation reason, print `response.get_data(as_text=True)` and fix the form, not the assertion.

In `test_events_data_returns_confirmed_revenue`, change the expected row's
`"event_date": event.event_date.isoformat(),` to
`"event_date": event.event_date.isoformat() + "Z",`.

Append to `tests/events/test_routes.py`:

```python
def test_registration_page_shows_the_central_start_time(client, public_event):
    event = public_event[0]
    event.event_date = datetime(2026, 10, 24, 14, 0)
    from app.models import db
    db.session.commit()

    html = client.get(f"/events/{event.slug}").get_data(as_text=True)

    assert "Saturday, October 24, 2026 at 9:00 AM CT" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$PYTEST tests/events/test_admin.py tests/events/test_routes.py -q`
Expected: FAIL. The create test sees `09:00` stored, the prefill test sees `T14:00`, the data test misses the `Z`. The registration page test may already PASS (the page was always converting; only the stored value was wrong). That is fine: it pins the reader side.

- [ ] **Step 3: Implement**

`app/routes/admin_events.py`, add to the imports:

```python
from ..utils import central_naive_to_utc_naive
```

Immediately after the `try/except` that parses the three dates and before `if signup_start >= signup_end:`:

```python
    # Admins type Central wall time; the database stores naive UTC.
    event_date = central_naive_to_utc_naive(event_date)
    signup_start = central_naive_to_utc_naive(signup_start)
    signup_end = central_naive_to_utc_naive(signup_end)
```

In the events list rows (around line 358):

```python
                "event_date": event.event_date.isoformat() + "Z",
```

`app/templates/admin/event_form.html`, in each of the three inputs replace `event.<field>.strftime('%Y-%m-%dT%H:%M')` with `event.<field>|central_time('%Y-%m-%dT%H:%M')`. For example line 95 becomes:

```html
               value="{{ form_data.get('event_date') if form_data else event.event_date|central_time('%Y-%m-%dT%H:%M') if event else '' }}"
```

`app/templates/index.html:108-109`:

```html
                <span class="card__meta-item">📅 {{ event.event_date|central_time('%B %-d, %Y') }}</span>
                <span class="card__meta-item">🕐 {{ event.event_date|central_time('%-I:%M %p') }}</span>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$PYTEST tests/events tests/test_events_js.py -q`
Expected: PASS, no new failures. The duplicate-event route copies datetimes as-is, which is correct (already UTC).

- [ ] **Step 5: Commit**

```bash
git add app/routes/admin_events.py app/templates/admin/event_form.html app/templates/index.html tests/events/test_admin.py tests/events/test_routes.py
git commit -m "Events: store admin-entered times as UTC, show them in Central"
```

### Task 3: Migrate existing event rows to UTC

**Files:**
- Create: `migrations/versions/c7e1a9d3f5b2_event_times_to_utc.py`
- Modify: `tests/practices/test_practice_migration_release.py:28` (`HEAD_REVISION`)
- Test: `tests/events/test_event_times_migration.py` (create)

**Interfaces:**
- Produces: module-level `central_to_utc_sql(column: str) -> str` and `utc_to_central_sql(column: str) -> str` in the migration file.

- [ ] **Step 1: Write the failing test**

```python
"""The conversion SQL, run against real PostgreSQL time zone rules."""
import importlib.util
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations/versions/c7e1a9d3f5b2_event_times_to_utc.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("event_times_to_utc", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(db_session, expression, value):
    sql = f"SELECT {expression}"
    return db_session.session.execute(text(sql), {"v": value}).scalar()


def test_cdt_value_converts_with_five_hours(db_session):
    m = _migration()
    expr = m.central_to_utc_sql("CAST(:v AS timestamp)")
    assert _run(db_session, expr, datetime(2026, 10, 24, 9, 0)) == datetime(2026, 10, 24, 14, 0)


def test_cst_value_converts_with_six_hours(db_session):
    m = _migration()
    expr = m.central_to_utc_sql("CAST(:v AS timestamp)")
    assert _run(db_session, expr, datetime(2026, 1, 19, 12, 0)) == datetime(2026, 1, 19, 18, 0)


def test_downgrade_expression_restores_the_original(db_session):
    m = _migration()
    expr = m.utc_to_central_sql(m.central_to_utc_sql("CAST(:v AS timestamp)"))
    for value in (datetime(2026, 10, 22, 23, 59), datetime(2025, 12, 10, 0, 0)):
        assert _run(db_session, expr, value) == value


def test_migration_follows_the_previous_head():
    assert _migration().down_revision == "9b2e6d4f1a37"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PYTEST tests/events/test_event_times_migration.py -v`
Expected: FAIL with `FileNotFoundError` for the migration path.

- [ ] **Step 3: Write the migration and bump the head**

`migrations/versions/c7e1a9d3f5b2_event_times_to_utc.py`:

```python
"""Event datetimes: Central wall time to UTC.

The admin event form saved what admins typed (Central) while every reader
treated the columns as UTC, so the public page showed a 9:00 AM race at
4:00 AM. From this revision on the form converts on save; this converts the
rows already stored. Each value uses its own offset (CDT or CST).

Revision ID: c7e1a9d3f5b2
Revises: 9b2e6d4f1a37
Create Date: 2026-10-06
"""
from alembic import op

revision = "c7e1a9d3f5b2"
down_revision = "9b2e6d4f1a37"
branch_labels = None
depends_on = None

COLUMNS = ("event_date", "signup_start", "signup_end")


def central_to_utc_sql(column: str) -> str:
    return f"(({column}) AT TIME ZONE 'America/Chicago') AT TIME ZONE 'UTC'"


def utc_to_central_sql(column: str) -> str:
    return f"(({column}) AT TIME ZONE 'UTC') AT TIME ZONE 'America/Chicago'"


def _convert(expression) -> None:
    assignments = ", ".join(f"{c} = {expression(c)}" for c in COLUMNS)
    op.execute(f"UPDATE events SET {assignments}")


def upgrade():
    _convert(central_to_utc_sql)


def downgrade():
    _convert(utc_to_central_sql)
```

`tests/practices/test_practice_migration_release.py:28`:

```python
HEAD_REVISION = "c7e1a9d3f5b2"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$PYTEST tests/events/test_event_times_migration.py -v`
Expected: PASS

Then apply it to the scratch DB and check the seeded row:

```bash
cd /workspace/tcsc-trips/.worktrees/event-times-utc
env DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test TCSC_MIGRATION_ONLY=1 SLACK_APP_TOKEN= FLASK_SECRET_KEY=x /workspace/tcsc-trips/.venv-linux/bin/flask db upgrade
```

Expected: `Running upgrade 9b2e6d4f1a37 -> c7e1a9d3f5b2`. If the scratch DB is behind `9b2e6d4f1a37`, upgrade it first the same way; if it has no events rows, that is fine.

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/c7e1a9d3f5b2_event_times_to_utc.py tests/events/test_event_times_migration.py tests/practices/test_practice_migration_release.py
git commit -m "Migrate stored event times from Central to UTC"
```

### Task 4: Ship PR 1

- [ ] **Step 1: Full relevant suites**

Run: `$PYTEST tests/events tests/seasons tests/routes tests/test_central_time_helpers.py tests/test_events_js.py -q`
Expected: PASS. Report any failure verbatim; do not mark it pre-existing without running the same test on `origin/main`.

- [ ] **Step 2: Push and open the PR**

```bash
git push -u origin event-times-utc
gh pr create --title "Event times are UTC: fix the 4:00 AM Dry Tri start" --body "$(cat <<'EOF'
The admin event form saved Central wall time while every reader treated it as UTC. tcsc.ski/events/dry-tri-2026 shows a 9:00 AM race as 4:00 AM CT, and signups close at 6:59 PM Central instead of 11:59 PM.

- Admin create and edit convert Central input to UTC; the edit form shows Central.
- Migration c7e1a9d3f5b2 converts existing rows (Dry Tri: +5h; Pickleball draft: +6h).
- Admin list JSON sends `Z`; home page cards use `central_time`.
- Seasons now share the same helper.

Spec: docs/superpowers/specs/2026-10-06-dry-tri-live-page-design.md

After deploy: tcsc.ski/events/dry-tri-2026 should read "Saturday, October 24, 2026 at 9:00 AM CT".

If PR #237 merges first, rebase this migration's down_revision onto its head and bump HEAD_REVISION again.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: After Rob merges and Render deploys**, verify against production:

```bash
curl -s https://tcsc.ski/events/dry-tri-2026 | grep -o 'Saturday, October 24, 2026 at [0-9:]* [AP]M CT'
```

Expected: `Saturday, October 24, 2026 at 9:00 AM CT`

---

## PR 2: live Dry Tri page

Setup, once Task 4 Step 3 passes:

```bash
cd /workspace/tcsc-trips && git fetch -q origin
git worktree add .worktrees/dry-tri-live-page -b dry-tri-live-page origin/main
cd .worktrees/dry-tri-live-page/site && npm ci
```

All paths below are relative to `.worktrees/dry-tri-live-page`.

### Task 5: Event selection

**Files:**
- Create: `app/events/selection.py`
- Test: `tests/events/test_selection.py`

**Interfaces:**
- Produces: `select_public_event(events: Iterable, template_key: str, now: datetime) -> Event | None`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime
from types import SimpleNamespace

from app.events.selection import select_public_event

NOW = datetime(2026, 10, 6, 15, 0)


def _event(slug, when, status="active", audience="both", template_key="dry_tri"):
    return SimpleNamespace(
        slug=slug, event_date=when, status=status, audience=audience, template_key=template_key
    )


def test_soonest_upcoming_wins():
    events = [
        _event("2027", datetime(2027, 10, 23, 14)),
        _event("2026", datetime(2026, 10, 24, 14)),
        _event("2025", datetime(2025, 10, 25, 14)),
    ]
    assert select_public_event(events, "dry_tri", NOW).slug == "2026"


def test_most_recent_past_when_nothing_is_ahead():
    events = [_event("2024", datetime(2024, 10, 26, 14)), _event("2025", datetime(2025, 10, 25, 14))]
    assert select_public_event(events, "dry_tri", NOW).slug == "2025"


def test_closed_events_still_count():
    events = [_event("2026", datetime(2026, 10, 24, 14), status="closed")]
    assert select_public_event(events, "dry_tri", NOW).slug == "2026"


def test_drafts_internal_and_other_series_are_ignored():
    events = [
        _event("draft", datetime(2026, 10, 24, 14), status="draft"),
        _event("internal", datetime(2026, 10, 24, 14), audience="internal"),
        _event("pickleball", datetime(2026, 10, 24, 14), template_key="social"),
    ]
    assert select_public_event(events, "dry_tri", NOW) is None


def test_external_audience_counts():
    events = [_event("2026", datetime(2026, 10, 24, 14), audience="external")]
    assert select_public_event(events, "dry_tri", NOW).slug == "2026"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PYTEST tests/events/test_selection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.events.selection'`

- [ ] **Step 3: Implement**

```python
"""Pick the one event a public page describes for an event series.

The marketing site's Dry Tri page and tcsc.ski/tri both ask "which Dry Tri
is current?" and must get the same answer, so the rule lives here once.
"""
from __future__ import annotations

from datetime import datetime

from .models import Audience, EventStatus


def select_public_event(events, template_key: str, now: datetime):
    """Soonest event on or after ``now``, else the most recent past one.

    Drafts and internal events never reach a public page. A closed event
    still counts: it stopped taking signups but the race is still on.
    """
    candidates = [
        event
        for event in events
        if event.template_key == template_key
        and event.status != EventStatus.DRAFT
        and event.audience != Audience.INTERNAL
    ]
    upcoming = [event for event in candidates if event.event_date >= now]
    if upcoming:
        return min(upcoming, key=lambda event: event.event_date)
    if candidates:
        return max(candidates, key=lambda event: event.event_date)
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PYTEST tests/events/test_selection.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/events/selection.py tests/events/test_selection.py
git commit -m "Events: one rule for which event a public page describes"
```

### Task 6: `GET /api/events/<series>`

**Files:**
- Create: `app/events/public_payload.py`
- Create: `app/routes/event_api.py`
- Modify: `app/__init__.py` (import beside `season_api_bp` at line 52; register beside it)
- Test: `tests/routes/test_event_api.py`

**Interfaces:**
- Consumes: `select_public_event` (Task 5); `app.seasons.payload._iso`; `app.routes.marketing_cors.apply_marketing_cors`.
- Produces: JSON `{"generated_at": str, "event": EventPayload | null}` where `EventPayload` keys are exactly `slug, name, location, description, event_date, signup_start, signup_end, registration_path, details_url, entries`, and each entry is `{name, description, price_cents}`. Module constant `event_api.SERIES = {"dry-tri": "dry_tri"}`. Test seam `event_api._all_events()`.

- [ ] **Step 1: Write the failing test**

```python
"""Wiring, shape, privacy and CORS for the public event API. Selection is
unit-tested in tests/events/test_selection.py, so most tests stub the query."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import app.routes.event_api as event_api
from app import create_app


def _option(name, cents, order, active=True, description=""):
    return SimpleNamespace(
        name=name, description=description, price_cents=cents,
        member_price_cents=cents - 2000, sort_order=order, active=active,
    )


def _stub_event(**overrides):
    fields = dict(
        slug="dry-tri-2026",
        name="TCSC Roll, Ride, and Run Dry Tri 2026",
        location="Carver Park Reserve, Parley Lake, Victoria",
        description="Schedule of events\r\n\r\n- 7:30 AM: Packet pickup opens",
        event_date=datetime.utcnow() + timedelta(days=18),
        signup_start=datetime(2026, 7, 25, 5, 0),
        signup_end=datetime(2026, 10, 23, 4, 59),
        details_url="https://docs.google.com/document/d/x",
        discount_code="SECRET",
        capacity=200,
        status="active",
        audience="both",
        template_key="dry_tri",
        price_options=[
            _option("Run-only 6K", 3000, 2),
            _option("Individual Triathlon", 5500, 0, description="Complete all three legs yourself"),
            _option("Retired", 100, 1, active=False),
        ],
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _client(monkeypatch, events):
    monkeypatch.setattr(event_api, "_all_events", lambda: events)
    return create_app().test_client()


def test_returns_the_selected_event_with_the_public_shape(monkeypatch):
    body = _client(monkeypatch, [_stub_event()]).get("/api/events/dry-tri").get_json()

    event = body["event"]
    assert set(event) == {
        "slug", "name", "location", "description", "event_date", "signup_start",
        "signup_end", "registration_path", "details_url", "entries",
    }
    assert event["registration_path"] == "/events/dry-tri-2026"
    assert event["signup_end"] == "2026-10-23T04:59:00Z"
    assert event["description"].startswith("Schedule of events\r\n")
    assert body["generated_at"].endswith("Z")


def test_entries_are_active_options_in_sort_order_with_public_prices_only(monkeypatch):
    body = _client(monkeypatch, [_stub_event()]).get("/api/events/dry-tri").get_json()

    assert body["event"]["entries"] == [
        {"name": "Individual Triathlon", "description": "Complete all three legs yourself", "price_cents": 5500},
        {"name": "Run-only 6K", "description": "", "price_cents": 3000},
    ]


def test_never_leaks_member_pricing_or_the_discount_code(monkeypatch):
    raw = _client(monkeypatch, [_stub_event()]).get("/api/events/dry-tri").get_data(as_text=True)

    for secret in ("member_price", "SECRET", "discount", "capacity", "3500"):
        assert secret not in raw


def test_no_event_returns_null_not_404(monkeypatch):
    resp = _client(monkeypatch, []).get("/api/events/dry-tri")
    assert resp.status_code == 200
    assert resp.get_json()["event"] is None


def test_unknown_series_is_404(monkeypatch):
    assert _client(monkeypatch, []).get("/api/events/pickleball").status_code == 404


def test_cors_and_cache_headers(monkeypatch):
    resp = _client(monkeypatch, [_stub_event()]).get(
        "/api/events/dry-tri", headers={"Origin": "https://twincitiesskiclub.org"}
    )
    assert resp.headers["Access-Control-Allow-Origin"] == "https://twincitiesskiclub.org"
    assert resp.headers["Vary"] == "Origin"
    assert resp.headers["Cache-Control"] == "public, max-age=300"


def test_disallowed_origin_gets_no_cors_header(monkeypatch):
    resp = _client(monkeypatch, [_stub_event()]).get(
        "/api/events/dry-tri", headers={"Origin": "https://evil.example"}
    )
    assert "Access-Control-Allow-Origin" not in resp.headers
```

Add one ORM-backed test to `tests/events/test_routes.py` (it already has the `public_event` fixture, slug `dry-tri-2026`, which needs `template_key` set):

```python
def test_event_api_serves_a_real_event_row(client, public_event):
    event = public_event[0]
    event.template_key = "dry_tri"
    from app.models import db
    db.session.commit()

    body = client.get("/api/events/dry-tri").get_json()

    assert body["event"]["slug"] == "dry-tri-2026"
    assert [e["name"] for e in body["event"]["entries"]] == ["Individual", "Team of 3", "Volunteer"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$PYTEST tests/routes/test_event_api.py tests/events/test_routes.py::test_event_api_serves_a_real_event_row -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.routes.event_api'`

- [ ] **Step 3: Implement**

`app/events/public_payload.py`:

```python
"""Shape one event for the public marketing site.

Public prices only. Member prices stay hidden until a code is verified on
tcsc.ski (PR #236), and the discount code is a secret, so neither is here.
Timestamps only, no open/closed state: see app/routes/season_api.py for why.
"""
from __future__ import annotations

from app.seasons.payload import _iso


def serialize_public_event(event, registration_path: str) -> dict:
    entries = sorted(
        (option for option in event.price_options if option.active),
        key=lambda option: option.sort_order,
    )
    return {
        "slug": event.slug,
        "name": event.name,
        "location": event.location,
        "description": event.description or "",
        "event_date": _iso(event.event_date),
        "signup_start": _iso(event.signup_start),
        "signup_end": _iso(event.signup_end),
        "registration_path": registration_path,
        "details_url": event.details_url,
        "entries": [
            {
                "name": option.name,
                "description": option.description or "",
                "price_cents": option.price_cents,
            }
            for option in entries
        ],
    }
```

`app/routes/event_api.py`:

```python
"""Public event API consumed by the marketing site.

Returns one event per series (selection in app/events/selection.py) as
timestamps and public facts. The registration link is a path, not a URL:
the app has no ProxyFix, so url_for(_external=True) can say http:// behind
Render. The site resolves the path against the API's own origin.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, abort, jsonify, request, url_for

from app.events.models import Event
from app.events.public_payload import serialize_public_event
from app.events.selection import select_public_event
from app.routes.marketing_cors import apply_marketing_cors
from app.seasons.payload import _iso

bp = Blueprint("event_api", __name__, url_prefix="/api")

SERIES = {"dry-tri": "dry_tri"}
_CACHE_MAX_AGE_SECONDS = 300


def _all_events():
    """Seam for tests, which cover shaping without seeding rows."""
    return Event.query.all()


@bp.route("/events/<series>", methods=["GET"])
def get_event_series(series):
    template_key = SERIES.get(series)
    if template_key is None:
        abort(404)
    now = datetime.utcnow()
    event = select_public_event(_all_events(), template_key, now)
    body = {
        "generated_at": _iso(now),
        "event": (
            serialize_public_event(
                event, url_for("events.get_event_page", slug=event.slug)
            )
            if event is not None
            else None
        ),
    }
    resp = jsonify(body)
    apply_marketing_cors(resp, request.headers.get("Origin", ""))
    resp.headers["Cache-Control"] = f"public, max-age={_CACHE_MAX_AGE_SECONDS}"
    return resp
```

`app/__init__.py`: beside line 52 add `from .routes.event_api import bp as event_api_bp`, and beside the `season_api_bp` registration add `app.register_blueprint(event_api_bp)`.

If the 404 test gets a JSON or HTML error body, that is fine; only the status matters.

- [ ] **Step 4: Run tests to verify they pass**

Run: `$PYTEST tests/routes/test_event_api.py tests/events -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/events/public_payload.py app/routes/event_api.py app/__init__.py tests/routes/test_event_api.py tests/events/test_routes.py
git commit -m "Public event API for the marketing site's Dry Tri page"
```

### Task 7: `tcsc.ski/tri` follows the same selection

**Files:**
- Modify: `app/routes/main.py:66-69`
- Test: `tests/events/test_routes.py`

**Interfaces:**
- Consumes: `select_public_event` (Task 5).

- [ ] **Step 1: Write the failing tests**

Append to `tests/events/test_routes.py`:

```python
def test_tri_redirects_to_the_selected_dry_tri(client, public_event):
    event = public_event[0]
    event.template_key = "dry_tri"
    # Not the old hardcoded slug, so the test fails until /tri selects.
    # admin-scope-test is in TEST_EVENT_SLUGS, so cleanup still removes it.
    event.slug = "admin-scope-test"
    from app.models import db
    db.session.commit()

    resp = client.get("/tri")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith(f"/events/{event.slug}")


def test_tri_without_a_dry_tri_goes_home(client, db_session):
    with patch("app.routes.main.Event") as event_model:
        event_model.query.filter.return_value.all.return_value = []
        resp = client.get("/tri")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$PYTEST tests/events/test_routes.py -k tri_ -v`
Expected: FAIL. Both redirect to the hardcoded `/events/dry-tri-2026`.

- [ ] **Step 3: Implement**

In `app/routes/main.py`, ensure `Event` is imported (it already is, for the home page query) and add:

```python
from app.events.selection import select_public_event
```

Replace the route body:

```python
@main.route('/tri')
@main.route('/dryland-triathlon')
def dryland_triathlon_page():
    candidates = Event.query.filter(Event.template_key == 'dry_tri').all()
    event = select_public_event(candidates, 'dry_tri', datetime.utcnow())
    if event is None:
        return redirect('/', code=302)
    return redirect(url_for('events.get_event_page', slug=event.slug), code=302)
```

Import `datetime` and `url_for` if `main.py` lacks them (check the top of the file).

- [ ] **Step 4: Run tests to verify they pass**

Run: `$PYTEST tests/events tests/routes -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/main.py tests/events/test_routes.py
git commit -m "tcsc.ski/tri redirects to the current Dry Tri, not a hardcoded slug"
```

### Task 8: Site event data and state rule

**Files:**
- Create: `site/src/lib/eventState.ts`
- Create: `site/src/lib/eventData.ts`
- Test: `site/tests/eventState.test.mjs`, `site/tests/eventData.test.mjs`

**Interfaces:**
- Produces (`eventState.ts`): `type EventState = 'upcoming' | 'open' | 'closed' | 'past'`; `interface EventTimes { event_date: string; signup_start: string; signup_end: string }`; `endOfCentralDay(instant: number): number`; `deriveEventState(t: EventTimes, now: number): EventState`.
- Produces (`eventData.ts`): `interface EventEntry { name: string; description: string; price_cents: number }`; `interface EventRecord extends EventTimes { slug: string; name: string; location: string; description: string; registration_path: string; details_url: string | null; entries: EventEntry[] }`; `interface EventData { source: 'api' | 'fallback'; event: EventRecord | null }`; `eventApiUrl(): string`; `fetchEventData(url?: string): Promise<EventData>`; `registrationUrl(event: EventRecord, apiUrl?: string): string`; `FALLBACK_URL = 'https://tcsc.ski/tri'`.

- [ ] **Step 1: Write the failing tests**

`site/tests/eventState.test.mjs`:

```js
import assert from 'node:assert/strict';
import test from 'node:test';

import { deriveEventState, endOfCentralDay } from '../src/lib/eventState.ts';

const TIMES = {
  signup_start: '2026-07-25T05:00:00Z',
  signup_end: '2026-10-23T04:59:00Z',
  event_date: '2026-10-24T14:00:00Z',
};
const at = (iso) => Date.parse(iso);

test('upcoming before signups open', () => {
  assert.equal(deriveEventState(TIMES, at('2026-07-25T04:59:59Z')), 'upcoming');
});

test('open at both boundaries, inclusive like the server', () => {
  assert.equal(deriveEventState(TIMES, at('2026-07-25T05:00:00Z')), 'open');
  assert.equal(deriveEventState(TIMES, at('2026-10-23T04:59:00Z')), 'open');
});

test('closed after signups end and through race day in Central', () => {
  assert.equal(deriveEventState(TIMES, at('2026-10-23T04:59:01Z')), 'closed');
  // 11:30 PM Central on race day is already Oct 25 in UTC.
  assert.equal(deriveEventState(TIMES, at('2026-10-25T04:30:00Z')), 'closed');
});

test('past from Central midnight after race day', () => {
  assert.equal(deriveEventState(TIMES, at('2026-10-25T05:00:00Z')), 'past');
});

test('end of a CST day is 06:00Z, of a CDT day 05:00Z', () => {
  assert.equal(endOfCentralDay(at('2026-01-19T18:00:00Z')), at('2026-01-20T06:00:00Z'));
  assert.equal(endOfCentralDay(at('2026-10-24T14:00:00Z')), at('2026-10-25T05:00:00Z'));
});

test('spring-forward: the day before ends at CST midnight, the day itself at CDT midnight', () => {
  // DST starts Sunday Mar 14 2027 at 2 AM. Midnight starting Mar 14 is still CST.
  assert.equal(endOfCentralDay(at('2027-03-13T18:00:00Z')), at('2027-03-14T06:00:00Z'));
  assert.equal(endOfCentralDay(at('2027-03-14T18:00:00Z')), at('2027-03-15T05:00:00Z'));
});

test('unparseable timestamps read as closed, never open', () => {
  assert.equal(deriveEventState({ ...TIMES, signup_end: 'nope' }, at('2026-08-01T00:00:00Z')), 'closed');
});
```

`site/tests/eventData.test.mjs`:

```js
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import test from 'node:test';

import { fetchEventData, registrationUrl, FALLBACK_URL } from '../src/lib/eventData.ts';

async function withServer(handler, run) {
  const server = createServer(handler);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}/api/events/dry-tri`;
  try {
    return await run(url);
  } finally {
    server.close();
  }
}

test('a healthy response is source api', async () => {
  const body = { generated_at: '2026-10-06T15:00:00Z', event: { slug: 'dry-tri-2026', entries: [] } };
  await withServer((_, res) => res.end(JSON.stringify(body)), async (url) => {
    const data = await fetchEventData(url);
    assert.equal(data.source, 'api');
    assert.equal(data.event.slug, 'dry-tri-2026');
  });
});

test('a null event from a healthy API is still source api', async () => {
  await withServer((_, res) => res.end('{"event": null}'), async (url) => {
    const data = await fetchEventData(url);
    assert.deepEqual(data, { source: 'api', event: null });
  });
});

test('a 500 falls back instead of throwing', async () => {
  await withServer((_, res) => { res.statusCode = 500; res.end(); }, async (url) => {
    assert.deepEqual(await fetchEventData(url), { source: 'fallback', event: null });
  });
});

test('registration path resolves against the API origin', () => {
  const event = { registration_path: '/events/dry-tri-2026' };
  assert.equal(
    registrationUrl(event, 'https://tcsc.ski/api/events/dry-tri'),
    'https://tcsc.ski/events/dry-tri-2026',
  );
});

test('a missing path falls back to tcsc.ski/tri', () => {
  assert.equal(registrationUrl({ registration_path: '' }, 'https://tcsc.ski/api/events/dry-tri'), FALLBACK_URL);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `site/`): `node --test tests/eventState.test.mjs tests/eventData.test.mjs`
Expected: FAIL with `ERR_MODULE_NOT_FOUND`

- [ ] **Step 3: Implement**

`site/src/lib/eventState.ts`:

```ts
// The Dry Tri page's registration state rule, in one place.
//
// Imported by the Astro build and shipped to the browser. The API sends
// timestamps only, so both callers derive the state here from the same
// inputs and cannot disagree. Mirrors registrationState.ts for seasons.
export type EventState = 'upcoming' | 'open' | 'closed' | 'past';

export interface EventTimes {
  event_date: string;
  signup_start: string;
  signup_end: string;
}

const CENTRAL = 'America/Chicago';

function centralParts(instant: number): { year: number; month: number; day: number; hour: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: CENTRAL,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    hourCycle: 'h23',
  }).formatToParts(new Date(instant));
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  return { year: get('year'), month: get('month'), day: get('day'), hour: get('hour') };
}

/** First instant of the Central calendar day after the one holding `instant`. */
export function endOfCentralDay(instant: number): number {
  const { year, month, day } = centralParts(instant);
  // Central midnight is 05:00Z (CDT) or 06:00Z (CST). US DST changes at
  // 2 AM, so exactly one candidate lands on hour 0.
  for (const utcHour of [5, 6]) {
    const candidate = Date.UTC(year, month - 1, day + 1, utcHour);
    if (centralParts(candidate).hour === 0) return candidate;
  }
  throw new Error(`no Central midnight found after ${new Date(instant).toISOString()}`);
}

/** `now` is a millisecond epoch so build and browser share the signature. */
export function deriveEventState(t: EventTimes, now: number): EventState {
  const start = Date.parse(t.signup_start);
  const end = Date.parse(t.signup_end);
  const race = Date.parse(t.event_date);
  if ([start, end, race].some(Number.isNaN)) return 'closed';
  if (now >= endOfCentralDay(race)) return 'past';
  if (now < start) return 'upcoming';
  // Inclusive, matching events.py: signup_start <= now <= signup_end.
  if (now <= end) return 'open';
  return 'closed';
}
```

`site/src/lib/eventData.ts`:

```ts
// Build-time fetch of the current Dry Tri from tcsc.ski.
//
// Never fails the build: an unreachable API yields { source: 'fallback' },
// the page renders its generic line pointing at tcsc.ski/tri, and the band
// carries data-event-source="fallback" so the cause is visible in the HTML.
import type { EventTimes } from './eventState.ts';

export interface EventEntry {
  name: string;
  description: string;
  price_cents: number;
}

export interface EventRecord extends EventTimes {
  slug: string;
  name: string;
  location: string;
  description: string;
  registration_path: string;
  details_url: string | null;
  entries: EventEntry[];
}

export interface EventData {
  source: 'api' | 'fallback';
  event: EventRecord | null;
}

export const FALLBACK_URL = 'https://tcsc.ski/tri';
const FETCH_TIMEOUT_MS = 10_000;

export function eventApiUrl(): string {
  // Optional chaining: plain `node --test` has no import.meta.env.
  return import.meta.env?.PUBLIC_EVENT_API_URL ?? 'https://tcsc.ski/api/events/dry-tri';
}

export function registrationUrl(event: Pick<EventRecord, 'registration_path'>, apiUrl: string = eventApiUrl()): string {
  if (!event.registration_path) return FALLBACK_URL;
  return new URL(event.registration_path, apiUrl).toString();
}

export async function fetchEventData(url: string = eventApiUrl()): Promise<EventData> {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const body = await response.json();
    return { source: 'api', event: body?.event ?? null };
  } catch (error) {
    console.warn(`[event] ${url} unreachable (${error}). The Dry Tri band will use its fallback line.`);
    return { source: 'fallback', event: null };
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/eventState.test.mjs tests/eventData.test.mjs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add site/src/lib/eventState.ts site/src/lib/eventData.ts site/tests/eventState.test.mjs site/tests/eventData.test.mjs
git commit -m "Site: Dry Tri event fetch and registration state rule"
```

### Task 9: One render function for the event band

**Files:**
- Create: `site/src/lib/eventRender.ts`
- Test: `site/tests/eventRender.test.mjs`

**Interfaces:**
- Consumes: `deriveEventState`, `EventState` (Task 8); `EventRecord`, `registrationUrl`, `FALLBACK_URL` (Task 8).
- Produces: `renderEventBand(event: EventRecord | null, now: number, apiUrl: string): string` (inner HTML of the band); `descriptionHtml(text: string): string`; `formatPrice(cents: number): string`; `escapeHtml(s: string): string`; `raceDayShort(iso: string): string` ("Sat, Oct 24"); `raceYear(iso: string): string` ("2026").

- [ ] **Step 1: Write the failing test**

```js
import assert from 'node:assert/strict';
import test from 'node:test';
import { JSDOM } from 'jsdom';

import {
  descriptionHtml, escapeHtml, formatPrice, raceDayShort, raceYear, renderEventBand,
} from '../src/lib/eventRender.ts';

const API = 'https://tcsc.ski/api/events/dry-tri';
const EVENT = {
  slug: 'dry-tri-2026',
  name: 'TCSC Roll, Ride, and Run Dry Tri 2026',
  location: 'Carver Park Reserve, Parley Lake, Victoria',
  description: "TCSC's fall race.\r\n\r\nSchedule of events\r\n\r\n- 7:30 AM: Packet pickup opens\r\n- 9:00 AM: Long course Wave 1",
  event_date: '2026-10-24T14:00:00Z',
  signup_start: '2026-07-25T05:00:00Z',
  signup_end: '2026-10-23T04:59:00Z',
  registration_path: '/events/dry-tri-2026',
  details_url: 'https://docs.google.com/document/d/x',
  entries: [
    { name: 'Individual Triathlon', description: 'Complete all three legs yourself', price_cents: 5500 },
    { name: 'Relay Triathlon', description: 'One registration covers your whole team.', price_cents: 10500 },
    { name: 'Run-only 6K', description: 'Just the 6K trail run', price_cents: 3000 },
  ],
};
const at = (iso) => Date.parse(iso);
const dom = (html) => new JSDOM(`<div id="b">${html}</div>`).window.document.getElementById('b');

test('prices drop .00 and keep real cents', () => {
  assert.equal(formatPrice(5500), '$55');
  assert.equal(formatPrice(5550), '$55.50');
  assert.equal(formatPrice(0), '$0');
});

test('race day and year format in Central', () => {
  assert.equal(raceDayShort(EVENT.event_date), 'Sat, Oct 24');
  // 11 PM Central on Dec 31 is already Jan 1 in UTC; the year stays Central.
  assert.equal(raceYear('2027-01-01T05:00:00Z'), '2026');
});

test('description handles CRLF and mixed blocks', () => {
  const el = dom(descriptionHtml(EVENT.description));
  assert.deepEqual([...el.querySelectorAll('p')].map((p) => p.textContent), ["TCSC's fall race.", 'Schedule of events']);
  assert.deepEqual([...el.querySelectorAll('li')].map((li) => li.textContent), [
    '7:30 AM: Packet pickup opens', '9:00 AM: Long course Wave 1',
  ]);
  assert.ok(!el.innerHTML.includes('\r'));
});

test('consecutive plain lines stay in one paragraph with a line break', () => {
  const el = dom(descriptionHtml('Line one\nLine two'));
  assert.equal(el.querySelectorAll('p').length, 1);
  assert.equal(el.querySelectorAll('br').length, 1);
});

test('escapes HTML in every field', () => {
  const nasty = '<img src=x onerror=alert(1)> & "q"';
  const event = {
    ...EVENT,
    location: nasty,
    description: nasty,
    details_url: 'javascript:alert(1)',
    entries: [{ name: nasty, description: nasty, price_cents: 100 }],
  };
  const el = dom(renderEventBand(event, at('2026-10-06T15:00:00Z'), API));
  assert.equal(el.querySelector('img'), null);
  assert.ok(el.textContent.includes('<img src=x onerror=alert(1)> & "q"'));
  assert.equal(el.querySelector('a[href^="javascript"]'), null);
  assert.equal(escapeHtml(`<&>"'`), '&lt;&amp;&gt;&quot;&#39;');
});

test('open state shows Register and the closing day', () => {
  const el = dom(renderEventBand(EVENT, at('2026-10-06T15:00:00Z'), API));
  const button = el.querySelector('[data-event-cta] a');
  assert.equal(button.textContent, 'Register');
  assert.equal(button.getAttribute('href'), 'https://tcsc.ski/events/dry-tri-2026');
  assert.ok(el.textContent.includes('Registration closes Thursday, October 22.'));
  assert.equal(el.querySelector('[data-event-cta]').getAttribute('data-state'), 'open');
});

test('upcoming, closed and past copy', () => {
  const text = (iso) => dom(renderEventBand(EVENT, at(iso), API)).querySelector('[data-event-cta]').textContent.trim();
  assert.equal(text('2026-07-01T12:00:00Z'), 'Registration opens Saturday, July 25');
  assert.equal(text('2026-10-23T12:00:00Z'), 'Registration is closed. See you at the start.');
  assert.equal(text('2026-10-26T12:00:00Z'), '');
});

test('shows date, time, location, entries and the details link', () => {
  const el = dom(renderEventBand(EVENT, at('2026-10-06T15:00:00Z'), API));
  assert.ok(el.textContent.includes('Saturday, October 24 · 9:00 AM'));
  assert.ok(el.textContent.includes('Carver Park Reserve, Parley Lake, Victoria'));
  assert.deepEqual([...el.querySelectorAll('[data-entry-price]')].map((p) => p.textContent), ['$55', '$105', '$30']);
  assert.equal(el.querySelector('a[data-event-details]').textContent, 'Full race details');
});

test('no event renders the fallback line linking tcsc.ski/tri', () => {
  const el = dom(renderEventBand(null, at('2026-10-06T15:00:00Z'), API));
  const link = el.querySelector('a');
  assert.equal(link.getAttribute('href'), 'https://tcsc.ski/tri');
  assert.equal(el.textContent.trim(), 'Dates, entries and registration: tcsc.ski/tri');
});

test('no em or en dashes in any rendered copy', () => {
  for (const iso of ['2026-07-01T12:00:00Z', '2026-10-06T15:00:00Z', '2026-10-23T12:00:00Z', '2026-10-26T12:00:00Z']) {
    const html = renderEventBand(EVENT, at(iso), API) + renderEventBand(null, at(iso), API);
    assert.ok(!/[\u2013\u2014]/.test(html), `dash in ${iso}`);
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/eventRender.test.mjs`
Expected: FAIL with `ERR_MODULE_NOT_FOUND`

- [ ] **Step 3: Implement**

`site/src/lib/eventRender.ts`:

```ts
// The Dry Tri event band, as an HTML string.
//
// One function serves both the Astro build (set:html) and the browser
// refresh (innerHTML), so the baked page and the refreshed page cannot
// drift. Every value from the API is escaped: admins type the description,
// location and entry names, and none of it is trusted markup.
import { deriveEventState, type EventState } from './eventState.ts';
import { FALLBACK_URL, registrationUrl, type EventRecord } from './eventData.ts';

const CENTRAL = 'America/Chicago';

export function escapeHtml(s: string): string {
  return String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function central(iso: string, options: Intl.DateTimeFormatOptions): string {
  return new Date(iso).toLocaleString('en-US', { ...options, timeZone: CENTRAL });
}

/** "Saturday, October 24" */
const longDay = (iso: string) => central(iso, { weekday: 'long', month: 'long', day: 'numeric' });
/** "9:00 AM". ICU puts U+202F (narrow no-break space) before AM/PM; use a plain space. */
const clock = (iso: string) => central(iso, { hour: 'numeric', minute: '2-digit' }).replace(/\u202f/g, ' ');
/** "Sat, Oct 24" */
export const raceDayShort = (iso: string) => central(iso, { weekday: 'short', month: 'short', day: 'numeric' });
/** "2026" */
export const raceYear = (iso: string) => central(iso, { year: 'numeric' });

export function formatPrice(cents: number): string {
  const dollars = cents / 100;
  return Number.isInteger(dollars) ? `$${dollars}` : `$${dollars.toFixed(2)}`;
}

/** Blank lines separate blocks; "- " lines become a list; other lines a paragraph. */
export function descriptionHtml(text: string): string {
  const out: string[] = [];
  let list: string[] = [];
  let para: string[] = [];
  const flushList = () => {
    if (list.length) out.push(`<ul>${list.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`);
    list = [];
  };
  const flushPara = () => {
    if (para.length) out.push(`<p>${para.map(escapeHtml).join('<br>')}</p>`);
    para = [];
  };
  for (const raw of (text ?? '').replace(/\r\n?/g, '\n').split('\n')) {
    const line = raw.trim();
    if (!line) {
      flushList();
      flushPara();
    } else if (line.startsWith('- ')) {
      flushPara();
      list.push(line.slice(2).trim());
    } else {
      flushList();
      para.push(line);
    }
  }
  flushList();
  flushPara();
  return out.join('');
}

const BUTTON =
  'inline-flex items-center px-5 py-3 rounded-md bg-navy text-mint font-semibold text-sm transition-colors duration-150 hover:bg-navy-deep active:bg-navy/90';
const LINK =
  'font-semibold text-navy underline underline-offset-4 decoration-ink/30 hover:decoration-mint-deep hover:text-mint-deep transition-colors';

function ctaHtml(event: EventRecord, state: EventState, apiUrl: string): string {
  switch (state) {
    case 'upcoming':
      return `<p class="font-semibold text-navy">Registration opens ${escapeHtml(longDay(event.signup_start))}</p>`;
    case 'open':
      return (
        `<a class="${BUTTON}" href="${escapeHtml(registrationUrl(event, apiUrl))}">Register</a>` +
        `<p class="mt-3 text-sm text-slate">Registration closes ${escapeHtml(longDay(event.signup_end))}.</p>`
      );
    case 'closed':
      return '<p class="font-semibold text-navy">Registration is closed. See you at the start.</p>';
    case 'past':
      return '';
  }
}

function safeHttpUrl(url: string | null): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.toString() : null;
  } catch {
    return null;
  }
}

export function renderEventBand(event: EventRecord | null, now: number, apiUrl: string): string {
  if (!event) {
    return `<p class="text-lg text-ink">Dates, entries and registration: <a class="${LINK}" href="${FALLBACK_URL}">tcsc.ski/tri</a></p>`;
  }
  const state = deriveEventState(event, now);
  const entries = event.entries
    .map(
      (entry) =>
        `<div class="py-4 grid grid-cols-[1fr_auto] gap-x-6">` +
        `<div><div class="font-semibold text-navy">${escapeHtml(entry.name)}</div>` +
        (entry.description ? `<div class="text-sm text-ink/70 mt-0.5">${escapeHtml(entry.description)}</div>` : '') +
        `</div><div class="font-semibold text-navy tabular-nums" data-entry-price>${formatPrice(entry.price_cents)}</div></div>`,
    )
    .join('');
  const details = safeHttpUrl(event.details_url);
  return (
    `<div class="grid gap-10 md:grid-cols-2">` +
    `<div>` +
    `<p class="text-2xl font-semibold text-navy">${escapeHtml(longDay(event.event_date))} · ${escapeHtml(clock(event.event_date))}</p>` +
    `<p class="mt-1 text-ink/80">${escapeHtml(event.location)}</p>` +
    `<div class="mt-6 prose text-ink">${descriptionHtml(event.description)}</div>` +
    `</div>` +
    `<div>` +
    `<div class="divide-y divide-ink/10 border-y border-ink/10">${entries}</div>` +
    `<div class="mt-6" data-event-cta data-state="${state}">${ctaHtml(event, state, apiUrl)}</div>` +
    (details ? `<p class="mt-6 text-sm"><a class="${LINK}" data-event-details href="${escapeHtml(details)}">Full race details</a></p>` : '') +
    `</div>` +
    `</div>`
  );
}
```

`EventRecord` needs `import type` for a type and a value import for `FALLBACK_URL`/`registrationUrl`; the combined `import { ..., type EventRecord }` form above does both.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/eventRender.test.mjs tests/eventState.test.mjs tests/eventData.test.mjs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add site/src/lib/eventRender.ts site/tests/eventRender.test.mjs
git commit -m "Site: one render function for the Dry Tri event band"
```

### Task 10: Wire the page, browser refresh, content and build test

**Files:**
- Create: `site/src/lib/eventRefresh.ts`
- Modify: `site/src/pages/dry-tri.astro`
- Modify: `site/src/content/pages/dry_tri.mdoc`
- Modify: `site/src/content.config.ts:366-400` (dry_tri schema)
- Modify: `site/keystatic.config.ts:226-251` (dry_tri singleton)
- Modify: `site/scripts/test-build.mjs`
- Modify: `site/package.json` (`test:refinement` list)
- Test: `site/tests/eventRefresh.test.mjs`, `site/tests/dryTriBuild.test.mjs`

**Interfaces:**
- Consumes: everything from Tasks 8 and 9.
- Produces: `refreshEventBands(root: ParentNode, fetchFn: typeof fetch, now: () => number): Promise<void>`. Band element contract: `[data-event-band]` with `data-event-api` (URL), `data-event` (baked JSON or `null`), `data-event-source` (`api` | `fallback`, set to `live` after a successful browser fetch).

- [ ] **Step 1: Write the failing refresh test**

`site/tests/eventRefresh.test.mjs`:

```js
import assert from 'node:assert/strict';
import test from 'node:test';
import { JSDOM } from 'jsdom';

import { refreshEventBands } from '../src/lib/eventRefresh.ts';

const EVENT = {
  slug: 'dry-tri-2026', name: 'Dry Tri', location: 'Carver Park Reserve', description: '',
  event_date: '2026-10-24T14:00:00Z', signup_start: '2026-07-25T05:00:00Z', signup_end: '2026-10-23T04:59:00Z',
  registration_path: '/events/dry-tri-2026', details_url: null, entries: [],
};
const API = 'https://tcsc.ski/api/events/dry-tri';

function page(baked) {
  const { document } = new JSDOM(
    `<div data-event-band data-event-api="${API}" data-event-source="api" data-event='${JSON.stringify(baked)}'>BAKED</div>`,
  ).window;
  return { document, band: document.querySelector('[data-event-band]') };
}
const ok = (body) => async () => ({ ok: true, json: async () => body });

test('re-derives the state from baked data with the current time', async () => {
  const { document, band } = page(EVENT);
  await refreshEventBands(document, async () => { throw new Error('offline'); }, () => Date.parse('2026-10-23T12:00:00Z'));
  assert.equal(band.querySelector('[data-event-cta]').getAttribute('data-state'), 'closed');
  assert.equal(band.getAttribute('data-event-source'), 'api');
});

test('a fresh event replaces the band and marks it live', async () => {
  const { document, band } = page(EVENT);
  const fresh = { ...EVENT, location: 'New place' };
  await refreshEventBands(document, ok({ event: fresh }), () => Date.parse('2026-10-06T15:00:00Z'));
  assert.ok(band.textContent.includes('New place'));
  assert.equal(band.getAttribute('data-event-source'), 'live');
});

test('a null event from the API switches to the fallback line', async () => {
  const { document, band } = page(EVENT);
  await refreshEventBands(document, ok({ event: null }), () => Date.parse('2026-10-06T15:00:00Z'));
  assert.ok(band.textContent.includes('tcsc.ski/tri'));
});

test('a failed fetch with no baked event leaves the fallback markup alone', async () => {
  const { document, band } = page(null);
  await refreshEventBands(document, async () => ({ ok: false, status: 503 }), () => Date.now());
  assert.equal(band.textContent, 'BAKED');
});

test('a malformed body leaves the baked band alone', async () => {
  const { document, band } = page(null);
  await refreshEventBands(document, ok({ unexpected: true }), () => Date.now());
  assert.equal(band.textContent, 'BAKED');
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test tests/eventRefresh.test.mjs`
Expected: FAIL with `ERR_MODULE_NOT_FOUND`

- [ ] **Step 3: Implement `eventRefresh.ts`**

```ts
// Browser refresh for the Dry Tri band.
//
// The marketing site rebuilds only on a commit, so the baked band is only
// as fresh as the last deploy. On load this (1) re-renders from the baked
// JSON with the current time, so the button flips at the right minute even
// offline, then (2) fetches the API and re-renders from fresh data, so an
// admin edit on tcsc.ski shows up without a deploy. Any failure leaves what
// is already on the page.
import { renderEventBand } from './eventRender.ts';
import type { EventRecord } from './eventData.ts';

const FETCH_TIMEOUT_MS = 10_000;

function parseBaked(raw: string | null): EventRecord | null {
  try {
    return raw ? (JSON.parse(raw) as EventRecord | null) : null;
  } catch {
    return null;
  }
}

export async function refreshEventBands(
  root: ParentNode,
  fetchFn: typeof fetch,
  now: () => number,
): Promise<void> {
  const bands = Array.from(root.querySelectorAll<HTMLElement>('[data-event-band]'));
  await Promise.all(
    bands.map(async (band) => {
      const apiUrl = band.getAttribute('data-event-api') ?? '';
      const baked = parseBaked(band.getAttribute('data-event'));
      if (baked) band.innerHTML = renderEventBand(baked, now(), apiUrl);
      if (!apiUrl) return;
      try {
        const response = await fetchFn(apiUrl, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
        if (!response.ok) return;
        const body = await response.json();
        if (!body || !('event' in body)) return;
        band.innerHTML = renderEventBand(body.event, now(), apiUrl);
        band.setAttribute('data-event-source', 'live');
      } catch {
        // Keep the baked band.
      }
    }),
  );
}
```

Run: `node --test tests/eventRefresh.test.mjs`
Expected: PASS

- [ ] **Step 4: Content and schema**

`site/src/content/pages/dry_tri.mdoc`, full replacement:

```markdown
---
headline: The Dry Tri
intro: >-
  Our fall race at Carver Park Reserve: rollerski, mountain bike, trail run.
  Do all three yourself, split them with a team of three, or just run the 6K.
  Open to everyone.
courses:
  - name: Long course
    legs: 18K roll · 17K ride · 11K run
  - name: Short course
    legs: 9K roll · 9K ride · 6K run
  - name: Run only
    legs: 6K trail run
roll_photo: ../../assets/images/photos/dry-tri-roller.jpg
roll_photo_alt: A racer in a TCSC jersey at full effort on the rollerski leg
ride_photo: ../../assets/images/photos/dry-tri-rider.jpg
ride_photo_alt: A smiling rider in a beanie on the bike leg, fall color behind her
run_photo: ../../assets/images/photos/dry-tri-runner.jpg
run_photo_alt: A runner with mud-spattered legs mid-stride on the run leg
results_url: https://my.raceresult.com/361087/results
---
## 2025

The first Dry Tri was held on October 25, 2025. The course was wet, with leaf-covered pavement on the rollerski leg and standing water on the bike trails. About 25 racers took the start, competing solo and in three-person relay teams.

The event was run by about twenty club volunteers covering parking, course marshaling, chip timing, the finish line, photography, and cleanup. Planning for the next edition started soon after the finish.
```

`site/src/content.config.ts`, in the `dry_tri` schema: delete the `start: z.string().optional(),` line inside `courses`, and delete `register_url: z.url().optional(),`. The course object stays `.strict()`, so a leftover `start:` in the `.mdoc` fails the build loudly, which is what we want.

`site/keystatic.config.ts`, in the `dry_tri` singleton: delete `start: fields.text({ label: 'Start time' }),` and `register_url: fields.url({ label: 'Registration URL' }),`, and change the courses label from `'Courses (2025 format)'` to `'Courses'`.

Update the comment at `content.config.ts:366` if it mentions the 2026 status or a registration URL.

- [ ] **Step 5: Page**

`site/src/pages/dry-tri.astro`, full replacement:

```astro
---
// /dry-tri: the club's own public race. Roll/Ride/Run triptych under the
// masthead, then the current race from tcsc.ski (baked at build, refreshed
// in the browser by eventRefresh.ts), then the course distances, then the
// recap from the markdoc body, then the results link.
import { getEntry, render } from 'astro:content';
import { Image } from 'astro:assets';
import InnerPageLayout from '@/layouts/InnerPageLayout.astro';
import SectionBand from '@/components/SectionBand.astro';
import { MOSAIC } from '@/components/imageWidths';
import { metaDescription } from '@/lib/metaDescription';
import { eventApiUrl, fetchEventData } from '@/lib/eventData';
import { raceDayShort, raceYear, renderEventBand } from '@/lib/eventRender';

const page = await getEntry('dry_tri', 'dry_tri');
if (!page) throw new Error('dry_tri singleton missing (src/content/pages/dry_tri.mdoc)');
const { Content } = await render(page);
const d = page.data;
const legs = [
  { label: 'Roll', src: d.roll_photo, alt: d.roll_photo_alt },
  { label: 'Ride', src: d.ride_photo, alt: d.ride_photo_alt },
  { label: 'Run', src: d.run_photo, alt: d.run_photo_alt },
].filter((l) => l.src);

const apiUrl = eventApiUrl();
const { source, event } = await fetchEventData(apiUrl);
const facts = [
  ...(event ? [{ value: raceDayShort(event.event_date), label: 'Race day' }] : []),
  { value: 'Carver Park Reserve', label: 'Venue' },
  { value: 'Roll · Ride · Run', label: 'Format' },
];
---
<InnerPageLayout
  title="Dry Tri · Twin Cities Ski Club"
  description={d.intro && metaDescription(d.intro)}
  headline={d.headline ?? 'The Dry Tri'}
  subhead={d.intro}
  facts={facts}
>
  {legs.length === 3 && (
    <section class="safe-inline-6-10 mx-auto max-w-7xl px-6 md:px-10 pt-14 md:pt-20" aria-label="The three legs">
      <div class="grid grid-cols-3 gap-px bg-ink/10 border border-ink/10">
        {legs.map((l) => (
          <figure class="bg-paper">
            <div class="relative aspect-[4/5] overflow-hidden">
              <Image
                src={l.src!}
                alt={l.alt ?? ''}
                widths={MOSAIC}
                width={Math.min(1200, l.src!.width)}
                height={Math.round((Math.min(1200, l.src!.width) * 5) / 4)}
                fit="cover"
                position="attention"
                sizes="33vw"
                class="absolute inset-0 w-full h-full object-cover"
                loading="eager"
                decoding="async"
              />
            </div>
          </figure>
        ))}
      </div>
    </section>
  )}
  <SectionBand variant="paper" seam={event ? `${raceYear(event.event_date)} race` : 'This year'}>
    <div
      data-event-band
      data-event-api={apiUrl}
      data-event-source={source}
      data-event={JSON.stringify(event)}
      set:html={renderEventBand(event, Date.now(), apiUrl)}
    />
  </SectionBand>
  {d.courses.length > 0 && (
    <SectionBand variant="paper" seam="The course">
      <div class="divide-y divide-ink/10 border-t border-ink/10">
        {d.courses.map((c) => (
          <div class="py-5 grid gap-x-6 gap-y-1 sm:grid-cols-[10rem_1fr]">
            <div class="font-semibold text-navy">{c.name}</div>
            <div class="text-ink/80">{c.legs}</div>
          </div>
        ))}
      </div>
      <p class="mt-4 text-sm text-slate">Each leg starts and ends at the transition zone in the Parley Lake lot.</p>
    </SectionBand>
  )}
  <div class="safe-inline-6 mx-auto max-w-3xl px-6 pb-12">
    <div class="prose prose-lg max-w-prose text-ink">
      <Content />
    </div>
    {d.results_url && (
      <div class="mt-8 flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <a
          href={d.results_url}
          class="font-semibold text-navy underline underline-offset-4 decoration-ink/30 hover:decoration-mint-deep hover:text-mint-deep transition-colors"
        >Latest results</a>
      </div>
    )}
  </div>
</InnerPageLayout>

<script>
  import { refreshEventBands } from '@/lib/eventRefresh';
  void refreshEventBands(document, fetch.bind(window), Date.now);
</script>
```

- [ ] **Step 6: Build fixture and build test**

`site/scripts/test-build.mjs`: serve both endpoints from the one server. Replace the `createServer` handler and add the event fixture. The fixture's signup window is open now and the race is ahead, relative to now:

```js
// The Dry Tri fixture: signups open now, race three weeks out, so the
// built page is always in the `open` state.
const eventBody = JSON.stringify({
  generated_at: iso(0),
  event: {
    slug: 'dry-tri-fixture',
    name: 'Fixture Dry Tri',
    location: 'Carver Park Reserve, Parley Lake, Victoria',
    description: 'Fixture race.\r\n\r\n- 7:30 AM: Packet pickup opens',
    event_date: iso(21),
    signup_start: iso(-30),
    signup_end: iso(19),
    registration_path: '/events/dry-tri-fixture',
    details_url: 'https://example.com/details',
    entries: [
      { name: 'Individual Triathlon', description: 'Complete all three legs yourself', price_cents: 5500 },
      { name: 'Run-only 6K', description: 'Just the 6K trail run', price_cents: 3000 },
    ],
  },
});

const server = createServer((request, response) => {
  response.writeHead(200, { 'Content-Type': 'application/json' });
  response.end(request.url.startsWith('/api/events/') ? eventBody : body);
});
```

and add to the build `env`:

```js
    PUBLIC_EVENT_API_URL: `http://127.0.0.1:${port}/api/events/dry-tri`,
```

`site/tests/dryTriBuild.test.mjs`:

```js
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

// TCSC_EDGE_CONFIG builds format 'file', so the page is dist/dry-tri.html.
const html = readFileSync(new URL('../dist/dry-tri.html', import.meta.url), 'utf8');
const { document } = new JSDOM(html).window;
const band = document.querySelector('[data-event-band]');

test('the band was baked from the fixture API, not the fallback', () => {
  assert.equal(band.getAttribute('data-event-source'), 'api');
});

test('the fixture build is open with a Register button to tcsc', () => {
  const cta = band.querySelector('[data-event-cta]');
  assert.equal(cta.getAttribute('data-state'), 'open');
  assert.match(cta.querySelector('a').getAttribute('href'), /\/events\/dry-tri-fixture$/);
});

test('entries and schedule render', () => {
  assert.deepEqual([...band.querySelectorAll('[data-entry-price]')].map((p) => p.textContent), ['$55', '$30']);
  assert.equal(band.querySelector('li').textContent, '7:30 AM: Packet pickup opens');
});

test('baked JSON round-trips for the browser refresh', () => {
  assert.equal(JSON.parse(band.getAttribute('data-event')).slug, 'dry-tri-fixture');
});

test('the old 2026 placeholder and 2025-only labels are gone', () => {
  const text = document.body.textContent;
  assert.ok(!text.includes('Planning for 2026 is underway'));
  assert.ok(!text.includes('The 2025 format'));
  assert.ok(text.includes('Latest results'));
});

test('no em or en dashes in the page body', () => {
  assert.ok(!/[\u2013\u2014]/.test(document.querySelector('main').textContent));
});
```

If the built file is `dist/dry-tri/index.html` instead, check `ls dist | grep dry` and use the path that exists; the existing tests read `dist/index.html` and `TCSC_EDGE_CONFIG` sets `build.format: 'file'`.

`site/package.json`: append `tests/eventState.test.mjs tests/eventData.test.mjs tests/eventRender.test.mjs tests/eventRefresh.test.mjs tests/dryTriBuild.test.mjs` to the end of the `test:refinement` file list.

- [ ] **Step 7: Run the whole site suite**

Run (from `site/`): `npm run test:refinement && npm run test:fallback && npx astro check`
Expected: build succeeds, every test passes, `astro check` reports 0 errors. If `test:fallback` builds without the fixture, `dryTriBuild` is not in that script, so it is unaffected.

- [ ] **Step 8: Commit**

```bash
git add site/src/lib/eventRefresh.ts site/src/pages/dry-tri.astro site/src/content/pages/dry_tri.mdoc site/src/content.config.ts site/keystatic.config.ts site/scripts/test-build.mjs site/package.json site/tests/eventRefresh.test.mjs site/tests/dryTriBuild.test.mjs
git commit -m "Dry Tri page shows the current race from tcsc.ski"
```

### Task 11: Verify against the live API, then ship PR 2

- [ ] **Step 1: Build against production data**

Run (from `site/`): `TCSC_EDGE_CONFIG=true npx astro build --force && grep -o 'data-event-source="[a-z]*"' dist/dry-tri.html`
Expected: `data-event-source="api"`. This needs PR 2's API deployed; until then expect `fallback` and check that the fallback line renders.

- [ ] **Step 2: Look at it**

Serve `dist/` and screenshot `/dry-tri` at 360, 390 and 1280 px wide with the headless Chromium recipe in memory note `headless-chromium-screenshots`. Check: no horizontal scroll at 360, the entries ledger does not wrap prices under names, the Register button is tappable, and the description list renders as a list. Show Rob the screenshots before opening the PR.

- [ ] **Step 3: Python suites once more**

Run: `$PYTEST tests/events tests/routes -q`
Expected: PASS

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin dry-tri-live-page
gh pr create --title "Dry Tri page shows the current race from tcsc.ski" --body "$(cat <<'EOF'
twincitiesskiclub.org/dry-tri said "Planning for 2026 is underway" with no registration link. It now shows the current Dry Tri from tcsc.ski.

- `GET /api/events/dry-tri` on tcsc.ski: the soonest non-draft, non-internal Dry Tri, else the latest past one. Public prices only, no state, marketing CORS, 5 minute cache.
- `tcsc.ski/tri` uses the same selection instead of a hardcoded slug.
- The page bakes the event at build time and re-renders in the browser on load, so admin edits show without a deploy. If tcsc.ski is unreachable it points at tcsc.ski/tri and stamps `data-event-source="fallback"` on the band.
- Register button follows the signup window: opens on, Register, closed, gone after race day.
- Course table fixed (short course roll is 9K, run-only row added); 2026 placeholder removed; results link reads "Latest results".

Spec: docs/superpowers/specs/2026-10-06-dry-tri-live-page-design.md

Overlaps draft #249 in `dry-tri.astro` and `dry_tri.mdoc`; #249 rebases onto this.

After deploy: swap in the 2026 results URL in Keystatic after the race.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: After Rob merges and both Render services deploy**, verify production:

```bash
curl -s https://tcsc.ski/api/events/dry-tri | jq '.event | {slug, event_date, entries: [.entries[].price_cents]}'
curl -s https://twincitiesskiclub.org/dry-tri | grep -o 'data-event-source="[a-z]*"'
```

Expected: slug `dry-tri-2026`, `event_date` `2026-10-24T14:00:00Z`, prices `[5500, 10500, 3000]`; marketing page `data-event-source="api"`. The marketing build runs on the same commit as the API deploy and may race it; if it says `fallback`, trigger a redeploy of `tcsc-team-site` once the API answers.
