# Lead Availability Poll & Capture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Post one emoji-reaction poll per practice block, capture reactions into the database as availability, reconcile against Slack's own reaction state, and DM only the people who have not answered.

**Architecture:** A `LeadAvailabilityPoll` owns one Slack message and a persisted emoji↔practice mapping. Reactions arrive through the existing `handle_attendance_reaction` router, which gains an availability branch ahead of its attendance logic. Slack maintains the reaction counts itself, so the bot never rewrites the poll — no `chat.update`, no concurrency hazard. A daily job reconciles via `reactions.get` and nudges non-responders.

**Tech Stack:** Flask, SQLAlchemy, Alembic, APScheduler, slack-sdk / slack-bolt, pytest with PostgreSQL fixtures.

Plan 2 of 3 from `docs/superpowers/specs/2026-07-25-lead-availability-design.md`. **Requires Plan 1** — polls are built from draft practices and refuse to open until those drafts are ready.

## Global Constraints

- Python 3.12+. Type-annotate new code in the style of the surrounding module.
- `PracticeStatus` is a `str, Enum` (`.value` is correct). `UserStatus` / `UserSeasonStatus` are plain strings — never call `.value`.
- Use `now_central_naive()` / `today_central()` from `app/utils.py`, never `datetime.now()`.
- Scheduler times are `America/Chicago`.
- **Letter emoji are custom workspace emoji named `letter_a` … `letter_z`.** They were renamed once already during Phase 0 (`regional_indicator_*` → `letter_*`) and that rename silently broke a live poll. They are therefore configuration, never hardcoded, and the set is validated before any poll opens.
- `✅` (`white_check_mark`) means "that's everything from me", including picking nothing. It is never a session.
- Approved poll copy, exact:
  - Title: `Practice Leads July 21 - Aug 13` (i.e. `Practice Leads {start} - {end}`)
  - Instruction: `React to each session you can lead. · :white_check_mark: when you're done, even if you picked nothing.`
  - No deadline footer.
- Approved nudge DM copy, exact:
  - Body: `Reminder: Provide lead availability for {start} – {end} in <#{channel}>`
  - Context: `To suppress these, if you can't lead at all just hit the :white_check_mark: on the post there.`
  - One button labelled `Go to post`, a URL button to the poll permalink.
- Requires the `reactions:read` Slack scope. **Verify it is granted before Task 5** — reconciliation depends on it.
- Run the suite with `pytest`.

> **Slack error handling — applies to every Slack call in this plan.** Catching only
> `SlackApiError` is insufficient. `get_slack_client()` raises `ValueError` when
> `SLACK_BOT_TOKEN` is unset, and network failures raise `TimeoutError` — both would
> crash a scheduled job that has already written good data. Follow the codebase's
> established pattern (see `_delete_slack_message` in
> `app/slack/practices/announcements.py:1361`): an `except SlackApiError` branch for
> the structured error, then an `except Exception as exc: return {"success": False,
> "error": str(exc)}` backstop. Every Slack-calling function in this plan needs both,
> and a test covering a non-`SlackApiError` failure.

---

### Task 1: Poll schema

**Files:**
- Create: `app/practices/availability_models.py`
- Modify: `app/practices/models.py` (import the new models at the bottom so Alembic sees them)
- Create: `migrations/versions/<generated>_add_lead_availability_tables.py`
- Test: `tests/practices/test_availability_schema.py`

**Interfaces:**
- Consumes: `Practice.is_draft`, `Practice.leads_needed` (Plan 1).
- Produces:
  - `LeadAvailabilityPoll` — `id, starts_on, ends_on, status, is_shadow, channel_id, message_ts, created_at, opened_at, closed_at`
  - `LeadAvailabilityPollPractice` — `id, poll_id, practice_id, emoji, position`
  - `LeadAvailabilityParticipant` — `id, poll_id, user_id, status, last_nudged_at, nudge_count`
  - `LeadAvailabilityResponse` — `id, poll_id, practice_id, user_id, responded_at, source, answered_for_date, answered_for_location_id`
  - `PollStatus` with `DRAFT = 'draft'`, `OPEN = 'open'`, `CLOSED = 'closed'`
  - `ParticipantStatus` with `PENDING = 'pending'`, `RESPONDED = 'responded'`, `DONE = 'done'`, `OPTED_OUT = 'opted_out'`

A response row *means* available — there is no boolean. Removing a reaction deletes the row. `answered_for_date` / `answered_for_location_id` snapshot what the practice looked like when the person answered, which is how staleness is detected in Plan 3.

- [ ] **Step 1: Write the failing test**

Create `tests/practices/test_availability_schema.py`:

```python
"""Lead availability schema."""

from datetime import date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import db
from app.practices.availability_models import (
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.models import Practice


def _poll():
    poll = LeadAvailabilityPoll(
        starts_on=date(2026, 7, 21),
        ends_on=date(2026, 8, 13),
        channel_id="C0B3Y71PG92",
    )
    db.session.add(poll)
    db.session.flush()
    return poll


def _practice(day):
    p = Practice(date=datetime(2026, 8, day, 18, 15),
                 day_of_week="Tuesday", is_draft=True)
    db.session.add(p)
    db.session.flush()
    return p


def test_poll_defaults_to_draft_and_not_shadow(db_session):
    poll = _poll()
    db_session.commit()
    assert poll.status == PollStatus.DRAFT
    assert poll.is_shadow is False


def test_emoji_is_unique_within_a_poll(db_session):
    poll, a, b = _poll(), _practice(4), _practice(6)
    db_session.add(LeadAvailabilityPollPractice(
        poll_id=poll.id, practice_id=a.id, emoji="letter_a", position=0))
    db_session.add(LeadAvailabilityPollPractice(
        poll_id=poll.id, practice_id=b.id, emoji="letter_a", position=1))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_one_response_per_person_per_practice(db_session):
    poll, practice = _poll(), _practice(4)
    db_session.commit()
    for _ in range(2):
        db_session.add(LeadAvailabilityResponse(
            poll_id=poll.id, practice_id=practice.id, user_id=1,
            source="reaction"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_response_snapshots_practice_details(db_session):
    poll, practice = _poll(), _practice(4)
    response = LeadAvailabilityResponse(
        poll_id=poll.id, practice_id=practice.id, user_id=1, source="reaction",
        answered_for_date=practice.date, answered_for_location_id=practice.location_id,
    )
    db_session.add(response)
    db_session.commit()
    assert response.answered_for_date == datetime(2026, 8, 4, 18, 15)


def test_participant_statuses_exist():
    assert ParticipantStatus.PENDING == "pending"
    assert ParticipantStatus.RESPONDED == "responded"
    assert ParticipantStatus.DONE == "done"
    assert ParticipantStatus.OPTED_OUT == "opted_out"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/practices/test_availability_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.practices.availability_models'`

- [ ] **Step 3: Implement the models**

Create `app/practices/availability_models.py`:

```python
"""Lead availability poll models.

A poll owns one Slack message and the emoji-to-practice mapping for it. The
mapping is persisted because inbound reaction events identify only an emoji
name, and because the custom letter emoji have already been renamed once.
"""

from datetime import datetime

from app.models import db


class PollStatus:
    """Plain strings, matching the project's status-field convention."""
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class ParticipantStatus:
    PENDING = "pending"
    RESPONDED = "responded"
    DONE = "done"
    OPTED_OUT = "opted_out"


class LeadAvailabilityPoll(db.Model):
    __tablename__ = "lead_availability_polls"

    id = db.Column(db.Integer, primary_key=True)
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=PollStatus.DRAFT)
    is_shadow = db.Column(db.Boolean, nullable=False, default=False)

    channel_id = db.Column(db.String(50), nullable=False)
    message_ts = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    opened_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    practices = db.relationship(
        "LeadAvailabilityPollPractice", backref="poll",
        cascade="all, delete-orphan", order_by="LeadAvailabilityPollPractice.position",
    )
    participants = db.relationship(
        "LeadAvailabilityParticipant", backref="poll", cascade="all, delete-orphan")
    responses = db.relationship(
        "LeadAvailabilityResponse", backref="poll", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LeadAvailabilityPoll {self.starts_on}..{self.ends_on} {self.status}>"


class LeadAvailabilityPollPractice(db.Model):
    """Emoji-to-practice mapping. Position survives an emoji rename."""
    __tablename__ = "lead_availability_poll_practices"

    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("lead_availability_polls.id"), nullable=False)
    practice_id = db.Column(db.Integer, db.ForeignKey("practices.id"), nullable=False)
    emoji = db.Column(db.String(80), nullable=False)
    position = db.Column(db.Integer, nullable=False)

    practice = db.relationship("Practice")

    __table_args__ = (
        db.UniqueConstraint("poll_id", "emoji", name="uq_poll_emoji"),
        db.UniqueConstraint("poll_id", "practice_id", name="uq_poll_practice"),
    )


class LeadAvailabilityParticipant(db.Model):
    """Drives nudging: who was asked, who has answered, who opted out."""
    __tablename__ = "lead_availability_participants"

    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("lead_availability_polls.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=ParticipantStatus.PENDING)
    last_nudged_at = db.Column(db.DateTime)
    nudge_count = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("poll_id", "user_id", name="uq_poll_participant"),
    )


class LeadAvailabilityResponse(db.Model):
    """A row means available. Un-reacting deletes it; there is no boolean."""
    __tablename__ = "lead_availability_responses"

    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("lead_availability_polls.id"), nullable=False)
    practice_id = db.Column(db.Integer, db.ForeignKey("practices.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    responded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    source = db.Column(db.String(20), nullable=False, default="reaction")

    # Snapshot of what the practice looked like when answered. Staleness is a
    # mismatch against these, NOT against Practice.updated_at — that column has
    # onupdate and a workout-text edit would mark every response stale.
    answered_for_date = db.Column(db.DateTime)
    answered_for_location_id = db.Column(db.Integer)

    user = db.relationship("User")
    practice = db.relationship("Practice")

    __table_args__ = (
        db.UniqueConstraint("poll_id", "practice_id", "user_id", name="uq_poll_practice_user"),
    )
```

At the bottom of `app/practices/models.py`, so Alembic autogenerate sees them:

```python
# Imported for Alembic metadata registration.
from app.practices.availability_models import (  # noqa: E402,F401
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
)
```

- [ ] **Step 4: Generate and apply the migration**

Run: `flask db heads` — confirm the head is Plan 1's migration.

Run: `flask db migrate -m "add lead availability tables"`

Review the generated file: confirm all four tables, both unique constraints on `lead_availability_poll_practices`, and the composite unique on responses. Then:

Run: `flask db upgrade`

- [ ] **Step 5: Run the tests**

Run: `pytest tests/practices/test_availability_schema.py -v`
Expected: PASS, 5 passed

- [ ] **Step 6: Commit**

```bash
git add app/practices/availability_models.py app/practices/models.py migrations/versions/ tests/practices/test_availability_schema.py
git commit -m "feat(practices): lead availability poll schema

A response row means available — un-reacting deletes it, so no boolean.
Responses snapshot practice date/location because staleness must not derive
from Practice.updated_at, which fires on any edit including workout text."
```

---

### Task 2: Emoji configuration and validation

**Files:**
- Create: `app/practices/availability_emoji.py`
- Modify: `config/practices.yaml`
- Test: `tests/practices/test_availability_emoji.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `letter_emoji(count: int) -> list[str]` — the first `count` configured letter names, raising `EmojiSupplyError` if too few.
  - `validate_emoji_available(names: list[str]) -> tuple[bool, list[str]]` — checks names against `emoji.list`, returning `(ok, missing)`.
  - `DONE_EMOJI = "white_check_mark"`
  - `EmojiSupplyError`

These emoji have already been renamed once, and it silently broke a live poll. A poll that opens against missing emoji is a poll nobody can answer, so opening must fail loudly instead.

- [ ] **Step 1: Write the failing test**

Create `tests/practices/test_availability_emoji.py`:

```python
"""Letter emoji supply and pre-flight validation."""

from unittest.mock import MagicMock, patch

import pytest

from app.practices.availability_emoji import (
    DONE_EMOJI,
    EmojiSupplyError,
    letter_emoji,
    validate_emoji_available,
)


def test_letter_emoji_returns_configured_names_in_order(app):
    with app.app_context():
        assert letter_emoji(3) == ["letter_a", "letter_b", "letter_c"]


def test_letter_emoji_refuses_to_run_short(app):
    with app.app_context():
        with pytest.raises(EmojiSupplyError) as exc:
            letter_emoji(99)
    assert "99" in str(exc.value)


def test_done_emoji_is_never_a_session(app):
    with app.app_context():
        assert DONE_EMOJI not in letter_emoji(26)


def test_validation_reports_missing_emoji(app):
    client = MagicMock()
    client.emoji_list.return_value = {"emoji": {"letter_a": "https://x/a.png"}}

    with patch("app.practices.availability_emoji.get_slack_client", return_value=client):
        with app.app_context():
            ok, missing = validate_emoji_available(["letter_a", "letter_b"])

    assert ok is False
    assert missing == ["letter_b"]


def test_validation_passes_when_all_present(app):
    client = MagicMock()
    client.emoji_list.return_value = {
        "emoji": {"letter_a": "u", "letter_b": "u", "white_check_mark": "u"}
    }

    with patch("app.practices.availability_emoji.get_slack_client", return_value=client):
        with app.app_context():
            ok, missing = validate_emoji_available(["letter_a", "letter_b"])

    assert ok is True
    assert missing == []


def test_native_emoji_are_not_reported_missing(app):
    """emoji.list only returns CUSTOM emoji; native ones must not fail validation."""
    client = MagicMock()
    client.emoji_list.return_value = {"emoji": {"letter_a": "u"}}

    with patch("app.practices.availability_emoji.get_slack_client", return_value=client):
        with app.app_context():
            ok, missing = validate_emoji_available(["letter_a", "white_check_mark"])

    assert ok is True, "white_check_mark is native and is not in emoji.list"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/practices/test_availability_emoji.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.practices.availability_emoji'`

- [ ] **Step 3: Add configuration**

Append to `config/practices.yaml`:

```yaml
lead_availability:
  # Custom workspace emoji, one per session, in order. These were renamed once
  # already (regional_indicator_* -> letter_*) and that silently broke a live
  # poll, so they live here rather than in code.
  letter_emoji:
    - letter_a
    - letter_b
    - letter_c
    - letter_d
    - letter_e
    - letter_f
    - letter_g
    - letter_h
    - letter_i
    - letter_j
    - letter_k
    - letter_l
    - letter_m
    - letter_n
    - letter_o
    - letter_p
    - letter_q
    - letter_r
    - letter_s
    - letter_t
    - letter_u
    - letter_v
    - letter_w
    - letter_x
    - letter_y
    - letter_z
  # Native emoji meaning "that's everything from me", including picking nothing.
  done_emoji: white_check_mark
```

- [ ] **Step 4: Implement**

Create `app/practices/availability_emoji.py`:

```python
"""Letter emoji supply and pre-flight validation for availability polls."""

import yaml
from flask import current_app
from pathlib import Path
from slack_sdk.errors import SlackApiError

from app.slack.client import get_slack_client

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "practices.yaml"

FALLBACK_LETTERS = [f"letter_{c}" for c in "abcdefghijklmnopqrstuvwxyz"]
DONE_EMOJI = "white_check_mark"

# Native emoji are not returned by emoji.list, which only lists custom ones.
NATIVE_EMOJI = {DONE_EMOJI}


class EmojiSupplyError(RuntimeError):
    """Raised when a poll needs more distinct emoji than are configured."""


def _config() -> dict:
    try:
        with open(CONFIG_PATH) as handle:
            return (yaml.safe_load(handle) or {}).get("lead_availability", {}) or {}
    except (OSError, yaml.YAMLError) as exc:
        current_app.logger.warning("Could not read lead_availability config: %s", exc)
        return {}


def letter_emoji(count: int) -> list[str]:
    """The first `count` configured letter emoji, in order."""
    letters = _config().get("letter_emoji") or FALLBACK_LETTERS
    if count > len(letters):
        raise EmojiSupplyError(
            f"poll needs {count} distinct emoji but only {len(letters)} are configured; "
            "add more to config/practices.yaml lead_availability.letter_emoji "
            "or split the block into shorter polls"
        )
    return list(letters[:count])


def validate_emoji_available(names: list[str]) -> tuple[bool, list[str]]:
    """Check every custom emoji exists before a poll opens.

    A poll posted against missing emoji is a poll nobody can answer, and these
    have been renamed once already. Returns (ok, missing).
    """
    custom = [name for name in names if name not in NATIVE_EMOJI]
    if not custom:
        return True, []

    try:
        available = set(get_slack_client().emoji_list().get("emoji", {}).keys())
    except SlackApiError as exc:
        current_app.logger.error(
            "emoji.list failed (%s); refusing to open a poll unverified",
            exc.response.get("error", exc),
        )
        return False, custom
    except Exception as exc:  # noqa: BLE001 - never raise; see Global Constraints
        current_app.logger.error('Slack call failed: %s', exc)
        return {'success': False, 'error': str(exc)}

    missing = [name for name in custom if name not in available]
    return (not missing), missing
```

- [ ] **Step 5: Run the tests**

Run: `pytest tests/practices/test_availability_emoji.py -v`
Expected: PASS, 6 passed

- [ ] **Step 6: Commit**

```bash
git add app/practices/availability_emoji.py config/practices.yaml tests/practices/test_availability_emoji.py
git commit -m "feat(practices): configurable letter emoji with pre-flight validation

These were renamed once already and it silently broke a live poll. The set
lives in config, and opening a poll fails loudly if any emoji is missing
rather than posting something nobody can answer."
```

---

### Task 3: Poll blocks

**Files:**
- Create: `app/slack/blocks/availability.py`
- Modify: `app/slack/blocks/__init__.py`
- Test: `tests/slack/test_availability_blocks.py`

**Interfaces:**
- Consumes: `letter_emoji`, `DONE_EMOJI` (Task 2).
- Produces:
  - `build_poll_blocks(rows: list[dict], start_label: str, end_label: str) -> list[dict]` where each row is `{"emoji": str, "date": datetime, "location": str, "kind": str, "week_label": str}`
  - `build_nudge_blocks(start_label: str, end_label: str, channel_id: str, permalink: str | None) -> list[dict]`
  - `poll_fallback_text(rows, start_label, end_label) -> str`

Screen readers read only the message's top-level `text`, not block contents, so the fallback must describe the whole poll.

- [ ] **Step 1: Write the failing test**

Create `tests/slack/test_availability_blocks.py`:

```python
"""Availability poll and nudge blocks — copy is approved and exact."""

import json
from datetime import datetime

from app.slack.blocks.availability import (
    build_nudge_blocks,
    build_poll_blocks,
    poll_fallback_text,
)


def _rows():
    return [
        {"emoji": "letter_a", "date": datetime(2026, 7, 21, 18, 15),
         "location": "Brackett Park", "kind": "Multi-sport", "week_label": "Week of Jul 21"},
        {"emoji": "letter_b", "date": datetime(2026, 7, 23, 18, 15),
         "location": "Balance", "kind": "Early Lift", "week_label": "Week of Jul 21"},
        {"emoji": "letter_c", "date": datetime(2026, 7, 28, 18, 15),
         "location": "Theo Wirth", "kind": "Trail Run", "week_label": "Week of Jul 28"},
    ]


def test_title_and_instruction_match_approved_copy():
    blocks = build_poll_blocks(_rows(), "July 21", "Aug 13")
    text = json.dumps(blocks)

    assert "Practice Leads July 21 - Aug 13" in text
    assert "React to each session you can lead." in text
    assert "when you're done, even if you picked nothing." in text


def test_no_deadline_footer():
    text = json.dumps(build_poll_blocks(_rows(), "July 21", "Aug 13")).lower()
    assert "closes" not in text
    assert "deadline" not in text


def test_rows_are_grouped_by_week_with_one_emoji_each():
    blocks = build_poll_blocks(_rows(), "July 21", "Aug 13")
    sections = [b for b in blocks if b["type"] == "section"]

    assert len(sections) == 2, "one section per week"
    assert "Week of Jul 21" in sections[0]["text"]["text"]
    assert ":letter_a:" in sections[0]["text"]["text"]
    assert ":letter_c:" in sections[1]["text"]["text"]


def test_each_line_carries_location_type_and_time():
    blocks = build_poll_blocks(_rows(), "July 21", "Aug 13")
    text = json.dumps(blocks)
    assert "Brackett Park" in text and "Multi-sport" in text and "6:15p" in text


def test_fallback_text_describes_the_poll_for_screen_readers():
    fallback = poll_fallback_text(_rows(), "July 21", "Aug 13")
    assert "Practice Leads" in fallback
    assert "3 sessions" in fallback


def test_poll_stays_within_block_limit():
    rows = [
        {"emoji": f"letter_{c}", "date": datetime(2026, 8, 4, 18, 15),
         "location": "Balance", "kind": "Lift", "week_label": f"Week {i}"}
        for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")
    ]
    assert len(build_poll_blocks(rows, "Aug 1", "Sep 1")) <= 50


def test_nudge_uses_approved_copy_and_a_single_url_button():
    blocks = build_nudge_blocks("Jul 21", "Aug 13", "C02J4DGCFL2", "https://slack.com/p/1")
    text = json.dumps(blocks)

    assert "Reminder: Provide lead availability for" in text
    assert "<#C02J4DGCFL2>" in text
    assert "To suppress these" in text

    actions = [b for b in blocks if b["type"] == "actions"]
    assert len(actions) == 1
    buttons = actions[0]["elements"]
    assert len(buttons) == 1, "one button only"
    assert buttons[0]["text"]["text"] == "Go to post"
    assert buttons[0]["url"] == "https://slack.com/p/1"


def test_nudge_without_permalink_omits_the_button_rather_than_breaking():
    blocks = build_nudge_blocks("Jul 21", "Aug 13", "C02J4DGCFL2", None)
    assert not [b for b in blocks if b["type"] == "actions"], \
        "a url button with no url is rejected by Slack"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/slack/test_availability_blocks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.slack.blocks.availability'`

- [ ] **Step 3: Implement**

Create `app/slack/blocks/availability.py`:

```python
"""Block Kit for the lead availability poll and its nudge DM.

Copy here is approved verbatim from the Phase 0 preview. Do not reword it
without re-previewing — it was revised four times against real Slack renders.
"""

from app.practices.availability_emoji import DONE_EMOJI

INSTRUCTION = (
    "React to each session you can lead. · "
    f":{DONE_EMOJI}: when you're done, even if you picked nothing."
)


def _time_label(when) -> str:
    return when.strftime("%-I:%M%p").replace("PM", "p").replace("AM", "a")


def _line(row: dict) -> str:
    """One session. Exactly one letter emoji per line, followed by whitespace."""
    when = row["date"]
    return (
        f":{row['emoji']}:  *{when.strftime('%a %-m/%-d')}* · {_time_label(when)} · "
        f"{row['location']} · _{row['kind']}_"
    )


def build_poll_blocks(rows: list[dict], start_label: str, end_label: str) -> list[dict]:
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text",
         "text": f"Practice Leads {start_label} - {end_label}", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": INSTRUCTION}]},
    ]

    for label in dict.fromkeys(row["week_label"] for row in rows):
        week_rows = [row for row in rows if row["week_label"] == label]
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{label}*\n" + "\n".join(_line(row) for row in week_rows)}})

    return blocks


def poll_fallback_text(rows: list[dict], start_label: str, end_label: str) -> str:
    """Screen readers read only this, never the block contents."""
    return (
        f"Practice Leads {start_label} - {end_label}: {len(rows)} sessions need leads. "
        "React to each session you can lead."
    )


def build_nudge_blocks(start_label: str, end_label: str, channel_id: str,
                       permalink: str | None) -> list[dict]:
    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f"Reminder: Provide lead availability for *{start_label} – {end_label}* "
                 f"in <#{channel_id}>"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": f"To suppress these, if you can't lead at all just hit the "
                 f":{DONE_EMOJI}: on the post there."}]},
    ]
    if permalink:
        blocks.append({"type": "actions", "elements": [{
            "type": "button",
            "text": {"type": "plain_text", "text": "Go to post", "emoji": True},
            "style": "primary",
            "url": permalink,
            "action_id": "availability_go_to_post",
        }]})
    return blocks
```

Re-export from `app/slack/blocks/__init__.py` and add all three names to `__all__`.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/slack/test_availability_blocks.py -v`
Expected: PASS, 8 passed

- [ ] **Step 5: Commit**

```bash
git add app/slack/blocks/availability.py app/slack/blocks/__init__.py tests/slack/test_availability_blocks.py
git commit -m "feat(slack): availability poll and nudge blocks

Copy is verbatim from the Phase 0 preview after four rounds of revision
against real Slack renders. A url button with no url is rejected by Slack,
so the nudge omits the button entirely when there is no permalink."
```

---

### Task 4: Poll creation and opening

**Files:**
- Create: `app/practices/availability.py`
- Test: `tests/practices/test_availability_service.py`

**Interfaces:**
- Consumes: `letter_emoji`, `validate_emoji_available` (Task 2); `build_poll_blocks`, `poll_fallback_text` (Task 3); `is_ready` (Plan 1 Task 4).
- Produces:
  - `eligible_leads() -> list[User]`
  - `build_poll(starts_on: date, ends_on: date, *, is_shadow: bool = False) -> LeadAvailabilityPoll` — creates a DRAFT poll with its emoji mapping; raises `PollNotReadyError` if any practice in range is incomplete.
  - `open_poll(poll) -> dict` — validates emoji, posts, seeds reactions, sets `status=OPEN`. Returns `{"success": bool, ...}`.
  - `PollNotReadyError`

- [ ] **Step 1: Write the failing test**

Create `tests/practices/test_availability_service.py`:

```python
"""Poll construction and opening."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models import Tag, User, db
from app.practices.availability import (
    PollNotReadyError,
    build_poll,
    eligible_leads,
    open_poll,
)
from app.practices.availability_models import PollStatus
from app.practices.models import Practice, PracticeLocation, PracticeType


def _ready_practice(day, hour=18, minute=15):
    location = PracticeLocation(name="Balance")
    ptype = PracticeType(name="Strength")
    db.session.add_all([location, ptype])
    db.session.flush()
    p = Practice(date=datetime(2026, 8, day, hour, minute),
                 day_of_week="Tuesday", is_draft=True, location_id=location.id)
    p.practice_types = [ptype]
    db.session.add(p)
    db.session.flush()
    return p


def _tagged_user(name, tag_name="PRACTICES_LEAD"):
    tag = Tag.query.filter_by(name=tag_name).first() or Tag(name=tag_name,
                                                            display_name=tag_name)
    db.session.add(tag)
    user = User(first_name=name, last_name="Lead", email=f"{name}@x.org")
    user.tags = [tag]
    db.session.add(user)
    db.session.flush()
    return user


def test_eligible_leads_comes_from_tags(db_session):
    lead = _tagged_user("Ada")
    _tagged_user("Coach", "HEAD_COACH")
    untagged = User(first_name="Nobody", last_name="X", email="n@x.org")
    db_session.add(untagged)
    db_session.commit()

    names = {u.first_name for u in eligible_leads()}
    assert "Ada" in names and "Coach" in names
    assert "Nobody" not in names, "untagged members are not asked"


def test_build_poll_assigns_emoji_in_chronological_order(db_session):
    later = _ready_practice(6)
    earlier = _ready_practice(4)
    db_session.commit()

    poll = build_poll(date(2026, 8, 1), date(2026, 8, 31))

    assert [m.practice_id for m in poll.practices] == [earlier.id, later.id]
    assert [m.emoji for m in poll.practices] == ["letter_a", "letter_b"]
    assert [m.position for m in poll.practices] == [0, 1]
    assert poll.status == PollStatus.DRAFT


def test_build_poll_refuses_incomplete_drafts(db_session):
    _ready_practice(4)
    Practice(date=datetime(2026, 8, 6, 18, 15), day_of_week="Thursday", is_draft=True)
    bare = Practice(date=datetime(2026, 8, 6, 18, 15), day_of_week="Thursday", is_draft=True)
    db_session.add(bare)
    db_session.commit()

    with pytest.raises(PollNotReadyError) as exc:
        build_poll(date(2026, 8, 1), date(2026, 8, 31))
    assert "location" in str(exc.value)


def test_open_poll_refuses_when_emoji_are_missing(db_session, app):
    _ready_practice(4)
    db_session.commit()
    poll = build_poll(date(2026, 8, 1), date(2026, 8, 31))

    client = MagicMock()
    with patch("app.practices.availability.validate_emoji_available",
               return_value=(False, ["letter_a"])), \
         patch("app.practices.availability.get_slack_client", return_value=client):
        result = open_poll(poll)

    assert result["success"] is False
    assert "letter_a" in result["error"]
    client.chat_postMessage.assert_not_called(), \
        "never post a poll nobody can answer"
    assert poll.status == PollStatus.DRAFT


def test_open_poll_posts_and_seeds_reactions(db_session, app):
    _ready_practice(4)
    _ready_practice(6)
    db_session.commit()
    poll = build_poll(date(2026, 8, 1), date(2026, 8, 31))

    client = MagicMock()
    client.chat_postMessage.return_value = {"ok": True, "ts": "1785.1"}

    with patch("app.practices.availability.validate_emoji_available", return_value=(True, [])), \
         patch("app.practices.availability.get_slack_client", return_value=client):
        result = open_poll(poll)

    assert result["success"] is True
    assert poll.status == PollStatus.OPEN
    assert poll.message_ts == "1785.1"

    seeded = [c.kwargs["name"] for c in client.reactions_add.call_args_list]
    assert seeded == ["letter_a", "letter_b", "white_check_mark"], \
        "seed each session emoji plus done, so members tap rather than search"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/practices/test_availability_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.practices.availability'`

- [ ] **Step 3: Implement**

Create `app/practices/availability.py`:

```python
"""Lead availability poll construction and lifecycle."""

from datetime import date, datetime

from flask import current_app
from slack_sdk.errors import SlackApiError
from sqlalchemy.orm import joinedload

from app.models import Tag, User, db
from app.practices.availability_emoji import (
    DONE_EMOJI,
    letter_emoji,
    validate_emoji_available,
)
from app.practices.availability_models import (
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    PollStatus,
)
from app.practices.drafting import is_ready, missing_fields
from app.practices.models import Practice
from app.slack.blocks.availability import build_poll_blocks, poll_fallback_text
from app.slack.client import get_slack_client

ELIGIBLE_TAGS = ["PRACTICES_LEAD", "PRACTICES_DIRECTOR", "HEAD_COACH", "ASSISTANT_COACH"]


class PollNotReadyError(RuntimeError):
    """Raised when practices in range still lack location, type or time."""


def eligible_leads() -> list[User]:
    """Everyone who may be asked, computed live from tags.

    Computed rather than stored so a lead who joins mid-block is included
    automatically — the roster going stale is a failure that recurred every
    season with the spreadsheet.
    """
    tag_ids = [t.id for t in Tag.query.filter(Tag.name.in_(ELIGIBLE_TAGS)).all()]
    if not tag_ids:
        return []
    return (
        User.query.options(joinedload(User.tags))
        .filter(User.tags.any(Tag.id.in_(tag_ids)))
        .order_by(User.first_name)
        .all()
    )


def _week_label(when: datetime) -> str:
    monday = when.date().fromordinal(when.date().toordinal() - when.weekday())
    return f"Week of {monday.strftime('%b %-d')}"


def build_poll(starts_on: date, ends_on: date, *, is_shadow: bool = False):
    """Create a DRAFT poll with its emoji mapping, or refuse if drafts are incomplete."""
    practices = (
        Practice.query
        .filter(Practice.date >= datetime.combine(starts_on, datetime.min.time()),
                Practice.date <= datetime.combine(ends_on, datetime.max.time()))
        .order_by(Practice.date)
        .all()
    )
    if not practices:
        raise PollNotReadyError(f"no practices between {starts_on} and {ends_on}")

    incomplete = [(p, missing_fields(p)) for p in practices if not is_ready(p)]
    if incomplete:
        detail = "; ".join(
            f"{p.date:%a %-m/%-d} needs {', '.join(fields)}" for p, fields in incomplete
        )
        raise PollNotReadyError(
            f"{len(incomplete)} practice(s) still need details: {detail}"
        )

    emoji = letter_emoji(len(practices))

    poll = LeadAvailabilityPoll(
        starts_on=starts_on,
        ends_on=ends_on,
        is_shadow=is_shadow,
        channel_id=_target_channel(is_shadow),
    )
    db.session.add(poll)
    db.session.flush()

    for position, (practice, name) in enumerate(zip(practices, emoji)):
        db.session.add(LeadAvailabilityPollPractice(
            poll_id=poll.id, practice_id=practice.id, emoji=name, position=position,
        ))

    db.session.commit()
    return poll


def _target_channel(is_shadow: bool) -> str:
    from app.models import AppConfig
    from app.slack.practices._config import COORD_CHANNEL_ID

    if is_shadow:
        return AppConfig.get("lead_availability.shadow_channel_id", "C0B3Y71PG92")
    return COORD_CHANNEL_ID


def poll_rows(poll) -> list[dict]:
    """Render rows for the block builder."""
    rows = []
    for mapping in poll.practices:
        practice = mapping.practice
        rows.append({
            "emoji": mapping.emoji,
            "date": practice.date,
            "location": practice.location.name if practice.location else "TBD",
            "kind": ", ".join(t.name for t in practice.practice_types) or "Practice",
            "week_label": _week_label(practice.date),
        })
    return rows


def open_poll(poll) -> dict:
    """Validate emoji, post the poll, seed reactions, mark it OPEN."""
    names = [m.emoji for m in poll.practices]
    ok, missing = validate_emoji_available(names + [DONE_EMOJI])
    if not ok:
        message = (
            "cannot open poll: missing workspace emoji "
            f"{', '.join(missing)} — re-add them or update "
            "config/practices.yaml lead_availability.letter_emoji"
        )
        current_app.logger.error(message)
        return {"success": False, "error": message}

    rows = poll_rows(poll)
    start_label = poll.starts_on.strftime("%B %-d")
    end_label = poll.ends_on.strftime("%b %-d")
    client = get_slack_client()

    try:
        response = client.chat_postMessage(
            channel=poll.channel_id,
            blocks=build_poll_blocks(rows, start_label, end_label),
            text=poll_fallback_text(rows, start_label, end_label),
        )
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        current_app.logger.error("Availability poll failed to post: %s", error)
        return {"success": False, "error": error}
    except Exception as exc:  # noqa: BLE001 - never raise; see Global Constraints
        current_app.logger.error('Slack call failed: %s', exc)
        return {'success': False, 'error': str(exc)}

    poll.message_ts = response["ts"]
    poll.status = PollStatus.OPEN
    poll.opened_at = datetime.utcnow()
    db.session.commit()

    # Seed every reaction so members tap an existing pill rather than hunting
    # through the emoji picker for :letter_g:.
    for name in names + [DONE_EMOJI]:
        try:
            client.reactions_add(channel=poll.channel_id,
                                 timestamp=poll.message_ts, name=name)
        except SlackApiError as exc:
            current_app.logger.warning(
                "Could not seed :%s: — %s", name, exc.response.get("error", exc)
            )
    except Exception as exc:  # noqa: BLE001 - never raise; see Global Constraints
        current_app.logger.error('Slack call failed: %s', exc)
        return {'success': False, 'error': str(exc)}

    return {"success": True, "poll_id": poll.id, "ts": poll.message_ts}
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/practices/test_availability_service.py -v`
Expected: PASS, 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/practices/availability.py tests/practices/test_availability_service.py
git commit -m "feat(practices): build and open lead availability polls

Opening validates the emoji set first and refuses to post if any are
missing — a poll against missing emoji is one nobody can answer. Reactions
are seeded so members tap an existing pill instead of hunting the picker."
```

---

### Task 5: Reaction capture and reconciliation

**Files:**
- Create: `app/slack/practices/availability_reactions.py`
- Modify: `app/slack/practices/reactions.py` (branch to availability before attendance handling)
- Test: `tests/slack/test_availability_reactions.py`

**Interfaces:**
- Consumes: poll models (Task 1), `DONE_EMOJI` (Task 2).
- Produces:
  - `handle_availability_reaction(*, channel, message_ts, reaction, slack_user_id, removed) -> dict | None` — returns `None` when the message is not an availability poll, so the caller falls through to attendance handling.
  - `reconcile_poll(poll) -> dict` with keys `added`, `removed`.

**Verify the `reactions:read` scope is granted before starting this task.** Reconciliation cannot work without it.

- [ ] **Step 1: Write the failing test**

Create `tests/slack/test_availability_reactions.py`:

```python
"""Reaction capture and reconciliation."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.models import SlackUser, User, db
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.models import Practice
from app.slack.practices.availability_reactions import (
    handle_availability_reaction,
    reconcile_poll,
)


def _setup(db_session):
    practice = Practice(date=datetime(2026, 8, 4, 18, 15),
                        day_of_week="Tuesday", is_draft=True)
    db_session.add(practice)
    db_session.flush()

    poll = LeadAvailabilityPoll(
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
        channel_id="C1", message_ts="111.1", status=PollStatus.OPEN,
    )
    db_session.add(poll)
    db_session.flush()
    db_session.add(LeadAvailabilityPollPractice(
        poll_id=poll.id, practice_id=practice.id, emoji="letter_a", position=0))

    user = User(first_name="Ada", last_name="Lead", email="ada@x.org")
    db_session.add(user)
    db_session.flush()
    db_session.add(SlackUser(slack_uid="U1", email="ada@x.org", user_id=user.id))
    db_session.commit()
    return poll, practice, user


def test_letter_reaction_records_availability(db_session):
    poll, practice, user = _setup(db_session)

    result = handle_availability_reaction(
        channel="C1", message_ts="111.1", reaction="letter_a",
        slack_user_id="U1", removed=False)

    assert result["success"] is True
    row = LeadAvailabilityResponse.query.one()
    assert row.practice_id == practice.id and row.user_id == user.id
    assert row.answered_for_date == practice.date, "snapshot for staleness detection"


def test_removing_the_reaction_deletes_the_row(db_session):
    poll, practice, user = _setup(db_session)
    handle_availability_reaction(channel="C1", message_ts="111.1",
                                 reaction="letter_a", slack_user_id="U1", removed=False)

    handle_availability_reaction(channel="C1", message_ts="111.1",
                                 reaction="letter_a", slack_user_id="U1", removed=True)

    assert LeadAvailabilityResponse.query.count() == 0


def test_done_emoji_marks_participant_done_without_a_response_row(db_session):
    poll, _, user = _setup(db_session)

    handle_availability_reaction(channel="C1", message_ts="111.1",
                                 reaction="white_check_mark", slack_user_id="U1",
                                 removed=False)

    participant = LeadAvailabilityParticipant.query.filter_by(
        poll_id=poll.id, user_id=user.id).one()
    assert participant.status == ParticipantStatus.DONE
    assert LeadAvailabilityResponse.query.count() == 0, \
        "done is not availability for any session"


def test_unmapped_emoji_is_ignored(db_session):
    _setup(db_session)
    result = handle_availability_reaction(channel="C1", message_ts="111.1",
                                          reaction="tada", slack_user_id="U1",
                                          removed=False)
    assert result["ignored"] == "unmapped_emoji"
    assert LeadAvailabilityResponse.query.count() == 0


def test_non_poll_message_returns_none_so_attendance_still_runs(db_session):
    _setup(db_session)
    assert handle_availability_reaction(
        channel="C1", message_ts="999.9", reaction="letter_a",
        slack_user_id="U1", removed=False) is None


def test_unlinked_slack_user_is_ignored_not_crashed(db_session):
    _setup(db_session)
    result = handle_availability_reaction(channel="C1", message_ts="111.1",
                                          reaction="letter_a", slack_user_id="U-UNKNOWN",
                                          removed=False)
    assert result["ignored"] == "unlinked_user"


def test_reconcile_adds_missed_and_removes_stale(db_session):
    poll, practice, user = _setup(db_session)
    # A response that Slack no longer shows.
    db_session.add(LeadAvailabilityResponse(
        poll_id=poll.id, practice_id=practice.id, user_id=user.id, source="reaction"))
    db_session.commit()

    client = MagicMock()
    client.reactions_get.return_value = {
        "message": {"reactions": [{"name": "white_check_mark", "users": ["U1"]}]}
    }

    with patch("app.slack.practices.availability_reactions.get_slack_client",
               return_value=client):
        result = reconcile_poll(poll)

    assert result["removed"] == 1, "a response Slack no longer shows must be dropped"
    assert LeadAvailabilityResponse.query.count() == 0
    participant = LeadAvailabilityParticipant.query.filter_by(user_id=user.id).one()
    assert participant.status == ParticipantStatus.DONE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/slack/test_availability_reactions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.slack.practices.availability_reactions'`

- [ ] **Step 3: Implement**

Create `app/slack/practices/availability_reactions.py`:

```python
"""Capture availability from poll reactions, and reconcile against Slack."""

from datetime import datetime

from flask import current_app
from slack_sdk.errors import SlackApiError

from app.models import User, db
from app.practices.availability_emoji import DONE_EMOJI
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.slack.client import get_slack_client


def _poll_for_message(channel, message_ts):
    return LeadAvailabilityPoll.query.filter_by(
        channel_id=channel, message_ts=message_ts, status=PollStatus.OPEN
    ).first()


def _user_for_slack_uid(slack_user_id):
    return User.query.join(User.slack_user).filter_by(slack_uid=slack_user_id).first()


def _participant(poll_id, user_id):
    participant = LeadAvailabilityParticipant.query.filter_by(
        poll_id=poll_id, user_id=user_id).first()
    if participant is None:
        # Created lazily so a lead who joins mid-poll is handled automatically.
        participant = LeadAvailabilityParticipant(poll_id=poll_id, user_id=user_id)
        db.session.add(participant)
    return participant


def handle_availability_reaction(*, channel, message_ts, reaction, slack_user_id,
                                 removed=False):
    """Record or withdraw availability.

    Returns None when the message is not an availability poll, so the caller
    falls through to the existing attendance handling.
    """
    poll = _poll_for_message(channel, message_ts)
    if poll is None:
        return None

    user = _user_for_slack_uid(slack_user_id)
    if user is None:
        current_app.logger.info(
            "Availability reaction from unlinked Slack user %s", slack_user_id)
        return {"success": True, "ignored": "unlinked_user"}

    participant = _participant(poll.id, user.id)

    if reaction == DONE_EMOJI:
        participant.status = (
            ParticipantStatus.PENDING if removed else ParticipantStatus.DONE
        )
        db.session.commit()
        return {"success": True, "done": not removed}

    mapping = LeadAvailabilityPollPractice.query.filter_by(
        poll_id=poll.id, emoji=reaction).first()
    if mapping is None:
        return {"success": True, "ignored": "unmapped_emoji"}

    existing = LeadAvailabilityResponse.query.filter_by(
        poll_id=poll.id, practice_id=mapping.practice_id, user_id=user.id).first()

    if removed:
        if existing:
            db.session.delete(existing)
    elif existing is None:
        practice = mapping.practice
        db.session.add(LeadAvailabilityResponse(
            poll_id=poll.id,
            practice_id=mapping.practice_id,
            user_id=user.id,
            source="reaction",
            answered_for_date=practice.date if practice else None,
            answered_for_location_id=practice.location_id if practice else None,
        ))

    if participant.status == ParticipantStatus.PENDING:
        participant.status = ParticipantStatus.RESPONDED

    db.session.commit()
    return {"success": True, "practice_id": mapping.practice_id, "removed": removed}


def reconcile_poll(poll) -> dict:
    """Make stored responses match Slack's actual reactions.

    Events are missed during deploys and outages, and a missed removal leaves
    someone scheduled for a practice they withdrew from.
    """
    try:
        response = get_slack_client().reactions_get(
            channel=poll.channel_id, timestamp=poll.message_ts, full=True)
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        current_app.logger.error("Reconcile failed for poll %s: %s", poll.id, error)
        return {"added": 0, "removed": 0, "error": error}
    except Exception as exc:  # noqa: BLE001 - never raise; see Global Constraints
        current_app.logger.error('Slack call failed: %s', exc)
        return {'success': False, 'error': str(exc)}

    reactions = (response.get("message") or {}).get("reactions") or []
    by_emoji = {r["name"]: set(r.get("users") or []) for r in reactions}

    slack_uid_to_user = {}
    for uid in {uid for users in by_emoji.values() for uid in users}:
        user = _user_for_slack_uid(uid)
        if user:
            slack_uid_to_user[uid] = user

    added = removed = 0

    for mapping in poll.practices:
        should_have = {
            slack_uid_to_user[uid].id
            for uid in by_emoji.get(mapping.emoji, set())
            if uid in slack_uid_to_user
        }
        existing_rows = LeadAvailabilityResponse.query.filter_by(
            poll_id=poll.id, practice_id=mapping.practice_id).all()
        has = {row.user_id: row for row in existing_rows}

        for user_id in should_have - set(has):
            practice = mapping.practice
            db.session.add(LeadAvailabilityResponse(
                poll_id=poll.id, practice_id=mapping.practice_id, user_id=user_id,
                source="reaction",
                answered_for_date=practice.date if practice else None,
                answered_for_location_id=practice.location_id if practice else None,
            ))
            added += 1
        for user_id in set(has) - should_have:
            db.session.delete(has[user_id])
            removed += 1

        for user_id in should_have:
            participant = _participant(poll.id, user_id)
            if participant.status == ParticipantStatus.PENDING:
                participant.status = ParticipantStatus.RESPONDED

    for uid in by_emoji.get(DONE_EMOJI, set()):
        user = slack_uid_to_user.get(uid)
        if user:
            _participant(poll.id, user.id).status = ParticipantStatus.DONE

    db.session.commit()
    current_app.logger.info(
        "Reconciled poll %s: +%d -%d responses", poll.id, added, removed)
    return {"added": added, "removed": removed}
```

- [ ] **Step 4: Branch the existing router**

At the very top of `handle_attendance_reaction` in `app/slack/practices/reactions.py`, immediately after the existing argument guard:

```python
    if not all((channel, message_ts, reaction, slack_user_id)):
        return {"success": True, "ignored": "invalid_event"}

    # Availability polls live in the same channels as announcements, so check
    # them first. Returns None when this message is not a poll.
    from app.slack.practices.availability_reactions import handle_availability_reaction

    availability = handle_availability_reaction(
        channel=channel, message_ts=message_ts, reaction=reaction,
        slack_user_id=slack_user_id, removed=removed,
    )
    if availability is not None:
        return availability
```

- [ ] **Step 5: Run the tests**

Run: `pytest tests/slack/test_availability_reactions.py -v`
Expected: PASS, 7 passed

Run: `pytest tests/slack/ -q`
Expected: PASS — existing RSVP reaction tests must be unaffected, because the availability branch returns `None` for non-poll messages.

- [ ] **Step 6: Commit**

```bash
git add app/slack/practices/availability_reactions.py app/slack/practices/reactions.py tests/slack/test_availability_reactions.py
git commit -m "feat(slack): capture lead availability from poll reactions

Branches ahead of attendance handling and returns None for non-poll
messages so RSVP routing is untouched. Reconciliation exists because a
missed removal event leaves someone scheduled for a practice they withdrew
from."
```

---

### Task 6: Nudge job

**Files:**
- Modify: `app/practices/availability.py`
- Create: `app/slack/practices/availability_nudge.py`
- Modify: `app/scheduler.py`
- Test: `tests/practices/test_availability_nudge.py`

**Interfaces:**
- Consumes: `reconcile_poll` (Task 5), `build_nudge_blocks` (Task 3), `eligible_leads` (Task 4).
- Produces:
  - `sync_participants(poll) -> int` — creates participant rows for eligible leads with none.
  - `participants_to_nudge(poll, *, now: datetime) -> list[LeadAvailabilityParticipant]`
  - `send_nudges(poll) -> dict` with `sent`, `skipped`
  - `run_lead_availability_nudge_job(app)` registered as `lead_availability_nudge`

Cadence per the spec: first nudge at day 3, maximum 3 sends, at least 2 days apart, non-responders only. An off-by-one here DMs everyone every morning, which is the fastest way to get the bot muted.

- [ ] **Step 1: Write the failing test**

Create `tests/practices/test_availability_nudge.py`:

```python
"""Nudge eligibility — the cadence rules are the whole point."""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from app.models import db
from app.practices.availability import participants_to_nudge, send_nudges, sync_participants
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    ParticipantStatus,
    PollStatus,
)

OPENED = datetime(2026, 7, 21, 9, 0)


def _poll(db_session):
    poll = LeadAvailabilityPoll(
        starts_on=date(2026, 7, 21), ends_on=date(2026, 8, 13),
        channel_id="C1", message_ts="1.1", status=PollStatus.OPEN, opened_at=OPENED,
    )
    db_session.add(poll)
    db_session.flush()
    return poll


def _participant(db_session, poll, user_id, **kw):
    p = LeadAvailabilityParticipant(poll_id=poll.id, user_id=user_id, **kw)
    db_session.add(p)
    db_session.flush()
    return p


def test_nobody_is_nudged_before_day_three(db_session):
    poll = _poll(db_session)
    _participant(db_session, poll, 1, status=ParticipantStatus.PENDING)
    db_session.commit()

    assert participants_to_nudge(poll, now=OPENED + timedelta(days=2)) == []


def test_pending_participant_is_nudged_on_day_three(db_session):
    poll = _poll(db_session)
    p = _participant(db_session, poll, 1, status=ParticipantStatus.PENDING)
    db_session.commit()

    due = participants_to_nudge(poll, now=OPENED + timedelta(days=3))
    assert [x.id for x in due] == [p.id]


def test_responded_and_done_and_opted_out_are_never_nudged(db_session):
    poll = _poll(db_session)
    for i, status in enumerate((ParticipantStatus.RESPONDED, ParticipantStatus.DONE,
                                ParticipantStatus.OPTED_OUT), start=1):
        _participant(db_session, poll, i, status=status)
    db_session.commit()

    assert participants_to_nudge(poll, now=OPENED + timedelta(days=10)) == []


def test_nudges_are_spaced_at_least_two_days(db_session):
    poll = _poll(db_session)
    _participant(db_session, poll, 1, status=ParticipantStatus.PENDING,
                 nudge_count=1, last_nudged_at=OPENED + timedelta(days=3))
    db_session.commit()

    assert participants_to_nudge(poll, now=OPENED + timedelta(days=4)) == []
    assert len(participants_to_nudge(poll, now=OPENED + timedelta(days=5))) == 1


def test_three_nudges_is_the_ceiling(db_session):
    poll = _poll(db_session)
    _participant(db_session, poll, 1, status=ParticipantStatus.PENDING,
                 nudge_count=3, last_nudged_at=OPENED + timedelta(days=7))
    db_session.commit()

    assert participants_to_nudge(poll, now=OPENED + timedelta(days=30)) == [], \
        "3 sends is the ceiling; more trains people to mute the bot"


def test_sync_participants_adds_new_leads_only(db_session):
    poll = _poll(db_session)
    _participant(db_session, poll, 1, status=ParticipantStatus.RESPONDED)
    db_session.commit()

    fake_leads = [type("U", (), {"id": 1})(), type("U", (), {"id": 2})()]
    with patch("app.practices.availability.eligible_leads", return_value=fake_leads):
        added = sync_participants(poll)

    assert added == 1
    assert LeadAvailabilityParticipant.query.filter_by(poll_id=poll.id).count() == 2


def test_send_nudges_records_the_send(db_session, app):
    poll = _poll(db_session)
    from app.models import SlackUser, User
    user = User(first_name="Ada", last_name="Lead", email="ada@x.org")
    db_session.add(user)
    db_session.flush()
    db_session.add(SlackUser(slack_uid="U1", email="ada@x.org", user_id=user.id))
    _participant(db_session, poll, user.id, status=ParticipantStatus.PENDING)
    db_session.commit()

    client = MagicMock()
    client.chat_getPermalink.return_value = {"permalink": "https://slack/p/1"}

    with patch("app.slack.practices.availability_nudge.get_slack_client",
               return_value=client):
        result = send_nudges(poll, now=OPENED + timedelta(days=3))

    assert result["sent"] == 1
    participant = LeadAvailabilityParticipant.query.filter_by(user_id=user.id).one()
    assert participant.nudge_count == 1
    assert participant.last_nudged_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/practices/test_availability_nudge.py -v`
Expected: FAIL — `ImportError: cannot import name 'participants_to_nudge'`

- [ ] **Step 3: Implement the DM sender**

Create `app/slack/practices/availability_nudge.py`:

```python
"""Send the availability reminder DM."""

from flask import current_app
from slack_sdk.errors import SlackApiError

from app.slack.blocks.availability import build_nudge_blocks
from app.slack.client import get_slack_client


def poll_permalink(poll) -> str | None:
    try:
        return get_slack_client().chat_getPermalink(
            channel=poll.channel_id, message_ts=poll.message_ts)["permalink"]
    except SlackApiError as exc:
        current_app.logger.warning(
            "No permalink for poll %s: %s", poll.id, exc.response.get("error", exc))
        return None
    except Exception as exc:  # noqa: BLE001 - never raise; see Global Constraints
        current_app.logger.error('Slack call failed: %s', exc)
        return {'success': False, 'error': str(exc)}


def send_nudge_dm(poll, slack_uid: str, permalink: str | None) -> bool:
    start_label = poll.starts_on.strftime("%b %-d")
    end_label = poll.ends_on.strftime("%b %-d")
    blocks = build_nudge_blocks(start_label, end_label, poll.channel_id, permalink)
    fallback = f"Reminder: provide lead availability for {start_label} – {end_label}"

    try:
        get_slack_client().chat_postMessage(
            channel=slack_uid, blocks=blocks, text=fallback)
        return True
    except SlackApiError as exc:
        current_app.logger.warning(
            "Nudge DM to %s failed: %s", slack_uid, exc.response.get("error", exc))
        return False
```

- [ ] **Step 4: Implement the eligibility rules**

Append to `app/practices/availability.py`:

```python
from datetime import timedelta

from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    ParticipantStatus,
)

FIRST_NUDGE_AFTER_DAYS = 3
MIN_DAYS_BETWEEN_NUDGES = 2
MAX_NUDGES = 3


def sync_participants(poll) -> int:
    """Ensure every currently-eligible lead has a participant row."""
    existing = {
        row.user_id for row in
        LeadAvailabilityParticipant.query.filter_by(poll_id=poll.id).all()
    }
    added = 0
    for user in eligible_leads():
        if user.id not in existing:
            db.session.add(LeadAvailabilityParticipant(poll_id=poll.id, user_id=user.id))
            added += 1
    if added:
        db.session.commit()
    return added


def participants_to_nudge(poll, *, now: datetime) -> list:
    """Who is due a reminder right now.

    Only PENDING participants — anyone who reacted, hit done, or opted out is
    left alone. Three sends is the ceiling; beyond that people mute the bot.
    """
    if not poll.opened_at:
        return []
    if now - poll.opened_at < timedelta(days=FIRST_NUDGE_AFTER_DAYS):
        return []

    due = []
    for participant in LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, status=ParticipantStatus.PENDING).all():
        if participant.nudge_count >= MAX_NUDGES:
            continue
        if participant.last_nudged_at and \
                now - participant.last_nudged_at < timedelta(days=MIN_DAYS_BETWEEN_NUDGES):
            continue
        due.append(participant)
    return due


def send_nudges(poll, *, now: datetime | None = None) -> dict:
    """DM everyone currently due a reminder."""
    from app.slack.practices.availability_nudge import poll_permalink, send_nudge_dm

    now = now or datetime.utcnow()
    due = participants_to_nudge(poll, now=now)
    if not due:
        return {"sent": 0, "skipped": 0}

    permalink = poll_permalink(poll)
    sent = skipped = 0
    for participant in due:
        slack_user = getattr(participant.user, "slack_user", None)
        if not slack_user or not slack_user.slack_uid:
            skipped += 1
            continue
        if send_nudge_dm(poll, slack_user.slack_uid, permalink):
            participant.nudge_count += 1
            participant.last_nudged_at = now
            sent += 1
        else:
            skipped += 1

    db.session.commit()
    current_app.logger.info("Poll %s nudges: %d sent, %d skipped", poll.id, sent, skipped)
    return {"sent": sent, "skipped": skipped}
```

- [ ] **Step 5: Register the scheduler job**

In `app/scheduler.py`:

```python
def run_lead_availability_nudge_job(app):
    """Daily: reconcile reactions, then DM only the people who haven't answered."""
    with app.app_context():
        from app.practices.availability import send_nudges, sync_participants
        from app.practices.availability_models import LeadAvailabilityPoll, PollStatus
        from app.slack.practices.availability_reactions import reconcile_poll

        open_polls = LeadAvailabilityPoll.query.filter_by(status=PollStatus.OPEN).all()
        for poll in open_polls:
            # Reconcile first: a missed removal would otherwise let us skip
            # someone who has actually withdrawn, or nudge someone who answered.
            reconcile_poll(poll)
            sync_participants(poll)
            send_nudges(poll)
```

and inside `init_scheduler`:

```python
    # Daily: nudge leads who have not responded to an open availability poll
    scheduler.add_job(
        func=run_lead_availability_nudge_job,
        args=[app],
        trigger=CronTrigger(
            hour=8,
            minute=0,
            timezone='America/Chicago'
        ),
        id='lead_availability_nudge',
        name='Lead Availability Nudge',
        replace_existing=True,
        misfire_grace_time=3600
    )
```

- [ ] **Step 6: Run the tests**

Run: `pytest tests/practices/test_availability_nudge.py -v`
Expected: PASS, 7 passed

Run: `pytest tests/ -q`
Expected: PASS, no regressions.

- [ ] **Step 7: Commit**

```bash
git add app/practices/availability.py app/slack/practices/availability_nudge.py app/scheduler.py tests/practices/test_availability_nudge.py
git commit -m "feat(practices): nudge only leads who haven't answered

Day 3 first, max 3 sends, 2 days apart, PENDING only. Reconciles before
nudging so a missed removal event doesn't cause a wrong send. An off-by-one
here DMs everyone every morning, which is how a bot gets muted."
```

---

### Task 7: Admin trigger and shadow mode

**Files:**
- Create: `app/routes/admin_availability.py`
- Modify: `app/__init__.py` (register the blueprint)
- Modify: `app/templates/admin/practices/list.html` (add the trigger)
- Test: `tests/routes/test_admin_availability.py`

**Interfaces:**
- Consumes: `build_poll`, `open_poll`, `PollNotReadyError` (Task 4).
- Produces:
  - `GET /admin/availability/` — current poll status
  - `POST /admin/availability/polls/create` — body `{"starts_on": "YYYY-MM-DD", "ends_on": "YYYY-MM-DD"}`
  - `POST /admin/availability/polls/<id>/open`

Shadow mode is read from `AppConfig` so leaving it needs no deploy.

- [ ] **Step 1: Write the failing test**

Create `tests/routes/test_admin_availability.py`:

```python
"""Admin poll trigger and shadow-mode routing."""

from unittest.mock import patch

from app.models import AppConfig, db
from app.practices.availability import PollNotReadyError


def test_create_reports_incomplete_drafts_as_a_400(admin_client):
    with patch("app.routes.admin_availability.build_poll",
               side_effect=PollNotReadyError("Tue 8/11 needs location")):
        response = admin_client.post("/admin/availability/polls/create", json={
            "starts_on": "2026-08-01", "ends_on": "2026-08-31",
        })

    assert response.status_code == 400
    assert "needs location" in response.get_json()["error"]


def test_create_uses_shadow_flag_from_config(admin_client, db_session):
    AppConfig.set(key="lead_availability.shadow_mode", value=True,
                  description="t", category="practices")
    db.session.commit()

    with patch("app.routes.admin_availability.build_poll") as build:
        build.return_value = type("P", (), {"id": 7})()
        admin_client.post("/admin/availability/polls/create", json={
            "starts_on": "2026-08-01", "ends_on": "2026-08-31",
        })

    assert build.call_args.kwargs["is_shadow"] is True


def test_open_surfaces_missing_emoji_to_the_director(admin_client):
    with patch("app.routes.admin_availability.LeadAvailabilityPoll") as model, \
         patch("app.routes.admin_availability.open_poll") as opener:
        model.query.get_or_404.return_value = object()
        opener.return_value = {"success": False, "error": "missing workspace emoji letter_c"}
        response = admin_client.post("/admin/availability/polls/1/open")

    assert response.status_code == 400
    assert "letter_c" in response.get_json()["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/routes/test_admin_availability.py -v`
Expected: FAIL — 404, the blueprint does not exist.

- [ ] **Step 3: Implement**

Create `app/routes/admin_availability.py`:

```python
"""Admin endpoints for lead availability polls."""

from datetime import date

from flask import Blueprint, jsonify, request

from app.models import AppConfig
from app.practices.availability import PollNotReadyError, build_poll, open_poll
from app.practices.availability_models import LeadAvailabilityPoll, PollStatus
from app.routes.admin import admin_required

admin_availability_bp = Blueprint(
    "admin_availability", __name__, url_prefix="/admin/availability")


def _shadow_mode() -> bool:
    return bool(AppConfig.get("lead_availability.shadow_mode", False))


@admin_availability_bp.route("/")
@admin_required
def dashboard():
    polls = LeadAvailabilityPoll.query.order_by(
        LeadAvailabilityPoll.created_at.desc()).limit(10).all()
    return jsonify({
        "shadow_mode": _shadow_mode(),
        "polls": [{
            "id": p.id,
            "starts_on": p.starts_on.isoformat(),
            "ends_on": p.ends_on.isoformat(),
            "status": p.status,
            "is_shadow": p.is_shadow,
            "sessions": len(p.practices),
        } for p in polls],
    })


@admin_availability_bp.route("/polls/create", methods=["POST"])
@admin_required
def create_poll():
    data = request.get_json() or {}
    try:
        starts_on = date.fromisoformat(data["starts_on"])
        ends_on = date.fromisoformat(data["ends_on"])
    except (KeyError, ValueError):
        return jsonify({"error": "starts_on and ends_on must be YYYY-MM-DD"}), 400

    try:
        poll = build_poll(starts_on, ends_on, is_shadow=_shadow_mode())
    except PollNotReadyError as exc:
        # Surfaced verbatim: the director needs to know which practice to fix.
        return jsonify({"error": str(exc)}), 400

    return jsonify({"success": True, "poll_id": poll.id})


@admin_availability_bp.route("/polls/<int:poll_id>/open", methods=["POST"])
@admin_required
def open_poll_route(poll_id):
    poll = LeadAvailabilityPoll.query.get_or_404(poll_id)
    result = open_poll(poll)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "could not open poll")}), 400
    return jsonify(result)
```

Register in `app/__init__.py` beside the other admin blueprints:

```python
    from app.routes.admin_availability import admin_availability_bp
    app.register_blueprint(admin_availability_bp)
```

- [ ] **Step 4: Add the trigger to the practices admin page**

In `app/templates/admin/practices/list.html`, add a button that POSTs to `/admin/availability/polls/create` then `/polls/<id>/open`, showing the returned `error` verbatim in a toast on failure. Follow the existing toast pattern in that template.

- [ ] **Step 5: Run the tests**

Run: `pytest tests/routes/test_admin_availability.py -v`
Expected: PASS, 3 passed

Run: `pytest tests/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routes/admin_availability.py app/__init__.py app/templates/admin/practices/list.html tests/routes/test_admin_availability.py
git commit -m "feat(admin): create and open lead availability polls

Shadow mode reads from AppConfig so leaving it needs no deploy. Readiness
and missing-emoji errors surface verbatim — the director needs to know
exactly which practice or emoji to fix."
```

---

## Verification

```bash
pytest tests/ -q
flask db upgrade
```

Shadow-mode smoke test, with `lead_availability.shadow_mode` set to `true`:

```bash
flask shell
>>> from app.practices.availability import build_poll, open_poll
>>> from datetime import date
>>> poll = build_poll(date(2026,8,1), date(2026,8,31), is_shadow=True)
>>> open_poll(poll)          # posts to #collab-asset-mgmt-practices
```

React to a letter in Slack, then confirm capture:

```bash
>>> from app.practices.availability_models import LeadAvailabilityResponse
>>> LeadAvailabilityResponse.query.count()
```

Then delete the reaction and confirm the row disappears. That round trip is the core contract of this plan.

## What this plan deliberately does not do

- No lead picker changes, load counts, or staleness display (Plan 3)
- No coverage thread reply — cut during Phase 0 review
- No `chat.update` of the poll: Slack maintains reaction counts itself, which is what removes the concurrency hazard
