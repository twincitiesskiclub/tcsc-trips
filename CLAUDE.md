# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment Setup

### Local Development

**Requirements:**
- Python 3.12+ (see `runtime.txt`)
- Docker (for local PostgreSQL)
- Stripe CLI (for webhook testing)

1. Create and activate virtual environment:
   ```bash
   python3 -m venv env
   source env/bin/activate  # macOS/Unix
   # or .\env\Scripts\activate.bat  # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   - Copy `.env.example` to `.env`
   - Fill in Stripe API keys and Google OAuth credentials
   - Optional: `SLACK_WEBHOOK_URL` for payment notifications
   - Optional: `GOOGLE_PLACES_API_KEY` for address autocomplete
   - Optional: `SLACK_BOT_TOKEN` for Slack user sync (pull from Slack)
   - Optional: `SLACK_USER_TOKEN` for Slack profile sync (push to Slack)
   - Optional: Slack Admin API credentials for automated channel sync (see Slack Channel Sync section)

4. Run the development server:
   ```bash
   ./scripts/dev.sh              # PostgreSQL on port 5001 (default)
   ./scripts/dev.sh 5000         # PostgreSQL on port 5000
   ./scripts/dev.sh --sqlite     # SQLite for quick testing (no Docker)
   ```

   On first run with PostgreSQL, the script will:
   - Pull and start a PostgreSQL 18 container (`tcsc-postgres`)
   - Migrate data from `app.db` (if present) or create empty tables

### Managing Local PostgreSQL

```bash
docker stop tcsc-postgres     # Stop the container (data persists)
docker start tcsc-postgres    # Restart it
docker rm -f tcsc-postgres    # Delete container and reset data
```

### Stripe Webhook Testing
The `dev.sh` script automatically handles webhook configuration. It:
- Starts Stripe webhook listener
- Extracts and sets `STRIPE_WEBHOOK_SECRET` in `.env`
- Launches Flask with the correct environment

**Manual method** (if needed separately):
```bash
stripe listen --forward-to localhost:5000/webhook
```
This provides a webhook signing secret (`whsec_...`) to set as `STRIPE_WEBHOOK_SECRET`.

### Database Management
- **Local Development:** PostgreSQL via Docker (default) or SQLite (`--sqlite` flag)
- **Production:** PostgreSQL on Render (via `DATABASE_URL` env var)
- **Create New Migration:** `flask db migrate -m "description"`
- **Apply Migrations:** `flask db upgrade`
- **Migration Files:** Located in `migrations/versions/`

### Helper Scripts
- `scripts/dev.sh` - **Recommended** dev startup (PostgreSQL + Stripe + Flask)
- `scripts/migrate_to_postgres.py` - Migrate data from SQLite to PostgreSQL
- `scripts/seed_former_members.py` - Import CSV of former members (sets status='ALUMNI')
- `scripts/seed_former_member_season.py` - Create legacy season linking inactive users

## Architecture Overview

### Application Structure
This is a Flask web application for the Twin Cities Ski Club (TCSC) trip and membership registration system.

**Core Components:**
- **Flask Application Factory:** `app/__init__.py` creates and configures the Flask app
- **Route Blueprints:** Organized in `app/routes/` directory:
  - `main.py` - Homepage and public trip/event listings
  - `trips.py` - Individual trip registration pages
  - `socials.py` - Social event registration (pickleball, etc.)
  - `payments.py` - Payment processing (Stripe integration)
  - `admin.py` - Admin dashboard and management
  - `auth.py` - Google OAuth authentication
  - `registration.py` - Membership registration forms

**Database Models (`app/models.py`):**
- **Trip:** Ski trip details, pricing, capacity, signup windows
- **SocialEvent:** Social activities with simplified single-price payment (immediate capture)
- **Payment:** Stripe payment intents with `payment_type` (season/trip/social_event)
- **User:** Member profiles with `seasons_since_active` for Slack tier calculation
- **Season:** Membership seasons with `is_current` flag (only one active at a time)
- **UserSeason:** Many-to-many with expanded status for lottery tracking
- **Tag:** Predefined tags for user roles/designations (board member, coach, lead, etc.)
  - Fields: `name` (unique identifier like 'PRESIDENT'), `display_name` (like 'President'), `description`, `emoji`, `gradient` (CSS styling for badges)
  - Seeded with 18 initial tags: Board roles (PRESIDENT, VICE_PRESIDENT, TREASURER, SECRETARY, AUDITOR, BOARD_MEMBER, FRIEND_OF_BOARD), Practices (PRACTICES_DIRECTOR, PRACTICES_LEAD, HEAD_COACH, ASSISTANT_COACH, WAX_MANAGER), Activities (TRIP_LEAD, ADVENTURES, SOCIAL, SOCIAL_COMMITTEE, MARKETING, APPAREL)
- **UserTag:** Junction table linking users to tags (many-to-many via `User.tags` relationship)

### Authentication & Security
- **Admin Access:** Restricted to `@twincitiesskiclub.org` email addresses via Google OAuth
- **Public Access:** Trip registration and membership signup (no authentication required)
- **Payment Security:** Stripe Payment Intents with manual capture (authorization holds)
- **Finance Authorization:** Payment amounts visible only to authorized finance admins (`FINANCE_AUTHORIZED_EMAILS`)

### Admin Interface
The admin dashboard (`/admin`) provides:
- **Tabulator.js Data Grids:** Interactive spreadsheet-style views for Members and Payments
- **Bulk Payment Actions:** Accept (capture) or refund multiple payments at once
- **CSV Export:** Export member and payment data
- **Toast Notifications:** Real-time feedback for admin actions

**Key Admin Static Files:**
- `app/static/admin_users.js` - Member management grid
- `app/static/admin_payments.js` - Payment management grid

### Admin API Endpoints

**Payment Management:**
- `GET /admin/payments/data` - JSON payment data for Tabulator grid
- `POST /admin/payments/bulk-capture` - Capture multiple payment intents
- `POST /admin/payments/bulk-refund` - Refund multiple payments

**User Management:**
- `GET /admin/users/data` - JSON user data for Tabulator grid

**Tag/Role Management:**
- `GET /admin/tags/data` - JSON tag data with user counts
- `POST /admin/tags/create` - Create new tag
- `POST /admin/tags/<id>/edit` - Update tag properties
- `POST /admin/tags/<id>/delete` - Delete tag (only if no users assigned)
- `GET /admin/users/<id>/tags` - Get user's current tags
- `POST /admin/users/<id>/tags` - Update user's tags (replaces all existing)

### Payment Flow Architecture
**Two-tier capture system based on member type:**
- **New Members:** `capture_method='manual'` - card authorized but not charged (lottery system)
- **Returning Members:** `capture_method='automatic'` - card charged immediately

**Payment lifecycle:**
1. **Authorization:** Payment intent created, card validated
2. **Hold Placement:** New members have funds held pending lottery
3. **Manual Capture:** Admins capture payments for lottery-selected new members
4. **Refund/Cancel:** Refund captured payments OR cancel uncaptured authorizations

**Member type determination:** Server-side via `User.is_returning` property (checks for any ACTIVE UserSeason in past seasons)

### Key Integrations
- **Stripe API:** Payment processing, webhooks, refunds
- **Google OAuth:** Admin authentication via Authlib
- **Flask-Migrate:** Database schema versioning with Alembic
- **SQLAlchemy:** ORM with PostgreSQL (production) and SQLite (optional local)
- **Slack Webhooks:** Payment notifications to club Slack channel
- **Slack API:** User sync, channel management, and automated role changes
- **APScheduler:** Background job scheduling for automated syncs
- **ExpertVoice SFTP:** Member pro deals access sync
- **Google Places API:** Address autocomplete on registration forms

### Slack User Sync
Bi-directional sync between database users and Slack workspace members.

**Module:** `app/slack/`
- `client.py` - Slack WebClient wrapper with bot and user token support
- `sync.py` - Sync service for both pull (Slack to DB) and push (DB to Slack) operations

**Models:**
- `SlackUser` - Stores Slack profile data (slack_uid, email, display_name, etc.)
- `User.slack_user_id` - FK linking User to SlackUser

**Admin Endpoints:**
- `GET /admin/slack` - Sync dashboard UI
- `POST /admin/slack/sync` - Pull user data FROM Slack API (creates/updates SlackUser records)
- `POST /admin/slack/sync-profiles` - Push profile data TO Slack (updates custom profile fields)
- `GET /admin/slack/status` - Get sync statistics
- `GET /admin/slack/unmatched` - List unmatched users on both sides
- `POST /admin/slack/link` - Manually link User to SlackUser
- `POST /admin/slack/unlink` - Remove Slack association
- `POST /admin/slack/delete-user` - Delete user (JSON API)

**Profile Sync to Slack:**
The profile sync feature pushes database fields to Slack custom profile fields:
- **Preferred Ski Technique:** Synced from `User.preferred_technique`
- **Birthday:** Synced from `User.date_of_birth` (YYYY-MM-DD format)
- **Roles:** Comma-separated list from `User.tags` (e.g., "Board Member, Trip Leader")
- **Fresh Tracks Post:** Auto-discovered by scanning #fresh-tracks channel for user's latest post

**Client Functions (app/slack/client.py):**
- `get_slack_client()` - Returns bot token WebClient
- `get_slack_user_client()` - Returns user token WebClient (for profile writes)
- `update_user_profile(slack_uid, fields)` - Updates custom profile fields
- `get_channel_id_by_name(channel_name)` - Looks up channel ID
- `get_latest_messages_by_user(channel_id)` - Batch fetches user messages with permalinks

**Sync Functions (app/slack/sync.py):**
- `sync_slack_users()` - Pull sync: fetches Slack members, creates/updates SlackUser records
- `sync_profiles_to_slack(batch_size, offset)` - Push sync: updates Slack profiles in batches
- Field ID constants: `SLACK_FIELD_SKI_TECHNIQUE`, `SLACK_FIELD_BIRTHDAY`, `SLACK_FIELD_ROLES`, `SLACK_FIELD_FRESH_TRACKS`

**Authentication:**
- `SLACK_BOT_TOKEN` - Bot token with scopes: `users:read`, `users:read.email`, `channels:read`, `channels:history`
- `SLACK_USER_TOKEN` - User token with scope: `users.profile:write` (required for profile sync)

**Rate Limiting:**
Both client functions include automatic retry handling for rate limits (429 errors). Profile sync processes users in batches (default 10) to avoid timeouts and uses a 5-minute cache for Fresh Tracks channel history.

### Role Management System
Flexible tagging system for assigning roles/designations to members (board positions, coach tiers, trip leads, etc.).

**Tag Model Enhancements (PR #110):**
- `emoji` - Single emoji character for compact display (e.g., '🎿', '⭐', '🏔️')
- `gradient` - CSS gradient string for visual badge styling (e.g., 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)')
- Display metadata stored in database rather than hardcoded in frontend
- Migration seeds 18 initial tags with predefined emoji and gradient values

**Admin Interface (`/admin/roles`):**
- Tabulator.js grid with inline editing for all tag properties
- Click any cell to edit: name, display_name, emoji, or gradient
- "Add New Role" button creates new empty row for immediate editing
- Delete button (only enabled if no users assigned to that role)
- Live user count badge shows how many members have each role
- Toast notifications for save/delete operations
- Visual gradient preview renders CSS in-grid for immediate feedback

**Tag Management API Endpoints:**
- `GET /admin/tags/data` - Returns all tags with emoji, gradient, and user counts
- `POST /admin/tags/create` - Create new tag with display metadata
- `POST /admin/tags/<id>/edit` - Update any tag property (name, display_name, emoji, gradient, description)
- `POST /admin/tags/<id>/delete` - Delete tag (only if user_count is 0)
- All endpoints return tag objects including `emoji` and `gradient` fields

**Usage Throughout App:**
- Tags appear as visual badges in member lists and profiles
- Emoji provides compact representation in constrained UI spaces
- Gradient CSS provides distinctive colored badges for different role types
- Many-to-many relationship via UserTag allows users to have multiple roles
- User tags updated via `POST /admin/users/<id>/tags` with `tag_ids` array

**Template:** `app/templates/admin/roles.html` (contains inline JavaScript for Tabulator grid)

### Slack Channel Sync
Automated synchronization of Slack workspace roles and channel memberships based on member status.

**Module:** `app/slack/channel_sync.py`
- Manages three member tiers: full_member (ACTIVE), multi_channel_guest (ALUMNI 1 season), single_channel_guest (ALUMNI 2+ seasons)
- Handles role changes, channel additions/removals, user invites, and reactivations
- Preserves manually-joined public channels for full members
- Respects exception tags (admins, board members, exempt users)

**Configuration:** `config/slack_channels.yaml` defines tier-specific channel lists and exception tags

**Background Execution Pattern:**
- Sync runs in background thread to avoid Gunicorn worker timeout (30s limit)
- POST request returns immediately with "started" status
- Frontend polls result endpoint every 1 second (max 2 minutes)
- Only one sync can run at a time (returns 409 if already running)

**Admin Endpoints:**
- `GET /admin/channel-sync` - Channel sync dashboard UI
- `GET /admin/channel-sync/status` - Config validation, credentials check, scheduler status
- `POST /admin/channel-sync/run` - Start sync in background (returns immediately)
- `GET /admin/channel-sync/result` - Poll for sync status/results (running/completed/error/idle)
- `POST /admin/channel-sync/expertvoice` - Run ExpertVoice sync only

**Integration:** Can optionally trigger ExpertVoice sync via `include_expertvoice` parameter

**Environment Variables Required:**
- `SLACK_ADMIN_TOKEN` - Admin user token (xoxs-...) from browser session
- `SLACK_YOUR_COOKIE` - Browser session cookie (d=xoxd-...)
- `SLACK_YOUR_X_ID` - Browser x-id value for API requests
- `SLACK_BOT_TOKEN` - Bot token for channel/user API calls (existing)

**Key Modules:**
- `app/slack/admin_api.py` - Undocumented Slack admin API wrapper (role changes, invites, reactivation)
  - `change_user_role()` - Set user to Full Member / MCG / SCG
  - `invite_user_by_email()` - Invite new members to workspace
  - `validate_admin_credentials()` - Test cookie-based auth
  - Uses cookie-based authentication (not official Slack API)
  - Retry with exponential backoff for resilience
  - Raises `CookieExpiredError` if cookies expire (aborts sync)

**Safety Features:**
- Dry-run mode enabled by default in config
- Cookie expiration detection aborts sync
- Preserves manually-joined public channels for full members
- Detailed trace logging with database state
- Exception users skipped (board members, admins, exempt)

### Background Job Scheduling
APScheduler integration for automated background tasks within the web process.

**Module:** `app/scheduler.py`

**Architecture:**
- **BackgroundScheduler:** Runs jobs in thread pool alongside web requests (no separate worker process needed)
- **Single-Worker Guard:** File lock (`/tmp/tcsc_scheduler.lock`) ensures only one Gunicorn worker runs jobs
- **Automatic Cleanup:** Lock released on shutdown via `atexit` hooks
- **Development Safety:** Skips reloader parent process to avoid duplicates

**Scheduled Jobs:**
- **Slack Channel Sync:** Daily at 3am US Central (`America/Chicago` timezone)
  - Runs `run_channel_sync()` from `app/slack/channel_sync.py`
  - Also triggers `sync_expertvoice()` in same job
  - Misfire grace time: 1 hour (catches up if server was down)

**Key Functions:**
- `init_scheduler(app)` - Initialize and start scheduler (called from `app/__init__.py`)
- `get_scheduler_status()` - Get running status and job list for admin UI
- `trigger_channel_sync_now(app)` - Manually trigger sync job on-demand
- `is_main_worker()` - File lock check for single-worker guard
- `run_channel_sync_job(app)` - Job function that runs both Slack sync and ExpertVoice sync

**Scheduler Status:**
- Integrated into `GET /admin/channel-sync/status` endpoint
- Shows running state, registered jobs, next run times
- Used by admin dashboard to display schedule information

**Deployment Considerations:**
- Works with Gunicorn multi-worker deployments (single-worker guard prevents duplicates)
- Scheduler starts only in the first worker that acquires the lock
- If main worker dies, lock is automatically released and another worker can take over
- Jobs run in background threads, not blocking web requests

### ExpertVoice Integration
SFTP-based member sync for ExpertVoice pro deals access.

**Module:** `app/integrations/expertvoice.py`

**Purpose:** Syncs eligible members to ExpertVoice partner portal for equipment pro deals. ExpertVoice provides discounted pricing on ski equipment to club members.

**Eligibility Criteria:**
- `ACTIVE` members (current season, `seasons_since_active == 0`)
- `ALUMNI` members with `seasons_since_active == 1` (one season gap, still eligible)
- Members inactive 2+ seasons are NOT eligible

**Sync Process:**
1. Query database for eligible members using `get_eligible_members()`
2. Generate CSV file with format: `EmployeeID,FirstName,LastName`
   - EmployeeID = member email (unique identifier)
   - Uses member's first_name and last_name from User model
3. Upload CSV via SFTP to ExpertVoice incoming directory
4. Return `ExpertVoiceSyncResult` with statistics

**Configuration:**
- Defined in `config/slack_channels.yaml` under `expertvoice` section
- `enabled: true/false` - Feature flag to disable sync entirely
- SFTP settings: host, port, path, filename
- Shares same `dry_run` flag as Slack channel sync

**Environment Variables:**
- `EXPERTVOICE_SFTP_USERNAME` - SFTP username
- `EXPERTVOICE_SFTP_PASSWORD` - SFTP password

**Key Functions:**
- `sync_expertvoice(dry_run)` - Main entry point, returns `ExpertVoiceSyncResult`
- `get_eligible_members()` - Query database for ACTIVE or ALUMNI (1 season) users
- `generate_csv(members, output_path)` - Generate CSV file in temp location
- `upload_csv(file_path, config, dry_run)` - Upload via Paramiko SFTP client

**Integration Points:**
1. **Scheduled Sync:** Runs daily at 3am via APScheduler (after Slack sync completes)
2. **Manual Trigger:** `POST /admin/channel-sync/expertvoice` endpoint
3. **Combined Sync:** Included in `POST /admin/channel-sync/run` if `include_expertvoice: true`

**Error Handling:**
- Returns result object with errors list (sync continues even if errors occur)
- Missing credentials logged as configuration error
- SFTP connection failures logged with details
- Dry-run mode skips actual upload but generates CSV for validation

## Configuration

### Environment Variables Required
Check `.env.example` for complete list. Critical variables include:

**Core Application:**
- `FLASK_SECRET_KEY` - Flask session security
- `FLASK_ENV` - Environment (development/production/testing)
- `DATABASE_URL` - PostgreSQL connection string (falls back to SQLite if not set)

**Payment Processing:**
- `STRIPE_PUBLISHABLE_KEY` / `STRIPE_SECRET_KEY` - Stripe API keys
- `STRIPE_WEBHOOK_SECRET` - Webhook signing secret

**Authentication:**
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - Admin OAuth credentials

**Slack Integration:**
- `SLACK_WEBHOOK_URL` - Payment notification webhook (optional)
- `SLACK_BOT_TOKEN` - Bot token for user/channel API calls (xoxb-...)
- `SLACK_ADMIN_TOKEN` - Admin user token for channel sync (xoxs-...)
- `SLACK_YOUR_COOKIE` - Browser session cookie for admin APIs (d=xoxd-...)
- `SLACK_YOUR_X_ID` - Browser x-id value for admin APIs

**ExpertVoice Integration:**
- `EXPERTVOICE_SFTP_USERNAME` - SFTP username for pro deals sync
- `EXPERTVOICE_SFTP_PASSWORD` - SFTP password

**Optional:**
- `GOOGLE_PLACES_API_KEY` - Address autocomplete on forms
- `FINANCE_AUTHORIZED_EMAILS` - Comma-separated list of emails with payment visibility

### Deployment
- **Production Server:** Configured for Gunicorn (see `Procfile`)
- **Database:** PostgreSQL on Render via `DATABASE_URL` env var (falls back to SQLite if not set)

## Business Logic Notes

### Trip Registration System
- **Public Interface:** Users browse active trips and register with payment authorization
- **Admin Interface:** Manage trips, seasons, users, and payment captures
- **Lottery System:** New members go into lottery; payment holds allow selective acceptance

### Social Events System
- **SocialEvent model:** Mirrors trips but with simplified single-price tier
- **Immediate capture:** Uses `capture_method='automatic'` (no lottery/holds)
- **Homepage display:** Appears alongside trips with "Social Event" badge
- **Admin CRUD:** Full management at `/admin/social-events`

### Season Management
- **Registration Windows:** Separate periods for returning vs new members
- **Member Status Tracking:** Users can be PENDING_LOTTERY, ACTIVE, or DROPPED per season
- **Historical Data:** Former member verification by email lookup
- **API Endpoint:** `POST /api/is_returning_member` - Frontend can check member status by email

### Status Fields (Two Levels)
- **User.status** (global, derived): `PENDING`, `ACTIVE`, `ALUMNI`, `DROPPED`
  - Computed via `User.derived_status` property based on current season's UserSeason
  - Synced via `User.sync_status()` method
- **UserSeason.status** (per-season):
  - `PENDING_LOTTERY` - Awaiting lottery
  - `ACTIVE` - Accepted member
  - `DROPPED_LOTTERY` - Lost lottery (gets priority next time)
  - `DROPPED_VOLUNTARY` - Withdrew by choice
  - `DROPPED_CAUSE` - Removed for cause

### Current Season
- **Season.is_current** flag designates the active season (only one at a time)
- **Season.get_current()** class method returns the current season
- **Admin "Activate Season"** action syncs all user statuses when season changes

### Data Conventions
- **Prices:** Stored in cents (e.g., $50.00 = 5000), converted from dollars on form input
- **Timestamps:** UTC in database, displayed in US Central (America/Chicago)
- **Member type:** Derived property (`User.is_returning`), not stored as a column
- **Status fields:** Stored as plain strings in database (e.g., `'ACTIVE'`, `'PENDING_LOTTERY'`)
  - `UserStatus` and `UserSeasonStatus` in `constants.py` are simple classes, NOT Python Enums
  - Do NOT call `.value` on status fields - they are already strings
  - Only `MemberType` is a true Enum with `.value` attribute

### Slack Tier Logic
Used for determining member access level in club Slack workspace:

| User.status | seasons_since_active | Slack Tier |
|-------------|---------------------|------------|
| ACTIVE | 0 | full_member |
| ALUMNI | 1 | multi_channel_guest |
| ALUMNI | 2+ | single_channel_guest |
| PENDING/DROPPED | — | None |

## Important Files
- **Product Specification:** `.cursor/rules/tcsc_registration_spec.mdc` contains detailed business requirements
- **Contributing Guide:** `CONTRIBUTING.md` explains User/UserSeason model and member type logic
- **Constants:** `app/constants.py` - Status constants (`UserStatus`, `UserSeasonStatus` classes), `StripeEvent` types, `PaymentType`, `MemberType` enum
- **Admin Templates:**
  - `app/templates/admin/roles.html` - Role management UI with inline Tabulator grid
  - `app/templates/admin/channel_sync.html` - Channel sync dashboard UI
  - Other admin templates in `app/templates/admin/` subdirectory
- **Admin JS:**
  - `app/static/admin_users.js` - Member management Tabulator grid
  - `app/static/admin_payments.js` - Payment management Tabulator grid
  - `app/static/admin_slack.js` - Slack user sync Tabulator grid
- **Slack Integration:**
  - `app/slack/channel_sync.py` - Main channel sync orchestration
  - `app/slack/admin_api.py` - Undocumented Slack admin APIs (cookie-based)
  - `app/slack/client.py` - Slack WebClient wrapper
  - `app/slack/sync.py` - User sync service
- **Background Jobs:**
  - `app/scheduler.py` - APScheduler setup with single-worker guard
- **Integrations:**
  - `app/integrations/expertvoice.py` - ExpertVoice SFTP sync
- **Configuration:**
  - `config/slack_channels.yaml` - Channel sync configuration and tier definitions
- **Static Assets:** CSS organized in modular structure under `app/static/css/styles/`
- **Templates:** Jinja2 templates in `app/templates/` with admin-specific subdirectory