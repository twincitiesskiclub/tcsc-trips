"""Tests for PracticeLead → PracticeLeadInfo conversion edge cases."""

from types import SimpleNamespace

from app.practices.interfaces import LeadRole
from app.practices.service import convert_lead_to_info


def _fake_lead(**kw):
    return SimpleNamespace(
        id=kw.get("id", 5),
        practice_id=kw.get("practice_id", 2),
        user_id=kw.get("user_id", 99),
        role=kw.get("role", "coach"),
        confirmed=kw.get("confirmed", False),
        confirmed_at=kw.get("confirmed_at", None),
        user=kw.get("user", None),
    )


def test_missing_user_returns_visible_degraded_entry():
    lead = _fake_lead(user=None, role="coach", user_id=99)
    info = convert_lead_to_info(lead)
    assert info is not None, "lead with unresolved user must not be dropped"
    assert info.role == LeadRole.COACH
    assert info.user_id == 99
    assert "Unknown" in info.display_name
    assert info.slack_user_id is None


def test_none_lead_still_returns_none():
    assert convert_lead_to_info(None) is None


def test_resolved_user_unchanged():
    user = SimpleNamespace(
        id=99, first_name="Casey", last_name="Coach",
        email="casey@x.org", slack_user=SimpleNamespace(slack_uid="U999"),
    )
    info = convert_lead_to_info(_fake_lead(user=user, role="coach"))
    assert info.display_name == "Casey Coach"
    assert info.slack_user_id == "U999"
    assert info.role == LeadRole.COACH
