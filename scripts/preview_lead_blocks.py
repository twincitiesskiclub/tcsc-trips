"""DM Rob every lead-availability v2 surface, from the real builders.

    python scripts/preview_lead_blocks.py           # post
    python scripts/preview_lead_blocks.py --clean   # delete what it posted

Pure builders only: no database, no Flask app context.
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values  # noqa: E402
from slack_sdk import WebClient  # noqa: E402

from app.practices.interfaces import (  # noqa: E402
    LeadRole,
    PracticeInfo,
    PracticeLeadInfo,
    PracticeStatus,
)
from app.slack.blocks.availability import build_nudge_blocks, build_poll_blocks  # noqa: E402
from app.slack.blocks.block_post import build_assign_modal, build_block_post  # noqa: E402
from app.slack.blocks.coach_review import build_coach_weekly_summary_blocks  # noqa: E402

ROB = "U02JS0R7ZG8"
STATE = ROOT / "scripts" / "output" / "preview_lead_blocks_ts.json"
DONE = "white_check_mark"  # passed explicitly so no config or app context is read
client = WebClient(token=dotenv_values(ROOT / ".env")["SLACK_BOT_TOKEN"])

S, E = date(2026, 10, 26), date(2026, 11, 8)
BAL = "Balance Fitness Studio · Strength"
ROWS = [
    ("letter_a", datetime(2026, 10, 27, 18, 15), "Theodore Wirth · Bounding", ["Katrin S"], [], 2),
    ("letter_b", datetime(2026, 10, 29, 18, 5), BAL, ["Ellie T"], ["KJ"], 1),
    ("letter_c", datetime(2026, 10, 29, 19, 20), BAL, [], [], 0),
    ("letter_d", datetime(2026, 11, 3, 18, 15), "location TBD", [], [], 1),
    ("letter_e", datetime(2026, 11, 5, 18, 5), BAL, ["Jacob D", "Dana P"], [], 0),
    ("letter_f", datetime(2026, 11, 5, 19, 20), BAL, [], [], 2),
]
# Added after the poll opened: the letter appends, nothing above it moves.
LATE = ("letter_g", datetime(2026, 11, 7, 9, 0), "Theodore Wirth · Skate", [], [], 0)


def rows(with_letters=True, items=ROWS):
    return [{"practice_id": i + 1, "emoji": e if with_letters else None, "when": w, "where": wh,
             "cancelled": False, "leads": l, "coaches": c, "leads_needed": 2, "available": a}
            for i, (e, w, wh, l, c, a) in enumerate(items)]


def poll(status, message_ts=None, opened_by=None, closed_at=None):
    return SimpleNamespace(id=0, starts_on=S, ends_on=E, status=status, message_ts=message_ts,
                           opened_by_slack_uid=opened_by, opened_at=None, closed_at=closed_at)


def label(text):
    return {"type": "context", "elements": [{"type": "mrkdwn",
            "text": f":construction: *DEMO* · {text} · example data, buttons do nothing here"}]}


def hidden_practice():
    lead = lambda role: PracticeLeadInfo(  # noqa: E731
        id=1, practice_id=1, user_id=1, display_name="Katrin S",
        slack_user_id="U0TEST", role=role)
    when = datetime(2026, 10, 27, 18, 15)
    return PracticeInfo(
        id=1, date=when, day_of_week=when.strftime("%A"), status=PracticeStatus.SCHEDULED,
        leads=[lead(LeadRole.LEAD), lead(LeadRole.COACH)],
        is_draft=True, missing_details=["location"])


def leads_poll_rows(items):
    out = []
    for e, w, wh, *_ in items:
        where, _, kind = wh.partition(" · ")
        out.append({"emoji": e, "date": w,
                    "location": "Location TBD" if "TBD" in where else where,
                    "kind": kind or "Practice",
                    "week_label": f"Week of {'Oct 26' if w.day >= 26 and w.month == 10 else 'Nov 2'}"})
    return out


ADMIN_NOTE = (
    "*Admin page changes* (/admin/practices)\n"
    "• The practices list shows \"Hidden · needs location\" on hidden practices, and the drawer "
    "explains what keeps one hidden.\n"
    "• There are no publish buttons. A practice appears to members once it has a location and a "
    "type or activity.\n"
    "• The date-range poll form is replaced by a \"Run block job now\" button.\n"
    "• Each block shows a card: Open poll while it has not been opened, or \"Assign only\" "
    "for the Oct 12–25 block."
)


def surfaces():
    yield "block post, before opening", build_block_post(poll("draft"), rows(), permalink=None, footer=None)
    yield "block post, open", build_block_post(
        poll("open", "1.0", "U0555FLT01E"), rows(), permalink="https://slack.com",
        footer="31 of 60 leads have answered. Reminders go to the rest Thu, Sat and Mon.")
    yield "block post, closed", build_block_post(
        poll("closed", "1.0", closed_at=datetime(2026, 11, 9, 8, 30)), rows(), permalink=None, footer=None)
    yield "Oct 12-25 assignment post (no poll)", build_block_post(
        poll("closed"), rows(with_letters=False), permalink=None, footer=None)
    modal = build_assign_modal({
        "practice_id": 1, "title": "Assign leads · Tue 10/27",
        "detail": "6:15p · Theodore Wirth · Bounding · needs 2",
        "available_text": "Available: Katrin S, Micah R, Dana P",
        "available": [(1, "Katrin S"), (2, "Micah R"), (3, "Dana P")],
        "others": [(4, "Augie L"), (5, "Chris F")], "initial_ids": [1]})
    # Slack rejects input blocks in a message, so show the modal's text and list its select.
    shown = [b for b in modal["blocks"] if b["type"] != "input"]
    groups = modal["blocks"][-1]["element"]["option_groups"]
    shown.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Leads dropdown* (multi-select, Katrin S preselected)\n" + "\n".join(
        f"_{g['label']['text']}_: " + ", ".join(o["text"]["text"] for o in g["options"]) for g in groups)}})
    yield "Assign modal (shown as a message, the real one opens from Assign)", shown
    yield "leads poll in #coord-practices-leads-assists", build_poll_blocks(
        leads_poll_rows(ROWS + [LATE]), "October 26", "Nov 8", done=DONE)
    yield "nudge DM to a lead", build_nudge_blocks("Oct 26", "Nov 8", "C02J4DGCFL2",
                                                    "https://slack.com", done=DONE)
    yield "Sunday coach summary (hidden practice, Open poll)", build_coach_weekly_summary_blocks(
        [hidden_practice()], [{"day": "tuesday", "time": "18:15", "active": True}],
        datetime(2026, 10, 26), open_poll_id=1)
    yield "admin page changes", [{"type": "section", "text": {"type": "mrkdwn", "text": ADMIN_NOTE}}]


def post():
    dm = client.conversations_open(users=ROB)["channel"]["id"]
    posted = []
    try:
        for title, blocks in surfaces():
            resp = client.chat_postMessage(channel=dm, blocks=[label(title)] + blocks[:49],
                                           text=f"Demo: {title}")
            posted.append(resp["ts"])
            print(f"ok  {title}")
    finally:
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text(json.dumps({"channel": dm, "ts": posted}))
    print(f"posted {len(posted)} to {dm}")


def clean():
    data = json.loads(STATE.read_text())
    for ts in data["ts"]:
        client.chat_delete(channel=data["channel"], ts=ts)
    STATE.unlink()
    print(f"deleted {len(data['ts'])}")


if __name__ == "__main__":
    clean() if "--clean" in sys.argv else post()
