# Daily Season Registration Recap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A scheduled job that posts a daily season-registration recap to the `leadership-registration` Slack channel while registration is running.

**Architecture:** Three layers, matching the codebase's existing split: a pure stats builder in `app/seasons/recap.py` (queries only), a Slack renderer/poster in `app/slack/season_recap.py` (never raises, trips.py contract), and a thin APScheduler job in `app/scheduler.py` that gates on `should_post()` and wires them together.

**Tech Stack:** Flask + SQLAlchemy (PostgreSQL), APScheduler, slack_sdk, pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-season-registration-recap-design.md`

## Global Constraints

- Timestamps in the DB are UTC; `Season.returning_start/end` and `new_start/end` are naive UTC DateTimes. Convert with `app.utils.utc_naive_to_central_naive()` before date math. `UserSeason.registration_date` is already a Central Date.
- `UserSeasonStatus` values are plain strings, NOT Enums — never call `.value`.
- `UserSeason.registration_type` stores lowercase `'new'` / `'returning'`.
- Counted registrations = status in (`PENDING_LOTTERY`, `ACTIVE`). Dropped rows never count.
- The Slack layer never raises; it returns `{"success": bool, ...}` dicts (see `app/slack/trips.py`).
- Tests run against the local Postgres dev DB (`postgresql://tcsc:tcsc@localhost:5432/tcsc_trips`) with per-fixture cleanup, house style per `tests/registration/test_season_register_verified.py`. Use year 2097/2098 seasons and `@recap-test.com` emails so fixtures can't collide with real dev data.
- No em dashes in any user-facing copy (Slack message text).
- Work happens on the `season-recap` branch; deploys go through PRs, never push to main.

## File Structure

- `app/seasons/recap.py` (new) — `build_recap(season, for_date)`, `should_post(season, today)`, private query helpers. No Slack or scheduler imports.
- `app/slack/season_recap.py` (new) — `CHANNEL_NAME`, `build_recap_blocks(stats)`, `post_season_recap(stats, channel_override=None)`.
- `app/scheduler.py` (modify) — `run_season_recap_job()`, job registration, manual-trigger map entry.
- `tests/seasons/test_recap.py` (new), `tests/slack/test_season_recap.py` (new), `tests/test_scheduler_season_recap.py` (new).

---

### Task 1: Stats builder core — yesterday split, season totals, trend

**Files:**
- Create: `app/seasons/recap.py`
- Test: `tests/seasons/test_recap.py`

**Interfaces:**
- Consumes: `app.models.Season`, `app.models.User`, `app.models.UserSeason`, `app.constants.UserSeasonStatus`.
- Produces: `build_recap(season, for_date: date) -> dict` with keys `season_id`, `season_name`, `for_date`, `yesterday` (`{"new": int, "returning": int, "total": int}`), `previous_day_total` (int), `season_totals` (`{"new", "returning", "total", "registration_limit", "pct_of_limit"}`). Later tasks add more keys to this same dict; the fixture helpers `_make_season` / `_make_reg` defined here are reused by every later test in this file.

- [ ] **Step 1: Write the failing tests**

Create `tests/seasons/test_recap.py`:

```python
"""Stats builder for the daily season registration recap.

House fixture style: real Postgres dev DB, far-future season years and
@recap-test.com emails so nothing collides with real data, cleanup in
fixture teardown.
"""
from datetime import date, datetime, timedelta

import pytest

from app import create_app
from app.constants import UserSeasonStatus
from app.models import db, Season, User, UserSeason


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


# The recap covers the prior Central day; tests pin it to a fixed date so
# nothing depends on the clock. Windows are stored as naive UTC datetimes;
# noon UTC converts to the same Central calendar date, which keeps the
# expected day math readable.
FOR_DATE = date(2098, 1, 10)


def _utc_noon(d):
    return datetime(d.year, d.month, d.day, 12, 0, 0)


def _make_season(name, year, *, window_start, window_end, season_type="winter",
                 registration_limit=None, new_window=None):
    """new_window: optional (start_date, end_date) for the new-member window;
    window_start/end are the returning window."""
    s = Season(
        name=name, year=year, season_type=season_type,
        price_cents=15000, registration_limit=registration_limit,
        start_date=date(year, 11, 1), end_date=date(year + 1, 3, 1),
        returning_start=_utc_noon(window_start),
        returning_end=_utc_noon(window_end),
        new_start=_utc_noon(new_window[0]) if new_window else None,
        new_end=_utc_noon(new_window[1]) if new_window else None,
    )
    db.session.add(s)
    db.session.commit()
    return s


_user_seq = 0


def _make_reg(season, reg_date, *, reg_type="new",
              status=UserSeasonStatus.PENDING_LOTTERY, phone=None,
              interests=None, committees=None, needs_review=False):
    global _user_seq
    _user_seq += 1
    u = User(
        first_name="Recap", last_name=f"Tester{_user_seq}",
        email=f"recap-{_user_seq}@recap-test.com",
        phone_e164=phone,
    )
    db.session.add(u)
    db.session.flush()
    us = UserSeason(
        user_id=u.id, season_id=season.id, registration_type=reg_type,
        registration_date=reg_date, status=status, needs_review=needs_review,
        volunteer_interests=interests, volunteer_committees=committees,
    )
    db.session.add(us)
    db.session.commit()
    return us


@pytest.fixture
def clean(app):
    """Delete every row the tests created, newest tables first."""
    with app.app_context():
        yield
        seasons = Season.query.filter(Season.year >= 2097).all()
        for s in seasons:
            UserSeason.query.filter_by(season_id=s.id).delete()
        User.query.filter(User.email.like("%@recap-test.com")).delete(
            synchronize_session=False)
        for s in seasons:
            db.session.delete(s)
        db.session.commit()


@pytest.fixture
def season(app, clean):
    with app.app_context():
        yield _make_season(
            "Recap Winter 2098", 2098,
            window_start=FOR_DATE - timedelta(days=4),
            window_end=FOR_DATE + timedelta(days=16),
            registration_limit=200,
        )


def test_yesterday_split_and_season_totals(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE, reg_type="new")
        _make_reg(season, FOR_DATE, reg_type="new")
        _make_reg(season, FOR_DATE, reg_type="returning",
                  status=UserSeasonStatus.ACTIVE)
        _make_reg(season, FOR_DATE - timedelta(days=1), reg_type="new")
        stats = build_recap(season, FOR_DATE)
    assert stats["yesterday"] == {"new": 2, "returning": 1, "total": 3}
    assert stats["previous_day_total"] == 1
    assert stats["season_totals"]["total"] == 4
    assert stats["season_totals"]["new"] == 3
    assert stats["season_totals"]["returning"] == 1
    assert stats["season_totals"]["registration_limit"] == 200
    assert stats["season_totals"]["pct_of_limit"] == 2  # 4/200
    assert stats["season_id"] == season.id
    assert stats["for_date"] == FOR_DATE


def test_dropped_registrations_do_not_count(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE)
        _make_reg(season, FOR_DATE, status=UserSeasonStatus.DROPPED_VOLUNTARY)
        _make_reg(season, FOR_DATE, status=UserSeasonStatus.DROPPED_LOTTERY)
        stats = build_recap(season, FOR_DATE)
    assert stats["yesterday"]["total"] == 1
    assert stats["season_totals"]["total"] == 1


def test_no_limit_means_no_percentage(app, clean):
    from app.seasons.recap import build_recap
    with app.app_context():
        s = _make_season("Recap NoLimit 2098", 2098,
                         window_start=FOR_DATE - timedelta(days=4),
                         window_end=FOR_DATE + timedelta(days=16))
        stats = build_recap(s, FOR_DATE)
    assert stats["season_totals"]["registration_limit"] is None
    assert stats["season_totals"]["pct_of_limit"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source env/bin/activate && python -m pytest tests/seasons/test_recap.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'app.seasons.recap'`

- [ ] **Step 3: Write minimal implementation**

Create `app/seasons/recap.py`:

```python
"""Stats for the daily season registration recap.

Pure data layer: queries only. Slack rendering lives in
app/slack/season_recap.py, scheduling in app/scheduler.py.
"""
from datetime import timedelta

from app.constants import UserSeasonStatus
from app.models import UserSeason

# PENDING_LOTTERY and ACTIVE count as registrations; any dropped status
# does not. (Status values are plain strings, not Enums.)
COUNTED_STATUSES = (UserSeasonStatus.PENDING_LOTTERY, UserSeasonStatus.ACTIVE)


def _counted_rows(season_id):
    return UserSeason.query.filter(
        UserSeason.season_id == season_id,
        UserSeason.status.in_(COUNTED_STATUSES),
    ).all()


def _split_counts(rows):
    new = sum(1 for r in rows if r.registration_type == 'new')
    returning = sum(1 for r in rows if r.registration_type == 'returning')
    return {"new": new, "returning": returning, "total": len(rows)}


def build_recap(season, for_date):
    """Stats dict for the recap covering the Central date `for_date`."""
    season_rows = _counted_rows(season.id)
    day_rows = [r for r in season_rows if r.registration_date == for_date]
    prev_rows = [r for r in season_rows
                 if r.registration_date == for_date - timedelta(days=1)]

    totals = _split_counts(season_rows)
    limit = season.registration_limit
    totals["registration_limit"] = limit
    totals["pct_of_limit"] = (
        round(100 * totals["total"] / limit) if limit else None)

    return {
        "season_id": season.id,
        "season_name": season.name,
        "for_date": for_date,
        "yesterday": _split_counts(day_rows),
        "previous_day_total": len(prev_rows),
        "season_totals": totals,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/seasons/test_recap.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add app/seasons/recap.py tests/seasons/test_recap.py
git commit -m "feat(recap): stats builder core - daily split, totals, trend"
```

---

### Task 2: Windows and the cadence gate

**Files:**
- Modify: `app/seasons/recap.py`
- Test: `tests/seasons/test_recap.py`

**Interfaces:**
- Consumes: `_make_season`, `FOR_DATE`, fixtures from Task 1; `app.utils.utc_naive_to_central_naive`.
- Produces: `build_recap` result gains `"windows"`: `{"returning": <window|None>, "new": <window|None>}` where a window is `{"start": date, "end": date, "is_open": bool, "day_number": int|None, "days_remaining": int|None, "length_days": int}`. New public function `should_post(season, today: date) -> bool`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/seasons/test_recap.py`:

```python
def test_window_day_math(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        stats = build_recap(season, FOR_DATE)
    w = stats["windows"]["returning"]
    # Window opened 4 days before FOR_DATE: day 5 of 21, 16 days left.
    assert w["is_open"] is True
    assert w["day_number"] == 5
    assert w["days_remaining"] == 16
    assert w["length_days"] == 21
    assert stats["windows"]["new"] is None


def test_should_post_gate(app, clean):
    from app.seasons.recap import should_post
    with app.app_context():
        s = _make_season(
            "Recap Gate 2098", 2098,
            window_start=date(2098, 1, 6), window_end=date(2098, 1, 20),
            new_window=(date(2098, 1, 13), date(2098, 1, 27)),
        )
        assert should_post(s, date(2098, 1, 5)) is False   # before any window
        assert should_post(s, date(2098, 1, 6)) is True    # first day
        assert should_post(s, date(2098, 1, 22)) is True   # new window open
        assert should_post(s, date(2098, 2, 3)) is True    # 7 days after last end
        assert should_post(s, date(2098, 2, 4)) is False   # 8 days after


def test_should_post_false_without_windows(app, clean):
    from app.seasons.recap import should_post
    with app.app_context():
        s = Season(name="Recap Bare 2097", year=2097, season_type="winter",
                   price_cents=15000,
                   start_date=date(2097, 11, 1), end_date=date(2098, 3, 1))
        db.session.add(s)
        db.session.commit()
        assert should_post(s, date(2097, 12, 1)) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/seasons/test_recap.py -v -k "window or should_post"`
Expected: FAIL with `KeyError: 'windows'` and `ImportError`/`AttributeError` for `should_post`

- [ ] **Step 3: Write minimal implementation**

In `app/seasons/recap.py`, add to imports:

```python
from app.utils import utc_naive_to_central_naive
```

Add above `build_recap`:

```python
def _window(start_utc, end_utc, for_date):
    """Central-date view of a UTC window; None when it isn't fully set,
    matching Season.is_open_for's both-ends-required rule."""
    if not (start_utc and end_utc):
        return None
    start = utc_naive_to_central_naive(start_utc).date()
    end = utc_naive_to_central_naive(end_utc).date()
    is_open = start <= for_date <= end
    return {
        "start": start,
        "end": end,
        "is_open": is_open,
        "day_number": (for_date - start).days + 1 if is_open else None,
        "days_remaining": (end - for_date).days if is_open else None,
        "length_days": (end - start).days + 1,
    }


def should_post(season, today):
    """The cadence gate: post while a window is open, and for 7 days after
    the last one closes so leadership sees the final tally settle."""
    windows = [w for w in (
        _window(season.returning_start, season.returning_end, today),
        _window(season.new_start, season.new_end, today),
    ) if w]
    if not windows:
        return False
    if any(w["is_open"] for w in windows):
        return True
    last_end = max(w["end"] for w in windows)
    return 0 <= (today - last_end).days <= 7
```

In `build_recap`'s return dict, add:

```python
        "windows": {
            "returning": _window(
                season.returning_start, season.returning_end, for_date),
            "new": _window(season.new_start, season.new_end, for_date),
        },
```

- [ ] **Step 4: Run the whole test file**

Run: `python -m pytest tests/seasons/test_recap.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add app/seasons/recap.py tests/seasons/test_recap.py
git commit -m "feat(recap): window day math and should_post cadence gate"
```

---

### Task 3: Prior-season comparison

**Files:**
- Modify: `app/seasons/recap.py`
- Test: `tests/seasons/test_recap.py`

**Interfaces:**
- Consumes: Task 1/2 helpers and fixtures.
- Produces: `build_recap` result gains `"prior_season"`: `{"name": str, "count_at_same_point": int, "final_count": int}` or `None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/seasons/test_recap.py`:

```python
def test_prior_season_comparison_at_same_day_offset(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        prior = _make_season(
            "Recap Winter 2097", 2097,
            window_start=date(2097, 1, 6), window_end=date(2097, 1, 26))
        # Prior season: 2 regs inside the first 5 window days, 1 later.
        _make_reg(prior, date(2097, 1, 6))
        _make_reg(prior, date(2097, 1, 10))
        _make_reg(prior, date(2097, 1, 20))
        _make_reg(season, FOR_DATE)
        stats = build_recap(season, FOR_DATE)
    # FOR_DATE is day 5 of the current window (offset 4 from its anchor):
    # cutoff in the prior season is Jan 10, so 2 of its 3 count.
    assert stats["prior_season"] == {
        "name": "Recap Winter 2097",
        "count_at_same_point": 2,
        "final_count": 3,
    }


def test_prior_season_requires_same_type(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        other = _make_season(
            "Recap Summer 2097", 2097, season_type="summer",
            window_start=date(2097, 1, 6), window_end=date(2097, 1, 26))
        _make_reg(other, date(2097, 1, 6))
        stats = build_recap(season, FOR_DATE)
    assert stats["prior_season"] is None


def test_prior_season_skips_empty_seasons(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_season("Recap Empty 2097", 2097,
                     window_start=date(2097, 6, 1), window_end=date(2097, 6, 20))
        older = _make_season(
            "Recap Older 2097", 2097,
            window_start=date(2097, 1, 6), window_end=date(2097, 1, 26))
        _make_reg(older, date(2097, 1, 6))
        stats = build_recap(season, FOR_DATE)
    # The empty nearer season is skipped; the older one with data is used.
    assert stats["prior_season"]["name"] == "Recap Older 2097"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/seasons/test_recap.py -v -k prior`
Expected: FAIL with `KeyError: 'prior_season'`

- [ ] **Step 3: Write minimal implementation**

In `app/seasons/recap.py`, add `Season` to the models import:

```python
from app.models import Season, UserSeason
```

Add above `build_recap`:

```python
def _anchor_date(season):
    """The season's registration-open anchor: earliest window start, as a
    Central date. None when no window start is set."""
    starts = [s for s in (season.returning_start, season.new_start) if s]
    if not starts:
        return None
    return utc_naive_to_central_naive(min(starts)).date()


def _prior_season(season, for_date):
    """Most recent earlier season of the same type that has registrations,
    compared at the same day-offset from its own anchor."""
    anchor = _anchor_date(season)
    if anchor is None:
        return None
    candidates = Season.query.filter(
        Season.season_type == season.season_type,
        Season.id != season.id,
    ).all()
    dated = []
    for candidate in candidates:
        candidate_anchor = _anchor_date(candidate)
        if candidate_anchor and candidate_anchor < anchor:
            dated.append((candidate_anchor, candidate))
    dated.sort(key=lambda pair: pair[0], reverse=True)

    offset = (for_date - anchor).days
    for prior_anchor, prior in dated:
        rows = _counted_rows(prior.id)
        if not rows:
            continue
        cutoff = prior_anchor + timedelta(days=offset)
        return {
            "name": prior.name,
            "count_at_same_point": sum(
                1 for r in rows if r.registration_date <= cutoff),
            "final_count": len(rows),
        }
    return None
```

In `build_recap`'s return dict, add:

```python
        "prior_season": _prior_season(season, for_date),
```

- [ ] **Step 4: Run the whole test file**

Run: `python -m pytest tests/seasons/test_recap.py -v`
Expected: 9 PASS

- [ ] **Step 5: Commit**

```bash
git add app/seasons/recap.py tests/seasons/test_recap.py
git commit -m "feat(recap): prior-season comparison at same window offset"
```

---

### Task 4: Volunteer interest, needs_review, highlights

**Files:**
- Modify: `app/seasons/recap.py`
- Test: `tests/seasons/test_recap.py`

**Interfaces:**
- Consumes: Task 1-3 helpers; `app.constants.VOLUNTEER_INTERESTS`, `VOLUNTEER_COMMITTEES`; `UserSeason.user` backref (`User.phone_e164`).
- Produces: `build_recap` result gains `"volunteer"` (`{"answered": int, "of": int, "interests": {label: count}, "committees": {label: count}}`), `"needs_review"` (int), `"highlights"` (list of str).

- [ ] **Step 1: Write the failing tests**

Append to `tests/seasons/test_recap.py`:

```python
def test_volunteer_summary_counts_yesterday_only(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE,
                  interests=["practice_lead", "committee"],
                  committees=["social"])
        _make_reg(season, FOR_DATE, interests=["practice_lead"])
        _make_reg(season, FOR_DATE, interests=[])          # declined
        _make_reg(season, FOR_DATE - timedelta(days=1),
                  interests=["event_volunteer"])           # not yesterday
        stats = build_recap(season, FOR_DATE)
    v = stats["volunteer"]
    assert v["answered"] == 2
    assert v["of"] == 3
    assert v["interests"] == {
        "Lead a group at practice": 2, "Join a committee": 1}
    assert v["committees"] == {"Social (community events)": 1}


def test_needs_review_counts_whole_season(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE - timedelta(days=3), needs_review=True)
        _make_reg(season, FOR_DATE, needs_review=True)
        _make_reg(season, FOR_DATE)
        stats = build_recap(season, FOR_DATE)
    assert stats["needs_review"] == 2


def test_highlight_record_day(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE - timedelta(days=2))
        _make_reg(season, FOR_DATE)
        _make_reg(season, FOR_DATE)
        stats = build_recap(season, FOR_DATE)
    assert any("Biggest day" in line for line in stats["highlights"])


def test_no_record_highlight_for_single_registration(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE)
        stats = build_recap(season, FOR_DATE)
    assert not any("Biggest day" in line for line in stats["highlights"])


def test_highlight_milestone_crossed(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        for _ in range(48):
            _make_reg(season, FOR_DATE - timedelta(days=2))
        for _ in range(3):
            _make_reg(season, FOR_DATE)
        stats = build_recap(season, FOR_DATE)
    assert any("50" in line and "Crossed" in line
               for line in stats["highlights"])


def test_highlight_household(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        _make_reg(season, FOR_DATE, phone="+16125550190")
        _make_reg(season, FOR_DATE, phone="+16125550190")
        _make_reg(season, FOR_DATE, phone="+16125550191")
        stats = build_recap(season, FOR_DATE)
    assert any("household" in line for line in stats["highlights"])


def test_no_highlights_on_quiet_day(app, season):
    from app.seasons.recap import build_recap
    with app.app_context():
        stats = build_recap(season, FOR_DATE)
    assert stats["highlights"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/seasons/test_recap.py -v -k "volunteer or needs_review or highlight"`
Expected: FAIL with `KeyError` on the new keys

- [ ] **Step 3: Write minimal implementation**

In `app/seasons/recap.py`, extend the constants import:

```python
from app.constants import (
    UserSeasonStatus, VOLUNTEER_COMMITTEES, VOLUNTEER_INTERESTS,
)
```

Add above `build_recap`:

```python
def _volunteer_summary(day_rows):
    """Get Involved answers among the day's registrations. Null interests
    means the question was never asked (pre-question registrant); an empty
    list means they answered and declined -- both count as unanswered here,
    only actual opt-ins are tallied."""
    answered = [r for r in day_rows if r.volunteer_interests]
    interests = {}
    committees = {}
    for row in answered:
        for key in row.volunteer_interests:
            label = VOLUNTEER_INTERESTS.get(key, key)
            interests[label] = interests.get(label, 0) + 1
        if 'committee' in row.volunteer_interests:
            for key in (row.volunteer_committees or []):
                label = VOLUNTEER_COMMITTEES.get(key, key)
                committees[label] = committees.get(label, 0) + 1
    return {
        "answered": len(answered),
        "of": len(day_rows),
        "interests": interests,
        "committees": committees,
    }


def _highlights(for_date, day_rows, season_rows):
    """Fun lines, each included only when true."""
    lines = []
    day_total = len(day_rows)

    # Biggest day of the season so far (ties don't count, nor does 1).
    daily = {}
    for row in season_rows:
        if row.registration_date < for_date:
            daily[row.registration_date] = daily.get(row.registration_date, 0) + 1
    if day_total > 1 and day_total > max(daily.values(), default=0):
        lines.append(
            f"Biggest day of the season so far: {day_total} registrations.")

    # Crossed a multiple of 50 (measured through for_date, so an early
    # same-morning registration can't claim yesterday's milestone).
    through = sum(1 for r in season_rows if r.registration_date <= for_date)
    before = through - day_total
    if through >= 50 and through // 50 > before // 50:
        lines.append(f"Crossed {(through // 50) * 50} total registrations.")

    # Households: two registrations sharing a verified phone number.
    phones = {}
    for row in day_rows:
        phone = row.user.phone_e164 if row.user else None
        if phone:
            phones[phone] = phones.get(phone, 0) + 1
    shared = sum(1 for count in phones.values() if count >= 2)
    if shared == 1:
        lines.append("A household registered together (shared phone number).")
    elif shared > 1:
        lines.append(
            f"{shared} households registered together (shared phone numbers).")

    return lines
```

In `build_recap`'s return dict, add:

```python
        "volunteer": _volunteer_summary(day_rows),
        "needs_review": UserSeason.query.filter_by(
            season_id=season.id, needs_review=True).count(),
        "highlights": _highlights(for_date, day_rows, season_rows),
```

- [ ] **Step 4: Run the whole test file**

Run: `python -m pytest tests/seasons/test_recap.py -v`
Expected: 16 PASS

- [ ] **Step 5: Commit**

```bash
git add app/seasons/recap.py tests/seasons/test_recap.py
git commit -m "feat(recap): volunteer summary, needs_review count, highlights"
```

---

### Task 5: Slack renderer and poster

**Files:**
- Create: `app/slack/season_recap.py`
- Test: `tests/slack/test_season_recap.py`

**Interfaces:**
- Consumes: the full stats dict from `build_recap` (Tasks 1-4); `app.slack.client.get_slack_client`, `get_channel_id_by_name`.
- Produces: `CHANNEL_NAME = "leadership-registration"`, `build_recap_blocks(stats) -> tuple[list, str]` (blocks, fallback text), `post_season_recap(stats, channel_override=None) -> dict` with `success` key. Task 6's job calls `post_season_recap`.

- [ ] **Step 1: Write the failing tests**

Create `tests/slack/test_season_recap.py`:

```python
"""Renderer + poster for the daily registration recap. The renderer is pure
(stats dict in, blocks out), so no DB needed; the poster mocks the Slack
client and must never raise."""
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


def _stats(**overrides):
    base = {
        "season_id": 42,
        "season_name": "Winter 2098",
        "for_date": date(2098, 1, 10),
        "yesterday": {"new": 2, "returning": 1, "total": 3},
        "previous_day_total": 1,
        "season_totals": {"new": 90, "returning": 52, "total": 142,
                          "registration_limit": 200, "pct_of_limit": 71},
        "windows": {
            "returning": {"start": date(2098, 1, 6), "end": date(2098, 1, 26),
                          "is_open": True, "day_number": 5,
                          "days_remaining": 16, "length_days": 21},
            "new": None,
        },
        "prior_season": {"name": "Winter 2097",
                         "count_at_same_point": 118, "final_count": 240},
        "volunteer": {"answered": 2, "of": 3,
                      "interests": {"Lead a group at practice": 2},
                      "committees": {}},
        "needs_review": 0,
        "highlights": ["Biggest day of the season so far: 3 registrations."],
    }
    base.update(overrides)
    return base


def _all_text(blocks):
    parts = []
    for block in blocks:
        text = block.get("text")
        if isinstance(text, dict):
            parts.append(text.get("text", ""))
    return "\n".join(parts)


def test_blocks_render_every_section():
    from app.slack.season_recap import build_recap_blocks
    blocks, fallback = build_recap_blocks(_stats())
    text = _all_text(blocks)
    assert "3 registrations" in text          # yesterday
    assert "142" in text                       # season total
    assert "71%" in text                       # cap progress
    assert "day 5 of 21" in text               # window pace
    assert "Winter 2097" in text               # prior season
    assert "118" in text
    assert "Lead a group at practice" in text  # volunteer
    assert "Biggest day" in text               # highlight
    assert "142" in fallback


def test_blocks_omit_empty_sections():
    from app.slack.season_recap import build_recap_blocks
    blocks, _ = build_recap_blocks(_stats(
        prior_season=None,
        volunteer={"answered": 0, "of": 0, "interests": {}, "committees": {}},
        highlights=[],
        needs_review=0,
    ))
    text = _all_text(blocks)
    assert "Winter 2097" not in text
    assert "Get Involved" not in text
    assert "need review" not in text


def test_needs_review_warning_renders_with_link():
    from app.slack.season_recap import build_recap_blocks
    blocks, _ = build_recap_blocks(_stats(needs_review=4))
    text = _all_text(blocks)
    assert "4" in text
    assert "registration-review?season_id=42" in text


def test_post_success(app):
    from app.slack.season_recap import post_season_recap
    client = MagicMock()
    with app.app_context(), \
         patch("app.slack.season_recap.get_channel_id_by_name",
               return_value="C123"), \
         patch("app.slack.season_recap.get_slack_client",
               return_value=client):
        result = post_season_recap(_stats())
    assert result["success"] is True
    kwargs = client.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "C123"
    assert kwargs["blocks"]


def test_post_never_raises(app):
    from app.slack.season_recap import post_season_recap
    with app.app_context(), \
         patch("app.slack.season_recap.get_channel_id_by_name",
               side_effect=RuntimeError("slack down")):
        result = post_season_recap(_stats())
    assert result["success"] is False
    assert "slack down" in result["error"]


def test_post_unknown_channel(app):
    from app.slack.season_recap import post_season_recap
    with app.app_context(), \
         patch("app.slack.season_recap.get_channel_id_by_name",
               return_value=None):
        result = post_season_recap(_stats(), channel_override="nope")
    assert result["success"] is False
    assert "nope" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/slack/test_season_recap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.slack.season_recap'`

- [ ] **Step 3: Write minimal implementation**

Create `app/slack/season_recap.py`:

```python
"""Daily season registration recap for the leadership channel.

Rendering is pure (stats dict in, Block Kit out). Posting never raises,
same contract as app/slack/trips.py: the scheduler job must not die
because Slack did. Copy style: no em dashes.
"""
import os

from flask import current_app

from app.slack.client import get_channel_id_by_name, get_slack_client

CHANNEL_NAME = "leadership-registration"


def _base_url():
    return os.environ.get('EXTERNAL_BASE_URL', 'https://tcsc.ski')


def _section(text):
    return {"type": "section",
            "text": {"type": "mrkdwn", "text": text}}


def _plural(count, noun="registration"):
    return f"{count} {noun}" + ("" if count == 1 else "s")


def _yesterday_line(stats):
    y = stats["yesterday"]
    prev = stats["previous_day_total"]
    if y["total"] > prev:
        trend = f"up from {prev} the day before"
    elif y["total"] < prev:
        trend = f"down from {prev} the day before"
    else:
        trend = f"same as the day before ({prev})"
    return (f"*{_plural(y['total'])} yesterday* "
            f"({y['new']} new, {y['returning']} returning), {trend}.")


def _totals_line(stats):
    t = stats["season_totals"]
    line = (f"Season total: *{t['total']}* "
            f"({t['new']} new, {t['returning']} returning)")
    if t["pct_of_limit"] is not None:
        line += f", {t['pct_of_limit']}% of the {t['registration_limit']} cap"
    return line + "."


def _window_lines(stats):
    lines = []
    for label, window in (("Returning", stats["windows"]["returning"]),
                          ("New member", stats["windows"]["new"])):
        if not window:
            continue
        if window["is_open"]:
            lines.append(
                f"{label} window: day {window['day_number']} of "
                f"{window['length_days']}, closes "
                f"{window['end'].strftime('%b %-d')}.")
        elif stats["for_date"] > window["end"]:
            lines.append(
                f"{label} window closed {window['end'].strftime('%b %-d')}.")
        else:
            lines.append(
                f"{label} window opens {window['start'].strftime('%b %-d')}.")
    return lines


def _prior_line(stats):
    prior = stats["prior_season"]
    if not prior:
        return None
    return (f"At this same point in {prior['name']}: "
            f"{prior['count_at_same_point']} registrations "
            f"(it finished at {prior['final_count']}).")


def _volunteer_line(stats):
    v = stats["volunteer"]
    if not v["answered"]:
        return None
    parts = [f"{label} x{count}" for label, count in v["interests"].items()]
    line = (f"Get Involved: {v['answered']} of {v['of']} opted in. "
            + ", ".join(parts) + ".")
    if v["committees"]:
        committee_parts = [
            f"{label} x{count}" for label, count in v["committees"].items()]
        line += " Committees: " + ", ".join(committee_parts) + "."
    return line


def build_recap_blocks(stats):
    """Returns (blocks, fallback_text) for chat_postMessage."""
    date_label = stats["for_date"].strftime('%A, %b %-d')
    blocks = [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"Registration recap: {date_label}"}},
        _section(_yesterday_line(stats)),
        _section(_totals_line(stats)),
    ]

    pace = _window_lines(stats)
    prior = _prior_line(stats)
    if prior:
        pace.append(prior)
    if pace:
        blocks.append(_section("\n".join(pace)))

    volunteer = _volunteer_line(stats)
    if volunteer:
        blocks.append(_section(volunteer))

    if stats["needs_review"]:
        url = (f"{_base_url()}/admin/registration-review"
               f"?season_id={stats['season_id']}")
        blocks.append(_section(
            f":warning: {_plural(stats['needs_review'])} need review "
            f"before the lottery: <{url}|review page>"))

    for line in stats["highlights"]:
        blocks.append(_section(f":sparkles: {line}"))

    fallback = (f"Registration recap {date_label}: "
                f"{stats['yesterday']['total']} yesterday, "
                f"{stats['season_totals']['total']} season total.")
    return blocks, fallback


def post_season_recap(stats, channel_override=None):
    """Post the recap. Returns {"success": bool, "error": str|None}."""
    channel_name = channel_override or CHANNEL_NAME
    try:
        channel_id = get_channel_id_by_name(channel_name)
        if not channel_id:
            error = f"channel {channel_name} not found"
            current_app.logger.warning(f"season recap: {error}")
            return {"success": False, "error": error}
        blocks, fallback = build_recap_blocks(stats)
        get_slack_client().chat_postMessage(
            channel=channel_id, blocks=blocks, text=fallback)
        return {"success": True}
    except Exception as exc:
        current_app.logger.warning(f"season recap: post failed: {exc}")
        return {"success": False, "error": str(exc)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/slack/test_season_recap.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add app/slack/season_recap.py tests/slack/test_season_recap.py
git commit -m "feat(recap): Slack renderer and poster for leadership-registration"
```

---

### Task 6: Scheduler job, registration, manual trigger

**Files:**
- Modify: `app/scheduler.py` (job function near the other `run_*_job` functions; registration inside `init_scheduler` after the lead-availability block at ~line 1388; `trigger_skipper_job_now`'s `job_map` and `jobs_with_channel_override` at ~lines 1473-1493; the module docstring's job list at lines 12-26)
- Test: `tests/test_scheduler_season_recap.py`

**Interfaces:**
- Consumes: `app.seasons.recap.build_recap`, `should_post`; `app.slack.season_recap.post_season_recap`; `app.models.Season.get_current`; `app.utils.today_central`.
- Produces: `run_season_recap_job(app, channel_override=None)`; scheduler job id `season_registration_recap`; manual trigger key `'season_recap'`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scheduler_season_recap.py`:

```python
"""The recap job is a thin gate-then-post wrapper; these tests mock the
stats and Slack layers and only assert the wiring: quiet when gated, one
post (for yesterday) when due, and no crash when everything blows up."""
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest

from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


TODAY = date(2098, 1, 11)


def test_quiet_when_gate_says_no(app):
    from app.scheduler import run_season_recap_job
    with patch("app.models.Season.get_current",
               return_value=MagicMock()), \
         patch("app.seasons.recap.should_post", return_value=False), \
         patch("app.slack.season_recap.post_season_recap") as post:
        run_season_recap_job(app)
    post.assert_not_called()


def test_quiet_without_current_season(app):
    from app.scheduler import run_season_recap_job
    with patch("app.models.Season.get_current", return_value=None), \
         patch("app.slack.season_recap.post_season_recap") as post:
        run_season_recap_job(app)
    post.assert_not_called()


def test_posts_yesterdays_recap_when_due(app):
    from app.scheduler import run_season_recap_job
    season = MagicMock()
    stats = {"yesterday": {"total": 3}, "season_totals": {"total": 142}}
    with patch("app.models.Season.get_current", return_value=season), \
         patch("app.seasons.recap.should_post", return_value=True), \
         patch("app.scheduler.today_central", return_value=TODAY), \
         patch("app.seasons.recap.build_recap",
               return_value=stats) as build, \
         patch("app.slack.season_recap.post_season_recap",
               return_value={"success": True}) as post:
        run_season_recap_job(app, channel_override="test-chan")
    build.assert_called_once_with(season, TODAY - timedelta(days=1))
    post.assert_called_once_with(stats, channel_override="test-chan")


def test_job_survives_exceptions(app):
    from app.scheduler import run_season_recap_job
    with patch("app.models.Season.get_current",
               side_effect=RuntimeError("db down")):
        run_season_recap_job(app)  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler_season_recap.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_season_recap_job'`

- [ ] **Step 3: Write minimal implementation**

In `app/scheduler.py`, add after `run_close_expired_polls_job` (before `init_scheduler`):

```python
def run_season_recap_job(app: Flask, channel_override: str = None):
    """Daily registration recap to #leadership-registration.

    Self-gating via should_post(): posts while a registration window is
    open plus a 7-day tail after the last one closes, silent otherwise.
    A zero-registration day during the window still posts -- the zero is
    the signal. Covers the prior Central day.

    Args:
        app: Flask application instance for context.
        channel_override: Optional channel name to override default.
    """
    from datetime import timedelta

    with app.app_context():
        from app.models import Season
        from app.seasons.recap import build_recap, should_post
        from app.slack.season_recap import post_season_recap

        try:
            season = Season.get_current()
            if not season:
                app.logger.info("Season recap: no current season, staying quiet")
                return
            today = today_central()
            if not should_post(season, today):
                app.logger.info(
                    "Season recap: no open or recently closed window, staying quiet")
                return

            stats = build_recap(season, today - timedelta(days=1))
            result = post_season_recap(stats, channel_override=channel_override)
            if result.get("success"):
                app.logger.info(
                    f"Season recap posted: {stats['yesterday']['total']} yesterday, "
                    f"{stats['season_totals']['total']} season total")
            else:
                app.logger.warning(
                    f"Season recap post failed: {result.get('error')}")
        except Exception as e:
            app.logger.error(f"Season recap job failed: {e}", exc_info=True)
```

Note the mocks in the test patch `app.seasons.recap.should_post` etc., so the
job MUST import those names inside the function from their home modules (as
shown above), not hold module-level references.

In `init_scheduler`, after the "Close Expired Availability Polls" job block and before `scheduler.start()`:

```python
    # ========================================================================
    # Season Registration Recap
    # ========================================================================

    # Daily: registration recap to #leadership-registration while a window
    # is open (plus a 7-day tail); the job self-gates via should_post().
    scheduler.add_job(
        func=run_season_recap_job,
        args=[app],
        trigger=CronTrigger(
            hour=8,
            minute=5,
            timezone='America/Chicago'
        ),
        id='season_registration_recap',
        name='Season Registration Recap',
        replace_existing=True,
        misfire_grace_time=3600
    )
```

In `trigger_skipper_job_now`, add to `job_map`:

```python
        'season_recap': run_season_recap_job,
```

and add `'season_recap'` to the `jobs_with_channel_override` set. Also add
`'season_recap'` to the docstring's `job_type` list in that function, and add
this line to the module docstring's "Scheduled Jobs" list at the top of the
file:

```
- 8:05 AM: Season registration recap → #leadership-registration (window-gated)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler_season_recap.py -v`
Expected: 4 PASS

- [ ] **Step 5: Run the neighboring suites to catch wiring regressions**

Run: `python -m pytest tests/seasons/ tests/slack/ tests/test_scheduler_season_recap.py tests/test_app_startup.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add app/scheduler.py tests/test_scheduler_season_recap.py
git commit -m "feat(recap): schedule daily season recap job at 8:05am Central"
```

---

### Task 7: Full verification and PR

**Files:**
- None new; verification only.

**Interfaces:**
- Consumes: everything above.
- Produces: a PR from `season-recap` to `main`.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: everything passes (note: two pre-existing leaks in `tests/events/` mutate local dev data; that's known, not caused by this work).

- [ ] **Step 2: Sanity-render a recap against the dev DB**

Run a one-off script through Flask shell to confirm `build_recap` runs against real data without errors (it may legitimately return zeros):

```bash
python -c "
from app import create_app
from app.models import Season
from app.seasons.recap import build_recap, should_post
from app.slack.season_recap import build_recap_blocks
from app.utils import today_central
from datetime import timedelta
app = create_app()
with app.app_context():
    season = Season.get_current()
    print('current season:', season)
    if season:
        print('should_post today:', should_post(season, today_central()))
        stats = build_recap(season, today_central() - timedelta(days=1))
        blocks, fallback = build_recap_blocks(stats)
        print(fallback)
        for b in blocks: print(b)
"
```

Expected: prints a plausible recap, no traceback.

- [ ] **Step 3: Push and open the PR**

```bash
git push -u origin season-recap
gh pr create --title "Daily season registration recap to #leadership-registration" --body "$(cat <<'EOF'
Daily 8:05am Central job posting a season-registration recap to #leadership-registration: yesterday's new/returning split, season totals and cap progress, window pace, same-point comparison to the prior season, Get Involved answers, a needs-review warning when nonzero, and occasional highlight lines (record day, 50-milestones, household signups).

Self-gating: posts only while a registration window is open plus 7 days after the last one closes. Silent the rest of the year. Zero days during the window still post.

Spec: docs/superpowers/specs/2026-08-24-season-registration-recap-design.md

Note for deploy: the leadership-registration channel must exist and the bot must be a member before the first post.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01TtqrVijCEgDNdJR3dcM35Y
EOF
)"
```

- [ ] **Step 4: Report back**

Summarize the PR link and remind: invite the bot to `#leadership-registration` (create it if needed) before merge, or the first run logs "channel not found" and skips.
