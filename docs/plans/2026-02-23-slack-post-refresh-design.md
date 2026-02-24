# Design: Centralized Slack Post Refresh

**Date:** 2026-02-23
**Status:** Approved

## Problem

When a practice is modified in the database (edited, cancelled, deleted, RSVP'd), not all Slack posts update to reflect the change. The full edit modal in Slack updates 4-5 post types, but the admin webapp routes, quick edit modal, workout entry, slash command RSVP, and admin cancel/delete update zero or one.

## Solution

Create a single `refresh_practice_posts()` function that updates ALL Slack posts for a given practice. Every code path that modifies a practice calls this one function after commit.

### New module: `app/slack/practices/refresh.py`

```python
def refresh_practice_posts(practice, change_type='edit', actor_slack_id=None, notify=True):
    """
    Update all Slack posts for a practice after DB changes.

    Args:
        practice: Practice model instance (already committed to DB)
        change_type: 'edit' | 'cancel' | 'delete' | 'rsvp' | 'workout' | 'create'
        actor_slack_id: Slack UID of person who made the change (for edit logs)
        notify: Whether to post thread notifications (edit logs)

    Returns:
        dict with results per post type
    """
```

Internally calls existing functions:
- `update_practice_slack_post()` / `update_practice_as_cancelled()` for announcement
- `update_collab_post()` for collab review
- Coach summary rebuild via `chat_update()` with `build_coach_weekly_summary_blocks()`
- Weekly summary rebuild via `chat_update()` with `build_weekly_summary_blocks()`
- `update_practice_rsvp_counts()` for RSVP-only changes
- `log_practice_edit()` / `log_collab_edit()` / `log_coach_summary_edit()` for thread notifications

Each step guarded by field existence check (e.g., only update collab if `slack_collab_message_ts` exists). Each step wrapped in try/except so one failure doesn't block others.

### New migration: `slack_weekly_summary_ts`

Add `slack_weekly_summary_ts` column to Practice model (nullable String(50)). Same pattern as `slack_coach_summary_ts`. Populated when `run_weekly_summary()` posts the weekly summary.

### Call sites (replace scattered logic)

| Location | change_type | Notes |
|----------|------------|-------|
| `admin_practices.edit_practice()` | `'edit'` | Replaces existing `update_practice_slack_post()` call |
| `admin_practices.cancel_practice()` | `'cancel'` | New (was missing) |
| `admin_practices.delete_practice()` | `'delete'` | New, called BEFORE db delete |
| `bolt_app: practice_edit` (quick edit) | `'edit'` | New (was missing) |
| `bolt_app: practice_edit_full` | `'edit'` | Replaces ~80 lines of inline update logic |
| `bolt_app: workout_entry` | `'workout'` | New (was missing) |
| `bolt_app: cancellation_approve` | `'cancel'` | Replaces existing `update_practice_as_cancelled()` call |
| `bolt_app: practice_create` | `'create'` | Coach summary only (practice not yet announced) |
| `commands: _handle_rsvp_command` | `'rsvp'` | New (was missing) |
| `bolt_app: _process_lead_confirmation` | `'edit'` | New (was missing) |

### Edge cases handled inside the function

- **Delete:** Called before `db.session.delete()`. Cleans up Slack messages using practice's stored ts fields.
- **Combined lift posts:** `update_practice_slack_post()` already handles detection and multi-practice rebuild.
- **No actor:** When `actor_slack_id=None` (admin routes), edit log thread replies are skipped.
- **Weather:** Not refreshed by this function. Weather is only added by the 24h pre-practice check via `update_practice_announcement()`.
- **Error isolation:** Each post type update is independent; failures don't cascade.

## Out of Scope

- App Home proactive refresh (on-open rebuild is sufficient)
- Daily recap updates (morning snapshot is sufficient)
- Notification-only improvements (edit thread logs are secondary to post accuracy)
