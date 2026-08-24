"""Daily season registration recap for the leadership channel.

Rendering is pure (stats dict in, Block Kit out). Posting never raises,
same contract as app/slack/trips.py: the scheduler job must not die
because Slack did. Copy style: no em dashes.

Layout (mobile first): the header carries the one number that matters,
yesterday's count (or the season total once every window has closed and
the tail posts are about the tally settling). A context line under it
names the season and date. Yesterday's news, highlights, Get Involved
answers, and the needs-review warning sit above the single divider;
season state (totals, prior-season pace, windows) sits below it.
Needs-review is the only :warning: and stays above the divider so it
can't be missed.
"""
import os

from flask import current_app

from app.slack.client import get_channel_id_by_name, get_slack_client

CHANNEL_NAME = "leadership-registration"


def _base_url():
    return os.environ.get('EXTERNAL_BASE_URL', 'https://tcsc.ski').rstrip('/')


def _escape(text):
    """Slack mrkdwn escaping for interpolated labels."""
    return (str(text).replace('&', '&amp;')
            .replace('<', '&lt;').replace('>', '&gt;'))


def _section(text):
    return {"type": "section",
            "text": {"type": "mrkdwn", "text": text}}


def _fields_section(fields):
    return {"type": "section",
            "fields": [{"type": "mrkdwn", "text": f} for f in fields]}


def _context(elements):
    return {"type": "context",
            "elements": [{"type": "mrkdwn", "text": e} for e in elements]}


def _plural(count, noun="registration"):
    return f"{count} {noun}" + ("" if count == 1 else "s")


def _fmt_date(d):
    return d.strftime('%b %-d')


def _is_closed(stats):
    """True once every configured window has fully passed: the tail
    period where the post exists so leadership sees the tally settle."""
    windows = [w for w in stats["windows"].values() if w]
    return bool(windows) and all(
        not w["is_open"] and stats["for_date"] > w["end"] for w in windows)


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
    """Pace against the prior season, with the comparison already done
    so the reader isn't left to subtract at 8am."""
    prior = stats["prior_season"]
    if not prior:
        return None
    total = stats["season_totals"]["total"]
    then = prior["count_at_same_point"]
    name = _escape(prior["name"])
    if total > then:
        lead = f"Ahead of {name}"
    elif total < then:
        lead = f"Behind {name}"
    else:
        lead = f"Even with {name}"
    return (f"{lead}: {then} at this point, "
            f"{prior['final_count']} at the finish.")


def _volunteer_text(stats):
    v = stats["volunteer"]
    if not v["answered"]:
        return None
    parts = [f"{_escape(label)} ({count})"
             for label, count in v["interests"].items()]
    text = (f"*Get Involved*\n{v['answered']} of {v['of']} opted in: "
            + ", ".join(parts) + ".")
    if v["committees"]:
        committee_parts = [f"{_escape(label)} ({count})"
                           for label, count in v["committees"].items()]
        text += "\nCommittees: " + ", ".join(committee_parts) + "."
    return text


def build_recap_blocks(stats):
    """Returns (blocks, fallback_text) for chat_postMessage."""
    date_label = stats["for_date"].strftime('%A, %b %-d')

    if _is_closed(stats):
        # Tail period: the news is the settling total, not the daily zero.
        header_text = f"{_plural(stats['season_totals']['total'])} this season"
        if stats["yesterday"]["total"] > 0:
            lead = _yesterday_line(stats)
        else:
            lead = "Registration is closed. 0 yesterday."
    else:
        header_text = f"{_plural(stats['yesterday']['total'])} yesterday"
        lead = _yesterday_line(stats)

    blocks = [
        {"type": "header",
         "text": {"type": "plain_text", "text": header_text}},
        _context([f"{_escape(stats['season_name'])} · {date_label}"]),
        _section(lead),
    ]

    if stats["highlights"]:
        # One mrkdwn element: context elements flow inline, but newlines
        # inside a single element stack. One :sparkles: marks the zone.
        blocks.append(_context(
            [":sparkles: " + "\n".join(stats["highlights"])]))

    volunteer = _volunteer_text(stats)
    if volunteer:
        blocks.append(_section(volunteer))

    if stats["needs_review"]:
        url = (f"{_base_url()}/admin/registration-review"
               f"?season_id={stats['season_id']}")
        n = stats["needs_review"]
        verb = "needs" if n == 1 else "need"
        blocks.append(_section(
            f":warning: *{_plural(n)} {verb} review "
            f"before the lottery.* <{url}|Open review page>"))

    blocks.append({"type": "divider"})
    blocks.append(_fields_section(_season_fields(stats)))

    prior = _prior_line(stats)
    if prior:
        blocks.append(_context([prior]))

    window_fields = _window_fields(stats)
    if window_fields:
        blocks.append(_fields_section(window_fields))

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
