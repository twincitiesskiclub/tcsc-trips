# Lead schedule restyle and Lead button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the lead schedule post in #coord-practices-leads-assists to the approved "v15" look and let anyone in the lead pool take an open session with one click.

**Architecture:** The post stays a pure Block Kit builder (`app/slack/blocks/block_post.py`) fed by `block_post_rows()` (`app/practices/blocks.py`), re-rendered on every refresh. A new `sign_up_as_lead()` in `blocks.py` adds a lead under a row lock and reuses `refresh_practice_posts()`, so every surface updates the way an Assign save does. The Assign modal records the leads it opened with, so a save only applies the director's own changes.

**Tech Stack:** Flask, SQLAlchemy, PostgreSQL, slack_bolt (socket mode), Slack Block Kit, pytest.

**Spec:** `docs/superpowers/specs/2026-10-09-lead-schedule-restyle-design.md`

## Global Constraints

- Work on branch `lead-schedule-restyle` in `/workspace/tcsc-trips/.worktrees/lead-schedule-restyle`. Never commit to `main`: Render deploys every commit on main.
- Run tests against the scratch DB: prefix every pytest command with `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test`. Use `/workspace/tcsc-trips/.venv/bin/python -m pytest`.
- DB tests follow `tests/practices/conftest.py`: year 2099 dates, `"TEST "` name prefixes, `try/finally` cleanup that starts with `db.session.rollback()`, ids captured as plain ints before the `try`, no `create_all`/`drop_all`, assertions scoped to the test's own rows.
- No em dashes in any product copy.
- All Slack post updates go through `refresh_practice_posts()`; never update a post directly except the sign-up thread reply.
- Slack calls in the sign-up path never raise to the caller; log and continue.
- Exact copy (do not reword):
  - Header: `:ski: Lead schedule · {range}`
  - Empty: `:raising_hand: *Needs {N} leads*` (`lead` when N is 1)
  - Partial: `{mentions} · :raising_hand: *Needs {N} more*`
  - Footer last line: `Can't make yours? Ask in this thread for a sub.`
  - Button: `Lead {Dow M/D} · {time}`; confirm title `Lead this practice?`, confirm `I'll lead it`, deny `Cancel`
  - Notification text: `Lead schedule for {range} is up · {need}` with need `1 practice still needs leads` / `{N} practices still need leads` / `every practice has leads`
  - Not in pool: `Leading is open to the lead pool. Want in? Ask in this thread.`
  - Thread reply: `:raised_hands: <@{uid}> is leading {Dow M/D} · {time}` plus ` with {mentions}`

## Review Focus

1. A lead whose Slack account isn't linked to a user taps Lead: they must get the not-in-pool message, not a crash. Test in Task 3.
2. A location or type name containing `&`, `<`, `>` or `|`: the map link and quote must stay intact. Test in Task 1.
3. A session with `leads_needed == 1`: "Needs 1 lead" (singular), and one sign-up fills it. Tests in Tasks 1 and 3.
4. A week with two or more open sessions: every button needs a distinct `action_id` or Slack rejects the whole message. Test in Task 1.
5. A director has the Assign modal open while someone taps Lead: the self-signup must survive the save. Test in Task 5.

---

### Task 1: Pure builder for the new post

**Files:**
- Modify: `app/slack/blocks/block_post.py` (add helpers; replace `build_lead_schedule`; edit `_schedule_button` confirm text)
- Test: `tests/slack/test_block_post_blocks.py`

**Interfaces:**
- Consumes: row dicts with the existing keys (`practice_id, emoji, when, where, cancelled, leads, lead_mentions, coaches, leads_needed, available`) plus three new keys Task 2 adds to `block_post_rows()`:
  - `activity: str | None`, the practice's first activity name
  - `location: dict | None`, `{"name": str, "spot": str | None, "url": str | None}`
  - `kinds: list[str]`, type names, else activity names
- Produces, in `app/slack/blocks/block_post.py`:
  - `escape(text) -> str`
  - `join_names(names) -> str`, giving "a", "a and b", "a, b and c"
  - `activity_emoji(activity: str | None) -> str`
  - `takeable(row, now) -> bool`
  - `build_lead_schedule(poll, rows, *, now) -> list[dict]` (signature changes: `now` is new and keyword-only)
  - `lead_schedule_text(poll, rows, *, now) -> str`

- [ ] **Step 1: Write the failing tests**

In `tests/slack/test_block_post_blocks.py`, add `lead_schedule_text` to the import from `app.slack.blocks.block_post`. Replace `_row` with this version, which adds the new keys with defaults:

```python
def _row(pid, *, emoji="letter_a", where="TEST Wirth · Bounding", leads=(), coaches=(),
         needed=2, available=0, cancelled=False, day=20, mentions=None,
         activity="Pole Run", location="default", kinds=("Intervals",), hour=18):
    if location == "default":
        location = {"name": "TEST Wirth", "spot": "Xerxes Field", "url": "https://maps.example/w"}
    return {"practice_id": pid, "emoji": emoji, "when": datetime(2099, 1, day, hour, 15),
            "where": where, "cancelled": cancelled, "leads": list(leads),
            "lead_mentions": list(leads if mentions is None else mentions),
            "coaches": list(coaches), "leads_needed": needed, "available": available,
            "activity": activity, "location": location, "kinds": list(kinds)}


NOW = datetime(2099, 1, 1, 9, 0)  # before every test session
```

Delete `test_lead_schedule_mentions_leads_and_flags_gaps` and add:

```python
def test_lead_schedule_groups_weeks_in_one_quote_each():
    rows = [
        _row(1, leads=["Katrin O", "Gunnar M"], mentions=["<@U1>", "<@U2>"]),
        _row(2, leads=["Jo E", "Al B"], mentions=["<@U3>", "<@U4>"], day=22),
        _row(3, leads=["Mo P", "Di Q"], mentions=["<@U5>", "<@U6>"], day=27),
    ]
    blocks = build_lead_schedule(_poll("closed"), rows, now=NOW)
    assert blocks[0]["text"]["text"] == ":ski: Lead schedule · Jan 19 – Feb 1"
    sections = [b for b in blocks if b["type"] == "section"]
    assert len(sections) == 2
    week1 = sections[0]["text"]["text"]
    assert week1.startswith("*Week of Jan 19*\n> :runner:  *Tue 1/20* · 6:15p · "
                            "<https://maps.example/w|TEST Wirth, Xerxes Field> · Intervals\n"
                            "> <@U1> and <@U2>\n>\n> :runner:  *Thu 1/22*")
    assert sections[1]["text"]["text"].startswith("*Week of Jan 26*\n")
    assert not any(b["type"] in ("actions", "divider") for b in blocks)
    assert blocks[-1] == {"type": "context", "elements": [{"type": "mrkdwn", "text":
        "Can't make yours? Ask in this thread for a sub."}]}
    assert "—" not in _text(blocks)


def test_lead_schedule_needs_lines_coaches_and_place_fallbacks():
    rows = [
        _row(1, location=None, kinds=()),
        _row(2, leads=["Joe H"], mentions=["<@U3>"], coaches=["KJ"], day=22),
        _row(3, needed=1, day=27),
        _row(4, location={"name": "TEST Balance", "spot": None, "url": None},
             activity="Strength", kinds=("Circuit",), day=29),
    ]
    text = _text(build_lead_schedule(_poll("closed"), rows, now=NOW))
    assert "*Tue 1/20* · 6:15p · location TBD\\n> :raising_hand: *Needs 2 leads*" in text
    assert "> <@U3> · :raising_hand: *Needs 1 more* · coach KJ" in text
    assert ":raising_hand: *Needs 1 lead*" in text
    assert ":muscle:  *Thu 1/29* · 6:15p · TEST Balance · Circuit" in text


def test_lead_schedule_escapes_names_and_keeps_links_intact():
    rows = [_row(1, location={"name": "TEST A&B <Park>", "spot": "Lot|2", "url": "https://m/x"},
                 kinds=("Run & Gun",))]
    text = build_lead_schedule(_poll("closed"), rows, now=NOW)[1]["text"]["text"]
    assert "<https://m/x|TEST A&amp;B &lt;Park&gt;, Lot 2>" in text
    assert "· Run &amp; Gun" in text


def test_cancelled_row_is_plain_strikethrough_without_button():
    rows = [_row(1, cancelled=True)]
    blocks = build_lead_schedule(_poll("closed"), rows, now=NOW)
    assert "> ~Tue 1/20 · 6:15p · TEST Wirth~ _Cancelled_" in blocks[1]["text"]["text"]
    assert not any(b["type"] == "actions" for b in blocks)


def test_activity_emoji_keywords_and_fallback():
    from app.slack.blocks.block_post import activity_emoji
    assert activity_emoji("Strength") == ":muscle:"
    assert activity_emoji("Mountain Bike") == ":bicyclist:"
    assert activity_emoji("Skate/Classic Rollerski") == ":ski:"
    assert activity_emoji("Pole Hike, Pole Run") == ":runner:"
    assert activity_emoji("Hike") == ":runner:"
    assert activity_emoji("Orienteering") == ":ski:"
    assert activity_emoji(None) == ":ski:"


def test_lead_buttons_only_for_takeable_sessions_with_unique_ids():
    rows = [
        _row(1),                                              # open
        _row(2, leads=["Sarah H"], mentions=["<@U9>"], hour=19),  # partial, same day
        _row(3, leads=["A B", "C D"], mentions=["<@U1>", "<@U2>"], day=22),  # full
        _row(4, cancelled=True, day=22, hour=19),             # cancelled
    ]
    blocks = build_lead_schedule(_poll("closed"), rows, now=NOW)
    actions = [b for b in blocks if b["type"] == "actions"]
    assert len(actions) == 1
    buttons = actions[0]["elements"]
    assert [b["action_id"] for b in buttons] == ["lead_signup_1", "lead_signup_2"]
    assert [b["value"] for b in buttons] == ["1", "2"]
    assert buttons[0]["text"]["text"] == "Lead Tue 1/20 · 6:15p"
    confirm = buttons[0]["confirm"]
    assert confirm["title"]["text"] == "Lead this practice?"
    assert confirm["confirm"]["text"] == "I'll lead it"
    assert confirm["deny"]["text"] == "Cancel"
    assert confirm["text"]["text"] == (
        "Tue 1/20 at 6:15p, Intervals at TEST Wirth. "
        "You're added right away. If plans change, ask in the thread.")
    assert "You'll lead with Sarah H." in buttons[1]["confirm"]["text"]["text"]
    assert all(len(b["confirm"]["text"]["text"]) <= 300 for b in buttons)


def test_past_sessions_get_no_button_and_do_not_count_as_open():
    from app.slack.blocks.block_post import lead_schedule_text
    rows = [_row(1), _row(2, day=27)]
    later = datetime(2099, 1, 21, 9, 0)  # after 1/20, before 1/27
    blocks = build_lead_schedule(_poll("closed"), rows, now=later)
    buttons = [e for b in blocks if b["type"] == "actions" for e in b["elements"]]
    assert [b["action_id"] for b in buttons] == ["lead_signup_2"]
    assert lead_schedule_text(_poll("closed"), rows, now=later).endswith(
        "· 1 practice still needs leads")


def test_star_line_wording():
    def footer(rows):
        return build_lead_schedule(_poll("closed"), rows, now=NOW)[-1]["elements"][0]["text"]

    full = lambda pid, a, b, **kw: _row(pid, leads=["x", "y"], mentions=[a, b], **kw)  # noqa: E731
    assert footer([full(1, "<@A>", "<@B>")]).startswith("Can't make yours?")
    assert footer([full(1, "<@A>", "<@B>"), full(2, "<@A>", "<@C>", day=22)]).startswith(
        ":star: <@A> is leading twice.\n")
    assert footer([full(1, "<@A>", "<@B>"), full(2, "<@A>", "<@B>", day=22)]).startswith(
        ":star: <@A> and <@B> are leading twice.\n")
    three = [full(1, "<@A>", "<@B>"), full(2, "<@A>", "<@B>", day=22),
             full(3, "<@A>", "<@C>", day=27)]
    assert footer(three).startswith(
        ":star: <@B> is leading twice.\n:star: <@A> is leading 3 times.\n")


def test_cancelled_sessions_do_not_count_toward_stars():
    rows = [_row(1, leads=["x"], mentions=["<@A>"]),
            _row(2, leads=["x"], mentions=["<@A>"], cancelled=True, day=22)]
    footer = build_lead_schedule(_poll("closed"), rows, now=NOW)[-1]["elements"][0]["text"]
    assert ":star:" not in footer


def test_lead_schedule_text_plurals():
    from app.slack.blocks.block_post import lead_schedule_text
    full = _row(9, leads=["a", "b"], mentions=["<@A>", "<@B>"])
    poll = _poll("closed")
    assert lead_schedule_text(poll, [full], now=NOW) == (
        "Lead schedule for Jan 19 – Feb 1 is up · every practice has leads")
    assert lead_schedule_text(poll, [_row(1), full], now=NOW).endswith(
        "· 1 practice still needs leads")
    assert lead_schedule_text(poll, [_row(1), _row(2, day=22)], now=NOW).endswith(
        "· 2 practices still need leads")


def test_join_names():
    from app.slack.blocks.block_post import join_names
    assert join_names([]) == ""
    assert join_names(["a"]) == "a"
    assert join_names(["a", "b"]) == "a and b"
    assert join_names(["a", "b", "c"]) == "a, b and c"


def test_post_schedule_confirm_mentions_lead_buttons():
    text = _text(build_block_post(_poll("open", "2.0"), [_row(1)], permalink=None, footer=None))
    assert "Open sessions get a Lead button anyone in the lead pool can take." in text
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_blocks.py -q`
Expected: FAIL (ImportError on `lead_schedule_text`, then assertion failures).

- [ ] **Step 3: Implement**

In `app/slack/blocks/block_post.py`, add at the top:

```python
from collections import Counter
from datetime import timedelta
```

Change `_schedule_button`'s confirm text to:

```python
            "text": {"type": "plain_text", "text":
                     "Posts every session and its leads to #coord-practices-leads-assists "
                     "and @mentions each lead. Open sessions get a Lead button anyone in "
                     "the lead pool can take. It updates itself after that."},
```

Replace the whole `build_lead_schedule` function with:

```python
# The leads' schedule post in #coord-practices-leads-assists.

ACTIVITY_EMOJI = (  # first keyword found in the practice's first activity wins
    ("strength", ":muscle:"),
    ("bike", ":bicyclist:"),
    ("ski", ":ski:"),
    ("run", ":runner:"),
    ("hike", ":runner:"),
)
SUB_LINE = "Can't make yours? Ask in this thread for a sub."


def escape(text) -> str:
    """Slack mrkdwn escaping for interpolated names."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def join_names(names) -> str:
    names = list(names)
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def activity_emoji(activity) -> str:
    name = (activity or "").lower()
    return next((emoji for word, emoji in ACTIVITY_EMOJI if word in name), ":ski:")


def _short(row) -> int:
    return max(row["leads_needed"] - len(row["leads"]), 0)


def takeable(row, now) -> bool:
    """Shows a Lead button: short of leads, not cancelled, not started."""
    return not row["cancelled"] and _short(row) > 0 and row["when"] > now


def _day(when) -> str:
    return when.strftime("%a %-m/%-d")


def _week_label(when) -> str:
    monday = when.date() - timedelta(days=when.weekday())
    return f"Week of {monday.strftime('%b %-d')}"


def _place_name(row) -> str:
    return row["location"]["name"] if row["location"] else "location TBD"


def _place(row) -> str:
    loc = row["location"]
    if not loc:
        return "location TBD"
    label = escape(", ".join(p for p in (loc["name"], loc["spot"]) if p)).replace("|", " ")
    return f"<{loc['url']}|{label}>" if loc["url"] else label


def _session_line(row) -> str:
    kinds = f" · {escape(', '.join(row['kinds']))}" if row["kinds"] else ""
    return (f"{activity_emoji(row['activity'])}  *{_day(row['when'])}* · "
            f"{_time(row['when'])} · {_place(row)}{kinds}")


def _schedule_leads_line(row) -> str:
    short = _short(row)
    if not row["lead_mentions"]:
        line = f":raising_hand: *Needs {short} lead{'' if short == 1 else 's'}*"
    elif short:
        line = f"{join_names(row['lead_mentions'])} · :raising_hand: *Needs {short} more*"
    else:
        line = join_names(row["lead_mentions"])
    if row["coaches"]:
        line += f" · coach {join_names(escape(c) for c in row['coaches'])}"
    return line


def _schedule_row(row) -> str:
    if row["cancelled"]:
        return (f"> ~{_day(row['when'])} · {_time(row['when'])} · "
                f"{escape(_place_name(row))}~ _Cancelled_")
    return f"> {_session_line(row)}\n> {_schedule_leads_line(row)}"


def _lead_button(row) -> dict:
    day, time = _day(row["when"]), _time(row["when"])
    text = f"{day} at {time}, {', '.join(row['kinds']) or 'Practice'} at {_place_name(row)}."
    if row["leads"]:
        text += f" You'll lead with {join_names(row['leads'])}."
    text += " You're added right away. If plans change, ask in the thread."
    return {
        "type": "button", "action_id": f"lead_signup_{row['practice_id']}",
        "value": str(row["practice_id"]),
        "text": {"type": "plain_text", "text": f"Lead {day} · {time}"},
        "confirm": {
            "title": {"type": "plain_text", "text": "Lead this practice?"},
            "text": {"type": "plain_text", "text": text[:300]},
            "confirm": {"type": "plain_text", "text": "I'll lead it"},
            "deny": {"type": "plain_text", "text": "Cancel"},
        },
    }


def _star_lines(rows) -> list[str]:
    counts = Counter(m for r in rows if not r["cancelled"] for m in r["lead_mentions"])
    by_count: dict[int, list[str]] = {}
    for mention, n in counts.items():
        if n >= 2:
            by_count.setdefault(n, []).append(mention)
    lines = []
    for n in sorted(by_count):
        people = by_count[n]
        times = "twice" if n == 2 else f"{n} times"
        lines.append(f":star: {join_names(people)} {'is' if len(people) == 1 else 'are'} "
                     f"leading {times}.")
    return lines


def build_lead_schedule(poll, rows, *, now) -> list[dict]:
    """One bold week label and one quote of sessions per week, Lead buttons
    under a week with a takeable session, stars and the sub line at the end."""
    blocks = [{"type": "header", "text": {"type": "plain_text", "emoji": True,
               "text": f":ski: Lead schedule · {block_range_label(poll.starts_on, poll.ends_on)}"}}]
    weeks: dict[str, list[dict]] = {}
    for row in rows:
        weeks.setdefault(_week_label(row["when"]), []).append(row)
    for label, week in weeks.items():
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text":
                       f"*{label}*\n" + "\n>\n".join(_schedule_row(r) for r in week)}})
        buttons = [_lead_button(r) for r in week if takeable(r, now)]
        if buttons:
            blocks.append({"type": "actions", "elements": buttons[:25]})
    blocks.append(_context("\n".join(_star_lines(rows) + [SUB_LINE])))
    return blocks


def lead_schedule_text(poll, rows, *, now) -> str:
    """Fallback text: what mention notifications and screen readers get."""
    open_count = sum(1 for r in rows if takeable(r, now))
    if not open_count:
        need = "every practice has leads"
    elif open_count == 1:
        need = "1 practice still needs leads"
    else:
        need = f"{open_count} practices still need leads"
    return f"Lead schedule for {block_range_label(poll.starts_on, poll.ends_on)} is up · {need}"
```

`_context` and `_time` already exist in this module. `_leads_line(row, leads=None)` is still used by the block post, so leave it in place.

- [ ] **Step 4: Run the tests to see them pass**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_blocks.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/slack/blocks/block_post.py tests/slack/test_block_post_blocks.py
git commit -m "Lead schedule: weekly quotes, map links, Needs lines and Lead buttons (builder)"
```

---

### Task 2: Feed the builder and post with the new text

**Files:**
- Modify: `app/practices/blocks.py` (`block_post_rows`, `_render_schedule`, `post_lead_schedule`)
- Modify: `scripts/preview_lead_blocks.py` (new row keys, `now`, a title filter)
- Test: `tests/slack/test_block_post_slack.py`

**Interfaces:**
- Consumes: `build_lead_schedule(poll, rows, *, now)` and `lead_schedule_text(poll, rows, *, now)` from Task 1.
- Produces: rows with the keys `activity`, `location`, `kinds`. `_render_schedule(poll, *, exclude_practice_id=None) -> tuple[list[dict], str]` keeps its signature.

- [ ] **Step 1: Write the failing tests**

Append to `tests/slack/test_block_post_slack.py`:

```python
def test_rows_carry_activity_location_and_kinds(block):
    from app.practices.models import PracticeActivity, PracticeLocation, PracticeType

    db.session.rollback()
    loc = PracticeLocation(name="TEST Sched Loc", spot="TEST Spot", google_maps_url="https://m/l")
    act = PracticeActivity(name="TEST Sched Strength")
    typ = PracticeType(name="TEST Sched Circuit")
    db.session.add_all([loc, act, typ])
    db.session.commit()
    ids = (loc.id, act.id, typ.id)
    try:
        practice = Practice.query.filter_by(logistics_notes="TEST b5").one()
        practice.location_id = ids[0]
        practice.activities = [act]
        practice.practice_types = [typ]
        db.session.commit()
        row = blocks.block_post_rows(block)[0]
        assert row["activity"] == "TEST Sched Strength"
        assert row["location"] == {"name": "TEST Sched Loc", "spot": "TEST Spot",
                                   "url": "https://m/l"}
        assert row["kinds"] == ["TEST Sched Circuit"]
    finally:
        db.session.rollback()
        practice = Practice.query.filter_by(logistics_notes="TEST b5").one()
        practice.location_id = None
        practice.activities = []
        practice.practice_types = []
        db.session.commit()
        for model, i in ((PracticeLocation, ids[0]), (PracticeActivity, ids[1]),
                         (PracticeType, ids[2])):
            row = db.session.get(model, i)
            if row is not None:
                db.session.delete(row)
        db.session.commit()


def test_schedule_post_uses_new_text_and_no_unfurls(assigned, client):
    client.chat_postMessage.return_value = {"ts": "5.000"}
    blocks.post_lead_schedule(assigned.id)
    posted = client.chat_postMessage.call_args.kwargs
    assert posted["text"].startswith("Lead schedule for Jan 19 – Feb 1 is up · ")
    assert posted["unfurl_links"] is False and posted["unfurl_media"] is False
    assert ":ski: Lead schedule · Jan 19 – Feb 1" in str(posted["blocks"])
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_slack.py -q`
Expected: the two new tests fail (KeyError `activity`, or a TypeError from the missing `now`).

- [ ] **Step 3: Implement**

In `app/practices/blocks.py`, in `block_post_rows`, add three keys to the dict appended to `rows` (after `"available"`):

```python
            "activity": practice.activities[0].name if practice.activities else None,
            "location": ({"name": practice.location.name, "spot": practice.location.spot,
                          "url": practice.location.google_maps_url}
                         if practice.location else None),
            "kinds": ([t.name for t in practice.practice_types]
                      or [a.name for a in practice.activities]),
```

Replace `_render_schedule` with:

```python
def _render_schedule(poll, *, exclude_practice_id=None) -> tuple[list[dict], str]:
    from app.slack.blocks.block_post import build_lead_schedule, lead_schedule_text

    rows = block_post_rows(poll, exclude_practice_id=exclude_practice_id)
    now = now_central_naive()
    return build_lead_schedule(poll, rows, now=now), lead_schedule_text(poll, rows, now=now)
```

In `post_lead_schedule`, change the post call to:

```python
        ts = get_slack_client().chat_postMessage(
            channel=COORD_CHANNEL_ID, blocks=rendered, text=text,
            unfurl_links=False, unfurl_media=False)["ts"]
```

In `scripts/preview_lead_blocks.py`:
- Add the three keys to the `rows()` dict, alternating activity by index so both emoji show:

```python
             "activity": "Strength" if "Balance" in wh else "Pole Run",
             "location": None if "TBD" in wh else {"name": wh.split(" · ")[0], "spot": None,
                                                   "url": "https://www.google.com/maps"},
             "kinds": [wh.split(" · ")[1]] if " · " in wh else [],
```

- Replace the existing `yield "lead schedule in #coord-practices-leads-assists", ...` line with two surfaces:

```python
    yield "lead schedule in #coord-practices-leads-assists (open sessions)", build_lead_schedule(
        poll("closed"), rows(), now=datetime(2026, 10, 20, 9, 0))
    full = [(e, w, wh, ["Katrin S", "Ellie T"], c, a) for e, w, wh, _, c, a in ROWS]
    yield "lead schedule in #coord-practices-leads-assists (all covered)", build_lead_schedule(
        poll("closed"), rows(items=full), now=datetime(2026, 10, 20, 9, 0))
```

- Make `post()` accept an optional title filter. Change `if __name__ == "__main__":` to:

```python
if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    else:
        post(next((a for a in sys.argv[1:] if not a.startswith("--")), ""))
```

  Then change `def post():` to `def post(only=""):`, and the loop line to `for title, blocks in surfaces():` followed by `if only not in title: continue` as its first statement.

- [ ] **Step 4: Run the tests to see them pass**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_slack.py tests/slack/test_block_post_blocks.py tests/practices/test_blocks.py -q`
Expected: all pass.

Run: `/workspace/tcsc-trips/.venv/bin/python -c "import runpy, sys; sys.argv=['x']; m = runpy.run_path('scripts/preview_lead_blocks.py', run_name='preview'); print(sum(1 for _ in m['surfaces']()))"`
Expected: prints a count, with no exception. This doesn't post anything, because `run_name` isn't `__main__`.

- [ ] **Step 5: Commit**

```bash
git add app/practices/blocks.py scripts/preview_lead_blocks.py tests/slack/test_block_post_slack.py
git commit -m "Lead schedule rows carry activity, location and kinds; new notification text"
```

---

### Task 3: `sign_up_as_lead`

**Files:**
- Modify: `app/practices/blocks.py` (add constants and three functions after `post_lead_schedule`)
- Create: `tests/practices/test_lead_signup.py`

**Interfaces:**
- Consumes: `eligible_leads()` (already imported in `blocks.py`), `poll_for_date`, `_mention`, `now_central_naive`, `get_slack_client`, `COORD_CHANNEL_ID`. Also `join_names` from `app.slack.blocks.block_post` (Task 1) and `refresh_practice_posts` from `app.slack.practices`.
- Produces: `sign_up_as_lead(practice_id: int, slack_uid: str) -> dict`. It returns `{"success": True}` or `{"success": False, "error": str}`. Task 4 calls it.

- [ ] **Step 1: Write the failing tests**

Create `tests/practices/test_lead_signup.py`:

```python
"""The Lead button: anyone in the lead pool takes an open spot.

Real local DB; year 2099 dates; see tests/practices/conftest.py.
"""

from datetime import date, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.models import SlackUser, Tag, User, db
from app.practices import blocks
from app.practices.availability_models import LeadAvailabilityPoll
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice, PracticeLead

START, END = date(2099, 1, 19), date(2099, 2, 1)


def _user(name, *, in_pool=True, slack=True):
    suffix = uuid4().hex[:10]
    su = SlackUser(slack_uid=f"TEST-SIGNUP-{suffix}") if slack else None
    user = User(first_name=f"TEST {name}", last_name="Signup",
                email=f"test-signup-{suffix}@example.invalid", slack_user=su)
    if in_pool:
        tag = Tag.query.filter_by(name="PRACTICES_LEAD").first() or Tag(
            name="PRACTICES_LEAD", display_name="Practices Lead")
        user.tags = [tag]
    db.session.add(user)
    db.session.commit()
    return user.id, (su.slack_uid if su else None), (su.id if su else None)


@pytest.fixture()
def env(db_session, monkeypatch):
    """A 2099 practice in a block whose schedule is posted, plus patched Slack."""
    db.session.rollback()
    practice = Practice(date=datetime(2099, 1, 20, 18, 15), day_of_week="Tuesday",
                        is_draft=False, leads_needed=2, logistics_notes="TEST signup")
    db.session.add(practice)
    db.session.commit()
    poll = blocks.create_block_poll(START, END)
    poll.schedule_ts = "7.000"
    db.session.commit()
    refreshes = []
    monkeypatch.setattr("app.slack.practices.refresh_practice_posts",
                        lambda p, **kw: refreshes.append((p.id, kw)) or {})
    client = MagicMock()
    monkeypatch.setattr(blocks, "get_slack_client", lambda: client)
    monkeypatch.setattr(blocks, "now_central_naive", lambda: datetime(2099, 1, 1, 9, 0))
    made = {"users": [], "slack": []}

    def user(name, **kw):
        uid, slack_uid, sid = _user(name, **kw)
        made["users"].append(uid)
        if sid:
            made["slack"].append(sid)
        return uid, slack_uid

    pid = practice.id
    yield {"pid": pid, "client": client, "refreshes": refreshes, "user": user}
    db.session.rollback()
    for lead in PracticeLead.query.filter_by(practice_id=pid).all():
        db.session.delete(lead)
    p = db.session.get(Practice, pid)
    if p is not None:
        db.session.delete(p)
    for poll in LeadAvailabilityPoll.query.filter_by(starts_on=START).all():
        db.session.delete(poll)
    db.session.commit()
    for uid in made["users"]:
        u = db.session.get(User, uid)
        if u is not None:
            db.session.delete(u)
    db.session.commit()
    for sid in made["slack"]:
        s = db.session.get(SlackUser, sid)
        if s is not None:
            db.session.delete(s)
    db.session.commit()


def _leads(pid):
    db.session.expire_all()
    return sorted((l.user_id, l.role) for l in db.session.get(Practice, pid).leads)


def _add(pid, uid, role="lead"):
    db.session.get(Practice, pid).leads.append(PracticeLead(user_id=uid, role=role))
    db.session.commit()


def test_sign_up_adds_refreshes_and_thanks_in_the_thread(env):
    pid = env["pid"]
    partner, partner_slack = env["user"]("Partner")
    _add(pid, partner)
    uid, slack_uid = env["user"]("Mike")
    assert blocks.sign_up_as_lead(pid, slack_uid) == {"success": True}
    assert _leads(pid) == sorted([(partner, "lead"), (uid, "lead")])
    assert env["refreshes"] == [(pid, {"change_type": "edit", "notify": False})]
    reply = env["client"].chat_postMessage.call_args.kwargs
    assert reply["thread_ts"] == "7.000"
    assert reply["text"] == (f":raised_hands: <@{slack_uid}> is leading Tue 1/20 · 6:15p "
                             f"with <@{partner_slack}>")


def test_first_sign_up_has_no_with(env):
    uid, slack_uid = env["user"]("Solo")
    blocks.sign_up_as_lead(env["pid"], slack_uid)
    assert env["client"].chat_postMessage.call_args.kwargs["text"] == (
        f":raised_hands: <@{slack_uid}> is leading Tue 1/20 · 6:15p")


def test_outside_the_pool_or_unlinked_is_refused(env):
    _, slack_uid = env["user"]("Outsider", in_pool=False)
    for who in (slack_uid, "UNKNOWN-TEST-UID"):
        result = blocks.sign_up_as_lead(env["pid"], who)
        assert result == {"success": False, "error":
                          "Leading is open to the lead pool. Want in? Ask in this thread."}
    assert _leads(env["pid"]) == []
    env["client"].chat_postMessage.assert_not_called()


def test_already_on_it_in_any_role(env):
    uid, slack_uid = env["user"]("Coach")
    _add(env["pid"], uid, role="coach")
    assert blocks.sign_up_as_lead(env["pid"], slack_uid) == {
        "success": False, "error": "You're already on it."}


def test_full_session_is_refused(env):
    pid = env["pid"]
    for name in ("One", "Two"):
        _add(pid, env["user"](name)[0])
    _, slack_uid = env["user"]("Late")
    assert blocks.sign_up_as_lead(pid, slack_uid) == {
        "success": False, "error": "Just filled, thanks!"}


def test_leads_needed_one_fills_with_one(env):
    pid = env["pid"]
    db.session.get(Practice, pid).leads_needed = 1
    db.session.commit()
    _, first = env["user"]("First")
    _, second = env["user"]("Second")
    assert blocks.sign_up_as_lead(pid, first)["success"] is True
    assert blocks.sign_up_as_lead(pid, second)["error"] == "Just filled, thanks!"


def test_cancelled_started_or_gone_is_refused(env, monkeypatch):
    pid = env["pid"]
    _, slack_uid = env["user"]("Eager")
    practice = db.session.get(Practice, pid)
    practice.status = PracticeStatus.CANCELLED.value
    db.session.commit()
    assert blocks.sign_up_as_lead(pid, slack_uid)["error"] == "That practice was cancelled."
    practice = db.session.get(Practice, pid)
    practice.status = PracticeStatus.SCHEDULED.value
    db.session.commit()
    monkeypatch.setattr(blocks, "now_central_naive", lambda: datetime(2099, 1, 20, 18, 15))
    assert blocks.sign_up_as_lead(pid, slack_uid)["error"] == "That practice already started."
    assert blocks.sign_up_as_lead(999999999, slack_uid)["error"] == "That practice is gone."
    assert _leads(pid) == []


def test_a_held_lock_is_refused(env):
    pid = env["pid"]
    _, slack_uid = env["user"]("Racer")
    with db.engine.connect() as other:
        trans = other.begin()
        other.execute(text("SELECT id FROM practices WHERE id = :id FOR UPDATE"), {"id": pid})
        result = blocks.sign_up_as_lead(pid, slack_uid)
        trans.rollback()
    assert result == {"success": False,
                      "error": "Someone just signed up. Try again in a second."}
    assert _leads(pid) == []


def test_failed_thread_reply_keeps_the_sign_up(env):
    env["client"].chat_postMessage.side_effect = RuntimeError("slack down")
    uid, slack_uid = env["user"]("Kept")
    assert blocks.sign_up_as_lead(env["pid"], slack_uid) == {"success": True}
    assert _leads(env["pid"]) == [(uid, "lead")]


def test_no_reply_before_the_schedule_is_posted(env):
    poll = LeadAvailabilityPoll.query.filter_by(starts_on=START).one()
    poll.schedule_ts = None
    db.session.commit()
    _, slack_uid = env["user"]("Early")
    assert blocks.sign_up_as_lead(env["pid"], slack_uid) == {"success": True}
    env["client"].chat_postMessage.assert_not_called()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices/test_lead_signup.py -q`
Expected: FAIL with `AttributeError: module 'app.practices.blocks' has no attribute 'sign_up_as_lead'`.

- [ ] **Step 3: Implement**

In `app/practices/blocks.py`, add after `post_lead_schedule`:

```python
NOT_IN_POOL = "Leading is open to the lead pool. Want in? Ask in this thread."


def _signup_refusal(practice, user_id: int) -> str | None:
    """Why this user can't take this session right now, or None if they can."""
    if practice is None:
        return "That practice is gone."
    if practice.status == PracticeStatus.CANCELLED.value:
        return "That practice was cancelled."
    if practice.date <= now_central_naive():
        return "That practice already started."
    if any(l.user_id == user_id for l in practice.leads):
        return "You're already on it."
    if sum(1 for l in practice.leads if l.role == "lead") >= (practice.leads_needed or 2):
        return "Just filled, thanks!"
    return None


def _post_signup_reply(practice, slack_uid: str, partners) -> None:
    from app.slack.blocks.block_post import join_names

    poll = poll_for_date(practice.date.date())
    if poll is None or not poll.schedule_ts:
        return
    when = practice.date
    text = (f":raised_hands: <@{slack_uid}> is leading {when.strftime('%a %-m/%-d')} · "
            f"{when.strftime('%-I:%M%p').replace('PM', 'p').replace('AM', 'a')}")
    if partners:
        text += f" with {join_names(_mention(u) for u in partners)}"
    try:
        get_slack_client().chat_postMessage(
            channel=COORD_CHANNEL_ID, thread_ts=poll.schedule_ts, text=text)
    except Exception as exc:  # noqa: BLE001 - never raise; the sign-up stands
        current_app.logger.warning("Sign-up reply for practice %s failed: %s", practice.id, exc)


def sign_up_as_lead(practice_id: int, slack_uid: str) -> dict:
    """The Lead button: add the clicker as a lead if the session still needs one.

    The practice row is locked NOWAIT (with populate_existing, see _lock_poll)
    so two clicks on the last spot can't both win.
    """
    from app.models import SlackUser
    from app.practices.models import Practice, PracticeLead
    from app.slack.practices import refresh_practice_posts

    slack = SlackUser.query.filter_by(slack_uid=slack_uid).first()
    user = slack.user if slack else None
    if user is None or user.id not in {u.id for u in eligible_leads()}:
        return {"success": False, "error": NOT_IN_POOL}
    try:
        practice = (Practice.query.filter_by(id=practice_id).populate_existing()
                    .with_for_update(nowait=True).one_or_none())
    except OperationalError:
        db.session.rollback()
        return {"success": False, "error": "Someone just signed up. Try again in a second."}
    refusal = _signup_refusal(practice, user.id)
    if refusal:
        db.session.rollback()
        return {"success": False, "error": refusal}

    partners = [l.user for l in practice.leads if l.role == "lead" and l.user]
    practice.leads.append(PracticeLead(user_id=user.id, role="lead"))
    db.session.commit()
    try:
        refresh_practice_posts(practice, change_type="edit", notify=False)
    except Exception:  # noqa: BLE001 - the sign-up is saved; the next refresh repairs posts
        db.session.rollback()
        current_app.logger.exception("Refresh after sign-up failed for practice %s", practice_id)
    _post_signup_reply(practice, slack_uid, partners)
    return {"success": True}
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/python -m pytest tests/practices/test_lead_signup.py tests/practices/test_blocks.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/practices/blocks.py tests/practices/test_lead_signup.py
git commit -m "Lead button backend: sign_up_as_lead with pool check, row lock and thread reply"
```

---

### Task 4: The Lead button handler

**Files:**
- Modify: `app/slack/bolt_app.py`. Add `import re` at the top, a module-level `LEAD_SIGNUP_ACTION` and `_lead_signup` beside `_save_block_assign`, and a registration beside `handle_block_schedule_post`.
- Create: `tests/slack/test_lead_signup_handler.py`

**Interfaces:**
- Consumes: `sign_up_as_lead(practice_id: int, slack_uid: str) -> dict` (Task 3), and the `lead_signup_{practice_id}` action ids from Task 1.
- Produces: `LEAD_SIGNUP_ACTION: re.Pattern` and `_lead_signup(body, action, client) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/slack/test_lead_signup_handler.py`:

```python
"""The Lead button handler: sign up, or tell the clicker privately why not."""

from contextlib import nullcontext
from unittest.mock import MagicMock

from app.slack import bolt_app

BODY = {"user": {"id": "U0CLICK"}, "channel": {"id": "C0COORD"}}


def test_action_pattern_matches_only_lead_buttons():
    assert bolt_app.LEAD_SIGNUP_ACTION.match("lead_signup_123")
    assert not bolt_app.LEAD_SIGNUP_ACTION.match("lead_signup_")
    assert not bolt_app.LEAD_SIGNUP_ACTION.match("block_schedule_post")


def test_success_is_silent(monkeypatch, app):
    calls = []
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    monkeypatch.setattr("app.practices.blocks.sign_up_as_lead",
                        lambda pid, uid: calls.append((pid, uid)) or {"success": True})
    client = MagicMock()
    bolt_app._lead_signup(BODY, {"value": "42"}, client)
    assert calls == [(42, "U0CLICK")]
    client.chat_postEphemeral.assert_not_called()


def test_refusal_goes_to_the_clicker_privately(monkeypatch, app):
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    monkeypatch.setattr("app.practices.blocks.sign_up_as_lead",
                        lambda pid, uid: {"success": False, "error": "Just filled, thanks!"})
    client = MagicMock()
    bolt_app._lead_signup(BODY, {"value": "42"}, client)
    client.chat_postEphemeral.assert_called_once_with(
        channel="C0COORD", user="U0CLICK", text="Just filled, thanks!")


def test_crash_becomes_a_try_again(monkeypatch, db_session):  # rollback needs an app context
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)

    def boom(pid, uid):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.practices.blocks.sign_up_as_lead", boom)
    client = MagicMock()
    bolt_app._lead_signup(BODY, {"value": "42"}, client)
    assert client.chat_postEphemeral.call_args.kwargs["text"] == (
        "Could not sign you up. Try again.")
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_lead_signup_handler.py -q`
Expected: FAIL with `AttributeError: ... has no attribute 'LEAD_SIGNUP_ACTION'`.

- [ ] **Step 3: Implement**

At the top of `app/slack/bolt_app.py`, add `import re` next to `import os`. Below `_save_block_assign`, add:

```python
LEAD_SIGNUP_ACTION = re.compile(r"^lead_signup_\d+$")


def _lead_signup(body, action, client) -> None:
    """Lead button on the leads' schedule post: sign the clicker up, or say why not."""
    user_id = body["user"]["id"]
    with get_app_context():
        from app.practices import blocks

        try:
            result = blocks.sign_up_as_lead(int(action["value"]), user_id)
        except Exception:
            from app.models import db

            db.session.rollback()
            logger.exception("sign_up_as_lead failed for practice %s", action.get("value"))
            result = {"success": False, "error": "Could not sign you up. Try again."}
    channel = (body.get("channel") or {}).get("id")
    if not result.get("success") and channel:
        client.chat_postEphemeral(channel=channel, user=user_id, text=result["error"])
```

Directly after the `handle_block_schedule_post` handler, register it:

```python
    @bolt_app.action(LEAD_SIGNUP_ACTION)
    def handle_lead_signup(ack, body, action, client, logger):
        ack()
        _lead_signup(body, action, client)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_lead_signup_handler.py tests/slack/test_block_assign_handlers.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/slack/bolt_app.py tests/slack/test_lead_signup_handler.py
git commit -m "Lead button handler: regex action, private refusals"
```

---

### Task 5: Assign keeps self-signups

**Files:**
- Modify: `app/slack/blocks/block_post.py`. Add `import json`, and have `build_assign_modal` write JSON `private_metadata`.
- Modify: `app/slack/bolt_app.py`. Add `import json`, add `_assign_metadata`, and change `_save_block_assign`.
- Modify: `app/practices/blocks.py`. `save_assignment` gains `initial_lead_ids=None`.
- Test: `tests/slack/test_block_post_blocks.py`, `tests/slack/test_block_assign_handlers.py`, `tests/practices/test_blocks.py`

**Interfaces:**
- Consumes: `assign_modal_data()["initial_ids"]` (existing).
- Produces:
  - `save_assignment(practice_id, *, lead_ids, location_id, type_ids, activity_ids, initial_lead_ids=None)`
  - `_assign_metadata(view) -> tuple[int, list[int] | None]`

- [ ] **Step 1: Write the failing tests**

In `tests/slack/test_block_post_blocks.py`, in `test_assign_modal_shows_available_line_and_grouped_dropdown`, replace `assert view["private_metadata"] == "5"` with:

```python
    assert json.loads(view["private_metadata"]) == {"practice_id": 5, "initial_lead_ids": [1]}
```

In `tests/slack/test_block_assign_handlers.py`, add `initial_lead_ids` to the two existing exact-kwargs assertions. Their bare `"5"` metadata reads as a modal opened before the deploy:

```python
    assert saved == [(5, {"lead_ids": [1, 3], "location_id": 7,
                          "type_ids": [11], "activity_ids": [21, 22],
                          "initial_lead_ids": None})]
```

```python
    assert saved == [(5, {"lead_ids": [], "location_id": None,
                          "type_ids": [], "activity_ids": [],
                          "initial_lead_ids": None})]
```

Append to the same file:

```python
def test_json_metadata_passes_the_opening_leads(monkeypatch, app):
    import json

    saved = []
    monkeypatch.setattr("app.practices.blocks.validate_assignment", lambda t, a: None)
    monkeypatch.setattr("app.practices.blocks.save_assignment",
                        lambda pid, **kw: saved.append((pid, kw)))
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    view = {"private_metadata": json.dumps({"practice_id": 5, "initial_lead_ids": [1, 2]}),
            "state": {"values": FULL}}
    bolt_app._save_block_assign(view)
    assert saved[0][0] == 5
    assert saved[0][1]["initial_lead_ids"] == [1, 2]
```

Append to `tests/practices/test_blocks.py`:

```python
def test_save_assignment_keeps_a_lead_added_while_the_modal_was_open(
        db_session, refresh_calls):
    from app.models import User
    from app.practices.models import PracticeLead

    db.session.rollback()
    users = [User(first_name=f"TEST C5 {i}", last_name="Diff",
                  email=f"test-c5-{i}@example.invalid") for i in range(3)]
    db.session.add_all(users)
    db.session.commit()
    a, b, c = [u.id for u in users]
    pid = _practice(20)
    try:
        practice = db.session.get(Practice, pid)
        practice.leads.append(PracticeLead(user_id=a, role="lead"))
        db.session.commit()
        # The modal opens with [a]; then b taps Lead before the director saves.
        db.session.get(Practice, pid).leads.append(PracticeLead(user_id=b, role="lead"))
        db.session.commit()
        blocks.save_assignment(pid, lead_ids=[a, c], location_id=None, type_ids=[],
                               activity_ids=[], initial_lead_ids=[a])
        db.session.expire_all()
        leads = sorted(l.user_id for l in db.session.get(Practice, pid).leads)
        assert leads == sorted([a, b, c])
        # Unchecking removes only who the director unchecked.
        blocks.save_assignment(pid, lead_ids=[b, c], location_id=None, type_ids=[],
                               activity_ids=[], initial_lead_ids=[a, b, c])
        db.session.expire_all()
        assert sorted(l.user_id for l in db.session.get(Practice, pid).leads) == sorted([b, c])
        # Checking someone who is already on it adds no duplicate.
        blocks.save_assignment(pid, lead_ids=[b, c], location_id=None, type_ids=[],
                               activity_ids=[], initial_lead_ids=[c])
        db.session.expire_all()
        assert sorted(l.user_id for l in db.session.get(Practice, pid).leads) == sorted([b, c])
    finally:
        _cleanup([pid])
        db.session.rollback()
        for uid in (a, b, c):
            u = db.session.get(User, uid)
            if u is not None:
                db.session.delete(u)
        db.session.commit()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_blocks.py tests/slack/test_block_assign_handlers.py tests/practices/test_blocks.py -q`
Expected: the metadata, handler and new save tests fail.

- [ ] **Step 3: Implement**

In `app/slack/blocks/block_post.py`, add `import json` at the top. In `build_assign_modal`, change the metadata line to:

```python
        "private_metadata": json.dumps({"practice_id": data["practice_id"],
                                        "initial_lead_ids": data["initial_ids"]}),
```

In `app/slack/bolt_app.py`, add `import json` next to `import os`. Add above `_save_block_assign`:

```python
def _assign_metadata(view) -> tuple[int, list[int] | None]:
    """The practice id and the leads the modal opened with.

    A modal opened before this change carries a bare id: None keeps the old
    replace-all save for it.
    """
    raw = view["private_metadata"]
    if raw.lstrip().startswith("{"):
        meta = json.loads(raw)
        return int(meta["practice_id"]), [int(i) for i in meta.get("initial_lead_ids") or []]
    return int(raw), None
```

In `_save_block_assign`, replace `practice_id = int(view["private_metadata"])` with `practice_id, initial_lead_ids = _assign_metadata(view)`. Replace the final call with:

```python
        blocks.save_assignment(practice_id, initial_lead_ids=initial_lead_ids, **parsed)
```

In `app/practices/blocks.py`, change the `save_assignment` signature and docstring's first line, and replace its two lead loops:

```python
def save_assignment(practice_id: int, *, lead_ids, location_id, type_ids,
                    activity_ids, initial_lead_ids=None) -> None:
    """Save one Assign submission: leads (coaches untouched), location, type, activity.

    With initial_lead_ids (who the modal opened with), only the director's own
    changes apply, so a lead who signed up while the modal was open stays.
    None replaces every lead with lead_ids.
```

Keep the rest of the docstring. Replace

```python
    for lead in [l for l in practice.leads if l.role == "lead"]:
        practice.leads.remove(lead)
    for user_id in dict.fromkeys(lead_ids):
        practice.leads.append(PracticeLead(user_id=user_id, role="lead"))
```

with

```python
    current = [l for l in practice.leads if l.role == "lead"]
    if initial_lead_ids is None:
        remove, add = {l.user_id for l in current}, list(dict.fromkeys(lead_ids))
    else:
        initial = set(initial_lead_ids)
        remove = initial - set(lead_ids)
        add = [u for u in dict.fromkeys(lead_ids) if u not in initial]
    for lead in current:
        if lead.user_id in remove:
            practice.leads.remove(lead)
    have = {l.user_id for l in practice.leads if l.role == "lead"}
    for user_id in add:
        if user_id not in have:
            practice.leads.append(PracticeLead(user_id=user_id, role="lead"))
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/python -m pytest tests/slack/test_block_post_blocks.py tests/slack/test_block_assign_handlers.py tests/practices/test_blocks.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/slack/blocks/block_post.py app/slack/bolt_app.py app/practices/blocks.py \
        tests/slack/test_block_post_blocks.py tests/slack/test_block_assign_handlers.py \
        tests/practices/test_blocks.py
git commit -m "Assign only applies the director's own lead changes, so self-signups survive"
```

---

### Task 6: Verify, preview, ship, switch the live post

**Files:**
- Modify: `/home/node/.claude/skills/lead-availability/SKILL.md` (outside the repo)

- [ ] **Step 1: Full suites**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test timeout 900 /workspace/tcsc-trips/.venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape -p no:warnings` (in the background; it takes about 5 minutes)
Expected: everything passes. Don't copy `.env` into the worktree. `tests/test_ui_audit_session_cookie.py` fails when a real `.env` sits in the repo root.

Run: `npm run -s test:practice-reactions` (symlink `node_modules` from the main checkout first if it's missing)
Expected: `fail 0`.

- [ ] **Step 2: Preview from the real builder**

Run: `/workspace/tcsc-trips/.venv/bin/python scripts/preview_lead_blocks.py schedule`
Expected: two DMs to Rob, "(open sessions)" and "(all covered)". Ask Rob to check them, including that the quote bar is unbroken on his phone. Wait for his OK. Afterwards: `scripts/preview_lead_blocks.py --clean`.

- [ ] **Step 3: Simplify, then the PR**

Run the `simplify` skill on the branch diff. Then push and open the PR:

```bash
git push -u origin lead-schedule-restyle
gh pr create --base main --title "Lead schedule: new look and a Lead button for open sessions" \
  --body-file "$SCRATCHPAD/pr-body.md"
```

First write `pr-body.md` in the session scratchpad. It needs these sections:
- Why: the post went to 60 leads as a data dump, and filling a spot took a director.
- What: weekly quotes, map links, Needs lines, stars, Lead button.
- The Assign fix.
- No migration.
- The test counts from Step 1.
- After deploy: refresh poll 1.
End it with the PR attribution line from the session's system reminder. Merge with `gh pr merge --squash` only after Rob OKs the preview. The merge deploys.

- [ ] **Step 4: After the deploy is live, switch the Oct 12-25 post**

Wait for Render deploy status `live` (service `srv-csgsnvbqf0us739q2kpg`). Poll 1 is closed, so it gets no 8:00 redraw. Refresh it once with the one-off pattern (`TCSC_MIGRATION_ONLY=1`, `SLACK_APP_TOKEN` unset, prod `DATABASE_URL` with `sslmode=require`), calling `blocks.refresh_block_post(poll)` for poll 1, from a checkout of the merged main.
Expected: `refreshed: True`. Then `conversations.history` on C02J4DGCFL2 at ts `1791556988.990059` shows the `:ski:` header. If Thu 10/15 6:05p still has fewer than 2 leads and hasn't started, it also shows an actions block with `lead_signup_122`.

- [ ] **Step 5: Wrap up**

- In the `lead-availability` skill, describe the new post (weekly quotes, Lead button, `sign_up_as_lead`, the Assign diff, "subs are community-run in the thread"), and update the project memory file.
- Remove the worktree: `git worktree remove .worktrees/lead-schedule-restyle && git worktree prune`.
- Offer Rob to delete the design samples in his DM (`send.py --clean` in the session scratchpad).
