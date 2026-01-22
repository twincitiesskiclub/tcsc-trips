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


def _make_lead(role: LeadRole) -> PracticeLeadInfo:
    """Create a minimal PracticeLeadInfo for testing."""
    return PracticeLeadInfo(
        id=1,
        practice_id=1,
        user_id=1,
        display_name="Test User",
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

    def test_edit_button_is_section_accessory(self):
        """Edit button should be inline with header as section accessory."""
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

        # Find section with accessory button
        header_section = next(
            b for b in blocks
            if b.get('type') == 'section' and b.get('accessory')
        )

        assert header_section['accessory'].get('style') == 'danger'

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

        # Find section with accessory button (the practice header)
        header_section = next(
            b for b in blocks
            if b.get('type') == 'section' and b.get('accessory')
        )

        header_text = header_section['text']['text']
        assert ":warning:" in header_text
