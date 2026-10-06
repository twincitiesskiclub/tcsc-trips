# Attendance Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the practice analytics lineage to every emoji-RSVP'd TCSC happening (events, socials, kickoffs, board meetings, races, trip sign-ups), prove completeness with gap checks, and replace the Thursday strength dashboard with three dashboards: what makes a practice draw, who comes and who drifts, and data coverage.

**Architecture:** Same three layers as the practice-analytics build. Layer 1 archives five more Slack channels. Layer 2 (`build_lineage`, pure) gains event sessions created by catalog corrections, trip sessions parsed from Slack Workflow sign-ups plus app trip registrations, a `category`, count-only sessions, a `decline` role, and one candidate detector that replaces the old "possible miss" check. `rebuild()` resolves people to a `person_key` and stores a coverage snapshot (candidates, empty weeks) in `AppConfig`. Layer 3 adds three dashboard modules on the existing framework.

**Tech Stack:** Flask 3, Flask-SQLAlchemy 3, Alembic via Flask-Migrate, PostgreSQL 18, slack_sdk, PyYAML, Vega-Lite 6 (already vendored), pytest, jsonschema and vl-convert-python (test only, already in `requirements-dev.txt`).

**Spec:** `docs/superpowers/specs/2026-09-25-attendance-analytics-design.md`, which builds on `docs/superpowers/specs/2026-09-25-practice-analytics-design.md`. Executors read both specs and this plan.

## Global Constraints

- The GitHub repo is PUBLIC. Never commit real Slack message text, Slack user IDs of members, member names, or per-person data. Committed fixtures are hand-written with fake IDs like `UFAKE0001`. Real data lives only in `/workspace/tcsc-trips/.superpowers/analytics-slack-dump/` (gitignored).
- The only Slack user IDs allowed in committed files are `U06FYPUNQCU` (TCSC app bot) and `U04C46UJXAM` (Zapier-linked account). Channel IDs are fine.
- Per-post data lives in `analytics_corrections`, never in YAML. `config/practice_history.yaml` holds rules only.
- Keep it simple. Rob's constraint: low complexity while meeting every goal. No new tables, no review UI, no new permissions.
- Timestamps in the DB are naive UTC. Practice dates and times are US Central. Use `app/utils.py` helpers, never `datetime.now()`.
- Tests run against `tcsc_trips_test`: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test`. Never `db.create_all()` / `db.drop_all()`. DB tests roll back.
- localhost:5432 goes through the pgforward relay (memory `pgforward-safe-relay.md`). The orchestrator starts it. Workers do not.
- Workers never touch production or real Slack. Only orchestrator tasks do.
- Nothing in `app/analytics/` writes to `practices`, `practice_rsvps`, `trip_registrations`, or posts to Slack.
- No em dashes or en dashes in user-facing copy. Periods and commas.
- The new migration bumps `HEAD_REVISION` in `tests/practices/test_practice_migration_release.py`.
- Admin UI is light only, Tailwind 3 classes, rendered by the existing `app/templates/admin/analytics/dashboard.html`.
- Codex workers: `codex exec -m gpt-6-astra -c 'model_reasoning_effort="high"' --dangerously-bypass-approvals-and-sandbox ... < /dev/null`, one dispatch per Bash call. Never pass `-s workspace-write` (bubblewrap fails in this container). After launch, wait 45 s and confirm the log has `exec` lines and the session transcript has no `"error"` (memory `codex-exec-in-container.md`).
- Before writing code that uses a dependency, read its docs: Vega-Lite 6 (https://vega.github.io/vega-lite/docs/ : bar, point, rule, text, layer, scale, condition), Slack `conversations.history` and Workflow message payloads (https://docs.slack.dev/reference/methods/conversations.history), Flask-Migrate/Alembic ops (https://alembic.sqlalchemy.org/en/latest/ops.html), PostgreSQL arrays (`ANY`, https://www.postgresql.org/docs/current/functions-array.html).

## Review Focus

1. A copied `#announcements-general` post (2026-05-11 `ts`, real date only in the footer) given a `create` correction: the session date must come from the correction's `date`, never the `ts`. Test in Task 3 (`test_created_event_uses_correction_date_not_post_ts`).
2. A Slack Workflow sign-up for someone else (typed name differs from the mentions): the typed name must win. Test in Task 5 (`test_typed_name_wins_over_mentions`).
3. Two members sharing a full name: a typed trip name must stay unmatched instead of guessing. Test in Task 6 (`test_ambiguous_name_stays_unmatched`).
4. A `#chat` post with 12 heart reactions and no RSVP wording: not a candidate. Test in Task 4 (`test_applause_only_post_is_not_candidate`).
5. The old `/admin/analytics/thursday-strength` bookmark: redirects to the practice dashboard with Strength and Thursday selected, never a 404. Test in Task 10 (`test_thursday_strength_redirects`).

---

## File structure

```
app/analytics/
  __init__.py            channel tuples (modified), CATEGORIES (new)
  models.py              category, reported_count, person_key, roles (modified)
  drafts.py              SessionDraft/AttendanceDraft fields, TripSignup (modified)
  history_config.py      trip_series, applause_emoji, practice_views (modified)
  corrections.py         new fields and key formats (modified)
  coverage.py            NEW: find_candidates, empty_weeks (pure)
  parse_trips.py         NEW: parse_signup, edition_year, trip_sessions (pure)
  lineage.py             event creates, emoji_roles, decline, reported_count, category, trips (modified)
  rebuild.py             all channels, app trip sign-ups, person_key, coverage snapshot (modified)
  cli.py                 flags prints candidates and empty weeks (modified)
  charts.py              factor_bars, points (modified)
  dashboards/
    __init__.py          registry: practices, people, coverage (modified)
    base.py              category filter, kind defaults, person_key in load_attendance (modified)
    splits.py            NEW: split/merged blocks moved out of thursday_strength.py
    practices.py         NEW
    people.py            NEW
    coverage.py          NEW
    thursday_strength.py DELETED in Task 12
app/routes/admin_analytics.py   thursday-strength redirect (modified)
config/practice_history.yaml    (modified)
migrations/versions/c3f9a1e7d2b4_attendance_analytics.py  NEW
```

---

# Part 1: data (PR 1)

### Task 1: Channels, migration, models

**Files:**
- Modify: `app/analytics/__init__.py`
- Modify: `app/analytics/models.py`
- Create: `migrations/versions/c3f9a1e7d2b4_attendance_analytics.py`
- Modify: `tests/practices/test_practice_migration_release.py:28`
- Test: `tests/analytics/test_models.py`

**Interfaces:**
- Produces: `CHANNELS`, `SESSION_CHANNELS`, `EVENT_CHANNELS`, `TRIP_CHANNEL`, `CANDIDATE_CHANNELS`, `LINEAGE_CHANNELS`, `SYNC_CHANNELS`, `CATEGORIES` in `app.analytics`. `PracticeSession.category` (str, not null), `PracticeSession.reported_count` (int | None), `PracticeAttendance.person_key` (str, not null), `PracticeAttendance.slack_uid` nullable, roles `rsvp|plan|lead|coach|signup|decline`, kinds `practice|event|trip`.

- [ ] **Step 1: Write the failing tests** (append to `tests/analytics/test_models.py`)

```python
import pytest
from datetime import date
from sqlalchemy.exc import IntegrityError

from app import analytics
from app.analytics.models import PracticeAttendance, PracticeSession


def test_channel_tuples():
    assert analytics.TRIP_CHANNEL == "C068ECRE0PQ"
    assert set(analytics.EVENT_CHANNELS) == {"C0B2VN1LU11", "C02HXN45214", "C02J1FDSBHT", "C046XRWC4NR"}
    assert analytics.CANDIDATE_CHANNELS == analytics.SESSION_CHANNELS + analytics.EVENT_CHANNELS
    assert analytics.LINEAGE_CHANNELS == analytics.CANDIDATE_CHANNELS + (analytics.TRIP_CHANNEL,)
    assert "C02HXN45214" not in analytics.SYNC_CHANNELS          # archived, imported once
    assert "C03FKTTHNHW" not in analytics.SYNC_CHANNELS
    assert set(analytics.LINEAGE_CHANNELS) <= set(analytics.CHANNELS)
    assert "trip" in analytics.CATEGORIES and "practice" in analytics.CATEGORIES


def _session(**overrides):
    values = dict(session_key="trip:cuyuna:2099", era="trip", kind="trip", category="trip",
                  date=date(2099, 9, 1), day_of_week="Tuesday", season_label="2099 Fall/Winter",
                  group_key="trip:cuyuna:2099")
    values.update(overrides)
    return PracticeSession(**values)


def test_trip_session_with_name_only_signup(db_session):
    session = _session()
    db_session.add(session)
    db_session.flush()
    db_session.add(PracticeAttendance(session_id=session.id, slack_uid=None,
                                      person_key="name:pat example", role="signup", source="reaction"))
    db_session.flush()
    assert session.reported_count is None


def test_person_key_is_the_uniqueness_key(db_session):
    session = _session()
    db_session.add(session)
    db_session.flush()
    for _ in range(2):
        db_session.add(PracticeAttendance(session_id=session.id, slack_uid="UFAKE0001",
                                          person_key="slack:UFAKE0001", role="decline",
                                          emoji="x", source="reaction"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_bad_category_rejected(db_session):
    db_session.add(_session(category="picnic"))
    with pytest.raises(IntegrityError):
        db_session.flush()
```

- [ ] **Step 2: Run to verify they fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/analytics/test_models.py -v`
Expected: FAIL (`AttributeError: module 'app.analytics' has no attribute 'TRIP_CHANNEL'`).

- [ ] **Step 3: Channel constants** (replace the body of `app/analytics/__init__.py`)

```python
"""Attendance analytics: Slack archive, session lineage, dashboards."""

CHANNELS = {
    "C042G463AQ1": "announcements-practices",
    "C03FKTTHNHW": "announcements-summer",     # archived; import needs the user token
    "C047BRZH1LG": "extra-training-fun",       # archived raw only, never sessions
    "C0B2VN1LU11": "announcements-general",
    "C02HXN45214": "announcements-adventures", # archived 2026-05-11, imported once
    "C068ECRE0PQ": "tech-trip-signups",
    "C02J1FDSBHT": "chat",
    "C046XRWC4NR": "races-information",
}
# Template and app-era practice parsing.
SESSION_CHANNELS = ("C042G463AQ1", "C03FKTTHNHW")
# Sessions only through `create` corrections (the event catalog).
EVENT_CHANNELS = ("C0B2VN1LU11", "C02HXN45214", "C02J1FDSBHT", "C046XRWC4NR")
# Slack Workflow trip sign-ups, parsed by parse_trips.
TRIP_CHANNEL = "C068ECRE0PQ"
CANDIDATE_CHANNELS = SESSION_CHANNELS + EVENT_CHANNELS
LINEAGE_CHANNELS = CANDIDATE_CHANNELS + (TRIP_CHANNEL,)
SYNC_CHANNELS = ("C042G463AQ1", "C047BRZH1LG", "C0B2VN1LU11", "C068ECRE0PQ", "C02J1FDSBHT", "C046XRWC4NR")
CATEGORIES = ("practice", "kickoff", "social", "board", "race", "volunteer", "banquet", "other", "trip")
```

- [ ] **Step 4: Models.** In `app/analytics/models.py`:

`PracticeSession`: add after `kind`:

```python
    category = db.Column(db.String(20), nullable=False, default="practice", index=True)
```

add after `rsvp_count`:

```python
    reported_count = db.Column(db.Integer)  # count-only sessions: names were lost
```

and replace the kind check constraint plus add a category check:

```python
        db.CheckConstraint("kind IN ('practice','event','trip')", name="ck_session_kind"),
        db.CheckConstraint(
            "category IN ('practice','kickoff','social','board','race','volunteer','banquet','other','trip')",
            name="ck_session_category"),
```

`PracticeAttendance`: make `slack_uid` nullable, add `person_key`, change the unique key and role check:

```python
    slack_uid = db.Column(db.String(20), index=True)
    person_key = db.Column(db.String(120), nullable=False, index=True)  # slack:U.. | user:N | name:...
    ...
    role = db.Column(db.String(10), nullable=False)    # rsvp | plan | lead | coach | signup | decline
    ...
    __table_args__ = (
        db.UniqueConstraint("session_id", "person_key", "role", "emoji",
                            name="uq_attendance_session_person_role_emoji"),
        db.CheckConstraint("role IN ('rsvp','plan','lead','coach','signup','decline')",
                           name="ck_attendance_role"),
    )
```

- [ ] **Step 5: Migration** `migrations/versions/c3f9a1e7d2b4_attendance_analytics.py`

```python
"""Widen analytics lineage to events and trips.

Revision ID: c3f9a1e7d2b4
Revises: b8e4d2a9c731
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "c3f9a1e7d2b4"
down_revision = "b8e4d2a9c731"
branch_labels = None
depends_on = None

CATEGORIES = "('practice','kickoff','social','board','race','volunteer','banquet','other','trip')"


def upgrade():
    op.add_column("practice_sessions", sa.Column(
        "category", sa.String(20), nullable=False, server_default="practice"))
    op.execute("UPDATE practice_sessions SET category = 'other' WHERE kind = 'event'")
    op.alter_column("practice_sessions", "category", server_default=None)
    op.create_index("ix_practice_sessions_category", "practice_sessions", ["category"])
    op.add_column("practice_sessions", sa.Column("reported_count", sa.Integer()))
    op.drop_constraint("ck_session_kind", "practice_sessions", type_="check")
    op.create_check_constraint("ck_session_kind", "practice_sessions", "kind IN ('practice','event','trip')")
    op.create_check_constraint("ck_session_category", "practice_sessions", f"category IN {CATEGORIES}")

    op.add_column("practice_attendance", sa.Column("person_key", sa.String(120)))
    op.execute("UPDATE practice_attendance SET person_key = 'slack:' || slack_uid")
    op.alter_column("practice_attendance", "person_key", nullable=False)
    op.alter_column("practice_attendance", "slack_uid", nullable=True)
    op.create_index("ix_practice_attendance_person_key", "practice_attendance", ["person_key"])
    op.drop_constraint("uq_attendance_session_uid_role_emoji", "practice_attendance", type_="unique")
    op.create_unique_constraint("uq_attendance_session_person_role_emoji", "practice_attendance",
                                ["session_id", "person_key", "role", "emoji"])
    op.drop_constraint("ck_attendance_role", "practice_attendance", type_="check")
    op.create_check_constraint("ck_attendance_role", "practice_attendance",
                               "role IN ('rsvp','plan','lead','coach','signup','decline')")


def downgrade():
    op.execute("DELETE FROM practice_attendance WHERE slack_uid IS NULL OR role IN ('signup','decline')")
    op.execute("DELETE FROM practice_sessions WHERE kind = 'trip'")
    op.drop_constraint("ck_attendance_role", "practice_attendance", type_="check")
    op.create_check_constraint("ck_attendance_role", "practice_attendance",
                               "role IN ('rsvp','plan','lead','coach')")
    op.drop_constraint("uq_attendance_session_person_role_emoji", "practice_attendance", type_="unique")
    op.create_unique_constraint("uq_attendance_session_uid_role_emoji", "practice_attendance",
                                ["session_id", "slack_uid", "role", "emoji"])
    op.drop_index("ix_practice_attendance_person_key", "practice_attendance")
    op.alter_column("practice_attendance", "slack_uid", nullable=False)
    op.drop_column("practice_attendance", "person_key")
    op.drop_constraint("ck_session_category", "practice_sessions", type_="check")
    op.drop_constraint("ck_session_kind", "practice_sessions", type_="check")
    op.create_check_constraint("ck_session_kind", "practice_sessions", "kind IN ('practice','event')")
    op.drop_column("practice_sessions", "reported_count")
    op.drop_index("ix_practice_sessions_category", "practice_sessions")
    op.drop_column("practice_sessions", "category")
```

Before writing it, check the exact constraint names in `migrations/versions/b8e4d2a9c731_practice_analytics.py` and use those.

- [ ] **Step 6:** Set `HEAD_REVISION = "c3f9a1e7d2b4"` in `tests/practices/test_practice_migration_release.py`.

- [ ] **Step 7: Upgrade the scratch DB and run tests**

```bash
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test TCSC_MIGRATION_ONLY=1 flask db upgrade
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/analytics/test_models.py tests/practices/test_practice_migration_release.py -v
```

Expected: PASS. Also run `flask db downgrade b8e4d2a9c731` then `flask db upgrade` on the scratch DB once and confirm both succeed.

- [ ] **Step 8: Commit**

```bash
git add app/analytics/__init__.py app/analytics/models.py migrations/versions/c3f9a1e7d2b4_attendance_analytics.py tests/analytics/test_models.py tests/practices/test_practice_migration_release.py
git commit -m "feat(analytics): widen lineage schema to events, trips and name-only people"
```

---

### Task 2: Correction fields and keys

**Files:**
- Modify: `app/analytics/corrections.py`
- Test: `tests/analytics/test_corrections.py`

**Interfaces:**
- Consumes: `CATEGORIES` (Task 1).
- Produces: `validate_correction(key, fields)` accepting `title`, `category`, `emoji_roles`, `reported_count`, `gap_ok`, kind `trip`, roles `signup`/`decline` in `add`/`remove`, keys `trip:<slug>:<YYYY>` and `gap:<Monday ISO date>`. Module constants `TRIP_KEY = re.compile(r"trip:([a-z0-9-]+):(\d{4})")`, `GAP_KEY = re.compile(r"gap:(\d{4}-\d{2}-\d{2})")`.

- [ ] **Step 1: Write the failing tests** (append to `tests/analytics/test_corrections.py`)

```python
import pytest

from app.analytics.corrections import CorrectionError, validate_correction

POST = "C02HXN45214:1700000000.000100"


def test_event_catalog_entry_validates():
    fields = {"create": True, "date": "2099-01-14", "title": "Pickleball night", "category": "social",
              "emoji_roles": {"pickle": "rsvp", "x": "decline", "call_me_hand::skin-tone-4": "rsvp"}}
    assert validate_correction(POST, fields) == fields


def test_count_only_entry_validates():
    validate_correction(POST, {"create": True, "date": "2024-05-16", "category": "kickoff",
                               "reported_count": 40})


@pytest.mark.parametrize("fields", [
    {"category": "picnic"},
    {"emoji_roles": {}},
    {"emoji_roles": {"x": "maybe"}},
    {"reported_count": -1},
    {"reported_count": True},
    {"title": "  "},
    {"kind": "social"},
])
def test_bad_new_fields_rejected(fields):
    with pytest.raises(CorrectionError):
        validate_correction(POST, fields)


def test_trip_key():
    validate_correction("trip:great-bear-chase:2024", {"date": "2025-03-06", "title": "Great Bear Chase 2025"})
    with pytest.raises(CorrectionError):
        validate_correction("trip:Great Bear:2024", {"date": "2025-03-06"})
    with pytest.raises(CorrectionError):
        validate_correction("trip:cuyuna:2024", {"create": True, "date": "2024-09-01"})


def test_gap_key_needs_monday_and_only_gap_ok():
    validate_correction("gap:2099-12-21", {"gap_ok": "Holiday break"})   # 2099-12-21 is a Monday
    with pytest.raises(CorrectionError):
        validate_correction("gap:2099-12-22", {"gap_ok": "Tuesday is not a week start"})
    with pytest.raises(CorrectionError):
        validate_correction("gap:2099-12-21", {"skip": True})
    with pytest.raises(CorrectionError):
        validate_correction(POST, {"gap_ok": "only on gap keys"})


def test_add_accepts_signup_and_decline():
    validate_correction(POST, {"add": [{"slack_uid": "UFAKE0001", "role": "decline"},
                                       {"slack_uid": "UFAKE0002", "role": "signup"}]})
```

- [ ] **Step 2: Run to verify they fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/analytics/test_corrections.py -v`
Expected: FAIL (`title: unknown correction field`).

- [ ] **Step 3: Implement.** In `app/analytics/corrections.py`:

```python
from app.analytics import CATEGORIES

CORRECTION_FIELDS = {
    "create", "skip", "kind", "date", "start_time", "status", "merged", "rsvp_emoji",
    "plan_emoji", "rsvp_from", "add", "remove", "location", "activities", "types", "ok",
    "title", "category", "emoji_roles", "reported_count", "gap_ok",
}
_POST_KEY = r"C[A-Z0-9]+:\d+\.\d+"
TRIP_KEY = re.compile(r"trip:([a-z0-9-]+):(\d{4})")
GAP_KEY = re.compile(r"gap:(\d{4}-\d{2}-\d{2})")
_KEY = re.compile(rf"(?:{_POST_KEY}(?::(?:early|late|merged|main|\d{{4}}-\d{{2}}-\d{{2}}))?|practice:\d+"
                  rf"|{TRIP_KEY.pattern}|{GAP_KEY.pattern})")
_ROLES = ("rsvp", "plan", "lead", "coach", "signup", "decline")
```

In `validate_correction`:
- Change the key error message to `"key: expected channel:ts[:slot], practice:id, trip:slug:YYYY or gap:YYYY-MM-DD"`.
- `kind` choices become `("practice", "event", "trip")`.
- `add` / `remove` roles use `_ROLES` and the message `"... with role rsvp/plan/lead/coach/signup/decline"`.
- New branches, placed before the final `else`:

```python
        elif field in {"title", "gap_ok"}:
            valid = isinstance(value, str) and bool(value.strip())
            expected = "a non-empty string"
        elif field == "category":
            valid = value in CATEGORIES
            expected = " or ".join(CATEGORIES)
        elif field == "reported_count":
            valid = type(value) is int and value >= 0
            expected = "a non-negative integer"
        elif field == "emoji_roles":
            valid = isinstance(value, dict) and bool(value) and all(
                isinstance(emoji, str) and emoji.strip() and role in ("rsvp", "decline", "plan")
                for emoji, role in value.items())
            expected = "a non-empty {emoji: rsvp|decline|plan} mapping"
```

- After the loop, add:

```python
    gap = GAP_KEY.fullmatch(key)
    if gap:
        if set(fields) != {"gap_ok"}:
            raise CorrectionError("gap keys take only gap_ok")
        if date.fromisoformat(gap[1]).weekday() != 0:
            raise CorrectionError("gap key: expected a Monday")
    elif "gap_ok" in fields:
        raise CorrectionError("gap_ok: only on gap:YYYY-MM-DD keys")
```

The existing `create` rule already rejects `create` on non-post keys (`trip:` included). Keep it.

- [ ] **Step 4: Run tests**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/analytics/test_corrections.py -v`
Expected: PASS (old tests included).

- [ ] **Step 5: Commit**

```bash
git add app/analytics/corrections.py tests/analytics/test_corrections.py
git commit -m "feat(analytics): catalog correction fields, trip and gap keys"
```

---

### Task 3: Event sessions in the lineage (categories, emoji roles, declines, count-only)

**Files:**
- Modify: `app/analytics/drafts.py`
- Modify: `app/analytics/lineage.py`
- Test: `tests/analytics/test_lineage.py`

**Interfaces:**
- Consumes: `EVENT_CHANNELS`, `CANDIDATE_CHANNELS` (Task 1); correction fields (Task 2).
- Produces:
  - `SessionDraft` gains `category: str = ""`, `reported_count: Optional[int] = None`, `decline_emoji: list = field(default_factory=list)`.
  - `AttendanceDraft.slack_uid` becomes `Optional[str]`, and it gains a last field `person_name: Optional[str] = None`.
  - `lineage.session_category(draft) -> str` (pure).
  - `build_lineage` creates sessions from `create` corrections on posts in any of `CANDIDATE_CHANNELS`; `emoji_roles` maps emoji to `rsvp`/`decline`/`plan`; `title` and `category` override; `reported_count` sets `rsvp_count` and adds flag `identities_lost`.

- [ ] **Step 1: Write the failing tests** (append to `tests/analytics/test_lineage.py`; reuse its `cfg`, `_ts`, `R`, `LOCS` helpers)

```python
from app.analytics.lineage import session_category

GEN = "C0B2VN1LU11"


def _event_post(text, reactions, channel=GEN, when=datetime(2099, 5, 1, 9, 0)):
    ts = _ts(when)
    return ArchivedMessage(channel, ts, {"ts": ts, "text": text, "reactions": reactions})


def test_created_event_uses_correction_date_not_post_ts(cfg):
    msg = _event_post("*Kickoff potluck!*\nReact :white_check_mark: or :x:",
                      [R("white_check_mark", "UFAKE0001", "UFAKE0002"), R("x", "UFAKE0003"),
                       R("tada", "UFAKE0004")])
    key = f"{GEN}:{msg.ts}"
    result = build_lineage([msg], [], LOCS, [], cfg, {key: {
        "create": True, "date": "2099-05-14", "category": "kickoff", "title": "Kickoff potluck",
        "emoji_roles": {"white_check_mark": "rsvp", "x": "decline"}}})
    session, = result.sessions
    assert (session.date, session.kind, session.category, session.title) == (
        date(2099, 5, 14), "event", "kickoff", "Kickoff potluck")
    assert session.rsvp_count == 2
    roles = sorted((row.slack_uid, row.role) for row in result.attendance)
    assert roles == [("UFAKE0001", "rsvp"), ("UFAKE0002", "rsvp"), ("UFAKE0003", "decline")]


def test_multi_option_post_counts_every_option_once(cfg):
    msg = _event_post("Race :runner: or cheer :mega:",
                      [R("runner", "UFAKE0001", "UFAKE0002"), R("mega", "UFAKE0002", "UFAKE0003")],
                      channel="C02HXN45214")
    key = f"C02HXN45214:{msg.ts}"
    result = build_lineage([msg], [], LOCS, [], cfg, {key: {
        "create": True, "date": "2099-05-20", "category": "race",
        "emoji_roles": {"runner": "rsvp", "mega": "rsvp"}}})
    assert result.sessions[0].rsvp_count == 3


def test_count_only_session(cfg):
    msg = _event_post("Old kickoff\n*May 1, 2099 9:43 AM* · :white_check_mark: 40 :x: 17", [])
    key = f"{GEN}:{msg.ts}"
    result = build_lineage([msg], [], LOCS, [], cfg, {key: {
        "create": True, "date": "2099-05-16", "category": "kickoff", "reported_count": 40}})
    session, = result.sessions
    assert (session.rsvp_count, session.reported_count) == (40, 40)
    assert "identities_lost" in session.flags and session.needs_review is False
    assert result.attendance == []


def test_event_channel_posts_never_parse_as_templates(cfg):
    text = "_Thursday, Jul 16th, 2099_ • _TCSC_\n*Board meeting @ Somewhere*\n*Time:* 6:00 PM"
    msg = _event_post(text, [R("white_check_mark", "UFAKE0001")])
    assert build_lineage([msg], [], LOCS, [], cfg).sessions == []


@pytest.mark.parametrize("kind,activities,override,expected", [
    ("practice", [], None, "practice"),
    ("practice", [], "social", "practice"),     # practices are always category practice
    ("event", ["Kickoff"], None, "kickoff"),
    ("event", [], None, "other"),
    ("event", [], "board", "board"),
    ("event", [], "practice", "other"),
    ("trip", [], None, "trip"),
])
def test_session_category(kind, activities, override, expected):
    draft = SessionDraft("k", "g", "template", date(2099, 1, 1), None, "t",
                         kind=kind, activities=activities, category=override or "")
    assert session_category(draft) == expected
```

Add `SessionDraft` to the file's `from app.analytics.drafts import ...` line.

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/analytics/test_lineage.py -v -k "created_event or multi_option or count_only or event_channel or session_category"`
Expected: FAIL (`ImportError: cannot import name 'session_category'`).

- [ ] **Step 3: Drafts.** In `app/analytics/drafts.py`:
  - `SessionDraft`: add `category: str = ""`, `reported_count: Optional[int] = None`, `decline_emoji: list = field(default_factory=list)` after `plan_emoji`.
  - `AttendanceDraft`: `slack_uid: Optional[str]`, and add `person_name: Optional[str] = None` as the last field. Update the role comment to `rsvp | plan | lead | coach | signup | decline`.

- [ ] **Step 4: Lineage.** In `app/analytics/lineage.py`:

Import `CANDIDATE_CHANNELS` and `CATEGORIES` from `app.analytics`.

Add:

```python
def session_category(session) -> str:
    """Practices are always 'practice' and trips 'trip'; events keep a valid override."""
    if session.kind == "practice":
        return "practice"
    if session.kind == "trip":
        return "trip"
    if session.category and session.category not in ("practice", "trip"):
        return session.category
    return "kickoff" if "Kickoff" in session.activities else "other"
```

In `_created_draft`: use the correction's title when present, and derive kind from category:

```python
    title = fields.get("title") or unescape(line).replace("*", "").replace("_", "").strip()[:120]
    ...
    kind = fields.get("kind") or ("event" if fields.get("category", "practice") != "practice"
                                  else classification["kind"])
```

and pass `kind=kind, category=fields.get("category", "")` to `SessionDraft`.

In `_apply_fields`, after the `plan_emoji` block:

```python
    if "title" in fields:
        session.title = fields["title"]
    if "category" in fields:
        session.category = fields["category"]
    if "reported_count" in fields:
        session.reported_count = fields["reported_count"]
    if "emoji_roles" in fields:
        roles = fields["emoji_roles"]
        rsvp = [emoji for emoji, role in roles.items() if role == "rsvp"]
        previous_slots = state.emoji_slots
        state.emoji_slots = {base_emoji(emoji): previous_slots.get(base_emoji(emoji), session.slot)
                             for emoji in rsvp}
        session.rsvp_emoji = rsvp[0] if len(rsvp) == 1 and session.format != "merged" else None
        session.plan_emoji = [emoji for emoji, role in roles.items() if role == "plan"]
        session.decline_emoji = [emoji for emoji, role in roles.items() if role == "decline"]
```

In `_attendance`, next to `plan_emoji`:

```python
    decline_emoji = {base_emoji(emoji) for emoji in session.decline_emoji}
```

and inside the reaction loop:

```python
                if base in decline_emoji:
                    add(uid, "decline", emoji, source="reaction")
```

`AttendanceDraft(...)` calls stay positional; `person_name` defaults to `None`.

In `build_lineage`, change the `create` condition from `message.channel_id in SESSION_CHANNELS` to `message.channel_id in CANDIDATE_CHANNELS`. Leave template parsing on `SESSION_CHANNELS` only.

In the final per-session loop, after `session.rsvp_count = ...`:

```python
            session.category = session_category(session)
            if session.reported_count is not None:
                session.rsvp_count = session.reported_count
                session.flags.append("identities_lost")
```

`identities_lost` comes from a correction, so `needs_review` stays False. Compute `needs_review` before appending the flag, or keep the existing expression (the session has a correction either way).

- [ ] **Step 5: Run the lineage and lift tests**

Run: `pytest tests/analytics/test_lineage.py tests/analytics/test_parse_app.py tests/analytics/test_parse_template.py tests/analytics/test_lift_acceptance.py -v`
Expected: PASS. Lift acceptance runs only on the dev box with the dump; it must still pass there.

- [ ] **Step 6: Commit**

```bash
git add app/analytics/drafts.py app/analytics/lineage.py tests/analytics/test_lineage.py
git commit -m "feat(analytics): event sessions from catalog corrections, declines, count-only"
```

---

### Task 4: Candidate detection (coverage check 1)

**Files:**
- Create: `app/analytics/coverage.py`
- Modify: `app/analytics/history_config.py` (only the `applause_emoji` key; Task 5 adds the rest)
- Modify: `config/practice_history.yaml`
- Modify: `app/analytics/lineage.py` (replace the misses block)
- Test: `tests/analytics/test_coverage.py` (new), `tests/analytics/test_history_config.py`

**Interfaces:**
- Consumes: `CANDIDATE_CHANNELS`; `is_weekly_preview` from `parse_template`; `base_emoji`.
- Produces:
  - `HistoryConfig.applause_emoji: frozenset`.
  - `coverage.RSVP_PHRASE` (compiled regex).
  - `coverage.is_candidate(raw: dict, applause: frozenset) -> bool`.
  - `coverage.find_candidates(messages, produced_posts: set[tuple[str, str]], corrections: dict, applause: frozenset) -> list[str]`, returning sorted `"channel:ts"` keys.
  - `LineageResult.possible_misses` keeps its name. It now holds candidates from `find_candidates` plus unparsed trip posts (Task 5).

- [ ] **Step 1: Write the failing tests** `tests/analytics/test_coverage.py`

```python
"""Hand-written posts only; no real Slack content."""
import pytest

from app.analytics.coverage import find_candidates, is_candidate
from app.analytics.drafts import ArchivedMessage

APPLAUSE = frozenset({"heart", "tada", "+1", "clap"})
CH = "C02HXN45214"


def R(name, count):
    return {"name": name, "count": count, "users": [f"UFAKE{i:04d}" for i in range(count)]}


@pytest.mark.parametrize("text", [
    "Hit a :baseball: if you're in",
    "Bop the :pickle: to join",
    "Smash that :party-wfh: button",
    "Please RSVP by reacting with a :white_check_mark: if you can come",
    "React with :bike: if you're IN",
    "give a :white_check_mark: if you're planning to attend",
    "React with :call_me_hand::skin-tone-4: to come",
])
def test_rsvp_phrasing_is_candidate(text):
    assert is_candidate({"text": text, "reactions": []}, APPLAUSE)


def test_applause_only_post_is_not_candidate():
    raw = {"text": "Congrats to our Birkie finishers!", "reactions": [R("heart", 12), R("tada", 9)]}
    assert not is_candidate(raw, APPLAUSE)


def test_five_reactions_on_non_applause_emoji_is_candidate():
    assert is_candidate({"text": "Cider tasting Saturday", "reactions": [R("apple", 5)]}, APPLAUSE)
    assert not is_candidate({"text": "Cider tasting Saturday", "reactions": [R("apple", 4)]}, APPLAUSE)


def _msg(ts, text, reactions=(), channel=CH, **raw):
    return ArchivedMessage(channel, ts, {"ts": ts, "text": text, "reactions": list(reactions), **raw})


def test_find_candidates_skips_resolved_produced_replies_and_system_posts():
    posts = [
        _msg("1.000001", "Bop the :pickle:"),                           # candidate
        _msg("1.000002", "Bop the :pickle:"),                           # skip correction
        _msg("1.000003", "Bop the :pickle:"),                           # produced a session
        _msg("1.000004", "Bop the :pickle:", thread_ts="1.000001"),     # reply
        _msg("1.000005", "x has joined", [R("wave", 9)], subtype="channel_join"),
        _msg("1.000006", "Bop the :pickle:", channel="C047BRZH1LG"),    # never counted
        _msg("1.000007", "Bop the :pickle:"),                           # rsvp_from target
        _msg("1.000008", "Bop the :pickle:"),                           # deleted
    ]
    posts[7] = ArchivedMessage(CH, "1.000008", posts[7].raw, deleted=True)
    corrections = {f"{CH}:1.000002": {"skip": True},
                   "practice:9": {"rsvp_from": [f"{CH}:1.000007"]}}
    produced = {(CH, "1.000003")}
    assert find_candidates(posts, produced, corrections, APPLAUSE) == [f"{CH}:1.000001"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/analytics/test_coverage.py -v`
Expected: FAIL (`ModuleNotFoundError: app.analytics.coverage`).

- [ ] **Step 3: YAML and config.** Add to `config/practice_history.yaml` (after `excluded_slack_uids`):

```yaml
# Reactions that mean applause, not attendance. A post whose only big
# reactions are these is not a candidate. Posts that NAME one of these as
# the RSVP emoji ("smash that :fire:") are still caught by the RSVP wording.
applause_emoji: ["heart", "+1", "thumbsup", "tada", "joy", "clap", "raised_hands", "100",
                 "heart_eyes", "laughing", "rolling_on_the_floor_laughing", "pray",
                 "partying_face", "star-struck", "sob", "eyes", "muscle", "fire",
                 "sparkles", "white_heart", "blue_heart", "purple_heart", "green_heart",
                 "exploding_head", "hugging_face", "catjam", "foxy_yay"]
```

In `history_config.py`: add `applause_emoji: frozenset` to `HistoryConfig`, validate with `_strings(data.get("applause_emoji"), "applause_emoji")` alongside `excluded_slack_uids`, and set `applause_emoji=frozenset(base_emoji(e) for e in data["applause_emoji"])`. Move `base_emoji` above `load_history_config` so it can be used there. Add a test to `tests/analytics/test_history_config.py`:

```python
def test_applause_emoji_required(tmp_path):
    import yaml
    from app.analytics.history_config import DEFAULT_PATH, HistoryConfigError, load_history_config
    data = yaml.safe_load(DEFAULT_PATH.read_text())
    assert "heart" in load_history_config().applause_emoji
    del data["applause_emoji"]
    path = tmp_path / "h.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(HistoryConfigError, match="applause_emoji"):
        load_history_config(path)
```

- [ ] **Step 4: Implement** `app/analytics/coverage.py`

```python
"""Completeness checks over the archive and the lineage. Pure functions."""
import re

from app.analytics import CANDIDATE_CHANNELS
from app.analytics.history_config import base_emoji
from app.analytics.parse_template import is_weekly_preview

RSVP_PHRASE = re.compile(
    r"\b(hit|bop|smash|react(?:ing)?\s+with|give\s+(?:it\s+)?an?|rsvp)\b[^\n]{0,60}?"
    r":([a-z0-9_+'-]+(?:::skin-tone-\d)?):", re.I)
_SYSTEM_SUBTYPES = {"channel_join", "channel_leave", "channel_purpose", "channel_topic",
                    "channel_name", "channel_archive", "channel_unarchive", "bot_add",
                    "bot_remove", "pinned_item", "tombstone"}


def is_candidate(raw: dict, applause: frozenset) -> bool:
    """RSVP wording that names an emoji, or 5+ of one non-applause reaction."""
    if RSVP_PHRASE.search(raw.get("text", "")):
        return True
    return any(reaction.get("count", 0) >= 5 and base_emoji(reaction["name"]) not in applause
               for reaction in raw.get("reactions", []))


def _resolved_posts(corrections: dict) -> set[str]:
    resolved = set()
    for key, fields in corrections.items():
        if key.startswith("C"):
            resolved.add(":".join(key.split(":")[:2]))
        resolved.update(fields.get("rsvp_from", []))
    return resolved


def find_candidates(messages, produced_posts, corrections, applause) -> list[str]:
    """Top-level posts that look like attendance but produced no session and have no correction."""
    resolved = _resolved_posts(corrections)
    found = []
    for message in messages:
        raw = message.raw
        key = f"{message.channel_id}:{message.ts}"
        if (message.channel_id not in CANDIDATE_CHANNELS or message.deleted
                or raw.get("thread_ts", message.ts) != message.ts
                or raw.get("subtype") in _SYSTEM_SUBTYPES
                or (message.channel_id, message.ts) in produced_posts or key in resolved
                or is_weekly_preview(raw.get("text", ""))):
            continue
        if is_candidate(raw, applause):
            found.append(key)
    return sorted(found)
```

- [ ] **Step 5: Use it in the lineage.** In `build_lineage`, replace everything from `produced = {(session.channel_id, ...` through the `misses = [...]` expression with:

```python
    produced = consumed | {(session.channel_id, session.source_ts) for session in sessions}
    # A correction on any session of a post resolves the whole post.
    corrected = {session.group_key for session in drafts if session.session_key in corrections}
    misses = [key for key in find_candidates(indexed.values(), produced, corrections, cfg.applause_emoji)
              if key not in corrected]
```

Import `find_candidates` from `app.analytics.coverage` and delete `_MISS_EMOJI`. Existing lineage tests that assert `possible_misses` must still pass. If one fails because the new rule is broader (for example a 5-reaction test post with a non-RSVP emoji), keep the test's intent and update only its fixture.

- [ ] **Step 6: Run tests**

Run: `pytest tests/analytics/test_coverage.py tests/analytics/test_lineage.py tests/analytics/test_history_config.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/analytics/coverage.py app/analytics/lineage.py app/analytics/history_config.py config/practice_history.yaml tests/analytics/test_coverage.py tests/analytics/test_history_config.py tests/analytics/test_lineage.py
git commit -m "feat(analytics): one candidate detector across every session channel"
```

---

### Task 5: Trip sign-ups (parser, series config, trip sessions)

**Files:**
- Create: `app/analytics/parse_trips.py`
- Modify: `app/analytics/drafts.py` (add `TripSignup`)
- Modify: `app/analytics/history_config.py`, `config/practice_history.yaml` (`trip_series`, `practice_views`)
- Modify: `app/analytics/lineage.py` (`trip_signups` keyword)
- Modify: `app/analytics/dashboards/thursday_strength.py` only if it reads `capacity_lines` by a path other than `load_history_config().capacity_lines` (it should not)
- Test: `tests/analytics/test_parse_trips.py` (new), `tests/analytics/test_history_config.py`

**Interfaces:**
- Consumes: `TRIP_CHANNEL`; `HistoryConfig`; `AttendanceDraft.person_name` (Task 3); `TRIP_KEY` (Task 2).
- Produces:
  - `drafts.TripSignup(series_slug: str, edition_year: int, posted_on: date, slack_uid: Optional[str], person_name: Optional[str], source_key: str)`.
  - `HistoryConfig.trip_series: list[dict]` (each `{match: [str], slug: str}`).
  - `HistoryConfig.capacity_lines` is still the attribute, but it is read from `practice_views.capacity_lines`. A top-level `capacity_lines` key is an error.
  - `parse_trips.normalize_name(text: str) -> str`: lowercase, whitespace collapsed.
  - `parse_trips.edition_year(day: date) -> int`: `day.year if day.month >= 6 else day.year - 1`.
  - `parse_trips.parse_signup(message: ArchivedMessage, cfg) -> TripSignup | None`.
  - `parse_trips.trip_sessions(signups, corrections, seasons) -> tuple[list[SessionDraft], list[AttendanceDraft]]`.
  - `build_lineage(..., cfg, corrections=None, trip_signups=())`. It parses Slack posts in `TRIP_CHANNEL`, adds `trip_signups` (app registrations), and returns trip sessions. Posts in `TRIP_CHANNEL` that look like sign-ups (`bot_message` with the header) but fail to parse, and have no correction, are added to `possible_misses`.

- [ ] **Step 1: Write the failing tests** `tests/analytics/test_parse_trips.py`

```python
"""Hand-written Workflow posts with fake names and IDs."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.analytics.drafts import ArchivedMessage, TripSignup
from app.analytics.history_config import load_history_config
from app.analytics.lineage import build_lineage
from app.analytics.parse_trips import edition_year, normalize_name, parse_signup, trip_sessions

TRIP = "C068ECRE0PQ"
HEADER = "Trip Signup Submitted. This does not mean that they have paid!"


@pytest.fixture
def cfg():
    return load_history_config()


def _post(body, username, when=datetime(2099, 11, 20, 12, 0)):
    ts = f"{when.replace(tzinfo=ZoneInfo('America/Chicago')).timestamp():.6f}"
    raw = {"ts": ts, "subtype": "bot_message", "username": username, "text": f"{HEADER}\n{body}"}
    return ArchivedMessage(TRIP, ts, raw)


def test_edition_year_and_name_normalizing():
    assert edition_year(date(2099, 6, 1)) == 2099
    assert edition_year(date(2099, 5, 31)) == 2098
    assert normalize_name("  Pat   EXAMPLE ") == "pat example"


def test_typed_name_line(cfg):
    signup = parse_signup(_post("Pat Example", "Cuyuna Trip Sign-Up"), cfg)
    assert (signup.series_slug, signup.edition_year, signup.person_name, signup.slack_uid) == (
        "cuyuna", 2099, "Pat Example", None)


def test_bare_mention(cfg):
    signup = parse_signup(_post("\n<@UFAKE0001>", "Birkie Sign-Up"), cfg)
    assert (signup.series_slug, signup.slack_uid, signup.person_name) == ("birkie", "UFAKE0001", None)


def test_first_last_form(cfg):
    body = ("\n*What's your first name?*\nPat \n*What's your last name?*\nExample\n"
            "*Dietary needs*\nNone")
    signup = parse_signup(_post(body, "Great Bear Chase Trip Sign-Up", datetime(2099, 1, 22)), cfg)
    assert (signup.series_slug, signup.edition_year, signup.person_name) == (
        "great-bear-chase", 2098, "Pat Example")


def test_typed_name_wins_over_mentions(cfg):
    body = ("\n*What's your name?*\nPat Example\n\n<@UFAKE0009>\n<#C02HXN45214|>\n<@UFAKE0008>\n"
            "Nov 21, 2099 12:40am UTC")
    signup = parse_signup(_post(body, "Sisu Trip Sign-Up"), cfg)
    assert (signup.series_slug, signup.person_name, signup.slack_uid) == ("sisu-ski-fest", "Pat Example", None)


def test_single_mention_kept_as_fallback(cfg):
    body = "\n*What's your name?*\nPat Example\n\n<@UFAKE0009>\n<#C02HXN45214|>\n<@UFAKE0009>"
    signup = parse_signup(_post(body, "Sisu Trip Sign-Up"), cfg)
    assert (signup.person_name, signup.slack_uid) == ("Pat Example", "UFAKE0009")


def test_pre_birkie_is_not_birkie_and_unknown_series_is_none(cfg):
    assert parse_signup(_post("Pat Example", "Pre-Birkie and North-end Classic Trip Sign-Up"), cfg).series_slug == "pre-birkie"
    assert parse_signup(_post("Pat Example", "Moon Base Trip Sign-Up"), cfg) is None
    join = ArchivedMessage(TRIP, "1.0", {"ts": "1.0", "subtype": "channel_join", "text": "joined"})
    assert parse_signup(join, cfg) is None


def test_trip_sessions_dedupe_and_date_correction():
    signups = [
        TripSignup("cuyuna", 2099, date(2099, 8, 7), None, "Pat Example", "C:1"),
        TripSignup("cuyuna", 2099, date(2099, 8, 9), None, "pat  example", "C:2"),     # duplicate
        TripSignup("cuyuna", 2099, date(2099, 8, 10), "UFAKE0002", None, "C:3"),
        TripSignup("cuyuna", 2098, date(2098, 8, 1), "UFAKE0002", None, "C:4"),        # other edition
    ]
    sessions, attendance = trip_sessions(signups, {"trip:cuyuna:2099": {"date": "2099-09-25",
                                                                         "title": "Cuyuna 2099"}}, [])
    by_key = {s.session_key: s for s in sessions}
    ours = by_key["trip:cuyuna:2099"]
    assert (ours.kind, ours.category, ours.date, ours.title, ours.rsvp_count, ours.flags) == (
        "trip", "trip", date(2099, 9, 25), "Cuyuna 2099", 2, [])
    other = by_key["trip:cuyuna:2098"]
    assert other.flags == ["missing_date"] and other.date == date(2098, 8, 1) and other.needs_review
    rows = [(a.session_key, a.slack_uid, a.person_name, a.role) for a in attendance]
    assert sorted(rows, key=str) == sorted([
        ("trip:cuyuna:2099", None, "pat example", "signup"),
        ("trip:cuyuna:2099", "UFAKE0002", None, "signup"),
        ("trip:cuyuna:2098", "UFAKE0002", None, "signup"),
    ], key=str)


def test_build_lineage_includes_trips_and_flags_unparsed(cfg):
    good = _post("Pat Example", "Cuyuna Trip Sign-Up")
    bad = _post("Pat Example", "Moon Base Trip Sign-Up", datetime(2099, 11, 21))
    result = build_lineage([good, bad], [], [], [], cfg)
    assert [s.session_key for s in result.sessions] == ["trip:cuyuna:2099"]
    assert result.possible_misses == [f"{TRIP}:{bad.ts}"]
    resolved = build_lineage([good, bad], [], [], [], cfg, {f"{TRIP}:{bad.ts}": {"skip": True}})
    assert resolved.possible_misses == []
```

Add a `test_history_config.py` test that a top-level `capacity_lines` key raises `HistoryConfigError` matching `practice_views`, and that `load_history_config().capacity_lines` still returns the three lines.

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/analytics/test_parse_trips.py -v`
Expected: FAIL (`ImportError: cannot import name 'TripSignup'`).

- [ ] **Step 3: YAML.** In `config/practice_history.yaml`, replace the top-level `capacity_lines:` block with:

```yaml
# Settings read only by the practice dashboard's split/merged section.
practice_views:
  capacity_lines:
    - {value: 27, label: "2025 split rule", from: 2025-05-01}
    - {value: 30, label: "Dec 2025 cap", from: 2025-12-01, to: 2026-03-31}
    - {value: 35, label: "One session (5x7)", from: 2026-08-01}

# Slack Workflow sign-up names (the post's username, lowercased substring,
# first rule wins) to trip series. Slugs equal the app's trip_series.slug.
trip_series:
  - {match: ["pre-birkie"], slug: pre-birkie}
  - {match: ["birkie"], slug: birkie}
  - {match: ["great bear"], slug: great-bear-chase}
  - {match: ["cuyuna"], slug: cuyuna}
  - {match: ["hayward"], slug: training-trip}
  - {match: ["sisu"], slug: sisu-ski-fest}
  - {match: ["north shore"], slug: north-shore}
  - {match: ["50kum", "50k um"], slug: 50kum}
```

- [ ] **Step 4: Config loader.** In `history_config.py`:
  - Add `trip_series: list[dict]` to `HistoryConfig`.
  - If `"capacity_lines" in data`, raise `HistoryConfigError("capacity_lines: moved under practice_views")`.
  - `_mapping(data.get("practice_views"), "practice_views")`, then validate `data["practice_views"].get("capacity_lines")` with the existing capacity-line checks, using key prefix `practice_views.capacity_lines`.
  - Validate `trip_series` as a list of mappings with `match` (non-empty strings) and `slug` (a string matching `[a-z0-9-]+`).
  - Construct with `capacity_lines=data["practice_views"]["capacity_lines"]` and `trip_series=data["trip_series"]`.

- [ ] **Step 5: Drafts.** Add to `app/analytics/drafts.py`:

```python
@dataclass(frozen=True)
class TripSignup:
    series_slug: str
    edition_year: int             # Fall/Winter start year
    posted_on: date               # Central date of the sign-up
    slack_uid: Optional[str]
    person_name: Optional[str]
    source_key: str               # "channel:ts" or "trip_registration:<id>"
```

- [ ] **Step 6: Parser** `app/analytics/parse_trips.py`

```python
"""Trip sign-ups from Slack Workflow posts, and trip sessions. Pure."""
from datetime import date, datetime
import re
from zoneinfo import ZoneInfo

from app.analytics.drafts import AttendanceDraft, SessionDraft, TripSignup
from app.analytics.seasons import season_label

_CENTRAL = ZoneInfo("America/Chicago")
HEADER = re.compile(r"submitted\.\s+this does not mean that they have paid", re.I)
_MENTION = re.compile(r"<@([UW][A-Z0-9]+)(?:\|[^>]*)?>")
_ANSWER = re.compile(r"\*What's your (first name|last name|name)\?\*\n([^\n]*)", re.I)


def normalize_name(text: str) -> str:
    return " ".join(text.lower().split())


def edition_year(day: date) -> int:
    return day.year if day.month >= 6 else day.year - 1


def is_signup_post(raw: dict) -> bool:
    return raw.get("subtype") == "bot_message" and bool(HEADER.search(raw.get("text", "")))


def _series(username: str, cfg) -> str | None:
    text = username.lower()
    return next((rule["slug"] for rule in cfg.trip_series
                 if any(match.lower() in text for match in rule["match"])), None)


def parse_signup(message, cfg) -> TripSignup | None:
    raw = message.raw
    if not is_signup_post(raw):
        return None
    slug = _series(raw.get("username", ""), cfg)
    if slug is None:
        return None
    posted_on = datetime.fromtimestamp(float(message.ts), _CENTRAL).date()
    body = raw["text"].split("\n", 1)[1] if "\n" in raw["text"] else ""
    answers = {label.lower(): value.strip() for label, value in _ANSWER.findall(body)}
    if "first name" in answers:
        name = f"{answers['first name']} {answers.get('last name', '')}".strip()
    elif "name" in answers:
        name = answers["name"]
    else:
        name = next((line.strip() for line in body.splitlines()
                     if line.strip() and not line.strip().startswith(("<", "*"))), "")
    mentions = list(dict.fromkeys(_MENTION.findall(body)))
    # Typed names win: one member often signs up another. A lone mention is a fallback.
    uid = mentions[0] if len(mentions) == 1 else None
    if not name and not uid:
        return None
    return TripSignup(slug, edition_year(posted_on), posted_on, uid, name or None,
                      f"{message.channel_id}:{message.ts}")


def trip_sessions(signups, corrections, seasons):
    """One session per series edition; one signup row per distinct person."""
    editions = {}
    for signup in signups:
        editions.setdefault((signup.series_slug, signup.edition_year), []).append(signup)
    sessions, attendance = [], []
    for (slug, year), group in sorted(editions.items()):
        key = f"trip:{slug}:{year}"
        fields = corrections.get(key, {})
        if fields.get("skip"):
            continue
        dated = "date" in fields
        day = date.fromisoformat(fields["date"]) if dated else max(s.posted_on for s in group)
        people = {}
        for signup in sorted(group, key=lambda s: s.source_key):
            name = normalize_name(signup.person_name) if signup.person_name else None
            person = f"name:{name}" if name else f"slack:{signup.slack_uid}"
            people.setdefault(person, AttendanceDraft(key, signup.slack_uid, "signup", None, None,
                                                      "reaction", name))
        flags = [] if dated else ["missing_date"]
        sessions.append(SessionDraft(
            session_key=key, group_key=key, era="trip", date=day, start_time=None,
            title=fields.get("title") or f"{slug.replace('-', ' ').title()} ({year} Fall/Winter)",
            kind="trip", category="trip", status=fields.get("status", "held"),
            flags=flags, needs_review=not dated, rsvp_count=len(people),
            day_of_week=day.strftime("%A"), season_label=season_label(day, seasons),
            lat=None, lon=None,
        ))
        attendance.extend(people.values())
    return sessions, attendance
```

The `source` value stays within the existing informal set. Rebuild (Task 6) resolves names, including matching a typed name to the same person as a mention. Corrections `add` / `remove` on trip keys are not applied to trips in this iteration; YAGNI.

- [ ] **Step 7: Wire into `build_lineage`.** Add the keyword `trip_signups=()`. Insert this directly after the `misses = [...]` statement from Task 4 and before `sessions.sort(...)`:

```python
    slack_signups, unparsed = [], []
    for key, message in indexed.items():
        if message.channel_id != TRIP_CHANNEL or not is_signup_post(message.raw):
            continue
        signup = parse_signup(message, cfg)
        if signup is None:
            if f"{message.channel_id}:{message.ts}" not in corrections:
                unparsed.append(f"{message.channel_id}:{message.ts}")
        else:
            slack_signups.append(signup)
    trips, trip_rows = trip_sessions([*slack_signups, *trip_signups], corrections, seasons)
    sessions.extend(trips)
    attendance.extend(trip_rows)
    misses = sorted(misses + unparsed)
```

Import `TRIP_CHANNEL`, `is_signup_post`, `parse_signup` and `trip_sessions`.

- [ ] **Step 8: Run tests**

Run: `pytest tests/analytics/test_parse_trips.py tests/analytics/test_history_config.py tests/analytics/test_lineage.py tests/analytics/test_thursday_strength.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/analytics/parse_trips.py app/analytics/drafts.py app/analytics/history_config.py app/analytics/lineage.py config/practice_history.yaml tests/analytics/test_parse_trips.py tests/analytics/test_history_config.py
git commit -m "feat(analytics): trip sign-up sessions from Slack Workflow posts"
```

---

### Task 6: Rebuild (all channels, app trip sign-ups, person keys, coverage snapshot)

**Files:**
- Modify: `app/analytics/rebuild.py`
- Modify: `app/analytics/coverage.py` (add `empty_weeks`)
- Test: `tests/analytics/test_rebuild.py`, `tests/analytics/test_coverage.py`

**Interfaces:**
- Consumes: everything above. `GAP_KEY` (Task 2).
- Produces:
  - `coverage.empty_weeks(sessions, corrections) -> list[date]`: Mondays inside a season's practice span with no practice session and no `gap:` correction. Sessions are anything with `.kind`, `.date` and `.season_label`.
  - `rebuild.load_app_trip_signups() -> list[TripSignup]`.
  - `rebuild.resolve_people(rows: list[AttendanceDraft], people: dict) -> list[dict]`. `people` is `{"uid_to_user": {uid: user_id}, "name_to_member": {normalized_name: (user_id, uid_or_None)}}`. Each returned dict has keys `session_key, slack_uid, user_id, person_key, role, emoji, slot, source, unmatched`. Rows are deduped on `(session_key, person_key, role, emoji)`.
  - `load_inputs()` reads `LINEAGE_CHANNELS`. `rebuild()` persists `category` and `reported_count`, writes `person_key`, adds flag `unmatched_person` to sessions with an unmatched row (without touching `needs_review`), and calls `AppConfig.set("analytics_coverage", snapshot, category="analytics")` with `{"computed_at": iso UTC, "candidates": [...], "empty_weeks": [iso dates]}`. Each candidate is `{"post_key", "channel", "date" (Central ISO), "text" (first 140 chars of the first non-empty line), "reactions" (top 3 as {name: count})}`.
  - Return stats gain `"candidates": int` and `"empty_weeks": int`. `possible_misses` stays in the stats.

- [ ] **Step 1: Write the failing tests.** Append to `tests/analytics/test_coverage.py`:

```python
from datetime import date
from types import SimpleNamespace

from app.analytics.coverage import empty_weeks


def _s(day, kind="practice", season="2099 Fall/Winter"):
    return SimpleNamespace(date=day, kind=kind, season_label=season)


def test_empty_weeks_inside_season_span_only():
    sessions = [_s(date(2099, 11, 3)), _s(date(2099, 11, 24)),          # Tue Nov 3 .. Tue Nov 24
                _s(date(2099, 11, 12), kind="event"),                   # events never fill a week
                _s(date(2099, 6, 2), season="2099 Spring/Summer")]
    assert empty_weeks(sessions, {}) == [date(2099, 11, 9), date(2099, 11, 16)]
    assert empty_weeks(sessions, {"gap:2099-11-09": {"gap_ok": "Break"}}) == [date(2099, 11, 16)]
```

Append to `tests/analytics/test_rebuild.py`:

```python
from app.analytics.drafts import AttendanceDraft
from app.analytics.rebuild import resolve_people

PEOPLE = {"uid_to_user": {"UFAKE0001": 11, "UFAKE0002": 12},
          "name_to_member": {"pat example": (11, "UFAKE0001"), "no slack": (13, None)}}


def _row(uid=None, name=None, key="trip:cuyuna:2099", role="signup"):
    return AttendanceDraft(key, uid, role, None, None, "reaction", name)


def test_resolve_people_matches_names_and_dedupes():
    rows = resolve_people([_row(name="pat example"), _row(uid="UFAKE0001"),   # same person twice
                           _row(name="no slack"), _row(name="nobody here"),
                           _row(uid="UFAKE0002", key="C1:1.0:main", role="rsvp")], PEOPLE)
    got = sorted((r["session_key"], r["person_key"], r["user_id"], r["unmatched"]) for r in rows)
    assert got == [("C1:1.0:main", "slack:UFAKE0002", 12, False),
                   ("trip:cuyuna:2099", "name:nobody here", None, True),
                   ("trip:cuyuna:2099", "slack:UFAKE0001", 11, False),
                   ("trip:cuyuna:2099", "user:13", 13, False)]


def test_ambiguous_name_stays_unmatched():
    rows = resolve_people([_row(name="pat example", uid="UFAKE0002")],
                          {"uid_to_user": {"UFAKE0002": 12}, "name_to_member": {}})
    assert rows[0]["person_key"] == "slack:UFAKE0002"          # lone-mention fallback
    rows = resolve_people([_row(name="pat example")], {"uid_to_user": {}, "name_to_member": {}})
    assert rows[0]["person_key"] == "name:pat example" and rows[0]["unmatched"]
```

Also add this DB test to `test_rebuild.py`. The dev scratch DB may hold other analytics rows, so every assertion filters on the keys it seeds:

```python
def test_rebuild_events_trips_and_coverage_snapshot(db_session):
    from app.analytics.corrections import upsert_correction
    from app.models import AppConfig

    gen, trip = "C0B2VN1LU11", "C068ECRE0PQ"
    upsert_message(gen, {"ts": "4087911700.000100", "text": "Game night, give a :white_check_mark:",
                         "reactions": [{"name": "white_check_mark", "count": 1, "users": ["UFAKE7001"]},
                                       {"name": "x", "count": 1, "users": ["UFAKE7002"]}]})
    upsert_message(gen, {"ts": "4087911701.000100", "text": "Bop the :pickle: for pickleball",
                         "reactions": [{"name": "pickle", "count": 2, "users": ["UFAKE7003", "UFAKE7004"]}]})
    upsert_message(trip, {"ts": "4087911702.000100", "subtype": "bot_message",
                          "username": "Cuyuna Trip Sign-Up",
                          "text": "Trip Signup Submitted. This does not mean that they have paid!\nZed Nobodyfake"})
    upsert_correction(f"{gen}:4087911700.000100", {
        "create": True, "date": "2099-07-20", "category": "social", "title": "Game night",
        "emoji_roles": {"white_check_mark": "rsvp", "x": "decline"}}, "test", "test")
    stats = rebuild(commit=False)

    event = PracticeSession.query.filter_by(session_key=f"{gen}:4087911700.000100:main").one()
    assert (event.kind, event.category, event.rsvp_count) == ("event", "social", 1)
    decline = PracticeAttendance.query.filter_by(session_id=event.id, role="decline").one()
    assert decline.person_key == "slack:UFAKE7002"

    trip_session = PracticeSession.query.filter_by(session_key="trip:cuyuna:2099").one()
    row = PracticeAttendance.query.filter_by(session_id=trip_session.id).one()
    assert row.person_key == "name:zed nobodyfake" and row.slack_uid is None
    assert "unmatched_person" in trip_session.flags and "missing_date" in trip_session.flags

    keys = [c["post_key"] for c in AppConfig.get("analytics_coverage")["candidates"]]
    assert f"{gen}:4087911701.000100" in keys and f"{gen}:4087911700.000100" not in keys
    assert stats["candidates"] == len(keys)
```

Add a unit test for `load_people` that seeds two users named "Pat Twin" (no Slack) and one "Solo Fake". It asserts `"pat twin" not in load_people()["name_to_member"]` and `"solo fake" in load_people()["name_to_member"]`.

- [ ] **Step 2: Run to verify they fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/analytics/test_rebuild.py tests/analytics/test_coverage.py -v`
Expected: FAIL (`ImportError: cannot import name 'empty_weeks'`).

- [ ] **Step 3: Implement.** `coverage.py`:

```python
from datetime import timedelta


def empty_weeks(sessions, corrections) -> list:
    """Mondays between a season's first and last practice with no practice at all."""
    spans, filled = {}, set()
    for session in sessions:
        if session.kind != "practice":
            continue
        monday = session.date - timedelta(days=session.date.weekday())
        filled.add(monday)
        first, last = spans.get(session.season_label, (monday, monday))
        spans[session.season_label] = (min(first, monday), max(last, monday))
    gaps = set()
    for first, last in spans.values():
        monday = first
        while monday <= last:
            if monday not in filled and f"gap:{monday.isoformat()}" not in corrections:
                gaps.add(monday)
            monday += timedelta(days=7)
    return sorted(gaps)
```

Cancelled practices count as filled: the week is known.

`rebuild.py`:

```python
from app.analytics import LINEAGE_CHANNELS
from app.analytics.coverage import empty_weeks
from app.analytics.drafts import TripSignup
from app.analytics.parse_trips import edition_year, normalize_name
from app.models import Trip
from app.trips.models import TripRegistration, TripSeries


def load_app_trip_signups() -> list[TripSignup]:
    rows = db.session.query(TripRegistration.id, TripSeries.slug, Trip.start_date, SlackUser.slack_uid,
                            User.first_name, User.last_name).join(
        Trip, TripRegistration.trip_id == Trip.id).join(
        TripSeries, Trip.series_id == TripSeries.id).join(
        User, TripRegistration.user_id == User.id).outerjoin(
        SlackUser, User.slack_user_id == SlackUser.id).filter(
        TripRegistration.status != "cancelled").order_by(TripRegistration.id).all()
    return [TripSignup(slug, edition_year(start.date() if hasattr(start, "date") else start),
                       start.date() if hasattr(start, "date") else start,
                       uid, None if uid else f"{first} {last}", f"trip_registration:{rid}")
            for rid, slug, start, uid, first, last in rows]


def load_people() -> dict:
    """Slack uid to user, and full names that belong to exactly one member."""
    rows = db.session.query(User.id, User.first_name, User.last_name, SlackUser.slack_uid).outerjoin(
        SlackUser, User.slack_user_id == SlackUser.id).all()
    by_name = defaultdict(set)
    for user_id, first, last, uid in rows:
        by_name[normalize_name(f"{first} {last}")].add((user_id, uid))
    return {"uid_to_user": {uid: user_id for user_id, _, _, uid in rows if uid},
            "name_to_member": {name: next(iter(members)) for name, members in by_name.items()
                               if len(members) == 1}}


def resolve_people(rows, people) -> list[dict]:
    resolved = {}
    for row in rows:
        uid, user_id, unmatched = row.slack_uid, None, False
        member = people["name_to_member"].get(normalize_name(row.person_name)) if row.person_name else None
        if member:
            user_id, member_uid = member
            uid = member_uid
        if uid:
            person_key = f"slack:{uid}"
            user_id = user_id or people["uid_to_user"].get(uid)
        elif user_id:
            person_key = f"user:{user_id}"
        else:
            person_key, unmatched = f"name:{normalize_name(row.person_name)}", True
        key = (row.session_key, person_key, row.role, row.emoji)
        resolved.setdefault(key, dict(
            session_key=row.session_key, slack_uid=uid, user_id=user_id, person_key=person_key,
            role=row.role, emoji=row.emoji, slot=row.slot, source=row.source, unmatched=unmatched))
    return list(resolved.values())
```

`Trip.start_date` is a `DateTime` in prod. Keep the `hasattr` guard so a `Date` also works.

In `load_inputs`, filter the archive on `LINEAGE_CHANNELS` instead of `SESSION_CHANNELS`.

In `_session_row`, add `category=draft.category, reported_count=draft.reported_count`.

In `rebuild()`:

```python
        result = build_lineage(*load_inputs(), cfg, corrections, trip_signups=load_app_trip_signups())
        people = resolve_people(result.attendance, load_people())
        unmatched = {row["session_key"] for row in people if row["unmatched"]}
        for draft in result.sessions:
            if draft.session_key in unmatched:
                draft.flags = [*draft.flags, "unmatched_person"]
        rebuilt_at = datetime.utcnow()
        session_rows = [_session_row(draft, rebuilt_at) for draft in result.sessions]
        ...
        attendance = [dict(session_id=session_ids[row["session_key"]],
                           **{k: row[k] for k in ("slack_uid", "user_id", "person_key", "role",
                                                  "emoji", "slot", "source")})
                      for row in people]
        ...
        weeks = empty_weeks(result.sessions, corrections)
        AppConfig.set("analytics_coverage", coverage_snapshot(result.possible_misses, weeks),
                      category="analytics")
        stats = {..., "candidates": len(result.possible_misses), "empty_weeks": len(weeks)}
```

Remove the old `user_ids` query (`load_people` replaces it). Add to `rebuild.py`:

```python
def coverage_snapshot(candidate_keys, weeks) -> dict:
    rows = {f"{row.channel_id}:{row.ts}": row for row in SlackArchiveMessage.query.filter(
        func.concat(SlackArchiveMessage.channel_id, ":", SlackArchiveMessage.ts).in_(candidate_keys)).all()} \
        if candidate_keys else {}
    candidates = []
    for key in candidate_keys:
        row = rows.get(key)
        text = next((line for line in (row.text if row else "").splitlines() if line.strip()), "")
        reactions = sorted((row.raw.get("reactions", []) if row else []),
                           key=lambda r: -r.get("count", 0))[:3]
        candidates.append({"post_key": key, "channel": key.split(":")[0],
                           "date": utc_naive_to_central_naive(row.posted_at).date().isoformat() if row else "",
                           "text": text[:140],
                           "reactions": {r["name"]: r.get("count", 0) for r in reactions}})
    return {"computed_at": datetime.utcnow().isoformat(timespec="seconds"),
            "candidates": candidates, "empty_weeks": [week.isoformat() for week in weeks]}
```

(`from sqlalchemy import func` and `from app.utils import utc_naive_to_central_naive`.)

- [ ] **Step 4: CLI flags.** In `app/analytics/cli.py` `flags`: pass `trip_signups=load_app_trip_signups()` to `build_lineage`. Label the miss lines `candidate` instead of `possible_miss`. After them, print one line per empty week (`<monday>  empty_week`) using `empty_weeks(lineage.sessions, corrections)`. Add `"empty_weeks"` to the JSON output. Update `tests/analytics/test_cli_and_job.py` where it asserts the `possible_miss` label.

- [ ] **Step 5: Run the analytics suite**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/analytics -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/analytics/rebuild.py app/analytics/coverage.py app/analytics/cli.py tests/analytics/test_rebuild.py tests/analytics/test_coverage.py tests/analytics/test_cli_and_job.py
git commit -m "feat(analytics): rebuild resolves people and stores the coverage snapshot"
```

---

### Task 7 (orchestrator): Local acceptance against the dumps, then PR 1

- [ ] **Step 1: Extend the local acceptance test** `tests/analytics/test_lift_acceptance.py` (skips without the dump). Add a test that loads `general.json`, `adventures.json` and `other/tech-trip-signups.json` from `DUMP_DIR` as `ArchivedMessage` lists (see the dump files' `messages` key) and runs `build_lineage` with no corrections. It asserts:
  - Every sign-up post (`is_signup_post`) either lands on a trip session or is in `possible_misses`, and the number in `possible_misses` is 0. If it isn't, extend `trip_series` in the YAML, never special-case the code.
  - The lift acceptance still passes.
- [ ] **Step 2:** Run the analytics suite, `tests/practices/test_practice_migration_release.py`, and `tests/test_scheduler_*.py`. Run the full suite once and compare failures with `main`.
- [ ] **Step 3:** Request code review (superpowers:requesting-code-review). Open PR 1 with `gh pr create`. The body lists the schema changes, the channel additions, the new YAML keys, and the post-merge runbook (Task 8). It also says Rob must `/invite @TCSC` in `#tech-trip-signups` before merge.

### Task 8 (orchestrator): prod import after PR 1 deploys

- [ ] **Step 1:** Confirm with Rob that the bot is in `#tech-trip-signups` (re-run the membership check: `users.conversations` with the bot token).
- [ ] **Step 2:** From the dev box, against prod:

```bash
cd /workspace/tcsc-trips && set -a && source .env && set +a
export DATABASE_URL="$PROD_DATABASE_URL" TCSC_MIGRATION_ONLY=1; unset SLACK_APP_TOKEN
flask analytics import-slack --channel C0B2VN1LU11
flask analytics import-slack --channel C02HXN45214
flask analytics import-slack --channel C068ECRE0PQ
flask analytics import-slack --channel C02J1FDSBHT
flask analytics import-slack --channel C046XRWC4NR
flask analytics rebuild
flask analytics flags --json .superpowers/analytics-slack-dump/flags-attendance.json > /dev/null
```

(Memory `prod-one-off-scripts.md`: `create_app` starts the scheduler and Socket Mode unless `TCSC_MIGRATION_ONLY=1` and `SLACK_APP_TOKEN` is unset.)

- [ ] **Step 3:** Record the counts: candidates by channel, empty weeks, trip sessions with `missing_date`, unmatched people. If `#chat` alone has more than about 150 candidates, look at the top reaction names there. When an obvious applause emoji is missing from `applause_emoji`, add it in a one-line PR before the catalog pass, rather than skip it post by post.

### Task 9 (orchestrator): catalog pass

Same fixer/reviewer loop as the practice-analytics plan's Task 12 Step 5, with these inputs:

- [ ] **Step 1:** Split `flags-attendance.json` (candidates, empty weeks, trip editions) into batches of about 40.
- [ ] **Step 2:** Fixer agents (Claude subagents, no code) get: the attendance spec's "Completeness" section, the correction fields with meanings, the categories, the batch, and read-only access to the dump folder (`general*.json`, `adventures*.json`, `other/*.json`, `chan.json`, `threads.json`). For each item they return exactly one of:
  - a candidate post → `create` (`date` from the post text, never the `ts`; `start_time` when the post gives one, since weather and daylight need it; `location` when the venue is named; for copied general posts, the date comes from the footer and `reported_count` from the footer's RSVP emoji), `title`, `category`, `emoji_roles` (only the emoji the post names as attendance options; `:x:`-style "can't make it" emoji as `decline`), or `skip` with the reason class (interest poll, reminder, bring-a-dish, member-run, form-only, applause, chatter).
  - the Sep 8, 2026 kickoff (`practice:101`): `rsvp_from` the general post plus `emoji_roles {white_check_mark: rsvp, x: decline}`, and `skip` on the general post.
  - the fall 2025 kickoff and the Oct 20, 2022 cross-posted practice: `create` on the post that holds the RSVPs.
  - a trip edition → `trip:<slug>:<YYYY>` with `date` (the trip's start date, from the trip's announcement in adventures or general) and `title`.
  - an empty week → `gap:<Monday>` with `gap_ok` naming the reason seen in the channel (holiday, season break, weather cancel week), or `needs_rob`.
  Every note cites the post text that justifies it.
- [ ] **Step 3:** One reviewer agent per batch checks each proposal against the raw post and thread and returns accept or reject with a reason. Rejects go to a fresh fixer once. Anything still disputed becomes `needs_rob`.
- [ ] **Step 4:** Merge the accepted entries into `.superpowers/analytics-slack-dump/corrections.json`, then run `flask analytics corrections import` against prod, `flask analytics rebuild` and `flask analytics fetch-weather`. Repeat from Task 8 Step 2's `flags` until candidates and empty weeks are both 0 or `needs_rob`.
- [ ] **Step 5:** Send Rob the `needs_rob` list as one short message, each item with the date, what's unclear, and the proposed answer.
- [ ] **Step 6:** Verify acceptance numbers against prod read-only: the Sep 8, 2026 kickoff session has `rsvp_count` 75 and 33 `decline` rows. Every `trip` session has no `missing_date` flag. Then export corrections (`flask analytics corrections export .superpowers/analytics-slack-dump/corrections.json`).

---

# Part 2: dashboards (PR 2)

Branch PR 2 from `main` after PR 1 merges.

### Task 10: Filter catalog, attendance loader, redirect

**Files:**
- Modify: `app/analytics/dashboards/base.py`
- Modify: `app/routes/admin_analytics.py`
- Modify: `app/templates/admin/analytics/dashboard.html` (category filter control)
- Test: `tests/analytics/test_dashboard_base.py`, `tests/analytics/test_admin_analytics_routes.py`

**Interfaces:**
- Produces:
  - `Filters.categories: list[str]`, and the filter name `category` in `FILTER_NAMES` (validated against `CATEGORIES`).
  - `KINDS = ("practice", "event", "trip")`. `Filters.kinds` defaults to `[]` (all kinds) with no forced `practice`.
  - `load_attendance(session_ids, role="rsvp")` rows carry `session_id, slack_uid, person_key, user_id, slot, role`. `role` may also be a tuple of roles.
  - `_past_sessions()` excludes sessions whose `flags` contain `missing_date`.
  - `GET /admin/analytics/thursday-strength` → 302 to `/admin/analytics/practices?activity=Strength&day_of_week=Thursday`.

- [ ] **Step 1: Write the failing tests**

In `test_dashboard_base.py`, update `test_invalid_values_dropped_and_defaults_applied`. `D` fixes activities only, so `f.kinds` is now `[]`. Add:

```python
def test_category_filter_validates_against_categories():
    dashboard = Dashboard("c", "C", "?", ["category"], lambda f: [])
    f = parse_filters(MultiDict({"category": ["social", "picnic"]}), dashboard, DOMAINS)
    assert f.categories == ["social"]


def test_kinds_default_is_all():
    dashboard = Dashboard("k", "K", "?", ["kind"], lambda f: [])
    assert parse_filters(MultiDict(), dashboard, DOMAINS).kinds == []


def test_missing_date_trips_are_hidden(db_session):
    today = date(2099, 1, 5)
    undated = _session("undated", today - timedelta(days=3), kind="trip", category="trip",
                       flags=["missing_date"])
    dated = _session("dated", today - timedelta(days=2), kind="trip", category="trip")
    db_session.add_all([undated, dated])
    db_session.flush()
    with patch("app.utils.today_central", return_value=today):
        keys = [s.session_key for s in base.load_sessions(base.Filters(seasons=["2099 Test"]))]
    assert "task13:dated" in keys and "task13:undated" not in keys
```

`_session` is the existing helper in `test_dashboard_base.py`. It prefixes keys with `task13:`.

In `test_admin_analytics_routes.py`:

```python
def test_thursday_strength_redirects(admin_client):
    response = admin_client.get("/admin/analytics/thursday-strength")
    assert response.status_code == 302
    location = response.headers["Location"]
    assert "/admin/analytics/practices" in location
    assert "activity=Strength" in location and "day_of_week=Thursday" in location
```

- [ ] **Step 2: Run to verify they fail.** Run: `pytest tests/analytics/test_dashboard_base.py tests/analytics/test_admin_analytics_routes.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement.** In `base.py`:
  - Add `categories: list[str] = field(default_factory=list)` to `Filters`, and change `kinds` to `field(default_factory=list)`.
  - `FILTER_NAMES` gains `"category"`. `_FIELDS` gains `("category", "categories", "category")`.
  - `KINDS = ("practice", "event", "trip")`.
  - In `parse_filters`, add `"categories": set(CATEGORIES)` to `domains`, include `"categories"` in the fixed-domain tuple `("days", "formats", "kinds", "categories")`, and delete the `if attribute == "kinds" and not values: values = ["practice"]` lines.
  - `_past_sessions()` becomes `PracticeSession.query.filter(PracticeSession.date <= utils.today_central(), ~PracticeSession.flags.any("missing_date"))`.
  - In `load_attendance`, add `PracticeAttendance.person_key, PracticeAttendance.user_id` to the selected columns. Accept `role` as a string or tuple (`role_filter = PracticeAttendance.role.in_(role) if isinstance(role, tuple) else PracticeAttendance.role == role`).
  - `filter_options` adds `"categories": [c for c in CATEGORIES if c in _distinct(PracticeSession.category)]`.

In `dashboard.html`, add `('category', 'categories', 'Categories', filters.categories)` to the list of multi-select filters, next to `kind`.

In `admin_analytics.py`, at the top of `dashboard(slug)`:

```python
    if slug == "thursday-strength":
        return redirect(url_for(".dashboard", slug="practices", activity="Strength",
                                day_of_week="Thursday"))
```

Until Task 12 registers `practices`, the redirect target is a 404. That's fine inside this PR.

- [ ] **Step 4: Run tests.** Run: `DATABASE_URL=...tcsc_trips_test pytest tests/analytics -q`. Expected: PASS. The Thursday strength dashboard still sets `fixed kinds=["practice"]`, so its tests keep passing.

- [ ] **Step 5: Commit**

```bash
git add app/analytics/dashboards/base.py app/routes/admin_analytics.py app/templates/admin/analytics/dashboard.html tests/analytics/test_dashboard_base.py tests/analytics/test_admin_analytics_routes.py
git commit -m "feat(analytics): category filter, all-kinds default, strength redirect"
```

---

### Task 11: Move the split/merged blocks into `splits.py`

**Files:**
- Create: `app/analytics/dashboards/splits.py` (moved code)
- Modify: `app/analytics/dashboards/thursday_strength.py` (becomes a thin wrapper until Task 12 deletes it)
- Move: `tests/analytics/test_thursday_strength.py` → `tests/analytics/test_splits.py`

**Interfaces:**
- Produces: `splits.split_blocks(sessions, attendance, filters) -> list[Block]`. It returns exactly what `thursday_strength.build` returned minus the leading `Tiles` block: session chart, season chart, season table, comparison chart, preference chart, then the notes. It also exports `splits.tiles(sessions, attendance) -> Tiles` (the old `_tiles`, computing `weeks` and `lines` itself). The pure helpers (`weekly_totals`, `season_summary`, `slot_preference`, `week_of_season`, `_session_rows`) move unchanged.

- [ ] **Step 1:** `git mv tests/analytics/test_thursday_strength.py tests/analytics/test_splits.py`. Change its import to `from app.analytics.dashboards import splits as ts`. Change `_build` to patch nothing and call:

```python
def _build(sessions, attendance, filters=None):
    selected = filters or Filters(days=["Thursday"], activities=["Strength"])
    return [ts.tiles(sessions, attendance), *ts.split_blocks(sessions, attendance, selected)]
```

Tests that reference `ts.DASHBOARD` move to Task 12's test file. Delete them here.

- [ ] **Step 2:** Run `pytest tests/analytics/test_splits.py -v`. Expected: FAIL (no module `splits`).
- [ ] **Step 3:** `git mv app/analytics/dashboards/thursday_strength.py app/analytics/dashboards/splits.py`. Rename `build(filters)` to `split_blocks(sessions, attendance, filters)`: drop its two `load_*` calls and the leading `_tiles(weeks, lines)` element. Add `def tiles(sessions, attendance): weeks = weekly_totals(sessions, attendance); return _tiles(weeks, _capacity_lines([s for s in sessions if s.status != "cancelled"]))`. Remove `DASHBOARD` from `splits.py`. Recreate `thursday_strength.py` as:

```python
"""Temporary wrapper; deleted when the practice dashboard ships (Task 12)."""
from app.analytics.dashboards.base import Dashboard, load_attendance, load_sessions
from app.analytics.dashboards.splits import split_blocks, tiles


def build(filters):
    sessions = load_sessions(filters)
    attendance = load_attendance([s.id for s in sessions])
    return [tiles(sessions, attendance), *split_blocks(sessions, attendance, filters)]


DASHBOARD = Dashboard(
    slug="thursday-strength", title="Thursday strength",
    question="Should Thursday strength run as one session or two?",
    filters=["season", "date_range", "day_of_week", "format"], build=build,
    fixed={"activities": ["Strength"], "kinds": ["practice"]}, defaults={"days": ["Thursday"]},
)
```

- [ ] **Step 4:** Run `pytest tests/analytics -q`. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -m "refactor(analytics): split/merged blocks move to splits.py"`.

---

### Task 12: What makes a practice draw

**Files:**
- Create: `app/analytics/dashboards/practices.py`
- Modify: `app/analytics/charts.py` (`factor_bars`, `points`)
- Modify: `app/analytics/dashboards/__init__.py`
- Delete: `app/analytics/dashboards/thursday_strength.py`
- Test: `tests/analytics/test_practices_dashboard.py` (new), `tests/analytics/test_charts.py`

**Interfaces:**
- Consumes: `splits.split_blocks`, `base.load_sessions`, `base.load_attendance`, `charts.spec`.
- Produces:
  - `practices.nights(sessions, attendance) -> list[dict]`. One row per practice night (sessions sharing `group_key` and `date`; held sessions only). Keys: `date, season_label, day_of_week, activity, workout_type, location, start_hour (int|None), temp_f, precip_in, snow_depth_in, minutes_after_sunset, has_lead (bool), rsvps (int), formats (sorted list)`. `rsvps` counts distinct `person_key` with role `rsvp` across the night's sessions.
  - `practices.baseline_medians(rows) -> dict[(season_label, day_of_week), float]`.
  - `practices.with_index(rows, medians) -> list[dict]`. Adds `index` (`rsvps / median`, rounded to 2 places, `None` when the median is 0 or missing).
  - `practices.band(field, value) -> str`, for fields `temp_f`, `precip_in`, `snow_depth_in`, `minutes_after_sunset`, `start_hour`.
  - `practices.factor_rows(rows, key) -> list[dict]`: `{value, median_index, median_rsvps, nights, thin}` sorted by `median_index` desc, `thin` when `nights < 5`.
  - `charts.factor_bars(rows, *, title) -> dict`: horizontal bars of `median_index` by `value`, a rule at 1.0, bar opacity 0.35 when `thin`, and a text label with the night count.
  - `charts.points(rows, *, x, y, color, tooltip) -> dict`: temporal x, quantitative y, nominal color.
  - `DASHBOARD` with slug `practices`.

- [ ] **Step 1: Write the failing tests** `tests/analytics/test_practices_dashboard.py`

```python
"""Synthetic sessions only."""
import json
from datetime import date, time
from types import SimpleNamespace
from unittest.mock import patch

import jsonschema
import vl_convert as vlc

from app.analytics.dashboards import practices as p
from app.analytics.dashboards.base import Chart, Filters, Tiles
from tests.analytics.conftest import FIXTURES

SCHEMA = json.loads((FIXTURES / "vega-lite-v6.schema.json").read_text())


def _s(id, day, rsvps, group=None, activity="Run", fmt="single", temp=50.0, season="2099 Fall/Winter",
       status="held", hour=18):
    return SimpleNamespace(id=id, date=day, group_key=group or f"g{id}", season_label=season,
                           day_of_week=day.strftime("%A"), activity=activity, workout_type="Endurance",
                           location_name="Park", start_time=time(hour, 0), temp_f=temp, precip_in=0.0,
                           snow_depth_in=0.0, minutes_after_sunset=-30, format=fmt, status=status,
                           kind="practice", slot=None, rsvp_count=rsvps)


def _rsvps(session, n, start=0, role="rsvp"):
    return [SimpleNamespace(session_id=session.id, person_key=f"slack:UFAKE{start + i:04d}",
                            slack_uid=f"UFAKE{start + i:04d}", user_id=None, slot=None, role=role)
            for i in range(n)]


def test_split_night_collapses_to_one_row():
    a = _s(1, date(2099, 11, 5), 0, group="g", fmt="split")
    b = _s(2, date(2099, 11, 5), 0, group="g", fmt="split", hour=19)
    rows = p.nights([a, b], _rsvps(a, 10) + _rsvps(b, 8, start=100) + _rsvps(b, 1, start=0))
    assert len(rows) == 1 and rows[0]["rsvps"] == 18 and rows[0]["start_hour"] == 18
    assert rows[0]["formats"] == ["split"]


def test_cancelled_sessions_are_not_nights():
    s = _s(1, date(2099, 11, 5), 0, status="cancelled")
    assert p.nights([s], _rsvps(s, 5)) == []


def test_index_is_relative_to_season_weekday_median():
    rows = [{"season_label": "S", "day_of_week": "Tuesday", "rsvps": n} for n in (10, 20, 30)]
    medians = p.baseline_medians(rows)
    assert medians[("S", "Tuesday")] == 20
    assert [r["index"] for r in p.with_index(rows, medians)] == [0.5, 1.0, 1.5]
    assert p.with_index([{"season_label": "X", "day_of_week": "Monday", "rsvps": 4}], medians)[0]["index"] is None


def test_bands():
    assert p.band("temp_f", None) == "Unknown"
    assert p.band("temp_f", 5) == "Below 15°F"
    assert p.band("temp_f", 72) == "70°F and up"
    assert p.band("precip_in", 0) == "Dry"
    assert p.band("minutes_after_sunset", -10) == "Before sunset"
    assert p.band("minutes_after_sunset", 90) == "Dark"
    assert p.band("start_hour", 6) == "6 AM" and p.band("start_hour", 18) == "6 PM"


def test_factor_rows_mark_thin_groups():
    rows = [{"activity": "Run", "index": 1.0, "rsvps": 20}] * 5 + [{"activity": "Ski", "index": 2.0, "rsvps": 40}]
    out = p.factor_rows(rows, "activity")
    assert [(r["value"], r["thin"], r["nights"]) for r in out] == [("Ski", True, 1), ("Run", False, 5)]


def test_dashboard_builds_valid_specs():
    sessions = [_s(i, date(2099, 11, 3 + 7 * i), 0, activity="Run" if i % 2 else "Ski") for i in range(8)]
    attendance = [row for i, s in enumerate(sessions) for row in _rsvps(s, 10 + i)]
    with patch.object(p, "load_sessions", return_value=sessions), \
         patch.object(p, "load_attendance", return_value=attendance), \
         patch.object(p, "load_baseline_sessions", return_value=(sessions, attendance)):
        blocks = p.DASHBOARD.build(Filters(kinds=["practice"]))
    assert isinstance(blocks[0], Tiles)
    charts = [b for b in blocks if isinstance(b, Chart)]
    assert len(charts) >= 5
    for chart in charts:
        jsonschema.validate(chart.spec, SCHEMA)
        assert vlc.vegalite_to_svg(chart.spec)


def test_split_section_only_when_splits_present():
    sessions = [_s(1, date(2099, 11, 5), 0)]
    with patch.object(p, "load_sessions", return_value=sessions), \
         patch.object(p, "load_attendance", return_value=[]), \
         patch.object(p, "load_baseline_sessions", return_value=(sessions, [])), \
         patch.object(p, "split_blocks") as split:
        p.DASHBOARD.build(Filters(kinds=["practice"]))
    split.assert_not_called()
```

Add to `test_charts.py`: `factor_bars` and `points` specs validate against the schema, and `factor_bars` sets the opacity condition on `thin`.

- [ ] **Step 2: Run to verify they fail.** Run: `pytest tests/analytics/test_practices_dashboard.py -v`. Expected: FAIL (no module).

- [ ] **Step 3: Charts.** Add to `charts.py`:

```python
def factor_bars(rows, *, title) -> dict:
    height = max(80, 28 * len(rows))
    y = {"field": "value", "type": "nominal", "title": None, "sort": None}
    return {
        "data": {"values": deepcopy(rows)}, "width": "container", "height": height,
        "description": f"Median turnout index by {title}",
        "layer": [
            {"mark": {"type": "bar", "color": PALETTE["violet"], "cornerRadiusEnd": 3},
             "encoding": {"y": y,
                          "x": {"field": "median_index", "type": "quantitative", "title": "Median turnout index"},
                          "opacity": {"condition": {"test": "datum.thin", "value": 0.35}, "value": 1},
                          "tooltip": [{"field": "value", "title": title},
                                      {"field": "median_index", "title": "Median index"},
                                      {"field": "median_rsvps", "title": "Median RSVPs"},
                                      {"field": "nights", "title": "Practices"}]}},
            {"mark": {"type": "text", "align": "left", "dx": 4, "color": PALETTE["muted"]},
             "encoding": {"y": y, "x": {"field": "median_index", "type": "quantitative"},
                          "text": {"field": "nights", "type": "quantitative"}}},
            {"data": {"values": [{"one": 1}]},
             "mark": {"type": "rule", "color": PALETTE["ref"], "strokeDash": [4, 3]},
             "encoding": {"x": {"field": "one", "type": "quantitative"}}},
        ],
    }


def points(rows, *, x, y, color, tooltip, height=280) -> dict:
    return {
        "data": {"values": deepcopy(rows)}, "width": "container", "height": height,
        "description": f"{y} over time",
        "mark": {"type": "point", "filled": True, "size": 36, "opacity": 0.8},
        "encoding": {"x": {"field": x, "type": "temporal", "title": None},
                     "y": {"field": y, "type": "quantitative", "title": "RSVPs"},
                     "color": {"field": color, "type": "nominal"},
                     "tooltip": _tooltip(tooltip, y)},
    }
```

- [ ] **Step 4: Dashboard** `app/analytics/dashboards/practices.py`

```python
"""What makes a practice draw: turnout by factor, normalized per season and weekday."""
from collections import defaultdict
from datetime import date
from statistics import median

from app.analytics import charts
from app.analytics.dashboards.base import (
    Chart, Dashboard, Filters, Note, Table, Tile, Tiles, load_attendance, load_sessions,
)
from app.analytics.dashboards.splits import split_blocks

FACTORS = [("activity", "Activity"), ("workout_type", "Workout"), ("location", "Location"),
           ("start_hour", "Start time"), ("temp_f", "Temperature"), ("precip_in", "Precipitation"),
           ("snow_depth_in", "Snow depth"), ("minutes_after_sunset", "Daylight"),
           ("week_band", "Week of season"), ("lead", "Lead")]


def band(field, value):
    if value is None:
        return "Unknown"
    if field == "temp_f":
        for limit, label in ((15, "Below 15°F"), (32, "15 to 31°F"), (50, "32 to 49°F"), (70, "50 to 69°F")):
            if value < limit:
                return label
        return "70°F and up"
    if field == "precip_in":
        return "Dry" if value == 0 else "Light" if value < 0.1 else "Wet"
    if field == "snow_depth_in":
        return "No snow" if value == 0 else "Under 4 in" if value < 4 else "4 in or more"
    if field == "minutes_after_sunset":
        return "Before sunset" if value < 0 else "First hour after sunset" if value < 60 else "Dark"
    if field == "start_hour":
        return f"{value % 12 or 12} {'AM' if value < 12 else 'PM'}"
    return str(value)


def nights(sessions, attendance):
    people = defaultdict(set)
    leads = set()
    for row in attendance:
        if row.role == "rsvp":
            people[row.session_id].add(row.person_key)
        elif row.role == "lead":
            leads.add(row.session_id)
    groups = defaultdict(list)
    for session in sessions:
        if session.status == "held":
            groups[(session.group_key, session.date)].append(session)
    rows = []
    for (_, day), group in sorted(groups.items(), key=lambda item: item[0][1]):
        first = min(group, key=lambda s: (s.start_time is None, s.start_time))
        rows.append({
            "date": day.isoformat(), "season_label": first.season_label, "day_of_week": first.day_of_week,
            "activity": first.activity, "workout_type": first.workout_type,
            "location": first.location_name or "Unknown",
            "start_hour": first.start_time.hour if first.start_time else None,
            "temp_f": first.temp_f, "precip_in": first.precip_in, "snow_depth_in": first.snow_depth_in,
            "minutes_after_sunset": first.minutes_after_sunset,
            "has_lead": any(s.id in leads for s in group),
            "rsvps": len(set().union(*(people[s.id] for s in group))),
            "formats": sorted({s.format for s in group}),
        })
    return rows


def baseline_medians(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["season_label"], row["day_of_week"])].append(row["rsvps"])
    return {key: median(values) for key, values in groups.items()}


def with_index(rows, medians):
    out = []
    for row in rows:
        base = medians.get((row["season_label"], row["day_of_week"]))
        out.append({**row, "index": round(row["rsvps"] / base, 2) if base else None})
    return out


def _week_bands(rows):
    starts = {}
    for row in rows:
        starts[row["season_label"]] = min(starts.get(row["season_label"], row["date"]), row["date"])
    for row in rows:
        week = (date.fromisoformat(row["date"]) - date.fromisoformat(starts[row["season_label"]])).days // 7 + 1
        row["week_band"] = "Weeks 1 to 4" if week <= 4 else "Weeks 5 to 8" if week <= 8 else \
            "Weeks 9 to 12" if week <= 12 else "Week 13 on"
        row["lead"] = "Named lead" if row["has_lead"] else "No lead"
    return rows


def factor_rows(rows, key):
    groups = defaultdict(list)
    for row in rows:
        if row.get("index") is not None:
            value = row[key] if key in ("activity", "workout_type", "location", "week_band", "lead") \
                else band(key, row[key])
            groups[value].append(row)
    out = [{"value": value, "median_index": round(median(r["index"] for r in group), 2),
            "median_rsvps": median(r["rsvps"] for r in group), "nights": len(group),
            "thin": len(group) < 5} for value, group in groups.items()]
    return sorted(out, key=lambda r: -r["median_index"])


def load_baseline_sessions(filters):
    """All practices in the selected seasons, unfiltered by factor, so the index keeps its meaning."""
    baseline = Filters(seasons=filters.seasons, kinds=["practice"])
    sessions = load_sessions(baseline)
    return sessions, load_attendance([s.id for s in sessions], role=("rsvp", "lead"))


def _tiles(rows, people):
    if not rows:
        return Tiles([Tile(label, "No data") for label in
                      ("Practices", "Average RSVPs", "Distinct people", "Strongest draw", "Weakest draw")])
    by_activity = [r for r in factor_rows(rows, "activity") if not r["thin"]]
    return Tiles([
        Tile("Practices", len(rows)),
        Tile("Average RSVPs", f"{sum(r['rsvps'] for r in rows) / len(rows):.1f}"),
        Tile("Distinct people", people),
        Tile("Strongest draw", by_activity[0]["value"] if by_activity else "N/A",
             f"median index {by_activity[0]['median_index']}" if by_activity else ""),
        Tile("Weakest draw", by_activity[-1]["value"] if by_activity else "N/A",
             f"median index {by_activity[-1]['median_index']}" if by_activity else ""),
    ])


def build(filters):
    sessions = load_sessions(filters)
    attendance = load_attendance([s.id for s in sessions], role=("rsvp", "lead"))
    base_sessions, base_attendance = load_baseline_sessions(filters)
    medians = baseline_medians(nights(base_sessions, base_attendance))
    rows = _week_bands(with_index(nights(sessions, attendance), medians))
    people = len({row.person_key for row in attendance if row.role == "rsvp"})
    blocks = [_tiles(rows, people)]
    over_time = "Every practice night, colored by activity."
    blocks.append(Chart("Turnout over time", over_time,
                        charts.spec(over_time, charts.points(rows, x="date", y="rsvps", color="activity",
                                                             tooltip=["date", "activity", "location", "rsvps", "index"])),
                        rows, [("date", "Date"), ("activity", "Activity"), ("location", "Location"),
                               ("rsvps", "RSVPs"), ("index", "Index")]))
    for key, label in FACTORS:
        factor = factor_rows(rows, key)
        description = f"Median turnout index by {label.lower()}. 1.0 is a typical practice for that season and weekday."
        blocks.append(Chart(label, description, charts.spec(description, charts.factor_bars(factor, title=label)),
                            factor, [("value", label), ("median_index", "Median index"),
                                     ("median_rsvps", "Median RSVPs"), ("nights", "Practices")]))
    if any(set(row["formats"]) & {"split", "merged"} for row in rows):
        split_attendance = [row for row in attendance if row.role == "rsvp"]
        blocks.extend(split_blocks(sessions, split_attendance, filters))
    blocks.append(Table("Every practice", rows, [
        ("date", "Date"), ("day_of_week", "Day"), ("activity", "Activity"), ("workout_type", "Workout"),
        ("location", "Location"), ("rsvps", "RSVPs"), ("index", "Index"), ("temp_f", "Temp °F")]))
    blocks += [Note("Turnout index: a practice's RSVPs divided by the median for practices on the same "
                    "weekday in the same season. 1.2 means 20% above a typical practice for that slot."),
               Note("Faded bars have fewer than 5 practices behind them. Read them as anecdotes."),
               Note("RSVPs are not headcount. Some people RSVP and skip, some come without reacting.")]
    return blocks


DASHBOARD = Dashboard(
    slug="practices", title="What makes a practice draw",
    question="Which days, times, activities, places and conditions bring people out?",
    filters=["season", "date_range", "day_of_week", "activity", "workout_type", "location", "format"],
    build=build, fixed={"kinds": ["practice"]},
)
```

- [ ] **Step 5: Registry.** `dashboards/__init__.py` imports `practices` and sets `DASHBOARDS = [PRACTICES]`. Task 13 and Task 14 append theirs. Delete `thursday_strength.py`.

- [ ] **Step 6: Run tests.** Run: `DATABASE_URL=...tcsc_trips_test pytest tests/analytics -q`. Expected: PASS, including `test_thursday_strength_redirects` (the target now exists) and the lift acceptance test.

- [ ] **Step 7: Commit**

```bash
git add -A app/analytics tests/analytics
git commit -m "feat(analytics): practice draw dashboard replaces Thursday strength"
```

---

### Task 13: Who comes and who drifts

**Files:**
- Create: `app/analytics/dashboards/people.py`
- Modify: `app/analytics/dashboards/__init__.py`
- Test: `tests/analytics/test_people_dashboard.py` (new)

**Interfaces:**
- Consumes: `load_sessions`, `load_attendance(role=("rsvp", "signup"))`, `charts.grouped_bars`, `charts.stacked_columns`, `Season.get_current()`, `UserSeason`.
- Produces (pure, over `(person_key, session)` pairs):
  - `season_key(label) -> tuple[int, int]`. `"2099 Spring/Summer"` gives `(2099, 0)` and `"2099 Fall/Winter"` gives `(2099, 1)`. Unknown labels give `(0, 0)`.
  - `attendance_pairs(sessions, attendance) -> list[tuple[str, session]]`. Held sessions only, count-only sessions dropped, roles `rsvp`/`signup`.
  - `retention(pairs) -> list[dict]`: `{season_label, next_season, group ("First season"|"Returning"), people, returned, rate}` for every season whose next same-type season has data.
  - `newcomer_curve(pairs) -> list[dict]`: `{season_label, bucket ("1","2","3","4 to 5","6 or more"), people}`.
  - `overlap(pairs) -> list[dict]`: `{combo, people}`, where combo is a `" + "`-joined sorted set of `Practice`/`Event`/`Trip`.
  - `lapsed_regulars(pairs, today) -> list[dict]`: `{person_key, last_rsvp, last_season_count, this_season_count}`. The current season is the season label of the latest session on or before today. "Running" means a practice in the last 14 days. A person qualifies with 6+ practice RSVPs in the previous same-type season and none in the last 28 days.
  - `everyone(pairs, current_label) -> list[dict]`: `{person_key, first_seen, last_seen, practice_this, event_this, trip_this, practice_last, all_time}`.
  - `display_names(person_keys) -> dict[str, str]`: DB lookup. `slack:` → `users` via `slack_users`, `user:` → `users.id`, `name:` → title case of the name.
  - `never_rsvpd() -> list[dict]`: DB. `{name}` for each `ACTIVE` `UserSeason` of `Season.get_current()` whose user has no `rsvp`/`signup` attendance row on a session dated on or after that season's `start_date`.
  - `DASHBOARD` slug `people`, filters `season`, `kind`.

- [ ] **Step 1: Write the failing tests** `tests/analytics/test_people_dashboard.py`

```python
"""Synthetic people only."""
from datetime import date
from types import SimpleNamespace

from app.analytics.dashboards import people as pp


def _s(id, day, season, kind="practice", reported=None, status="held"):
    return SimpleNamespace(id=id, date=day, season_label=season, kind=kind,
                           reported_count=reported, status=status)


def _a(session, person, role="rsvp"):
    return SimpleNamespace(session_id=session.id, person_key=person, role=role)


F24, F25 = "2098 Fall/Winter", "2099 Fall/Winter"


def test_season_key_orders_labels():
    assert sorted(["2099 Fall/Winter", "2099 Spring/Summer", "2098 Fall/Winter"], key=pp.season_key) == [
        "2098 Fall/Winter", "2099 Spring/Summer", "2099 Fall/Winter"]


def test_pairs_drop_count_only_cancelled_and_declines():
    s1, s2, s3 = _s(1, date(2099, 1, 1), F24), _s(2, date(2099, 1, 2), F24, reported=40), \
        _s(3, date(2099, 1, 3), F24, status="cancelled")
    pairs = pp.attendance_pairs([s1, s2, s3], [_a(s1, "a"), _a(s1, "b", "decline"), _a(s3, "c")])
    assert [(p, s.id) for p, s in pairs] == [("a", 1)]


def test_retention_splits_first_season_and_returning():
    old = _s(1, date(2098, 1, 1), "2097 Fall/Winter")
    a, b = _s(2, date(2099, 1, 1), F24), _s(3, date(2100, 1, 1), F25)
    pairs = [("vet", old), ("vet", a), ("new", a), ("new2", a), ("vet", b), ("new", b)]
    rows = {(r["season_label"], r["group"]): r for r in pp.retention(pairs)}
    assert rows[(F24, "Returning")]["rate"] == 1.0
    assert (rows[(F24, "First season")]["people"], rows[(F24, "First season")]["returned"]) == (2, 1)


def test_newcomer_curve_buckets():
    sessions = [_s(i, date(2099, 1, i), F24) for i in range(1, 8)]
    pairs = [("one", sessions[0])] + [("seven", s) for s in sessions]
    rows = {r["bucket"]: r["people"] for r in pp.newcomer_curve(pairs) if r["season_label"] == F24}
    assert rows["1"] == 1 and rows["6 or more"] == 1 and rows["2"] == 0


def test_overlap_combos():
    p, e, t = _s(1, date(2099, 1, 1), F24), _s(2, date(2099, 1, 2), F24, "event"), _s(3, date(2099, 1, 3), F24, "trip")
    rows = {r["combo"]: r["people"] for r in pp.overlap([("x", p), ("x", e), ("y", t), ("z", p)])}
    assert rows == {"Event + Practice": 1, "Trip": 1, "Practice": 1}


def test_lapsed_regular():
    last = [_s(i, date(2098, 11, i), F24) for i in range(1, 7)]
    now = [_s(10, date(2099, 11, 1), F25), _s(11, date(2099, 11, 25), F25)]
    pairs = [("reg", s) for s in last] + [("reg", now[0]), ("other", now[1])]
    rows = pp.lapsed_regulars(pairs, today=date(2099, 11, 30))
    assert [(r["person_key"], r["last_season_count"], r["this_season_count"]) for r in rows] == [("reg", 6, 1)]
    assert pp.lapsed_regulars(pairs, today=date(2099, 11, 20)) == []    # no practice in the last 14 days
```

Add one DB test for `display_names` and `never_rsvpd`, following the seeding pattern in `test_rebuild.py`. Seed a user with a Slack user, an ACTIVE `UserSeason` in a current `Season`, and no attendance. Assert the user's name appears in `never_rsvpd()` and `display_names(["slack:UFAKE0001", "name:pat example"])` returns the full name and `"Pat Example"`.

- [ ] **Step 2: Run to verify they fail.** Run: `pytest tests/analytics/test_people_dashboard.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement** `app/analytics/dashboards/people.py`

```python
"""Who comes and who drifts. Names are shown; every /admin user can see them."""
from collections import defaultdict
from datetime import timedelta

from app import utils
from app.analytics import charts
from app.analytics.dashboards.base import (
    Chart, Dashboard, Filters, Note, Table, Tile, Tiles, load_attendance, load_sessions,
)
from app.analytics.models import PracticeAttendance, PracticeSession
from app.models import Season, SlackUser, User, UserSeason, db

KIND_LABELS = {"practice": "Practice", "event": "Event", "trip": "Trip"}
BUCKETS = ("1", "2", "3", "4 to 5", "6 or more")


def season_key(label):
    year, _, kind = label.partition(" ")
    return (int(year), 1 if kind == "Fall/Winter" else 0) if year.isdigit() else (0, 0)


def _shift(label, years):
    year, _, kind = (label or "").partition(" ")
    return f"{int(year) + years} {kind}" if year.isdigit() else None


def attendance_pairs(sessions, attendance):
    by_id = {s.id: s for s in sessions if s.status == "held" and s.reported_count is None}
    pairs = {(row.person_key, row.session_id): by_id[row.session_id] for row in attendance
             if row.role in ("rsvp", "signup") and row.session_id in by_id}
    return sorted(((person, session) for (person, _), session in pairs.items()),
                  key=lambda pair: (pair[1].date, pair[0]))


def _by_season(pairs):
    seasons = defaultdict(lambda: defaultdict(int))
    for person, session in pairs:
        seasons[session.season_label][person] += 1
    return seasons


def _first_season(pairs):
    first = {}
    for person, session in pairs:           # pairs are date-ordered
        first.setdefault(person, session.season_label)
    return first


def retention(pairs):
    seasons, first, rows = _by_season(pairs), _first_season(pairs), []
    for label in sorted(seasons, key=season_key):
        following = _shift(label, 1)
        if following not in seasons:
            continue
        for group in ("First season", "Returning"):
            people = [p for p in seasons[label] if (first[p] == label) == (group == "First season")]
            returned = sum(p in seasons[following] for p in people)
            rows.append({"season_label": label, "next_season": following, "group": group,
                         "people": len(people), "returned": returned,
                         "rate": round(returned / len(people), 2) if people else 0.0})
    return rows


def _bucket(count):
    return str(count) if count <= 3 else "4 to 5" if count <= 5 else "6 or more"


def newcomer_curve(pairs):
    seasons, first, rows = _by_season(pairs), _first_season(pairs), []
    for label in sorted(seasons, key=season_key):
        counts = [n for person, n in seasons[label].items() if first[person] == label]
        rows.extend({"season_label": label, "bucket": bucket,
                     "people": sum(_bucket(n) == bucket for n in counts)} for bucket in BUCKETS)
    return rows


def overlap(pairs):
    kinds = defaultdict(set)
    for person, session in pairs:
        kinds[person].add(KIND_LABELS[session.kind])
    counts = defaultdict(int)
    for labels in kinds.values():
        counts[" + ".join(sorted(labels))] += 1
    return [{"combo": combo, "people": n} for combo, n in sorted(counts.items(), key=lambda kv: -kv[1])]


def current_label(pairs, today):
    past = [session for _, session in pairs if session.date <= today]
    return max(past, key=lambda s: s.date).season_label if past else None


def lapsed_regulars(pairs, today):
    current = current_label(pairs, today)
    previous = _shift(current, -1)
    practices = [(p, s) for p, s in pairs if s.kind == "practice" and s.date <= today]
    if current is None or not any(s.date >= today - timedelta(days=14) for _, s in practices):
        return []
    last_count, this_count, last_seen = defaultdict(int), defaultdict(int), {}
    for person, session in practices:
        last_count[person] += session.season_label == previous
        this_count[person] += session.season_label == current
        last_seen[person] = max(last_seen.get(person, session.date), session.date)
    cutoff = today - timedelta(days=28)
    rows = [{"person_key": p, "last_rsvp": last_seen[p].isoformat(), "last_season_count": n,
             "this_season_count": this_count[p]}
            for p, n in last_count.items() if n >= 6 and last_seen[p] < cutoff]
    return sorted(rows, key=lambda r: r["last_rsvp"])


def everyone(pairs, current):
    previous, rows = _shift(current, -1), {}
    for person, session in pairs:
        row = rows.setdefault(person, {"person_key": person, "first_seen": session.date,
                                       "last_seen": session.date, "practice_this": 0, "event_this": 0,
                                       "trip_this": 0, "practice_last": 0, "all_time": 0})
        row["last_seen"] = max(row["last_seen"], session.date)
        row["all_time"] += 1
        if session.season_label == current:
            row[f"{session.kind}_this"] += 1
        if session.season_label == previous and session.kind == "practice":
            row["practice_last"] += 1
    return [{**row, "first_seen": row["first_seen"].isoformat(), "last_seen": row["last_seen"].isoformat()}
            for row in sorted(rows.values(), key=lambda r: r["last_seen"], reverse=True)]


def display_names(keys):
    keys = list(dict.fromkeys(keys))
    uids = [key[6:] for key in keys if key.startswith("slack:")]
    ids = [int(key[5:]) for key in keys if key.startswith("user:")]
    names = {}
    if uids:
        for uid, first, last in db.session.query(SlackUser.slack_uid, User.first_name, User.last_name).join(
                User, User.slack_user_id == SlackUser.id).filter(SlackUser.slack_uid.in_(uids)):
            names[f"slack:{uid}"] = f"{first} {last}"
        for uid, full in db.session.query(SlackUser.slack_uid, SlackUser.full_name).filter(
                SlackUser.slack_uid.in_(uids)):
            names.setdefault(f"slack:{uid}", full or uid)
    if ids:
        for user_id, first, last in db.session.query(User.id, User.first_name, User.last_name).filter(
                User.id.in_(ids)):
            names[f"user:{user_id}"] = f"{first} {last}"
    for key in keys:
        names.setdefault(key, key[5:].title() if key.startswith("name:") else key)
    return names


def never_rsvpd():
    season = Season.get_current()
    if season is None:
        return []
    came = db.session.query(PracticeAttendance.user_id).join(PracticeSession).filter(
        PracticeSession.date >= season.start_date, PracticeAttendance.user_id.isnot(None),
        PracticeAttendance.role.in_(("rsvp", "signup")))
    rows = db.session.query(User.first_name, User.last_name).join(
        UserSeason, UserSeason.user_id == User.id).filter(
        UserSeason.season_id == season.id, UserSeason.status == "ACTIVE",
        ~User.id.in_(came)).order_by(User.last_name, User.first_name).all()
    return [{"name": f"{first} {last}"} for first, last in rows]


def build(filters):
    everything = load_sessions(Filters(kinds=filters.kinds))
    pairs = attendance_pairs(everything, load_attendance([s.id for s in everything], role=("rsvp", "signup")))
    today = utils.today_central()
    current = current_label(pairs, today)
    lapsed = lapsed_regulars(pairs, today)
    names = display_names([p for p, _ in pairs])
    selected = [(p, s) for p, s in pairs if not filters.seasons or s.season_label in filters.seasons]

    this_season = _by_season(pairs).get(current, {})
    first = _first_season(pairs)
    practice_counts = defaultdict(int)
    for person, session in pairs:
        if session.season_label == current and session.kind == "practice":
            practice_counts[person] += 1
    tiles = Tiles([
        Tile("People this season", len(this_season), current or ""),
        Tile("Regulars", sum(n >= 6 for n in practice_counts.values()), "6 or more practices this season"),
        Tile("First-timers", sum(first[p] == current for p in this_season), "first time ever this season"),
        Tile("Lapsed regulars", len(lapsed), "regular last season, gone 4 weeks"),
    ])
    retained = retention(selected)
    retention_description = "Share of each season's people who came back the next season of the same type."
    newcomers = newcomer_curve(selected)
    newcomer_description = "People in their first season, by how many sessions they came to that season."
    return [
        tiles,
        Chart("Coming back next season", retention_description,
              charts.spec(retention_description, charts.grouped_bars(
                  retained, x="season_label", y="rate", color="group",
                  color_domain=["First season", "Returning"],
                  color_range=[charts.PALETTE["early"], charts.PALETTE["violet"]],
                  x_title="Season", y_title="Came back", tooltip=["season_label", "group", "people", "returned", "rate"])),
              retained, [("season_label", "Season"), ("group", "Group"), ("people", "People"),
                         ("returned", "Came back"), ("rate", "Rate")]),
        Chart("How far newcomers get", newcomer_description,
              charts.spec(newcomer_description, charts.stacked_columns(
                  newcomers, x="season_label", y="people", color="bucket", color_domain=list(BUCKETS),
                  color_range=["#c7d2fe", "#a5b4fc", "#818cf8", "#6366f1", "#4a3aa7"],
                  x_title="Season", y_title="People", tooltip=["season_label", "bucket", "people"])),
              newcomers, [("season_label", "Season"), ("bucket", "Sessions"), ("people", "People")]),
        Table("Who comes to what", overlap(selected), [("combo", "Comes to"), ("people", "People")]),
        Table("Lapsed regulars", [{**row, "name": names[row["person_key"]]} for row in lapsed],
              [("name", "Name"), ("last_rsvp", "Last RSVP"), ("last_season_count", "Last season"),
               ("this_season_count", "This season")]),
        Table("Registered, never RSVP'd", never_rsvpd(), [("name", "Name")]),
        Table("Everyone", [{**row, "name": names[row["person_key"]]} for row in everyone(pairs, current)],
              [("name", "Name"), ("first_seen", "First seen"), ("last_seen", "Last seen"),
               ("practice_this", "Practices this season"), ("event_this", "Events this season"),
               ("trip_this", "Trips this season"), ("practice_last", "Practices last season"),
               ("all_time", "All time")]),
        Note("A person counts as coming when they RSVP'd or signed up. Count-only sessions from the "
             "old general channel have no names, so they are left out here."),
    ]


DASHBOARD = Dashboard(
    slug="people", title="Who comes and who drifts",
    question="Who keeps coming, who stops, and who never started?",
    filters=["season", "kind"], build=build,
)
```

The season filter narrows the retention, newcomer and overlap views. Tiles, lapsed regulars, never-RSVP'd and Everyone always use full history, which is why `build` loads sessions without the season filter.

- [ ] **Step 4: Registry.** Append `PEOPLE` to `DASHBOARDS`.
- [ ] **Step 5: Run tests.** `DATABASE_URL=...tcsc_trips_test pytest tests/analytics -q`. Expected: PASS. Add a build test like Task 12's, with every chart spec validated against the schema.
- [ ] **Step 6: Commit** `git commit -m "feat(analytics): who comes and who drifts dashboard"`.

---

### Task 14: Data coverage dashboard

**Files:**
- Create: `app/analytics/dashboards/coverage.py`
- Modify: `app/analytics/dashboards/__init__.py`
- Test: `tests/analytics/test_coverage_dashboard.py` (new)

**Interfaces:**
- Consumes: `AppConfig.get("analytics_coverage")` (Task 6), `SlackArchiveMessage.synced_at`, `SYNC_CHANNELS`, `CHANNELS`, `PracticeSession`.
- Produces: `DASHBOARD` slug `coverage`, no filters. Pure helpers `weekly_counts(rows) -> list[dict]` (`{week, kind, sessions}`) and `freshness(rows, now) -> list[dict]` (`{channel, last_synced, fresh: bool}`, fresh when within 48 hours).

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date, datetime, timedelta
from unittest.mock import patch

from app.analytics.dashboards import coverage as cv
from app.analytics.dashboards.base import Filters, Tiles


def test_freshness():
    now = datetime(2099, 1, 3, 12)
    rows = cv.freshness([("C042G463AQ1", now - timedelta(hours=10)), ("C02J1FDSBHT", now - timedelta(days=3))], now)
    assert [(r["channel"], r["fresh"]) for r in rows] == [("announcements-practices", True), ("chat", False)]


def test_weekly_counts_group_by_monday_and_kind():
    rows = cv.weekly_counts([(date(2099, 1, 6), "practice"), (date(2099, 1, 8), "practice"),
                             (date(2099, 1, 8), "event")])
    assert rows == [{"week": "2099-01-05", "kind": "event", "sessions": 1},
                    {"week": "2099-01-05", "kind": "practice", "sessions": 2}]


def test_build_with_empty_snapshot():
    with patch.object(cv, "_snapshot", return_value=None), \
         patch.object(cv, "_session_dates", return_value=[]), \
         patch.object(cv, "_sync_rows", return_value=[]), \
         patch.object(cv, "_soft_items", return_value=[]):
        blocks = cv.DASHBOARD.build(Filters())
    assert isinstance(blocks[0], Tiles)
    assert blocks[0].tiles[0].value == "Not computed yet"
```

- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** `app/analytics/dashboards/coverage.py`

```python
"""Is the data set complete? Candidates, empty weeks, sync freshness, soft items."""
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func

from app.analytics import CHANNELS, SYNC_CHANNELS, charts
from app.analytics.dashboards.base import Chart, Dashboard, Note, Table, Tile, Tiles
from app.analytics.models import PracticeSession, SlackArchiveMessage
from app.models import AppConfig, db

SOFT_FLAGS = ["identities_lost", "unmatched_person", "missing_date"]


def freshness(rows, now):
    return [{"channel": CHANNELS.get(channel, channel),
             "last_synced": synced.isoformat(sep=" ", timespec="minutes") if synced else "never",
             "fresh": bool(synced) and now - synced <= timedelta(hours=48)} for channel, synced in rows]


def weekly_counts(rows):
    counts = defaultdict(int)
    for day, kind in rows:
        counts[((day - timedelta(days=day.weekday())).isoformat(), kind)] += 1
    return [{"week": week, "kind": kind, "sessions": n} for (week, kind), n in sorted(counts.items())]


def _snapshot():
    return AppConfig.get("analytics_coverage")


def _session_dates():
    return db.session.query(PracticeSession.date, PracticeSession.kind).all()


def _sync_rows():
    found = dict(db.session.query(SlackArchiveMessage.channel_id, func.max(SlackArchiveMessage.synced_at))
                 .filter(SlackArchiveMessage.channel_id.in_(SYNC_CHANNELS))
                 .group_by(SlackArchiveMessage.channel_id).all())
    return [(channel, found.get(channel)) for channel in SYNC_CHANNELS]


def _soft_items():
    rows = PracticeSession.query.filter(PracticeSession.flags.overlap(SOFT_FLAGS)).order_by(
        PracticeSession.date).all()
    return [{"date": s.date.isoformat(), "title": s.title,
             "flag": ", ".join(f for f in s.flags if f in SOFT_FLAGS)} for s in rows]


def build(filters):
    snapshot = _snapshot()
    sync = freshness(_sync_rows(), datetime.utcnow())
    soft = _soft_items()
    candidates = snapshot["candidates"] if snapshot else []
    empty = snapshot["empty_weeks"] if snapshot else []
    tiles = Tiles([
        Tile("Unresolved candidates", len(candidates) if snapshot else "Not computed yet"),
        Tile("Empty weeks", len(empty) if snapshot else "Not computed yet"),
        Tile("Channels synced", f"{sum(r['fresh'] for r in sync)} of {len(sync)}", "in the last 48 hours"),
        Tile("Soft items", len(soft), "count-only, unmatched, undated"),
    ])
    candidate_rows = [{**row, "channel": CHANNELS.get(row["channel"], row["channel"]),
                       "reactions": ", ".join(f"{name} {n}" for name, n in row["reactions"].items())}
                      for row in candidates]
    weeks = weekly_counts(_session_dates())
    description = "Sessions per week by kind across all history. Red lines are weeks inside a practice season with no practice."
    body = charts.stacked_columns(weeks, x="week", y="sessions", color="kind",
                                  color_domain=["practice", "event", "trip"],
                                  color_range=[charts.PALETTE["violet"], charts.PALETTE["early"], charts.PALETTE["late"]],
                                  x_title="Week", y_title="Sessions", tooltip=["week", "kind", "sessions"],
                                  x_type="temporal")
    gaps = {"data": {"values": [{"week": week} for week in empty]},
            "mark": {"type": "rule", "color": "#dc2626", "strokeWidth": 1},
            "encoding": {"x": {"field": "week", "type": "temporal"}}}
    chart_spec = charts.spec(description, charts.layered(body, gaps) if empty else body)
    return [
        tiles,
        Table("Unresolved candidates", candidate_rows, [("date", "Posted"), ("channel", "Channel"),
                                                        ("text", "Text"), ("reactions", "Top reactions"),
                                                        ("post_key", "Post key")]),
        Chart("Sessions per week", description, chart_spec, weeks,
              [("week", "Week of"), ("kind", "Kind"), ("sessions", "Sessions")]),
        Table("Empty weeks", [{"week": week} for week in empty], [("week", "Week of")]),
        Table("Sync freshness", sync, [("channel", "Channel"), ("last_synced", "Last synced (UTC)"),
                                       ("fresh", "Fresh")]),
        Table("Soft items", soft, [("date", "Date"), ("title", "Session"), ("flag", "Flag")]),
        Note("Complete means zero unresolved candidates and zero empty weeks. "
             "Claude resolves new candidates with catalog corrections."),
    ]


DASHBOARD = Dashboard(slug="coverage", title="Data coverage",
                      question="Is every club happening in the data, and what is missing?",
                      filters=[], build=build)
```

- [ ] **Step 4: Registry.** Append `COVERAGE`. Final order: `[PRACTICES, PEOPLE, COVERAGE]`.
- [ ] **Step 5: Run tests.** Run the analytics suite. Expected: PASS.
- [ ] **Step 6: Commit** `git commit -m "feat(analytics): data coverage dashboard"`.

---

### Task 15 (orchestrator): visual check, review, PR 2

- [ ] **Step 1:** Serve the branch locally against prod read-only (memory `practice-analytics-project.md`: `PGOPTIONS='-c default_transaction_read_only=on'` with `DATABASE_URL=$PROD_DATABASE_URL`, `TCSC_MIGRATION_ONLY=1`, `SLACK_APP_TOKEN` unset, in a herdr pane on this project's port block). Screenshot each dashboard at 1280 and 390 wide with the headless chromium recipe (memory `headless-chromium-screenshots.md`). Check the practices dashboard with Strength and Thursday selected against the old dashboard's numbers.
- [ ] **Step 2:** Run the full analytics suite and the full test suite. Compare failures with `main`.
- [ ] **Step 3:** Request code review. Open PR 2 with screenshots in the body. After deploy, verify on prod that `/admin/analytics/thursday-strength` redirects and that all three dashboards load.
- [ ] **Step 4:** Update the project memory (`attendance-analytics-project.md`) with the final state and the ongoing task: resolve new candidates periodically.
