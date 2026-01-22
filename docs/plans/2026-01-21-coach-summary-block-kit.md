# Coach Weekly Summary Block Kit Improvements

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve `build_coach_weekly_summary_blocks` to reduce block count (27→17), add status indicators, use visual hierarchy via Block Kit sections/fields/context, and make Edit buttons immediately visible.

**Architecture:** Refactor the existing function to use section accessories for buttons, section fields for 2-column compressed data, context blocks for de-emphasized metadata, and status badges for practices needing attention (missing coach, lead, or workout).

**Tech Stack:** Python, Slack Block Kit, pytest

---

## Task 1: Add Helper Function for Completeness Detection

**Files:**
- Modify: `app/slack/blocks.py` (add before `build_coach_weekly_summary_blocks`)

**Step 1: Write the failing test**

Create test file:
```python
# tests/slack/test_coach_summary_blocks.py
import pytest
from datetime import datetime
from app.slack.blocks import _practice_needs_attention
from app.practices.interfaces import PracticeInfo, LeadInfo, LeadRole

def test_practice_needs_attention_missing_workout():
    """Practice with no workout_description needs attention."""
    practice = PracticeInfo(
        id=1,
        date=datetime(2026, 1, 21, 18, 0),
        workout_description=None,
        leads=[
            LeadInfo(user_id=1, display_name="Alice", role=LeadRole.COACH),
            LeadInfo(user_id=2, display_name="Bob", role=LeadRole.LEAD),
        ]
    )
    assert _practice_needs_attention(practice) == True

def test_practice_needs_attention_missing_coach():
    """Practice with no coach needs attention."""
    practice = PracticeInfo(
        id=1,
        date=datetime(2026, 1, 21, 18, 0),
        workout_description="4x3min intervals",
        leads=[
            LeadInfo(user_id=2, display_name="Bob", role=LeadRole.LEAD),
        ]
    )
    assert _practice_needs_attention(practice) == True

def test_practice_needs_attention_missing_lead():
    """Practice with no lead needs attention."""
    practice = PracticeInfo(
        id=1,
        date=datetime(2026, 1, 21, 18, 0),
        workout_description="4x3min intervals",
        leads=[
            LeadInfo(user_id=1, display_name="Alice", role=LeadRole.COACH),
        ]
    )
    assert _practice_needs_attention(practice) == True

def test_practice_complete():
    """Practice with workout, coach, and lead is complete."""
    practice = PracticeInfo(
        id=1,
        date=datetime(2026, 1, 21, 18, 0),
        workout_description="4x3min intervals",
        leads=[
            LeadInfo(user_id=1, display_name="Alice", role=LeadRole.COACH),
            LeadInfo(user_id=2, display_name="Bob", role=LeadRole.LEAD),
        ]
    )
    assert _practice_needs_attention(practice) == False
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/slack/test_coach_summary_blocks.py -v
```
Expected: FAIL with `ImportError: cannot import name '_practice_needs_attention'`

**Step 3: Write minimal implementation**

Add to `app/slack/blocks.py` before `build_coach_weekly_summary_blocks` (around line 465):

```python
def _practice_needs_attention(practice: PracticeInfo) -> bool:
    """Check if practice needs attention (missing coach, lead, or workout).

    Args:
        practice: PracticeInfo to check

    Returns:
        True if practice is missing coach, lead, or workout description
    """
    has_coach = any(l.role == LeadRole.COACH for l in (practice.leads or []))
    has_lead = any(l.role == LeadRole.LEAD for l in (practice.leads or []))
    has_workout = bool(practice.workout_description)

    return not (has_coach and has_lead and has_workout)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/slack/test_coach_summary_blocks.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add tests/slack/test_coach_summary_blocks.py app/slack/blocks.py
git commit -m "feat(blocks): add _practice_needs_attention helper for coach summary"
```

---

## Task 2: Update Week Header with Attention Count

**Files:**
- Modify: `app/slack/blocks.py:505-517` (header section)

**Step 1: Write the failing test**

Add to `tests/slack/test_coach_summary_blocks.py`:

```python
from app.slack.blocks import build_coach_weekly_summary_blocks

def test_header_shows_attention_count():
    """Header should show count of practices needing attention."""
    from datetime import datetime, timedelta

    week_start = datetime(2026, 1, 20)  # Monday
    expected_days = [
        {"day": "tuesday", "time": "18:00", "active": True},
        {"day": "thursday", "time": "18:00", "active": True},
    ]

    # One complete, one incomplete
    practices = [
        PracticeInfo(
            id=1, date=datetime(2026, 1, 21, 18, 0),
            workout_description="Workout",
            leads=[
                LeadInfo(user_id=1, display_name="A", role=LeadRole.COACH),
                LeadInfo(user_id=2, display_name="B", role=LeadRole.LEAD),
            ]
        ),
        PracticeInfo(
            id=2, date=datetime(2026, 1, 23, 18, 0),
            workout_description=None,  # Missing!
            leads=[]
        ),
    ]

    blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

    # Find header block
    header = next(b for b in blocks if b.get('type') == 'header')
    header_text = header['text']['text']

    assert ":warning:" in header_text
    assert "1 need" in header_text  # "1 need attention" or similar
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_header_shows_attention_count -v
```
Expected: FAIL - header doesn't contain warning

**Step 3: Modify implementation**

Update `app/slack/blocks.py` lines 505-517:

```python
    # ==========================================================================
    # HEADER
    # ==========================================================================
    # Count practices needing attention
    incomplete_count = sum(1 for p in practices if _practice_needs_attention(p))

    header_text = f":clipboard: Coach Review: Week of {week_range}"
    if incomplete_count > 0:
        header_text += f" | :warning: {incomplete_count} need attention"

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": header_text,
            "emoji": True
        }
    })

    blocks.append({"type": "divider"})
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_header_shows_attention_count -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/slack/blocks.py tests/slack/test_coach_summary_blocks.py
git commit -m "feat(blocks): show attention count in coach summary header"
```

---

## Task 3: Refactor Practice Header with Section Accessory Button

**Files:**
- Modify: `app/slack/blocks.py:561-580` and `650-659` (header section and edit button)

**Step 1: Write the failing test**

Add to `tests/slack/test_coach_summary_blocks.py`:

```python
def test_edit_button_is_section_accessory():
    """Edit button should be inline with header as section accessory."""
    week_start = datetime(2026, 1, 20)
    expected_days = [{"day": "tuesday", "time": "18:00", "active": True}]

    practices = [
        PracticeInfo(
            id=1, date=datetime(2026, 1, 21, 18, 0),
            workout_description="Workout",
            leads=[
                LeadInfo(user_id=1, display_name="A", role=LeadRole.COACH),
                LeadInfo(user_id=2, display_name="B", role=LeadRole.LEAD),
            ]
        ),
    ]

    blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

    # Find section with accessory button
    sections_with_accessory = [
        b for b in blocks
        if b.get('type') == 'section' and b.get('accessory')
    ]

    assert len(sections_with_accessory) >= 1

    # First should be the date header with Edit button
    header_section = sections_with_accessory[0]
    assert header_section['accessory']['type'] == 'button'
    assert header_section['accessory']['action_id'] == 'edit_practice_full'
    assert 'Edit' in header_section['accessory']['text']['text']


def test_edit_button_danger_style_when_incomplete():
    """Edit button should have danger style when practice needs attention."""
    week_start = datetime(2026, 1, 20)
    expected_days = [{"day": "tuesday", "time": "18:00", "active": True}]

    # Incomplete practice (no workout)
    practices = [
        PracticeInfo(
            id=1, date=datetime(2026, 1, 21, 18, 0),
            workout_description=None,
            leads=[]
        ),
    ]

    blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

    # Find section with accessory button
    header_section = next(
        b for b in blocks
        if b.get('type') == 'section' and b.get('accessory')
    )

    assert header_section['accessory'].get('style') == 'danger'
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_edit_button_is_section_accessory -v
pytest tests/slack/test_coach_summary_blocks.py::test_edit_button_danger_style_when_incomplete -v
```
Expected: FAIL - no section accessory

**Step 3: Modify implementation**

Replace lines 561-580 and DELETE lines 650-659 (old actions block):

```python
            # Header line with date/time
            header_text = f":calendar: *{day_full}, {month_short} {day_num}{day_suffix} at {time_str}*"

            # Add warning badge if incomplete
            needs_attention = _practice_needs_attention(practice)
            if needs_attention:
                header_text += " :warning:"

            # Section with accessory Edit button (inline, no scrolling)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": header_text
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":pencil2: Edit", "emoji": True},
                    "action_id": "edit_practice_full",
                    "value": str(practice.id),
                    **({"style": "danger"} if needs_attention else {})
                }
            })
```

Remove the old actions block (lines 650-659 approximately):
```python
            # DELETE THIS SECTION:
            # # Edit button
            # blocks.append({
            #     "type": "actions",
            #     ...
            # })
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_edit_button_is_section_accessory -v
pytest tests/slack/test_coach_summary_blocks.py::test_edit_button_danger_style_when_incomplete -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/slack/blocks.py tests/slack/test_coach_summary_blocks.py
git commit -m "feat(blocks): move Edit button to section accessory with danger style"
```

---

## Task 4: Add Two-Column Fields (Location/Types + Warmup/Cooldown)

**Files:**
- Modify: `app/slack/blocks.py` (after header section, before workout)

**Step 1: Write the failing test**

Add to `tests/slack/test_coach_summary_blocks.py`:

```python
def test_location_and_warmup_in_fields():
    """Location/types and warmup/cooldown should be in 2-column fields."""
    week_start = datetime(2026, 1, 20)
    expected_days = [{"day": "tuesday", "time": "18:00", "active": True}]

    from app.practices.interfaces import LocationInfo, ActivityInfo

    practices = [
        PracticeInfo(
            id=1, date=datetime(2026, 1, 21, 18, 0),
            location=LocationInfo(name="Wirth Park", spot="Trailhead 4"),
            activities=[ActivityInfo(name="Classic"), ActivityInfo(name="Skate")],
            warmup_description="10 min easy ski",
            cooldown_description="5 min easy",
            workout_description="4x3min",
            leads=[
                LeadInfo(user_id=1, display_name="A", role=LeadRole.COACH),
                LeadInfo(user_id=2, display_name="B", role=LeadRole.LEAD),
            ]
        ),
    ]

    blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

    # Find section with fields
    fields_section = next(
        (b for b in blocks if b.get('type') == 'section' and b.get('fields')),
        None
    )

    assert fields_section is not None
    assert len(fields_section['fields']) == 2

    # Left column should have location
    left_col = fields_section['fields'][0]['text']
    assert 'Location' in left_col or 'Wirth Park' in left_col

    # Right column should have warmup/cooldown
    right_col = fields_section['fields'][1]['text']
    assert 'Warmup' in right_col or 'Cooldown' in right_col
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_location_and_warmup_in_fields -v
```
Expected: FAIL - no fields section

**Step 3: Modify implementation**

Add after the header section (replace old context_parts logic):

```python
            # ==========================================================
            # TWO-COLUMN FIELDS: Location/Types + Warmup/Cooldown
            # ==========================================================
            fields = []

            # LEFT COLUMN: Location + Activities + Types
            location_name = practice.location.name if practice.location else "TBD"
            location_spot = practice.location.spot if practice.location and practice.location.spot else None
            full_location = f"{location_name} - {location_spot}" if location_spot else location_name

            location_col = f"*:round_pushpin: Location*\n{full_location}"
            if practice.activities:
                activity_names = ", ".join([a.name for a in practice.activities])
                location_col += f"\n:skier: {activity_names}"
            if practice.practice_types:
                type_names = ", ".join([t.name for t in practice.practice_types])
                location_col += f" | :snowflake: {type_names}"
            fields.append({"type": "mrkdwn", "text": location_col})

            # RIGHT COLUMN: Warmup + Cooldown (truncated)
            warmup_cooldown = "*:fire: Warmup / :ice_cube: Cooldown*\n"
            if practice.warmup_description:
                warmup = practice.warmup_description[:40] + "..." if len(practice.warmup_description) > 40 else practice.warmup_description
                warmup_cooldown += f"{warmup}\n"
            else:
                warmup_cooldown += "_No warmup_\n"

            if practice.cooldown_description:
                cooldown = practice.cooldown_description[:40] + "..." if len(practice.cooldown_description) > 40 else practice.cooldown_description
                warmup_cooldown += cooldown
            else:
                warmup_cooldown += "_No cooldown_"
            fields.append({"type": "mrkdwn", "text": warmup_cooldown})

            blocks.append({
                "type": "section",
                "fields": fields
            })
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_location_and_warmup_in_fields -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/slack/blocks.py tests/slack/test_coach_summary_blocks.py
git commit -m "feat(blocks): add 2-column fields for location and warmup/cooldown"
```

---

## Task 5: Full-Width Workout Section (No Truncation)

**Files:**
- Modify: `app/slack/blocks.py` (workout section)

**Step 1: Write the failing test**

Add to `tests/slack/test_coach_summary_blocks.py`:

```python
def test_workout_not_truncated():
    """Workout description should NOT be truncated."""
    week_start = datetime(2026, 1, 20)
    expected_days = [{"day": "tuesday", "time": "18:00", "active": True}]

    long_workout = "A" * 200  # 200 character workout

    practices = [
        PracticeInfo(
            id=1, date=datetime(2026, 1, 21, 18, 0),
            workout_description=long_workout,
            leads=[
                LeadInfo(user_id=1, display_name="A", role=LeadRole.COACH),
                LeadInfo(user_id=2, display_name="B", role=LeadRole.LEAD),
            ]
        ),
    ]

    blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

    # Find workout section (has :nerd_face:)
    workout_section = next(
        (b for b in blocks
         if b.get('type') == 'section'
         and ':nerd_face:' in b.get('text', {}).get('text', '')),
        None
    )

    assert workout_section is not None
    # Full workout should be present, not truncated
    assert long_workout in workout_section['text']['text']
    assert '...' not in workout_section['text']['text']
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_workout_not_truncated -v
```
Expected: FAIL - workout is truncated at 150 chars

**Step 3: Modify implementation**

Replace the workout section (around lines 582-610):

```python
            # ==========================================================
            # FULL-WIDTH WORKOUT SECTION (no truncation)
            # ==========================================================
            if practice.workout_description:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*:nerd_face: Workout*\n{practice.workout_description}"
                    }
                })
            else:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":warning: *Workout:* _Not entered yet - click Edit to add_"
                    }
                })
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_workout_not_truncated -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/slack/blocks.py tests/slack/test_coach_summary_blocks.py
git commit -m "feat(blocks): show full workout without truncation"
```

---

## Task 6: Combine Flags + Coaches + Leads into Single Context

**Files:**
- Modify: `app/slack/blocks.py` (flags and coach/lead sections)

**Step 1: Write the failing test**

Add to `tests/slack/test_coach_summary_blocks.py`:

```python
def test_flags_and_assignments_in_single_context():
    """Flags and coach/lead should be combined in one context block."""
    week_start = datetime(2026, 1, 20)
    expected_days = [{"day": "tuesday", "time": "18:00", "active": True}]

    from app.practices.interfaces import SocialLocationInfo

    practices = [
        PracticeInfo(
            id=1, date=datetime(2026, 1, 21, 18, 0),
            is_dark_practice=True,
            has_social=True,
            social_location=SocialLocationInfo(name="Bar"),
            workout_description="Workout",
            leads=[
                LeadInfo(user_id=1, slack_user_id="U123", display_name="Alice", role=LeadRole.COACH),
                LeadInfo(user_id=2, slack_user_id="U456", display_name="Bob", role=LeadRole.LEAD),
            ]
        ),
    ]

    blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

    # Count context blocks between header divider and footer divider
    # Should only be ONE context block for flags+assignments
    context_blocks = [b for b in blocks if b.get('type') == 'context']

    # One for footer + one for flags/assignments per practice
    # Footer has ":bulb:" text
    non_footer_contexts = [
        c for c in context_blocks
        if ':bulb:' not in c.get('elements', [{}])[0].get('text', '')
    ]

    # Should be exactly 1 context per practice (combined flags+assignments)
    assert len(non_footer_contexts) == 1

    combined_text = non_footer_contexts[0]['elements'][0]['text']
    assert ':new_moon:' in combined_text  # Dark flag
    assert ':tropical_drink:' in combined_text  # Social flag
    assert '<@U123>' in combined_text  # Coach mention
    assert '<@U456>' in combined_text  # Lead mention
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_flags_and_assignments_in_single_context -v
```
Expected: FAIL - multiple context blocks

**Step 3: Modify implementation**

Replace the flags and coach/lead sections (lines 612-648) with:

```python
            # ==========================================================
            # CONTEXT: Flags + Coaches + Leads (de-emphasized, combined)
            # ==========================================================
            combined_parts = []

            # Flags
            if practice.is_dark_practice:
                combined_parts.append(":new_moon: Dark")
            if practice.has_social:
                combined_parts.append(":tropical_drink: Social")

            # Coaches (with warning if missing)
            coaches = [l for l in practice.leads if l.role == LeadRole.COACH]
            if coaches:
                coach_names = [f"<@{c.slack_user_id}>" if c.slack_user_id else c.display_name for c in coaches]
                combined_parts.append(f":male-teacher: {', '.join(coach_names)}")
            else:
                combined_parts.append(":warning: No coach")

            # Leads (with warning if missing)
            leads = [l for l in practice.leads if l.role == LeadRole.LEAD]
            if leads:
                lead_names = [f"<@{l.slack_user_id}>" if l.slack_user_id else l.display_name for l in leads]
                combined_parts.append(f":people_holding_hands: {', '.join(lead_names)}")
            else:
                combined_parts.append(":warning: No lead")

            # Single context block (de-emphasized, smaller gray text)
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": " | ".join(combined_parts)
                }]
            })
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_flags_and_assignments_in_single_context -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/slack/blocks.py tests/slack/test_coach_summary_blocks.py
git commit -m "feat(blocks): combine flags and assignments into single context block"
```

---

## Task 7: Update Empty Day Placeholder with Section Accessory

**Files:**
- Modify: `app/slack/blocks.py:661-687` (placeholder section)

**Step 1: Write the failing test**

Add to `tests/slack/test_coach_summary_blocks.py`:

```python
def test_empty_day_has_inline_add_button():
    """Empty day should have Add Practice button as section accessory."""
    week_start = datetime(2026, 1, 20)
    expected_days = [
        {"day": "tuesday", "time": "18:00", "active": True},  # Has practice
        {"day": "thursday", "time": "18:00", "active": True},  # No practice
    ]

    practices = [
        PracticeInfo(
            id=1, date=datetime(2026, 1, 21, 18, 0),  # Tuesday
            workout_description="Workout",
            leads=[
                LeadInfo(user_id=1, display_name="A", role=LeadRole.COACH),
                LeadInfo(user_id=2, display_name="B", role=LeadRole.LEAD),
            ]
        ),
        # Thursday has no practice
    ]

    blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

    # Find section with "No practice scheduled" and accessory
    placeholder = next(
        (b for b in blocks
         if b.get('type') == 'section'
         and 'No practice scheduled' in b.get('text', {}).get('text', '')
         and b.get('accessory')),
        None
    )

    assert placeholder is not None
    assert placeholder['accessory']['action_id'] == 'create_practice_from_summary'
    assert placeholder['accessory'].get('style') == 'primary'
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_empty_day_has_inline_add_button -v
```
Expected: FAIL - no accessory on placeholder

**Step 3: Modify implementation**

Replace lines 661-687:

```python
        else:
            # ==========================================================
            # PLACEHOLDER - NO PRACTICE FOR THIS DAY
            # ==========================================================
            day_num = day_date.strftime('%-d')
            day_suffix = _get_day_suffix(int(day_num))
            day_full = day_date.strftime('%A')
            month_short = day_date.strftime('%b')

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":calendar: *{day_full}, {month_short} {day_num}{day_suffix}* — _No practice scheduled_"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":heavy_plus_sign: Add Practice", "emoji": True},
                    "action_id": "create_practice_from_summary",
                    "value": day_date.strftime('%Y-%m-%d'),
                    "style": "primary"
                }
            })
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_empty_day_has_inline_add_button -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/slack/blocks.py tests/slack/test_coach_summary_blocks.py
git commit -m "feat(blocks): use section accessory for Add Practice button"
```

---

## Task 8: Verify Block Count Reduction

**Files:**
- Add test in: `tests/slack/test_coach_summary_blocks.py`

**Step 1: Write the test**

```python
def test_block_count_under_limit():
    """Full week should produce fewer than 20 blocks."""
    week_start = datetime(2026, 1, 20)
    expected_days = [
        {"day": "tuesday", "time": "18:00", "active": True},
        {"day": "thursday", "time": "18:00", "active": True},
        {"day": "saturday", "time": "09:00", "active": True},
    ]

    # 2 practices, 1 empty day
    practices = [
        PracticeInfo(
            id=1, date=datetime(2026, 1, 21, 18, 0),
            workout_description="Workout 1",
            leads=[
                LeadInfo(user_id=1, display_name="A", role=LeadRole.COACH),
                LeadInfo(user_id=2, display_name="B", role=LeadRole.LEAD),
            ]
        ),
        PracticeInfo(
            id=2, date=datetime(2026, 1, 23, 18, 0),
            workout_description="Workout 2",
            leads=[
                LeadInfo(user_id=1, display_name="A", role=LeadRole.COACH),
                LeadInfo(user_id=2, display_name="B", role=LeadRole.LEAD),
            ]
        ),
    ]

    blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

    print(f"\nBlock count: {len(blocks)}")
    for i, b in enumerate(blocks):
        print(f"  {i}: {b.get('type')}")

    # Target: under 20 blocks for a typical week
    # Header(1) + Divider(1) + 2 practices(~5 each) + 1 empty(2) + Footer(1) = ~15
    assert len(blocks) < 20, f"Expected < 20 blocks, got {len(blocks)}"
```

**Step 2: Run test**

```bash
pytest tests/slack/test_coach_summary_blocks.py::test_block_count_under_limit -v -s
```
Expected: PASS with block count printed

**Step 3: Commit**

```bash
git add tests/slack/test_coach_summary_blocks.py
git commit -m "test(blocks): verify block count stays under 20"
```

---

## Task 9: Manual Integration Test

**Step 1: Run the test script**

```bash
python test_practice_post.py post-coach-summary
```

**Step 2: Verify in Slack**

Check #tcsc-devs for the posted message:
- [ ] Header shows attention count if any practices incomplete
- [ ] Edit buttons are inline with date headers
- [ ] Incomplete practices have red Edit buttons
- [ ] Location/types and warmup/cooldown are in 2 columns
- [ ] Full workout is visible (not truncated)
- [ ] Flags + coach/lead are combined in one gray context line
- [ ] Empty days have green "Add Practice" button inline
- [ ] Message doesn't show "See more" (block count OK)

**Step 3: Commit final changes if needed**

```bash
git add -A
git commit -m "feat(blocks): complete coach summary Block Kit improvements"
```

---

## Verification Checklist

- [ ] All unit tests pass: `pytest tests/slack/test_coach_summary_blocks.py -v`
- [ ] Block count < 20 for typical week
- [ ] Manual test shows correct formatting in Slack
- [ ] Edit buttons visible without scrolling
- [ ] Danger style on incomplete practices
- [ ] Visual hierarchy: emphasized (sections), compressed (fields), de-emphasized (context)
