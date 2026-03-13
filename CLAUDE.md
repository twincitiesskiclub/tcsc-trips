# CLAUDE.md

Twin Cities Ski Club (TCSC) — Flask web app for trip/membership registration, practice management, and club operations.

## Development Setup

**Requirements:** Python 3.12+ (`runtime.txt`), Docker (local PostgreSQL), Stripe CLI (webhook testing)

```bash
python3 -m venv env && source env/bin/activate
pip install -r requirements.txt
# Copy .env.example → .env, fill in Stripe keys + Google OAuth credentials
# Optional: SLACK_BOT_TOKEN, SLACK_USER_TOKEN, GOOGLE_PLACES_API_KEY, SLACK_WEBHOOK_URL
./scripts/dev.sh              # Start PostgreSQL + Stripe + Flask (port 5001)
./scripts/dev.sh 5000         # Custom port
```

First run pulls PostgreSQL 18 container (`tcsc-postgres`) and runs migrations.

**Docker:** `docker stop/start/rm -f tcsc-postgres` to manage container.

**Stripe webhooks:** `dev.sh` handles automatically. Manual: `stripe listen --forward-to localhost:5000/webhook`

**Database:** `flask db migrate -m "desc"` (create), `flask db upgrade` (apply). Files in `migrations/versions/`.

**Scripts:** `scripts/dev.sh` (dev startup), `scripts/release.sh` (production migration via Procfile), `scripts/seed_former_members.py` (import CSV, sets status='ALUMNI'), `scripts/seed_former_member_season.py` (create legacy season linking inactive users), `scripts/add_practice_leads.py` (bulk tag assign, `--commit`), `scripts/migrate_from_airtable.py` (one-time Airtable→PostgreSQL), `scripts/analyze_newsletter_content.py` (Claude API)

## Architecture (app structure, blueprints, routing)

**App factory:** `app/__init__.py` — creates Flask app. **Procfile:** `release: ./scripts/release.sh` + `web: gunicorn --timeout 120 "app:create_app()"`

**12 Route Blueprints** in `app/routes/`:

| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| `main.py` | `/` | Homepage, public trip/event listings |
| `trips.py` | | Trip registration pages |
| `socials.py` | | Social event registration |
| `payments.py` | | Stripe payment processing |
| `registration.py` | | Membership registration forms |
| `auth.py` | | Google OAuth authentication |
| `admin.py` | `/admin` | Admin dashboard, user/payment/trip management |
| `admin_practices.py` | `/admin/practices` | Practice CRUD, calendar, leads |
| `admin_skipper.py` | `/admin/skipper` | Skipper AI dashboard |
| `admin_newsletter.py` | `/admin/newsletter` | Newsletter prompt editor |
| `admin_scheduled_tasks.py` | | Scheduled tasks admin UI |
| `slack_interactivity.py` | `/slack` | Slack events/commands/interactions |

**Auth:** Admin restricted to `@twincitiesskiclub.org` via Google OAuth. Public access for registration/trips. Finance visibility gated by `FINANCE_AUTHORIZED_EMAILS`.

**Template filters** (`app/__init__.py`): `format_price` (cents→$50.00), `format_cents` (cents→50.00), `format_date` (datetime formatting)

**Admin dashboard** (`/admin`): Tabulator.js grids for Members/Payments/Trips/Social Events/Practices/Seasons. Bulk payment capture/refund. CSV export. Toast notifications. JS files follow `admin_*.js` naming pattern in `app/static/`.

**Admin API Endpoints:**
- `GET /admin/{payments,users}/data` — JSON data for Tabulator grids
- `POST /admin/payments/bulk-capture` / `bulk-refund` — Bulk payment operations
- `GET /admin/tags/data`, `POST /admin/tags/create`, `POST /admin/tags/<id>/edit`, `POST /admin/tags/<id>/delete` — Tag CRUD
- `GET /admin/users/<id>/tags`, `POST /admin/users/<id>/tags` — User tag assignment (POST replaces all)

## Data Model (database, ORM, schema)

Models split across three files. All use SQLAlchemy with PostgreSQL.

### Core Models (`app/models.py`)

- **User** — Member profiles; `seasons_since_active` for Slack tier; `is_returning` property (checks past ACTIVE UserSeasons); linked to SlackUser via `slack_user_id` FK
- **Season** — Membership seasons; `is_current` flag (one active); `Season.get_current()` class method
- **UserSeason** — User↔Season many-to-many with status for lottery tracking
- **Payment** — Stripe payment intents; `payment_type` (season/trip/social_event)
- **Trip** — Ski trip details, pricing, capacity, signup windows
- **SocialEvent** — Social activities, single-price, immediate capture
- **SlackUser** — Slack profile data (slack_uid, email, display_name)
- **Tag** / **UserTag** — Role tagging system (18 seeded tags: board roles, coaches, leads, activities). Tag fields: name, display_name, description, emoji, gradient
- **StatusChange** — Audit trail (user_id, previous_status, new_status, reason, changed_at)
- **AppConfig** — Key-value store (key, JSON value, description, category); `AppConfig.get()` / `.set()`

### Practice Models (`app/practices/models.py`)

- **Practice** — Session (date, location, status, warmup/workout/cooldown, slack_message_ts, coach_approved)
- **PracticeLocation** — Venues with lat/lon for weather API
- **PracticeActivity** — Activity types with `gear_required` JSON
- **PracticeType** — Workout types with `fitness_goals`, `has_intervals`
- **SocialLocation** — Post-practice social venues
- **PracticeLead** — User→practice assignment (role: lead/assist/coach, confirmed)
- **PracticeRSVP** — RSVP status (going/not_going/maybe)
- **CancellationRequest** — Skipper proposals with `evaluation_data` JSON
- Junction tables: `practice_activities_junction`, `practice_types_junction`

**Practice Interfaces** (`app/practices/interfaces.py`): Enums (`PracticeStatus`, `CancellationStatus`, `RSVPStatus`, `LeadRole`) and dataclasses (`PracticeInfo`, `PracticeEvaluation`, `CancellationProposal`, `WeatherConditions`, `ThresholdViolation`, `DaylightInfo`, `RSVPInfo`, etc.)

### Newsletter Models (`app/newsletter/models.py`)

Newsletter, NewsletterVersion, NewsletterSubmission, NewsletterDigest, NewsletterNewsItem, NewsletterPrompt, NewsletterSection, QOTMResponse, CoachRotation, MemberHighlight, NewsletterHost, PhotoSubmission

## Domain Concepts (status fields, member types, business rules)

### Status Fields — Two Levels

**CRITICAL:** Status fields are stored as plain strings (e.g., `'ACTIVE'`). `UserStatus` and `UserSeasonStatus` in `app/constants.py` are simple classes, NOT Python Enums. Do NOT call `.value` — they are already strings. Only `MemberType` is a true Enum.

- **User.status** (global, derived): `PENDING`, `ACTIVE`, `ALUMNI`, `DROPPED` — computed via `User.derived_status`, synced via `User.sync_status()`
- **UserSeason.status** (per-season): `PENDING_LOTTERY`, `ACTIVE`, `DROPPED_LOTTERY`, `DROPPED_VOLUNTARY`, `DROPPED_CAUSE`

### Data Conventions

- **Prices:** Stored in cents (5000 = $50.00), converted from dollars on form input
- **Timestamps:** UTC in database, displayed in US Central (America/Chicago)
- **Member type:** `User.is_returning` property (not stored). `get_user_member_type(user)` → 'returning'/'new'
- **Utilities** (`app/utils.py`): `now_central_naive()`, `today_central()`, `parse_date()`, `normalize_email()`, `validate_registration_form()`, etc.

### Payment Flow (Stripe integration, charges, refunds)

Capture method varies by payment type:
- **Season (new members):** `manual` capture — authorized, not charged (lottery)
- **Season (returning):** `automatic` — charged immediately
- **Trips:** Always `manual` — hold until admin captures
- **Social events:** Always `automatic` — immediate charge

Lifecycle: authorize → hold → admin capture/refund. Member type determined server-side via `User.is_returning`.

**Notifications:** `app/notifications/slack.py` — `send_payment_notification()` via `SLACK_WEBHOOK_URL` (separate from Bolt).

### Slack Tier Logic (workspace access, guest tiers)

| User.status | seasons_since_active | Slack Tier |
|-------------|---------------------|------------|
| ACTIVE | 0 | full_member |
| ALUMNI | 1 | multi_channel_guest |
| ALUMNI | 2+ | single_channel_guest |
| PENDING/DROPPED | — | None |

**Coach override:** HEAD_COACH or ASSISTANT_COACH tags → always `full_member`.

## Membership, Trips & Social Events (registration, lottery, seasons)

**Trip Registration:** Public browse → register with payment authorization → admin captures after confirmation. **Lottery system** for new members; payment holds enable selective acceptance.

**Social Events:** Mirrors trips with single-price tier. `capture_method='automatic'` (no lottery). Appears on homepage with "Social Event" badge. Admin CRUD at `/admin/social-events`.

**Season Management:** Separate registration windows for returning vs new members. `Season.is_current` flag (one at a time). "Activate Season" admin action syncs all user statuses. `POST /api/is_returning_member` for frontend member type check.

## Practice Management (workouts, RSVP, lead scheduling, coach review, practice announcements)

Config: `config/practices.yaml` — default_duration (90min), reminder_hours (24), workout_due_hours (48), default_location (Theodore Wirth), RSVP settings, Slack channels.

**Admin (`/admin/practices/`):** Practice CRUD (list, calendar, detail, create, edit, delete, cancel). Location/Activity/Type CRUD. Lead management (people filtered by tags, per-practice assignment). RSVP data. Weekly summary trigger. Settings: practice days. Templates: `admin/practices/{list,calendar,detail,config}.html`.

**Slack integration:** Announcements to #announcements-practices with RSVP buttons. Collab review in #collab-coaches-practices for coach approval. Lead availability DMs. RSVP via buttons, emoji reactions, `/tcsc rsvp`, or App Home. Centralized refresh via `refresh_practice_posts()`.

## Skipper AI (weather checks, practice cancellation, safety evaluation, trail conditions, air quality)

Automated practice safety evaluation. Config: `config/skipper.yaml`.

**Thresholds:** temp (-10°F/95°F), wind (30mph), gusts (45mph), precip (70%), lightning (cancel), trail quality (fair min), AQI cancel (151)/warning (101). Escalation: 2hr timeout, fail-open default "keep", channel #practices-core.

**Module `app/agent/`:**
- `decision_engine.py` — `evaluate_practice()`: fetches weather/trails/daylight/conflicts/AQI, threshold checks → `PracticeEvaluation`
- `thresholds.py` — Per-factor checks returning `list[ThresholdViolation]` (critical/warning)
- `brain.py` — Claude API `generate_evaluation_summary()`; template fallback
- `proposals.py` — Cancellation approve/reject processing
- `routines/` — `morning_check.py`, `pre_practice.py`, `lead_verification.py`, `weekly_summary.py`

**External Data (`app/integrations/`):**
- `weather.py` — NWS API: forecasts, alerts, wind chill/heat index, grid caching
- `trail_conditions.py` — SkinnySkI scraper: trail quality, fuzzy location matching (0.6 threshold)
- `air_quality.py` — EPA AirNow: AQI scoring, `is_safe_for_exercise`/`requires_cancellation`
- `daylight.py` — Astral: sunrise/sunset/twilight
- `event_conflicts.py` — SkinnySkI race calendar: date/location conflicts, 12hr cache

**Admin (`/admin/skipper/`):** Dashboard, proposals data, approve/reject, manual evaluate, config view.

**Workflow:** Morning check → evaluate → create cancellation proposals if violations → post to #practices-core → coaches approve/reject → 2hr timeout (fail-open) → announcements updated.

## Newsletter/Dispatch (monthly email, member submissions, living post, QOTM, AI generation)

Monthly newsletter generation and publication. Config: `config/newsletter.yaml`.

**9 sections:** opener, qotm, coaches_corner, member_heads_up, upcoming_events, member_highlight, month_in_review, from_the_board, photo_gallery, closer.

**Schedule:** Day 1 (host DM + coach assignment), Day 5 (highlight request), Day 10-13 (reminders), Day 12 (AI draft gen), Day 15 (publish deadline). AI uses Claude Opus 4.5 with extended thinking (32K budget).

**Module `app/newsletter/`:**
- `service.py` — `run_daily_update()`, `run_sunday_finalize()`, `run_monthly_orchestrator()`, `regenerate_newsletter()`
- `collector.py` — Slack message collection
- `news_scraper.py` — SkinnySkI/Loppet/Three Rivers scrapers
- `generator.py` — Claude API generation with prompt building and fallback
- `monthly_generator.py` — Per-section AI drafts: `generate_section_draft()`, `generate_all_ai_sections()`
- `mcp_server.py` — MCP tools for agentic generation
- `slack_actions.py` — Living post CRUD, review buttons, publish to announcement channel
- `modals.py` — Dispatch submission modal
- `section_editor.py` — Per-section edit modal, save, initialize
- `host.py`, `qotm.py`, `coach_rotation.py`, `member_highlight.py`, `photos.py`, `templates.py`
- `interfaces.py` — Enums (NewsletterStatus, SubmissionStatus, SectionType) and dataclasses

**Prompts:** `config/prompts/newsletter_main.md`, `config/prompts/newsletter_monthly.md`

**Admin (`/admin/newsletter/prompts`):** Prompt editor, definitions, DB/file-based prompts, save, reset to file default, version history.

## Slack Platform (bot, commands, buttons, modals, events, user sync, channel management)

### Bolt Framework (event dispatcher, slash commands, interactive components)

**Core:** `app/slack/bolt_app.py` (1744 lines). Socket Mode for local dev (`SLACK_APP_TOKEN` xapp-...), HTTP Mode for production (`SLACK_SIGNING_SECRET`).

**Routes** (`app/routes/slack_interactivity.py`): `POST /slack/{events,commands,interactions,options}` — all delegate to `get_flask_handler()`.

**Slash Commands** (`app/slack/commands.py`):
- `/tcsc practice` — today's + upcoming 7-day practices
- `/tcsc rsvp <id> <going|not_going|maybe>` — quick RSVP
- `/tcsc status` — user's RSVPs and lead assignments
- `/tcsc help` — help text
- `/dispatch` — open newsletter submission modal

**Block Actions (11+):** `rsvp_going/not_going/maybe` (announcement buttons), `home_rsvp` (App Home modal), `cancellation_approve/reject` (Skipper), `lead_confirm/need_sub` (lead response), `approve_practice` (coach approval), `edit_practice_full` (collab edit modal), `create_practice_from_summary` (weekly summary), `newsletter_approve/request_changes` (review), `section_edit` (newsletter edit), `open_dispatch_modal`

**Modal Submissions (9):** `practice_create`, `practice_edit`, `practice_edit_full`, `practice_rsvp`, `workout_entry` (sets CONFIRMED), `lead_substitution`, `dispatch_submission`, `newsletter_feedback`, `section_edit_submit`

**Events:** `app_home_opened` → `publish_app_home()`, `reaction_added` → emoji-to-RSVP (✓/+1/👍=going, ❓/🤔=maybe, ❌/-1=not_going, plus ski emojis), `message` (stub)

### Practices Slack Sub-Package (announcements, RSVP counts, lead DMs, coach review posts)

**Module `app/slack/practices/`** (barrel re-exports via `__init__.py`):

- `_config.py` — Config cache, channel/user ID constants (LOGGING_CHANNEL_ID, PRACTICES_CORE_CHANNEL_ID, COORD_CHANNEL_ID, COLLAB_CHANNEL_ID, ADMIN_SLACK_IDS, FALLBACK_COACH_IDS)
- `announcements.py` — `post_practice_announcement()`, `post_combined_lift_announcement()`, `update_practice_announcement()`, `update_practice_slack_post()`
- `cancellations.py` — `post_cancellation_proposal()`, `update_cancellation_decision()`, `post_cancellation_notice()`, `update_practice_as_cancelled()`
- `leads.py` — `send_lead_availability_request()`, `send_workout_reminder()`, `send_lead_checkin_dm()`, `post_substitution_request()`, `post_24h_lead_confirmation()`
- `coach_review.py` — `post_48h_workout_reminder()`, `post_collab_review()`, `update_collab_post()`, `post_coach_weekly_summary()`, `escalate_practice_review()`, logging helpers
- `rsvp.py` — `post_thread_reply()`, `update_going_list_thread()`, `update_practice_rsvp_counts()`, `log_rsvp_action()`
- `app_home.py` — `publish_app_home(user_id)`
- `refresh.py` — **Centralized dispatcher**: `refresh_practice_posts(practice, change_type, actor_slack_id, notify)` updates announcement, collab, coach summary, weekly summary. Change types: `edit`, `cancel`, `delete`, `rsvp`, `workout`, `create`

**Block Kit Builders** (`app/slack/blocks/`): Parallel sub-package with builders for announcements, cancellations, leads, coach_review, rsvp, summary, app_home, recap, dispatch.

### User Sync (Slack profile sync, member matching, profile push)

Bi-directional sync. `app/slack/client.py` (20 public functions — WebClient wrappers for messaging, channels, reactions, profiles). `app/slack/sync.py` (10 functions — pull sync, push sync, status queries, linking, import).

**Profile sync pushes to Slack:** preferred_technique, date_of_birth, roles (from tags), fresh_tracks_post (auto-discovered). Field IDs: `SLACK_FIELD_SKI_TECHNIQUE`, `SLACK_FIELD_BIRTHDAY`, `SLACK_FIELD_ROLES`, `SLACK_FIELD_FRESH_TRACKS`.

**Slack tokens:** `SLACK_BOT_TOKEN` scopes: `users:read`, `users:read.email`, `channels:read`, `channels:history`. `SLACK_USER_TOKEN` scope: `users.profile:write`.

**Admin** (`/admin/slack`): Sync dashboard, pull from Slack, push profiles to Slack, match/link/unlink users. Rate limiting: auto-retry on 429, batch size 10, 5-min Fresh Tracks cache.

### Channel Sync (workspace roles, guest tiers, automated channel management)

`app/slack/channel_sync.py` — Manages three tiers (full_member/multi_channel_guest/single_channel_guest). Handles role changes, channel add/remove, invites, reactivations. Config: `config/slack_channels.yaml`.

`app/slack/admin_api.py` — Undocumented Slack admin API (cookie-based auth). `change_user_role()`, `invite_user_by_email()`, `validate_admin_credentials()`. Raises `CookieExpiredError`. Retry with exponential backoff.

**Admin** (`/admin/channel-sync`): Dashboard, run sync (background thread), poll results, ExpertVoice trigger. Dry-run mode by default. Preserves manually-joined channels for full members.

### Role Management (tags, badges, member designations)

Admin at `/admin/roles`: Tabulator.js grid with inline editing (name, display_name, emoji, gradient). Template: `admin/roles.html`.

## Background Jobs (scheduler, cron, automated tasks)

`app/scheduler.py` — APScheduler BackgroundScheduler in thread pool. Single-worker guard via file lock (`/tmp/tcsc_scheduler.lock`). All times US Central.

| Job ID | Schedule | Purpose |
|--------|----------|---------|
| `slack_channel_sync` | 3am daily | Channel sync + ExpertVoice |
| `skipper_morning_check` | 7am daily | Evaluate today's practices |
| `skipper_48h_check` | 7:15am daily | Nudge coaches for workout submission |
| `skipper_evening_lead_check` | 4pm daily | Verify leads (noon-midnight practices) |
| `skipper_morning_lead_check` | 9pm daily | Verify leads (tomorrow AM practices) |
| `skipper_expire_proposals` | Hourly | Expire pending proposals (fail-open: "keep") |
| `practice_announcements_morning` | 8am daily | Announce evening practices |
| `practice_announcements_evening` | 8pm daily | Announce next-day morning practices |
| `coach_weekly_summary` | Sun 8am | Coach review to #collab-coaches |
| `skipper_weekly_summary` | Sun 8:30pm | Weekly overview to #announcements |
| `newsletter_daily_update` | 8am daily | Regenerate living post |
| `newsletter_sunday_finalize` | Sun 6pm | Finalize for admin review |
| `newsletter_monthly_orchestrator` | 8am daily | Day-of-month newsletter actions |

Note: `skipper_24h_check` exists but disabled (replaced by evening/morning lead checks).

**Functions:** `init_scheduler(app)`, `get_scheduler_status()`, `trigger_channel_sync_now(app)`, `trigger_skipper_job_now(app, job_type)`, `is_main_worker()`

## ExpertVoice (pro deals, SFTP member sync)

`app/integrations/expertvoice.py` — Syncs eligible members to ExpertVoice via SFTP. Eligible: ACTIVE members + ALUMNI with `seasons_since_active == 1`. Config in `config/slack_channels.yaml`. Runs daily at 3am (after Slack sync) or manual via `/admin/channel-sync/expertvoice`.

## Configuration & Deployment

**Config files:** `config/slack_channels.yaml` (channel tiers, ExpertVoice), `config/practices.yaml` (practice settings), `config/skipper.yaml` (AI thresholds, caching), `config/newsletter.yaml` (sections, schedule, AI generation), `config/prompts/` (AI prompt templates)

**Environment variables** (see `.env.example`):

| Category | Variables |
|----------|-----------|
| Core | `DATABASE_URL`, `FLASK_SECRET_KEY`, `FLASK_ENV` |
| Stripe | `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |
| Google | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_PLACES_API_KEY` |
| Slack | `SLACK_BOT_TOKEN`, `SLACK_USER_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_APP_TOKEN`, `SLACK_WEBHOOK_URL`, `SLACK_ADMIN_TOKEN`, `SLACK_YOUR_COOKIE`, `SLACK_YOUR_X_ID` |
| AI | `ANTHROPIC_API_KEY` |
| ExpertVoice | `EXPERTVOICE_SFTP_USERNAME`, `EXPERTVOICE_SFTP_PASSWORD` |
| Optional | `FINANCE_AUTHORIZED_EMAILS`, `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID` |

**Key dependencies:** flask/flask-sqlalchemy/flask-migrate, stripe, slack-sdk/slack-bolt, anthropic, apscheduler, paramiko (SFTP), beautifulsoup4, astral, tenacity, authlib/google-auth, pyyaml, psycopg2-binary

**Deployment:** Gunicorn (120s timeout) on Render. `scripts/release.sh` runs migrations. Tailwind CSS build via `package.json`.

## Tests

pytest with PostgreSQL fixtures. **10 files, 124 tests:**

| File | # | Area |
|------|---|------|
| `tests/newsletter/test_qotm.py` | 8 | Question of the Month |
| `tests/newsletter/test_host.py` | 12 | Host management |
| `tests/newsletter/test_coach_rotation.py` | 17 | Coach rotation |
| `tests/newsletter/test_member_highlight.py` | 20 | Member spotlight |
| `tests/newsletter/test_photos.py` | 9 | Photo gallery |
| `tests/newsletter/test_section_editor.py` | 2 | Section editing |
| `tests/newsletter/test_slack_actions.py` | 16 | Living post |
| `tests/newsletter/test_monthly_generator.py` | 15 | Monthly AI generation |
| `tests/slack/test_coach_summary_blocks.py` | 14 | Coach summary blocks |
| `tests/slack/test_refresh.py` | 11 | Post refresh dispatcher |

`test_practice_post.py` (root) — manual practice announcement testing, not pytest.

**Not tested:** Trips, payments, admin routes, auth, core models, scheduler, ExpertVoice, Skipper AI.

**Reference:** `.cursor/rules/tcsc_registration_spec.mdc` (product spec), `CONTRIBUTING.md` (User/UserSeason model), `app/constants.py` (status constants, `MemberType` enum)
