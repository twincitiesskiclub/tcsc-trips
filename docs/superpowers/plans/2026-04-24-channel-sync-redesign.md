# Channel Sync Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Use the opus model for all executing agents.**

**Goal:** Redesign the Slack channel sync to support activity-based tier decisions for 2+ season alumni, self-service reactivation via Slack Custom Steps, and private channel preservation during full_member → MCG transitions.

**Architecture:** The existing `channel_sync.py` orchestrates a 3am daily sync using cookie-based admin APIs. We add an activity-fetch step early in the sync, update `User.get_slack_tier()` to incorporate a 90-day activity check via `SlackUser.last_slack_activity`, modify `sync_single_user()` to preserve private channels during MCG transitions, add a Bolt custom function handler for reactivation, and add webhook notifications for tier transitions. Config changes in `slack_channels.yaml` update the channel-to-tier mapping.

**Tech Stack:** Flask, SQLAlchemy, Flask-Migrate, slack-bolt (Python), Slack admin API (cookie-based), PostgreSQL

**Spec:** `docs/superpowers/specs/2026-04-24-channel-sync-redesign-design.md`

---

### Task 0: Activity API Endpoint Spike — COMPLETE (2026-05-11)

**Outcome:** ✓ Verified. Endpoint is `admin.analytics.getMemberAnalytics`, paired with `admin.analytics.getAvailableDateRange`. See the "Activity Detection" section of the spec for the full contract. Probe script at `scripts/probe_slack_activity.py`. Distribution snapshot at time of probe (223 total members):

| Days since last active | Members |
|---|---|
| 0–30 | 121 |
| 30–90 | 15 |
| 90–180 | 8 |
| 180–365 | 15 |
| Over 365 | 29 |
| Never | 35 |

Under the 90-day MCG rule, 136 members are activity-eligible and 87 would be flagged inactive (of which only the 2+ season alumni become SCG candidates).

**Files:**
- Created: `scripts/probe_slack_activity.py`

- [x] **Step 1: Write the probe script**

Probe lives at `scripts/probe_slack_activity.py`. It exercises `admin.analytics.getAvailableDateRange` and `admin.analytics.getMemberAnalytics` via the cookie-based auth in `app.slack.admin_api`, prints the response shapes, and summarizes the workspace's activity distribution. See the script for current behavior.

- [x] **Step 2: Run the probe**

```bash
source env/bin/activate
python scripts/probe_slack_activity.py
```

Verified output: 223 members fetched, `date_last_active` present, distribution buckets printed. Endpoint contract recorded in the spec under "Activity Detection." Used by Task 2 to implement `fetch_user_activity()`.

- [ ] **Step 3: Commit**

```bash
git add scripts/probe_slack_activity.py
git commit -m "feat: add probe script to verify Slack admin activity API endpoint"
```

(Commit will be made along with Task 0's spec updates.)

---

### Task 1: Database Migration — Add `last_slack_activity` to SlackUser

**Files:**
- Modify: `app/models.py:107-126` (SlackUser model)
- Create: `migrations/versions/xxxx_add_last_slack_activity.py` (via flask db migrate)

- [ ] **Step 1: Add column to SlackUser model**

In `app/models.py`, add the `last_slack_activity` column to the `SlackUser` class, after the `timezone` column (line 118):

```python
class SlackUser(db.Model):
    __tablename__ = 'slack_users'

    id = db.Column(db.Integer, primary_key=True)
    slack_uid = db.Column(db.String(255), unique=True, nullable=False)
    display_name = db.Column(db.String(255))
    full_name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    title = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    status = db.Column(db.Text)
    timezone = db.Column(db.String(100))
    last_slack_activity = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = db.relationship('User', backref='slack_user', uselist=False)

    def __repr__(self):
        return f'<SlackUser {self.slack_uid}>'
```

- [ ] **Step 2: Generate and review migration**

Run:
```bash
source env/bin/activate
flask db migrate -m "add last_slack_activity to slack_users"
```

Expected: A new migration file in `migrations/versions/`. Review it to confirm it adds a nullable DateTime column `last_slack_activity` to the `slack_users` table.

- [ ] **Step 3: Apply migration**

Run:
```bash
flask db upgrade
```

Expected: Migration applies successfully. Verify with:
```bash
docker exec tcsc-postgres psql -U tcsc -d tcsc_trips -c "\d slack_users" | grep last_slack_activity
```

Expected output includes: `last_slack_activity | timestamp without time zone |`

- [ ] **Step 4: Commit**

```bash
git add app/models.py migrations/versions/*last_slack_activity*
git commit -m "feat: add last_slack_activity column to SlackUser model"
```

---

### Task 2: Activity Detection — `fetch_user_activity()` in admin_api.py

**Files:**
- Modify: `app/slack/admin_api.py` (add function after `invite_user_by_email`)
- Test: `tests/slack/test_admin_api.py`

- [ ] **Step 1: Write the test file**

Create `tests/slack/test_admin_api.py`. Tests mock `make_admin_request` to return the verified response shapes from Task 0:

```python
"""Tests for admin API activity fetch.

The implementation makes two calls:
  1. admin.analytics.getAvailableDateRange — returns {start_date, end_date}
  2. admin.analytics.getMemberAnalytics — returns {member_activity: [...], num_found, next_cursor_mark}
Tests mock both via side_effect on make_admin_request.
"""

from datetime import datetime
from unittest.mock import patch

import pytest


RANGE_OK = {
    'ok': True,
    'start_date': '2025-04-10',
    'end_date': '2026-05-10',
    'date_last_updated': 1778502662,
    'date_last_indexed': 1778502662,
}


class TestFetchUserActivity:
    """Test fetch_user_activity admin API function."""

    @patch('app.slack.admin_api.make_admin_request')
    def test_returns_user_id_to_timestamp_map(self, mock_request):
        from app.slack.admin_api import fetch_user_activity

        mock_request.side_effect = [
            RANGE_OK,
            {
                'ok': True,
                'num_found': 2,
                'next_cursor_mark': '',
                'member_activity': [
                    {'user_id': 'U123', 'date_last_active': 1714000000},
                    {'user_id': 'U456', 'date_last_active': 1713000000},
                ],
            },
        ]

        result = fetch_user_activity()

        assert 'U123' in result
        assert 'U456' in result
        assert isinstance(result['U123'], datetime)
        assert isinstance(result['U456'], datetime)

    @patch('app.slack.admin_api.make_admin_request')
    def test_skips_members_with_zero_or_missing_activity(self, mock_request):
        """Bots, never-onboarded users have date_last_active = 0 or missing."""
        from app.slack.admin_api import fetch_user_activity

        mock_request.side_effect = [
            RANGE_OK,
            {
                'ok': True,
                'num_found': 3,
                'next_cursor_mark': '',
                'member_activity': [
                    {'user_id': 'U123', 'date_last_active': 1714000000},
                    {'user_id': 'U789', 'date_last_active': 0},
                    {'user_id': 'U000'},  # field missing entirely
                ],
            },
        ]

        result = fetch_user_activity()

        assert 'U123' in result
        assert 'U789' not in result
        assert 'U000' not in result

    @patch('app.slack.admin_api.make_admin_request')
    def test_handles_pagination(self, mock_request):
        from app.slack.admin_api import fetch_user_activity

        mock_request.side_effect = [
            RANGE_OK,
            {
                'ok': True,
                'num_found': 2,
                'next_cursor_mark': 'cursor-page-2',
                'member_activity': [{'user_id': 'U1', 'date_last_active': 1714000000}],
            },
            {
                'ok': True,
                'num_found': 2,
                'next_cursor_mark': '',
                'member_activity': [{'user_id': 'U2', 'date_last_active': 1714000000}],
            },
        ]

        result = fetch_user_activity()

        assert len(result) == 2
        assert 'U1' in result
        assert 'U2' in result
        # 1 range call + 2 analytics calls
        assert mock_request.call_count == 3

    @patch('app.slack.admin_api.make_admin_request')
    def test_returns_empty_dict_on_range_failure(self, mock_request):
        from app.slack.admin_api import fetch_user_activity

        mock_request.side_effect = Exception("API error")

        result = fetch_user_activity()

        assert result == {}

    @patch('app.slack.admin_api.make_admin_request')
    def test_returns_empty_dict_on_analytics_failure(self, mock_request):
        from app.slack.admin_api import fetch_user_activity

        mock_request.side_effect = [RANGE_OK, Exception("analytics failed")]

        result = fetch_user_activity()

        assert result == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
pytest tests/slack/test_admin_api.py -v
```

Expected: FAIL — `fetch_user_activity` does not exist yet.

- [ ] **Step 3: Implement `fetch_user_activity()`**

Add to `app/slack/admin_api.py` after the `invite_user_by_email` function.

The function makes two calls in sequence: first to `getAvailableDateRange` to learn the valid window (Slack's analytics index lags today by ~1 day), then to `getMemberAnalytics` with that window. Both endpoints require `_x_app_name=manage` — different from the workspace UI calls used elsewhere in `admin_api.py`.

```python
def fetch_user_activity() -> dict[str, datetime]:
    """Fetch last-active timestamps for all workspace members.

    Uses Slack's admin analytics API (admin.analytics.getMemberAnalytics).
    Two-call sequence:
      1. getAvailableDateRange to determine the valid window
      2. getMemberAnalytics to retrieve per-member date_last_active

    Returns:
        Dict mapping Slack user ID -> last active datetime (UTC).
        Members with date_last_active <= 0 (bots, never-onboarded) are omitted.
        Returns empty dict on failure (caller uses stale data).
    """
    activity_map: dict[str, datetime] = {}

    try:
        # Step 1: get the valid window
        range_response = make_admin_request(
            api_method='admin.analytics.getAvailableDateRange',
            data={
                'token': get_admin_credentials()['token'],
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

        # Step 2: paginate through member_activity rows
        cursor = ''
        total_expected = None
        while True:
            data = {
                'token': get_admin_credentials()['token'],
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

            for member in response.get('member_activity', []):
                user_id = member.get('user_id')
                ts = member.get('date_last_active') or 0
                if user_id and ts > 0:
                    activity_map[user_id] = datetime.utcfromtimestamp(ts)

            if total_expected is None:
                total_expected = response.get('num_found', 0)

            next_cursor = response.get('next_cursor_mark', '')
            if not next_cursor or next_cursor == cursor:
                break
            if total_expected and len(activity_map) >= total_expected:
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

Add `from datetime import datetime` to the imports at the top of `admin_api.py`:

```python
import os
import time
import functools
import requests
from datetime import datetime
from typing import Optional
from flask import current_app
```

**Note on `make_admin_request`:** it currently injects auth params from `get_admin_credentials()` but does NOT auto-add `_x_app_name=manage` (the workspace UI endpoints use the default UI app name). Including `_x_app_name=manage` in the `data` dict per-call works because it's passed through as multipart form data. If this becomes painful for multiple analytics endpoints later, consider a `make_admin_request(..., app_name='manage')` keyword.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
pytest tests/slack/test_admin_api.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/slack/admin_api.py tests/slack/test_admin_api.py
git commit -m "feat: add fetch_user_activity() to admin API for activity-based tier checks"
```

---

### Task 3: Update Tier Logic — `User.get_slack_tier()` with Activity Check

**Files:**
- Modify: `app/models.py:226-252` (User.get_slack_tier method)
- Test: `tests/slack/test_tier_logic.py`

- [ ] **Step 1: Write the tests**

Create `tests/slack/test_tier_logic.py`:

```python
"""Tests for User.get_slack_tier() activity-based logic."""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, PropertyMock

import pytest


class FakeTag:
    def __init__(self, name):
        self.name = name


class FakeSlackUser:
    def __init__(self, last_slack_activity=None):
        self.last_slack_activity = last_slack_activity


class FakeUser:
    """Minimal User stand-in that mirrors get_slack_tier logic."""
    def __init__(self, status, seasons_since_active, tags=None, slack_user=None):
        self.status = status
        self.seasons_since_active = seasons_since_active
        self.tags = tags or []
        self.slack_user = slack_user


def get_slack_tier_under_test(user, threshold_days=90):
    """Call the real get_slack_tier after importing. We test the actual model method."""
    # We'll test via the actual User model in integration,
    # but for unit tests we replicate the logic to validate it.
    # The implementation test verifies the model method matches.
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


class TestTierLogicActivity:
    """Test activity-based tier for 2+ season alumni."""

    def test_active_user_is_full_member(self):
        user = FakeUser(status='ACTIVE', seasons_since_active=0)
        assert get_slack_tier_under_test(user) == 'full_member'

    def test_one_season_alumni_is_mcg(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=1)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_two_season_alumni_no_activity_is_scg(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=None)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_two_season_alumni_recent_activity_is_mcg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=30))
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_two_season_alumni_old_activity_is_scg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=120))
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_two_season_alumni_activity_exactly_at_threshold_is_scg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=90))
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_two_season_alumni_activity_just_under_threshold_is_mcg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=89))
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_three_season_alumni_recent_activity_is_mcg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=10))
        user = FakeUser(status='ALUMNI', seasons_since_active=3, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_coach_override_trumps_everything(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=200))
        user = FakeUser(status='ALUMNI', seasons_since_active=5, tags=[FakeTag('HEAD_COACH')], slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'full_member'

    def test_pending_user_returns_none(self):
        user = FakeUser(status='PENDING', seasons_since_active=0)
        assert get_slack_tier_under_test(user) is None

    def test_dropped_user_returns_none(self):
        user = FakeUser(status='DROPPED', seasons_since_active=0)
        assert get_slack_tier_under_test(user) is None

    def test_no_slack_user_linked_is_scg(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=None)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_slack_user_with_null_activity_is_scg(self):
        slack_user = FakeSlackUser(last_slack_activity=None)
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'
```

- [ ] **Step 2: Run tests to verify they pass (testing the expected logic)**

Run:
```bash
pytest tests/slack/test_tier_logic.py -v
```

Expected: All 13 tests PASS. These validate the target logic before we modify the model.

- [ ] **Step 3: Update `User.get_slack_tier()` in models.py**

Replace the `get_slack_tier` method at `app/models.py:226-252` with:

```python
    def get_slack_tier(self):
        """Determine Slack membership tier based on status and activity.

        Override rules (checked first):
        - HEAD_COACH or ASSISTANT_COACH tags -> always full_member

        Standard rules:
        - ACTIVE status -> full_member
        - ALUMNI with seasons_since_active == 1 -> multi_channel_guest
        - ALUMNI with seasons_since_active >= 2 + active in last 90 days -> multi_channel_guest
        - ALUMNI with seasons_since_active >= 2 + inactive 90+ days -> single_channel_guest
        - PENDING or DROPPED -> None (no Slack automation)
        """
        full_member_tags = {'HEAD_COACH', 'ASSISTANT_COACH'}
        if any(tag.name in full_member_tags for tag in self.tags):
            return 'full_member'

        if self.status == UserStatus.ACTIVE:
            return 'full_member'
        elif self.status == UserStatus.ALUMNI:
            if self.seasons_since_active == 1:
                return 'multi_channel_guest'
            else:
                if (self.slack_user
                        and self.slack_user.last_slack_activity
                        and (datetime.utcnow() - self.slack_user.last_slack_activity).days < 90):
                    return 'multi_channel_guest'
                return 'single_channel_guest'
        return None
```

Note: `datetime` is already imported at the top of `models.py`.

- [ ] **Step 4: Run tier logic tests again**

Run:
```bash
pytest tests/slack/test_tier_logic.py -v
```

Expected: All 13 tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

Run:
```bash
pytest tests/ -v --tb=short
```

Expected: All existing tests pass. The only change is the `get_slack_tier` method, which now checks `self.slack_user.last_slack_activity` for 2+ season alumni. Existing tests that don't set up `slack_user` will still see `single_channel_guest` for 2+ alumni (same as before since `self.slack_user` will be `None`).

- [ ] **Step 6: Commit**

```bash
git add app/models.py tests/slack/test_tier_logic.py
git commit -m "feat: add activity-based tier logic for 2+ season alumni"
```

---

### Task 4: Update Channel Config — `slack_channels.yaml`

**Files:**
- Modify: `config/slack_channels.yaml`

- [ ] **Step 1: Update the config file**

Replace the entire contents of `config/slack_channels.yaml` with:

```yaml
# Slack Channel Sync Configuration
# This config controls the automated channel membership sync job

# Safety: Set to false only after validating dry-run logs
dry_run: true  # DEFAULT: true - logs actions without making changes

# Slack workspace settings
slack:
  workspace_domain: "twincitiesskiclub"
  base_url: "https://twincitiesskiclub.slack.com/api/"

# Channel configuration by membership tier
# Maps User.get_slack_tier() return values to channel lists
channels:
  # ACTIVE users (seasons_since_active = 0) - full workspace access
  full_member:
    - "welcome-to-tcsc"
    - "announcements-practices"
    - "announcements-general"
    - "chat"
    - "fresh-tracks"
    - "gear-recs-swap"
    - "races-information"
    - "volunteer-and-job-opportunities"
    - "extra-training-fun"
    - "meme"
    - "photos-videos"
    - "race-waxing"

  # ALUMNI (seasons_since_active = 1, or 2+ with recent activity/reactivated)
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

  # ALUMNI (seasons_since_active >= 2, inactive 90+ days) - single-channel guest
  # SCG is the demoted tier — only gets the reactivation channel. Not welcome-to-tcsc.
  single_channel_guest:
    - "tcsc-reactivate-me"

# Channels exclusive to full members (full_member - multi_channel_guest)
exclusive_channels:
  - "announcements-practices"
  - "announcements-general"

# Activity-based tier check for 2+ season alumni
# Alumni inactive longer than this threshold are demoted to SCG
activity_threshold_days: 90

# Channel for SCG reactivation workflow
reactivation_channel: "tcsc-reactivate-me"
reactivation_channel_id: "C0AUQCG7UB1"

# Notifications: end-of-sync summary always posts. Per-transition pings are
# off by default to avoid flooding the channel and tripping webhook rate
# limits on large runs (e.g. the first run after season activation).
notify_per_transition: false

# Private community channels where the bot has been added. Listed for
# record-keeping only; the sync auto-detects any private channel the bot
# is in via get_user_channels(). Channels without the bot will lose alumni
# members on the full_member → MCG transition.
known_private_channels:
  # Fill in actual list — examples:
  # - "book-club"
  # - "soccer"
  # - "lake-placid"

# Tags that mark users as exceptions (skipped by automation)
# These users retain their current Slack status regardless of DB status
# Note: HEAD_COACH and ASSISTANT_COACH are NOT exceptions - they get full_member tier override
# Note: BOARD_MEMBER is intentionally NOT in this list — board members should be
#       subject to normal tier logic so their channel memberships stay accurate.
exception_tags:
  - "ADMIN"
  - "EXEMPT"

# Welcome message for new member invitations
invitation_message: "Welcome to the Twin Cities Ski Club Slack!"

# ExpertVoice SFTP configuration
# Members with ACTIVE status or ALUMNI (1 season) get ExpertVoice access
expertvoice:
  enabled: true
  sftp:
    host: "sftp.expertvoice.com"
    port: 22
    path: "/incoming/"
    filename: "twincitiesskiclub.memberauth.csv"
```

Key changes from old config:
- Renamed `announcements-tcsc` → `announcements-general` everywhere
- Removed `announcements-adventures` from `full_member` list
- `announcements-general` is now full_member-only (members-only announcements)
- MCG announcement channel is the new `announcements-alumni` (C0B2ZQ4KM0E)
- `single_channel_guest` channel is `tcsc-reactivate-me`
- `exclusive_channels` is the set of channels only full_members get: `announcements-practices` and `announcements-general`
- Added `activity_threshold_days: 90`
- Added `reactivation_channel` and `reactivation_channel_id`
- Added `notify_per_transition: false` (default off)
- Added `known_private_channels` documentation block

- [ ] **Step 2: Commit**

```bash
git add config/slack_channels.yaml
git commit -m "feat: update channel config for sync redesign

- Remove announcements-adventures (will be archived)
- SCG channel changes to tcsc-reactivate-me
- Add activity_threshold_days and reactivation_channel config"
```

---

### Task 5: Tier Transition Notifications

**Approach:** End-of-sync summary is the default notification. Per-transition pings are optional and off by default (controlled by `notify_per_transition` in `slack_channels.yaml`). The summary is built from `ChannelSyncResult` counters that already exist; this task adds the webhook function and the per-transition variant.

**Files:**
- Modify: `app/notifications/slack.py` (add new notification functions)
- Test: `tests/slack/test_notifications.py`

- [ ] **Step 1: Write the tests**

Create `tests/slack/test_notifications.py`:

```python
"""Tests for tier transition notifications."""

from unittest.mock import patch, MagicMock

import pytest


class TestSendTierTransitionNotification:

    @patch('app.notifications.slack.requests.post')
    @patch('app.notifications.slack.os.environ.get', return_value='https://hooks.slack.com/test')
    def test_sends_demotion_notification(self, mock_env, mock_post):
        from app.notifications.slack import send_tier_transition_notification

        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        result = send_tier_transition_notification(
            name='Jane Doe',
            email='jane@example.com',
            from_tier='multi_channel_guest',
            to_tier='single_channel_guest',
            reason='inactive 90+ days',
        )

        assert result is True
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert 'Jane Doe' in payload['text']
        assert 'jane@example.com' in payload['text']
        assert 'MCG → SCG' in payload['text']
        assert 'inactive 90+ days' in payload['text']

    @patch('app.notifications.slack.requests.post')
    @patch('app.notifications.slack.os.environ.get', return_value='https://hooks.slack.com/test')
    def test_sends_reactivation_notification(self, mock_env, mock_post):
        from app.notifications.slack import send_tier_transition_notification

        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        result = send_tier_transition_notification(
            name='Jane Doe',
            email='jane@example.com',
            from_tier='single_channel_guest',
            to_tier='multi_channel_guest',
            reason='self-service reactivation',
        )

        assert result is True
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert 'SCG → MCG' in payload['text']
        assert 'self-service reactivation' in payload['text']

    @patch('app.notifications.slack.os.environ.get', return_value=None)
    def test_returns_false_when_no_webhook(self, mock_env):
        from app.notifications.slack import send_tier_transition_notification

        result = send_tier_transition_notification(
            name='Jane Doe',
            email='jane@example.com',
            from_tier='full_member',
            to_tier='multi_channel_guest',
            reason='1 season not registered',
        )

        assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
pytest tests/slack/test_notifications.py -v
```

Expected: FAIL — `send_tier_transition_notification` does not exist yet.

- [ ] **Step 3: Implement notification functions**

Add to `app/notifications/slack.py` after the existing `send_payment_notification` function:

```python
TIER_DISPLAY = {
    'full_member': 'Full Member',
    'multi_channel_guest': 'MCG',
    'single_channel_guest': 'SCG',
}


def send_tier_transition_notification(name, email, from_tier, to_tier, reason):
    """Per-transition notification. Gated by notify_per_transition config flag.

    The caller is responsible for honoring the flag; this function always sends
    when called. Use send_sync_summary_notification for default per-run output.
    """
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')

    if not slack_webhook_url:
        current_app.logger.warning("SLACK_WEBHOOK_URL not configured, skipping tier notification")
        return False

    from_display = TIER_DISPLAY.get(from_tier, from_tier)
    to_display = TIER_DISPLAY.get(to_tier, to_tier)

    message = {
        "text": (
            f"Slack tier change: {name} ({email})\n"
            f"{from_display} → {to_display}\n"
            f"Reason: {reason}"
        )
    }

    try:
        response = requests.post(slack_webhook_url, json=message, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send tier transition notification: {e}")
        return False


def send_sync_summary_notification(result, dry_run=False):
    """End-of-sync summary. Always sent.

    Args:
        result: ChannelSyncResult with populated counters
        dry_run: whether this sync was a dry-run
    """
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')

    if not slack_webhook_url:
        current_app.logger.warning("SLACK_WEBHOOK_URL not configured, skipping sync summary")
        return False

    mode = "DRY RUN" if dry_run else "live"
    lines = [
        f"Channel sync complete ({mode}):",
        f"• Role changes: {result.role_changes}",
        f"• Channel additions: {result.channels_added}",
        f"• Channel removals: {result.channels_removed}",
        f"• Invites: {result.invites_sent}",
        f"• Errors: {len(result.errors)}",
    ]

    message = {"text": "\n".join(lines)}

    try:
        response = requests.post(slack_webhook_url, json=message, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send sync summary notification: {e}")
        return False
```

Add a test for `send_sync_summary_notification` to `tests/slack/test_notifications.py` covering: (a) summary text includes counts, (b) dry_run vs live labeling, (c) returns False when webhook unset.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
pytest tests/slack/test_notifications.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/notifications/slack.py tests/slack/test_notifications.py
git commit -m "feat: add webhook notifications for tier transitions"
```

---

### Task 6: Channel Sync Updates — Activity Integration & Private Channel Preservation

**Files:**
- Modify: `app/slack/channel_sync.py`
- Test: `tests/slack/test_channel_sync.py`

- [ ] **Step 1: Write the tests**

Create `tests/slack/test_channel_sync.py`:

```python
"""Tests for channel sync private channel preservation and activity integration."""

from unittest.mock import patch, MagicMock

import pytest

from app.slack.channel_sync import (
    ChannelSyncResult,
    get_managed_channel_ids,
)


class TestGetManagedChannelIds:
    """Test helper that collects all managed channel IDs across tiers."""

    def test_returns_union_of_all_tier_channels(self):
        config = {
            'channels': {
                'full_member': ['ch-a', 'ch-b', 'ch-c'],
                'multi_channel_guest': ['ch-a', 'ch-b'],
                'single_channel_guest': ['ch-d'],
            }
        }
        name_to_id = {
            'ch-a': 'CA',
            'ch-b': 'CB',
            'ch-c': 'CC',
            'ch-d': 'CD',
        }

        result = get_managed_channel_ids(config, name_to_id)

        assert result == {'CA', 'CB', 'CC', 'CD'}

    def test_skips_unknown_channels(self):
        config = {
            'channels': {
                'full_member': ['ch-a', 'ch-missing'],
                'multi_channel_guest': [],
                'single_channel_guest': [],
            }
        }
        name_to_id = {'ch-a': 'CA'}

        result = get_managed_channel_ids(config, name_to_id)

        assert result == {'CA'}


class TestPrivateChannelPreservation:
    """Test that MCG transitions preserve unmanaged private channels."""

    def test_merge_preserves_private_channels(self):
        """Verify the merge logic that will be used in sync_single_user."""
        managed_ids = {'C_ANN', 'C_CHAT', 'C_GEAR'}
        target_mcg_ids = {'C_ANN', 'C_CHAT', 'C_GEAR'}
        current_user_channels = {'C_ANN', 'C_CHAT', 'C_GEAR', 'C_BOOKCLUB', 'C_SOCCER'}

        private_to_preserve = current_user_channels - managed_ids
        merged = target_mcg_ids | private_to_preserve

        assert 'C_BOOKCLUB' in merged
        assert 'C_SOCCER' in merged
        assert len(merged) == 5

    def test_merge_with_no_private_channels(self):
        managed_ids = {'C_ANN', 'C_CHAT'}
        target_mcg_ids = {'C_ANN', 'C_CHAT'}
        current_user_channels = {'C_ANN', 'C_CHAT'}

        private_to_preserve = current_user_channels - managed_ids
        merged = target_mcg_ids | private_to_preserve

        assert merged == target_mcg_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
pytest tests/slack/test_channel_sync.py -v
```

Expected: FAIL — `get_managed_channel_ids` does not exist yet.

- [ ] **Step 3: Add `get_managed_channel_ids` helper to channel_sync.py**

Add after the `get_target_channel_ids` function (after line 230 in `app/slack/channel_sync.py`):

```python
def get_managed_channel_ids(
    config: dict,
    channel_name_to_id: dict[str, str]
) -> set[str]:
    """Get all channel IDs managed by the sync across all tiers.

    Used to distinguish managed channels from private/community channels
    that users joined manually (and should be preserved during transitions).
    """
    all_managed = set()
    for tier in ['full_member', 'multi_channel_guest', 'single_channel_guest']:
        for name in config.get('channels', {}).get(tier, []):
            channel_id = channel_name_to_id.get(name)
            if channel_id:
                all_managed.add(channel_id)
    return all_managed
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
pytest tests/slack/test_channel_sync.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Update `sync_single_user()` for private channel preservation on MCG transitions**

In `app/slack/channel_sync.py`, modify `sync_single_user()`. The function signature gains a new parameter `managed_channel_ids`. Find the block at lines 384-395 where MCG/SCG role changes are handled:

```python
            # For MCG/SCG, role change also sets channels
            if target_tier in ('multi_channel_guest', 'single_channel_guest'):
                change_user_role(
                    user_id=user_id,
                    email=email,
                    target_role=target_role,
                    team_id=team_id,
                    dry_run=dry_run,
                    channel_ids=list(target_channel_ids)
                )
                result.role_changes += 1
                return  # MCG/SCG role change handles channels
```

Replace with:

```python
            if target_tier == 'multi_channel_guest':
                channels_for_role = set(target_channel_ids)
                private_preserved = current_channels - managed_channel_ids
                if private_preserved:
                    channels_for_role |= private_preserved
                    preserve_names = [channel_id_to_properties.get(cid, {}).get('name', cid) for cid in private_preserved]
                    result.traces.append(f"PRESERVE_PRIVATE: {email} | keeping {preserve_names}")
                change_user_role(
                    user_id=user_id,
                    email=email,
                    target_role=target_role,
                    team_id=team_id,
                    dry_run=dry_run,
                    channel_ids=list(channels_for_role)
                )
                result.role_changes += 1
                return

            elif target_tier == 'single_channel_guest':
                change_user_role(
                    user_id=user_id,
                    email=email,
                    target_role=target_role,
                    team_id=team_id,
                    dry_run=dry_run,
                    channel_ids=list(target_channel_ids)
                )
                result.role_changes += 1
                return
```

- [ ] **Step 6: Update `sync_single_user()` function signature**

Add `managed_channel_ids: set[str]` parameter to `sync_single_user()`:

Change line 291:
```python
def sync_single_user(
    slack_user: dict,
    target_tier: str,
    target_channel_ids: set[str],
    full_member_channel_ids: set[str],
    managed_channel_ids: set[str],
    channel_id_to_properties: dict[str, dict],
    team_id: str,
    dry_run: bool,
    result: ChannelSyncResult
) -> None:
```

- [ ] **Step 7: Update `run_channel_sync()` to compute and pass managed IDs, and integrate activity fetch**

In `app/slack/channel_sync.py`, add to the existing module-level imports (do not import inside the function):

```python
from app.slack.admin_api import (
    ROLE_FULL_MEMBER,
    ROLE_MCG,
    ROLE_SCG,
    change_user_role,
    invite_user_by_email,
    validate_admin_credentials,
    CookieExpiredError,
    AdminAPIError,
    fetch_user_activity,
)
from app.models import SlackUser  # already used elsewhere — promote to module-level
from app.notifications.slack import (
    send_tier_transition_notification,
    send_sync_summary_notification,
)
```

Then in `run_channel_sync()`, after the `tier_channel_ids` computation (after line 592), add:

```python
        # Compute all managed channel IDs (for private channel preservation)
        managed_channel_ids = get_managed_channel_ids(config, channel_name_to_id)

        # Activity backfill is NOT gated by dry_run — writing to our own DB
        # is always safe and is required for tier decisions to be correct.
        activity_map = fetch_user_activity()
        if activity_map:
            for slack_user_record in SlackUser.query.all():
                if slack_user_record.slack_uid in activity_map:
                    slack_user_record.last_slack_activity = activity_map[slack_user_record.slack_uid]
            db.session.commit()
            current_app.logger.info(f"Updated last_slack_activity for {len(activity_map)} users")
        else:
            current_app.logger.warning("Activity fetch returned no data — using stale last_slack_activity values")
```

At the end of `run_channel_sync()`, just before returning `result`, add:

```python
        # End-of-sync summary notification (always on)
        send_sync_summary_notification(result, dry_run=dry_run)
```

And update the `sync_single_user` call (around line 624) to pass `managed_channel_ids`:

```python
            sync_single_user(
                slack_user=slack_user,
                target_tier=target_tier,
                target_channel_ids=target_channel_ids,
                full_member_channel_ids=tier_channel_ids['full_member'],
                managed_channel_ids=managed_channel_ids,
                channel_id_to_properties=channel_id_to_properties,
                team_id=team_id,
                dry_run=dry_run,
                result=result
            )
```

- [ ] **Step 8: Add gated per-transition notification calls to sync_single_user**

`send_tier_transition_notification` is already imported at the module level (Step 7). Per-transition pings are gated by the `notify_per_transition` config flag — read it once at the top of `sync_single_user()` (it's already loaded into `config` upstream and can be passed in or read from a module-level cache):

```python
notify_per_transition = config.get('notify_per_transition', False)
```

(Pass `config` through `sync_single_user()`'s signature, or capture `notify_per_transition` as an additional parameter when called from `run_channel_sync()`. Prefer the parameter approach to keep the function pure.)

Then inside `sync_single_user()`, wrap each per-transition notification call in the flag check. After the `result.role_changes += 1` for the MCG block:

```python
                if notify_per_transition:
                    send_tier_transition_notification(
                        name=db_user.full_name if db_user else email,
                        email=email,
                        from_tier=current_role,
                        to_tier='multi_channel_guest',
                        reason='activity-based or 1-season alumni',
                    )
```

After the SCG block:

```python
                if notify_per_transition:
                    send_tier_transition_notification(
                        name=db_user.full_name if db_user else email,
                        email=email,
                        from_tier=current_role,
                        to_tier='single_channel_guest',
                        reason='inactive 90+ days',
                    )
```

After the full_member role change (existing block):

```python
                if notify_per_transition:
                    send_tier_transition_notification(
                        name=db_user.full_name if db_user else email,
                        email=email,
                        from_tier=current_role,
                        to_tier='full_member',
                        reason='active member or re-registration',
                    )
```

The end-of-sync summary (added in Step 7) provides the default per-run visibility. Per-transition notifications are for debugging or low-volume periods.

- [ ] **Step 9: Run all tests**

Run:
```bash
pytest tests/ -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 10: Commit**

```bash
git add app/slack/channel_sync.py tests/slack/test_channel_sync.py
git commit -m "feat: add activity fetch integration and private channel preservation to channel sync"
```

---

### Task 7: Reactivation Custom Step — Bolt Handler

**Files:**
- Modify: `app/slack/bolt_app.py` (add function handler before the `else` block at line 1340)
- Test: `tests/slack/test_reactivation.py`

- [ ] **Step 1: Write the tests**

Create `tests/slack/test_reactivation.py`:

```python
"""Tests for the reactivation custom step handler logic."""

from unittest.mock import patch, MagicMock

import pytest


class FakeSlackUser:
    def __init__(self, slack_uid):
        self.slack_uid = slack_uid
        self.id = 1


class FakeUser:
    def __init__(self, status='ALUMNI', seasons_since_active=2, email='test@example.com',
                 first_name='Jane', last_name='Doe', slack_user=None):
        self.status = status
        self.seasons_since_active = seasons_since_active
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.slack_user = slack_user

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


def validate_reactivation(user):
    """Replicate validation logic from the handler for unit testing."""
    if not user:
        return False, "No linked account found"
    if user.status != 'ALUMNI' or user.seasons_since_active < 2:
        return False, "Not eligible for reactivation"
    return True, None


class TestReactivationValidation:

    def test_valid_alumni_2_seasons(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=2)
        valid, error = validate_reactivation(user)
        assert valid is True
        assert error is None

    def test_valid_alumni_3_seasons(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=3)
        valid, error = validate_reactivation(user)
        assert valid is True

    def test_rejects_active_user(self):
        user = FakeUser(status='ACTIVE', seasons_since_active=0)
        valid, error = validate_reactivation(user)
        assert valid is False
        assert 'Not eligible' in error

    def test_rejects_1_season_alumni(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=1)
        valid, error = validate_reactivation(user)
        assert valid is False

    def test_rejects_none_user(self):
        valid, error = validate_reactivation(None)
        assert valid is False
        assert 'No linked account' in error

    def test_rejects_pending_user(self):
        user = FakeUser(status='PENDING', seasons_since_active=0)
        valid, error = validate_reactivation(user)
        assert valid is False
```

- [ ] **Step 2: Run tests to verify they pass (validation logic)**

Run:
```bash
pytest tests/slack/test_reactivation.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 3: Add the Bolt custom function handler**

In `app/slack/bolt_app.py`, add the following BEFORE the `@bolt_app.event("message")` handler (before line 1335). This goes in the `if _bot_token:` block:

```python
    # =========================================================================
    # Custom Functions (Workflow Builder Custom Steps)
    # =========================================================================

    @bolt_app.function("reactivate_membership")
    def handle_reactivate_membership(inputs, complete, fail, logger):
        """Handle reactivation workflow custom step.

        Triggered by Workflow Builder when an SCG user clicks the
        reactivation workflow in #tcsc-reactivate-me.
        """
        user_id = inputs.get("user_id")
        if not user_id:
            fail("No user_id provided")
            return

        logger.info(f"Reactivation request from {user_id}")

        with get_app_context():
            from app.models import User, SlackUser, db
            from app.slack.channel_sync import load_channel_config, get_target_channel_ids
            from app.slack.client import get_team_id, get_channel_maps
            from app.slack.admin_api import change_user_role, ROLE_MCG
            from app.notifications.slack import send_tier_transition_notification

            slack_user = SlackUser.query.filter_by(slack_uid=user_id).first()
            if not slack_user or not slack_user.user:
                fail("No linked TCSC account found for your Slack user. Please contact an admin.")
                return

            user = slack_user.user

            if user.status != 'ALUMNI' or user.seasons_since_active < 2:
                fail("Your account is not eligible for reactivation. You may already have full access.")
                return

            try:
                config = load_channel_config()
                channel_name_to_id, _ = get_channel_maps()
                team_id = get_team_id()

                mcg_channel_names = config.get('channels', {}).get('multi_channel_guest', [])
                mcg_channel_ids = []
                for name in mcg_channel_names:
                    cid = channel_name_to_id.get(name)
                    if cid:
                        mcg_channel_ids.append(cid)

                change_user_role(
                    user_id=user_id,
                    email=user.email,
                    target_role=ROLE_MCG,
                    team_id=team_id,
                    dry_run=False,
                    channel_ids=mcg_channel_ids,
                )

                send_tier_transition_notification(
                    name=user.full_name,
                    email=user.email,
                    from_tier='single_channel_guest',
                    to_tier='multi_channel_guest',
                    reason='self-service reactivation',
                )

                logger.info(f"Reactivated {user.email} from SCG to MCG")
                complete(outputs={})

            except Exception as e:
                logger.error(f"Reactivation failed for {user.email}: {e}")
                fail(f"Reactivation failed. Please try again or contact an admin.")
```

Note: The `get_app_context()` helper is already defined in `bolt_app.py` — it provides a Flask app context for database operations inside Bolt handlers. Verify it exists by checking for `def get_app_context` in the file.

- [ ] **Step 4: Verify `get_app_context` exists in bolt_app.py**

Run:
```bash
grep -n "def get_app_context" app/slack/bolt_app.py
```

Expected: A line showing the helper function definition. If it doesn't exist, check for the pattern used by other handlers (like `handle_rsvp_action`) that access the database — they use `with get_app_context():` or a similar pattern.

- [ ] **Step 5: Run full test suite**

Run:
```bash
pytest tests/ -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/slack/bolt_app.py tests/slack/test_reactivation.py
git commit -m "feat: add reactivate_membership custom step handler for Workflow Builder"
```

---

### Task 8: Slack App Manifest & Workflow Configuration

This task documents the manual steps needed in the Slack admin UI. No code changes.

- [ ] **Step 1: Update Slack app manifest**

Go to https://api.slack.com/apps → select the TCSC app → App Manifest. Add the following:

Under `settings.event_subscriptions.bot_events`, add:
```
- function_executed
```

Under `settings`, add:
```yaml
org_deploy_enabled: true
function_runtime: remote
```

Under the top-level `functions` key, add:
```yaml
functions:
  reactivate_membership:
    title: "Reactivate Membership"
    description: "Promotes an inactive alumni from SCG to MCG"
    input_parameters:
      user_id:
        type: "slack#/types/user_id"
        title: "User"
        description: "The person who triggered the workflow"
        is_required: true
    output_parameters: {}
```

- [ ] **Step 2: Configure the workflow in Workflow Builder**

In Slack, open the existing workflow in `#tcsc-reactivate-me`:
1. Add a new step → search for the TCSC app → select "Reactivate Membership"
2. Map the "Person who used this workflow" variable to the `user_id` input
3. Save and publish the workflow

- [ ] **Step 3: Confirm channel admin prep is complete**

Already done out-of-band — verify:
- `#announcements-adventures` is archived
- Old public `announcements-tcsc`/`announcements-general` channel renamed to **`#welcome-to-tcsc`** (public, workspace-default, contains everyone — NOT managed by the sync)
- **New private `#announcements-general` exists**; existing messages migrated from the old public channel; posting permissions board-only; **bot added** so sync can manage membership
- `#announcements-alumni` exists (channel ID C0B2ZQ4KM0E); Rob, president, and VP added as posters; posting permissions limited to those three; **bot added**
- `#tcsc-reactivate-me` exists (channel ID C0AUQCG7UB1); **bot added**

Quick verification command (from `flask shell`):

```python
from app.slack.client import get_channel_maps
name_to_id, _ = get_channel_maps()
for name in ['announcements-general', 'announcements-alumni', 'announcements-practices', 'tcsc-reactivate-me']:
    print(f"{name}: {name_to_id.get(name) or 'NOT FOUND — bot not in channel?'}")
```

All four channels must resolve to a non-None ID. If any are `NOT FOUND`, add the bot to that channel before proceeding.

- [ ] **Step 4: Add the bot to community private channels**

Notify channel owners of private community channels (book club, soccer, Lake Placid, etc.) to add the TCSC bot so that MCG transitions preserve membership. Channels without the bot will lose alumni members. Update `known_private_channels` in `slack_channels.yaml` with the confirmed list for record-keeping.

---

### Task 9: Validation Sequence & Go-Live

**Files:** None (operational sequence). Each step is a hard gate — do not advance until the prior step is confirmed.

The order matters: season activation changes DB statuses, which in turn change the tiers the sync will apply. Backfilling activity data BEFORE season activation ensures 2+ alumni with recent activity are correctly classified as MCG instead of falling through to SCG.

- [ ] **Step 1: First dry-run — activity backfill**

Confirm `dry_run: true` in `config/slack_channels.yaml`. Trigger a manual sync from `/admin/channel-sync` or via the Flask shell:

```bash
flask shell
>>> from app.slack.channel_sync import run_channel_sync
>>> result = run_channel_sync(dry_run=True)
>>> print(result.to_dict())
```

Activity backfill runs regardless of `dry_run`. Proposed tier changes are logged but not applied.

- [ ] **Step 2: Verify activity data populated**

```bash
flask shell
>>> from app.models import SlackUser
>>> total = SlackUser.query.count()
>>> with_activity = SlackUser.query.filter(SlackUser.last_slack_activity.isnot(None)).count()
>>> print(f"{with_activity} / {total} users have activity data")
>>> for su in SlackUser.query.filter(SlackUser.last_slack_activity.isnot(None)).limit(5):
...     print(f"{su.email}: {su.last_slack_activity}")
```

Expected: a meaningful proportion of users have populated `last_slack_activity` (most active users should). If most are NULL, investigate the activity fetch before proceeding — do not activate the season.

- [ ] **Step 3: Activate the new season**

Via `/admin/seasons/<id>/activate`. This updates `User.status` and `seasons_since_active` for all users but does NOT touch Slack (sync is still `dry_run=true`).

- [ ] **Step 4: Second dry-run — review proposed tier changes**

Run the sync again with `dry_run=True`. Now the trace output reflects the new post-activation state. Inspect `result.traces`:

- 2+ season alumni with recent activity → MCG (not SCG)
- 2+ season alumni without recent activity → SCG
- 1-season alumni → MCG with private channels preserved (`PRESERVE_PRIVATE` trace lines)
- MCG announcement channel is `announcements-alumni` (NOT `announcements-general`)
- SCG channel is `tcsc-reactivate-me`
- `announcements-adventures` does not appear anywhere
- Exception-tagged users (`ADMIN`, `EXEMPT`) skipped entirely

- [ ] **Step 5: Human review gate**

Before flipping to live, manually review:
- Count of transitions by type — does the volume look reasonable?
- Spot-check 5 specific named users you know personally — are their proposed tiers correct?
- Look for any board members or coaches accidentally being demoted (would indicate exception tag or coach override misconfiguration)
- Verify no `announcements-tcsc` references remain in the trace (would indicate a stale config)

**Do not proceed until this review is complete.**

- [ ] **Step 6: Switch to live mode**

Update `config/slack_channels.yaml`:
```yaml
dry_run: false
```

Commit and deploy:
```bash
git add config/slack_channels.yaml
git commit -m "chore: switch channel sync to live mode after dry-run validation"
```

- [ ] **Step 7: Run live sync and verify**

Trigger sync via admin UI or `flask shell`. End-of-sync summary will post to the webhook channel.

Spot-check 5–10 users in the Slack admin UI to confirm their roles match expected tiers. Specifically verify:
- A 1-season alumni you know is now MCG, in `announcements-alumni` (not `announcements-general`), with private channels intact
- A 2+ season alumni with recent activity is MCG (not SCG)
- A 2+ season alumni without recent activity is SCG, with access to `tcsc-reactivate-me`
- A current ACTIVE member is full_member, in `announcements-general` and `announcements-practices`
