"""Block Kit for the lead availability poll and its nudge DM.

Copy here is approved verbatim from the Phase 0 preview. Do not reword it
without re-previewing — it was revised four times against real Slack renders.
"""

from app.practices.availability_emoji import DONE_EMOJI
from app.slack.blocks.text import BLOCKS_MAX

INSTRUCTION = (
    "React to each session you can lead. · "
    f":{DONE_EMOJI}: when you're done, even if you picked nothing."
)


def _time_label(when) -> str:
    return when.strftime("%-I:%M%p").replace("PM", "p").replace("AM", "a")


def _line(row: dict) -> str:
    """One session. Exactly one letter emoji per line, followed by whitespace.

    The double space after the emoji is load-bearing: two adjacent
    regional-indicator-style emoji can combine into a single flag glyph, so
    each letter emoji must always be followed by whitespace.
    """
    when = row["date"]
    return (
        f":{row['emoji']}:  *{when.strftime('%a %-m/%-d')}* · {_time_label(when)} · "
        f"{row['location']} · _{row['kind']}_"
    )


def build_poll_blocks(rows: list[dict], start_label: str, end_label: str) -> list[dict]:
    """Build the lead-availability poll message.

    One section per week, one line (with a distinct letter emoji) per
    session. No deadline footer -- one was drafted and deliberately cut.

    Slack rejects messages over 50 blocks. If the week groups would push
    past that, later weeks are summarized in a trailing note instead of
    being silently dropped or breaching the cap.
    """
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text",
         "text": f"Practice Leads {start_label} - {end_label}", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": INSTRUCTION}]},
    ]

    week_labels = list(dict.fromkeys(row["week_label"] for row in rows))
    max_weeks_shown = BLOCKS_MAX - len(blocks) - 1  # reserve 1 block for an overflow note
    shown_labels, hidden_labels = week_labels[:max_weeks_shown], week_labels[max_weeks_shown:]

    for label in shown_labels:
        week_rows = [row for row in rows if row["week_label"] == label]
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{label}*\n" + "\n".join(_line(row) for row in week_rows)}})

    if hidden_labels:
        hidden_sessions = sum(1 for row in rows if row["week_label"] in hidden_labels)
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"_+{hidden_sessions} more sessions across {len(hidden_labels)} "
                    "more weeks not shown._"}]})

    return blocks


def poll_fallback_text(rows: list[dict], start_label: str, end_label: str) -> str:
    """Screen readers read only this, never the block contents."""
    return (
        f"Practice Leads {start_label} - {end_label}: {len(rows)} sessions need leads. "
        "React to each session you can lead."
    )


def build_nudge_blocks(start_label: str, end_label: str, channel_id: str,
                        permalink: str | None) -> list[dict]:
    """Build the lead-availability nudge DM.

    A Slack URL button with no `url` is rejected by the API, so when no
    permalink is available the button is omitted entirely.
    """
    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f"Reminder: Provide lead availability for *{start_label} – {end_label}* "
                 f"in <#{channel_id}>"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": "To suppress these, if you can't lead at all just hit the "
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
