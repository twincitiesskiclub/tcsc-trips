# Practices Team Transition Document — Design Spec

**Date:** 2026-04-28
**Goal:** Extract Slack channel history and synthesize a concise transition document capturing the roles, responsibilities, and institutional knowledge of the TCSC practices leadership team (Rob, Simon, Augie) as they shift into other roles.

## Context

Two Slack channels contain 2.5 years of operational history for the practices team:
- **C04AUHEDBSR** — Internal coordination channel (Rob, Simon, Augie)
- **C0535SLU7TR** — Coaches collaboration channel (practices leads + coaches: KJ, Greg, Rebecca, Michael)

The transition doc is for Rob, Simon, Augie, and their successors. It should be easy to comment on and review collaboratively.

## Part 1: Message Extraction Script

### File: `scripts/extract_channel_history.py`

Standalone Python script. No Flask dependency. Reads `SLACK_BOT_TOKEN` from `.env`.

### Behavior

1. Connects to Slack via `slack_sdk.WebClient`
2. Fetches all messages from both channels since **October 1, 2023**
3. For messages with threads (`reply_count > 0`), fetches full thread via `conversations.replies`
4. Resolves user IDs to display names (cached per unique user)
5. Handles pagination (100 messages/page) and rate limiting (auto-retry on 429)

### Output

Per-month plain text chat logs in `scripts/output/`, with messages from **both channels merged chronologically** and tagged by channel:

```
scripts/output/2023-10.txt
scripts/output/2023-11.txt
...
scripts/output/2026-04.txt
```

Format:
```
[2023-11-01 12:00] #internal-channel | Rob: Hey can we move Thursday's practice to Wirth?
  [thread] Simon: Works for me, I'll update the post
  [thread] Augie: Same, I'll let KJ know
[2023-11-01 14:30] #coaches-channel | Rob: @KJ heads up we moved to Wirth Thursday
  [thread] KJ: Got it, thanks
```

### Included content
- All human messages (including from coaches — needed for context)
- Thread replies nested under parent messages
- Bot messages and system messages tagged with `[bot]` or `[system]` for context
- File attachment names noted as `[attached: filename.pdf]`
- Edited messages show latest text (Slack API default)

### Edge cases
- Bot must be a member of both channels — script errors clearly if not
- Deleted messages not available via API — nothing to do
- Empty months produce no file (skip)
- Rate limiting handled by `slack_sdk` retry handler (3 retries with backoff)

## Part 2: Chunked Agent Analysis

### Season definitions

| Season | Date Range |
|--------|-----------|
| Fall/Winter 2023-24 | Oct 2023 – Mar 2024 |
| Spring/Summer 2024 | Apr 2024 – Aug 2024 |
| Fall/Winter 2024-25 | Sep 2024 – Mar 2025 |
| Spring/Summer 2025 | Apr 2025 – Aug 2025 |
| Fall/Winter 2025-26 | Sep 2025 – Mar 2026 |
| Spring/Summer 2026 | Apr 2026 (partial) |

### Stage 1: Per-month agents

One Opus agent per month (or batched for quiet months). Each agent:
- Reads its month's `.txt` file
- Extracts:
  - **Who did what** — specific tasks and actions by Rob, Simon, Augie
  - **Recurring responsibilities** — things that happen regularly
  - **Decisions made** — who decided, what, why
  - **Coach coordination** — how the trio interacts with coaches
  - **Notable context** — anything a successor should know
- Writes summary to `scripts/output/summaries/YYYY-MM_summary.md`
- Parallel execution where possible (independent months)

### Stage 2: Per-season synthesis agents

One agent per season (6 total). Each agent:
- Reads all monthly summaries for its season
- Produces a season-level view:
  - Key responsibilities that season
  - How roles were divided among the trio
  - Seasonal patterns (what's different about fall/winter vs spring/summer)
  - Evolution from previous season (if applicable)
- Writes to `scripts/output/summaries/season_YYYY-YY_type_summary.md`

### Stage 3: Final synthesis agent

Reads all 6 season summaries. Produces the transition document.

## Part 3: Transition Document Output

### File: `scripts/output/practices_transition_doc.md`

### Structure

Standard transition document format, adapted for TCSC practices:

1. **Overview** — What the practices team does, who's on it, why this doc exists (2-3 sentences)

2. **Roles & Ownership**
   - Per-person section for Rob, Simon, Augie
   - What each person owns/owned, their strengths, their typical contributions
   - Not rigid job descriptions — more "here's how we naturally divided things"

3. **Recurring Workflows**
   - Seasonal calendar: what happens when (season kickoff, weekly practice cycle, wind-down)
   - Weekly cycle: scheduling, announcements, coach coordination, cancellation decisions
   - How-to for key processes (creating practices, handling weather cancellations, sub requests)

4. **Coach Coordination**
   - How the trio works with coaches (KJ, Greg, Rebecca, Michael)
   - Communication patterns, expectations, typical asks
   - What coaches handle themselves vs. what needs practices team input

5. **Tools & Systems**
   - Slack channels, the web app, Skipper AI, any other tools
   - What's automated vs. manual

6. **Institutional Knowledge**
   - Things that aren't written down anywhere else
   - Gotchas, lessons learned, "we tried X and it didn't work"
   - Relationships and context that matter

7. **Recommendations for Successors**
   - What to keep, what to change, what to watch out for

### Tone & length
- **Target length:** 3-5 pages (roughly 1500-2500 words)
- **Tone:** Conversational, direct — written as Rob speaking to the team, not a corporate document
- **Commentable:** Clear section headings, short paragraphs, bullet points where appropriate so people can easily point to specific items and add comments
- **No fluff:** Every sentence should be something a successor would actually need to know

## Dependencies

- `slack_sdk` (already in `requirements.txt`)
- `python-dotenv` (for reading `.env` without Flask)
- `SLACK_BOT_TOKEN` (configured in `.env`)
- Bot must be a member of both channels

## Not in scope

- Storing messages in the database
- Any changes to the Flask app
- Ongoing sync or scheduled extraction
- Analysis of channels beyond the two specified
