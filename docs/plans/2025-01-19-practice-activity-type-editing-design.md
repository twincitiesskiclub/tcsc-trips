# Practice Activity & Type Editing from Slack

## Overview

Add activity and type fields to the coach practice summary edit modal, allowing coaches to edit these values directly from Slack.

## Changes

### 1. Edit Modal (`app/slack/modals.py`)

Add two new `multi_static_select` fields to `build_practice_edit_full_modal()`:

- **Activities**: Multi-select populated from `PracticeActivity.query.all()`, pre-selected with current practice activities
- **Types**: Multi-select populated from `PracticeType.query.all()`, pre-selected with current practice types

### 2. Button Handler (`app/slack/bolt_app.py`)

Update `handle_edit_practice_full()` to:
- Query all activities from database
- Query all types from database
- Pass both to the modal builder

### 3. Submission Handler (`app/slack/bolt_app.py`)

Update `handle_practice_edit_full_submission()` to:
- Extract selected activity IDs from modal values
- Extract selected type IDs from modal values
- Clear existing `practice.activities` and `practice.types`
- Add newly selected activities and types
- Commit (already happens at end of handler)

### 4. Modal Field Order

Reorder fields for logical grouping:

1. Activities (new)
2. Types (new)
3. Coaches (moved up)
4. Practice Leads (moved up)
5. Location
6. Warmup Description
7. Main Workout
8. Cooldown
9. Options/Flags (dark practice, social)
10. Notification checkbox

### 5. Summary Post Display

No changes needed - existing rebuild logic in submission handler will pick up new values automatically.

## Files to Modify

| File | Changes |
|------|---------|
| `app/slack/modals.py` | Add activity/type selects, reorder fields |
| `app/slack/bolt_app.py` | Query activities/types in handler, save on submit |
