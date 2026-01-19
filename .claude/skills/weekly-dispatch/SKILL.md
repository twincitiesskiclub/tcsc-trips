---
name: monthly-dispatch
description: Build the TCSC Monthly Dispatch newsletter system. Use when implementing newsletter generation, Slack message collection, member submissions, coach rotation, QOTM, member highlights, photo gallery, or section editing. Triggers for tasks involving app/newsletter/, config/newsletter.yaml, or newsletter-related scheduled jobs.
---

# TCSC Monthly Dispatch

## Overview

A human-first newsletter with AI-assisted drafts that publishes mid-month (around the 15th). Emphasizes member-created content with AI drafts for editorial efficiency.

## Architecture

```
1st          5th         10th        12th        14th        15th
 ↓            ↓           ↓           ↓           ↓           ↓
[Coach/QOTM] [Highlight] [Reminder]  [AI Draft]  [Review]   [PUBLISH]
```

**Living post** in `#tcsc-logging` with thread-based sections (one per section for editing).

## Quick Reference

| Component | Location |
|-----------|----------|
| Implementation plan | `.claude/plans/synchronous-mapping-island.md` |
| Configuration | `config/newsletter.yaml` |
| Prompts | `config/prompts/newsletter_*.md` |
| Models | `app/newsletter/models.py` |

## Newsletter Sections

| # | Section | Owner | AI Role |
|---|---------|-------|---------|
| 1 | **Opener** | Newsletter Host (manual pick) | None |
| 2 | **Question of the Month** | Admin curates responses | None |
| 3 | **Coaches Corner** | Rotating coach | None |
| 4 | **Member Heads Up** | Admin/Editor | AI draft → edit |
| 5 | **Upcoming Races & Events** | Admin/Editor | AI draft → edit |
| 6 | **Member Highlight** | Nominated member answers template | AI composes → edit |
| 7 | **Month in Review** | Admin/Editor | AI draft → edit (includes Slack recap) |
| 8 | **From the Board** | Admin/Editor | AI draft from leadership-* → edit |
| 9 | **Closer** | Newsletter Host (same as opener) | None |
| 10 | **Photo Gallery** | Admin curates | None *(thread reply)* |

**Key Roles:**
- **Newsletter Host** - Manually assigned, writes opener + closer, can be external guest
- **Rotating Coach** - Automated rotation through HEAD_COACH/ASSISTANT_COACH tags
- **Member Highlight** - Nominated member answers template questions (fun + meaningful), AI composes

## Module Structure

```
app/newsletter/
├── models.py            # 12 DB models (6 original + 6 new incl. NewsletterHost)
├── interfaces.py        # Enums, dataclasses
├── service.py           # Core orchestration
├── collector.py         # Slack message collection
├── news_scraper.py      # SkinnySkI, Loppet, Three Rivers
├── generator.py         # Claude Opus 4.5 generation + Member Highlight AI composition
├── slack_actions.py     # Living post management + photo thread reply
├── modals.py            # Host, QOTM, coach, highlight template modals
├── host.py              # Newsletter Host (opener/closer) system
├── qotm.py              # Question of the Month system
├── coach_rotation.py    # Coach rotation logic
├── member_highlight.py  # Member nomination + template + AI composition
├── photos.py            # Photo gallery curation + thread publishing
├── events.py            # Upcoming races & events
└── section_editor.py    # Per-section Slack editing
```

## Implementation Milestones

See [references/milestones.md](references/milestones.md) for complete milestone details.

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Database Foundation | Not started |
| 2 | QOTM System | Not started |
| 3 | Newsletter Host System | Not started |
| 4 | Coach Rotation | Not started |
| 5 | Member Highlight (Template + AI) | Not started |
| 6 | Photo Gallery (Thread Reply) | Not started |
| 7 | Section Editing | Not started |
| 8 | Events Section | Not started |
| 9 | AI Draft Generation | Not started |
| 10 | Monthly Scheduling | Not started |
| 11 | Config Updates | Not started |

## Key Patterns

### Human-First, AI-Assisted

```
Monthly orchestration:
1st:  send_host_request()         → DM Newsletter Host (after manual assignment)
      assign_coach_for_month()    → DM coach with modal
      post_qotm_to_channel()      → Post question to #chat
5th:  send_highlight_request()    → DM nominated member with template
10th: send_host_reminder()        → Follow up if needed
      send_coach_reminder()       → Follow up if needed
12th: generate_ai_drafts()        → AI sections + Member Highlight composition
      create_living_post()        → Thread-based sections
13th: send_final_reminders()      → Last chance notices
14th: add_review_buttons()        → Approve/Edit per section
15th: [Manual publish + photo thread reply]
```

### Thread-Based Section Editing

Each section is a thread reply with its own Edit button:
- Click Edit → Modal opens with section content
- Save → Section updates in place
- AI drafts limited to <2900 chars (Slack modal limit)

### Section Status State Machine

```
awaiting_content → (human submits) → human_edited → final
has_ai_draft     → (human edits)  → human_edited → final
```

### Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
def collect_channel_messages(channel_id, since): ...
```

## Existing Patterns to Follow

| Pattern | Reference |
|---------|-----------|
| Slack client | `app/slack/client.py` |
| Bolt commands | `app/slack/bolt_app.py` |
| Claude API | `app/agent/brain.py` |
| Web scraping | `app/integrations/trail_conditions.py` |
| Scheduled jobs | `app/scheduler.py` |

## Database Models

| Model | Purpose |
|-------|---------|
| Newsletter | Monthly newsletter record with status, content, Slack refs |
| NewsletterVersion | Version history at each regeneration |
| NewsletterSection | Individual section content, status, and Slack thread ref |
| NewsletterSubmission | Member content via /dispatch |
| NewsletterDigest | Collected Slack messages |
| NewsletterNewsItem | Scraped external news |
| NewsletterPrompt | Database-editable prompts |
| **NewsletterHost** | Host assignment, opener/closer content (can be external) |
| QOTMResponse | Question of the Month answers |
| CoachRotation | Coach assignment and content |
| MemberHighlight | Nomination + raw_answers + ai_composed_content + final content |
| PhotoSubmission | Curated photos from #photos |

## Monthly Schedule

| Day | Action | Manual Trigger |
|-----|--------|----------------|
| 1st | Assign Newsletter Host (manual), DM them | `/admin/newsletter/trigger/host` |
| 1st | Assign coach (auto rotation), DM them | `/admin/newsletter/trigger/coach` |
| 1st | Post QOTM to #chat | `/admin/newsletter/trigger/qotm` |
| 5th | Send member highlight request (template) | `/admin/newsletter/trigger/highlight` |
| 10th | Host + Coach reminders if not submitted | `/admin/newsletter/trigger/reminders` |
| 12th | Generate AI drafts + compose highlight | `/admin/newsletter/trigger/ai-drafts` |
| 12th | Create living post | `/admin/newsletter/trigger/living-post` |
| 13th | Final reminders for pending content | `/admin/newsletter/trigger/reminders` |
| 14th | Add review/edit buttons | `/admin/newsletter/trigger/review` |
| 15th | Publish + photo gallery thread | `/admin/newsletter/trigger/publish`, `/admin/newsletter/trigger/photo-thread` |

All stages can be triggered manually for out-of-band newsletters via admin UI or API.

## Channels

| Channel | Purpose |
|---------|---------|
| `#tcsc-logging` | Living post with section threads |
| `#announcements-tcsc` | Published newsletter |
| `#newsletter-admin` | QOTM review, section approvals |
| `#chat` | QOTM prompt posted here |
| `#photos` | Photo gallery source |
| `leadership-*` | Board recap content source |
