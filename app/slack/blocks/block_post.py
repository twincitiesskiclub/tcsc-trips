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
    when = poll.opened_at.strftime("%a %-m/%-d") if poll.opened_at else ""
    opener = f"Opened by <@{poll.opened_by_slack_uid}>" if poll.opened_by_slack_uid else "Opened"
    if when:
        opener = f"{opener}, {when}" if poll.opened_by_slack_uid else f"{opener} {when}"
    return f"{opener} · <{permalink}|see the poll>" if permalink else opener


def build_block_post(poll, rows, *, permalink, footer) -> list[dict]:
    if poll.status == "draft":
        return _before_opening(poll, rows)
    blocks = [_header(poll), _context(_status_line(poll, permalink))]
    blocks.extend(_row_section(r) for r in rows[:40])
    if footer and poll.status == "open":
        blocks.append(_context(footer))
    return blocks


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
        "private_metadata": str(data["practice_id"]),
        "title": {"type": "plain_text", "text": "Assign leads"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }
