# Channel Sync Redesign

**Date:** 2026-04-24
**Status:** Draft
**Stakeholders:** Rob, Alex Gude, Augie Witkowski, Ellie Thorsgaard

## Problem

The current Slack channel sync system uses a simple time-based tier model: ACTIVE members get full access, 1-season alumni become multi-channel guests (MCG), and 2+ season alumni become single-channel guests (SCG). This creates two issues:

1. **Engaged alumni lose access** — A 2+ season alumni who is actively using Slack (chatting in book club, participating in community channels) gets demoted to SCG with one channel. This hurts community retention.
2. **Channel structure is confusing** — `announcements-adventures` vs `announcements-tcsc` is unclear. Trip, apparel, and adventure content is split across channels with no obvious distinction.
3. **No path back** — Once demoted to SCG, alumni have no self-service way to regain access. They need manual admin intervention.
4. **250 paid seat limit** — Currently 223/250. All MCGs count as paid seats. We need a mechanism to keep the MCG pool limited to people who are actually engaged.

## Design

### Channel Structure

Archive `announcements-adventures`. Restructure announcement channels by audience:

| Channel | Audience | Content | Posting permissions |
|---|---|---|---|
| `announcements-tcsc` | full_member + MCG | Trips, adventures, apparel, seasonal info, club news | Board members only |
| `announcements-practices` | full_member only | Practice schedules, workouts, RSVPs | Board/coaches |
| `tcsc-reactivate-me` (C0AUQCG7UB1) | SCG only + Rob + president | Reactivation workflow | Board only (SCGs interact via workflow) |

Community channels (chat, gear-recs-swap, extra-training-fun, races-information, meme, photos-videos, race-waxing, fresh-tracks, volunteer-and-job-opportunities) remain unchanged — available to full_member and MCG tiers.

**Full channel-to-tier mapping:**

| Channel | full_member | MCG | SCG |
|---|---|---|---|
| `announcements-tcsc` | yes | yes | no |
| `announcements-practices` | yes | no | no |
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

Three paths to MCG for 2+ season alumni:
1. **Still active on Slack** — `last_slack_activity` within 90 days, stays MCG automatically
2. **Self-service reactivation** — SCG clicks workflow in `tcsc-reactivate-me`, promoted to MCG
3. **Re-registers for a season** — becomes ACTIVE/full_member via normal registration flow

Demotion cycle: any MCG whose `last_slack_activity` exceeds 90 days is demoted to SCG during the daily sync. This includes previously-reactivated users who went quiet again.

### Activity Detection

**Data source:** Slack admin API at `twincitiesskiclub.slack.com/admin/stats#members` — the "Last active" column. Accessed via the existing cookie-based admin API auth in `admin_api.py`.

**New function:** `fetch_user_activity()` in `admin_api.py` — calls the admin endpoint that powers the stats page, returns a map of `{slack_user_id: last_active_timestamp}`. The exact admin API endpoint (likely `users.admin.list` or a stats-specific endpoint) needs to be discovered during implementation by inspecting the network requests on the admin stats page.

**Storage:** New `last_slack_activity` column (DateTime, nullable) on the `SlackUser` model. Updated during each sync run.

**Integration:** The existing 3am daily `run_channel_sync()` job gets an additional early step:
1. Call `fetch_user_activity()` → get activity map
2. Update `SlackUser.last_slack_activity` for each matched user
3. Proceed with existing sync logic — `get_slack_tier()` now uses the updated activity data

**90-day threshold:** Configurable via `activity_threshold_days` in `config/slack_channels.yaml`. Default: 90.

**Failure handling:** If the admin API activity fetch fails (cookies expired, network error), the sync continues using the last-stored `last_slack_activity` values. No mass demotions on transient failures. A warning is logged.

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

Webhook notifications sent to the registration team channel for tier transitions:
- **Demotion:** "Jane Doe (jane@example.com) demoted MCG → SCG — inactive 90+ days"
- **Reactivation:** "Jane Doe reactivated their account (SCG → MCG)"
- **Role change:** "Jane Doe transitioned full_member → MCG (1 season not registered)"

Uses the existing `SLACK_WEBHOOK_URL` pattern from `app/notifications/slack.py`. The webhook URL may point to the same channel as payment notifications or a separate registration-team channel — to be configured via environment variable or `slack_channels.yaml`.

### Config Changes

**`config/slack_channels.yaml` updates:**

```yaml
channels:
  full_member:
    - "announcements-tcsc"
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
    - "announcements-tcsc"
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
```

### Migration Plan

**One-time admin steps:**
1. Create `tcsc-reactivate-me` channel (done — C0AUQCG7UB1)
2. Archive `announcements-adventures`
3. Confirm `announcements-tcsc` posting permissions are board-only
4. Add the bot to any private community channels that should preserve MCG membership
5. Update Slack app manifest (function_executed event, function definition)
6. Configure workflow in Workflow Builder to use the custom step

**Code deployment order:**
1. Database migration: add `last_slack_activity` column to `slack_users` table
2. `admin_api.py`: add `fetch_user_activity()` function
3. `models.py`: add `last_slack_activity` to `SlackUser`, update `User.get_slack_tier()` with activity logic
4. `slack_channels.yaml`: update channel config
5. `channel_sync.py`: update `sync_single_user()` with private channel preservation and activity fetch integration
6. `bolt_app.py`: add `@bolt_app.function("reactivate_membership")` handler
7. `notifications/slack.py`: add tier transition notification functions
8. Deploy and run first sync in dry-run mode to validate

**Rollback:** Revert `slack_channels.yaml` to the old config and the sync reverts to current behavior. The `last_slack_activity` column and reactivation handler are additive and don't break anything if the config is rolled back.

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
