"""Block Kit for the team's block post. Pure functions over plain data."""

import json
from collections import Counter
from datetime import timedelta

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


def _leads_line(row, leads=None) -> str:
    """`leads` overrides the display names, e.g. with Slack mentions."""
    leads = row["leads"] if leads is None else leads
    parts = []
    if row["coaches"]:
        parts.append(f"Coach: {', '.join(row['coaches'])}")
    if leads:
        line = f"Leads: {', '.join(leads)}"
        short = row["leads_needed"] - len(leads)
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
    when = poll.opened_at.strftime("%a %-m/%-d") if poll.opened_at else ""
    opener = f"Opened by <@{poll.opened_by_slack_uid}>" if poll.opened_by_slack_uid else "Opened"
    if when:
        opener = f"{opener}, {when}" if poll.opened_by_slack_uid else f"{opener} {when}"
    return f"{opener} · <{permalink}|see the poll>" if permalink else opener


def _schedule_button(poll) -> dict:
    return {"type": "actions", "elements": [{
        "type": "button", "action_id": "block_schedule_post", "value": str(poll.id),
        "text": {"type": "plain_text", "text": "Post schedule to leads"},
        "confirm": {
            "title": {"type": "plain_text", "text": "Post the schedule?"},
            "text": {"type": "plain_text", "text":
                     "Posts every session and its leads to #coord-practices-leads-assists "
                     "and @mentions each lead. Open sessions get a Lead button anyone in "
                     "the lead pool can take. It updates itself after that."},
            "confirm": {"type": "plain_text", "text": "Post"},
            "deny": {"type": "plain_text", "text": "Cancel"},
        },
    }]}


def build_block_post(poll, rows, *, permalink, footer) -> list[dict]:
    if poll.status == "draft":
        return _before_opening(poll, rows)
    status = _status_line(poll, permalink)
    if poll.schedule_ts:
        status += f" · Schedule posted to <#{COORD_CHANNEL_ID}>"
    blocks = [_header(poll), _context(status)]
    blocks.extend(_row_section(r) for r in rows[:40])
    if footer and poll.status == "open":
        blocks.append(_context(footer))
    if not poll.schedule_ts:
        blocks.append(_schedule_button(poll))
    return blocks


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


MAX_SELECT_OPTIONS = 100


def _option(user_id, name) -> dict:
    return {"text": {"type": "plain_text", "text": name[:75]}, "value": str(user_id)}


def build_assign_modal(data: dict, *, locations=(), all_types=(), all_activities=()) -> dict:
    """The Assign modal: available line, lead dropdown, then location, type, activity.

    Slack selects need at least one option, so an empty list omits its block.
    """
    from app.slack.modals import _build_activity_type_multi_select, _build_location_select

    available = data["available"][:MAX_SELECT_OPTIONS]
    others = data["others"][: MAX_SELECT_OPTIONS - len(available)]
    groups = []
    if available:
        groups.append({"label": {"type": "plain_text", "text": "Available"},
                       "options": [_option(*p) for p in available]})
    if others:
        groups.append({"label": {"type": "plain_text", "text": "Everyone else"},
                       "options": [_option(*p) for p in others]})
    names = dict(available + others)
    select = {"type": "multi_static_select", "action_id": "leads_select",
              "placeholder": {"type": "plain_text", "text": "Choose leads"},
              "option_groups": groups}
    initial = [_option(uid, names[uid]) for uid in data["initial_ids"] if uid in names]
    if initial:
        select["initial_options"] = initial

    blocks = [{"type": "header", "text": {"type": "plain_text", "text": data["title"][:150]}},
              {"type": "context", "elements": [{"type": "mrkdwn", "text": data["detail"]}]}]
    if data["available_text"]:
        blocks.append({"type": "section",
                       "text": {"type": "mrkdwn", "text": data["available_text"]}})
    blocks.append({"type": "input", "block_id": "leads", "optional": True,
                   "label": {"type": "plain_text", "text": "Leads"}, "element": select})
    location = _build_location_select(locations, data.get("location_id"), "location_select")
    extras = [("location", "Location", location)]
    if all_types:
        extras.append(("types", "Type", _build_activity_type_multi_select(
            "type_ids", "Choose types", all_types, data.get("type_ids", []))))
    if all_activities:
        extras.append(("activities", "Activity", _build_activity_type_multi_select(
            "activity_ids", "Choose activities", all_activities, data.get("activity_ids", []))))
    for block_id, label, element in extras:
        if element:
            blocks.append({"type": "input", "block_id": block_id, "optional": True,
                           "label": {"type": "plain_text", "text": label}, "element": element})
    return {
        "type": "modal",
        "callback_id": "block_assign_submit",
        "private_metadata": json.dumps({"practice_id": data["practice_id"],
                                        "initial_lead_ids": data["initial_ids"]}),
        "title": {"type": "plain_text", "text": "Assign leads"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }
