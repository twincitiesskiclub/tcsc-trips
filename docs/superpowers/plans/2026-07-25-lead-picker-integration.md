# Lead Picker Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put availability, load balance and staleness in front of the practices director inside the form where they already assign leads, so scheduling stops requiring a spreadsheet in a second window.

**Architecture:** A single endpoint ranks the eligible pool for one practice — available and least-loaded first, unavailable last but still selectable. Staleness compares a response's snapshot against the practice's current date and location. The picker informs the choice; it never blocks one.

**Tech Stack:** Flask, SQLAlchemy, Tabulator.js / vanilla JS in `app/static/`, pytest with PostgreSQL fixtures.

Plan 3 of 3 from `docs/superpowers/specs/2026-07-25-lead-availability-design.md`. **Requires Plans 1 and 2** — it reads `LeadAvailabilityResponse` rows and `Practice.leads_needed`.

## Global Constraints

- Python 3.12+. Type-annotate new code in the style of the surrounding module.
- `UserStatus` / `UserSeasonStatus` are plain strings — never call `.value`. `PracticeStatus` is a `str, Enum`.
- Use `now_central_naive()` / `today_central()` from `app/utils.py`, never `datetime.now()`.
- **Assignment stays a human judgment call.** Unavailable people must remain selectable — the picker sorts and labels, it never filters anyone out or blocks a choice.
- **Staleness is a mismatch against `LeadAvailabilityResponse.answered_for_date` / `answered_for_location_id`, never against `Practice.updated_at`.** That column has `onupdate` and fires on any edit, so a workout-text tweak would mark every response stale and train directors to ignore the warning.
- Load counts come from `PracticeLead` rows with `role='lead'`. The `assist` role is retired (Plan 1 Task 8) and must not be counted.
- Run the suite with `pytest`.

---

### Task 1: Candidate ranking

**Files:**
- Create: `app/practices/lead_candidates.py`
- Test: `tests/practices/test_lead_candidates.py`

**Interfaces:**
- Consumes: `LeadAvailabilityResponse`, `LeadAvailabilityParticipant`, `LeadAvailabilityPoll`, `ParticipantStatus`, `PollStatus` (Plan 2 Task 1); `eligible_leads` (Plan 2 Task 4).
- Produces: `lead_candidates(practice) -> list[dict]`, each dict having keys `user_id`, `name`, `available` (bool), `responded` (bool), `stale` (bool), `led_in_block` (int), `led_last_90d` (int).

Ordering: available first, then fewest `led_in_block`, then fewest `led_last_90d`, then name. Unavailable and no-response candidates follow, never removed.

- [ ] **Step 1: Write the failing test**

Create `tests/practices/test_lead_candidates.py`:

```python
"""Candidate ranking for the lead picker."""

from datetime import date, datetime, timedelta

from app.models import SlackUser, Tag, User, db
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.lead_candidates import lead_candidates
from app.practices.models import Practice, PracticeLead, PracticeLocation


def _lead_user(name):
    tag = Tag.query.filter_by(name="PRACTICES_LEAD").first()
    if tag is None:
        tag = Tag(name="PRACTICES_LEAD", display_name="Practices Lead")
        db.session.add(tag)
        db.session.flush()
    user = User(first_name=name, last_name="L", email=f"{name.lower()}@x.org")
    user.tags = [tag]
    db.session.add(user)
    db.session.flush()
    return user


def _practice(day, location_id=None):
    p = Practice(date=datetime(2026, 8, day, 18, 15), day_of_week="Tuesday",
                 leads_needed=2, location_id=location_id)
    db.session.add(p)
    db.session.flush()
    return p


def _open_poll(practice):
    poll = LeadAvailabilityPoll(
        starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
        channel_id="C1", message_ts="1.1", status=PollStatus.OPEN,
        opened_at=datetime(2026, 8, 1),
    )
    db.session.add(poll)
    db.session.flush()
    db.session.add(LeadAvailabilityPollPractice(
        poll_id=poll.id, practice_id=practice.id, emoji="letter_a", position=0))
    db.session.flush()
    return poll


def _available(poll, practice, user, *, snapshot=True):
    db.session.add(LeadAvailabilityResponse(
        poll_id=poll.id, practice_id=practice.id, user_id=user.id, source="reaction",
        answered_for_date=practice.date if snapshot else datetime(2020, 1, 1),
        answered_for_location_id=practice.location_id if snapshot else None,
    ))
    db.session.add(LeadAvailabilityParticipant(
        poll_id=poll.id, user_id=user.id, status=ParticipantStatus.RESPONDED))
    db.session.flush()


def test_available_sorts_before_unavailable(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    quiet = _lead_user("Zoe")
    keen = _lead_user("Ada")
    _available(poll, practice, keen)
    db_session.commit()

    rows = lead_candidates(practice)
    assert rows[0]["user_id"] == keen.id
    assert rows[0]["available"] is True
    assert {r["user_id"] for r in rows} == {keen.id, quiet.id}, \
        "unavailable people are ranked down, never removed"


def test_least_loaded_available_lead_comes_first(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    busy = _lead_user("Busy")
    fresh = _lead_user("Fresh")
    _available(poll, practice, busy)
    _available(poll, practice, fresh)

    for day in (11, 13):
        other = _practice(day)
        db_session.add(PracticeLead(practice_id=other.id, user_id=busy.id, role="lead"))
    db_session.commit()

    rows = lead_candidates(practice)
    assert rows[0]["user_id"] == fresh.id
    assert rows[0]["led_in_block"] == 0
    assert rows[1]["led_in_block"] == 2


def test_assist_rows_are_not_counted_as_load(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    user = _lead_user("Ada")
    _available(poll, practice, user)
    other = _practice(11)
    db_session.add(PracticeLead(practice_id=other.id, user_id=user.id, role="assist"))
    db_session.commit()

    rows = lead_candidates(practice)
    assert rows[0]["led_in_block"] == 0, "the assist role is retired and must not count"


def test_response_is_stale_when_location_changed(db_session):
    location = PracticeLocation(name="Wirth")
    db_session.add(location)
    db_session.flush()
    practice = _practice(4, location_id=location.id)
    poll = _open_poll(practice)
    user = _lead_user("Ada")
    _available(poll, practice, user)
    db_session.commit()

    moved = PracticeLocation(name="Hyland")
    db_session.add(moved)
    db_session.flush()
    practice.location_id = moved.id
    db_session.commit()

    rows = lead_candidates(practice)
    assert rows[0]["stale"] is True, \
        "volunteering for Wirth is not volunteering for Hyland"


def test_workout_edit_does_not_make_a_response_stale(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    user = _lead_user("Ada")
    _available(poll, practice, user)
    db_session.commit()

    practice.workout_description = "edited after they answered"
    db_session.commit()

    rows = lead_candidates(practice)
    assert rows[0]["stale"] is False, \
        "only date/time and location decide availability; text edits must not warn"


def test_responded_flag_distinguishes_silence_from_unavailable(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    silent = _lead_user("Silent")
    declined = _lead_user("Declined")
    db_session.add(LeadAvailabilityParticipant(
        poll_id=poll.id, user_id=declined.id, status=ParticipantStatus.DONE))
    db_session.commit()

    rows = {r["user_id"]: r for r in lead_candidates(practice)}
    assert rows[silent.id]["responded"] is False
    assert rows[declined.id]["responded"] is True
    assert rows[declined.id]["available"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/practices/test_lead_candidates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.practices.lead_candidates'`

- [ ] **Step 3: Implement**

Create `app/practices/lead_candidates.py`:

```python
"""Rank the eligible lead pool for one practice.

Assignment is a human judgment call, so nobody is ever filtered out — this
sorts and labels only.
"""

from datetime import timedelta

from app.practices.availability import eligible_leads
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.models import Practice, PracticeLead

LOAD_WINDOW_DAYS = 90


def _poll_for_practice(practice):
    return (
        LeadAvailabilityPoll.query
        .join(LeadAvailabilityPollPractice,
              LeadAvailabilityPollPractice.poll_id == LeadAvailabilityPoll.id)
        .filter(LeadAvailabilityPollPractice.practice_id == practice.id,
                LeadAvailabilityPoll.status.in_([PollStatus.OPEN, PollStatus.CLOSED]))
        .order_by(LeadAvailabilityPoll.created_at.desc())
        .first()
    )


def _is_stale(response, practice) -> bool:
    """Did the details that decide availability change after they answered?

    Deliberately not derived from Practice.updated_at — that fires on any edit,
    so a workout-text tweak would mark everything stale and the warning would
    stop meaning anything.
    """
    if response.answered_for_date and response.answered_for_date != practice.date:
        return True
    if response.answered_for_location_id != practice.location_id:
        return True
    return False


def _load_counts(user_ids, poll, anchor):
    """Leads led within the poll block, and in the 90 days before `anchor`.

    The trailing window is anchored to the practice being scheduled, not to the
    newest row found — anchoring to the data would make the number drift every
    time anyone anywhere led a practice.
    """
    if not user_ids:
        return {}, {}

    in_block = {uid: 0 for uid in user_ids}
    recent = {uid: 0 for uid in user_ids}
    window_start = anchor - timedelta(days=LOAD_WINDOW_DAYS)

    rows = (
        PracticeLead.query
        .join(Practice, Practice.id == PracticeLead.practice_id)
        .filter(PracticeLead.user_id.in_(user_ids), PracticeLead.role == "lead")
        .with_entities(PracticeLead.user_id, Practice.date)
        .all()
    )

    for user_id, when in rows:
        if poll and poll.starts_on <= when.date() <= poll.ends_on:
            in_block[user_id] += 1
        if window_start <= when <= anchor:
            recent[user_id] += 1

    return in_block, recent


def lead_candidates(practice) -> list[dict]:
    """The eligible pool, ranked for this practice."""
    poll = _poll_for_practice(practice)
    users = eligible_leads()
    user_ids = [u.id for u in users]

    responses = {}
    responded = set()
    if poll:
        responses = {
            r.user_id: r for r in LeadAvailabilityResponse.query.filter_by(
                poll_id=poll.id, practice_id=practice.id).all()
        }
        responded = {
            p.user_id for p in LeadAvailabilityParticipant.query.filter_by(
                poll_id=poll.id).all()
            if p.status in (ParticipantStatus.RESPONDED, ParticipantStatus.DONE,
                            ParticipantStatus.OPTED_OUT)
        }

    in_block, recent = _load_counts(user_ids, poll, practice.date)

    rows = []
    for user in users:
        response = responses.get(user.id)
        rows.append({
            "user_id": user.id,
            "name": f"{user.first_name} {user.last_name}".strip(),
            "available": response is not None,
            "responded": user.id in responded or response is not None,
            "stale": bool(response) and _is_stale(response, practice),
            "led_in_block": in_block.get(user.id, 0),
            "led_last_90d": recent.get(user.id, 0),
        })

    rows.sort(key=lambda r: (
        not r["available"],      # available first
        r["led_in_block"],       # then least loaded this block
        r["led_last_90d"],       # then least loaded recently
        r["name"],
    ))
    return rows
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/practices/test_lead_candidates.py -v`
Expected: PASS, 6 passed

- [ ] **Step 5: Commit**

```bash
git add app/practices/lead_candidates.py tests/practices/test_lead_candidates.py
git commit -m "feat(practices): rank lead candidates by availability and load

Nobody is filtered out — assignment stays a judgment call, so this sorts
and labels only. Staleness compares the response's own snapshot rather than
Practice.updated_at, which fires on any edit and would cry wolf."
```

---

### Task 2: Candidates endpoint

**Files:**
- Modify: `app/routes/admin_practices.py`
- Test: `tests/routes/test_lead_candidates_endpoint.py`

**Interfaces:**
- Consumes: `lead_candidates` (Task 1).
- Produces: `GET /admin/practices/<int:practice_id>/lead-candidates` returning `{"leads_needed": int, "assigned": [user_id], "candidates": [...]}`.

- [ ] **Step 1: Write the failing test**

Create `tests/routes/test_lead_candidates_endpoint.py`:

```python
"""Lead candidates endpoint."""

from datetime import datetime
from unittest.mock import patch

from app.models import db
from app.practices.models import Practice, PracticeLead


def _practice():
    p = Practice(date=datetime(2026, 8, 4, 18, 15), day_of_week="Tuesday",
                 leads_needed=3)
    db.session.add(p)
    db.session.commit()
    return p


def test_returns_ranked_candidates_and_capacity(admin_client, db_session):
    practice = _practice()
    fake = [{
        "user_id": 1, "name": "Ada L", "available": True, "responded": True,
        "stale": False, "led_in_block": 0, "led_last_90d": 2,
    }]

    with patch("app.routes.admin_practices.lead_candidates", return_value=fake):
        response = admin_client.get(f"/admin/practices/{practice.id}/lead-candidates")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["leads_needed"] == 3
    assert payload["candidates"] == fake


def test_reports_who_is_already_assigned(admin_client, db_session):
    practice = _practice()
    db_session.add(PracticeLead(practice_id=practice.id, user_id=7, role="lead"))
    db_session.add(PracticeLead(practice_id=practice.id, user_id=8, role="coach"))
    db_session.commit()

    with patch("app.routes.admin_practices.lead_candidates", return_value=[]):
        response = admin_client.get(f"/admin/practices/{practice.id}/lead-candidates")

    assert response.get_json()["assigned"] == [7], "coaches are not leads"


def test_unknown_practice_is_404(admin_client):
    with patch("app.routes.admin_practices.lead_candidates", return_value=[]):
        assert admin_client.get("/admin/practices/999999/lead-candidates").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/routes/test_lead_candidates_endpoint.py -v`
Expected: FAIL — 404 for every case, the route does not exist.

- [ ] **Step 3: Implement**

At the top of `app/routes/admin_practices.py`, with the other imports:

```python
from app.practices.lead_candidates import lead_candidates
```

and add the route beside `practice_leads_data`:

```python
@admin_practices_bp.route('/<int:practice_id>/lead-candidates')
@admin_required
def practice_lead_candidates(practice_id):
    """Eligible leads for this practice, ranked by availability then load."""
    practice = Practice.query.get_or_404(practice_id)
    assigned = [
        lead.user_id for lead in
        PracticeLead.query.filter_by(practice_id=practice.id, role='lead').all()
    ]
    return jsonify({
        'leads_needed': practice.leads_needed,
        'assigned': assigned,
        'candidates': lead_candidates(practice),
    })
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/routes/test_lead_candidates_endpoint.py -v`
Expected: PASS, 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/routes/admin_practices.py tests/routes/test_lead_candidates_endpoint.py
git commit -m "feat(admin): lead-candidates endpoint for the practice form"
```

---

### Task 3: Picker UI

**Files:**
- Modify: `app/static/admin_practices.js`
- Modify: `app/templates/admin/practices/detail.html` (and the create/edit form partial)
- Test: `tests/js/test_lead_picker_source.py`

**Interfaces:**
- Consumes: `GET /admin/practices/<id>/lead-candidates` (Task 2).
- Produces: a lead picker rendering each candidate as `Name · available · led N this block · M in 90d`, with a `⚠` marker on stale rows and a `needs N` capacity hint.

`tests/js/` already tests JS by asserting on source content; follow that existing pattern rather than adding a JS test runner.

- [ ] **Step 1: Write the failing test**

Create `tests/js/test_lead_picker_source.py`:

```python
"""The lead picker must render availability, load and staleness."""

import pathlib

SOURCE = pathlib.Path("app/static/admin_practices.js").read_text()


def test_picker_fetches_the_candidates_endpoint():
    assert "lead-candidates" in SOURCE


def test_picker_renders_load_counts():
    assert "led_in_block" in SOURCE
    assert "led_last_90d" in SOURCE


def test_picker_marks_stale_responses():
    assert "stale" in SOURCE
    assert "⚠" in SOURCE or "warning" in SOURCE.lower()


def test_picker_shows_capacity():
    assert "leads_needed" in SOURCE


def test_picker_does_not_disable_unavailable_candidates():
    """Assignment is a judgment call — unavailable people stay selectable."""
    import re
    for match in re.finditer(r"disabled", SOURCE):
        window = SOURCE[max(0, match.start() - 200):match.start() + 200]
        assert "available" not in window, (
            "unavailable candidates must never be disabled; the picker informs "
            "the choice, it does not block it"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/js/test_lead_picker_source.py -v`
Expected: FAIL — `lead-candidates` is not in the source.

- [ ] **Step 3: Implement**

In `app/static/admin_practices.js`, add a loader and renderer, following the existing fetch/toast conventions in that file:

```javascript
async function loadLeadCandidates(practiceId) {
  const response = await fetch(`/admin/practices/${practiceId}/lead-candidates`);
  if (!response.ok) {
    showToast('Could not load lead availability', 'error');
    return null;
  }
  return response.json();
}

function leadCandidateLabel(candidate) {
  const parts = [];
  if (candidate.available) {
    parts.push('available');
  } else if (candidate.responded) {
    parts.push('unavailable');
  } else {
    parts.push('no response');
  }
  parts.push(`led ${candidate.led_in_block} this block`);
  parts.push(`${candidate.led_last_90d} in 90d`);
  const warning = candidate.stale ? ' ⚠ answered before this practice changed' : '';
  return `${candidate.name} · ${parts.join(' · ')}${warning}`;
}

function renderLeadPicker(container, payload) {
  const assigned = new Set(payload.assigned || []);
  container.innerHTML = '';

  const capacity = document.createElement('div');
  capacity.className = 'lead-capacity';
  capacity.textContent =
    `Leads (needs ${payload.leads_needed}, assigned ${assigned.size})`;
  container.appendChild(capacity);

  // Ordering comes from the server: available and least-loaded first.
  // Every candidate stays selectable — assignment is a human judgment call.
  payload.candidates.forEach((candidate) => {
    const row = document.createElement('label');
    row.className = candidate.available ? 'lead-option available' : 'lead-option';
    if (candidate.stale) row.classList.add('stale');

    const box = document.createElement('input');
    box.type = 'checkbox';
    box.name = 'lead_ids';
    box.value = candidate.user_id;
    box.checked = assigned.has(candidate.user_id);

    const text = document.createElement('span');
    text.textContent = leadCandidateLabel(candidate);

    row.appendChild(box);
    row.appendChild(text);
    container.appendChild(row);
  });
}
```

Wire `loadLeadCandidates` + `renderLeadPicker` into the practice create/edit form where the leads picker is built, replacing the current population from `people_data`. Add a `#lead-picker` container to the form template.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/js/test_lead_picker_source.py -v`
Expected: PASS, 5 passed

- [ ] **Step 5: Verify in the browser**

Run `./scripts/dev.sh`, open a practice in `/admin/practices`, and confirm: available leads appear first with load counts, an unavailable lead is still selectable, and changing the practice's location makes a previously-recorded response show the ⚠ marker.

- [ ] **Step 6: Commit**

```bash
git add app/static/admin_practices.js app/templates/admin/practices/ tests/js/test_lead_picker_source.py
git commit -m "feat(admin): show availability, load and staleness in the lead picker

Server-side ordering puts available and least-loaded first. Unavailable
leads stay selectable — a test asserts they are never disabled, because
assignment is a judgment call the tool informs rather than makes."
```

---

### Task 4: Close the loop — poll closing

**Files:**
- Modify: `app/practices/availability.py`
- Modify: `app/scheduler.py`
- Test: `tests/practices/test_poll_closing.py`

**Interfaces:**
- Consumes: `reconcile_poll` (Plan 2 Task 5).
- Produces: `close_poll(poll) -> dict` and `run_close_expired_polls_job(app)` registered as `lead_availability_close`.

Closing reconciles one last time, so the picker reads final state rather than whatever the last event delivered. Candidates keep reading closed polls, which is what lets directors assign after collection ends.

- [ ] **Step 1: Write the failing test**

Create `tests/practices/test_poll_closing.py`:

```python
"""Poll closing."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

from app.models import db
from app.practices.availability import close_poll
from app.practices.availability_models import LeadAvailabilityPoll, PollStatus


def _poll(db_session, ends_on):
    poll = LeadAvailabilityPoll(
        starts_on=date(2026, 8, 1), ends_on=ends_on, channel_id="C1",
        message_ts="1.1", status=PollStatus.OPEN, opened_at=datetime(2026, 8, 1),
    )
    db_session.add(poll)
    db_session.commit()
    return poll


def test_closing_reconciles_first(db_session):
    poll = _poll(db_session, date(2026, 8, 31))

    with patch("app.practices.availability.reconcile_poll") as reconcile:
        reconcile.return_value = {"added": 0, "removed": 1}
        result = close_poll(poll)

    reconcile.assert_called_once_with(poll)
    assert result["success"] is True
    assert poll.status == PollStatus.CLOSED
    assert poll.closed_at is not None


def test_closing_twice_is_harmless(db_session):
    poll = _poll(db_session, date(2026, 8, 31))
    with patch("app.practices.availability.reconcile_poll", return_value={}):
        close_poll(poll)
        result = close_poll(poll)

    assert result["success"] is True
    assert result.get("already_closed") is True


def test_expired_polls_close_automatically(db_session, app):
    from app.scheduler import run_close_expired_polls_job

    past = _poll(db_session, date(2026, 8, 1))
    future = _poll(db_session, date(2099, 1, 1))

    with patch("app.practices.availability.reconcile_poll", return_value={}), \
         patch("app.scheduler.today_central", return_value=date(2026, 8, 15)):
        run_close_expired_polls_job(app)

    assert past.status == PollStatus.CLOSED
    assert future.status == PollStatus.OPEN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/practices/test_poll_closing.py -v`
Expected: FAIL — `ImportError: cannot import name 'close_poll'`

- [ ] **Step 3: Implement**

Append to `app/practices/availability.py`:

```python
def close_poll(poll) -> dict:
    """Reconcile one final time, then close.

    The last reconcile matters: the picker must read Slack's actual final
    state, not whatever the last delivered event happened to say.
    """
    from app.slack.practices.availability_reactions import reconcile_poll

    if poll.status == PollStatus.CLOSED:
        return {"success": True, "already_closed": True}

    reconcile_poll(poll)
    poll.status = PollStatus.CLOSED
    poll.closed_at = datetime.utcnow()
    db.session.commit()
    current_app.logger.info("Closed availability poll %s", poll.id)
    return {"success": True, "poll_id": poll.id}
```

In `app/scheduler.py`, add the import `from app.utils import today_central` at module level if it is not already there, then:

```python
def run_close_expired_polls_job(app):
    """Daily: close polls whose block has ended."""
    with app.app_context():
        from app.practices.availability import close_poll
        from app.practices.availability_models import LeadAvailabilityPoll, PollStatus

        today = today_central()
        expired = LeadAvailabilityPoll.query.filter(
            LeadAvailabilityPoll.status == PollStatus.OPEN,
            LeadAvailabilityPoll.ends_on < today,
        ).all()
        for poll in expired:
            close_poll(poll)
```

and register it in `init_scheduler`:

```python
    # Daily: close availability polls whose block has ended
    scheduler.add_job(
        func=run_close_expired_polls_job,
        args=[app],
        trigger=CronTrigger(
            hour=8,
            minute=30,
            timezone='America/Chicago'
        ),
        id='lead_availability_close',
        name='Close Expired Availability Polls',
        replace_existing=True,
        misfire_grace_time=3600
    )
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/practices/test_poll_closing.py -v`
Expected: PASS, 3 passed

Run: `pytest tests/ -q`
Expected: PASS, no regressions.

- [ ] **Step 5: Commit**

```bash
git add app/practices/availability.py app/scheduler.py tests/practices/test_poll_closing.py
git commit -m "feat(practices): close availability polls after their block ends

Closing reconciles once more so the picker reads Slack's final state rather
than the last event delivered. Closed polls stay readable by the picker so
directors can still assign after collection ends."
```

---

## Verification

```bash
pytest tests/ -q
```

Then the full loop against the local database:

```bash
./scripts/dev.sh
```

1. Open `/admin/practices`, create a poll and open it in shadow mode
2. React to a letter in Slack
3. Open the practice in the admin form — that person is now top of the picker, marked available
4. Change the practice's location, reload — the ⚠ stale marker appears
5. Assign two leads and save — `PracticeLead` rows are written and `refresh_practice_posts()` fires as before

Step 4 is the one worth doing deliberately: it is the failure this whole mechanism exists to prevent, and the one the spreadsheet produced repeatedly.

## What this plan deliberately does not do

- No automated substitutions — the highest-volume traffic in the channel, and the part that already works socially
- No lead capability profiles
- No automatic assignment; the picker informs a human choice and never makes one
- No coverage thread reply — cut during Phase 0 review
