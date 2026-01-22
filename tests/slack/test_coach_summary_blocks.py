"""Tests for coach weekly summary Block Kit helpers."""

from datetime import datetime

import pytest

from app.practices.interfaces import (
    LeadRole,
    PracticeInfo,
    PracticeLeadInfo,
    PracticeStatus,
)
from app.slack.blocks import _practice_needs_attention


def _make_practice(
    workout_description: str | None = None,
    leads: list[PracticeLeadInfo] | None = None,
) -> PracticeInfo:
    """Create a minimal PracticeInfo for testing."""
    return PracticeInfo(
        id=1,
        date=datetime(2025, 1, 14, 18, 0),
        day_of_week="Tuesday",
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
