"""Daily season registration recap for the leadership channel.

Rendering is pure (stats dict in, Block Kit out). Posting never raises,
same contract as app/slack/trips.py: the scheduler job must not die
because Slack did. Copy style: no em dashes.

Layout (mobile first): the header carries the one number that matters,
yesterday's count. A context line under it names the season and date.
Everything season-level sits below a divider as short field pairs, with
prior-season pace de-emphasized into a context block. Needs-review is
the only :warning: and stays above the divider so it can't be missed.
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


def _fields_section(fields, text=None):
    block = {"type": "section",
             "fields": [{"type": "mrkdwn", "text": f} for f in fields]}
    if text:
        block["text"] = {"type": "mrkdwn", "text": text}
    return block


def _context(elements):
    return {"type": "context",
            "elements": [{"type": "mrkdwn", "text": e} for e in elements]}


def _plural(count, noun="registration"):
    return f"{count} {noun}" + ("" if count == 1 else "s")


def _fmt_date(d):
    return d.strftime('%b %-d')


def _yesterday_line(stats):
    """Breakdown plus trend, one short line. On a zero day the new and
    returning split is noise, so only the trend renders."""
    y = stats["yesterday"]
    prev = stats["previous_day_total"]
    if y["total"] > prev:
        trend = f"Up from {prev} the day before."
    elif y["total"] < prev:
        trend = f"Down from {prev} the day before."
    else:
        trend = f"Same as the day before ({prev})."
    if y["total"] == 0:
        return trend
    return f"{y['new']} new, {y['returning']} returning. {trend}"


def _season_fields(stats):
    t = stats["season_totals"]
    total = f"*Season total*\n{t['total']}"
    if t["pct_of_limit"] is not None:
        total += f" of {t['registration_limit']} ({t['pct_of_limit']}%)"
    split = f"*New / returning*\n{t['new']} / {t['returning']}"
    return [total, split]


def _window_fields(stats):
    fields = []
    for label, window in (("Returning window", stats["windows"]["returning"]),
                          ("New member window", stats["windows"]["new"])):
        if not window:
            continue
        if window["is_open"]:
            value = (f"Day {window['day_number']} of "
                     f"{window['length_days']}, closes "
                     f"{_fmt_date(window['end'])}")
        elif stats["for_date"] > window["end"]:
            value = f"Closed {_fmt_date(window['end'])}"
        else:
            value = f"Opens {_fmt_date(window['start'])}"
        fields.append(f"*{label}*\n{value}")
    return fields


def _prior_line(stats):
    prior = stats["prior_season"]
    if not prior:
        return None
    return (f"At this point in {prior['name']}: "
            f"{prior['count_at_same_point']}. "
            f"It finished at {prior['final_count']}.")


def _volunteer_text(stats):
    v = stats["volunteer"]
    if not v["answered"]:
        return None
    parts = [f"{label} ({count})" for label, count in v["interests"].items()]
    text = (f"*Get Involved*\n{v['answered']} of {v['of']} opted in: "
            + ", ".join(parts) + ".")
    if v["committees"]:
        committee_parts = [
            f"{label} ({count})" for label, count in v["committees"].items()]
        text += "\nCommittees: " + ", ".join(committee_parts) + "."
    return text


def build_recap_blocks(stats):
    """Returns (blocks, fallback_text) for chat_postMessage."""
    date_label = stats["for_date"].strftime('%A, %b %-d')
    blocks = [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"{_plural(stats['yesterday']['total'])} "
                          "yesterday"}},
        _context([f"{stats['season_name']} · {date_label}"]),
        _section(_yesterday_line(stats)),
    ]

    if stats["highlights"]:
        blocks.append(_context(
            [f":sparkles: {line}" for line in stats["highlights"]]))

    if stats["needs_review"]:
        url = (f"{_base_url()}/admin/registration-review"
               f"?season_id={stats['season_id']}")
        blocks.append(_section(
            f":warning: *{_plural(stats['needs_review'])} need review "
            f"before the lottery.* <{url}|Open review page>"))

    blocks.append({"type": "divider"})
    blocks.append(_fields_section(_season_fields(stats)))

    prior = _prior_line(stats)
    if prior:
        blocks.append(_context([prior]))

    window_fields = _window_fields(stats)
    if window_fields:
        blocks.append(_fields_section(window_fields))

    volunteer = _volunteer_text(stats)
    if volunteer:
        blocks.append(_section(volunteer))

    fallback = (f"Registration recap {date_label}: "
                f"{stats['yesterday']['total']} yesterday, "
                f"{stats['season_totals']['total']} season total.")
    return blocks, fallback


def post_season_recap(stats, channel_override=None):
    """Post the recap. Returns {"success": bool, "error": str|None}."""
    channel_name = (channel_override or CHANNEL_NAME).lstrip('#')
    try:
        channel_id = get_channel_id_by_name(channel_name)
        if not channel_id:
            error = f"channel {channel_name} not found"
            current_app.logger.warning(f"season recap: {error}")
            return {"success": False, "error": error}
        blocks, fallback = build_recap_blocks(stats)
        get_slack_client().chat_postMessage(
            channel=channel_id, blocks=blocks, text=fallback)
        return {"success": True, "error": None}
    except Exception as exc:
        current_app.logger.warning(f"season recap: post failed: {exc}")
        return {"success": False, "error": str(exc)}
