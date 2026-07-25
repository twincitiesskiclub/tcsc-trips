# Practices Transition Document Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract 2.5 years of Slack channel history from two practices team channels, then use chunked Opus agents (per-month → per-season → final synthesis) to produce a concise transition document.

**Architecture:** A standalone Python script extracts messages from Slack and writes per-month chat log files. Then Claude Code agents are spawned in stages — per-month extraction summaries, per-season synthesis, final document — each reading the previous stage's output.

**Tech Stack:** `slack_sdk`, `python-dotenv`, Claude Code Agent tool (Opus)

---

### Task 1: Create the extraction script

**Files:**
- Create: `scripts/extract_channel_history.py`

This script pulls all messages from two Slack channels since Oct 1 2023, resolves user names, fetches threads, and writes per-month `.txt` chat logs to `scripts/output/`.

- [ ] **Step 1: Create the script file**

```python
"""Extract Slack channel history to per-month chat log files.

Standalone script — no Flask dependency. Reads SLACK_BOT_TOKEN from .env.

Usage: python scripts/extract_channel_history.py
"""

import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

load_dotenv()

CHANNELS = {
    "C04AUHEDBSR": "internal",
    "C0535SLU7TR": "coaches",
}
OLDEST = datetime(2023, 10, 1, tzinfo=timezone.utc)
OUTPUT_DIR = Path(__file__).parent / "output"

_user_cache: dict[str, str] = {}


def get_client() -> WebClient:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("ERROR: SLACK_BOT_TOKEN not set in .env")
        sys.exit(1)
    handler = RateLimitErrorRetryHandler(max_retry_count=3)
    return WebClient(token=token, retry_handlers=[handler])


def resolve_user(client: WebClient, user_id: str) -> str:
    if user_id in _user_cache:
        return _user_cache[user_id]
    try:
        result = client.users_info(user=user_id)
        profile = result["user"]["profile"]
        name = profile.get("display_name") or profile.get("real_name") or user_id
        _user_cache[user_id] = name
    except SlackApiError:
        _user_cache[user_id] = user_id
    return _user_cache[user_id]


def fetch_thread(client: WebClient, channel_id: str, thread_ts: str) -> list[dict]:
    replies = []
    cursor = None
    while True:
        params = {"channel": channel_id, "ts": thread_ts, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        try:
            result = client.conversations_replies(**params)
        except SlackApiError as e:
            print(f"  Warning: failed to fetch thread {thread_ts}: {e}")
            break
        for msg in result.get("messages", []):
            if msg.get("ts") == thread_ts:
                continue
            replies.append(msg)
        cursor = result.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return replies


def format_message(client: WebClient, msg: dict, channel_label: str, indent: str = "") -> str:
    ts = float(msg["ts"])
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    time_str = dt.strftime("%Y-%m-%d %H:%M")

    user_id = msg.get("user", "")
    if msg.get("bot_id") or msg.get("subtype") == "bot_message":
        name = f"[bot:{msg.get('username', msg.get('bot_id', 'unknown'))}]"
    elif msg.get("subtype"):
        name = f"[system:{msg.get('subtype')}]"
    elif user_id:
        name = resolve_user(client, user_id)
    else:
        name = "[unknown]"

    text = msg.get("text", "")

    attachments = msg.get("files", [])
    if attachments:
        file_names = ", ".join(f.get("name", "file") for f in attachments)
        text += f" [attached: {file_names}]"

    if indent:
        return f"{indent}[thread] {name}: {text}"
    else:
        return f"[{time_str}] #{channel_label} | {name}: {text}"


def fetch_channel(client: WebClient, channel_id: str, channel_label: str) -> list[dict]:
    """Fetch all messages from a channel since OLDEST. Returns raw message dicts with channel_label attached."""
    messages = []
    cursor = None
    oldest_ts = str(OLDEST.timestamp())
    page = 0

    while True:
        params = {"channel": channel_id, "oldest": oldest_ts, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        try:
            result = client.conversations_history(**params)
        except SlackApiError as e:
            print(f"ERROR: Cannot read channel {channel_id}: {e}")
            if "not_in_channel" in str(e):
                print(f"  Bot is not a member of {channel_id}. Invite it first.")
            sys.exit(1)

        for msg in result.get("messages", []):
            msg["_channel_label"] = channel_label
            msg["_channel_id"] = channel_id
            messages.append(msg)

        page += 1
        count = len(messages)
        print(f"  #{channel_label}: fetched page {page} ({count} messages so far)")

        cursor = result.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    return messages


def month_key(msg: dict) -> str:
    ts = float(msg["ts"])
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m")


def main():
    client = get_client()

    print("Fetching channel history...")
    all_messages = []
    for channel_id, label in CHANNELS.items():
        print(f"  Channel: {channel_id} ({label})")
        msgs = fetch_channel(client, channel_id, label)
        all_messages.extend(msgs)
    print(f"Total messages: {len(all_messages)}")

    print("Resolving user names and threads...")
    by_month: dict[str, list[str]] = defaultdict(list)

    all_messages.sort(key=lambda m: float(m["ts"]))

    for i, msg in enumerate(all_messages):
        if i % 100 == 0 and i > 0:
            print(f"  Processing message {i}/{len(all_messages)}")

        mk = month_key(msg)
        channel_label = msg["_channel_label"]
        channel_id = msg["_channel_id"]

        line = format_message(client, msg, channel_label)
        by_month[mk].append(line)

        if msg.get("reply_count", 0) > 0:
            replies = fetch_thread(client, channel_id, msg["ts"])
            for reply in replies:
                reply_line = format_message(client, reply, channel_label, indent="  ")
                by_month[mk].append(reply_line)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for mk in sorted(by_month.keys()):
        filepath = OUTPUT_DIR / f"{mk}.txt"
        with open(filepath, "w") as f:
            f.write("\n".join(by_month[mk]))
        print(f"  Wrote {filepath} ({len(by_month[mk])} lines)")

    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

```bash
cd /Users/rob/env/tcsc-trips
source env/bin/activate
python scripts/extract_channel_history.py
```

Expected: Script prints progress as it fetches pages, resolves users, and writes per-month `.txt` files into `scripts/output/`. Verify by checking a few output files:

```bash
ls -la scripts/output/*.txt
head -20 scripts/output/2023-10.txt
```

- [ ] **Step 3: Commit the script**

```bash
git add scripts/extract_channel_history.py
git commit -m "feat: add Slack channel history extraction script for practices transition"
```

Do NOT commit the output files — they contain Slack message content.

---

### Task 2: Run per-month analysis agents

**Files:**
- Read: `scripts/output/YYYY-MM.txt` (one per month)
- Create: `scripts/output/summaries/YYYY-MM_summary.md` (one per month, written by agents)

Spawn Opus agents to analyze each month's chat log. Run in parallel batches (3-4 at a time to avoid overwhelming the system).

- [ ] **Step 1: Create summaries directory**

```bash
mkdir -p scripts/output/summaries
```

- [ ] **Step 2: Spawn per-month agents**

For each `.txt` file in `scripts/output/`, spawn an Agent with this prompt template (substitute the month and file path):

```
You are analyzing Slack chat logs from the TCSC (Twin Cities Ski Club) practices
leadership team for {MONTH_LABEL} (e.g., "October 2023").

Read the file at: scripts/output/{YYYY-MM}.txt

This file contains messages from two Slack channels:
- #internal — private coordination between Rob, Simon, and Augie (the practices leadership trio)
- #coaches — collaboration between the trio and coaches (KJ, Greg, Rebecca, Michael)

Your job: Extract a structured summary focusing on the TRIO's roles and responsibilities.
Do NOT document what the coaches do — only reference coaches for context on how the trio
coordinates with them.

Write the summary to: scripts/output/summaries/{YYYY-MM}_summary.md

Use this structure:

# {Month Year} Summary

## Key Activities
- What happened this month? Major events, decisions, milestones.

## Rob's Contributions
- Specific tasks, decisions, actions Rob took this month.

## Simon's Contributions
- Specific tasks, decisions, actions Simon took this month.

## Augie's Contributions
- Specific tasks, decisions, actions Augie took this month.

## Recurring Responsibilities Observed
- Any repeating tasks or patterns visible this month.

## Coach Coordination
- How the trio communicated with coaches. What was delegated vs. decided by the trio.

## Notable Context
- Anything a successor should know. Lessons learned, surprises, institutional knowledge.

Be specific. Cite dates and quote messages where they reveal important context.
If a month is quiet with few messages, keep the summary short — don't invent substance.
```

Run agents in parallel batches of 3-4. Each agent is independent.

- [ ] **Step 3: Verify summaries were written**

```bash
ls -la scripts/output/summaries/*_summary.md
```

Spot-check 2-3 summaries to confirm they have substance and follow the structure.

---

### Task 3: Run per-season synthesis agents

**Files:**
- Read: `scripts/output/summaries/YYYY-MM_summary.md` (monthly summaries)
- Create: `scripts/output/summaries/season_*.md` (one per season, written by agents)

Season definitions:
| Season | Months |
|--------|--------|
| Fall/Winter 2023-24 | 2023-10, 2023-11, 2023-12, 2024-01, 2024-02, 2024-03 |
| Spring/Summer 2024 | 2024-04, 2024-05, 2024-06, 2024-07, 2024-08 |
| Fall/Winter 2024-25 | 2024-09, 2024-10, 2024-11, 2024-12, 2025-01, 2025-02, 2025-03 |
| Spring/Summer 2025 | 2025-04, 2025-05, 2025-06, 2025-07, 2025-08 |
| Fall/Winter 2025-26 | 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-02, 2026-03 |
| Spring/Summer 2026 | 2026-04 |

- [ ] **Step 1: Spawn per-season agents**

For each season, spawn an Agent with this prompt (substitute season label and file list):

```
You are synthesizing monthly summaries from the TCSC practices leadership team
for the {SEASON_LABEL} season (e.g., "Fall/Winter 2023-24").

Read these monthly summary files:
{LIST_OF_FILES}

These summaries document what Rob, Simon, and Augie did each month — their roles,
recurring responsibilities, decisions, and coordination with coaches (KJ, Greg, Rebecca, Michael).

Your job: Produce a season-level synthesis that captures patterns across the months.

Write the output to: scripts/output/summaries/season_{FILENAME_SLUG}.md

Use this structure:

# {SEASON_LABEL} Season Summary

## Season Overview
- 2-3 sentence summary of what this season looked like for the practices team.

## Role Division
- How did Rob, Simon, and Augie divide responsibilities this season?
- Who owned what? Were there clear lanes or was it fluid?

## Key Workflows & Processes
- What recurring workflows were active this season?
- Weekly rhythms, seasonal setup/teardown, coach coordination cadence.

## Evolution & Changes
- What changed compared to the previous season (if applicable)?
- New processes introduced, responsibilities shifted, tools adopted.

## Institutional Knowledge
- Lessons learned, things that worked or didn't, context a successor needs.

Be concise. This will be read by another agent that synthesizes all seasons into
a final transition document — focus on patterns and insights, not exhaustive detail.
```

Run all 6 in parallel — they're independent.

- [ ] **Step 2: Verify season summaries**

```bash
ls -la scripts/output/summaries/season_*.md
```

Spot-check 1-2 to confirm quality.

---

### Task 4: Run final synthesis agent

**Files:**
- Read: `scripts/output/summaries/season_*.md` (6 season summaries)
- Create: `scripts/output/practices_transition_doc.md`

- [ ] **Step 1: Spawn the synthesis agent**

Spawn a single Opus agent with this prompt:

```
You are writing a transition document for the TCSC (Twin Cities Ski Club) practices
leadership team. Rob, Simon, and Augie are shifting into other roles on the team/board,
and this document captures what they did, how things work, and what successors need to know.

Read all season summary files:
- scripts/output/summaries/season_fall_winter_2023_24.md
- scripts/output/summaries/season_spring_summer_2024.md
- scripts/output/summaries/season_fall_winter_2024_25.md
- scripts/output/summaries/season_spring_summer_2025.md
- scripts/output/summaries/season_fall_winter_2025_26.md
- scripts/output/summaries/season_spring_summer_2026.md

Synthesize everything into a single transition document.

Write the output to: scripts/output/practices_transition_doc.md

Use this structure:

# TCSC Practices Team — Transition Document

## Overview
What the practices team does, who's on it, why this doc exists. 2-3 sentences max.

## Roles & Ownership
Per-person section for Rob, Simon, Augie. What each person owns/owned, their strengths,
their typical contributions. Not rigid job descriptions — more "here's how we naturally
divided things." Note how roles evolved over time.

## Recurring Workflows
- Seasonal calendar: what happens when (season kickoff, weekly practice cycle, wind-down)
- Weekly cycle: scheduling, announcements, coach coordination, cancellation decisions
- How-to for key processes (creating practices, handling weather cancellations, sub requests)

## Coach Coordination
How the trio works with coaches (KJ, Greg, Rebecca, Michael). Communication patterns,
expectations, typical asks. What coaches handle themselves vs. what needs practices team input.

## Tools & Systems
Slack channels, the web app, Skipper AI, any other tools used. What's automated vs. manual.

## Institutional Knowledge
Things that aren't written down anywhere else. Gotchas, lessons learned,
"we tried X and it didn't work." Relationships and context that matter.

## Recommendations for Successors
What to keep, what to change, what to watch out for.

CRITICAL GUIDELINES:
- Target length: 1500-2500 words (3-5 pages). Be concise and actionable.
- Tone: Conversational and direct — written as Rob speaking to the team. Not corporate.
- Use clear section headings, short paragraphs, and bullet points so teammates
  can easily comment on specific items.
- Every sentence should be something a successor would actually need to know. No fluff.
- If the data doesn't support a section (e.g., no clear recommendations emerged),
  say so briefly rather than inventing content.
```

- [ ] **Step 2: Review the output**

Read `scripts/output/practices_transition_doc.md` and verify:
- Follows the structure above
- Stays within 1500-2500 words
- Tone is conversational, not corporate
- Sections are scannable with clear bullets/headings
- No invented content — everything traces back to actual channel data

---

### Task 5: Add output directory to .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add scripts/output/ to .gitignore**

Add this line to `.gitignore`:

```
scripts/output/
```

This prevents committing Slack message content or intermediate analysis files.

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore scripts/output for channel history extraction"
```
