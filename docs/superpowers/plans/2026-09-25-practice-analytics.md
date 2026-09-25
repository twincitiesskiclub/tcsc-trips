# Practice Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Archive the club's practice channels in Postgres, rebuild them into one normalized practice lineage (Oct 2022 to today) with weather, and ship an admin Analytics section whose first dashboard answers "Should Thursday strength run as one session or two?"

**Architecture:** Three layers inside a new `app/analytics/` package. (1) A raw Slack archive (`slack_archive_messages`) plus an append-only reaction event log. (2) A pure-Python lineage builder that turns archived messages, app practice rows and a checked-in YAML file into `practice_sessions` and `practice_attendance`, rebuilt from scratch in one transaction, with weather from a cached Open-Meteo table. (3) Dashboards as one Python module each, rendered by one shared Jinja template and one script using vendored Vega-Lite.

**Tech Stack:** Flask 3, Flask-SQLAlchemy 3, Alembic via Flask-Migrate, PostgreSQL 18, slack_sdk WebClient, APScheduler 3, PyYAML, requests, Vega 6 / Vega-Lite 6 / vega-embed 7 (vendored), pytest, jsonschema and vl-convert-python (test only), node:test + jsdom for JS.

**Spec:** `docs/superpowers/specs/2026-09-25-practice-analytics-design.md`. Executors read the spec and this plan.

## Global Constraints

- The GitHub repo is PUBLIC. Never commit real Slack message text, Slack user IDs of members, member names, or per-person data. Committed fixtures are hand-written. Real data lives only in `/workspace/tcsc-trips/.superpowers/analytics-slack-dump/` (gitignored).
- Data lives in the database, not the repo. Per-post corrections live in the `analytics_corrections` table, never in YAML or fixtures. `config/practice_history.yaml` holds only rules (venue names, title keywords, excluded accounts, capacity lines). Hand-verified counts (`lift_verified.json`) stay in `.superpowers/`.
- The only Slack user IDs allowed in committed files are the two excluded accounts: `U06FYPUNQCU` (TCSC app bot) and `U04C46UJXAM` (Zapier-linked account).
- Timestamps in the database are naive UTC (`datetime.utcnow()` convention). Practice dates and times are US Central. Use `app/utils.py` helpers (`now_central_naive()`, `today_central()`), never `datetime.now()`.
- Tests run against the scratch database `tcsc_trips_test`: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test`. Never `db.create_all()` / `db.drop_all()`. DB tests roll back (`db.session.rollback()` in `finally`) instead of committing, or delete exactly the rows they created.
- localhost:5432 is reached through the pgforward relay (see the project memory `pgforward-safe-relay.md`). The orchestrator starts it before any DB test run. Workers do not start or stop it.
- Workers never touch production: no `PROD_DATABASE_URL`, no Slack writes, no Slack reads with real tokens. Only the orchestrator runs anything against prod or real Slack, and only in the tasks marked "orchestrator".
- Nothing in `app/analytics/` writes to `practices`, `practice_rsvps`, or posts to Slack. The only change outside analytics code paths is the guarded event-log call in `_delegate_reaction_event` (Task 5).
- No em dashes in any user-facing copy (templates, notes, tiles, chart titles). Use periods and commas.
- Every new migration bumps `HEAD_REVISION` in `tests/practices/test_practice_migration_release.py`.
- Test-only Python dependencies go in `requirements-dev.txt`, never `requirements.txt`.
- Admin UI is light only, Tailwind 3 classes, following `app/templates/admin/admin_base.html`.
- Before writing code that uses a dependency, read its docs pages listed in the task. Reviews check the code against those docs.
- Codex workers: `codex exec -m gpt-6-astra -c 'model_reasoning_effort="high"' --dangerously-bypass-approvals-and-sandbox ... < /dev/null`, one dispatch per Bash call. Never pass `-s workspace-write` (bubblewrap fails in this container). After launch, wait 45 s and confirm the log has `exec` lines and the session transcript has no `"error"` (project memory `codex-exec-in-container.md`).

## Review Focus

1. A Slack message edited or deleted after import: sync must update `raw`/`edited_at` or set `deleted_at`, and rebuild must drop deleted posts from sessions. Test in Task 4 (`test_sync_marks_deleted_and_updates_edits`).
2. The app bot and Zapier account reacting to posts: they must never appear in `practice_attendance`, including on merged nights and `rsvp_from` messages. Test in Task 8 (`test_excluded_accounts_never_attend`).
3. A thread reply that mentions merging on a different day, or says a night is too big for one session: no merge unless the reply is on the practice date and matches a merge phrase, and a `merged: false` correction always wins. Test in Task 8 (`test_merge_needs_same_day_reply_and_correction_wins`).
4. A filter URL with junk values (`?season=<script>`, `?date_from=notadate`, unknown slug): the page renders with the bad value ignored, never a 500. Test in Task 13 (`test_invalid_filter_values_are_ignored`).
5. Open-Meteo returning an error, an empty body, or units other than requested: the fetch logs, writes nothing, and the rebuild still succeeds with weather left null. Test in Task 10 (`test_fetch_failure_writes_nothing` and `test_units_read_from_response`).

---

## File structure

```
app/analytics/
  __init__.py            channel constants
  models.py              5 SQLAlchemy models
  drafts.py              dataclasses passed between pure functions
  history_config.py      YAML loader, venue and title resolution
  corrections.py         analytics_corrections: validate, load, upsert, import/export
  archive.py             Slack import and 21-day sync (Layer 1)
  reaction_log.py        record_reaction_event (Layer 1)
  parse_template.py      template-era message parsing (pure)
  parse_app.py           app-era sessions from practice rows (pure)
  lineage.py             build_lineage: sessions + attendance + merges + corrections (pure)
  seasons.py             season_label (pure)
  rebuild.py             DB IO: load inputs, replace tables, apply cached weather
  weather.py             Open-Meteo fetch, unit conversion, per-session weather math
  cli.py                 `flask analytics ...`
  jobs.py                nightly job body
  charts.py              Vega-Lite builders and theme (PR 2)
  dashboards/
    __init__.py          registry
    base.py              blocks, filters, loaders
    thursday_strength.py first dashboard
app/routes/admin_analytics.py
app/templates/admin/analytics/index.html
app/templates/admin/analytics/dashboard.html
app/static/admin_analytics.js
app/static/vendor/vega@6.x.x.min.js, vega-lite@6.x.x.min.js, vega-embed@7.x.x.min.js
config/practice_history.yaml
migrations/versions/b8e4d2a9c731_practice_analytics.py
requirements-dev.txt
tests/analytics/conftest.py
tests/analytics/fixtures/*.json
tests/analytics/test_*.py
tests/js/admin_analytics.test.js
```

Modified: `app/__init__.py` (model import, blueprint, CLI), `app/scheduler.py` (nightly job), `app/slack/bolt_app.py` (`_delegate_reaction_event`), `app/templates/admin/partials/sidebar.html`, `tests/practices/test_practice_migration_release.py`, `package.json`.

---

# Part 1: data foundation (PR 1)

### Task 0 (orchestrator, not a worker): real-data exports

Runs once on the dev box before Task 8's acceptance test can pass. Nothing here is committed.

**Files:**
- Create: `/workspace/tcsc-trips/.superpowers/analytics-slack-dump/app_practices.json`
- Already present: `chan.json`, `threads.json`, `summer.json`, `summer_threads.json`, `lift_verified.json` in the same folder (saved during brainstorming).

- [ ] **Step 1: Export app-era practices from prod, read-only**

```bash
cd /workspace/tcsc-trips && set -a && source .env && set +a
psql "$PROD_DATABASE_URL" -At -c "
select json_agg(row_to_json(p)) from (
  select pr.id, to_char(pr.date,'YYYY-MM-DD\"T\"HH24:MI:SS') as date, pr.status, pr.is_draft,
         pr.slack_channel_id, pr.slack_message_ts, pr.slack_session_emoji,
         l.name as location_name, l.spot as location_spot,
         coalesce((select json_agg(a.name) from practice_activities_junction j join practice_activities a on a.id=j.activity_id where j.practice_id=pr.id),'[]') as activities,
         coalesce((select json_agg(t.name) from practice_types_junction j join practice_types t on t.id=j.type_id where j.practice_id=pr.id),'[]') as types,
         coalesce((select json_agg(su.slack_uid) from practice_leads pl join slack_users su on su.user_id=pl.user_id where pl.practice_id=pr.id and pl.role='lead'),'[]') as lead_uids,
         coalesce((select json_agg(su.slack_uid) from practice_leads pl join slack_users su on su.user_id=pl.user_id where pl.practice_id=pr.id and pl.role='coach'),'[]') as coach_uids,
         coalesce((select json_agg(x->>'emoji') from json_array_elements(pr.plan_reactions::json) x),'[]') as plan_emoji,
         coalesce((select json_agg(su.slack_uid) from practice_rsvps r join slack_users su on su.user_id=r.user_id where r.practice_id=pr.id and r.status='going'),'[]') as button_rsvp_uids
  from practices pr left join practice_locations l on l.id=pr.location_id
  order by pr.id) p;" > .superpowers/analytics-slack-dump/app_practices.json
python3 -c "import json;d=json.load(open('.superpowers/analytics-slack-dump/app_practices.json'));print(len(d))"
```

Expected: a count around 125 (every `practices` row, drafts included; the builder filters them).

Note: `button_rsvp_uids` contains every `going` RSVP, both reactions and buttons. The builder unions them with reactions, so duplicates collapse.

- [ ] **Step 2: Export location rows (needed to resolve venues in the acceptance test)**

```bash
psql "$PROD_DATABASE_URL" -At -c "select json_agg(row_to_json(l)) from (select id,name,spot,latitude as lat,longitude as lon from practice_locations order by id) l;" > .superpowers/analytics-slack-dump/locations.json
```

---

### Task 1: Models, migration, test harness

**Files:**
- Create: `app/analytics/__init__.py`, `app/analytics/models.py`, `migrations/versions/b8e4d2a9c731_practice_analytics.py`, `requirements-dev.txt`, `tests/analytics/__init__.py`, `tests/analytics/conftest.py`, `tests/analytics/test_models.py`
- Modify: `app/__init__.py` (import models next to the other model imports at the top), `tests/practices/test_practice_migration_release.py:28` (`HEAD_REVISION`)

**Docs to read first:** Flask-Migrate https://flask-migrate.readthedocs.io/, Alembic operations https://alembic.sqlalchemy.org/en/latest/ops.html, PostgreSQL arrays https://www.postgresql.org/docs/current/arrays.html and JSONB https://www.postgresql.org/docs/current/datatype-json.html.

**Interfaces:**
- Produces: `app.analytics.CHANNELS`, `SESSION_CHANNELS`, `SYNC_CHANNELS`; models `SlackArchiveMessage`, `SlackReactionEvent`, `PracticeSession`, `PracticeAttendance`, `WeatherHour`, `AnalyticsCorrection`.

- [ ] **Step 1: Channel constants**

`app/analytics/__init__.py`:

```python
"""Practice analytics: Slack archive, practice lineage, dashboards."""

CHANNELS = {
    "C042G463AQ1": "announcements-practices",
    "C03FKTTHNHW": "announcements-summer",   # archived; import needs the user token
    "C047BRZH1LG": "extra-training-fun",     # archived raw only, never sessions
}
SESSION_CHANNELS = ("C042G463AQ1", "C03FKTTHNHW")
SYNC_CHANNELS = ("C042G463AQ1", "C047BRZH1LG")
```

- [ ] **Step 2: Models**

`app/analytics/models.py`:

```python
"""Analytics tables. Layer 1 (archive) is written by archive.py and
reaction_log.py; layer 2 (sessions, attendance) only by rebuild.py;
weather_hours only by weather.py."""
from datetime import datetime

from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from app.models import db


class SlackArchiveMessage(db.Model):
    __tablename__ = "slack_archive_messages"

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.String(20), nullable=False)
    ts = db.Column(db.String(32), nullable=False)
    thread_ts = db.Column(db.String(32))
    user_id = db.Column(db.String(20))
    bot_id = db.Column(db.String(20))
    subtype = db.Column(db.String(64))
    text = db.Column(db.Text, nullable=False, default="")
    posted_at = db.Column(db.DateTime, nullable=False)
    edited_at = db.Column(db.DateTime)
    deleted_at = db.Column(db.DateTime)
    raw = db.Column(JSONB, nullable=False)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("channel_id", "ts", name="uq_slack_archive_channel_ts"),
        db.Index("ix_slack_archive_thread", "channel_id", "thread_ts"),
        db.Index("ix_slack_archive_posted_at", "posted_at"),
    )


class SlackReactionEvent(db.Model):
    __tablename__ = "slack_reaction_events"

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.String(20), nullable=False)
    message_ts = db.Column(db.String(32), nullable=False)
    emoji = db.Column(db.String(100), nullable=False)
    slack_uid = db.Column(db.String(20), nullable=False)
    action = db.Column(db.String(10), nullable=False)  # added | removed
    event_ts = db.Column(db.String(32))
    received_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("action IN ('added','removed')", name="ck_reaction_event_action"),
        db.Index("ix_reaction_events_message", "channel_id", "message_ts"),
    )


class PracticeSession(db.Model):
    __tablename__ = "practice_sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_key = db.Column(db.String(80), nullable=False, unique=True)
    era = db.Column(db.String(10), nullable=False)          # template | app
    kind = db.Column(db.String(10), nullable=False, default="practice")  # practice | event
    source_message_id = db.Column(db.Integer, db.ForeignKey("slack_archive_messages.id"))
    practice_id = db.Column(db.Integer, db.ForeignKey("practices.id"))
    date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time)
    day_of_week = db.Column(db.String(10), nullable=False)
    season_label = db.Column(db.String(40), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey("practice_locations.id"))
    location_name = db.Column(db.String(255))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    is_indoor = db.Column(db.Boolean, nullable=False, default=False)
    activity = db.Column(db.String(40), nullable=False, default="Other", index=True)
    activities = db.Column(ARRAY(db.String(80)), nullable=False, default=list)
    workout_type = db.Column(db.String(40), nullable=False, default="Other")
    workout_types = db.Column(ARRAY(db.String(80)), nullable=False, default=list)
    title = db.Column(db.Text, nullable=False, default="")
    format = db.Column(db.String(10), nullable=False, default="single")  # single | split | merged
    slot = db.Column(db.String(10))                                      # early | late
    group_key = db.Column(db.String(80), nullable=False)
    rsvp_emoji = db.Column(db.String(100))
    status = db.Column(db.String(10), nullable=False, default="held")  # held | cancelled
    rsvp_count = db.Column(db.Integer, nullable=False, default=0)
    temp_f = db.Column(db.Float)
    feels_like_f = db.Column(db.Float)
    wind_mph = db.Column(db.Float)
    precip_in = db.Column(db.Float)
    snowfall_in = db.Column(db.Float)
    snowfall_prior_24h_in = db.Column(db.Float)
    snow_depth_in = db.Column(db.Float)
    weather_code = db.Column(db.Integer)
    minutes_after_sunset = db.Column(db.Integer)
    flags = db.Column(ARRAY(db.String(40)), nullable=False, default=list)
    needs_review = db.Column(db.Boolean, nullable=False, default=False)
    rebuilt_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    attendance = db.relationship(
        "PracticeAttendance", backref="session", cascade="all, delete-orphan",
        passive_deletes=True)

    __table_args__ = (
        db.CheckConstraint("format IN ('single','split','merged')", name="ck_session_format"),
        db.CheckConstraint("status IN ('held','cancelled')", name="ck_session_status"),
        db.CheckConstraint("kind IN ('practice','event')", name="ck_session_kind"),
    )


class PracticeAttendance(db.Model):
    __tablename__ = "practice_attendance"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True)
    slack_uid = db.Column(db.String(20), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    role = db.Column(db.String(10), nullable=False)    # rsvp | plan | lead | coach
    emoji = db.Column(db.String(100))
    slot = db.Column(db.String(10))                    # early | late
    source = db.Column(db.String(12), nullable=False)  # reaction | button | post_text | app | correction

    __table_args__ = (
        db.UniqueConstraint("session_id", "slack_uid", "role", "emoji",
                            name="uq_attendance_session_uid_role_emoji"),
        db.CheckConstraint("role IN ('rsvp','plan','lead','coach')", name="ck_attendance_role"),
    )


class WeatherHour(db.Model):
    __tablename__ = "weather_hours"

    lat = db.Column(db.Numeric(6, 2), primary_key=True)
    lon = db.Column(db.Numeric(6, 2), primary_key=True)
    hour_local = db.Column(db.DateTime, primary_key=True)  # naive Central
    temp_f = db.Column(db.Float)
    feels_like_f = db.Column(db.Float)
    precip_in = db.Column(db.Float)
    snowfall_in = db.Column(db.Float)
    snow_depth_in = db.Column(db.Float)
    wind_mph = db.Column(db.Float)
    weather_code = db.Column(db.Integer)
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class AnalyticsCorrection(db.Model):
    """One fix to the lineage, keyed by session_key or "<channel>:<ts>" (whole post).
    Data, not config: lives here, never in the repo."""
    __tablename__ = "analytics_corrections"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), nullable=False, unique=True)
    fields = db.Column(JSONB, nullable=False)          # validated by corrections.validate_correction
    note = db.Column(db.Text, nullable=False)          # why; required
    author = db.Column(db.String(80), nullable=False)  # "claude-fixer", "rob", ...
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow)
```

Note the `emoji` column in the unique constraint is nullable; Postgres treats NULLs as distinct, so the lineage builder must dedupe `(session, uid, role, emoji)` itself before insert (Task 8 does).

- [ ] **Step 3: Register the models**

In `app/__init__.py`, next to the existing `from .events.models import (...)` and `from .newsletter.models import (...)` imports at the top, add:

```python
from .analytics.models import (  # noqa: F401  (Alembic metadata registration)
    PracticeAttendance,
    PracticeSession,
    SlackArchiveMessage,
    SlackReactionEvent,
    WeatherHour,
    AnalyticsCorrection,
)
```

- [ ] **Step 4: Write the migration by hand**

Check the current head first: `grep -l "^revision" migrations/versions/*.py | xargs grep -h "^down_revision\|^revision"`, or run `flask db heads` with `TCSC_MIGRATION_ONLY=1`. Use the head as `down_revision` (it was `6c2f8a4d9e10` when this plan was written).

`migrations/versions/b8e4d2a9c731_practice_analytics.py`: `op.create_table` for all six tables with exactly the columns, constraints and indexes from Step 2 (use `postgresql.JSONB`, `postgresql.ARRAY(sa.String(n))`, `server_default=sa.text("'{}'")` for the two array columns and `sa.false()` for booleans). The `practice_attendance.session_id` FK uses `ondelete="CASCADE"`. `downgrade()` drops the tables in reverse dependency order: corrections, attendance, sessions, weather_hours, reaction events, archive messages.

- [ ] **Step 5: Bump the pinned head**

`tests/practices/test_practice_migration_release.py:28`: `HEAD_REVISION = "b8e4d2a9c731"`.

- [ ] **Step 6: Test dependencies**

`requirements-dev.txt`:

```
-r requirements.txt
pytest>=8
jsonschema>=4.23
vl-convert-python>=1.7
```

Install: `pip install -r requirements-dev.txt` (in the worktree's venv; see CLAUDE.md "Development Setup").

- [ ] **Step 7: Test harness**

`tests/analytics/conftest.py`:

```python
"""Fixtures for tests/analytics.

Run against the scratch DB, never the shared dev DB:
    DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/analytics
DB tests roll back; nothing here commits. The repo is public: fixtures are
hand-written and contain no real Slack content or member IDs.
"""
import json
import os
from pathlib import Path

import pytest

from app import create_app
from app.models import db
from tests._db_guard import LOCAL_TEST_DB

FIXTURES = Path(__file__).parent / "fixtures"
DUMP_DIR = Path(os.environ.get(
    "TCSC_ANALYTICS_DUMP_DIR",
    "/workspace/tcsc-trips/.superpowers/analytics-slack-dump"))


@pytest.fixture
def app():
    os.environ.setdefault("TCSC_MIGRATION_ONLY", "1")  # no scheduler in tests
    application = create_app()
    application.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", LOCAL_TEST_DB),
    )
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        try:
            yield db.session
        finally:
            db.session.rollback()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as sess:
        sess["user"] = {"email": "tester@twincitiesskiclub.org", "name": "Tester"}
    return client


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())
```

- [ ] **Step 8: Write the failing schema test**

`tests/analytics/test_models.py`:

```python
from sqlalchemy import inspect

from app.models import db


def test_analytics_tables_exist_with_key_columns(db_session):
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    assert {"slack_archive_messages", "slack_reaction_events", "practice_sessions",
            "practice_attendance", "weather_hours", "analytics_corrections"} <= tables
    cols = {c["name"] for c in insp.get_columns("practice_sessions")}
    assert {"session_key", "format", "slot", "rsvp_count", "temp_f",
            "minutes_after_sunset", "flags", "needs_review"} <= cols
    att = {c["name"] for c in insp.get_columns("practice_attendance")}
    assert {"slack_uid", "role", "emoji", "slot", "source"} <= att


def test_attendance_rows_cascade_with_session(db_session):
    from app.analytics.models import PracticeAttendance, PracticeSession
    from datetime import date
    s = PracticeSession(session_key="test:cascade", era="template", date=date(2099, 1, 1),
                        day_of_week="Thursday", season_label="2098 Fall/Winter",
                        group_key="test:cascade")
    db_session.add(s)
    db_session.flush()
    db_session.add(PracticeAttendance(session_id=s.id, slack_uid="UFAKE0001",
                                      role="rsvp", emoji="six", source="reaction"))
    db_session.flush()
    db_session.delete(s)
    db_session.flush()
    assert PracticeAttendance.query.filter_by(slack_uid="UFAKE0001").count() == 0
```

- [ ] **Step 9: Run it, expect failure** (tables missing)

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/analytics/test_models.py -v`
Expected: FAIL, `slack_archive_messages` not in tables.

- [ ] **Step 10: Migrate the scratch DB and rerun**

```bash
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test TCSC_MIGRATION_ONLY=1 flask db upgrade
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/analytics/test_models.py tests/practices/test_practice_migration_release.py -v
```

Expected: PASS. Then run `flask db downgrade -1` and `flask db upgrade` again against the scratch DB to prove the downgrade works.

- [ ] **Step 11: Commit**

```bash
git add app/analytics/__init__.py app/analytics/models.py app/__init__.py migrations/versions/b8e4d2a9c731_practice_analytics.py requirements-dev.txt tests/analytics tests/practices/test_practice_migration_release.py
git commit -m "feat(analytics): archive, lineage, weather and corrections tables"
```

---

### Task 2: Drafts and seasons (pure)

**Files:**
- Create: `app/analytics/drafts.py`, `app/analytics/seasons.py`, `tests/analytics/test_seasons.py`

**Interfaces:**
- Produces: `ArchivedMessage`, `AppPractice`, `LocationRef`, `SessionDraft`, `AttendanceDraft`, `LineageResult` (dataclasses below); `season_label(d: date, seasons: list[SeasonRef]) -> str`, `SeasonRef`.

- [ ] **Step 1: Dataclasses**

`app/analytics/drafts.py`:

```python
"""Plain data passed between the pure lineage functions. No DB access here."""
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional


@dataclass(frozen=True)
class ArchivedMessage:
    channel_id: str
    ts: str
    raw: dict                      # Slack message payload as stored in slack_archive_messages.raw
    replies: tuple = ()            # raw payloads of thread replies, oldest first
    deleted: bool = False
    archive_id: Optional[int] = None


@dataclass(frozen=True)
class AppPractice:
    id: int
    date: datetime                 # naive Central, as stored in practices.date
    status: str                    # scheduled | cancelled | ...
    is_draft: bool
    slack_channel_id: Optional[str]
    slack_message_ts: Optional[str]
    slack_session_emoji: Optional[str]
    location_name: Optional[str]
    location_spot: Optional[str]
    activities: tuple = ()
    types: tuple = ()
    lead_uids: tuple = ()
    coach_uids: tuple = ()
    plan_emoji: tuple = ()
    button_rsvp_uids: tuple = ()


@dataclass(frozen=True)
class LocationRef:
    id: int
    name: str
    spot: Optional[str]
    lat: Optional[float]
    lon: Optional[float]


@dataclass(frozen=True)
class SeasonRef:
    name: str
    start_date: date
    end_date: date


@dataclass
class SessionDraft:
    session_key: str
    group_key: str
    era: str                       # template | app
    date: date
    start_time: Optional[time]
    title: str
    venue_raw: Optional[str] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    is_indoor: bool = False
    activities: list = field(default_factory=list)
    workout_types: list = field(default_factory=list)
    activity: str = "Other"
    workout_type: str = "Other"
    kind: str = "practice"
    format: str = "single"
    slot: Optional[str] = None
    rsvp_emoji: Optional[str] = None
    status: str = "held"
    channel_id: Optional[str] = None
    source_ts: Optional[str] = None
    source_archive_id: Optional[int] = None
    practice_id: Optional[int] = None
    lead_uids: list = field(default_factory=list)
    coach_uids: list = field(default_factory=list)
    plan_emoji: list = field(default_factory=list)
    flags: list = field(default_factory=list)


@dataclass(frozen=True)
class AttendanceDraft:
    session_key: str
    slack_uid: str
    role: str                      # rsvp | plan | lead | coach
    emoji: Optional[str]
    slot: Optional[str]
    source: str                    # reaction | button | post_text | app | correction


@dataclass
class LineageResult:
    sessions: list                 # SessionDraft with season_label/day_of_week filled by lineage
    attendance: list               # AttendanceDraft
    possible_misses: list          # "channel:ts" of reacted messages that produced no session
```

- [ ] **Step 2: Failing season tests**

`tests/analytics/test_seasons.py`:

```python
from datetime import date

from app.analytics.drafts import SeasonRef
from app.analytics.seasons import season_label

SEASONS = [SeasonRef("2025 Fall/Winter", date(2025, 9, 11), date(2026, 3, 19))]


def test_uses_seasons_table_when_date_inside():
    assert season_label(date(2025, 12, 3), SEASONS) == "2025 Fall/Winter"


def test_computed_label_for_winter_months():
    assert season_label(date(2023, 1, 31), []) == "2022 Fall/Winter"
    assert season_label(date(2022, 10, 25), []) == "2022 Fall/Winter"
    assert season_label(date(2024, 4, 2), []) == "2023 Fall/Winter"


def test_computed_label_for_summer_months():
    assert season_label(date(2023, 6, 13), []) == "2023 Spring/Summer"
    assert season_label(date(2025, 9, 5), []) == "2025 Fall/Winter"  # Sep counts as Fall/Winter


def test_gap_between_table_seasons_falls_back_to_rule():
    # 2025-09-05 is before the 2025 Fall/Winter season starts on 9/11
    assert season_label(date(2025, 9, 5), SEASONS) == "2025 Fall/Winter"
```

- [ ] **Step 3: Run, expect ImportError.** `pytest tests/analytics/test_seasons.py -v`

- [ ] **Step 4: Implement**

`app/analytics/seasons.py`:

```python
"""Season labels for any practice date, 2022 onward."""
from datetime import date


def season_label(d: date, seasons) -> str:
    for s in seasons:
        if s.start_date <= d <= s.end_date:
            return s.name
    if 5 <= d.month <= 8:
        return f"{d.year} Spring/Summer"
    start_year = d.year if d.month >= 9 else d.year - 1
    return f"{start_year} Fall/Winter"
```

- [ ] **Step 5: Run, expect PASS.** Then commit:

```bash
git add app/analytics/drafts.py app/analytics/seasons.py tests/analytics/test_seasons.py
git commit -m "feat(analytics): lineage dataclasses and season labels"
```

---

### Task 3: History config (YAML) and resolution

**Files:**
- Create: `config/practice_history.yaml`, `app/analytics/history_config.py`, `tests/analytics/test_history_config.py`

**Docs to read first:** PyYAML `safe_load` https://pyyaml.org/wiki/PyYAMLDocumentation.

**Interfaces:**
- Consumes: `LocationRef` (Task 2).
- Produces:
  - `HistoryConfig` dataclass with fields `excluded_slack_uids: frozenset`, `coach_emoji: frozenset`, `default_lat: float`, `default_lon: float`, `venues: list[dict]`, `activity_rules: list[dict]`, `type_rules: list[dict]`, `activity_buckets: dict`, `workout_buckets: list[tuple[str, list[str]]]`, `event_keywords: list[str]`, `indoor_locations: list[str]`, `capacity_lines: list[dict]`
  - `load_history_config(path: str | Path = DEFAULT_PATH) -> HistoryConfig` (raises `HistoryConfigError` on invalid content)
  - `resolve_venue(raw: str | None, cfg, locations: list[LocationRef]) -> dict` returning `{"location_id", "location_name", "lat", "lon", "is_indoor", "matched": bool, "rule_kind": "location"|"name"|None}`; parsers add `unknown_location_row` when `rule_kind == "location"` and `location_id is None`
  - `classify_title(title: str, cfg) -> dict` returning `{"activities": list, "workout_types": list, "kind": "practice"|"event", "matched": bool}`
  - `activity_bucket(activities: list, cfg) -> str`, `workout_bucket(types: list, cfg) -> str`
  - `base_emoji(name: str) -> str` (strips `::skin-tone-N`)

- [ ] **Step 1: Write the YAML**

`config/practice_history.yaml`:

```yaml
# Practice lineage configuration. Read by app/analytics/history_config.py at
# every rebuild. An invalid file fails the rebuild and leaves the previous
# tables in place. PUBLIC REPO: never put member names or member Slack IDs here.

excluded_slack_uids:
  - U06FYPUNQCU   # TCSC app bot, reacts to its own posts with every RSVP emoji
  - U04C46UJXAM   # Zapier-linked account that posted 2022-2025 templates

# Coach face emoji are names, so they live in the DB: AppConfig key
# "analytics_coach_emoji" (JSON list). A coach_emoji key here is an error.

default_location: {lat: 44.9778, lon: -93.2650}   # central Minneapolis, used when a venue is unknown

indoor_locations: ["Balance Fitness Studio", "Royals Athletic Center"]

# Raw venue text (lowercased substring match, first rule wins) to a location.
# `location` is looked up by practice_locations.name (+ spot); row ids differ
# between databases, so never use ids here.
venues:
  - match: ["balance fitness"]
    location: {name: "Balance Fitness Studio"}
  - match: ["bassett creek"]
    location: {name: "Theodore Wirth", spot: "Bassett Creek Playground"}
  - match: ["xerxes", "theodore wirth trails", "wirth trails"]
    location: {name: "Theodore Wirth", spot: "Xerxes Field"}
  - match: ["the trailhead", "trailhead", "wirth chalet", "chalet @ theodore wirth", "theodore wirth chalet"]
    location: {name: "Theodore Wirth", spot: "Trailhead Bridge"}
  - match: ["theodore wirth", "wirth"]
    location: {name: "Theodore Wirth", spot: "Xerxes Field"}
  - match: ["richardson nature"]
    location: {name: "Hyland - Richardson Nature Center"}
  - match: ["hyland park - visitor", "hyland - visitor"]
    location: {name: "Hyland", spot: "Visitor Center"}
  - match: ["hyland", "jan's place", "jan’s place"]
    location: {name: "Hyland", spot: "Jan's Place"}
  - match: ["elm creek"]
    location: {name: "Elm Creek", spot: "Chalet"}
  - match: ["french park"]
    location: {name: "French Park", spot: "Visitor Center"}
  - match: ["brackett"]
    location: {name: "Brackett Park", spot: "Recreation Center"}
  - match: ["royals athletic"]
    location: {name: "Hopkins Highschool", spot: "Royals Athletic Center"}
  - match: ["bohemian flats"]
    location: {name: "Bohemian Flats", spot: "Parking Lot"}
  - match: ["fort snelling"]
    location: {name: "Fort Snelling", spot: "Whiskey the Horse Grave"}
  - match: ["battle creek"]
    location: {name: "Battle Creek", spot: "Recreation Center"}
  - match: ["minnehaha"]
    location: {name: "Minnehaha Park", spot: "Pavillion 1"}
  - match: ["cedar lake"]
    location: {name: "Cedar Lake", spot: "Point Beach Parking Lot"}
  - match: ["murray field"]
    location: {name: "Murray Field", spot: "Track"}
  - match: ["bde maka ska", "thomas beach"]
    location: {name: "Bde Maka Ska", spot: "Thomas Beach"}
  - match: ["carver lake"]
    location: {name: "Carver Lake Preserve"}
  - match: ["afton"]
    location: {name: "Afton", spot: "Valley Creek Trail"}
  - match: ["brookview"]
    location: {name: "Brookview Park", spot: "Large Picnic Shelter"}
  - match: ["beards plaisance"]
    name: Beards Plaisance
    lat: 44.9215
    lon: -93.3100
  - match: ["punch pizza", "greenway behind"]
    name: Midtown Greenway
    lat: 44.9486
    lon: -93.2984
  - match: ["monument on east river"]
    name: East River Road Monument
    lat: 44.9570
    lon: -93.2090
  - match: ["house", "residence"]
    name: Member's home          # private homes, never store the address or owner

# Title keywords to canonical practice_activities names. Lowercased substring
# match, first rule wins. default_types apply when no type rule matches.
activity_rules:
  - match: ["multi-sport", "multisport", "multi sport", "run / rollerski / ride"]
    activities: [Run, Skate/Classic Rollerski, Bike]
  - match: ["rollerski (skate/classic) or pole hike", "or pole hike"]
    activities: [Skate/Classic Rollerski, Pole Hike]
  - match: ["classic rollerski"]
    activities: [Classic Rollerski]
  - match: ["skate rollerski"]
    activities: [Skate Rollerski]
  - match: ["rollerski", "roller-ski", "roller ski"]
    activities: [Skate/Classic Rollerski]
  - match: ["strength", "lift"]
    activities: [Strength]
    default_types: [Circuit]
  - match: ["pole hike / pole run", "pole hike or pole jog", "pole hike, pole run"]
    activities: ["Pole Hike, Pole Run"]
  - match: ["pole run", "run w/ poles", "running w/ poles", "bounding"]
    activities: [Pole Run]
  - match: ["pole hike"]
    activities: [Pole Hike]
  - match: ["skate/classic", "skate or classic", "either technique", "hamster wheel", "natural trails", "casual group ski", "snowy ski", "chill skate"]
    activities: [Skate/Classic Ski]
  - match: ["classic"]
    activities: [Classic Ski]
  - match: ["skate"]
    activities: [Skate Ski]
  - match: ["orienteering"]
    activities: [Orienteering]
  - match: ["trail run", "run/hike", "jog", "run"]
    activities: [Run]
  - match: ["hike"]
    activities: [Hike]
  - match: ["bike", "ride"]
    activities: [Bike]
  - match: ["relay", "heptathlon", "scavenger", "ultimate", "game"]
    activities: [Game]
  - match: ["kickoff", "kick-off", "potluck"]
    activities: [Kickoff]

# All matching rules contribute (not first-wins).
type_rules:
  - match: ["vo2"]
    types: ["Intervals (VO2 Max)"]
  - match: ["threshold"]
    types: ["Intervals (Threshold)"]
  - match: ["tempo"]
    types: ["Intervals (Tempo)"]
  - match: ["interval", "techniquetervals", "repeats", "800s"]
    types: [Intervals]
  - match: ["circuit"]
    types: [Circuit]
  - match: ["technique"]
    types: [Technique]
  - match: ["endurance", "meetup", "easy", "chill", "casual"]
    types: [Endurance]
  - match: ["time trial", " tt", "bog tt"]
    types: [Time Trial]
  - match: ["benchmark"]
    types: [Benchmark]
  - match: ["relay"]
    types: [Relays]
  - match: ["game", "ultimate", "frisbee", "scavenger", "capture the flag"]
    types: [Non-structured]
  - match: ["kickoff", "potluck"]
    types: [Kickoff]

activity_buckets:
  Strength: Strength
  Run: Run
  Pole Run: Run
  Pole Hike: Run
  "Pole Hike, Pole Run": Run
  Hike: Run
  Skate Ski: Ski
  Classic Ski: Ski
  Skate/Classic Ski: Ski
  Skate Rollerski: Rollerski
  Classic Rollerski: Rollerski
  Skate/Classic Rollerski: Rollerski
  Bike: Bike
  Mountain Bike: Bike
  Orienteering: Other
  Game: Other
  Dryland Triathlon: Other
  Kickoff: Event
  Season: Event

# First bucket whose list contains any of the session's types wins.
workout_buckets:
  - [Intervals, ["Intervals", "Intervals (VO2 Max)", "Intervals (Threshold)", "Intervals (Tempo)"]]
  - [Time Trial, ["Time Trial", "Benchmark"]]
  - [Technique, ["Technique"]]
  - [Circuit, ["Circuit"]]
  - [Games, ["Relays", "Non-structured"]]
  - [Endurance, ["Endurance", "Active Recovery"]]
  - [Event, ["Kickoff"]]

# Titles containing these words become kind=event (excluded from practice averages).
event_keywords: ["kickoff", "kick-off", "potluck", "board meeting", "leadership meeting", "social event", "new member event"]

capacity_lines:
  - {value: 27, label: "2025 split rule", from: 2025-05-01}
  - {value: 30, label: "Dec 2025 cap", from: 2025-12-01, to: 2026-03-31}
  - {value: 35, label: "One session (5x7)", from: 2026-08-01}

# Per-post corrections are data and live in the analytics_corrections table
# (see app/analytics/corrections.py), never in this file.
```

- [ ] **Step 2: Failing tests**

`tests/analytics/test_history_config.py`:

```python
import textwrap

import pytest

from app.analytics.drafts import LocationRef
from app.analytics.history_config import (
    HistoryConfigError, activity_bucket, base_emoji, classify_title,
    load_history_config, resolve_venue, workout_bucket)

LOCS = [
    LocationRef(34, "Theodore Wirth", "Xerxes Field", 44.98, -93.31),
    LocationRef(36, "Theodore Wirth", "Trailhead Bridge", 44.99, -93.32),
    LocationRef(38, "Balance Fitness Studio", None, 44.95, -93.28),
    LocationRef(32, "Hyland", "Jan's Place", 44.82, -93.36),
]


@pytest.fixture(scope="module")
def cfg():
    return load_history_config()


def test_real_config_loads(cfg):
    assert "U06FYPUNQCU" in cfg.excluded_slack_uids
    assert cfg.coach_emoji == frozenset()   # filled from AppConfig at rebuild
    assert cfg.capacity_lines[0]["value"] == 27


def test_venue_by_name_and_spot(cfg):
    v = resolve_venue("The Trailhead @ Wirth", cfg, LOCS)
    assert (v["location_id"], v["matched"]) == (36, True)
    v = resolve_venue("Theodore Wirth Trails", cfg, LOCS)
    assert v["location_id"] == 34


def test_indoor_and_unknown_venue(cfg):
    assert resolve_venue("Balance Fitness Studio", cfg, LOCS)["is_indoor"] is True
    v = resolve_venue("Somewhere New", cfg, LOCS)
    assert v["matched"] is False and v["location_id"] is None
    assert (v["lat"], v["lon"]) == (44.9778, -93.2650)


def test_config_only_venue_has_own_coordinates(cfg):
    v = resolve_venue("Beards Plaisance", cfg, LOCS)
    assert v["location_id"] is None and v["location_name"] == "Beards Plaisance"
    assert v["lat"] == pytest.approx(44.9215) and v["matched"] is True


def test_private_home_never_keeps_raw_text(cfg):
    v = resolve_venue("Somebody's House", cfg, LOCS)
    assert v["location_name"] == "Member's home"


@pytest.mark.parametrize("title,acts,types", [
    ("Strength Circuit", ["Strength"], ["Circuit"]),
    ("Strength", ["Strength"], ["Circuit"]),
    ("Skate or Classic Intervals", ["Skate/Classic Ski"], ["Intervals"]),
    ("Run w/ Poles - Intervals", ["Pole Run"], ["Intervals"]),
    ("Classic Ski - Technique", ["Classic Ski"], ["Technique"]),
    ("Multi-Sport (Rollerski, Run, Bike)", ["Run", "Skate/Classic Rollerski", "Bike"], []),
])
def test_classify_title(cfg, title, acts, types):
    r = classify_title(title, cfg)
    assert r["activities"] == acts and r["workout_types"] == types and r["matched"]


def test_event_titles_and_unmatched(cfg):
    assert classify_title("Season Kickoff + Potluck", cfg)["kind"] == "event"
    r = classify_title("Super Secret Surprise", cfg)
    assert r["matched"] is False and r["activities"] == []


def test_buckets(cfg):
    assert activity_bucket(["Pole Run"], cfg) == "Run"
    assert activity_bucket(["Run", "Bike"], cfg) == "Multisport"
    assert activity_bucket([], cfg) == "Other"
    assert workout_bucket(["Technique", "Intervals"], cfg) == "Intervals"
    assert workout_bucket([], cfg) == "Other"


def test_base_emoji():
    assert base_emoji("older_adult::skin-tone-4") == "older_adult"
    assert base_emoji("six") == "six"


def test_invalid_config_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(textwrap.dedent("""
        excluded_slack_uids: not-a-list
    """))
    with pytest.raises(HistoryConfigError):
        load_history_config(p)
```

- [ ] **Step 3: Run, expect ImportError.**

- [ ] **Step 4: Implement `app/analytics/history_config.py`**

Requirements (write the code to satisfy the tests and these rules):
- `DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "practice_history.yaml"`.
- `load_history_config` uses `yaml.safe_load`. Validate types: lists where lists are expected, each venue has `match` (non-empty list of strings) and either `location: {name, spot?}` or `name` (with optional `lat`/`lon`). A top-level `corrections` key is an error (corrections belong in the DB). Any violation raises `HistoryConfigError(message naming the offending key)`.
- Matching lowercases the raw text and normalizes the curly apostrophe `’` to `'` before substring checks.
- `resolve_venue`: first venue rule whose any `match` substring is in the text. For `location:` rules, find the `LocationRef` with equal `name` (and equal `spot` when the rule gives one); if the rule names a location that is not in `locations`, return `matched=True`, `location_id=None`, `location_name=<rule name>`, default coordinates, and the caller flags `unknown_location_row`. For `name:` rules, return the rule's name and coordinates (default coordinates when absent). No rule: `matched=False`, `location_name=None`, default coordinates. `is_indoor` is true when the resolved name or spot appears in `indoor_locations`.
- `classify_title`: first matching `activity_rules` entry gives `activities`; all matching `type_rules` entries contribute `types`, deduped in rule order; if none matched and the activity rule has `default_types`, use them. `kind` is `"event"` when any `event_keywords` substring is in the title. `matched` is true when an activity rule matched.
- `activity_bucket`: map each activity through `activity_buckets` (unknown → `"Other"`); one distinct bucket → it; several → `"Multisport"`; none → `"Other"`.
- `workout_bucket`: first `workout_buckets` entry that intersects the types; none → `"Other"`.

- [ ] **Step 5: Run, expect PASS.** Commit:

```bash
git add config/practice_history.yaml app/analytics/history_config.py tests/analytics/test_history_config.py
git commit -m "feat(analytics): practice history config and venue/title resolution"
```

---

### Task 4: Slack archive import and sync

**Files:**
- Create: `app/analytics/archive.py`, `tests/analytics/test_archive.py`

**Docs to read first:** https://docs.slack.dev/reference/methods/conversations.history, https://docs.slack.dev/reference/methods/conversations.replies, https://docs.slack.dev/reference/methods/reactions.get, https://docs.slack.dev/apis/web-api/rate-limits, slack_sdk retry handlers https://tools.slack.dev/python-slack-sdk/web#retryhandler. The existing clients are `get_slack_client()` and `get_slack_user_client()` in `app/slack/client.py`; both already retry on 429.

**Interfaces:**
- Consumes: `SlackArchiveMessage` (Task 1).
- Produces:
  - `import_channel(client, channel_id: str, *, oldest: float | None = None) -> dict` returning `{"messages": int, "replies": int, "reactions_refetched": int, "seen": set[str]}` where `seen` holds every ts returned (parents and replies).
  - `sync_recent(client, channel_ids=SYNC_CHANNELS, *, days: int = 21, now: datetime | None = None) -> dict` per-channel stats; also sets `deleted_at` on archived rows in the window that Slack no longer returns.
  - `upsert_message(channel_id: str, raw: dict) -> SlackArchiveMessage` (no commit).

The functions take a `client` so tests pass a fake. Real callers pass `get_slack_client()` or `get_slack_user_client()`. The caller commits.

- [ ] **Step 1: Failing tests with a fake client**

`tests/analytics/test_archive.py`:

```python
from datetime import datetime

from app.analytics.archive import import_channel, sync_recent, upsert_message
from app.analytics.models import SlackArchiveMessage

CH = "CTESTARCH1"


class FakeSlack:
    """Serves conversations.history/replies/reactions.get from dicts."""

    def __init__(self, history, replies=None, full_reactions=None):
        self.history = history            # list of raw messages, newest first
        self.replies = replies or {}      # parent ts -> list of raw replies (parent first, like Slack)
        self.full_reactions = full_reactions or {}
        self.calls = []

    def conversations_history(self, channel, limit=200, cursor=None, oldest=None, **_):
        self.calls.append(("history", cursor, oldest))
        msgs = [m for m in self.history if oldest is None or float(m["ts"]) >= float(oldest)]
        if cursor is None and len(msgs) > 1:   # force one pagination hop
            return {"ok": True, "messages": msgs[:1], "has_more": True,
                    "response_metadata": {"next_cursor": "page2"}}
        start = 1 if cursor == "page2" else 0
        return {"ok": True, "messages": msgs[start:], "has_more": False,
                "response_metadata": {"next_cursor": ""}}

    def conversations_replies(self, channel, ts, limit=200, cursor=None, **_):
        self.calls.append(("replies", ts))
        return {"ok": True, "messages": self.replies.get(ts, []),
                "response_metadata": {"next_cursor": ""}}

    def reactions_get(self, channel, timestamp, full=True, **_):
        self.calls.append(("reactions", timestamp))
        return {"ok": True, "message": {"ts": timestamp,
                                        "reactions": self.full_reactions[timestamp]}}


def _msg(ts, text="hello", **extra):
    return {"type": "message", "ts": ts, "user": "UFAKE0001", "text": text, **extra}


def _rows():
    return {m.ts: m for m in SlackArchiveMessage.query.filter_by(channel_id=CH).all()}


def test_import_pages_threads_and_truncated_reactions(db_session):
    big = [{"name": "white_check_mark", "count": 3, "users": ["UFAKE0001", "UFAKE0002"]}]
    full = [{"name": "white_check_mark", "count": 3,
             "users": ["UFAKE0001", "UFAKE0002", "UFAKE0003"]}]
    parent = _msg("1700000100.000100", reply_count=1, thread_ts="1700000100.000100", reactions=big)
    reply = _msg("1700000200.000200", text="merging tonight", thread_ts="1700000100.000100")
    client = FakeSlack([_msg("1700000300.000300"), parent],
                       replies={parent["ts"]: [parent, reply]},
                       full_reactions={parent["ts"]: full})
    stats = import_channel(client, CH)
    rows = _rows()
    assert stats["messages"] == 2 and stats["replies"] == 1 and stats["reactions_refetched"] == 1
    assert set(rows) == {"1700000100.000100", "1700000200.000200", "1700000300.000300"}
    assert rows["1700000200.000200"].thread_ts == "1700000100.000100"
    users = rows["1700000100.000100"].raw["reactions"][0]["users"]
    assert users == ["UFAKE0001", "UFAKE0002", "UFAKE0003"]
    assert rows["1700000100.000100"].posted_at == datetime.utcfromtimestamp(1700000100.0001)


def test_import_is_idempotent(db_session):
    client = FakeSlack([_msg("1700000400.000400")])
    import_channel(client, CH)
    import_channel(client, CH)
    assert SlackArchiveMessage.query.filter_by(channel_id=CH, ts="1700000400.000400").count() == 1


def test_sync_marks_deleted_and_updates_edits(db_session):
    now = datetime(2099, 1, 22, 12)
    t_keep, t_gone = "4072435200.000100", "4072435300.000200"   # 2099-01-20-ish
    upsert_message(CH, _msg(t_keep, text="old text"))
    upsert_message(CH, _msg(t_gone))
    db_session.flush()
    edited = _msg(t_keep, text="new text", edited={"ts": "4072435400.000000"})
    client = FakeSlack([edited])
    sync_recent(client, (CH,), days=21, now=now)
    rows = _rows()
    assert rows[t_keep].text == "new text" and rows[t_keep].edited_at is not None
    assert rows[t_gone].deleted_at is not None
    assert rows[t_keep].deleted_at is None
```

- [ ] **Step 2: Run, expect ImportError.**

- [ ] **Step 3: Implement `app/analytics/archive.py`**

```python
"""Layer 1: copy Slack channels into slack_archive_messages.

Callers commit. Functions take a slack_sdk-like client so tests can pass a
fake; production passes get_slack_client() (bot) or get_slack_user_client()
(user token, needed only for the archived #announcements-summer)."""
import logging
from datetime import datetime, timedelta

from sqlalchemy.dialects.postgresql import insert

from app.analytics import SYNC_CHANNELS
from app.analytics.models import SlackArchiveMessage
from app.models import db

logger = logging.getLogger(__name__)


def _utc(ts):
    return datetime.utcfromtimestamp(float(ts))


def upsert_message(channel_id, raw):
    edited = raw.get("edited") or {}
    values = dict(
        channel_id=channel_id, ts=raw["ts"], thread_ts=raw.get("thread_ts"),
        user_id=raw.get("user"), bot_id=raw.get("bot_id"), subtype=raw.get("subtype"),
        text=raw.get("text") or "", posted_at=_utc(raw["ts"]),
        edited_at=_utc(edited["ts"]) if edited.get("ts") else None,
        deleted_at=None, raw=raw, synced_at=datetime.utcnow())
    stmt = insert(SlackArchiveMessage).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_slack_archive_channel_ts",
        set_={k: stmt.excluded[k] for k in values if k not in ("channel_id", "ts")})
    db.session.execute(stmt)


def _complete_reactions(client, channel_id, raw):
    """conversations.history caps each reaction's users list; refetch when short."""
    reactions = raw.get("reactions") or []
    if not any(r.get("count", 0) > len(r.get("users", [])) for r in reactions):
        return raw, False
    resp = client.reactions_get(channel=channel_id, timestamp=raw["ts"], full=True)
    full = (resp.get("message") or {}).get("reactions") or reactions
    return {**raw, "reactions": full}, True


def _paginate(call, key="messages", **kwargs):
    cursor = None
    while True:
        resp = call(cursor=cursor, limit=200, **kwargs)
        yield from resp.get(key) or []
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return


def import_channel(client, channel_id, *, oldest=None):
    stats = {"messages": 0, "replies": 0, "reactions_refetched": 0, "seen": set()}
    kwargs = {"channel": channel_id}
    if oldest is not None:
        kwargs["oldest"] = str(oldest)
    for raw in _paginate(client.conversations_history, **kwargs):
        raw, refetched = _complete_reactions(client, channel_id, raw)
        upsert_message(channel_id, raw)
        stats["messages"] += 1
        stats["reactions_refetched"] += refetched
        stats["seen"].add(raw["ts"])
        if raw.get("reply_count"):
            for reply in _paginate(client.conversations_replies, channel=channel_id, ts=raw["ts"]):
                if reply["ts"] == raw["ts"]:
                    continue
                reply, refetched = _complete_reactions(client, channel_id, reply)
                upsert_message(channel_id, reply)
                stats["replies"] += 1
                stats["reactions_refetched"] += refetched
                stats["seen"].add(reply["ts"])
    return stats


def sync_recent(client, channel_ids=SYNC_CHANNELS, *, days=21, now=None):
    now = now or datetime.utcnow()
    since = now - timedelta(days=days)
    out = {}
    for channel_id in channel_ids:
        stats = import_channel(client, channel_id,
                               oldest=(since - datetime(1970, 1, 1)).total_seconds())
        # Anything archived in the window that Slack no longer returns was deleted.
        # Only top-level messages and replies of threads we re-fetched are judged.
        stale = SlackArchiveMessage.query.filter(
            SlackArchiveMessage.channel_id == channel_id,
            SlackArchiveMessage.posted_at >= since,
            SlackArchiveMessage.deleted_at.is_(None),
            ~SlackArchiveMessage.ts.in_(stats["seen"] or {""}),
        ).all()
        for row in stale:
            if row.thread_ts and row.thread_ts != row.ts and row.thread_ts not in stats["seen"]:
                continue
            row.deleted_at = datetime.utcnow()
        stats["deleted"] = len(stale)
        out[channel_id] = {k: v for k, v in stats.items() if k != "seen"}
        logger.info("analytics sync %s: %s", channel_id, out[channel_id])
    return out
```

`since` is naive UTC, so the epoch is computed by subtraction; `since.timestamp()` would wrongly apply the container's local zone.

- [ ] **Step 4: Run, expect PASS.** Fix until green.

- [ ] **Step 5: Commit**

```bash
git add app/analytics/archive.py tests/analytics/test_archive.py
git commit -m "feat(analytics): Slack channel import and 21-day sync"
```

---

### Task 5: Reaction event log

**Files:**
- Create: `app/analytics/reaction_log.py`, `tests/analytics/test_reaction_log.py`
- Modify: `app/slack/bolt_app.py:3334-3348` (`_delegate_reaction_event`)

**Docs to read first:** https://docs.slack.dev/reference/events/reaction_added, https://docs.slack.dev/reference/events/reaction_removed.

**Interfaces:**
- Produces: `record_reaction_event(*, channel, message_ts, emoji, slack_uid, removed, event_ts=None, commit=True) -> bool`. Never raises. Returns False for channels outside `CHANNELS`.

- [ ] **Step 1: Failing tests**

`tests/analytics/test_reaction_log.py`:

```python
from unittest.mock import patch

from app.analytics.models import SlackReactionEvent
from app.analytics.reaction_log import record_reaction_event
import app.slack.bolt_app as bolt_module


def test_records_add_and_remove_for_archived_channel(db_session):
    assert record_reaction_event(channel="C042G463AQ1", message_ts="4072435200.000100",
                                 emoji="six", slack_uid="UFAKE0009", removed=False,
                                 event_ts="4072435201.1", commit=False)
    assert record_reaction_event(channel="C042G463AQ1", message_ts="4072435200.000100",
                                 emoji="six", slack_uid="UFAKE0009", removed=True, commit=False)
    rows = SlackReactionEvent.query.filter_by(slack_uid="UFAKE0009").order_by(SlackReactionEvent.id).all()
    assert [r.action for r in rows] == ["added", "removed"]


def test_ignores_other_channels(db_session):
    assert record_reaction_event(channel="COTHER", message_ts="1.1", emoji="six",
                                 slack_uid="UFAKE0010", removed=False, commit=False) is False
    assert SlackReactionEvent.query.filter_by(slack_uid="UFAKE0010").count() == 0


def test_never_raises(db_session):
    with patch("app.analytics.reaction_log.db.session.add", side_effect=RuntimeError("boom")):
        assert record_reaction_event(channel="C042G463AQ1", message_ts="1.1", emoji="six",
                                     slack_uid="UFAKE0011", removed=False, commit=False) is False


def test_delegate_returns_attendance_result_even_if_log_fails(app):
    event = {"item": {"type": "message", "channel": "C042G463AQ1", "ts": "1.1"},
             "reaction": "six", "user": "UFAKE0012", "event_ts": "1.2"}
    with patch("app.slack.practices.reactions.handle_attendance_reaction",
               return_value={"success": True, "ignored": "message_not_linked"}), \
         patch("app.analytics.reaction_log.record_reaction_event",
               side_effect=RuntimeError("should be swallowed")) as rec, \
         patch.object(bolt_module, "get_app_context", return_value=app.app_context()):
        result = bolt_module._delegate_reaction_event(event, removed=False)
    assert result == {"success": True, "ignored": "message_not_linked"}
    assert rec.called
```

- [ ] **Step 2: Run, expect ImportError.**

- [ ] **Step 3: Implement**

`app/analytics/reaction_log.py`:

```python
"""Append-only log of reaction adds/removals on archived channels.

The only record of un-checks (removed RSVPs). Must never affect attendance
handling: every failure is logged and swallowed."""
import logging

from app.analytics import CHANNELS
from app.models import db

logger = logging.getLogger(__name__)


def record_reaction_event(*, channel, message_ts, emoji, slack_uid, removed,
                          event_ts=None, commit=True):
    if channel not in CHANNELS or not (message_ts and emoji and slack_uid):
        return False
    try:
        from app.analytics.models import SlackReactionEvent
        db.session.add(SlackReactionEvent(
            channel_id=channel, message_ts=message_ts, emoji=emoji,
            slack_uid=slack_uid, action="removed" if removed else "added",
            event_ts=event_ts))
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return True
    except Exception:
        db.session.rollback()
        logger.warning("reaction event log failed for %s %s", channel, message_ts, exc_info=True)
        return False
```

In `app/slack/bolt_app.py`, change `_delegate_reaction_event` so the log runs after attendance handling, in a `finally`, and a failure there can never change the return value:

```python
def _delegate_reaction_event(event, *, removed):
    """Validate one Bolt reaction envelope and delegate attendance routing."""
    item = event.get("item", {})
    if item.get("type") != "message":
        return
    from app.slack.practices.reactions import handle_attendance_reaction

    with get_app_context():
        try:
            return handle_attendance_reaction(
                channel=item.get("channel"),
                message_ts=item.get("ts"),
                reaction=event.get("reaction"),
                slack_user_id=event.get("user"),
                removed=removed,
            )
        finally:
            # Analytics un-check log. Guarded twice: record_reaction_event never
            # raises, and this except covers an import failure.
            try:
                from app.analytics.reaction_log import record_reaction_event
                record_reaction_event(
                    channel=item.get("channel"), message_ts=item.get("ts"),
                    emoji=event.get("reaction"), slack_uid=event.get("user"),
                    removed=removed, event_ts=event.get("event_ts"))
            except Exception:
                logger.warning("analytics reaction log skipped", exc_info=True)
```

Check the module already has a `logger`; if it uses another name, use that.

- [ ] **Step 4: Run the new tests and the existing reaction suite.**

Run: `pytest tests/analytics/test_reaction_log.py tests/slack/test_reaction_rsvp.py -v`
Expected: all PASS (existing tests unchanged).

- [ ] **Step 5: Commit**

```bash
git add app/analytics/reaction_log.py app/slack/bolt_app.py tests/analytics/test_reaction_log.py
git commit -m "feat(analytics): log reaction adds and removals for un-check history"
```

---

### Task 6: Template-era parser (pure)

**Files:**
- Create: `app/analytics/parse_template.py`, `tests/analytics/fixtures/template_messages.json`, `tests/analytics/test_parse_template.py`

**Interfaces:**
- Consumes: `ArchivedMessage`, `SessionDraft`, `LocationRef` (Task 2); `HistoryConfig`, `resolve_venue`, `classify_title` (Task 3).
- Produces:
  - `is_weekly_preview(text: str) -> bool`
  - `looks_like_template(text: str) -> bool`
  - `parse_header(text: str, posted_at_central: datetime) -> tuple[list[date], list[str]]` (dates, flags)
  - `parse_bop(text: str) -> list[tuple[str, str | None]]` ((emoji, label) in order)
  - `parse_times(text: str) -> list[time]`
  - `parse_people(text: str, label: str) -> list[str]` (Slack uids from `<@U...>` on lines starting with that label)
  - `parse_venue(text: str) -> str | None`
  - `parse_title(text: str) -> str`
  - `extract_template_sessions(msg: ArchivedMessage, cfg, locations) -> list[SessionDraft]`

Session keys: `f"{channel}:{ts}:{slot}"` where slot is `early`/`late` for splits, the ISO date for multi-day posts, and `main` otherwise. `group_key = f"{channel}:{ts}"`.

- [ ] **Step 1: Hand-written fixtures**

`tests/analytics/fixtures/template_messages.json` is a list of cases `{"name", "channel_id", "posted_at_central", "raw", "expected"}`. The `raw.text` values are written by hand to copy the real format (see the format notes in the spec's "What the data looks like" section), with invented content, fake user IDs `UFAKExxxx`, and HTML entities as Slack sends them (`&gt;`, `&amp;`). Write these ten cases:

1. `zapier_single`: 2022-style Zapier post. Header `:woman-playing-handball:  _Tuesday,_ _Oct 25, 2022_ • _TCSC_ • :man-playing-handball:`, title line `*Run w/ Poles - Intervals* *@* *Theodore Wirth Trails*`, `&gt;:clock6:  *Time:* 6:15 PM`, `&gt;:people_holding_hands:  *Leads:* <@UFAKE0101> &amp; <@UFAKE0102>`, `&gt; :pushpin:  *Location:* Theodore Wirth Trails`, closing `*Bop that* :white_check_mark: *so we'll know you'll be there.*`. Expected: one session, date 2022-10-25, 18:15, venue "Theodore Wirth Trails", activities [Pole Run], types [Intervals], rsvp_emoji white_check_mark, leads [UFAKE0101, UFAKE0102], format single, no flags.
2. `split_zap_check`: header Thursday Oct 26, 2023; title `*Strength Circuit @ Balance Fitness Studio*`; `*Bop that* :zap: *(for 6:00PM session) or* :white_check_mark: *(for 7:00PM session) so we'll know you'll be there.*`. Expected: two sessions, keys `...:early` (zap, 18:00) and `...:late` (white_check_mark, 19:00), format split, same group_key, is_indoor true.
3. `split_six_seven`: 2025 lift with `*Time:* 6:05 PM :six: & 7:20 PM :seven:` and `*Bop that* :six: *(6:05PM) or* :seven: *(7:20PM)*`. Expected: early six 18:05, late seven 19:20.
4. `friday_am_posted_night_before`: posted_at_central 2025-02-06T20:16, header `Friday, Feb 7th, 2025`, `*Time:* 7:00 AM  ( :meow-coffee: )`, `*Bop that* :meow-coffee: *if you'll be there*`. Expected: date 2025-02-07, 07:00, rsvp_emoji meow-coffee.
5. `wrong_year_header`: posted_at_central 2025-01-30T12:00, header `Friday, Jan 31st, 2024` (the real posts had this typo). Expected: date 2025-01-31, flags [date_mismatch].
6. `multi_day`: header `Wednesday & Friday, Dec 3rd & 5th, 2025`, `*Bop that* :white_check_mark: *(Wed 6:30 PM) or* :ballot_box_with_check: *(Fri 7:00 AM)*`. Expected: two sessions dated 2025-12-03 18:30 (white_check_mark) and 2025-12-05 07:00 (ballot_box_with_check), format single each, keys `...:2025-12-03` and `...:2025-12-05`, flags [multi_day].
7. `weekly_preview`: `:date: • _Week of Oct 22, 2023_ _| TCSC_ • :date:` then two day blocks and `_Additional details are available in the TCSC Team Calendar..._`. Expected: no sessions (is_weekly_preview true).
8. `event_kickoff`: template-shaped post titled `*Season Kickoff + Potluck @ Minnehaha Pavillion 1*`. Expected: one session, kind event.
9. `unknown_venue_and_title`: title `*Super Secret Surprise @ Some New Park*`. Expected: flags [unknown_venue, unmatched_title], activities [].
10. `plain_announcement`: a text-only note ("Remember to bring a pen to practice today!"). Expected: no sessions.

- [ ] **Step 2: Failing tests**

`tests/analytics/test_parse_template.py`:

```python
from datetime import date, datetime, time

import pytest

from app.analytics.drafts import ArchivedMessage, LocationRef
from app.analytics.history_config import load_history_config
from app.analytics.parse_template import (
    extract_template_sessions, is_weekly_preview, parse_bop, parse_header, parse_times)
from tests.analytics.conftest import load_fixture

CASES = load_fixture("template_messages.json")
LOCS = [LocationRef(38, "Balance Fitness Studio", None, 44.95, -93.28),
        LocationRef(34, "Theodore Wirth", "Xerxes Field", 44.98, -93.31)]


@pytest.fixture(scope="module")
def cfg():
    return load_history_config()


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_golden(case, cfg):
    raw = case["raw"]
    msg = ArchivedMessage(channel_id=case["channel_id"], ts=raw["ts"], raw=raw)
    sessions = extract_template_sessions(msg, cfg, LOCS)
    exp = case["expected"]
    assert len(sessions) == len(exp["sessions"])
    for got, want in zip(sessions, exp["sessions"]):
        assert got.session_key.endswith(want["key_suffix"])
        assert got.date == date.fromisoformat(want["date"])
        assert got.start_time == (time.fromisoformat(want["start"]) if want.get("start") else None)
        assert got.rsvp_emoji == want["rsvp_emoji"]
        assert got.format == want["format"]
        assert got.kind == want.get("kind", "practice")
        assert sorted(got.flags) == sorted(want.get("flags", []))
        for k in ("activities", "workout_types", "lead_uids", "venue_raw", "is_indoor"):
            if k in want:
                assert getattr(got, k) == want[k], k


def test_header_year_missing_uses_post_year():
    dates, flags = parse_header("_Tuesday, Jan 31_ • _TCSC_", datetime(2023, 1, 31, 8))
    assert dates == [date(2023, 1, 31)] and flags == []


def test_header_weekday_mismatch_snaps_to_named_weekday():
    # Header says Thursday Jun 8 but the post went out Thu Jun 15 (stale repost)
    dates, flags = parse_header("_Thursday, Jun 8th, 2023_", datetime(2023, 6, 15, 9))
    assert dates == [date(2023, 6, 15)] and "date_mismatch" in flags


def test_parse_bop_orders_and_labels():
    t = "*Bop that* :zap: *(for 6:00PM session) or* :white_check_mark: *(for 7:00PM session)*"
    assert parse_bop(t) == [("zap", "for 6:00PM session"), ("white_check_mark", "for 7:00PM session")]


def test_parse_times():
    assert parse_times("*Time:* 6:05 PM :six: & 7:20 PM :seven:") == [time(18, 5), time(19, 20)]
    assert parse_times("Thursday, 10/26/2023 @ 6:00 & 7:00 PM") == [time(18, 0), time(19, 0)]


def test_weekly_preview_detection():
    assert is_weekly_preview(":date: • _Week of Oct 22, 2023_")
    assert is_weekly_preview("There are *2* events this week")
    assert not is_weekly_preview("*Bop that* :white_check_mark:")
```

- [ ] **Step 3: Run, expect ImportError.**

- [ ] **Step 4: Implement `app/analytics/parse_template.py`**

Rules (write code that meets them and the tests):
- Unescape with `html.unescape` first, then strip `*` and `_` for header/label parsing (keep the original for emoji extraction).
- `is_weekly_preview`: regex `(Week of |There are \*?\d+\*? events|Weekly Practice Summary|Practices this week|Additional details are available in the TCSC Team Calendar)`.
- `looks_like_template`: has a weekday+month+day header within the first 300 characters AND (`Bop that` or `Time:` or `Workout:` or ` @ `).
- Header regex (weekday, optional `& Weekday`, month name or abbreviation, day with optional ordinal, optional `& day`, optional 4-digit year). Also accept `Weekday, M/D/YYYY`. Year missing: use the post's year, or the next year if that lands more than 30 days before the post.
- Date sanity window: a header date is accepted when `posted_date - 1 day <= date <= posted_date + 8 days`. Otherwise, try the same month/day in the post's year and the next year. If still outside, pick the first date on or after `posted_date - 1 day` whose weekday equals the header weekday. Any correction adds `date_mismatch`.
- A header weekday that disagrees with an accepted date's weekday: snap to the date in the window with the header's weekday, add `date_mismatch`.
- `parse_times`: all `H:MM` with optional AM/PM; a time without AM/PM takes the next time's meridiem (so `6:00 & 7:00 PM` gives 18:00, 19:00); bare times 1-9 without any meridiem are PM.
- `parse_bop`: the text after `Bop that` up to `so we` / `if you` / end of line; returns `(emoji_name, label_or_None)` for each `:name:` in order, where the label is the next parenthesized text before the next emoji, with `*` removed and stripped.
- Session layout:
  - 2+ bop emoji and the post has 2 header dates (multi-day): one session per date, paired in order; the start time comes from the label (`Wed 6:30 PM`) or the times in order; format single; flag `multi_day`.
  - 2 bop emoji, one date: split. Times from the labels, else from `parse_times` in order. The earlier time is `early`. Format split.
  - 1 bop emoji or none: single session, rsvp_emoji the bop emoji or `white_check_mark`; start time = first time from the `Time:` line, else from the header.
- Title: the first line within the first 5 non-empty lines that contains `@` and not `Details`, markup stripped; the part before `@` is the title and the part after is the venue candidate. Fall back to a `Workout:` line.
- Venue: the `Location:` line value when present, else the title's `@` part. Resolved through `resolve_venue`; unmatched adds `unknown_venue`.
- Activities/types/kind from `classify_title(title)`; unmatched adds `unmatched_title`. `activity`/`workout_type` buckets are set here with `activity_bucket`/`workout_bucket`.
- `lead_uids` from `Leads:` lines, `coach_uids` from `Coach:`/`Coaches:` lines.
- `source_archive_id = msg.archive_id`, `channel_id`, `source_ts` set on every draft. Posted time in Central comes from `msg.raw["ts"]` converted with `zoneinfo.ZoneInfo("America/Chicago")`.

- [ ] **Step 5: Run, expect PASS.** Commit:

```bash
git add app/analytics/parse_template.py tests/analytics/fixtures/template_messages.json tests/analytics/test_parse_template.py
git commit -m "feat(analytics): template-era post parser"
```

---

### Task 7: App-era extractor (pure)

**Files:**
- Create: `app/analytics/parse_app.py`, `tests/analytics/test_parse_app.py`

**Interfaces:**
- Consumes: `AppPractice`, `ArchivedMessage`, `SessionDraft`, `LocationRef`; `HistoryConfig`, `resolve_venue`, `activity_bucket`, `workout_bucket`.
- Produces: `extract_app_sessions(practices: list[AppPractice], messages_by_ts: dict[tuple[str, str], ArchivedMessage], cfg, locations) -> list[SessionDraft]` and `parse_rsvp_mapping(blocks_text: str) -> dict[str, str]` (emoji → `Wed`/`Fri`/time label).

Rules:
- Skip `is_draft` practices and practices with no `slack_message_ts`.
- Group by `(slack_channel_id, slack_message_ts)`. Sort each group by `date`.
- One practice in the group: format single, key `practice:<id>`, rsvp_emoji `slack_session_emoji` or `white_check_mark`.
- Two practices on the same date: format split, earlier is `early`. Emoji from `slack_session_emoji`; if blank, from `parse_rsvp_mapping` over the archived message's text and block text (pattern `RSVP: :e1: <label> | :e2: <label>`, or the lift post's `:six: 6:05` / `:seven: 7:20` pairs), matched to practices by weekday or time; if still unknown, `six`/`seven` for Thursday strength, else flag `emoji_unknown`.
- Two practices on different dates (Wed+Fri posts): format single each, emoji as above.
- `status` = `cancelled` when `practice.status == "cancelled"`, else `held`.
- Venue: find the `LocationRef` with the practice's `location_name`/`location_spot`, and take `is_indoor` from `indoor_locations`. If not found, pass `f"{name} - {spot}"` through `resolve_venue`.
- `activities`/`workout_types` from the practice; buckets via the helpers. `kind` = `event` when an activity is `Kickoff`.
- `lead_uids`, `coach_uids`, `plan_emoji` copied from the practice. `title` = activities joined with ", " plus " - " plus types joined, or "Practice" when both are empty.
- `group_key` = `f"{channel}:{ts}"`, `source_archive_id` from the archived message when present; if the message is missing from the archive (deleted), flag `post_missing`.

- [ ] **Step 1: Failing tests**

`tests/analytics/test_parse_app.py`:

```python
from datetime import datetime, time

import pytest

from app.analytics.drafts import AppPractice, ArchivedMessage, LocationRef
from app.analytics.history_config import load_history_config
from app.analytics.parse_app import extract_app_sessions, parse_rsvp_mapping

CH = "C042G463AQ1"
LOCS = [LocationRef(38, "Balance Fitness Studio", None, 44.95, -93.28),
        LocationRef(35, "Hyland", "Visitor Center", 44.82, -93.37)]


@pytest.fixture(scope="module")
def cfg():
    return load_history_config()


def P(id, dt, ts, emoji=None, **kw):
    base = dict(id=id, date=dt, status="scheduled", is_draft=False, slack_channel_id=CH,
                slack_message_ts=ts, slack_session_emoji=emoji,
                location_name="Balance Fitness Studio", location_spot=None,
                activities=("Strength",), types=("Circuit",))
    base.update(kw)
    return AppPractice(**base)


def test_split_lift_with_saved_emoji(cfg):
    ps = [P(1, datetime(2099, 5, 21, 18, 5), "4082.1", "six"),
          P(2, datetime(2099, 5, 21, 19, 20), "4082.1", "seven")]
    out = extract_app_sessions(ps, {(CH, "4082.1"): ArchivedMessage(CH, "4082.1", {"ts": "4082.1", "text": ""})}, cfg, LOCS)
    assert [(s.slot, s.rsvp_emoji, s.format, s.session_key) for s in out] == [
        ("early", "six", "split", "practice:1"), ("late", "seven", "split", "practice:2")]
    assert out[0].is_indoor and out[0].activity == "Strength"


def test_wed_fri_group_reads_mapping_from_post(cfg):
    text = "RSVP: :white_check_mark: Wed (6:30 PM) | :ballot_box_with_check: Fri (7:00 AM)"
    ps = [P(3, datetime(2099, 1, 7, 18, 30), "4083.1"), P(4, datetime(2099, 1, 9, 7, 0), "4083.1")]
    out = extract_app_sessions(ps, {(CH, "4083.1"): ArchivedMessage(CH, "4083.1", {"ts": "4083.1", "text": text})}, cfg, LOCS)
    assert [(s.rsvp_emoji, s.format, s.start_time) for s in out] == [
        ("white_check_mark", "single", time(18, 30)), ("ballot_box_with_check", "single", time(7, 0))]


def test_drafts_skipped_cancelled_kept_missing_post_flagged(cfg):
    ps = [P(5, datetime(2099, 2, 3, 18, 15), "4084.1", is_draft=True),
          P(6, datetime(2099, 2, 5, 18, 15), "4085.1", status="cancelled")]
    out = extract_app_sessions(ps, {}, cfg, LOCS)
    assert [s.practice_id for s in out] == [6]
    assert out[0].status == "cancelled" and "post_missing" in out[0].flags


def test_parse_rsvp_mapping():
    assert parse_rsvp_mapping("RSVP: :white_check_mark: Wed (6:30 PM) | :ballot_box_with_check: Fri (7:00 AM)") == {
        "white_check_mark": "Wed (6:30 PM)", "ballot_box_with_check": "Fri (7:00 AM)"}
```

- [ ] **Step 2: Run, expect ImportError. Step 3: implement to the rules above. Step 4: run, expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add app/analytics/parse_app.py tests/analytics/test_parse_app.py
git commit -m "feat(analytics): app-era sessions from practice rows"
```

---

### Task 8: Lineage builder (pure): attendance, merges, corrections

**Files:**
- Create: `app/analytics/lineage.py`, `tests/analytics/test_lineage.py`, `tests/analytics/test_lift_acceptance.py`
- Real data read in place (never copied into the repo): `.superpowers/analytics-slack-dump/lift_verified.json`, `corrections.json` (created in Step 4)

**Interfaces:**
- Consumes: everything from Tasks 2, 3, 6, 7.
- Produces: `build_lineage(messages: list[ArchivedMessage], app_practices: list[AppPractice], locations: list[LocationRef], seasons: list[SeasonRef], cfg: HistoryConfig, corrections: dict | None = None) -> LineageResult`. `corrections` maps key → fields dict (the shape `corrections.load_corrections()` returns in Task 9); the builder never reads the DB. Each returned `SessionDraft` also carries `season_label`, `day_of_week`, `rsvp_count` and `needs_review` as extra attributes set by the builder (add these three fields to `SessionDraft` in `drafts.py` with defaults `""`, `""`, `0`, `False`).
- `MERGE_RE`, `CANCEL_RE` module constants.

Algorithm:
1. Drop messages with `deleted=True`. Index by `(channel_id, ts)`.
2. App sessions first: `extract_app_sessions` over all app practices. Remember every `(channel, ts)` they consume.
3. Template sessions: for top-level messages in `SESSION_CHANNELS` not consumed by step 2, not a weekly preview, and `looks_like_template`: `extract_template_sessions`.
4. Corrections keyed by `"<channel>:<ts>"` apply to every session of that post; keys equal to a `session_key` apply to that session only. `skip: true` removes the session(s). Fields `kind`, `date`, `start_time`, `status`, `location` (a raw venue string, resolved with `resolve_venue`), `activities`, `types` overwrite. `rsvp_emoji` (a list) replaces the RSVP emoji set, `plan_emoji` (a list) sets plan emoji, and `rsvp_from` (list of `"<channel>:<ts>"`) adds those messages' reactions as RSVP sources.
5. Merges, per group of 2+ split sessions: merged when a correction says `merged: true`, or when no correction has a `merged` key and some reply in the thread was posted on the practice date (Central) and matches `MERGE_RE = re.compile(r"\b(combin\w*|merg\w*|one session|single session|one lift)\b", re.I)`. The "too big for one session" case is handled by a `merged: false` correction, which always wins. A merged group becomes one session: key `f"{group_key}:merged"` (template) or `practice:<first id>` (app), format `merged`, slot None, start_time = first `H:MM` time found in the matching reply (PM assumed), else the early session's time, `rsvp_emoji` None. It keeps an `emoji → slot` map from the pre-merge sessions. Auto-detected merges add the flag `merge_detected`.
6. Cancel language: any reply matching `CANCEL_RE = re.compile(r"\bcancel(l?ed|l?ing|s)?\b", re.I)` on or before the practice date adds the flag `cancel_language`. Status changes only through the app or a correction.
7. Attendance per session, from the post's `raw["reactions"]` plus `rsvp_from` messages:
   - Skip reactors in `cfg.excluded_slack_uids`.
   - `base_emoji(name)` in the session's RSVP emoji set (the merged set on merged sessions): role `rsvp`, source `reaction`, `slot` from the emoji→slot map.
   - Base emoji in `cfg.coach_emoji`: role `coach`, source `reaction`.
   - Base emoji in the session's `plan_emoji` (compared by base name): role `plan`, source `reaction`.
   - App era: every `button_rsvp_uids` entry not excluded is role `rsvp`, source `button`, emoji None, slot None, unless the same uid already has an rsvp reaction row for this session.
   - `lead_uids`: role `lead`, source `post_text` (template) or `app`. `coach_uids`: role `coach`, same sources.
   - Correction `add`/`remove` apply last (source `correction`).
   - Dedupe on `(session_key, slack_uid, role, emoji)`.
8. For each session: `rsvp_count` = distinct uids with role `rsvp`. `day_of_week` = `date.strftime("%A")`. `season_label` via `season_label`. `needs_review` = `bool(flags)` and no correction (by session key or post key) exists in `corrections`, where a correction with only `ok: true` also counts.
9. `possible_misses`: top-level messages in `SESSION_CHANNELS` that produced no session, are not weekly previews, are not consumed, and have any reaction with `count >= 5` whose base emoji is `white_check_mark`, `six`, `seven`, `zap`, `meow-coffee` or `ballot_box_with_check`.
10. Return sessions sorted by `(date, start_time or 00:00, session_key)`.

- [ ] **Step 1: Failing unit tests**

`tests/analytics/test_lineage.py` builds small `ArchivedMessage` lists by hand (reusing the template text from the fixtures file where convenient) and asserts:

```python
from datetime import date, datetime
from dataclasses import replace

import pytest

from app.analytics.drafts import AppPractice, ArchivedMessage, LocationRef
from app.analytics.history_config import load_history_config
from app.analytics.lineage import build_lineage

CH = "C042G463AQ1"
BOT, ZAP = "U06FYPUNQCU", "U04C46UJXAM"
LOCS = [LocationRef(38, "Balance Fitness Studio", None, 44.95, -93.28)]
SPLIT_TEXT = ("_Thursday, Jul 16th, 2099_ • _TCSC_\n*Strength Circuit @ Balance Fitness Studio*\n"
              "*Time:* 6:05 PM :six: & 7:20 PM :seven:\n*Bop that* :six: *(6:05PM) or* :seven: *(7:20PM)*")


@pytest.fixture
def cfg():
    return load_history_config()


def _ts(dt):  # naive Central -> Slack ts string; tests only need ordering and the date
    from zoneinfo import ZoneInfo
    return f"{dt.replace(tzinfo=ZoneInfo('America/Chicago')).timestamp():.6f}"


def _post(text, reactions, when=datetime(2099, 7, 16, 8, 0), replies=()):
    ts = _ts(when)
    raw = {"ts": ts, "text": text, "reactions": reactions}
    return ArchivedMessage(CH, ts, raw, replies=tuple(replies))


def R(name, *users):
    return {"name": name, "count": len(users), "users": list(users)}


def test_excluded_accounts_never_attend(cfg):
    msg = _post(SPLIT_TEXT, [R("six", BOT, "UFAKE1", ZAP), R("seven", BOT, "UFAKE2")])
    res = build_lineage([msg], [], LOCS, [], cfg)
    uids = {a.slack_uid for a in res.attendance}
    assert BOT not in uids and ZAP not in uids
    assert [s.rsvp_count for s in res.sessions] == [1, 1]


def test_merge_needs_same_day_reply_and_correction_wins(cfg):
    same_day = {"ts": _ts(datetime(2099, 7, 16, 15, 0)), "text": "We're merging to one session at 6:30 tonight!"}
    msg = _post(SPLIT_TEXT, [R("six", "UFAKE1", "UFAKE3"), R("seven", "UFAKE2")], replies=[same_day])
    res = build_lineage([msg], [], LOCS, [], cfg)
    assert len(res.sessions) == 1
    s = res.sessions[0]
    assert (s.format, s.rsvp_count, s.start_time.hour, s.start_time.minute) == ("merged", 3, 18, 30)
    assert "merge_detected" in s.flags
    slots = sorted((a.slack_uid, a.slot) for a in res.attendance if a.role == "rsvp")
    assert slots == [("UFAKE1", "early"), ("UFAKE2", "late"), ("UFAKE3", "early")]

    next_day = {"ts": _ts(datetime(2099, 7, 17, 9, 0)), "text": "merging next week?"}
    res = build_lineage([replace(msg, replies=(next_day,))], [], LOCS, [], cfg)
    assert [s.format for s in res.sessions] == ["split", "split"]

    res = build_lineage([msg], [], LOCS, [], cfg, corrections={f"{CH}:{msg.ts}": {"merged": False}})
    assert [s.format for s in res.sessions] == ["split", "split"]


def test_coach_plan_and_lead_roles(cfg):
    text = SPLIT_TEXT + "\n*Leads:* <@UFAKE9>"
    msg = _post(text, [R("six", "UFAKE1"), R("coachface", "UFAKE7")])
    res = build_lineage([msg], [], LOCS, [], replace(cfg, coach_emoji=frozenset({"coachface"})))
    roles = {(a.slack_uid, a.role) for a in res.attendance}
    assert ("UFAKE7", "coach") in roles and ("UFAKE9", "lead") in roles
    assert ("UFAKE7", "rsvp") not in roles


def test_button_rsvps_union_without_double_count(cfg):
    ts = "4090000000.000100"
    p = AppPractice(id=900, date=datetime(2099, 1, 6, 18, 15), status="scheduled", is_draft=False,
                    slack_channel_id=CH, slack_message_ts=ts, slack_session_emoji=None,
                    location_name="Balance Fitness Studio", location_spot=None,
                    activities=("Strength",), types=("Circuit",),
                    button_rsvp_uids=("UFAKE1", "UFAKE5"))
    msg = ArchivedMessage(CH, ts, {"ts": ts, "text": "Practice on Tuesday",
                                   "reactions": [R("white_check_mark", "UFAKE1", BOT)]})
    res = build_lineage([msg], [p], LOCS, [], cfg)
    assert res.sessions[0].rsvp_count == 2
    sources = sorted((a.slack_uid, a.source) for a in res.attendance if a.role == "rsvp")
    assert sources == [("UFAKE1", "reaction"), ("UFAKE5", "button")]


def test_rsvp_from_other_message_and_skip(cfg):
    main = _post(SPLIT_TEXT, [R("six", "UFAKE1")])
    other_ts = _ts(datetime(2099, 7, 15, 20, 0))
    other = ArchivedMessage(CH, other_ts, {"ts": other_ts, "text": "official RSVP, add a check",
                                           "reactions": [R("six", "UFAKE4")]})
    corr = {f"{CH}:{main.ts}:early": {"rsvp_from": [f"{CH}:{other_ts}"]}}
    res = build_lineage([main, other], [], LOCS, [], cfg, corrections=corr)
    early = [s for s in res.sessions if s.slot == "early"][0]
    assert early.rsvp_count == 2
    corr[f"{CH}:{main.ts}"] = {"skip": True}
    assert build_lineage([main, other], [], LOCS, [], cfg, corrections=corr).sessions == []


def test_deleted_messages_and_weekly_previews_produce_nothing(cfg):
    gone = replace(_post(SPLIT_TEXT, [R("six", "UFAKE1")]), deleted=True)
    preview = _post(":date: • _Week of Jul 13, 2099_", [R("white_check_mark", "UFAKE1")])
    assert build_lineage([gone, preview], [], LOCS, [], cfg).sessions == []


def test_needs_review_and_possible_misses(cfg):
    odd = _post("_Thursday, Jul 16th, 2099_\n*Super Secret Surprise @ Nowhere*",
                [R("white_check_mark", "UFAKE1")])
    stray_ts = _ts(datetime(2099, 7, 10, 9))
    stray = ArchivedMessage(CH, stray_ts, {"ts": stray_ts, "text": "please check this message",
                                          "reactions": [R("white_check_mark", *[f"UFAKE{i}" for i in range(6)])]})
    res = build_lineage([odd, stray], [], LOCS, [], cfg)
    assert res.sessions[0].needs_review is True
    assert f"{CH}:{stray_ts}" in res.possible_misses
    ok = {res.sessions[0].session_key: {"ok": True}}
    assert build_lineage([odd], [], LOCS, [], cfg, corrections=ok).sessions[0].needs_review is False
```

Corrections are passed in as a plain dict. The DB loader is Task 9's `load_corrections()`.

- [ ] **Step 2: Real-data acceptance test (skips without the dump)**

`tests/analytics/test_lift_acceptance.py`:

```python
"""The rebuilt strength lineage must reproduce the hand-verified lift counts.

Uses the real Slack dump, hand-verified counts and proposed corrections in
the gitignored .superpowers folder, so it only runs on the dev box. Nothing
it reads is committed."""
import json
from datetime import date, datetime

import pytest

from app.analytics.drafts import AppPractice, ArchivedMessage, LocationRef
from app.analytics.history_config import load_history_config
from app.analytics.lineage import build_lineage
from tests.analytics.conftest import DUMP_DIR

pytestmark = pytest.mark.skipif(not (DUMP_DIR / "lift_verified.json").exists(),
                                reason="real Slack dump not present")


def _corrections():
    path = DUMP_DIR / "corrections.json"   # {key: {"fields": {...}, "note": str}}
    if not path.exists():
        return {}
    return {k: v["fields"] for k, v in json.loads(path.read_text()).items()}


def _messages():
    out = []
    for chan, hist, threads in (("C042G463AQ1", "chan.json", "threads.json"),
                                ("C03FKTTHNHW", "summer.json", "summer_threads.json")):
        replies = json.loads((DUMP_DIR / threads).read_text())
        for raw in json.loads((DUMP_DIR / hist).read_text()):
            out.append(ArchivedMessage(chan, raw["ts"], raw, tuple(replies.get(raw["ts"], []))))
    return out


def _practices():
    rows = json.loads((DUMP_DIR / "app_practices.json").read_text())
    return [AppPractice(**{**r, "date": datetime.fromisoformat(r["date"]),
                           **{k: tuple(r[k]) for k in ("activities", "types", "lead_uids",
                                                       "coach_uids", "plan_emoji", "button_rsvp_uids")}})
            for r in rows]


def test_strength_lineage_matches_verified_counts():
    locs = [LocationRef(r["id"], r["name"], r["spot"], r["lat"], r["lon"])
            for r in json.loads((DUMP_DIR / "locations.json").read_text())]
    res = build_lineage(_messages(), _practices(), locs, [], load_history_config(), _corrections())
    by_date = {}
    for s in res.sessions:
        if s.activity == "Strength" and s.kind == "practice":
            by_date.setdefault(s.date, []).append(s)
    att = {}
    for a in res.attendance:
        if a.role == "rsvp":
            att.setdefault(a.session_key, []).append(a)
    mismatches = []
    for row in json.loads((DUMP_DIR / "lift_verified.json").read_text())["sessions"]:
        d = date.fromisoformat(row["date"])
        sessions = by_date.get(d, [])
        rows = [a for s in sessions for a in att.get(s.session_key, [])]
        if row["format"] == "single":
            got = {"one": len({a.slack_uid for a in rows})}
            want = {"one": row["one"]}
        else:
            got = {"early": len({a.slack_uid for a in rows if a.slot == "early"}),
                   "late": len({a.slack_uid for a in rows if a.slot == "late"})}
            want = {"early": row["early"], "late": row["late"]}
        fmt = sorted({s.format for s in sessions})
        if got != want or fmt != [row["format"]]:
            mismatches.append((row["date"], fmt, got, want))
    assert not mismatches, "\n".join(map(str, mismatches))
```

Mismatches here are expected on the first run. Fix a pattern with a parser or YAML rule change. Fix a one-off (e.g. `merged: true` for a merge the regex missed, `merged: false` for the Jul 17, 2025 false positive) by adding an entry to `.superpowers/analytics-slack-dump/corrections.json` in the shape `{"<key>": {"fields": {...}, "note": "why"}}`. Task 12 imports that file into the prod `analytics_corrections` table. Never commit it.

- [ ] **Step 3: Run the unit tests, expect ImportError. Implement `lineage.py`. Run until the unit tests pass.**

Run: `pytest tests/analytics/test_lineage.py -v`

- [ ] **Step 4: Run the acceptance test and reconcile**

Run: `pytest tests/analytics/test_lift_acceptance.py -v`
Expected at the end: PASS, with 44 of 44 dates matching.

- [ ] **Step 5: Commit**

```bash
git add app/analytics/lineage.py app/analytics/drafts.py config/practice_history.yaml tests/analytics/test_lineage.py tests/analytics/test_lift_acceptance.py
git commit -m "feat(analytics): lineage builder with merges, corrections and lift acceptance"
```

---

### Task 9: Rebuild (DB IO)

**Files:**
- Create: `app/analytics/rebuild.py`, `app/analytics/corrections.py`, `tests/analytics/test_rebuild.py`, `tests/analytics/test_corrections.py`

**Interfaces:**
- Consumes: `build_lineage`, `load_history_config`, models, `apply_weather(session_rows)` from Task 10 (import lazily; Task 10 lands next, so in this task implement `apply_weather` as a call guarded by `try/except ImportError` and complete the wiring in Task 10).
- Produces:
  - `load_inputs() -> tuple[list[ArchivedMessage], list[AppPractice], list[LocationRef], list[SeasonRef]]`
  - `rebuild(*, cfg=None, commit=True) -> dict` with `{"sessions", "attendance", "needs_review", "possible_misses"}`
  - `flagged_sessions() -> list[PracticeSession]` (needs_review true, ordered by date)
- `app/analytics/corrections.py` produces:
  - `CORRECTION_FIELDS = {"skip", "kind", "date", "start_time", "status", "merged", "rsvp_emoji", "plan_emoji", "rsvp_from", "add", "remove", "location", "activities", "types", "ok"}`
  - `class CorrectionError(ValueError)`
  - `validate_correction(key: str, fields: dict) -> dict`: key matches `^C[A-Z0-9]+:\d+\.\d+(:(early|late|merged|main|\d{4}-\d{2}-\d{2}))?$` or `^practice:\d+$`; fields non-empty; every field in `CORRECTION_FIELDS` with the right type (`skip`/`merged`/`ok` bool; `kind` in practice/event; `status` in held/cancelled; `date` ISO date; `start_time` `HH:MM`; `rsvp_emoji`/`plan_emoji`/`activities`/`types` list of str; `rsvp_from` list of `<channel>:<ts>`; `add`/`remove` list of `{slack_uid, role}` with role in rsvp/plan/lead/coach; `location` str). Returns the fields; raises `CorrectionError` naming the problem.
  - `load_corrections() -> dict[str, dict]` (key → fields, from the table)
  - `upsert_correction(key, fields, note, author) -> AnalyticsCorrection` (validates; `note` required, non-empty; no commit)
  - `import_corrections(path) -> int` (file shape `{key: {"fields": {...}, "note": str}}`, author from the entry's optional `"author"`, default `"claude-fixer"`; validates every entry before writing any; no commit)
  - `export_corrections(path) -> int` (same shape, keys sorted)

Rules:
- `load_inputs`: archive rows from `SESSION_CHANNELS` (top-level: `thread_ts is None or thread_ts == ts`), with `deleted = row.deleted_at is not None` and `archive_id = row.id`, each with its non-deleted replies (rows with the same `thread_ts`, `ts != thread_ts`, ordered by `ts`) as raw dicts. Also load `rsvp_from` targets: every archive row in `SESSION_CHANNELS` is loaded, so no special case is needed. App practices come from `Practice` joined with location, activities, types, `PracticeLead`→`SlackUser.slack_uid` by role, `plan_reactions` emoji, and `PracticeRSVP` status `going`→`SlackUser.slack_uid`. Locations come from `PracticeLocation`, seasons from `Season` (skip the legacy row where `season_type == "legacy"`).
- `rebuild`: load the config and `load_corrections()` first (an invalid config raises before anything is deleted). Fill coach emoji from the DB: `cfg = dataclasses.replace(cfg, coach_emoji=frozenset(AppConfig.get("analytics_coach_emoji", []) or []))`. Call `build_lineage(..., cfg, corrections)`. User ids resolve through `users.slack_user_id = slack_users.id` (the FK is on `users`). Then in one transaction: `DELETE FROM practice_attendance`, `DELETE FROM practice_sessions` (DELETE, not TRUNCATE, so tests can roll back), bulk insert sessions, flush for ids, map `session_key → id`, and bulk insert attendance with `user_id` resolved through `SlackUser.slack_uid → user_id`. Then call `apply_weather`. `rebuilt_at = datetime.utcnow()`. Commit when `commit=True`, else flush. Any exception: `db.session.rollback()` and re-raise, so the previous tables survive.

- [ ] **Step 1: Failing tests**

`tests/analytics/test_rebuild.py`:

```python
from unittest.mock import patch

import pytest

from app.analytics.history_config import HistoryConfigError
from app.analytics.models import PracticeAttendance, PracticeSession, SlackArchiveMessage
from app.analytics.rebuild import rebuild
from app.analytics.archive import upsert_message

CH = "C042G463AQ1"
TEXT = ("_Thursday, Jul 16th, 2099_ • _TCSC_\n*Strength Circuit @ Balance Fitness Studio*\n"
        "*Time:* 6:05 PM :six: & 7:20 PM :seven:\n*Bop that* :six: *(6:05PM) or* :seven: *(7:20PM)*")


def _seed():
    upsert_message(CH, {"ts": "4087911600.000100", "text": TEXT, "reactions": [
        {"name": "six", "count": 2, "users": ["UFAKE1", "UFAKE2"]},
        {"name": "seven", "count": 1, "users": ["UFAKE3"]}]})


def test_rebuild_writes_sessions_and_is_repeatable(db_session):
    _seed()
    first = rebuild(commit=False)
    keys1 = sorted(s.session_key for s in PracticeSession.query.filter(PracticeSession.session_key.like(f"{CH}:4087911600%")))
    second = rebuild(commit=False)
    keys2 = sorted(s.session_key for s in PracticeSession.query.filter(PracticeSession.session_key.like(f"{CH}:4087911600%")))
    assert keys1 == keys2 == [f"{CH}:4087911600.000100:early", f"{CH}:4087911600.000100:late"]
    assert first["sessions"] == second["sessions"]
    early = PracticeSession.query.filter_by(session_key=keys1[0]).one()
    assert early.rsvp_count == 2 and early.format == "split"
    assert PracticeAttendance.query.filter_by(session_id=early.id, role="rsvp").count() == 2


def test_invalid_config_leaves_tables_untouched(db_session):
    _seed()
    rebuild(commit=False)
    before = PracticeSession.query.count()
    with patch("app.analytics.rebuild.load_history_config", side_effect=HistoryConfigError("bad")):
        with pytest.raises(HistoryConfigError):
            rebuild(commit=False)
    assert PracticeSession.query.count() == before
```

`tests/analytics/test_corrections.py`:

```python
import json

import pytest

from app.analytics.corrections import (
    CorrectionError, export_corrections, import_corrections, load_corrections,
    upsert_correction, validate_correction)

KEY = "C042G463AQ1:4087911600.000100"


@pytest.mark.parametrize("key,fields", [
    ("not-a-key", {"skip": True}),
    (KEY, {}),
    (KEY, {"merged": "yes"}),
    (KEY, {"status": "gone"}),
    (KEY, {"add": [{"slack_uid": "UFAKE1", "role": "boss"}]}),
    (KEY, {"unknown_field": 1}),
])
def test_validation_rejects(key, fields):
    with pytest.raises(CorrectionError):
        validate_correction(key, fields)


def test_upsert_requires_note_and_round_trips(db_session, tmp_path):
    with pytest.raises(CorrectionError):
        upsert_correction(KEY, {"merged": True}, "", "test")
    upsert_correction(KEY, {"merged": True}, "thread says merged", "test")
    upsert_correction(KEY + ":early", {"ok": True}, "checked", "test")
    db_session.flush()
    assert load_corrections()[KEY] == {"merged": True}
    out = tmp_path / "c.json"
    export_corrections(out)
    data = json.loads(out.read_text())
    assert data[KEY] == {"fields": {"merged": True}, "note": "thread says merged", "author": "test"}


def test_import_validates_everything_before_writing(db_session, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "practice:1": {"fields": {"skip": True}, "note": "dup post"},
        "practice:2": {"fields": {"skip": "nope"}, "note": "bad"}}))
    with pytest.raises(CorrectionError):
        import_corrections(bad)
    assert "practice:1" not in load_corrections()
```

Add to `tests/analytics/test_rebuild.py`:

```python
def test_rebuild_applies_db_corrections(db_session):
    from app.analytics.corrections import upsert_correction
    _seed()
    upsert_correction(f"{CH}:4087911600.000100", {"merged": True}, "test merge", "test")
    rebuild(commit=False)
    s = PracticeSession.query.filter_by(session_key=f"{CH}:4087911600.000100:merged").one()
    assert s.format == "merged" and s.rsvp_count == 3
```

- [ ] **Step 2: Run, expect ImportError. Step 3: implement `corrections.py` and `rebuild.py`. Step 4: run both test files, expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add app/analytics/rebuild.py app/analytics/corrections.py tests/analytics/test_rebuild.py tests/analytics/test_corrections.py
git commit -m "feat(analytics): DB-backed corrections and transactional rebuild"
```

---

### Task 10: Weather

**Files:**
- Create: `app/analytics/weather.py`, `tests/analytics/fixtures/openmeteo_sample.json`, `tests/analytics/test_weather.py`
- Modify: `app/analytics/rebuild.py` (call `apply_weather` for real)

**Docs to read first:** https://open-meteo.com/en/docs/historical-weather-api (variables, `hourly_units`, `timezone`, unit parameters, the archive's ~5-day delay). `app/integrations/daylight.py` (`get_daylight_info(lat, lon, date).sunset` is tz-aware).

**Interfaces:**
- Produces:
  - `OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"`
  - `HOURLY_VARS = ("temperature_2m", "apparent_temperature", "precipitation", "snowfall", "snow_depth", "wind_speed_10m", "weather_code")`
  - `fetch_hours(lat: float, lon: float, start: date, end: date, *, http_get=requests.get) -> list[dict]`. Each dict has `hour_local` (naive Central), `temp_f`, `feels_like_f`, `precip_in`, `snowfall_in`, `snow_depth_in`, `wind_mph`, `weather_code`. Returns `[]` on any failure.
  - `to_inches(value, unit: str) -> float | None` handling `mm`, `cm`, `m`, `inch`.
  - `session_weather(start: datetime, hours: dict[datetime, WeatherHour-like]) -> dict` computing the session columns (start hour values; precip and snowfall summed over the start hour and the next hour; snowfall summed over the 24 hours before the start hour; snow depth at the start hour).
  - `apply_weather(sessions: list[PracticeSession]) -> int` fills weather and `minutes_after_sunset` from `weather_hours` for sessions with `lat`/`lon`, `date` and `start_time`. No network. Returns the count filled.
  - `fetch_missing_weather(*, today: date | None = None, http_get=requests.get) -> dict` finds sessions dated on or before `today - 6 days` whose start hour is not cached, groups them by `(round(lat, 2), round(lon, 2))`, fetches one date range per group (min date − 1 day to max date), upserts `weather_hours`, then runs `apply_weather` on those sessions and commits. Returns `{"locations": n, "hours": n, "sessions": n, "errors": n}`.

Rules: request `temperature_unit=fahrenheit`, `wind_speed_unit=mph`, `precipitation_unit=inch`, `timezone=America/Chicago`. Read each variable's unit from `hourly_units` and convert with `to_inches` (snow depth arrives in feet when precipitation_unit=inch, verified live). A non-200 response, JSON error, missing `hourly` key, or unknown unit is logged and returns `[]`.

- [ ] **Step 1: Fixture**

`tests/analytics/fixtures/openmeteo_sample.json`: a hand-written response in the documented shape for 2099-12-20, 26 hours starting at 2099-12-19T22:00, with `hourly_units` `{"temperature_2m": "°F", "apparent_temperature": "°F", "precipitation": "inch", "snowfall": "inch", "snow_depth": "m", "wind_speed_10m": "mp/h", "weather_code": "wmo code"}`. Values: temperature -2.7 at 18:00 on 12-20, snow_depth 0.689 (m) at 18:00, snowfall 0.1 at 17:00 and 0.2 at 19:00 and 0.3 at 20:00, precipitation 0.02 at 18:00 and 0.03 at 19:00, weather_code 71 at 18:00, zeros elsewhere.

- [ ] **Step 2: Failing tests**

`tests/analytics/test_weather.py`:

```python
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.analytics.weather import fetch_hours, session_weather, to_inches
from tests.analytics.conftest import load_fixture


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def test_units_read_from_response():
    hours = fetch_hours(44.98, -93.32, date(2099, 12, 20), date(2099, 12, 20),
                        http_get=lambda *a, **k: Resp(200, load_fixture("openmeteo_sample.json")))
    h = {x["hour_local"]: x for x in hours}[datetime(2099, 12, 20, 18)]
    assert h["temp_f"] == pytest.approx(-2.7)
    assert h["snow_depth_in"] == pytest.approx(0.689 * 39.3701, rel=1e-3)
    assert h["weather_code"] == 71


@pytest.mark.parametrize("resp", [Resp(500, {}), Resp(200, ValueError("bad json")), Resp(200, {"error": True})])
def test_fetch_failure_writes_nothing(resp):
    assert fetch_hours(1, 2, date(2099, 1, 1), date(2099, 1, 1), http_get=lambda *a, **k: resp) == []


def test_to_inches():
    assert to_inches(25.4, "mm") == pytest.approx(1)
    assert to_inches(2.54, "cm") == pytest.approx(1)
    assert to_inches(1, "inch") == 1
    assert to_inches(None, "mm") is None


def test_session_window_math():
    hours = {x["hour_local"]: SimpleNamespace(**x) for x in fetch_hours(
        0, 0, date(2099, 12, 20), date(2099, 12, 20),
        http_get=lambda *a, **k: Resp(200, load_fixture("openmeteo_sample.json")))}
    w = session_weather(datetime(2099, 12, 20, 18, 15), hours)
    assert w["temp_f"] == pytest.approx(-2.7)
    assert w["precip_in"] == pytest.approx(0.05)          # 18:00 + 19:00
    assert w["snowfall_in"] == pytest.approx(0.2)         # 18:00 (0) + 19:00 (0.2)
    assert w["snowfall_prior_24h_in"] == pytest.approx(0.1)  # 17:00 only in the prior 24 h
```

- [ ] **Step 3: Run, expect ImportError. Step 4: implement. Step 5: wire `apply_weather` into `rebuild()` and rerun `tests/analytics/test_rebuild.py`. Expect PASS.**

- [ ] **Step 6: Commit**

```bash
git add app/analytics/weather.py app/analytics/rebuild.py tests/analytics/fixtures/openmeteo_sample.json tests/analytics/test_weather.py
git commit -m "feat(analytics): Open-Meteo weather cache and per-session weather"
```

---

### Task 11: CLI and nightly job

**Files:**
- Create: `app/analytics/cli.py`, `app/analytics/jobs.py`, `tests/analytics/test_cli_and_job.py`
- Modify: `app/__init__.py` (register the CLI group after the blueprints: `from .analytics.cli import analytics_cli` then `app.cli.add_command(analytics_cli)`), `app/scheduler.py` (job function near `run_season_recap_job` and its registration before `scheduler.start()`)

**Docs to read first:** Flask CLI https://flask.palletsprojects.com/en/stable/cli/ (custom commands, `AppGroup`), APScheduler 3 cron trigger https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html.

**Interfaces:**
- Produces:
  - `analytics_cli = AppGroup("analytics")` with commands `import-slack --channel ID [--token bot|user]`, `sync [--days 21]`, `rebuild`, `fetch-weather`, `flags [--json PATH]`, `nightly`, `set-coach-emoji NAMES` (comma-separated, writes AppConfig `analytics_coach_emoji` with category `analytics`), and a `corrections` subgroup: `corrections list`, `corrections import PATH` (commits, then prints the count), `corrections export PATH`.
  - `flags --json PATH` writes the flagged sessions and possible misses as JSON for the fixer agents: for each flagged session `{session_key, post_key, date, title, flags, format, rsvp_count, text, replies: [text...]}`, where `text` and `replies` come from the archive. For each miss: `{post_key, date, text, reactions: {emoji: count}}`.
  - `run_nightly(*, client=None, http_get=None) -> dict`: sync (bot client from `get_slack_client()` when `client` is None), commit, rebuild, fetch_missing_weather. `jobs.py` imports `sync_recent`, `rebuild` and `fetch_missing_weather` at module level so tests can patch them on `app.analytics.jobs`. On the first failing step it rolls back, logs, and returns exactly `{"step": "sync"|"rebuild"|"weather", "ok": False, "error": str(exc)}`. On success it returns `{"step": "done", "ok": True, "sync": ..., "rebuild": ..., "weather": ...}`.
  - `app.scheduler.run_analytics_nightly_job(app)` wrapper, and job id `analytics_nightly` at 03:30 America/Chicago, `misfire_grace_time=3600`.

`flags` prints one line per `needs_review` session (`date  session_key  flags  title`) and then one line per possible miss, and exits 0. `import-slack` prints the stats and commits once at the end.

- [ ] **Step 1: Failing tests**

`tests/analytics/test_cli_and_job.py`:

```python
from unittest.mock import MagicMock, patch


def test_cli_group_registered(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["analytics", "--help"])
    assert result.exit_code == 0
    for cmd in ("import-slack", "sync", "rebuild", "fetch-weather", "flags", "nightly", "corrections"):
        assert cmd in result.output


def test_nightly_stops_at_first_failure(app):
    from app.analytics import jobs
    with app.app_context(), \
         patch.object(jobs, "sync_recent", side_effect=RuntimeError("slack down")), \
         patch.object(jobs, "rebuild") as rebuild:
        out = jobs.run_nightly(client=MagicMock())
    assert out == {"step": "sync", "ok": False, "error": "slack down"}
    rebuild.assert_not_called()


def test_nightly_runs_all_steps(app):
    from app.analytics import jobs
    with app.app_context(), \
         patch.object(jobs, "sync_recent", return_value={}), \
         patch.object(jobs, "rebuild", return_value={"sessions": 1}), \
         patch.object(jobs, "fetch_missing_weather", return_value={"sessions": 0}):
        out = jobs.run_nightly(client=MagicMock())
    assert out["ok"] is True and out["step"] == "done"


def test_scheduler_registers_nightly_job():
    import inspect
    import app.scheduler as sched
    src = inspect.getsource(sched.init_scheduler)
    assert "run_analytics_nightly_job" in src and "'analytics_nightly'" in src
```

- [ ] **Step 2: Run, expect failures. Step 3: implement. Step 4: run the new tests plus `tests/test_scheduler_*.py`. Expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add app/analytics/cli.py app/analytics/jobs.py app/__init__.py app/scheduler.py tests/analytics/test_cli_and_job.py
git commit -m "feat(analytics): flask analytics CLI and nightly sync-rebuild-weather job"
```

---

### Task 12 (orchestrator): PR 1, prod import, corrections

- [ ] **Step 1:** Run the whole analytics suite and the suites touched: `DATABASE_URL=...tcsc_trips_test pytest tests/analytics tests/slack/test_reaction_rsvp.py tests/practices/test_practice_migration_release.py tests/test_scheduler_*.py -q`. Then run the full suite once and compare failures against `main` (pre-existing failures are not this PR's).
- [ ] **Step 2:** Request code review (superpowers:requesting-code-review). Open PR 1 with `gh pr create`. The body lists the tables, the one bolt_app touch, and the post-merge import runbook below.
- [ ] **Step 3: After Rob merges and Render deploys**, from the dev box, against prod:

```bash
cd /workspace/tcsc-trips && set -a && source .env && set +a
export DATABASE_URL="$PROD_DATABASE_URL" TCSC_MIGRATION_ONLY=1; unset SLACK_APP_TOKEN
flask analytics set-coach-emoji <comma-separated emoji names>   # AppConfig analytics_coach_emoji, never in the repo
flask analytics import-slack --channel C042G463AQ1
flask analytics import-slack --channel C047BRZH1LG
flask analytics import-slack --channel C03FKTTHNHW --token user
flask analytics rebuild
flask analytics fetch-weather
flask analytics flags > .superpowers/analytics-slack-dump/flags-$(date +%F).txt
```

(Memory `prod-one-off-scripts.md`: `create_app` starts the scheduler and Socket Mode unless `TCSC_MIGRATION_ONLY=1` and `SLACK_APP_TOKEN` is unset.)

- [ ] **Step 4: Import the corrections found during Task 8**, then rebuild: `flask analytics corrections import .superpowers/analytics-slack-dump/corrections.json && flask analytics rebuild`.
- [ ] **Step 5: Agents clear the remaining flags.** Rob's rule: agents fix the data and check themselves. Only what they truly cannot settle goes to Rob.
  1. `flask analytics flags --json .superpowers/analytics-slack-dump/flags.json` (against prod, as in Step 3).
  2. Split `flags.json` into batches of about 40 items. For each batch, dispatch a **fixer** agent (Claude subagent, not Codex, since no code is written). It gets the spec's parsing rules, `CORRECTION_FIELDS` with their meanings, the batch, and read-only access to the dump folder. For each item it returns one of: a correction `{key, fields, note}`, `"parser"` (a pattern the parser should handle, with a one-line rule), `"ok"` (the flag is harmless; becomes `{"ok": true}`), or `"needs_rob"` with the question. Every note cites the post text or reply that justifies it.
  3. Dispatch a **reviewer** agent per batch. It gets the same inputs plus the fixer's output. It checks every proposal against the raw post and thread and returns accept / reject (with reason) per item. Rejected items go back to a fresh fixer once. Anything still disputed after that becomes `needs_rob`.
  4. Merge the accepted corrections into `corrections.json`, `flask analytics corrections import` it, and rebuild. `"parser"` items become a small parser PR written by a Codex worker with a test per pattern.
  5. Repeat from 1 until `flags` lists only `needs_rob` items. Send those to Rob as one short list, each with the post date, what is unclear, and the proposed answer.
  6. Export the final table (`flask analytics corrections export .superpowers/analytics-slack-dump/corrections.json`) so the local acceptance test uses the same corrections as prod.

---

# Part 2: dashboards (PR 2)

Branch PR 2 from `main` after PR 1 merges, or stack it on PR 1's branch if Rob prefers one review.

### Task 13: Chart kit, vendored Vega, dashboard base, routes, template, JS

This is one task because none of the pieces is reviewable alone. The deliverable is an Analytics section that renders a test dashboard end to end.

**Files:**
- Create: `app/static/vendor/vega@6.4.0.min.js`, `app/static/vendor/vega-lite@6.4.3.min.js`, `app/static/vendor/vega-embed@7.3.0.min.js` (use the latest 6.x / 6.x / 7.x at build time and put the exact versions in the filenames), `tests/analytics/fixtures/vega-lite-v6.schema.json`, `app/analytics/charts.py`, `app/analytics/dashboards/__init__.py`, `app/analytics/dashboards/base.py`, `app/routes/admin_analytics.py`, `app/templates/admin/analytics/index.html`, `app/templates/admin/analytics/dashboard.html`, `app/static/admin_analytics.js`, `tests/analytics/test_charts.py`, `tests/analytics/test_dashboard_base.py`, `tests/analytics/test_admin_analytics_routes.py`, `tests/js/admin_analytics.test.js`
- Modify: `app/__init__.py` (register `admin_analytics_bp`), `app/templates/admin/partials/sidebar.html` (new "Analytics" section after "Practices", one link, active when `request.blueprint == 'admin_analytics'`, chart-bar heroicon outline like the others), `package.json` (`"test:analytics": "node --test tests/js/admin_analytics.test.js"`)

**Docs to read first:** Vega-Lite https://vega.github.io/vega-lite/docs/ (mark, bar, rule, text, layer, stack, config, size and autosize, `description`), schema https://vega.github.io/schema/vega-lite/v6.json, vega-embed options https://github.com/vega/vega-embed#options, vl-convert https://github.com/vega/vl-convert (Python `vl_convert.vegalite_to_png`), jsonschema https://python-jsonschema.readthedocs.io/. Also load the `dataviz` skill before choosing colors or chart forms.

**Interfaces:**
- `charts.py`:
  - `PALETTE = {"navy": "#1c2c44", "early": "#2a78d6", "late": "#eb6834", "single": "#8e949a", "ref": "#6b7076", "grid": "#e3e5e6", "ink": "#1c2c44", "muted": "#6b7280"}` (validate contrast with the dataviz skill's checker and adjust if it fails)
  - `theme() -> dict` (Vega-Lite `config`: system font stack from `tailwind.config.js`, axis and grid colors, no chart border, `view.stroke` null)
  - `stacked_columns(rows, *, x, y, color, color_domain, color_range, x_title, y_title, tooltip, height=280, x_type="ordinal", x_sort=None) -> dict`
  - `grouped_bars(rows, *, x, y, color, color_domain, color_range, x_title, y_title, tooltip, height=260) -> dict`
  - `line(rows, *, x, y, color, x_title, y_title, tooltip, height=260) -> dict`
  - `reference_lines(lines: list[dict]) -> list[dict]` (`{"value", "label"}` each; returns a rule layer and a text layer)
  - `layered(base: dict, *extra_layers) -> dict` (wraps `base` and the extras in one `layer` spec, keeps `data` at the top, sets `$schema`, `width: "container"`, `description`)
  - `spec(description: str, body: dict) -> dict` (adds `$schema: https://vega.github.io/schema/vega-lite/v6.json`, `config: theme()`, `description`, `autosize: {"type": "fit-x", "contains": "padding"}`)
- `dashboards/base.py`:
  - Blocks: `Tile(label, value, sub="")`, `Tiles(tiles)`, `Chart(title, description, spec, rows, columns)` where `columns` is a list of `(key, label)`, `Table(title, rows, columns)`, `Note(text)`. Each has a `kind` class attribute (`"tiles"`, `"chart"`, `"table"`, `"note"`).
  - `Dashboard(slug, title, question, filters: list[str], build, fixed: dict = {}, defaults: dict = {})`
  - `Filters` dataclass: `seasons: list[str]`, `date_from: date | None`, `date_to: date | None`, `days: list[str]`, `activities: list[str]`, `workout_types: list[str]`, `location_ids: list[int]`, `formats: list[str]`, `kinds: list[str]`
  - `FILTER_NAMES = ("season", "date_range", "day_of_week", "activity", "workout_type", "location", "format", "kind")`
  - `parse_filters(args: MultiDict, dashboard: Dashboard) -> Filters`. Only the dashboard's allowed filters are read. Each value is validated against its allowed set: days are weekday names; formats are single/split/merged; kinds are practice/event; seasons, activities and workout types must exist in `practice_sessions`; location ids are ints that exist; dates are ISO. Invalid values are dropped. `fixed` overrides the request, and `defaults` apply when the request gives nothing for that filter. `kinds` defaults to `["practice"]`.
  - `apply_filters(query, filters) -> query` on `PracticeSession`
  - `load_sessions(filters) -> list[PracticeSession]` ordered by date, start_time
  - `load_attendance(session_ids: list[int], role="rsvp") -> list[PracticeAttendance]`
  - `filter_options(dashboard) -> dict` (distinct seasons newest first, activities, workout types, locations `(id, name)`, days in Monday order, formats)
  - `footer() -> dict` with `data_through` (Central string of `max(SlackArchiveMessage.synced_at)`, or None) and `needs_review` (count)
- `dashboards/__init__.py`: `DASHBOARDS: list[Dashboard]`, `get_dashboard(slug) -> Dashboard | None`. It starts empty in this task; tests register a stub.
- Routes, blueprint `admin_analytics` with `url_prefix="/admin/analytics"`, all `@admin_required`. The routes call `dashboards.get_dashboard(...)`, `base.parse_filters(...)`, `base.filter_options(...)` and `base.footer()` through the module objects (`from app.analytics import dashboards` and `from app.analytics.dashboards import base`), never through `from ... import name`, because the tests patch them on those modules:
  - `GET /` → `analytics.index`: cards (title, question, link)
  - `GET /<slug>` → `analytics.dashboard`: 404 for unknown slugs; renders `dashboard.html` with `dashboard`, `blocks`, `filters`, `options`, `footer`, `request_args`
- `dashboard.html` extends `admin/admin_base.html`. It has a title, the question as the subtitle, and a filter form (`method="get"`: multi-select pills for seasons, days and formats; two date inputs; an "Apply" button and a "Reset" link to the bare URL). Blocks render in order:
  - tiles: a responsive grid, 2 columns on phones and 4 on desktop
  - chart: a card with title and description, then `<div class="analytics-chart" data-spec-id="spec-N" role="img" aria-label="{{ block.description }}">`, then `<script type="application/json" id="spec-N">{{ block.spec|tojson }}</script>`, then `<details><summary>Show data</summary><table class="analytics-table">…</table></details>`
  - table: a card with a sortable `analytics-table`
  - note: muted text

  The footer reads: "Data through {{ footer.data_through }} · RSVPs are not headcount · {{ footer.needs_review }} sessions need review". Load the three vendored scripts, then `admin_analytics.js`, in `{% block extra_js %}`, only on this template.
- `admin_analytics.js` (vanilla, UMD-style export for node tests like `practice_plan_reactions.js`):
  - `embedAll(root, vegaEmbed)`: for each `.analytics-chart`, parse its JSON script, set `spec.width` to the element's `clientWidth` minus 8, and call `vegaEmbed(el, spec, {renderer: "svg", actions: false, ast: true})` (`ast: true` because the admin CSP has no `unsafe-eval`). On a rejected promise, set `el.textContent = "This chart could not be drawn. The table below has the same numbers."`
  - `watchResize(root, vegaEmbed)`: a ResizeObserver, debounced 150 ms, that re-embeds a chart when its width changes by more than 8 px
  - `sortTable(table, colIndex)`: numeric-aware, toggles asc/desc, sets `aria-sort`, and is attached on `th` click and Enter key
  - Auto-init on `DOMContentLoaded` when `window.vegaEmbed` exists

- [ ] **Step 1: Vendor the libraries and schema**

```bash
cd app/static/vendor
curl -fsSLo vega@6.4.0.min.js https://cdn.jsdelivr.net/npm/vega@6.4.0/build/vega.min.js
curl -fsSLo vega-lite@6.4.3.min.js https://cdn.jsdelivr.net/npm/vega-lite@6.4.3/build/vega-lite.min.js
curl -fsSLo vega-embed@7.3.0.min.js https://cdn.jsdelivr.net/npm/vega-embed@7.3.0/build/vega-embed.min.js
curl -fsSLo ../../../tests/analytics/fixtures/vega-lite-v6.schema.json https://vega.github.io/schema/vega-lite/v6.json
head -c 200 vega@6.4.0.min.js   # confirm it is JavaScript, not an HTML error page
```

If a version 404s, use `npm view vega version` (and likewise for the others) and use those exact versions everywhere.

- [ ] **Step 2: Failing Python tests**

`tests/analytics/test_charts.py`:

```python
import json

import jsonschema
import pytest

from app.analytics import charts
from tests.analytics.conftest import FIXTURES

SCHEMA = json.loads((FIXTURES / "vega-lite-v6.schema.json").read_text())
ROWS = [{"week": "2099-01-05", "slot": "Early", "rsvps": 20},
        {"week": "2099-01-05", "slot": "Late", "rsvps": 12}]


def _check(spec):
    jsonschema.validate(spec, SCHEMA)
    import vl_convert as vlc
    png = vlc.vegalite_to_png(json.dumps({**spec, "width": 600}))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_stacked_columns_with_reference_lines_validates_and_renders():
    base = charts.stacked_columns(
        ROWS, x="week", y="rsvps", color="slot", color_domain=["Early", "Late"],
        color_range=[charts.PALETTE["early"], charts.PALETTE["late"]],
        x_title="Week", y_title="RSVPs", tooltip=["week", "slot", "rsvps"])
    s = charts.spec("RSVPs per week", charts.layered(
        base, *charts.reference_lines([{"value": 27, "label": "27 split rule"}])))
    assert s["description"] == "RSVPs per week"
    _check(s)


@pytest.mark.parametrize("builder", ["grouped_bars", "line"])
def test_other_builders_validate(builder):
    fn = getattr(charts, builder)
    s = charts.spec("x", fn(ROWS, x="week", y="rsvps", color="slot",
                            **({"color_domain": ["Early", "Late"],
                                "color_range": ["#000", "#111"]} if builder == "grouped_bars" else {}),
                            x_title="Week", y_title="RSVPs", tooltip=["rsvps"]))
    _check(s)
```

`tests/analytics/test_dashboard_base.py` covers `parse_filters` (valid values kept, junk dropped, `fixed` wins, `defaults` apply only when empty) with `get_filter_domains` patched to return fixed domains, so no DB is needed. Name the internal domain loader `get_filter_domains() -> dict` and patch it.

```python
from datetime import date
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

from app.analytics.dashboards.base import Dashboard, parse_filters

DOMAINS = {"seasons": {"2025 Fall/Winter", "2026 Spring/Summer"}, "activities": {"Strength", "Run"},
           "workout_types": {"Circuit"}, "location_ids": {38}}
D = Dashboard(slug="t", title="T", question="Q?",
              filters=["season", "date_range", "day_of_week", "format"],
              build=lambda f: [], fixed={"activities": ["Strength"]}, defaults={"days": ["Thursday"]})


def _parse(**args):
    with patch("app.analytics.dashboards.base.get_filter_domains", return_value=DOMAINS):
        return parse_filters(MultiDict(args), D)


def test_invalid_values_dropped_and_defaults_applied():
    f = _parse(season=["2025 Fall/Winter", "<script>"], date_from="notadate", format=["split", "bogus"])
    assert f.seasons == ["2025 Fall/Winter"] and f.date_from is None and f.formats == ["split"]
    assert f.days == ["Thursday"] and f.activities == ["Strength"] and f.kinds == ["practice"]


def test_request_overrides_defaults_but_not_fixed():
    f = _parse(day_of_week=["Wednesday", "Friday"], activity=["Run"], date_from="2025-05-01")
    assert f.days == ["Wednesday", "Friday"] and f.activities == ["Strength"]
    assert f.date_from == date(2025, 5, 1)
```

`tests/analytics/test_admin_analytics_routes.py`:

```python
from unittest.mock import patch

import pytest

from app.analytics.dashboards import base
from app.analytics import dashboards
from app.analytics.dashboards.base import Chart, Dashboard, Note, Tile, Tiles


def _build(filters):
    return [Tiles([Tile("Average", "41.6", "RSVPs a week")]),
            Chart("Weekly", "Weekly RSVPs", {"$schema": "https://vega.github.io/schema/vega-lite/v6.json",
                                              "mark": "bar", "data": {"values": []}},
                  rows=[{"week": "2099-01-05", "rsvps": 3}], columns=[("week", "Week"), ("rsvps", "RSVPs")]),
            Note("RSVPs are not headcount.")]


STUB = Dashboard(slug="stub", title="Stub", question="Does it render?",
                 filters=["season", "date_range"], build=_build)


@pytest.fixture(autouse=True)
def registry():
    with patch.object(dashboards, "DASHBOARDS", [STUB]), \
         patch.object(base, "get_filter_domains", return_value={"seasons": set(), "activities": set(),
                                                               "workout_types": set(), "location_ids": set()}), \
         patch.object(base, "footer", return_value={"data_through": "Sep 24, 2099", "needs_review": 3}), \
         patch.object(base, "filter_options", return_value={"seasons": [], "days": [], "formats": []}):
        yield


def test_requires_admin(client):
    assert client.get("/admin/analytics/").status_code in (302, 401)


def test_index_lists_dashboards(admin_client):
    r = admin_client.get("/admin/analytics/")
    assert r.status_code == 200 and b"Does it render?" in r.data


def test_dashboard_renders_blocks_and_footer(admin_client):
    r = admin_client.get("/admin/analytics/stub")
    html = r.data.decode()
    assert r.status_code == 200
    assert "41.6" in html and 'class="analytics-chart"' in html and "Show data" in html
    assert "3 sessions need review" in html and "RSVPs are not headcount" in html
    assert "vega-embed@" in html


def test_invalid_filter_values_are_ignored(admin_client):
    r = admin_client.get("/admin/analytics/stub?season=%3Cscript%3E&date_from=notadate&date_to=2099-99-99")
    assert r.status_code == 200 and b"<script>alert" not in r.data


def test_unknown_slug_404(admin_client):
    assert admin_client.get("/admin/analytics/nope").status_code == 404
```

- [ ] **Step 3: Failing JS test**

`tests/js/admin_analytics.test.js`:

```javascript
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const A = require('../../app/static/admin_analytics.js');

function dom(html) {
  const d = new JSDOM(`<!doctype html><body>${html}</body>`);
  return d.window.document;
}

test('embedAll passes parsed spec with measured width and svg renderer', async () => {
  const doc = dom('<div class="analytics-chart" data-spec-id="spec-1"></div>' +
    '<script type="application/json" id="spec-1">{"mark":"bar"}</script>');
  const el = doc.querySelector('.analytics-chart');
  Object.defineProperty(el, 'clientWidth', {value: 408});
  const calls = [];
  await A.embedAll(doc, (target, spec, opts) => { calls.push([target, spec, opts]); return Promise.resolve(); });
  assert.equal(calls.length, 1);
  assert.equal(calls[0][1].width, 400);
  assert.deepEqual(calls[0][2], {renderer: 'svg', actions: false});
});

test('embed failure shows fallback text', async () => {
  const doc = dom('<div class="analytics-chart" data-spec-id="s"></div><script type="application/json" id="s">{}</script>');
  await A.embedAll(doc, () => Promise.reject(new Error('x')));
  assert.match(doc.querySelector('.analytics-chart').textContent, /could not be drawn/);
});

test('sortTable sorts numerically and toggles', () => {
  const doc = dom('<table><thead><tr><th>Week</th><th>RSVPs</th></tr></thead><tbody>' +
    '<tr><td>a</td><td>9</td></tr><tr><td>b</td><td>30</td></tr><tr><td>c</td><td>12</td></tr></tbody></table>');
  const table = doc.querySelector('table');
  A.sortTable(table, 1);
  assert.deepEqual([...table.querySelectorAll('tbody td:nth-child(2)')].map(td => td.textContent), ['9', '12', '30']);
  A.sortTable(table, 1);
  assert.deepEqual([...table.querySelectorAll('tbody td:nth-child(2)')].map(td => td.textContent), ['30', '12', '9']);
  assert.equal(table.querySelectorAll('th')[1].getAttribute('aria-sort'), 'descending');
});
```

- [ ] **Step 4: Run all, expect failures.** `pytest tests/analytics/test_charts.py tests/analytics/test_dashboard_base.py tests/analytics/test_admin_analytics_routes.py -v` and `node --test tests/js/admin_analytics.test.js`

- [ ] **Step 5: Implement everything in this task. Run until green.**

- [ ] **Step 6: Commit**

```bash
git add app/static/vendor app/analytics/charts.py app/analytics/dashboards app/routes/admin_analytics.py app/templates/admin/analytics app/static/admin_analytics.js app/__init__.py app/templates/admin/partials/sidebar.html package.json tests/analytics/fixtures/vega-lite-v6.schema.json tests/analytics/test_charts.py tests/analytics/test_dashboard_base.py tests/analytics/test_admin_analytics_routes.py tests/js/admin_analytics.test.js
git commit -m "feat(analytics): admin Analytics section, chart kit and dashboard framework"
```

---

### Task 14: Thursday strength dashboard

**Files:**
- Create: `app/analytics/dashboards/thursday_strength.py`, `tests/analytics/test_thursday_strength.py`
- Modify: `app/analytics/dashboards/__init__.py` (register it)

**Docs to read first:** the same Vega-Lite pages as Task 13, plus the `dataviz` skill.

**Interfaces:**
- Consumes: `charts.*`, `base.Dashboard/Tile/Tiles/Chart/Table/Note/load_sessions/load_attendance`, `load_history_config().capacity_lines`.
- Produces: `DASHBOARD` with slug `thursday-strength`, title "Thursday strength", question "Should Thursday strength run as one session or two?", filters `["season", "date_range", "day_of_week", "format"]`, `fixed={"activities": ["Strength"], "kinds": ["practice"]}`, `defaults={"days": ["Thursday"]}`. Also the pure helpers `weekly_totals(sessions, attendance) -> list[dict]`, `season_summary(weeks, lines) -> list[dict]`, `slot_preference(sessions, attendance) -> list[dict]`, `week_of_season(weeks) -> list[dict]`.

Definitions:
- A session's counts: `early` = distinct rsvp uids with `slot == "early"`, `late` = distinct uids with `slot == "late"`, `single` = distinct rsvp uids on single sessions. For split and merged sessions, `total = early + late` (a person reacting to both counts once in each, which matches how the verified data counted). For single sessions, `total = single`.
- Week = Monday-start week of `date`. `weekly_totals` sums totals per week and keeps `season_label` and the week's formats.
- Capacity lines shown: every YAML line without a `to` date (the 27 split rule and the 35 one-session size are the reference points for the decision whatever range is selected), plus bounded lines whose `from`/`to` overlap the selected sessions' dates. Tiles and chart rules use the same list.
- `thursday_strength.py` imports `load_sessions` and `load_attendance` into its own namespace (`from app.analytics.dashboards.base import load_sessions, load_attendance`) so tests patch them on the module. `build(filters)` trusts the loaders to have applied the filters and does not filter again.

Blocks, in order:
1. `Tiles`:
   - "Average per week": weekly mean to 1 decimal, sub "RSVPs a week, peak N"
   - one tile per capacity line in effect: "Weeks over {value}" as "k of n", sub = the line label
   - "Late session share": late / (early + late) over split weeks only, as a percent, sub "of two-session RSVPs"
   - "Latest week": the total, sub "Same week last year: N" when a week within ±3 days of 364 days earlier exists
2. `Chart` "Every strength session": stacked columns per session (x = date label, color Early/Late/Single, with merged sessions marked by a `point` layer under the column in a ring style), plus capacity rules. Its rows table shows date, format, early, late, single, total, status.
3. `Chart` "Season by season": grouped bars of average and peak per week by season. It includes a `Table` with season, weeks, avg, peak, weeks over each line, and late %.
4. `Chart` "This season against last": `line` of weekly totals by week-of-season (1, 2, …) for the latest season label and the same season type one year earlier.
5. `Chart` "Who picks which slot": grouped bars per season of people who only chose early, only chose late, or both (from split and merged sessions). Counts only.
6. `Note`: "RSVPs are not headcount. Some people RSVP and skip, some come without reacting, and leads often don't react."
7. `Note`: "Merges happened on nights with low RSVPs, so merged weeks averaging fewer people does not mean merging lowers turnout."

Every chart's description is one plain sentence naming what is plotted.

- [ ] **Step 1: Failing tests**

`tests/analytics/test_thursday_strength.py` uses a small made-up season (no real data in the repo): four Thursdays with early/late RSVPs of (20, 10), (25, 15), (18, 17), (30, 20). Weekly totals are 30, 40, 35 and 50, so the average is 38.8, the peak is 50, 4 of 4 weeks are over 27, 2 of 4 are over 35 (35 itself is not over), and the late share is 62 / 155 = 40%.

```python
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.analytics.dashboards import thursday_strength as ts
from app.analytics.dashboards.base import Chart, Filters, Tiles

WEEKS = [(20, 10), (25, 15), (18, 17), (30, 20)]
FIRST = date(2099, 9, 17)   # a Thursday


def _data():
    sessions, attendance = [], []
    for i, (early, late) in enumerate(WEEKS):
        d = FIRST + timedelta(weeks=i)
        sessions.append(SimpleNamespace(id=i, date=d, format="split", status="held",
                                        season_label="2099 Fall/Winter", day_of_week="Thursday",
                                        start_time=None))
        for slot, n in (("early", early), ("late", late)):
            attendance += [SimpleNamespace(session_id=i, slack_uid=f"U{i}{slot}{k}", slot=slot, role="rsvp")
                           for k in range(n)]
    return sessions, attendance


@pytest.fixture
def blocks():
    sessions, attendance = _data()
    with patch.object(ts, "load_sessions", return_value=sessions), \
         patch.object(ts, "load_attendance", return_value=attendance):
        yield ts.DASHBOARD.build(Filters(seasons=[], date_from=None, date_to=None, days=["Thursday"],
                                         activities=["Strength"], workout_types=[], location_ids=[],
                                         formats=[], kinds=["practice"]))


def test_tiles(blocks):
    tiles = {t.label: t for t in next(b for b in blocks if isinstance(b, Tiles)).tiles}
    assert tiles["Average per week"].value == "38.8"
    assert "peak 50" in tiles["Average per week"].sub
    assert tiles["Weeks over 27"].value == "4 of 4"
    assert tiles["Weeks over 35"].value == "2 of 4"
    assert tiles["Late session share"].value == "40%"
    assert "Weeks over 30" not in tiles   # the bounded Dec 2025 cap does not overlap 2099


def test_every_chart_has_rows_and_a_valid_spec(blocks):
    import json, jsonschema
    from tests.analytics.conftest import FIXTURES
    schema = json.loads((FIXTURES / "vega-lite-v6.schema.json").read_text())
    charts = [b for b in blocks if isinstance(b, Chart)]
    assert len(charts) == 4
    for c in charts:
        jsonschema.validate(c.spec, schema)
        assert c.rows and c.description


def test_slot_preference_counts_people_not_rsvps():
    sessions = [SimpleNamespace(id=1, format="split", season_label="2099 Fall/Winter"),
                SimpleNamespace(id=2, format="merged", season_label="2099 Fall/Winter")]
    att = [SimpleNamespace(session_id=1, slack_uid="A", slot="early", role="rsvp"),
           SimpleNamespace(session_id=2, slack_uid="A", slot="late", role="rsvp"),
           SimpleNamespace(session_id=1, slack_uid="B", slot="late", role="rsvp")]
    got = {r["preference"]: r["people"] for r in ts.slot_preference(sessions, att)}
    assert got == {"Both": 1, "Late only": 1, "Early only": 0}
```

- [ ] **Step 2: Run, expect failures. Step 3: implement. Step 4: run, expect PASS. Also render each chart to PNG with vl-convert into the scratchpad and look at them (orchestrator step).**

- [ ] **Step 5: Commit**

```bash
git add app/analytics/dashboards/thursday_strength.py app/analytics/dashboards/__init__.py tests/analytics/test_thursday_strength.py
git commit -m "feat(analytics): Thursday strength dashboard"
```

---

### Task 15 (orchestrator): visual check, review, PR 2

- [ ] **Step 1:** Run the dev server in a herdr pane against the scratch DB with a rebuilt lineage. Take headless Chromium screenshots of `/admin/analytics/thursday-strength` at 360, 390 and 1280 px (project memories `headless-chromium-screenshots.md` and `verify-against-what-production-serves.md`). Check that there is no horizontal page scroll at 360, that the tiles wrap to 2 columns, that the charts fit, and that the tables open.
- [ ] **Step 2:** Run the full test suite and `npm run test:analytics`. Request a code review. Open PR 2 with screenshots in the body.
- [ ] **Step 3:** After deploy, open the prod dashboard and confirm the fall 2025 tiles read 41.6 / 8 of 10 / 43%, and that the footer's review count is 0.

---

## Self-review notes

- Spec coverage: archive (Tasks 1, 4, 12), event log (5), lineage schema and rules (1, 2, 3, 6, 7, 8), rebuild (9), weather (10), YAML (3, 8, 12), CLI and nightly (11), dashboard framework (13), lift dashboard (14), footer (13), public-repo fixtures (Global Constraints, 6, 8), docs per dependency (each task), PR split (12, 15).
- The spec's "timestamptz" wording was aligned to the codebase's naive-UTC convention in the spec.
- `SessionDraft` gains `season_label`, `day_of_week`, `rsvp_count`, `needs_review` in Task 8; Tasks 6 and 7 do not set them.
