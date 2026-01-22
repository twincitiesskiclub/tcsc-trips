"""Tests for coach weekly summary Block Kit helpers."""

from datetime import datetime

import pytest

from app.practices.interfaces import (
    LeadRole,
    PracticeInfo,
    PracticeLeadInfo,
    PracticeStatus,
)
from app.slack.blocks import _practice_needs_attention, build_coach_weekly_summary_blocks


def _make_practice(
    id: int = 1,
    date: datetime | None = None,
    workout_description: str | None = None,
    leads: list[PracticeLeadInfo] | None = None,
) -> PracticeInfo:
    """Create a minimal PracticeInfo for testing."""
    if date is None:
        date = datetime(2025, 1, 14, 18, 0)
    return PracticeInfo(
        id=id,
        date=date,
        day_of_week=date.strftime('%A'),
        status=PracticeStatus.SCHEDULED,
        workout_description=workout_description,
        leads=leads or [],
    )


def _make_lead(role: LeadRole, slack_user_id: str | None = None) -> PracticeLeadInfo:
    """Create a minimal PracticeLeadInfo for testing."""
    return PracticeLeadInfo(
        id=1,
        practice_id=1,
        user_id=1,
        display_name="Test User",
        slack_user_id=slack_user_id,
        role=role,
    )


class TestPracticeNeedsAttention:
    """Tests for _practice_needs_attention helper."""

    def test_missing_workout_needs_attention(self):
        """Practice without workout description needs attention."""
        practice = _make_practice(
            workout_description=None,
            leads=[_make_lead(LeadRole.LEAD), _make_lead(LeadRole.COACH)],
        )
        assert _practice_needs_attention(practice) is True

    def test_missing_coach_needs_attention(self):
        """Practice without coach assignment needs attention."""
        practice = _make_practice(
            workout_description="Intervals",
            leads=[_make_lead(LeadRole.LEAD)],  # No coach
        )
        assert _practice_needs_attention(practice) is True

    def test_missing_lead_needs_attention(self):
        """Practice without lead assignment needs attention."""
        practice = _make_practice(
            workout_description="Intervals",
            leads=[_make_lead(LeadRole.COACH)],  # No lead
        )
        assert _practice_needs_attention(practice) is True

    def test_complete_practice_does_not_need_attention(self):
        """Practice with workout, coach, and lead does not need attention."""
        practice = _make_practice(
            workout_description="Intervals",
            leads=[_make_lead(LeadRole.LEAD), _make_lead(LeadRole.COACH)],
        )
        assert _practice_needs_attention(practice) is False

    def test_empty_workout_string_needs_attention(self):
        """Practice with empty string workout needs attention."""
        practice = _make_practice(
            workout_description="",
            leads=[_make_lead(LeadRole.LEAD), _make_lead(LeadRole.COACH)],
        )
        assert _practice_needs_attention(practice) is True

    def test_no_leads_needs_attention(self):
        """Practice with no leads at all needs attention."""
        practice = _make_practice(
            workout_description="Intervals",
            leads=[],
        )
        assert _practice_needs_attention(practice) is True


class TestBuildCoachWeeklySummaryBlocks:
    """Tests for build_coach_weekly_summary_blocks function."""

    def test_location_and_warmup_in_fields(self):
        """Location/types and warmup/cooldown should be in 2-column fields."""
        from app.slack.blocks import build_coach_weekly_summary_blocks
        from app.practices.interfaces import (
            PracticeLocationInfo,
            PracticeActivityInfo,
            PracticeTypeInfo,
        )

        # 2026-01-19 is a Monday, 2026-01-20 is a Tuesday
        week_start = datetime(2026, 1, 19)
        expected_days = [{"day": "tuesday", "time": "18:00", "active": True}]

        # Add location, activities, warmup, cooldown
        practice = PracticeInfo(
            id=1,
            date=datetime(2026, 1, 20, 18, 0),  # Tuesday Jan 20, 2026
            day_of_week="tuesday",
            status=PracticeStatus.SCHEDULED,
            location=PracticeLocationInfo(id=1, name="Wirth Park", spot="Trailhead 4"),
            activities=[
                PracticeActivityInfo(id=1, name="Classic"),
                PracticeActivityInfo(id=2, name="Skate"),
            ],
            practice_types=[PracticeTypeInfo(id=1, name="Intervals")],
            warmup_description="10 min easy ski around the lake",
            cooldown_description="5 min easy cool-down",
            workout_description="4x3min",
            leads=[
                _make_lead(role=LeadRole.COACH),
                _make_lead(role=LeadRole.LEAD),
            ]
        )
        practices = [practice]

        blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

        # Find section with fields
        fields_section = next(
            (b for b in blocks if b.get('type') == 'section' and b.get('fields')),
            None
        )

        assert fields_section is not None, "Should have a section with fields"
        assert len(fields_section['fields']) == 2, "Should have 2 columns"

        # Left column should have location info
        left_col = fields_section['fields'][0]['text']
        assert 'Location' in left_col or 'Wirth Park' in left_col

        # Right column should have warmup/cooldown
        right_col = fields_section['fields'][1]['text']
        assert 'Warmup' in right_col or 'Cooldown' in right_col

    def test_header_shows_attention_count(self):
        """Header should show count of practices needing attention."""
        week_start = datetime(2026, 1, 20)  # Monday
        expected_days = [
            {"day": "tuesday", "time": "18:00", "active": True},
            {"day": "thursday", "time": "18:00", "active": True},
        ]

        # One complete, one incomplete
        practices = [
            _make_practice(
                id=1,
                date=datetime(2026, 1, 21, 18, 0),
                workout_description="Workout",
                leads=[
                    _make_lead(role=LeadRole.COACH),
                    _make_lead(role=LeadRole.LEAD),
                ],
            ),
            _make_practice(
                id=2,
                date=datetime(2026, 1, 23, 18, 0),
                workout_description=None,  # Missing!
                leads=[],
            ),
        ]

        blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

        # Find header block
        header = next(b for b in blocks if b.get("type") == "header")
        header_text = header["text"]["text"]

        assert ":warning:" in header_text
        assert "1 need" in header_text

    def test_edit_button_is_actions_block_at_bottom(self):
        """Edit button should be in actions block at bottom for better mobile UX."""
        week_start = datetime(2026, 1, 19)  # Monday
        expected_days = [{"day": "tuesday", "time": "18:00", "active": True}]

        practices = [
            _make_practice(
                id=1,
                date=datetime(2026, 1, 20, 18, 0),  # Tuesday
                workout_description="Workout",
                leads=[
                    _make_lead(role=LeadRole.COACH),
                    _make_lead(role=LeadRole.LEAD),
                ],
            ),
        ]

        blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

        # Find actions blocks with Edit button
        actions_blocks = [
            b for b in blocks
            if b.get('type') == 'actions'
        ]

        assert len(actions_blocks) >= 1

        # Should have Edit button
        edit_actions = actions_blocks[0]
        edit_button = edit_actions['elements'][0]
        assert edit_button['type'] == 'button'
        assert edit_button['action_id'] == 'edit_practice_full'
        assert 'Edit' in edit_button['text']['text']

    def test_edit_button_danger_style_when_incomplete(self):
        """Edit button should have danger style when practice needs attention."""
        week_start = datetime(2026, 1, 19)  # Monday
        expected_days = [{"day": "tuesday", "time": "18:00", "active": True}]

        # Incomplete practice (no workout, no leads)
        practices = [
            _make_practice(
                id=1,
                date=datetime(2026, 1, 20, 18, 0),  # Tuesday
                workout_description=None,
                leads=[]
            ),
        ]

        blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

        # Find actions block with Edit button
        actions_block = next(
            b for b in blocks
            if b.get('type') == 'actions'
        )

        assert actions_block['elements'][0].get('style') == 'danger'

    def test_practice_header_has_warning_badge_when_incomplete(self):
        """Practice header should show :warning: badge when needs attention."""
        week_start = datetime(2026, 1, 19)  # Monday
        expected_days = [{"day": "tuesday", "time": "18:00", "active": True}]

        # Incomplete practice
        practices = [
            _make_practice(
                id=1,
                date=datetime(2026, 1, 20, 18, 0),  # Tuesday
                workout_description=None,
                leads=[]
            ),
        ]

        blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

        # Find section with :calendar: (the practice header)
        header_section = next(
            b for b in blocks
            if b.get('type') == 'section' and ':calendar:' in b.get('text', {}).get('text', '')
        )

        header_text = header_section['text']['text']
        assert ":warning:" in header_text

    def test_flags_and_assignments_in_single_context(self):
        """Flags and coach/lead should be combined in one context block."""
        from app.slack.blocks import build_coach_weekly_summary_blocks
        from app.practices.interfaces import SocialLocationInfo

        # Jan 19, 2026 is Monday (week_start must be Monday)
        week_start = datetime(2026, 1, 19)
        expected_days = [{"day": "tuesday", "time": "18:00", "active": True}]

        practice = PracticeInfo(
            id=1,
            date=datetime(2026, 1, 20, 18, 0),  # Jan 20, 2026 is Tuesday
            day_of_week="tuesday",
            status="scheduled",
            is_dark_practice=True,
            has_social=True,
            social_location=SocialLocationInfo(id=1, name="Bar"),
            workout_description="Workout",
            leads=[
                _make_lead(role=LeadRole.COACH, slack_user_id="U123"),
                _make_lead(role=LeadRole.LEAD, slack_user_id="U456"),
            ]
        )
        practices = [practice]

        blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

        # Count non-footer context blocks
        context_blocks = [b for b in blocks if b.get('type') == 'context']
        non_footer = [c for c in context_blocks if ':bulb:' not in c.get('elements', [{}])[0].get('text', '')]

        # Should be exactly 1 combined context
        assert len(non_footer) == 1

        combined_text = non_footer[0]['elements'][0]['text']
        assert ':new_moon:' in combined_text  # Dark
        assert ':tropical_drink:' in combined_text  # Social
        assert '<@U123>' in combined_text or 'U123' in combined_text  # Coach
        assert '<@U456>' in combined_text or 'U456' in combined_text  # Lead

    def test_empty_day_uses_section_accessory(self):
        """Empty day placeholder has Add Practice button as section accessory."""
        from app.slack.blocks import build_coach_weekly_summary_blocks

        # Jan 19, 2026 is Monday (week_start must be Monday)
        week_start = datetime(2026, 1, 19)
        expected_days = [{"day": "tuesday", "time": "18:00", "active": True}]
        practices = []  # No practices = empty day

        blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

        # Find section blocks (excluding header)
        section_blocks = [b for b in blocks if b.get('type') == 'section']

        # Should have exactly 1 section (empty day placeholder)
        assert len(section_blocks) == 1

        empty_day = section_blocks[0]
        # Should have "No practice scheduled" text
        assert "No practice scheduled" in empty_day.get('text', {}).get('text', '')

        # Should have accessory button (not separate actions block)
        accessory = empty_day.get('accessory')
        assert accessory is not None
        assert accessory.get('type') == 'button'
        assert "Add Practice" in accessory.get('text', {}).get('text', '')
        assert accessory.get('action_id') == 'create_practice_from_summary'
        assert accessory.get('style') == 'primary'

        # Verify no separate actions block
        actions_blocks = [b for b in blocks if b.get('type') == 'actions']
        assert len(actions_blocks) == 0

    def test_block_count_is_optimized(self):
        """Verify block count is optimized for typical week.

        Expected blocks per practice: 6 (header+fields+workout+context+actions+divider)
        Expected blocks per empty day: 2 (section+divider)
        Plus: header + initial divider + footer context = 3

        3 practices + 2 empty days = 18 + 4 + 3 = 25 blocks
        """
        from app.slack.blocks import build_coach_weekly_summary_blocks
        from app.practices.interfaces import PracticeLocationInfo

        # Jan 19, 2026 is Monday (week_start must be Monday)
        week_start = datetime(2026, 1, 19)
        expected_days = [
            {"day": "tuesday", "active": True},
            {"day": "wednesday", "active": True},
            {"day": "thursday", "active": True},
            {"day": "friday", "active": True},
            {"day": "saturday", "active": True},
        ]

        # 3 practices (Tue, Wed, Sat) + 2 empty days (Thu, Fri)
        practices = [
            PracticeInfo(
                id=1,
                date=datetime(2026, 1, 20, 18, 0),
                day_of_week="tuesday",
                status="scheduled",
                workout_description="Workout 1",
                leads=[
                    _make_lead(LeadRole.COACH, "U1"),
                    _make_lead(LeadRole.LEAD, "U2"),
                ],
            ),
            PracticeInfo(
                id=2,
                date=datetime(2026, 1, 21, 18, 0),
                day_of_week="wednesday",
                status="scheduled",
                workout_description="Workout 2",
                leads=[
                    _make_lead(LeadRole.COACH, "U3"),
                    _make_lead(LeadRole.LEAD, "U4"),
                ],
            ),
            PracticeInfo(
                id=3,
                date=datetime(2026, 1, 24, 9, 0),
                day_of_week="saturday",
                status="scheduled",
                workout_description="Workout 3",
                leads=[
                    _make_lead(LeadRole.COACH, "U5"),
                    _make_lead(LeadRole.LEAD, "U6"),
                ],
            ),
        ]

        blocks = build_coach_weekly_summary_blocks(practices, expected_days, week_start)

        # Should be around 25 blocks
        # 3 practices × 6 = 18
        # 2 empty days × 2 = 4
        # header + divider + footer = 3
        assert len(blocks) <= 28, f"Block count {len(blocks)} exceeds target of 28"
        assert len(blocks) >= 22, f"Block count {len(blocks)} unexpectedly low"

        # Practices should have Edit buttons in actions blocks
        actions_blocks = [b for b in blocks if b.get('type') == 'actions']
        assert len(actions_blocks) == 3, f"Expected 3 actions blocks (one per practice), got {len(actions_blocks)}"
