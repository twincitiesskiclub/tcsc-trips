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
