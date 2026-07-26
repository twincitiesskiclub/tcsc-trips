"""Drafts in the Sunday coach review post.

The Sunday 8am post to #collab-coaches-practices is where coaches actually
work: it lists the week with Edit buttons and offers "Add Practice" for any
configured slot that has none. Drafts used to be filtered out of it entirely
(the query went through published_practices()), which had two consequences —
the auto-drafted practices coaches are supposed to fill in were invisible in
the one place they'd look, and each drafted slot rendered as an empty
placeholder inviting a coach to create a *second* practice on top of it.

This is also the surface where publishing happens, since it's already the
weekly batch review.
"""

import json
from datetime import datetime

from app.practices.interfaces import (
    LeadRole,
    PracticeInfo,
    PracticeLeadInfo,
    PracticeStatus,
)
from app.slack.blocks import build_coach_weekly_summary_blocks

_WEEK_START = datetime(2099, 5, 4)  # a Monday
_EXPECTED_DAYS = [
    {"day": "tuesday", "time": "18:15", "active": True},
    {"day": "thursday", "time": "18:15", "active": True},
]


def _lead(role: LeadRole) -> PracticeLeadInfo:
    return PracticeLeadInfo(
        id=1, practice_id=1, user_id=1, display_name="TEST Lead",
        slack_user_id="U0TEST", role=role,
    )


def _practice(day, *, is_draft=False, missing=None, id=1):
    date = datetime(2099, 5, day, 18, 15)
    return PracticeInfo(
        id=id,
        date=date,
        day_of_week=date.strftime("%A"),
        status=PracticeStatus.SCHEDULED,
        workout_description="TEST intervals",
        leads=[_lead(LeadRole.LEAD), _lead(LeadRole.COACH)],
        is_draft=is_draft,
        missing_details=missing or [],
    )


def test_a_draft_is_labelled_as_not_yet_visible():
    """A coach reading the week must be able to tell what members can see."""
    blocks = build_coach_weekly_summary_blocks(
        [_practice(5, is_draft=True)], _EXPECTED_DAYS, _WEEK_START)
    text = json.dumps(blocks)

    assert "Draft" in text
    assert "not visible to members" in text.lower()


def test_a_published_practice_is_not_labelled_a_draft():
    blocks = build_coach_weekly_summary_blocks(
        [_practice(5)], _EXPECTED_DAYS, _WEEK_START)

    assert "Draft" not in json.dumps(blocks)


def test_a_draft_slot_does_not_also_offer_add_practice():
    """The duplicate-practice trap.

    A drafted Tuesday that renders as "No practice scheduled" invites a coach
    to add a second practice in the same slot, which is exactly the visible
    chaos generate_draft_block()'s idempotency guard exists to prevent.
    """
    blocks = build_coach_weekly_summary_blocks(
        [_practice(5, is_draft=True)], _EXPECTED_DAYS, _WEEK_START)
    action_ids = [
        element.get("action_id")
        for block in blocks
        for element in (
            block.get("elements", []) if block.get("type") == "actions"
            else [block["accessory"]] if block.get("accessory") else []
        )
    ]

    tuesday_adds = [a for a in action_ids if a == "create_practice_from_summary"]
    assert len(tuesday_adds) == 1, (
        "only Thursday (which genuinely has no practice) should offer Add "
        f"Practice; got {action_ids}"
    )


def test_a_ready_draft_offers_publish():
    blocks = build_coach_weekly_summary_blocks(
        [_practice(5, is_draft=True)], _EXPECTED_DAYS, _WEEK_START)
    text = json.dumps(blocks)

    assert "publish_week_drafts" in text
    assert "Publish 1" in text


def test_a_draft_missing_details_cannot_be_published_yet():
    """Location/type/time are what a member needs; publishing without them
    puts a broken practice in front of the club."""
    blocks = build_coach_weekly_summary_blocks(
        [_practice(5, is_draft=True, missing=["location"])],
        _EXPECTED_DAYS, _WEEK_START)
    text = json.dumps(blocks)

    assert "needs location" in text
    assert "publish_week_drafts" not in text, (
        "nothing is publishable, so the button must not be offered"
    )


def test_publish_counts_only_the_ready_drafts():
    blocks = build_coach_weekly_summary_blocks(
        [
            _practice(5, is_draft=True, id=1),
            _practice(7, is_draft=True, missing=["type"], id=2),
        ],
        _EXPECTED_DAYS, _WEEK_START)
    text = json.dumps(blocks)

    assert "Publish 1" in text
    assert "needs type" in text


def test_publish_button_carries_the_week_it_belongs_to():
    """The handler re-reads the week from the database rather than trusting a
    list of ids baked into a post that may be days old."""
    blocks = build_coach_weekly_summary_blocks(
        [_practice(5, is_draft=True)], _EXPECTED_DAYS, _WEEK_START)
    buttons = [
        element
        for block in blocks if block.get("type") == "actions"
        for element in block["elements"]
        if element.get("action_id") == "publish_week_drafts"
    ]

    assert len(buttons) == 1
    assert buttons[0]["value"] == "2099-05-04"


def test_a_week_with_no_drafts_offers_no_publish_button():
    blocks = build_coach_weekly_summary_blocks(
        [_practice(5)], _EXPECTED_DAYS, _WEEK_START)

    assert "publish_week_drafts" not in json.dumps(blocks)
