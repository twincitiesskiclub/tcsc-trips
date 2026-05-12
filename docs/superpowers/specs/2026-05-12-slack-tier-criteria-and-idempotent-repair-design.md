# Slack Tier Criteria + Idempotent Channel Repair — Design

**Date:** 2026-05-12
**Status:** Approved
**Related PRs:** #188 (eea949e), #189 (21f2585), #190 (bff09fc)

## Problem

The 2026-05-12 channel sync wrongly promoted 70+ alumni from `single_channel_guest` (SCG) to `multi_channel_guest` (MCG). Root cause is two interacting bugs:

1. **Stable-tier repair churn.** PR #188 added a branch in `sync_single_user` that calls `change_user_role` every sync for SCG/MCG users whose Slack role already matches the target tier — intended to repair channel membership for users missing the reactivation channel. PR #189 switched the underlying API call from `conversations.invite` to `change_user_role` because the former silently no-ops for restricted users. Side effect: every admin role-change touches Slack's analytics, bumping `date_last_active` for the user even though they took no real action.

2. **Weak tier criterion.** `User.get_slack_tier()` for ALUMNI with `seasons_since_active >= 2` only checks `last_slack_activity < 90 days`. That check is satisfied by the bumped timestamp from bug #1, so on the next sync the user is treated as "active" and promoted to MCG.

Additionally, PR #190 removed `fresh-tracks` from the MCG tier list. The stable-tier repair branch is additive-only ("Don't remove anything for these tiers" — eea949e commit msg), so MCG users currently in `#fresh-tracks` will not be removed.

## Goals

- Stop promoting 2+ season alumni to MCG when the only evidence of activity is `date_last_active` (which our own sync can bump).
- Make stable-tier channel repair idempotent: skip the admin call when channels already match.
- When channels don't match: add missing AND remove extras (so tier-list shrinks like the fresh-tracks change propagate).
- Preserve private-channel membership for MCG (existing guarantee).
- Self-heal the 70+ wrongly-promoted users on next sync without a one-off script.

## Non-Goals

- Reading `activity_threshold_days` from config. There's a pre-existing TODO; keep the hardcoded 90 for this PR.
- Changing full_member tier behavior. Full members can manually join channels; the sync must not remove channels for them.
- Reworking the analytics fetch retry/cache behavior.

## Architecture

```
admin.analytics.getMemberAnalytics
            │
            ▼
fetch_user_activity()  ──► returns dict[slack_uid → {last_active, days_active, messages_posted}]
            │
            ▼
channel_sync writes 3 fields to SlackUser  ──► get_slack_tier() reads all 3
                                                        │
                                                        ▼
                                          stable-tier repair branch:
                                          - compute target_set vs current_set
                                          - no diff  → skip (no activity bump)
                                          - else     → change_user_role with
                                                       (target ∪ preserved_private)
```

## Per-Component Detail

### 1. Schema migration

Add two columns to `slack_users`:

```python
op.add_column('slack_users', sa.Column('slack_days_active', sa.Integer(), nullable=True))
op.add_column('slack_users', sa.Column('slack_messages_posted', sa.Integer(), nullable=True))
```

Both nullable so existing rows and analytics-fetch failures don't error. New users start `None` until first analytics fetch populates them.

### 2. `app/slack/admin_api.py` — `fetch_user_activity()`

Change return type from `dict[str, datetime]` to `dict[str, dict]`:

```python
{
    "U07XXX": {
        "last_active": datetime(2026, 5, 12, ...),
        "days_active": 0,
        "messages_posted": 0,
    },
    ...
}
```

The Slack API already returns `days_active` and `messages_posted` in each `member_activity[]` row; this change just parses more of the response. Existing skip rule (`date_last_active <= 0` → omit) stays. New fields default via `member.get('days_active') or 0` and `member.get('messages_posted') or 0`.

### 3. `app/models.py`

Add columns to `SlackUser`:

```python
slack_days_active = db.Column(db.Integer, nullable=True)
slack_messages_posted = db.Column(db.Integer, nullable=True)
```

Update `User.get_slack_tier()` 2+ seasons branch:

```python
else:  # 2+ seasons alumni — require real engagement
    su = self.slack_user
    if (su and su.last_slack_activity
            and (datetime.utcnow() - su.last_slack_activity).days < 90):
        messages = su.slack_messages_posted or 0
        days_active = su.slack_days_active or 0
        if messages >= 1 or days_active >= 3:
            return 'multi_channel_guest'
    return 'single_channel_guest'
```

The pre-existing `# TODO: read threshold from config activity_threshold_days` comment stays; that refactor is out of scope.

### 4. `app/slack/channel_sync.py`

**4a. Activity backfill** (around line 699) — write all three fields:

```python
activity_map = fetch_user_activity()
if activity_map:
    for slack_user_record in SlackUser.query.all():
        if slack_user_record.slack_uid in activity_map:
            a = activity_map[slack_user_record.slack_uid]
            slack_user_record.last_slack_activity = a['last_active']
            slack_user_record.slack_days_active = a['days_active']
            slack_user_record.slack_messages_posted = a['messages_posted']
    db.session.commit()
```

**4b. Stable-tier repair branches** in `sync_single_user` (SCG and MCG paths added in PR #188/#189) — replace blind `change_user_role` with diff-then-act:

```python
target_channels = set(config['channels'][tier])
target_channel_ids = {channel_name_to_id[c] for c in target_channels if c in channel_name_to_id}

current_managed = current_channel_ids & managed_channel_ids
preserved_private = current_channel_ids - managed_channel_ids  # MCG only — SCG has no privates by definition

final_target = target_channel_ids | preserved_private

if current_channel_ids == final_target:
    logger.info(f"Stable-tier no-op: channels match target for {email}")
    return  # critical: no change_user_role call, no activity bump

# Diff exists — apply via change_user_role with the full final_target
change_user_role(slack_uid, tier, list(final_target))
added = final_target - current_channel_ids
removed = current_channel_ids - final_target
logger.info(f"Stable-tier repair for {email}: +{added} -{removed}")
```

This single block achieves all four behaviors required:

- Skips the admin call when channels already match (kills churn for users whose state is correct)
- Adds missing channels (original PR #188 case: SCGs missing `tcsc-reactivate-me`)
- Removes channels no longer in the tier list (fresh-tracks case for MCG)
- Preserves private channels for MCG (existing guarantee)

The same logic is applied identically to both SCG and MCG stable-tier branches; SCG's `preserved_private` set will be empty in practice (single-channel guests don't get into private channels), so the math degenerates to `final_target == target_channel_ids` for them.

### 5. Tests

`tests/slack/test_tier_logic.py`:

- Extend `FakeSlackUser` to include `slack_days_active` and `slack_messages_posted` fields.
- Update `get_slack_tier_under_test()` to mirror the new criterion.
- Add cases:
  - 2+ alumni, last_active within 90d, messages=0, days_active=1 → SCG (the bug)
  - 2+ alumni, last_active within 90d, messages=1, days_active=1 → MCG
  - 2+ alumni, last_active within 90d, messages=0, days_active=3 → MCG
  - 2+ alumni, last_active within 90d, messages=0, days_active=2 → SCG
  - 2+ alumni, last_active 100d ago, messages=10 → SCG (window beats activity counts)

`tests/slack/test_channel_sync.py`:

- Stable-tier MCG, current_channels == target → assert `change_user_role` NOT called.
- Stable-tier MCG, current missing one target channel → assert `change_user_role` called with full target set + preserved privates.
- Stable-tier MCG, current has an extra managed channel not in target list (e.g., `fresh-tracks` after removal) → assert `change_user_role` called, extra removed, privates preserved.
- Stable-tier SCG, current missing `tcsc-reactivate-me` → assert `change_user_role` called.
- Stable-tier SCG, current matches target → assert `change_user_role` NOT called.

Existing tests for PR #188/#189 may need adjustment since they were written against the always-call behavior.

### 6. Cleanup (operational, no code)

After deploy + migration:

1. Next scheduled sync (3am daily, or manual trigger) runs `fetch_user_activity` → writes `messages_posted=0, days_active=1` for the 70+ wrongly-promoted users (they have no real engagement; their `days_active=1` reflects only yesterday's role-change-induced bump).
2. Tier evaluation: criterion fails → tier flips MCG → SCG.
3. `change_user_role` fires for the legitimate demotion (real diff, not churn).
4. Bonus: any MCG users still in `#fresh-tracks` get removed in the same operation via the new diff-then-act logic.
5. The demotion bumps `date_last_active` once more, but with `messages_posted=0` the next sync sees `current == target` and skips → loop closed.

## Risks

- **Analytics fetch fails.** If `fetch_user_activity()` returns `{}`, the new columns stay stale. `get_slack_tier()` would use yesterday's `slack_messages_posted`/`slack_days_active` from the DB, which is acceptable (degrades to old-snapshot behavior, not catastrophic).
- **First sync after deploy.** Existing rows have `slack_messages_posted=NULL, slack_days_active=NULL` until analytics backfill runs. The `or 0` defaults in `get_slack_tier()` mean these users would all be treated as inactive (SCG) until analytics writes real values. Since the analytics backfill runs before tier evaluation in the same sync run (lines 699-712), this is a non-issue in practice.
- **`change_user_role` semantics.** Calling it with `target ∪ preserved_private` replaces the user's channel set with that union. If Slack's API has surprising behavior when the union is identical to current (e.g., still bumps activity), the `current == final_target` short-circuit prevents that call entirely, so we're safe.

## Out of Scope

- Reading `activity_threshold_days` from `config/slack_channels.yaml` instead of hardcoded 90.
- Adding `reactions_added` as a third activity signal.
- Refactoring `sync_single_user` to extract the diff logic into a reusable helper (could be a follow-up).
- Backfilling historic `messages_posted` / `days_active` for users not in the current analytics window.
