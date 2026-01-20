# Implementation Milestones

Each milestone is self-contained. Resume from any milestone by checking its files.

## MILESTONE 1: Database Foundation

**Goal:** Update newsletter module with new models for monthly dispatch

**Files to Create/Modify:**
- `app/newsletter/models.py` (add 5 new models, update Newsletter)
- `app/newsletter/interfaces.py` (add section type enums)
- `config/newsletter.yaml` (restructure for monthly)

**New Models:**
1. **NewsletterSection** - Per-section content with status and Slack thread ref
2. **QOTMResponse** - Question of the Month answers (unique per user/newsletter)
3. **CoachRotation** - Coach assignment and submission tracking
4. **MemberHighlight** - Nominated member spotlight content
5. **PhotoSubmission** - Curated photos from #photos channel

**Newsletter Model Updates:**
- Add `month_year` field (e.g., "2026-01")
- Add `period_start`/`period_end` (generic date range)
- Add `publish_target_date` (15th of month)
- Add `qotm_question` field (Text)

**Steps:**
1. Update models.py with new models
2. Update interfaces.py with SectionType, SectionStatus enums
3. Update config/newsletter.yaml with new sections config
4. Run `flask db migrate -m "Monthly dispatch models"`
5. Run `flask db upgrade`

**Verification:**
```python
from app.newsletter.models import NewsletterSection, QOTMResponse
NewsletterSection.query.all()
```

---

## MILESTONE 2: Question of the Month System

**Goal:** Channel-based QOTM with modal submission and admin curation

**Files to Create:**
- `app/newsletter/qotm.py`

**Files to Modify:**
- `app/newsletter/modals.py` (add QOTM modal)
- `app/slack/bolt_app.py` (add handlers)

**Key Functions:**
- `post_qotm_to_channel(question, channel)` - Post with "Share Your Answer" button
- `handle_qotm_submission(user_id, response)` - Store response (upsert)
- `get_qotm_responses(newsletter_id)` - Fetch for review
- `select_qotm_responses(response_ids)` - Mark selected
- `get_selected_qotm_for_newsletter(newsletter_id)` - For rendering

**Slack Components:**
1. QOTM channel post with button
2. QOTM response modal (max 500 chars)
3. Admin review message in #newsletter-admin with checkboxes

**Steps:**
1. Create qotm.py with core functions
2. Add `build_qotm_response_modal()` to modals.py
3. Add `qotm_button_click` action handler to bolt_app.py
4. Add `qotm_response_submit` view handler
5. Add `qotm_selection_save` action handler

**Verification:**
- Post QOTM to test channel
- Submit response via modal
- Verify response in database
- Select responses in admin review

---

## MILESTONE 3: Coach Rotation System

**Goal:** Automated coach assignment with DM-based submission

**Files to Create:**
- `app/newsletter/coach_rotation.py`

**Files to Modify:**
- `app/newsletter/modals.py` (add coach submission modal)
- `app/slack/bolt_app.py` (add handlers)

**Key Functions:**
- `get_next_coach()` - Select coach with oldest/no contribution
- `assign_coach_for_month(newsletter_id)` - Create rotation record
- `send_coach_request(coach_user_id)` - DM with modal button
- `handle_coach_submission(user_id, content)` - Store content
- `send_coach_reminder(coach_user_id)` - Follow-up DM
- `skip_to_backup_coach(newsletter_id)` - Handle non-response

**Coach Selection Logic:**
```python
# Query users with HEAD_COACH or ASSISTANT_COACH tags
# Find most recent contribution per coach via CoachRotation.submitted_at
# Select coach with oldest (or no) contribution
```

**Steps:**
1. Create coach_rotation.py with rotation logic
2. Add `build_coach_submission_modal()` to modals.py
3. Add `coach_submit_button` action handler
4. Add `coach_submission_submit` view handler
5. Add `coach_decline_button` action handler

**Verification:**
- Call `get_next_coach()` manually
- Send DM to test coach
- Submit via modal
- Verify content stored

---

## MILESTONE 4: Member Highlight System

**Goal:** Admin-nominated member spotlights via DM

**Files to Create:**
- `app/newsletter/member_highlight.py`

**Files to Modify:**
- `app/routes/admin.py` (add nomination endpoint)
- `app/newsletter/modals.py` (add highlight modal)
- `app/slack/bolt_app.py` (add handlers)

**Key Functions:**
- `nominate_member(admin_email, member_user_id)` - Create nomination
- `send_highlight_request(member_user_id)` - DM with modal button
- `handle_highlight_submission(user_id, content)` - Store content
- `mark_highlight_declined(member_user_id)` - Record declination

**Admin UI:**
- Dropdown to select member
- Shows "last featured" date
- Suggests members not recently featured

**Steps:**
1. Create member_highlight.py
2. Add `build_highlight_modal()` to modals.py
3. Add nomination endpoint to admin.py
4. Add `highlight_submit_button` action handler
5. Add `highlight_submission_submit` view handler

**Verification:**
- Nominate member via admin UI
- Verify DM sent to member
- Submit spotlight via modal
- Verify content stored

---

## MILESTONE 5: Photo Gallery Curation

**Goal:** Collect and curate photos from #photos channel

**Files to Create:**
- `app/newsletter/photos.py`

**Files to Modify:**
- `app/slack/bolt_app.py` (add selection handlers)

**Key Functions:**
- `collect_month_photos(channel_id, month_start, month_end)` - Scan channel
- `get_photo_submissions(newsletter_id)` - Fetch for review
- `select_photos(photo_ids)` - Mark selected

**Photo Collection:**
- Use `files.list` API to get images
- Sort by reaction count (most popular first)
- Store permalink, caption, fallback description

**Admin Curation:**
- Display top 10-15 photos with thumbnails in #newsletter-admin
- Checkbox to select each
- Selected photos appear in newsletter

**Steps:**
1. Create photos.py with collection functions
2. Add photo selection UI to admin review
3. Add `photo_selection_save` action handler

**Verification:**
- Collect photos from #photos
- Display in admin review
- Select photos
- Verify selected in database

---

## MILESTONE 6: Section-by-Section Editing

**Goal:** Per-section editing via Slack modals

**Files to Create:**
- `app/newsletter/section_editor.py`

**Files to Modify:**
- `app/newsletter/slack_actions.py` (thread-based sections)
- `app/newsletter/modals.py` (section edit modal)
- `app/slack/bolt_app.py` (add handlers)

**Thread-Based Structure:**
- Main post: Header, status, table of contents
- Thread replies: One per section with Edit button
- Each section tracks its own `slack_thread_ts`

**Section Status State Machine:**
- `awaiting_content` → waiting for human input
- `has_ai_draft` → AI generated, needs edit
- `human_edited` → human has modified
- `final` → no more edits expected

**Steps:**
1. Create section_editor.py with edit functions
2. Update slack_actions.py for thread-based posts
3. Add `build_section_edit_modal()` to modals.py
4. Add `section_edit_button` action handler
5. Add `section_edit_submit` view handler

**Verification:**
- Create living post with thread sections
- Click Edit on a section
- Modify content in modal
- Verify section updates in thread

---

## MILESTONE 7: Upcoming Events Section

**Goal:** Scrape upcoming races and events

**Files to Create:**
- `app/newsletter/events.py`

**Files to Modify:**
- `app/newsletter/news_scraper.py` (add race calendar parsing)

**Data Sources:**
- SkinnySkI race calendar
- Club events (if calendar exists)
- Manual additions via admin

**Key Functions:**
- `scrape_upcoming_races(month, year)` - Get races from SkinnySkI
- `get_club_events(newsletter_id)` - Get club events
- `format_events_section(races, events)` - Generate draft

**Steps:**
1. Create events.py
2. Update news_scraper.py with race calendar parsing
3. Add events to AI draft generation

**Verification:**
- Scrape upcoming races
- Verify events collected
- Generate draft section

---

## MILESTONE 8: AI Draft Generation

**Goal:** Generate drafts for AI-assisted sections only

**Files to Modify:**
- `app/newsletter/generator.py` (section-specific generation)
- `config/prompts/newsletter_main.md` (new prompt structure)

**AI-Assisted Sections:**
- From the Board (from leadership-* channels)
- Member Heads Up (events/reminders)
- Upcoming Races & Events (from scrapers)
- Slack Recap (high-activity posts)
- Month in Review (summary)

**Generation Constraints:**
- Each section draft <2900 chars (Slack modal limit)
- Tone: Starting point for editors, not final copy
- Output: JSON with section drafts

**Steps:**
1. Update generator.py for section-specific output
2. Rewrite newsletter_main.md prompt
3. Add length validation

**Verification:**
- Generate AI drafts
- Verify each section <2900 chars
- Verify JSON structure

---

## MILESTONE 9: Monthly Scheduling

**Goal:** Single orchestrator job + manual triggers for each stage

**Files to Modify:**
- `app/scheduler.py`
- `app/newsletter/service.py`
- `app/routes/admin_scheduled_tasks.py`

**Consolidated Orchestrator:**
```python
@scheduler.scheduled_job('cron', hour=8, minute=0, timezone='America/Chicago')
def newsletter_monthly_orchestrator():
    today = datetime.now(tz).day
    newsletter = Newsletter.get_or_create_current_month()

    if today == 1:
        assign_coach_for_month(newsletter)
        post_qotm_to_channel(newsletter)
    elif today == 5:
        if newsletter.has_highlight_nomination:
            send_highlight_request(newsletter)
    # ... etc
```

**Manual Trigger Endpoints:**
Each stage can be triggered manually for out-of-band newsletters:

| Endpoint | Action |
|----------|--------|
| `POST /admin/newsletter/trigger/qotm` | Post QOTM to #chat |
| `POST /admin/newsletter/trigger/coach` | Assign & DM coach |
| `POST /admin/newsletter/trigger/highlight` | Send highlight request |
| `POST /admin/newsletter/trigger/reminders` | Send all reminders |
| `POST /admin/newsletter/trigger/ai-drafts` | Generate AI sections |
| `POST /admin/newsletter/trigger/living-post` | Create/update living post |
| `POST /admin/newsletter/trigger/review` | Add review buttons |
| `POST /admin/newsletter/trigger/publish` | Publish to announcements |
| `POST /admin/newsletter/create` | Create newsletter for any month |

**Steps:**
1. Remove daily 8am regeneration job
2. Add `newsletter_monthly_orchestrator` job
3. Add `get_or_create_current_month()` to Newsletter model
4. Add manual trigger endpoints to admin routes
5. Add trigger buttons to `/admin/scheduled-tasks` UI
6. Ensure all stages are idempotent (safe to re-run)

**Verification:**
- Check scheduler has monthly job
- Manually trigger each stage via admin UI
- Verify stages work in any order
- Test creating out-of-band newsletter

---

## MILESTONE 10: Config Updates

**Goal:** Update configuration for monthly dispatch

**Files to Modify:**
- `config/newsletter.yaml`

**New Config Structure:**
```yaml
dispatch:
  frequency: monthly
  publish_day: 15
  timezone: America/Chicago

sections:
  - id: qotm
    name: Question of the Month
    ai_generated: false
    required: true
  # ... all 9 sections

schedule:
  coach_assignment: 1
  qotm_send: 1
  highlight_request: 5
  coach_reminder: 10
  ai_draft_generation: 12
  final_reminders: 13
  review_buttons: 14
  publish_deadline: 15

channels:
  living_post: tcsc-logging
  publish: announcements-tcsc
  admin_review: newsletter-admin
  photos: photos
  qotm_post: chat

private_channels:
  - pattern: "leadership-*"
```

**Steps:**
1. Update newsletter.yaml with new structure
2. Update code to read new config format
3. Create #newsletter-admin channel

**Verification:**
- Load config
- Verify all sections present
- Verify schedule correct
