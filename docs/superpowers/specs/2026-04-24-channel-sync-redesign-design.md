# Channel Sync Redesign

**Date:** 2026-04-24
**Status:** Revised 2026-05-11
**Stakeholders:** Rob, Alex Gude, Augie Witkowski, Ellie Thorsgaard

## Problem

The current Slack channel sync system uses a simple time-based tier model: ACTIVE members get full access, 1-season alumni become multi-channel guests (MCG), and 2+ season alumni become single-channel guests (SCG). This creates two issues:

1. **Engaged alumni lose access** — A 2+ season alumni who is actively using Slack (chatting in book club, participating in community channels) gets demoted to SCG with one channel. This hurts community retention.
2. **Channel structure is confusing** — `announcements-adventures` vs `announcements-tcsc` is unclear. Trip, apparel, and adventure content is split across channels with no obvious distinction. (Resolved out-of-band by renaming `announcements-tcsc` → `announcements-general` and archiving `announcements-adventures`. This spec reflects the new names.)
3. **No path back** — Once demoted to SCG, alumni have no self-service way to regain access. They need manual admin intervention.
4. **250 paid seat limit** — Currently 223/250. All MCGs count as paid seats. We need a mechanism to keep the MCG pool limited to people who are actually engaged.

## Design

### Channel Structure

Out-of-band changes already made:
- `announcements-adventures` archived.
- The original `announcements-tcsc` was renamed to `announcements-general`, then re-purposed: that channel was renamed again to **`welcome-to-tcsc`** (public, workspace-default, contains everyone) and a **new** `announcements-general` was created as a **private** channel for the full_member tier. Existing messages from the old channel were migrated to the new private one.
- New `announcements-alumni` channel created (`C0B2ZQ4KM0E`) for alumni-tier announcements.

Announcement channels by audience:

| Channel | Audience | Content | Posting permissions |
|---|---|---|---|
| `welcome-to-tcsc` (public) | full_member + MCG (the sync re-adds them if they fall out). SCG users are NOT added — they're isolated to the reactivation channel. | Public landing/orientation channel | Board only |
| `announcements-general` (private) | full_member only | Members-only announcements: trips, adventures, apparel, seasonal info, club news | Board members only |
| `announcements-practices` | full_member only | Practice schedules, workouts, RSVPs | Board/coaches |
| `announcements-alumni` (C0B2ZQ4KM0E) | MCG only | Alumni-facing announcements (re-engagement, alumni events, club news appropriate for non-members) | Rob, president, and vice president only |
| `tcsc-reactivate-me` (C0AUQCG7UB1) | SCG only + Rob + president | Reactivation workflow | Board only (SCGs interact via workflow) |

**Why `announcements-general` was made private:** the old public channel forced every workspace member to be in it, defeating tier separation. A private channel lets the sync manage membership precisely — only full_members are added.

Community channels (chat, gear-recs-swap, extra-training-fun, races-information, meme, photos-videos, race-waxing, fresh-tracks, volunteer-and-job-opportunities) remain shared between full_member and MCG tiers.

**Prerequisite:** the TCSC bot must be added to the private `announcements-general` before the sync runs. Otherwise the channel-name→ID lookup fails silently and full_members will not be added to the channel. Same applies to `announcements-alumni` and `tcsc-reactivate-me`.

**Full channel-to-tier mapping:**

| Channel | full_member | MCG | SCG |
|---|---|---|---|
| `welcome-to-tcsc` | yes | yes | no |
| `announcements-general` | yes | no | no |
| `announcements-practices` | yes | no | no |
| `announcements-alumni` | no | yes | no |
| `chat` | yes | yes | no |
| `fresh-tracks` | yes | yes | no |
| `gear-recs-swap` | yes | yes | no |
| `races-information` | yes | yes | no |
| `volunteer-and-job-opportunities` | yes | yes | no |
| `extra-training-fun` | yes | yes | no |
| `meme` | yes | yes | no |
| `photos-videos` | yes | yes | no |
| `race-waxing` | yes | yes | no |
| `tcsc-reactivate-me` | no | no | yes |

### Tier Logic

Updated `User.get_slack_tier()` rules:

```
Coach override (HEAD_COACH, ASSISTANT_COACH tags) → full_member
ACTIVE status → full_member
ALUMNI + seasons_since_active == 1 → multi_channel_guest
ALUMNI + seasons_since_active >= 2 + last_slack_activity within 90 days → multi_channel_guest
ALUMNI + seasons_since_active >= 2 + last_slack_activity older than 90 days → single_channel_guest
PENDING / DROPPED → None (no Slack automation)
```

**Exception tags** (`BOARD_MEMBER`, `ADMIN`, `EXEMPT`, from `exception_tags` in `slack_channels.yaml`): users with any of these tags are skipped entirely by the sync — they keep whatever Slack status they currently have regardless of DB state. Unchanged from existing behavior.

**PENDING during lottery window:** A new member who registers but has not yet been admitted to ACTIVE has `User.status == PENDING`. `get_slack_tier()` returns `None`, so the sync ignores them. They get no Slack access during the lottery window. Unchanged from existing behavior.

Three paths to MCG for 2+ season alumni:
1. **Still active on Slack** — `last_slack_activity` within 90 days, stays MCG automatically
2. **Self-service reactivation** — SCG clicks workflow in `tcsc-reactivate-me`, promoted to MCG
3. **Re-registers for a season** — becomes ACTIVE/full_member via normal registration flow

Demotion cycle: any MCG whose `last_slack_activity` exceeds 90 days is demoted to SCG during the daily sync. This includes previously-reactivated users who went quiet again.

### Activity Detection

**Data source:** Slack admin analytics API (`admin.analytics.getMemberAnalytics`) — same data that powers the admin analytics page at `https://app.slack.com/manage/<team_id>/analytics`. Accessed via the existing cookie-based admin API auth in `admin_api.py`.

**Endpoint contract (verified by `scripts/probe_slack_activity.py` on 2026-05-11):**

Two-call sequence. Both endpoints require the `_x_app_name=manage` form parameter in addition to the usual auth params used by `make_admin_request`.

1. **`POST admin.analytics.getAvailableDateRange`** — returns the date window the analytics index covers (typically lags today by ~1 day):
   - Required form fields: `token`, `type=member`, `_x_reason=fetchMembersDataAvailableDateRange`, `_x_mode=online`, `_x_app_name=manage`
   - Response: `{ok: true, start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD", date_last_updated, date_last_indexed}`
   - Only `type` values that the endpoint accepts: `member`, `channel`, `huddle`. Anything else returns `invalid_arguments`. We always pass `type=member`.

2. **`POST admin.analytics.getMemberAnalytics`** — returns per-member analytics rows for the requested window:
   - Required form fields: `token`, `start_date`, `end_date` (both from step 1, NOT today), `count=500`, `sort_column=date_last_active`, `sort_direction=desc`, `query=""`, `_x_reason=loadMembersDataForTimeRange`, `_x_mode=online`, `_x_app_name=manage`
   - The `date_range` shortcut (e.g. `30d`) is only accepted for specific values (`30d` confirmed working, `7d`/`90d`/`365d` rejected). Use explicit `start_date`/`end_date` instead.
   - Response: `{ok: true, num_found: <int>, next_cursor_mark: "<cursor>", member_activity: [...]}`
   - Each `member_activity` row includes (among other fields): `user_id`, `email`, `real_name`, `date_last_active` (Unix timestamp), per-platform variants (`date_last_active_ios/android/desktop`), `days_active`, `messages_posted`, `is_billable_seat`.
   - **The field we care about is `date_last_active`** — an absolute Unix timestamp (seconds, UTC) of the member's most recent activity. It does NOT depend on the window; the window only constrains the activity-count fields like `days_active` and `messages_posted`.
   - Pagination: For the TCSC workspace (~223 members) a single `count=500` page returns everything. If pagination is ever needed, response includes `next_cursor_mark` and the request accepts `cursor_mark` (Solr-style). Loop while `len(all_rows) < num_found`.

**New function:** `fetch_user_activity()` in `admin_api.py` — performs the two-call sequence above, returns a map of `{slack_user_id: datetime}` for every member where `date_last_active > 0`. Members with `date_last_active == 0` (bots, never-onboarded invitees, deactivated users) are omitted from the map, leaving their stored `last_slack_activity` NULL — which the tier logic treats as "no activity signal."

**Storage:** New `last_slack_activity` column (DateTime, nullable) on the `SlackUser` model. Updated during each sync run.

**Integration:** The existing 3am daily `run_channel_sync()` job gets an additional early step:
1. Call `fetch_user_activity()` → get activity map
2. Update `SlackUser.last_slack_activity` for each matched user and commit to DB
3. Proceed with existing sync logic — `get_slack_tier()` now uses the updated activity data

**Activity backfill is NOT gated by `dry_run`.** Writing `last_slack_activity` to our own DB is safe regardless. Only the downstream Slack API calls (`change_user_role`, etc.) honor `dry_run`. This makes the first production run trivially safe: run with `dry_run=true`, activity gets backfilled, proposed tier changes are logged without acting, human reviews the log, then flip `dry_run=false`.

**90-day threshold:** Configurable via `activity_threshold_days` in `config/slack_channels.yaml`. Default: 90.

**Failure handling:** If the admin API activity fetch fails (cookies expired, network error), the sync continues using the last-stored `last_slack_activity` values. No mass demotions on transient failures. A warning is logged. On the very first run (before any activity has ever been stored), a fetch failure means everyone with `seasons_since_active >= 2` would route to SCG. Mitigation: the first run is `dry_run=true` and the sequence below requires verifying activity data was successfully populated before flipping to live mode.

### Reactivation Workflow

**Mechanism:** Slack Custom Steps (Custom Functions) via Bolt.

**Slack App Manifest changes:**
- Add `function_executed` to bot event subscriptions
- Set `org_deploy_enabled: true` and `function_runtime: remote`
- Define `reactivate_membership` function with `user_id` input parameter (type `slack#/types/user_id`)

**Bolt handler:** New `@bolt_app.function("reactivate_membership")` handler in `bolt_app.py`:
1. Receives triggering user's Slack ID via `inputs["user_id"]`
2. Looks up user by Slack ID → finds linked `User` record
3. Validates they are currently SCG and 2+ season alumni
4. Calls `change_user_role()` to promote SCG → MCG with standard MCG channel list
5. Sends webhook notification to registration team channel
6. Calls `complete()` to signal success back to the workflow

**Workflow Builder setup** (manual, done by Rob):
- Add the app's "Reactivate Membership" custom step to the existing workflow in `tcsc-reactivate-me`
- Map "Person who used this workflow" → `user_id` input parameter

### Private Channel Preservation

When transitioning full_member → MCG, private channel memberships should be preserved (e.g., book club, soccer team, Lake Placid).

**Prerequisite:** The bot must be a member of any private channel it needs to detect. Channel owners opt in by adding the bot — no centralized config list needed.

**Sync logic change** in `sync_single_user()`:
1. Before calling `change_user_role()` for MCG, fetch the user's current channels via `get_user_channels()` (already queries both public and private channels)
2. Identify channels not in the managed config (these are the private/community channels to preserve)
3. Merge those channel IDs into the MCG channel list
4. Pass the combined list to `change_user_role()`

When transitioning MCG → SCG, no preservation — they lose all channels and get only `tcsc-reactivate-me`.

### Logging & Notifications

Two notification modes, controlled by config:

**1. End-of-sync summary (always on for live runs, gated off for dry-runs):** At the end of `run_channel_sync()`, post a single webhook message summarizing the run. Built from the in-memory `ChannelSyncResult` (already accumulating counts and traces during the run). Example:

> Channel sync complete (live):
> • Role changes: 67
> • Channel additions: 12
> • Channel removals: 8
> • Invites: 3
> • Errors: 0

Note: As initially built, `ChannelSyncResult.role_changes` is a single counter across all directions (full_member promotions, MCG demotions, SCG demotions). Splitting that into per-tier counters (`promoted_full_member`, `demoted_mcg`, `demoted_scg`, `reactivated_mcg`) would produce a more actionable summary but requires structural changes to `ChannelSyncResult` and every role-change site. **Follow-up:** add per-tier counters when there's appetite.

Reactivations triggered by the Workflow Builder custom step also post a separate immediate notification (they're user-initiated, infrequent, and operationally interesting).

Dry-runs do NOT post a summary — the 3am scheduled job runs in dry-run mode during the validation window before going live, and we don't want a daily ops-channel ping for no-op runs.

**2. Per-transition notifications (off by default):** Controlled by `notify_per_transition: false` in `slack_channels.yaml`. When enabled, fires one webhook per transition with name/email/from→to/reason. Useful for debugging or low-volume periods, not for the first run.

This avoids flooding the channel and tripping Slack webhook rate limits on the first run, which is expected to be the highest-volume sync.

Uses the existing `SLACK_WEBHOOK_URL` pattern from `app/notifications/slack.py`. The webhook URL may point to the same channel as payment notifications or a separate registration-team channel — to be configured via environment variable or `slack_channels.yaml`.

### Config Changes

**`config/slack_channels.yaml` updates:**

```yaml
channels:
  full_member:
    - "welcome-to-tcsc"
    - "announcements-general"
    - "announcements-practices"
    - "chat"
    - "fresh-tracks"
    - "gear-recs-swap"
    - "races-information"
    - "volunteer-and-job-opportunities"
    - "extra-training-fun"
    - "meme"
    - "photos-videos"
    - "race-waxing"

  multi_channel_guest:
    - "welcome-to-tcsc"
    - "announcements-alumni"
    - "chat"
    - "fresh-tracks"
    - "gear-recs-swap"
    - "races-information"
    - "volunteer-and-job-opportunities"
    - "extra-training-fun"
    - "meme"
    - "photos-videos"
    - "race-waxing"

  single_channel_guest:
    - "tcsc-reactivate-me"

# Activity-based tier check for 2+ season alumni
activity_threshold_days: 90

# Channel for SCG reactivation workflow
reactivation_channel: "tcsc-reactivate-me"
reactivation_channel_id: "C0AUQCG7UB1"

# Notifications: end-of-sync summary always posts. Per-transition pings are
# off by default to avoid flooding the channel on large runs (e.g. the first
# run after season activation).
notify_per_transition: false

# Private community channels where the bot has been added to enable
# membership preservation on full_member → MCG transitions. Listed here for
# record-keeping; the sync auto-detects any private channel the bot is in.
# Channels not in this list (or not granted bot access) will lose alumni
# members on the transition.
known_private_channels:
  # - "book-club"
  # - "soccer"
  # - "lake-placid"
  # (fill in actual list)
```

### Migration Plan

**Sequence (must run in this order):**

0. **Spike — verify activity API.** Run `scripts/probe_slack_activity.py` and confirm we can fetch per-user last-active timestamps. **Hard gate:** do not proceed if this fails.
1. **Manual admin prep:**
   - `tcsc-reactivate-me` channel exists (done — C0AUQCG7UB1)
   - `announcements-adventures` archived (done out-of-band)
   - Old public `announcements-tcsc`/`announcements-general` channel renamed to `welcome-to-tcsc` (public, contains all workspace members; NOT managed by the sync — leave alone)
   - **New private `announcements-general` created**; existing messages migrated from the old public channel; posting permissions board-only; **bot added** so the sync can manage membership
   - `announcements-alumni` created (done — C0B2ZQ4KM0E); Rob, president, and VP added as posters; posting permissions limited to those three; **bot added** (alumni added as channel members by the sync)
   - Bot added to private community channels (best-effort; channels without bot lose alumni members on transition)
   - Slack app manifest updated (`function_executed` event, `reactivate_membership` function)
   - Workflow Builder workflow configured with the custom step
2. **Code deployment with `dry_run: true`:**
   - Migration: add `last_slack_activity` column to `slack_users`
   - `admin_api.py`: add `fetch_user_activity()`
   - `models.py`: add `last_slack_activity` to `SlackUser`, update `get_slack_tier()` with activity logic
   - `slack_channels.yaml`: update channel config (names, new flags)
   - `channel_sync.py`: activity fetch (ungated by dry_run), private channel preservation, end-of-sync summary
   - `bolt_app.py`: `@bolt_app.function("reactivate_membership")` handler
   - `notifications/slack.py`: end-of-sync summary + optional per-transition functions
3. **First dry-run (activity backfill only):** Run sync with `dry_run=true`. Activity data populates DB. Tier changes are logged, not applied. Verify `SlackUser.last_slack_activity` populated for expected number of users.
4. **Activate the new season** via `/admin/seasons/<id>/activate`. DB statuses update, but no Slack changes (sync is still `dry_run=true`).
5. **Second dry-run:** Run sync again. Now the proposed tier changes reflect post-activation state. Review the trace output for surprises.
6. **Human review gate.** Examine the proposed transitions before going live. Look for: anyone unexpectedly going to SCG, board members caught by the sync (shouldn't happen — exception tags), large bulk transitions that don't make sense.
7. **Flip to live:** Update `dry_run: false`, deploy, run sync. End-of-sync summary posts to webhook channel.
8. **Verify live results:** Spot-check 5–10 users in Slack admin to confirm their roles match expected tiers.

**Rollback:**

- **Config rollback:** Revert `slack_channels.yaml` to old config — future syncs revert to old tier behavior. Does NOT undo tier changes already applied in Slack.
- **Manual reversal:** If a sync misclassifies users, use the end-of-sync summary plus the per-run trace logs to identify affected users and write a one-off script that calls `change_user_role()` to restore prior tiers. The `ChannelSyncResult.traces` list records each transition with from/to tiers.
- **Code rollback:** The `last_slack_activity` column and reactivation handler are additive and safe to leave in place if config is rolled back.

### Edge Cases

- **Cookie expiry during activity fetch:** Sync continues with stale `last_slack_activity` data. No demotions from missing data. Warning logged.
- **User not in database:** Treated as SCG (existing behavior, unchanged).
- **Reactivation when near 250 seat limit:** Reactivation proceeds (Slack handles billing). Current paid seat count logged in webhook notification for visibility.
- **User reactivates then goes quiet again:** The 90-day inactivity check applies uniformly. They get demoted back to SCG and can reactivate again.
- **Bot not in a private channel:** User loses access to that private channel on full_member → MCG transition. Channel owners can re-invite, or add the bot to preserve future transitions.
- **1-season alumni with private channels:** MCG tier is automatic. Private channels are preserved via the same merge logic as full_member → MCG transitions.
- **Multiple seasons skipped at once:** `seasons_since_active` jumps from 0 to 2+ on season activation. Activity check applies immediately.
- **Coach tag override:** Coaches always get full_member regardless of registration status or activity. Unchanged.
- **SCG tries to reactivate but isn't 2+ season alumni:** Handler validates status and rejects with a message. Guards against misuse if a non-SCG user somehow accesses the workflow.
- **Exception-tagged users (BOARD_MEMBER/ADMIN/EXEMPT):** Skipped entirely. They retain current Slack status across season activations and tier evaluations. Documented to prevent surprise.
- **Activity probe fails on production but worked in spike:** Sync logs warning, uses stale `last_slack_activity` values. If stale values exist, no mass demotions. If first ever run (no stale values), 2+ alumni would route to SCG — which is why sequence step 3 verifies activity populated before step 7 flips to live.
