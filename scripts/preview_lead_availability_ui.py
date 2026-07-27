"""Phase 0 UI preview for the lead availability poll.

Posts static Block Kit renders of every bot-authored surface to a test channel so
the practices directors can review layout on desktop and mobile before any of the
real pipeline is built. Posts nothing to member-facing channels.

Resolved the open emoji risk (see the LETTER constants below): native ordered emoji
sets are inadequate, so the lettered layout depends on custom workspace emoji.

Usage:
    uv run --with slack_sdk --with python-dotenv python scripts/preview_lead_availability_ui.py
    ... --dry-run     print payloads, post nothing
    ... --clean       delete everything this script previously posted
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

load_dotenv(Path(__file__).parent.parent / ".env")

CHANNEL = "C0B3Y71PG92"       # #collab-asset-mgmt-practices (5 members) — preview target
COORD_CHANNEL = "C02J4DGCFL2"  # #coord-practices-leads-assists — referenced in the DM copy
STATE = Path(__file__).parent / "output" / "preview_lead_availability_ts.json"

# Real block from Chris's 2026-07-20 post. Times per the 2026-05-17 / 06-12 notes:
# Tuesdays 6:15p, early lift 6:15p, late lift 7:20p.
SESSIONS = [
    ("a", "Tue 7/21", "6:15p", "Brackett Park", "Multi-sport"),
    ("b", "Thu 7/23", "6:15p", "Balance", "Early Lift"),
    ("c", "Thu 7/23", "7:20p", "Balance", "Late Lift"),
    ("d", "Tue 7/28", "6:15p", "Theo Wirth", "Trail Run"),
    ("e", "Thu 7/30", "6:15p", "Balance", "Early Lift"),
    ("f", "Thu 7/30", "7:20p", "Balance", "Late Lift"),
    ("g", "Tue 8/4", "6:15p", "Hyland", "Rollerski"),
    ("h", "Thu 8/6", "6:15p", "Balance", "Early Lift"),
    ("i", "Thu 8/6", "7:20p", "Balance", "Late Lift"),
    ("j", "Tue 8/11", "6:15p", "Theo Wirth", "Trail run / bounding"),
    ("k", "Thu 8/13", "6:15p", "Balance", "Early Lift"),
    ("l", "Thu 8/13", "7:20p", "Balance", "Late Lift"),
]

# Week boundaries, by index into SESSIONS.
WEEKS = [("Week of Jul 21", 0, 3), ("Week of Jul 28", 3, 6),
         ("Week of Aug 4", 6, 9), ("Week of Aug 11", 9, 12)]

# Phase 0 emoji findings (2026-07-25), all verified against the live API:
#   Native ordered sets are inadequate: :alphabet-white-*: / :alphabet-yellow-*:
#   do not exist, and keycap numbers stop being ordered after :nine:. That is why
#   Chris's hand-written 12-session poll ended in :cactus: and :evergreen_tree:.
#   Rob then uploaded A-Z as CUSTOM workspace emoji named :letter_a: .. :letter_z:
#   (uploaded images, not aliases). Probed 2026-07-25: 26/26 accepted as reactions.
#   Lettered layout is viable.
#
# NOTE: these are custom emoji, not native, so the name is workspace-specific and
# was already renamed once (regional_indicator_* -> letter_*). If they are deleted
# or renamed again, open polls break and stored reaction mappings stop resolving.
# The numbered weekly layout is the fallback. Keep this list in config, not
# hardcoded, when this ships for real.
LETTER = [f":letter_{c}:" for c in "abcdefghijklmnopqrstuvwxyz"]
LETTER_NAMES = [f"letter_{c}" for c in "abcdefghijklmnopqrstuvwxyz"]
NUM = [":one:", ":two:", ":three:", ":four:", ":five:",
       ":six:", ":seven:", ":eight:", ":nine:"]
NUM_NAMES = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
DONE = ":white_check_mark:"


def client() -> WebClient:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        sys.exit("ERROR: SLACK_BOT_TOKEN not set in .env")
    return WebClient(token=token, retry_handlers=[RateLimitErrorRetryHandler(max_retry_count=5)])


def block_poll_blocks() -> list:
    """Surface 1a — one post for the whole block, lettered A..L.

    One letter emoji per line, always followed by whitespace, so the column reads
    as an index against the reaction pill row Slack renders at the bottom.
    """
    blocks = [
        {"type": "header",
         "text": {"type": "plain_text", "text": "Practice Leads July 21 - Aug 13", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": f"React to each session you can lead. · "
                 f"{DONE} when you're done, even if you picked nothing."}]},
    ]
    for label, start, end in WEEKS:
        lines = [f"{LETTER[i]}  *{day}* · {time} · {loc} · _{kind}_"
                 for i, (_, day, time, loc, kind) in enumerate(SESSIONS[start:end], start)]
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                       "text": f"*{label}*\n" + "\n".join(lines)}})
    return blocks


def week_poll_blocks(label: str, start: int, end: int) -> list:
    """Surface 1 — one availability poll per week, numbered 1..n.

    Short list keeps the reaction pill row directly beneath the legend, which is
    emoji's only real weakness: reactions render at the bottom, not beside each line.
    """
    lines = [f"{NUM[i]}  *{day}* · {time} · {loc} · _{kind}_"
             for i, (_, day, time, loc, kind) in enumerate(SESSIONS[start:end])]
    return [
        {"type": "header",
         "text": {"type": "plain_text", "text": f"Practice Leads — {label}", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": f"React to each session you can lead. · "
                 f"{DONE} when you're done, even if you picked nothing."}]},
    ]


def coverage_blocks(state: str) -> list:
    """Surface 2 — the threaded coverage reply, in each of its three states.

    States a need, never a participation statistic: advertising low turnout is a
    documented backfire pattern.
    """
    bodies = {
        "empty": ":red_circle: *Nobody yet* on any of this week's sessions.",
        "partial": (f":red_circle: *Still nobody:* {NUM[2]} Thu 7/23 Late Lift\n"
                    f":large_yellow_circle: *Could use one more:* {NUM[1]} Thu 7/23 Early Lift\n"
                    f":large_green_circle: *Covered:* {NUM[0]} Tue 7/21 Multi-sport"),
        "full": ":large_green_circle: *Every session this week has at least 2 people.* "
                "Thanks all — the practices team takes it from here.",
    }
    return [{"type": "section", "text": {"type": "mrkdwn", "text": bodies[state]}}]


def nudge_blocks(permalink: str | None = None) -> list:
    """Surface 3 — the nudge DM. Sent only to people who have not responded at all.

    The check mark means "I'm done responding", which covers the can't-lead-at-all
    case (picked nothing, done). This DM frames it as the way to stop reminders.
    """
    btn = {"type": "button", "text": {"type": "plain_text", "text": "Go to post", "emoji": True},
           "style": "primary", "action_id": "preview_noop_1"}
    if permalink:
        btn["url"] = permalink
    return [
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": ":envelope: *PREVIEW — this would arrive as a DM, not a channel post*"}]},
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f"Reminder: Provide lead availability for *Jul 21 – Aug 13* "
                 f"in <#{COORD_CHANNEL}>"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": f"To suppress these, if you can't lead at all just hit the {DONE} "
                 "on the post there."}]},
        {"type": "actions", "elements": [btn]},
    ]


def digest_blocks() -> list:
    """Surface 4 — the monthly readiness digest to coaches and directors."""
    return [
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": ":calendar: *PREVIEW — this would post to #coord-coaches-practices*"}]},
        {"type": "header", "text": {"type": "plain_text",
         "text": "12 practices drafted · Jul 21 – Aug 13", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn",
         "text": "*8 of 12 ready* · 4 still need details. "
                 "The availability poll unlocks once all 12 are set."}},
        {"type": "section", "text": {"type": "mrkdwn",
         "text": ":red_circle: *Tue 8/11* · 6:15p — _no location, no type_\n"
                 ":red_circle: *Thu 8/13* · 6:15p — _no type_\n"
                 ":red_circle: *Thu 8/13* · 7:20p — _no type_\n"
                 ":red_circle: *Tue 8/4* · 6:15p — _no location_"},
         "accessory": {"type": "button", "text": {"type": "plain_text", "text": "Fill in details", "emoji": True},
                       "style": "primary", "action_id": "preview_noop_3"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": ":bulb: Leads pick their availability from location, type and time — "
                 "so these four are what's blocking the poll."}]},
    ]


def _permalink(c, ts):
    try:
        return c.chat_getPermalink(channel=CHANNEL, message_ts=ts)["permalink"]
    except SlackApiError:
        return None


def _post_tail(c, posted, permalink=None):
    """Nudge DM + readiness digest, shared by both layouts."""
    for name, blocks, fallback in (("nudge DM", nudge_blocks(permalink), "Nudge DM preview"),
                                   ("readiness digest", digest_blocks(), "Readiness digest preview")):
        r = c.chat_postMessage(channel=CHANNEL, blocks=blocks, text=fallback)
        posted.append(r["ts"]); print(f"Posted {name}: {r['ts']}")
    STATE.write_text(json.dumps(posted))
    print(f"\nRecorded {len(posted)} messages → {STATE}")
    print("Re-run with --clean to remove them all.")
    print("\nReview on desktop AND mobile: does the emoji column line up against the "
          "reaction pill row, and is the legend readable at a glance?")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--layout", choices=["block-letters", "week-numbers"],
                    default="block-letters",
                    help="block-letters: one post, A..L. week-numbers: one post per week, 1..n.")
    args = ap.parse_args()
    c = client()
    STATE.parent.mkdir(parents=True, exist_ok=True)

    if args.clean:
        if not STATE.exists():
            sys.exit("Nothing recorded to clean.")
        for ts in json.loads(STATE.read_text()):
            try:
                c.chat_delete(channel=CHANNEL, ts=ts)
                print(f"  deleted {ts}")
            except SlackApiError as e:
                print(f"  could not delete {ts}: {e.response.get('error')}")
        STATE.unlink()
        return

    if args.dry_run:
        if args.layout == "block-letters":
            print(f"\n===== poll: lettered block =====\n{json.dumps(block_poll_blocks(), indent=2)}")
        else:
            for label, s, e in WEEKS:
                print(f"\n===== poll: {label} =====\n{json.dumps(week_poll_blocks(label, s, e), indent=2)}")
        for name, b in (("coverage/empty", coverage_blocks("empty")),
                        ("coverage/partial", coverage_blocks("partial")),
                        ("coverage/full", coverage_blocks("full")),
                        ("nudge DM", nudge_blocks()), ("readiness digest", digest_blocks())):
            print(f"\n===== {name} =====\n{json.dumps(b, indent=2)}")
        return

    posted = []

    if args.layout == "block-letters":
        r = c.chat_postMessage(channel=CHANNEL, blocks=block_poll_blocks(),
                               text="Who can lead? Jul 21 – Aug 13 (UI preview)")
        posted.append(r["ts"])
        for i in range(len(SESSIONS)):
            try:
                c.reactions_add(channel=CHANNEL, timestamp=r["ts"], name=LETTER_NAMES[i])
            except SlackApiError as e:
                print(f"  :{LETTER_NAMES[i]}: FAILED — {e.response.get('error')}")
        try:
            c.reactions_add(channel=CHANNEL, timestamp=r["ts"], name="white_check_mark")
        except SlackApiError:
            pass
        print(f"Posted lettered block poll: {r['ts']}  ({len(SESSIONS)} sessions)")
        # Coverage thread replies deferred — not previewed for now.
        _post_tail(c, posted, _permalink(c, r["ts"]))
        return

    # One poll per week. Seed reactions so the pill row renders realistically.
    first_ts = None
    for label, start, end in WEEKS:
        r = c.chat_postMessage(channel=CHANNEL, blocks=week_poll_blocks(label, start, end),
                               text=f"Practice Leads — {label} (UI preview)")
        posted.append(r["ts"])
        first_ts = first_ts or r["ts"]
        for i in range(end - start):
            try:
                c.reactions_add(channel=CHANNEL, timestamp=r["ts"], name=NUM_NAMES[i])
            except SlackApiError as e:
                print(f"  {label} :{NUM_NAMES[i]}: FAILED — {e.response.get('error')}")
        print(f"Posted poll [{label}]: {r['ts']}  ({end - start} sessions)")

    # Coverage thread replies deferred — not previewed for now.
    _post_tail(c, posted, _permalink(c, first_ts))


if __name__ == "__main__":
    main()
