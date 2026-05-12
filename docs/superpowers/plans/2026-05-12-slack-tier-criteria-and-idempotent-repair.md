# Slack Tier Criteria + Idempotent Channel Repair — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop wrongly promoting 2+ season alumni from SCG to MCG when the only evidence of "activity" is our own `change_user_role` admin call bumping `date_last_active`. Make stable-tier channel repair idempotent (skip when channels match) and bidirectional (remove extras, not just add missing) so tier-list shrinks like the fresh-tracks removal actually propagate.

**Architecture:** Two new analytics columns on `slack_users` (`slack_days_active`, `slack_messages_posted`). `fetch_user_activity()` returns a richer dict including those fields; the channel sync writes all three during the activity backfill. `User.get_slack_tier()` requires real engagement (`messages_posted >= 1 OR days_active >= 3`) on top of the existing 90-day window. The stable-tier MCG/SCG repair branches in `sync_single_user` compute target vs. current and skip the admin call when they match; otherwise call `change_user_role` with `target ∪ preserved_private`.

**Tech Stack:** Python 3.12, Flask, SQLAlchemy, Alembic, PostgreSQL, pytest. Slack admin API (cookie-based). Spec: `docs/superpowers/specs/2026-05-12-slack-tier-criteria-and-idempotent-repair-design.md`.

**Branch / PR:** Work on `fix/slack-tier-real-engagement` branched from `main`. Ship as a single PR.

---

## Task 1: Create the feature branch

**Files:** none (git only)

- [ ] **Step 1: Verify clean tree on main**

Run: `git status && git branch --show-current`
Expected: branch is `main`. Untracked files are fine; modified `.gitignore` is fine.

- [ ] **Step 2: Create + switch to feature branch**

```bash
git checkout -b fix/slack-tier-real-engagement
```

Expected: `Switched to a new branch 'fix/slack-tier-real-engagement'`

---

## Task 2: Alembic migration — add `slack_days_active` and `slack_messages_posted`

**Files:**
- Create: `migrations/versions/a7c3f9d2e1b8_add_slack_activity_metrics_to_slack_users.py`

Current Alembic head is `b62e16189188_add_last_slack_activity_to_slack_users.py` (revision `b62e16189188`). The new migration chains from it.

- [ ] **Step 1: Create the migration file**

Write exactly:

```python
"""add slack activity metrics to slack_users

Revision ID: a7c3f9d2e1b8
Revises: b62e16189188
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7c3f9d2e1b8'
down_revision = 'b62e16189188'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('slack_users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('slack_days_active', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('slack_messages_posted', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('slack_users', schema=None) as batch_op:
        batch_op.drop_column('slack_messages_posted')
        batch_op.drop_column('slack_days_active')
```

- [ ] **Step 2: Run the migration locally**

The dev DB must be running. If `./scripts/dev.sh` isn't already up:

```bash
docker start tcsc-postgres 2>/dev/null || true
```

Then:

```bash
source env/bin/activate
export DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
flask db upgrade
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade b62e16189188 -> a7c3f9d2e1b8, add slack activity metrics to slack_users`

- [ ] **Step 3: Verify columns exist**

```bash
docker exec tcsc-postgres psql -U tcsc -d tcsc_trips -c "\d slack_users" | grep -E 'slack_days_active|slack_messages_posted'
```

Expected: two lines showing both columns as `integer` and nullable.

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/a7c3f9d2e1b8_add_slack_activity_metrics_to_slack_users.py
git commit -m "$(cat <<'EOF'
feat: add slack activity metrics columns to slack_users

Adds slack_days_active and slack_messages_posted to track real
engagement signals from admin.analytics.getMemberAnalytics. Used by
the upcoming get_slack_tier() change to gate 2+ season alumni MCG
eligibility against actual user activity (vs. our own admin-call-
induced date_last_active bumps).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add columns to the `SlackUser` model

**Files:**
- Modify: `app/models.py:107-127` (SlackUser class)

- [ ] **Step 1: Add the two columns**

In `app/models.py`, find the `SlackUser` class. After this existing line:

```python
    last_slack_activity = db.Column(db.DateTime, nullable=True)
```

Add the two new columns immediately after:

```python
    last_slack_activity = db.Column(db.DateTime, nullable=True)
    slack_days_active = db.Column(db.Integer, nullable=True)
    slack_messages_posted = db.Column(db.Integer, nullable=True)
```

- [ ] **Step 2: Smoke-test the import**

Run:

```bash
source env/bin/activate
export DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
python -c "from app.models import SlackUser; print(SlackUser.__table__.columns.keys())"
```

Expected: a Python list including `'last_slack_activity'`, `'slack_days_active'`, `'slack_messages_posted'`.

- [ ] **Step 3: Commit**

```bash
git add app/models.py
git commit -m "$(cat <<'EOF'
feat: add slack_days_active and slack_messages_posted to SlackUser

Mirrors the migration in a7c3f9d2e1b8. Columns are nullable so existing
rows and analytics-fetch failures degrade gracefully.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Update `User.get_slack_tier()` with the new criterion

**Files:**
- Modify: `app/models.py:227-259` (get_slack_tier method)
- Test: `tests/slack/test_tier_logic.py` (updated in Task 9)

Note: tests for this change land in Task 9. We're modifying the production method first because the FakeUser replica in the test file is meant to mirror it. Doing them out of order keeps each commit focused.

- [ ] **Step 1: Update the 2+ seasons branch**

In `app/models.py`, replace the `elif self.status == UserStatus.ALUMNI:` block inside `get_slack_tier()`. The current code (lines 248-257):

```python
        elif self.status == UserStatus.ALUMNI:
            if self.seasons_since_active == 1:
                return 'multi_channel_guest'
            else:  # 2+ seasons alumni — check activity
                # TODO: read threshold from config activity_threshold_days (currently hardcoded 90)
                if (self.slack_user
                        and self.slack_user.last_slack_activity
                        and (datetime.utcnow() - self.slack_user.last_slack_activity).days < 90):
                    return 'multi_channel_guest'
                return 'single_channel_guest'
```

Replace with:

```python
        elif self.status == UserStatus.ALUMNI:
            if self.seasons_since_active == 1:
                return 'multi_channel_guest'
            else:  # 2+ seasons alumni — require real engagement, not just analytics presence
                # TODO: read threshold from config activity_threshold_days (currently hardcoded 90)
                su = self.slack_user
                if (su and su.last_slack_activity
                        and (datetime.utcnow() - su.last_slack_activity).days < 90):
                    messages = su.slack_messages_posted or 0
                    days_active = su.slack_days_active or 0
                    if messages >= 1 or days_active >= 3:
                        return 'multi_channel_guest'
                return 'single_channel_guest'
```

The 90-day window check is preserved; the new clause adds the engagement requirement on top.

- [ ] **Step 2: Update the docstring**

In the same method, replace the docstring (lines 228-239) with:

```python
    def get_slack_tier(self):
        """Determine Slack membership tier based on status and activity.

        Override rules (checked first):
        - HEAD_COACH or ASSISTANT_COACH tags -> always full_member

        Standard rules:
        - ACTIVE status -> full_member
        - ALUMNI with seasons_since_active == 1 -> multi_channel_guest
        - ALUMNI with seasons_since_active >= 2 + last_slack_activity within
          90 days + (messages_posted >= 1 OR days_active >= 3) -> multi_channel_guest
        - ALUMNI with seasons_since_active >= 2 + no real engagement -> single_channel_guest
        - PENDING or DROPPED -> None (no Slack automation)
        """
```

- [ ] **Step 3: Smoke-test the import**

```bash
source env/bin/activate
export DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
python -c "from app.models import User; print(User.get_slack_tier.__doc__[:60])"
```

Expected: prints the first ~60 chars of the new docstring.

- [ ] **Step 4: Commit**

```bash
git add app/models.py
git commit -m "$(cat <<'EOF'
feat: require real engagement for 2+ season alumni MCG tier

get_slack_tier now requires messages_posted >= 1 OR days_active >= 3
(on top of the existing 90-day last_slack_activity window) before
classifying 2+ season alumni as multi_channel_guest.

Closes the loop where our own change_user_role admin call bumps
date_last_active, which under the old logic was sufficient by itself
to promote a dormant SCG back to MCG.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Extend `fetch_user_activity()` to return richer dict

**Files:**
- Modify: `app/slack/admin_api.py:358-446` (`fetch_user_activity` function)

- [ ] **Step 1: Update the function**

In `app/slack/admin_api.py`, replace the entire `fetch_user_activity()` function. The current body parses only `date_last_active`; we need to also parse `days_active` and `messages_posted`.

Replace the existing function (starting at `def fetch_user_activity() -> dict[str, datetime]:` through the final `return activity_map` and including the closing newline of the function) with:

```python
def fetch_user_activity() -> dict[str, dict]:
    """Fetch activity metrics for all workspace members.

    Uses Slack's admin analytics API (admin.analytics.getMemberAnalytics).
    Two-call sequence:
      1. getAvailableDateRange to determine the valid window
      2. getMemberAnalytics to retrieve per-member metrics

    Returns:
        Dict mapping Slack user ID -> {
            'last_active': datetime (UTC),
            'days_active': int,
            'messages_posted': int,
        }
        Members with date_last_active <= 0 (bots, never-onboarded) are omitted.
        Returns empty dict on failure (caller uses stale data).
    """
    activity_map: dict[str, dict] = {}

    try:
        creds = get_admin_credentials()
        token = creds['token']

        range_response = make_admin_request(
            api_method='admin.analytics.getAvailableDateRange',
            data={
                'token': token,
                'type': 'member',
                '_x_reason': 'fetchMembersDataAvailableDateRange',
                '_x_mode': 'online',
                '_x_app_name': 'manage',
            },
            action_description='Fetch analytics date range',
            email='(bulk activity fetch)',
        )

        start_date = range_response['start_date']
        end_date = range_response['end_date']

        cursor = ''
        total_expected = None
        rows_seen = 0
        while True:
            data = {
                'token': token,
                'start_date': start_date,
                'end_date': end_date,
                'count': '500',
                'sort_column': 'date_last_active',
                'sort_direction': 'desc',
                'query': '',
                '_x_reason': 'loadMembersDataForTimeRange',
                '_x_mode': 'online',
                '_x_app_name': 'manage',
            }
            if cursor:
                data['cursor_mark'] = cursor

            response = make_admin_request(
                api_method='admin.analytics.getMemberAnalytics',
                data=data,
                action_description='Fetch member analytics',
                email='(bulk activity fetch)',
            )

            member_activity = response.get('member_activity', [])
            rows_seen += len(member_activity)

            for member in member_activity:
                user_id = member.get('user_id')
                ts = member.get('date_last_active') or 0
                if user_id and ts > 0:
                    activity_map[user_id] = {
                        'last_active': datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None),
                        'days_active': int(member.get('days_active') or 0),
                        'messages_posted': int(member.get('messages_posted') or 0),
                    }

            if total_expected is None:
                total_expected = response.get('num_found', 0)

            next_cursor = response.get('next_cursor_mark', '')
            if not next_cursor or next_cursor == cursor:
                break
            if total_expected and rows_seen >= total_expected:
                break
            cursor = next_cursor

        current_app.logger.info(
            f"Fetched activity for {len(activity_map)} of {total_expected or '?'} Slack users"
        )

    except Exception as e:
        current_app.logger.error(f"Failed to fetch user activity: {e}")
        return {}

    return activity_map
```

- [ ] **Step 2: Smoke-test the import (no API calls)**

```bash
source env/bin/activate
export DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
python -c "
from app.slack.admin_api import fetch_user_activity
import inspect
sig = inspect.signature(fetch_user_activity)
print('return annotation:', sig.return_annotation)
"
```

Expected: `return annotation: dict[str, dict]`

- [ ] **Step 3: Commit**

```bash
git add app/slack/admin_api.py
git commit -m "$(cat <<'EOF'
feat: fetch_user_activity returns days_active and messages_posted

Parses the additional metrics Slack already returns in each
member_activity row. Return type changes from dict[str, datetime] to
dict[str, dict] with keys last_active, days_active, messages_posted.
Empty dict on failure preserved.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Update activity backfill in `channel_sync.py` to write all 3 fields

**Files:**
- Modify: `app/slack/channel_sync.py:695-709` (activity backfill block)

- [ ] **Step 1: Update the backfill loop**

In `app/slack/channel_sync.py`, replace the existing block:

```python
        # Activity backfill BEFORE tier evaluation — last_slack_activity values
        # must be written before get_db_email_to_tier() materializes the tier map,
        # because that map is a plain dict[str, str] snapshot from the ORM. Updates
        # after that call don't retroactively affect tier decisions in this sync run.
        activity_map = fetch_user_activity()
        if activity_map:
            for slack_user_record in SlackUser.query.all():
                if slack_user_record.slack_uid in activity_map:
                    slack_user_record.last_slack_activity = activity_map[slack_user_record.slack_uid]
            db.session.commit()
            current_app.logger.info(f"Updated last_slack_activity for {len(activity_map)} users")
        else:
            current_app.logger.warning(
                "Activity fetch returned no data — using stale last_slack_activity values"
            )
```

With:

```python
        # Activity backfill BEFORE tier evaluation — last_slack_activity, days_active,
        # and messages_posted must be written before get_db_email_to_tier() materializes
        # the tier map, because that map is a plain dict[str, str] snapshot from the ORM.
        # Updates after that call don't retroactively affect tier decisions in this sync run.
        activity_map = fetch_user_activity()
        if activity_map:
            for slack_user_record in SlackUser.query.all():
                if slack_user_record.slack_uid in activity_map:
                    a = activity_map[slack_user_record.slack_uid]
                    slack_user_record.last_slack_activity = a['last_active']
                    slack_user_record.slack_days_active = a['days_active']
                    slack_user_record.slack_messages_posted = a['messages_posted']
            db.session.commit()
            current_app.logger.info(f"Updated activity metrics for {len(activity_map)} users")
        else:
            current_app.logger.warning(
                "Activity fetch returned no data — using stale activity metrics"
            )
```

- [ ] **Step 2: Smoke-test the import**

```bash
source env/bin/activate
export DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
python -c "from app.slack.channel_sync import sync_users; print('ok')"
```

Expected: `ok` (no import errors).

- [ ] **Step 3: Commit**

```bash
git add app/slack/channel_sync.py
git commit -m "$(cat <<'EOF'
feat: persist days_active and messages_posted during activity backfill

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Rewrite stable-tier MCG repair to diff-then-act

**Files:**
- Modify: `app/slack/channel_sync.py:519-542` (stable-tier MCG branch in `sync_single_user`)

Current behavior: only fires if there's a channel to ADD. Never removes extras. Always calls `change_user_role` when adding even one, bumping `date_last_active`.

New behavior: compute the full target set (`target ∪ preserved_private`); if it equals the current set, do nothing. Otherwise call `change_user_role` once with the full target set (this both adds missing and removes extras within managed channels).

- [ ] **Step 1: Replace the MCG stable-tier block**

In `app/slack/channel_sync.py`, replace this existing block (currently lines ~519-542):

```python
        elif target_tier == 'multi_channel_guest':
            # MCG no-role-change channel repair: if any managed target channels are
            # missing, re-apply via change_user_role (admin API). conversations.invite
            # silently no-ops on restricted users — only the admin API actually moves
            # them. Preserve private channels via the same merge as the role-change branch.
            channels_to_add = target_channel_ids - current_channels
            if channels_to_add:
                add_names = [channel_id_to_properties.get(cid, {}).get('name', cid) for cid in channels_to_add]
                channels_for_role = set(target_channel_ids)
                private_preserved = current_channels - managed_channel_ids
                if private_preserved:
                    channels_for_role |= private_preserved
                    preserve_names = [channel_id_to_properties.get(cid, {}).get('name', cid) for cid in private_preserved]
                    result.traces.append(f"PRESERVE_PRIVATE: {email} | keeping {preserve_names}")
                result.traces.append(f"CHANNEL_ADD: {email} | +{add_names} | {db_info}")
                change_user_role(
                    user_id=user_id,
                    email=email,
                    target_role=ROLE_MCG,
                    team_id=team_id,
                    dry_run=dry_run,
                    channel_ids=list(channels_for_role)
                )
                result.channel_adds += len(channels_to_add)
```

With:

```python
        elif target_tier == 'multi_channel_guest':
            # MCG stable-tier diff-then-act repair.
            #
            # We must avoid calling change_user_role when channels already match
            # the target. Each admin role-change bumps Slack analytics'
            # date_last_active for the target user, which the tier criterion
            # treats as activity — so a no-op repair would create a churn loop
            # that re-promotes dormant SCGs.
            #
            # When a real diff exists (add OR remove), apply it via a single
            # change_user_role call with target ∪ preserved_private. Slack's
            # admin API replaces the user's managed channel set, so this both
            # adds missing channels and removes extras inside the managed set.
            # Private (unmanaged) channels are preserved by including them in
            # the call.
            private_preserved = current_channels - managed_channel_ids
            final_target = set(target_channel_ids) | private_preserved
            if current_channels != final_target:
                channels_to_add = final_target - current_channels
                channels_to_remove = current_channels - final_target
                if private_preserved:
                    preserve_names = [channel_id_to_properties.get(cid, {}).get('name', cid) for cid in private_preserved]
                    result.traces.append(f"PRESERVE_PRIVATE: {email} | keeping {preserve_names}")
                if channels_to_add:
                    add_names = [channel_id_to_properties.get(cid, {}).get('name', cid) for cid in channels_to_add]
                    result.traces.append(f"CHANNEL_ADD: {email} | +{add_names} | {db_info}")
                if channels_to_remove:
                    remove_names = [channel_id_to_properties.get(cid, {}).get('name', cid) for cid in channels_to_remove]
                    result.traces.append(f"CHANNEL_REMOVE: {email} | -{remove_names} | {db_info}")
                change_user_role(
                    user_id=user_id,
                    email=email,
                    target_role=ROLE_MCG,
                    team_id=team_id,
                    dry_run=dry_run,
                    channel_ids=list(final_target)
                )
                result.channel_adds += len(channels_to_add)
                result.channel_removals += len(channels_to_remove)
```

- [ ] **Step 2: Smoke-test the import**

```bash
source env/bin/activate
export DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
python -c "from app.slack.channel_sync import sync_single_user; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add app/slack/channel_sync.py
git commit -m "$(cat <<'EOF'
fix: idempotent + bidirectional MCG stable-tier channel repair

Previously the stable-tier MCG branch only fired when channels needed
to be ADDED, and called change_user_role unconditionally in that case.
This had two problems:

1. Every call bumped date_last_active in Slack analytics (the bug that
   caused 70+ wrongful SCG->MCG promotions on 2026-05-12).
2. Channels removed from the MCG tier list (e.g. fresh-tracks in PR
   #190) were never removed from users' actual Slack memberships, since
   the branch was additive-only.

The new logic computes target ∪ preserved_private, compares it to
current channels, skips the admin call when they match, and otherwise
applies the full diff (add + remove of managed channels) in a single
change_user_role call.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Rewrite stable-tier SCG repair to diff-then-act

**Files:**
- Modify: `app/slack/channel_sync.py:544-561` (stable-tier SCG branch in `sync_single_user`)

Same idea as MCG, but SCG has no private-channel preservation (ultra-restricted users are confined to the managed channel set by Slack itself).

- [ ] **Step 1: Replace the SCG stable-tier block**

In `app/slack/channel_sync.py`, replace this existing block (currently lines ~544-561):

```python
        elif target_tier == 'single_channel_guest':
            # SCG no-role-change channel repair: if the user is not in the target
            # channel (typically tcsc-reactivate-me), re-apply via change_user_role
            # (admin API). conversations.invite silently no-ops on ultra_restricted
            # users — only the admin API actually moves them.
            channels_to_add = target_channel_ids - current_channels
            if channels_to_add:
                add_names = [channel_id_to_properties.get(cid, {}).get('name', cid) for cid in channels_to_add]
                result.traces.append(f"CHANNEL_ADD: {email} | +{add_names} | {db_info}")
                change_user_role(
                    user_id=user_id,
                    email=email,
                    target_role=ROLE_SCG,
                    team_id=team_id,
                    dry_run=dry_run,
                    channel_ids=list(target_channel_ids)
                )
                result.channel_adds += len(channels_to_add)
```

With:

```python
        elif target_tier == 'single_channel_guest':
            # SCG stable-tier diff-then-act repair. Same idempotency rationale as
            # MCG above. SCG has no private-channel preservation — ultra_restricted
            # users are confined to the managed set by Slack itself.
            final_target = set(target_channel_ids)
            if current_channels != final_target:
                channels_to_add = final_target - current_channels
                channels_to_remove = current_channels - final_target
                if channels_to_add:
                    add_names = [channel_id_to_properties.get(cid, {}).get('name', cid) for cid in channels_to_add]
                    result.traces.append(f"CHANNEL_ADD: {email} | +{add_names} | {db_info}")
                if channels_to_remove:
                    remove_names = [channel_id_to_properties.get(cid, {}).get('name', cid) for cid in channels_to_remove]
                    result.traces.append(f"CHANNEL_REMOVE: {email} | -{remove_names} | {db_info}")
                change_user_role(
                    user_id=user_id,
                    email=email,
                    target_role=ROLE_SCG,
                    team_id=team_id,
                    dry_run=dry_run,
                    channel_ids=list(final_target)
                )
                result.channel_adds += len(channels_to_add)
                result.channel_removals += len(channels_to_remove)
```

- [ ] **Step 2: Smoke-test the import**

```bash
source env/bin/activate
export DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
python -c "from app.slack.channel_sync import sync_single_user; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add app/slack/channel_sync.py
git commit -m "$(cat <<'EOF'
fix: idempotent SCG stable-tier channel repair

Mirror of the MCG fix in the previous commit. SCG has no private-
channel preservation since ultra_restricted users are confined to the
managed set by Slack itself, so final_target is just target_channel_ids.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Update tier-logic tests

**Files:**
- Modify: `tests/slack/test_tier_logic.py`
- Test: same file

The test file has two test classes:
- `TestTierLogicActivity` — uses `FakeUser`/`FakeSlackUser` stand-ins + `get_slack_tier_under_test()` replica.
- `TestUserGetSlackTierIntegration` — exercises the real `User.get_slack_tier()` against a Postgres test DB.

Both need updates for the new criterion.

- [ ] **Step 1: Update `FakeSlackUser` and `get_slack_tier_under_test`**

In `tests/slack/test_tier_logic.py`, replace the existing class (lines 15-17):

```python
class FakeSlackUser:
    def __init__(self, last_slack_activity=None):
        self.last_slack_activity = last_slack_activity
```

With:

```python
class FakeSlackUser:
    def __init__(self, last_slack_activity=None, slack_days_active=None, slack_messages_posted=None):
        self.last_slack_activity = last_slack_activity
        self.slack_days_active = slack_days_active
        self.slack_messages_posted = slack_messages_posted
```

Then replace the existing replica function (lines 29-47):

```python
def get_slack_tier_under_test(user, threshold_days=90):
    """Replicates get_slack_tier logic for FakeUser unit tests."""
    full_member_tags = {'HEAD_COACH', 'ASSISTANT_COACH'}
    if any(tag.name in full_member_tags for tag in user.tags):
        return 'full_member'

    if user.status == 'ACTIVE':
        return 'full_member'
    elif user.status == 'ALUMNI':
        if user.seasons_since_active == 1:
            return 'multi_channel_guest'
        else:
            if (user.slack_user
                    and user.slack_user.last_slack_activity
                    and (datetime.utcnow() - user.slack_user.last_slack_activity).days < threshold_days):
                return 'multi_channel_guest'
            return 'single_channel_guest'
    return None
```

With:

```python
def get_slack_tier_under_test(user, threshold_days=90):
    """Replicates get_slack_tier logic for FakeUser unit tests."""
    full_member_tags = {'HEAD_COACH', 'ASSISTANT_COACH'}
    if any(tag.name in full_member_tags for tag in user.tags):
        return 'full_member'

    if user.status == 'ACTIVE':
        return 'full_member'
    elif user.status == 'ALUMNI':
        if user.seasons_since_active == 1:
            return 'multi_channel_guest'
        else:
            su = user.slack_user
            if (su and su.last_slack_activity
                    and (datetime.utcnow() - su.last_slack_activity).days < threshold_days):
                messages = su.slack_messages_posted or 0
                days_active = su.slack_days_active or 0
                if messages >= 1 or days_active >= 3:
                    return 'multi_channel_guest'
            return 'single_channel_guest'
    return None
```

- [ ] **Step 2: Update existing tests that build `FakeSlackUser` for 2+ alumni**

Several existing tests build a `FakeSlackUser` with only `last_slack_activity` and expect MCG. Under the new logic those need engagement signals to remain MCG. Edit these specific tests:

In `test_two_season_alumni_recent_activity_is_mcg` (around line 64), change:

```python
    def test_two_season_alumni_recent_activity_is_mcg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=30))
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'
```

To:

```python
    def test_two_season_alumni_recent_activity_with_messages_is_mcg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=30),
            slack_messages_posted=1,
            slack_days_active=1,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'
```

In `test_two_season_alumni_activity_just_under_threshold_is_mcg` (around line 79), change:

```python
    def test_two_season_alumni_activity_just_under_threshold_is_mcg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=89))
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'
```

To:

```python
    def test_two_season_alumni_activity_just_under_threshold_with_engagement_is_mcg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=89),
            slack_messages_posted=1,
            slack_days_active=1,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'
```

In `test_three_season_alumni_recent_activity_is_mcg` (around line 84), change:

```python
    def test_three_season_alumni_recent_activity_is_mcg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=10))
        user = FakeUser(status='ALUMNI', seasons_since_active=3, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'
```

To:

```python
    def test_three_season_alumni_recent_activity_with_engagement_is_mcg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=10),
            slack_messages_posted=1,
            slack_days_active=1,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=3, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'
```

- [ ] **Step 3: Add new tests covering the engagement criterion**

Append these tests inside the `TestTierLogicActivity` class (after `test_slack_user_with_null_activity_is_scg`, around line 109):

```python
    def test_two_season_alumni_recent_no_engagement_is_scg(self):
        """The bug case: date_last_active bumped by admin call, but no real activity."""
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=1),
            slack_messages_posted=0,
            slack_days_active=1,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_two_season_alumni_with_one_message_is_mcg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=10),
            slack_messages_posted=1,
            slack_days_active=1,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_two_season_alumni_with_three_days_active_is_mcg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=10),
            slack_messages_posted=0,
            slack_days_active=3,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_two_season_alumni_with_two_days_active_no_messages_is_scg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=10),
            slack_messages_posted=0,
            slack_days_active=2,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_two_season_alumni_old_activity_with_many_messages_is_scg(self):
        """90-day window is required even with real engagement signals."""
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=120),
            slack_messages_posted=10,
            slack_days_active=20,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'
```

- [ ] **Step 4: Update integration tests that build a real `SlackUser`**

In the `TestUserGetSlackTierIntegration` class, `test_real_alumni_two_seasons_recent_activity_is_mcg` currently constructs a `SlackUser` with only `last_slack_activity`. Update it to also set the engagement fields.

Find this block (around line 184-188):

```python
        slack_user = SlackUser(
            slack_uid=f'U{uuid.uuid4().hex[:8].upper()}',
            last_slack_activity=datetime.utcnow() - timedelta(days=30),
        )
```

Change to:

```python
        slack_user = SlackUser(
            slack_uid=f'U{uuid.uuid4().hex[:8].upper()}',
            last_slack_activity=datetime.utcnow() - timedelta(days=30),
            slack_messages_posted=1,
            slack_days_active=1,
        )
```

The stale-activity integration test (around line 214) does not need changes — it asserts SCG, which the new logic also returns.

- [ ] **Step 5: Run the tier-logic tests**

```bash
source env/bin/activate
export DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
pytest tests/slack/test_tier_logic.py -v
```

Expected: all tests pass. The unit tests (`TestTierLogicActivity`) should all pass without a DB. The integration tests need the dev Postgres up.

- [ ] **Step 6: Commit**

```bash
git add tests/slack/test_tier_logic.py
git commit -m "$(cat <<'EOF'
test: cover new engagement criterion in get_slack_tier tests

Extends FakeSlackUser + test replica with slack_days_active and
slack_messages_posted. Adds cases for the bug scenario (date_last_active
bumped, no real engagement → SCG) and the two engagement signals
individually. Existing integration tests updated to set the new fields
where MCG is expected.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Update channel-sync tests

**Files:**
- Modify: `tests/slack/test_channel_sync.py:222-378` (`TestSyncSingleUserStableTierChannelRepair`)
- Add tests for: no-op MCG, MCG with extra channel to remove, no-op SCG already covered

The existing class has three tests:
1. `test_scg_missing_target_channel_gets_added` — already valid; the new code still calls `change_user_role` when channels are missing.
2. `test_mcg_missing_managed_channel_gets_added` — already valid; same as above for MCG.
3. `test_scg_no_op_when_channels_already_correct` — already valid; asserts `change_user_role` NOT called.

We need to add three tests:
- MCG no-op when channels already match (currently absent — the original code's `if channels_to_add:` guard hides this case from the test suite).
- MCG with an extra managed channel that should be removed (the fresh-tracks scenario).
- SCG with an extra managed channel that should be removed (defensive: SCG is usually one channel, but if list shrinks, extras should still go).

The existing tests should continue to pass without modification.

- [ ] **Step 1: Add MCG no-op test**

Append this test method to the `TestSyncSingleUserStableTierChannelRepair` class in `tests/slack/test_channel_sync.py`:

```python
    @patch('app.slack.channel_sync.add_user_to_channel')
    @patch('app.slack.channel_sync.change_user_role')
    @patch('app.slack.channel_sync.get_user_channels')
    @patch('app.slack.channel_sync.needs_role_change', return_value=False)
    @patch('app.slack.channel_sync.User.get_by_email', return_value=None)
    @patch('app.slack.channel_sync.Season.get_current', return_value=None)
    def test_mcg_no_op_when_channels_already_correct(
        self, mock_season, mock_user, mock_needs, mock_get_chans,
        mock_change_role, mock_add_channel, app
    ):
        """MCG user with channels matching target ∪ privates — no role change, no API call.

        This is the critical regression guard. Without the diff-then-act check,
        every sync would call change_user_role and bump date_last_active.
        """
        from app.slack.channel_sync import sync_single_user, ChannelSyncResult

        # User has all managed MCG channels + one private channel
        mock_get_chans.return_value = {C_WELCOME, C_CHAT, C_ALUMNI, C_BOOKCLUB}

        slack_user = {
            'id': 'U_MCG_NOOP',
            'profile': {'email': 'mcg-noop@example.com'},
            'is_restricted': True,
            'is_ultra_restricted': False,
        }
        managed = {C_WELCOME, C_CHAT, C_ALUMNI}
        target_mcg = {C_WELCOME, C_CHAT, C_ALUMNI}
        result = ChannelSyncResult()

        sync_single_user(
            slack_user=slack_user,
            target_tier='multi_channel_guest',
            target_channel_ids=target_mcg,
            full_member_channel_ids=set(),
            managed_channel_ids=managed,
            channel_id_to_properties={
                C_WELCOME: {'name': 'welcome-to-tcsc', 'is_public': True},
                C_CHAT: {'name': 'general-chat', 'is_public': False},
                C_ALUMNI: {'name': 'alumni-corner', 'is_public': False},
                C_BOOKCLUB: {'name': 'book-club', 'is_public': False},
            },
            team_id='T_TEST',
            dry_run=True,
            result=result,
            notify_per_transition=False,
        )

        mock_change_role.assert_not_called()
        mock_add_channel.assert_not_called()
        assert result.channel_adds == 0
        assert result.channel_removals == 0
```

- [ ] **Step 2: Add MCG extra-channel-removal test (the fresh-tracks scenario)**

Append:

```python
    @patch('app.slack.channel_sync.add_user_to_channel')
    @patch('app.slack.channel_sync.change_user_role')
    @patch('app.slack.channel_sync.get_user_channels')
    @patch('app.slack.channel_sync.needs_role_change', return_value=False)
    @patch('app.slack.channel_sync.User.get_by_email', return_value=None)
    @patch('app.slack.channel_sync.Season.get_current', return_value=None)
    def test_mcg_extra_managed_channel_gets_removed(
        self, mock_season, mock_user, mock_needs, mock_get_chans,
        mock_change_role, mock_add_channel, app
    ):
        """MCG user has a channel that is managed but no longer in the MCG target list.

        Models the fresh-tracks removal: a channel was removed from the MCG tier
        list in config; this user is still in it and should be removed.
        Private channels must still be preserved.
        """
        from app.slack.channel_sync import sync_single_user, ChannelSyncResult

        C_FRESHTRACKS = 'C_FRESHTRACKS'  # managed (full_member tier) but no longer in MCG target
        # User has the managed MCG channels + the now-removed fresh-tracks + a private channel
        mock_get_chans.return_value = {C_WELCOME, C_CHAT, C_ALUMNI, C_FRESHTRACKS, C_BOOKCLUB}

        slack_user = {
            'id': 'U_MCG_EXTRA',
            'profile': {'email': 'mcg-extra@example.com'},
            'is_restricted': True,
            'is_ultra_restricted': False,
        }
        # managed = union of all tier lists (incl. full_member where fresh-tracks lives)
        managed = {C_WELCOME, C_CHAT, C_ALUMNI, C_FRESHTRACKS}
        target_mcg = {C_WELCOME, C_CHAT, C_ALUMNI}  # fresh-tracks no longer here
        result = ChannelSyncResult()

        sync_single_user(
            slack_user=slack_user,
            target_tier='multi_channel_guest',
            target_channel_ids=target_mcg,
            full_member_channel_ids=set(),
            managed_channel_ids=managed,
            channel_id_to_properties={
                C_WELCOME: {'name': 'welcome-to-tcsc', 'is_public': True},
                C_CHAT: {'name': 'general-chat', 'is_public': False},
                C_ALUMNI: {'name': 'alumni-corner', 'is_public': False},
                C_FRESHTRACKS: {'name': 'fresh-tracks', 'is_public': False},
                C_BOOKCLUB: {'name': 'book-club', 'is_public': False},
            },
            team_id='T_TEST',
            dry_run=True,
            result=result,
            notify_per_transition=False,
        )

        mock_change_role.assert_called_once()
        call_kwargs = mock_change_role.call_args.kwargs
        assert call_kwargs['target_role'] == ROLE_MCG
        passed_channels = set(call_kwargs['channel_ids'])
        # Must NOT contain fresh-tracks; must contain target + preserved private
        assert C_FRESHTRACKS not in passed_channels
        assert passed_channels == {C_WELCOME, C_CHAT, C_ALUMNI, C_BOOKCLUB}
        # conversations.invite NOT called
        mock_add_channel.assert_not_called()
        # Counters reflect a real removal
        assert result.channel_removals == 1
        assert result.channel_adds == 0
        # Trace strings present
        assert any('CHANNEL_REMOVE' in t and 'fresh-tracks' in t for t in result.traces)
        assert any('PRESERVE_PRIVATE' in t for t in result.traces)
```

- [ ] **Step 3: Add SCG extra-channel-removal test (defensive)**

Append:

```python
    @patch('app.slack.channel_sync.add_user_to_channel')
    @patch('app.slack.channel_sync.change_user_role')
    @patch('app.slack.channel_sync.get_user_channels')
    @patch('app.slack.channel_sync.needs_role_change', return_value=False)
    @patch('app.slack.channel_sync.User.get_by_email', return_value=None)
    @patch('app.slack.channel_sync.Season.get_current', return_value=None)
    def test_scg_extra_channel_gets_removed(
        self, mock_season, mock_user, mock_needs, mock_get_chans,
        mock_change_role, mock_add_channel, app
    ):
        """SCG user has an extra managed channel that should be removed."""
        from app.slack.channel_sync import sync_single_user, ChannelSyncResult

        # User is in reactivate channel + an extra managed channel they shouldn't have
        mock_get_chans.return_value = {C_REACTIVATE, C_CHAT}

        slack_user = {
            'id': 'U_SCG_EXTRA',
            'profile': {'email': 'scg-extra@example.com'},
            'is_restricted': False,
            'is_ultra_restricted': True,
        }
        result = ChannelSyncResult()

        sync_single_user(
            slack_user=slack_user,
            target_tier='single_channel_guest',
            target_channel_ids={C_REACTIVATE},
            full_member_channel_ids=set(),
            managed_channel_ids={C_REACTIVATE, C_CHAT},
            channel_id_to_properties={
                C_REACTIVATE: {'name': 'tcsc-reactivate-me', 'is_public': False},
                C_CHAT: {'name': 'general-chat', 'is_public': False},
            },
            team_id='T_TEST',
            dry_run=True,
            result=result,
            notify_per_transition=False,
        )

        mock_change_role.assert_called_once()
        call_kwargs = mock_change_role.call_args.kwargs
        assert call_kwargs['target_role'] == ROLE_SCG
        passed_channels = set(call_kwargs['channel_ids'])
        assert passed_channels == {C_REACTIVATE}
        mock_add_channel.assert_not_called()
        assert result.channel_removals == 1
        assert result.channel_adds == 0
```

- [ ] **Step 4: Run the channel-sync tests**

```bash
source env/bin/activate
export DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
pytest tests/slack/test_channel_sync.py -v
```

Expected: all tests pass — three existing + three new in `TestSyncSingleUserStableTierChannelRepair`, plus the rest of the file unchanged.

- [ ] **Step 5: Commit**

```bash
git add tests/slack/test_channel_sync.py
git commit -m "$(cat <<'EOF'
test: cover idempotent + bidirectional stable-tier channel repair

Adds three tests:
- MCG no-op when channels match (regression guard against the
  date_last_active churn)
- MCG with an extra managed channel (the fresh-tracks scenario)
- SCG with an extra managed channel (defensive)

Existing add-missing and SCG no-op tests already pass against the new
implementation without changes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Run full test suite, push branch, open PR

**Files:** none (verification + git)

- [ ] **Step 1: Run the full Slack test suite**

```bash
source env/bin/activate
export DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
pytest tests/slack/ -v
```

Expected: all tests pass. Pay attention to `test_admin_api.py` — it may not exercise `fetch_user_activity` directly, but if it does the return-type change could break it. If a test fails, fix it (don't bypass) and add a commit.

- [ ] **Step 2: Run the full repo test suite**

```bash
pytest -v
```

Expected: all 124 tests pass. If a non-Slack test fails it's likely unrelated; investigate before assuming so.

- [ ] **Step 3: Verify no rogue print/debug statements**

```bash
git diff main..HEAD -- app/ | grep -E '^\+.*\b(print|breakpoint|pdb)\b' || echo "clean"
```

Expected: `clean`

- [ ] **Step 4: Verify commit history is clean**

```bash
git log --oneline main..HEAD
```

Expected: ~10 commits (one migration, one model, one tier-logic, one fetch_user_activity, one backfill, two repair-branch fixes, two test commits, possibly one fix-up). Each message should be a single focused change.

- [ ] **Step 5: Push the branch**

```bash
git push -u origin fix/slack-tier-real-engagement
```

- [ ] **Step 6: Open the PR**

```bash
gh pr create --title "fix: stop SCG↔MCG churn from change_user_role bumping date_last_active" --body "$(cat <<'EOF'
## Summary

On 2026-05-12 the channel sync wrongly promoted 70+ alumni from `single_channel_guest` to `multi_channel_guest`. Root cause is two interacting bugs:

1. **Stable-tier repair churn (PR #188/#189).** `sync_single_user` was calling `change_user_role` every sync for SCG/MCG users whose Slack role already matched the target tier, to repair channel membership. The admin call bumps `date_last_active` in Slack's analytics — even though the user took no action.
2. **Weak tier criterion.** `User.get_slack_tier()` for 2+ season alumni only checked `last_slack_activity < 90 days`, which the bumped timestamp from #1 satisfied. Next sync: SCG → MCG.

Separately, PR #190 removed `fresh-tracks` from the MCG tier list, but the stable-tier repair branch was additive-only — MCG users in `#fresh-tracks` weren't removed.

## Changes

- **Migration** `a7c3f9d2e1b8`: add `slack_days_active` and `slack_messages_posted` columns to `slack_users`.
- **`fetch_user_activity`**: returns a richer dict per user (`last_active`, `days_active`, `messages_posted`). API already returns these fields; we now parse them.
- **Activity backfill**: writes all three fields during sync.
- **`User.get_slack_tier()`**: for 2+ season alumni, requires `messages_posted >= 1 OR days_active >= 3` on top of the 90-day window.
- **Stable-tier MCG/SCG repair**: computes `target ∪ preserved_private`; skips `change_user_role` when current channels already match (kills churn); otherwise applies the full diff (add missing + remove extras within managed set, preserve privates for MCG).

## Self-healing rollout

After deploy, the next sync:
1. Fetches fresh analytics — the 70+ wrongly-promoted users have `messages_posted=0`, `days_active=1`.
2. Tier evaluation fails the new criterion → demotes them MCG → SCG.
3. The legitimate demotion bumps `date_last_active` once more, but `messages_posted=0` keeps them gated correctly afterward.
4. Any remaining MCG members of `#fresh-tracks` get removed in the same operation via the diff-then-act logic.

## Spec & plan

- Spec: `docs/superpowers/specs/2026-05-12-slack-tier-criteria-and-idempotent-repair-design.md`
- Plan: `docs/superpowers/plans/2026-05-12-slack-tier-criteria-and-idempotent-repair.md`

## Test plan

- [x] `pytest tests/slack/ -v` passes
- [x] `pytest -v` (full repo) passes
- [ ] Deploy to staging (or run sync in dry-run on prod) and confirm the 70+ MCG users show up in `CHANNEL_REMOVE` traces
- [ ] After production sync runs, spot-check `slack_users` table for populated `slack_days_active` and `slack_messages_posted`
- [ ] Verify a previously-correct SCG (e.g. someone with `messages_posted=0` who was already SCG before today's bug) produces no `change_user_role` call in the sync traces

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: the PR URL is printed.

---

## Self-Review Notes

**Spec coverage:**
- Schema migration → Task 2 ✓
- `fetch_user_activity` extension → Task 5 ✓
- `SlackUser` columns → Task 3 ✓
- `get_slack_tier` 2+ branch → Task 4 ✓
- Activity backfill writes all 3 fields → Task 6 ✓
- Diff-then-act stable-tier MCG → Task 7 ✓
- Diff-then-act stable-tier SCG → Task 8 ✓
- Tier-logic tests → Task 9 ✓
- Channel-sync tests (no-op MCG, extra-channel MCG, extra-channel SCG) → Task 10 ✓
- Cleanup is operational (next sync auto-demotes); covered in the PR body, not code.

**Placeholder scan:** none.

**Type consistency:** `fetch_user_activity` returns `dict[str, dict]` with keys `last_active`, `days_active`, `messages_posted` — consistent everywhere it's read (Task 6 backfill). `SlackUser.slack_days_active` / `SlackUser.slack_messages_posted` naming is consistent across migration, model, and consumers.
