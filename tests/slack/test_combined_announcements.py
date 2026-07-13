"""Coverage for stable combined Strength announcement behavior."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from app.practices.interfaces import PracticeStatus
from app.slack.blocks import (
    build_combined_fallback_text,
    build_combined_lift_blocks,
)
from app.slack.blocks.cancellations import build_practice_cancelled_notice
from app.slack.client import (
    assign_combined_session_emojis,
    get_lead_confirmation_emoji_for_practice,
)
from app.slack.blocks.text import FALLBACK_TEXT_MAX


@pytest.fixture
def app_context():
    app = Flask(__name__)
    app.config["TESTING"] = True
    with app.app_context():
        yield app


def combined_practice(
    practice_id,
    day,
    hour,
    emoji,
    *,
    minute=15,
    status=PracticeStatus.SCHEDULED,
    reason=None,
    workout="3 x 8 strength circuit",
    notes="Bring indoor shoes",
    social=None,
    plan=None,
):
    return SimpleNamespace(
        id=practice_id,
        date=datetime(2026, 7, day, hour, minute),
        status=status,
        slack_session_emoji=emoji,
        location=SimpleNamespace(id=10, name="Balance Fitness", spot=None),
        activities=[SimpleNamespace(id=1, name="Strength")],
        practice_types=[SimpleNamespace(id=2, name="Strength")],
        workout_description=workout,
        logistics_notes=notes,
        has_social=social is not None,
        social_location=(
            SimpleNamespace(id=20, name=social) if social is not None else None
        ),
        plan_reactions=list(plan or []),
        leads=[],
        cancellation_reason=reason,
    )


def model_practice(*args, **kwargs):
    practice = combined_practice(*args, **kwargs)
    practice.slack_channel_id = None
    practice.slack_message_ts = None
    practice.slack_details_ts = None
    practice.location.latitude = None
    practice.location.longitude = None
    practice.location.parking_notes = None
    return practice


def rendered_text(blocks):
    parts = []
    for block in blocks:
        if block["type"] in {"header", "section"}:
            parts.append(block["text"]["text"])
        elif block["type"] == "context":
            parts.extend(item["text"] for item in block["elements"])
    return "\n".join(parts)


def _combined_rsvp_text(blocks):
    matches = [
        item["text"]
        for block in blocks
        if block.get("type") == "context"
        for item in block.get("elements", [])
        if item.get("text", "").startswith("Bop ")
    ]
    assert len(matches) == 1
    return matches[0]


def test_cross_day_mapping_is_only_in_bottom_context():
    practices = [
        combined_practice(1, 14, 18, "six"),
        combined_practice(2, 15, 19, "seven"),
    ]
    blocks = build_combined_lift_blocks(practices)
    text = rendered_text(blocks)
    assert "Choose a session:" not in text
    assert ":six: *Tuesday" not in text
    assert ":seven: *Wednesday" not in text
    assert _combined_rsvp_text(blocks) == (
        "Bop :six: for Tue at 6:15 PM or :seven: for Wed at 7:15 PM "
        "so we'll know you'll be there.\n"
        "Running late? Reply in the thread. <!channel>"
    )


def test_combined_shared_plan_is_appended_to_attendance_line():
    plan = [{
        "emoji": "hatching_chick",
        "label": "first strength practice support",
    }]
    practices = [
        combined_practice(1, 14, 18, "six", plan=plan),
        combined_practice(2, 15, 19, "seven", plan=plan),
    ]
    assert _combined_rsvp_text(build_combined_lift_blocks(practices)) == (
        "Bop :six: for Tue at 6:15 PM or :seven: for Wed at 7:15 PM "
        "so we'll know you'll be there. In addition to your attendance emoji, "
        "hit a :hatching_chick: for first strength practice support.\n"
        "Running late? Reply in the thread. <!channel>"
    )


def test_same_day_rows_and_mapping_use_times_only():
    practices = [
        combined_practice(1, 14, 18, "six", minute=5),
        combined_practice(2, 14, 19, "seven", minute=20),
    ]
    blocks = build_combined_lift_blocks(practices)
    text = rendered_text(blocks)
    assert "*6:05 PM*" in text
    assert "*7:20 PM*" in text
    assert "Tuesday, July 14 · 6:05 PM" not in text
    assert _combined_rsvp_text(blocks) == (
        "Bop :six: for 6:05 PM or :seven: for 7:20 PM "
        "so we'll know you'll be there.\n"
        "Running late? Reply in the thread. <!channel>"
    )


def test_same_day_cancelled_sibling_keeps_time_only_active_mapping():
    practices = [
        combined_practice(1, 14, 18, "six", minute=5),
        combined_practice(
            2,
            14,
            19,
            "seven",
            minute=20,
            status=PracticeStatus.CANCELLED,
            reason="Facility closed",
        ),
    ]
    rsvp = _combined_rsvp_text(build_combined_lift_blocks(practices))
    assert rsvp.startswith(
        "Bop :six: for 6:05 PM so we'll know you'll be there."
    )
    assert "Tue at" not in rsvp
    assert ":seven: for" not in rsvp


def test_three_active_sessions_use_oxford_or_mapping():
    practices = [
        combined_practice(1, 14, 18, "six"),
        combined_practice(2, 15, 19, "seven"),
        combined_practice(3, 16, 20, "eight"),
    ]
    assert _combined_rsvp_text(build_combined_lift_blocks(practices)).startswith(
        "Bop :six: for Tue at 6:15 PM, :seven: for Wed at 7:15 PM, "
        "or :eight: for Thu at 8:15 PM so we'll know you'll be there."
    )


def test_cancelled_sibling_stays_visible_but_leaves_cross_day_mapping():
    practices = [
        combined_practice(1, 14, 18, "six"),
        combined_practice(
            2,
            15,
            19,
            "seven",
            status=PracticeStatus.CANCELLED,
            reason="Facility closed",
        ),
    ]
    blocks = build_combined_lift_blocks(practices)
    assert "Facility closed" in rendered_text(blocks)
    assert _combined_rsvp_text(blocks).startswith(
        "Bop :six: for Tue at 6:15 PM so we'll know you'll be there."
    )
    assert ":seven: for" not in _combined_rsvp_text(blocks)


def test_long_cancellation_reason_preserves_lead_and_every_fallback_session():
    cancelled = combined_practice(
        1,
        14,
        18,
        "six",
        status=PracticeStatus.CANCELLED,
        reason="Facility issue " + ("x" * 5_000),
    )
    cancelled.leads = [SimpleNamespace(
        role=SimpleNamespace(name="COACH"),
        slack_user_id="UCOACH",
        display_name="Coach",
    )]
    practices = [
        cancelled,
        combined_practice(2, 15, 19, "seven"),
        combined_practice(3, 16, 20, "eight"),
    ]

    text = rendered_text(build_combined_lift_blocks(practices))
    fallback = build_combined_fallback_text(practices)

    assert "CANCELLED" in text
    assert "Coach <@UCOACH>" in text
    for value in (
        "Tuesday, July 14 at 6:15 PM",
        "CANCELLED",
        "Balance Fitness",
        "Wednesday, July 15 at 7:15 PM",
        "Active",
        "Thursday, July 16 at 8:15 PM",
        "seven for Wed at 7:15 PM",
        "eight for Thu at 8:15 PM",
    ):
        assert value in fallback


def test_one_displayed_session_keeps_combined_reaction_grammar():
    blocks = build_combined_lift_blocks([
        combined_practice(2, 15, 19, "seven")
    ])
    rsvp = _combined_rsvp_text(blocks)
    assert rsvp.startswith(
        "Bop :seven: for 7:15 PM so we'll know you'll be there."
    )
    assert ":white_check_mark:" not in rsvp


def test_all_cancelled_combined_root_has_no_rsvp_context_or_fallback_tail():
    plan = [{"emoji": "hatching_chick", "label": "new rollerskier"}]
    practices = [
        combined_practice(
            1,
            14,
            18,
            "six",
            status=PracticeStatus.CANCELLED,
            reason="Closed",
            plan=plan,
        ),
        combined_practice(
            2,
            15,
            19,
            "seven",
            status=PracticeStatus.CANCELLED,
            reason="Closed",
            plan=plan,
        ),
    ]
    blocks = build_combined_lift_blocks(practices)
    fallback = build_combined_fallback_text(practices)
    assert not any(
        item.get("text", "").startswith("Bop ")
        for block in blocks if block.get("type") == "context"
        for item in block.get("elements", [])
    )
    for forbidden in ("RSVP", "Additional reaction", "Running late"):
        assert forbidden not in fallback


def test_cancelled_sibling_with_different_plan_suppresses_supplemental_copy():
    active = combined_practice(
        1,
        14,
        18,
        "six",
        plan=[{"emoji": "hatching_chick", "label": "new rollerskier"}],
    )
    cancelled = combined_practice(
        2,
        15,
        19,
        "seven",
        status=PracticeStatus.CANCELLED,
        reason="Closed",
        plan=[{"emoji": "athletic_shoe", "label": "runner"}],
    )
    assert "In addition" not in _combined_rsvp_text(
        build_combined_lift_blocks([active, cancelled])
    )


def test_different_notes_keep_exact_heading_and_text_owner():
    practices = [
        combined_practice(1, 14, 18, "six", notes="Shoes A"),
        combined_practice(2, 15, 19, "seven", notes="Shoes B"),
    ]
    notes_sections = [
        block["text"]["text"] for block in build_combined_lift_blocks(practices)
        if block.get("type") == "section"
        and block.get("text", {}).get("text", "").startswith("*📝 Notes*")
    ]
    assert notes_sections == [
        "*📝 Notes*\n*Tuesday at 6:15 PM*\nShoes A",
        "*📝 Notes*\n*Wednesday at 7:15 PM*\nShoes B",
    ]
    assert all(
        ":six:" not in text and ":seven:" not in text
        for text in notes_sections
    )


def test_divergent_workout_and_social_use_text_owners_not_reactions():
    practices = [
        combined_practice(
            1,
            14,
            18,
            "six",
            workout="Session A circuit",
            notes="Shoes A",
            social="Cafe A",
        ),
        combined_practice(
            2,
            15,
            19,
            "seven",
            workout="Session B circuit",
            notes="Shoes B",
            social="Cafe B",
        ),
    ]
    sections = [
        block["text"]["text"] for block in build_combined_lift_blocks(practices)
        if block.get("type") == "section"
    ]
    owned = "\n".join(
        text for text in sections
        if (
            "Session A" in text
            or "Session B" in text
            or "Cafe A" in text
            or "Cafe B" in text
        )
    )
    assert "Tuesday at 6:15 PM" in owned
    assert "Wednesday at 7:15 PM" in owned
    assert ":six:" not in owned
    assert ":seven:" not in owned


def test_whitespace_only_shared_content_differences_stay_compact():
    first = combined_practice(
        1,
        14,
        18,
        "six",
        workout="3 x 8   strength circuit",
        notes="Bring   indoor shoes",
        social="Cafe  A",
    )
    second = combined_practice(
        2,
        15,
        19,
        "seven",
        workout="  3 x 8 strength circuit  ",
        notes=" Bring indoor   shoes ",
        social=" Cafe A ",
    )

    text = rendered_text(build_combined_lift_blocks([first, second]))
    fallback = build_combined_fallback_text([first, second])

    assert text.count("Workout · Strength") == 1
    assert "3 x 8   strength circuit" in text
    assert text.count("Notes*") == 1
    assert "Bring   indoor shoes" in text
    assert text.count("Social after at") == 1
    assert "Social after at Cafe  A" in text
    assert "Wednesday at 7:15 PM workout" not in fallback
    assert "Workout: 3 x 8   strength circuit" in fallback


def test_combined_fallback_uses_plain_active_mapping_and_complete_tail():
    plan = [{"emoji": "hatching_chick", "label": "first strength support"}]
    practices = [
        combined_practice(1, 14, 18, "six", plan=plan),
        combined_practice(2, 15, 19, "seven", plan=plan),
    ]
    fallback = build_combined_fallback_text(practices)
    assert fallback.endswith(
        "RSVP with six for Tue at 6:15 PM or seven for Wed at 7:15 PM "
        "so we'll know you'll be there. Additional reaction: hatching chick "
        "for first strength support. Running late? Reply in the thread."
    )
    assert "session :six:" not in fallback
    assert "<!channel>" not in fallback


def test_same_day_combined_fallback_uses_time_only_mapping():
    practices = [
        combined_practice(1, 14, 18, "six", minute=5),
        combined_practice(2, 14, 19, "seven", minute=20),
    ]
    fallback = build_combined_fallback_text(practices)
    assert fallback.endswith(
        "RSVP with six for 6:05 PM or seven for 7:20 PM "
        "so we'll know you'll be there. Running late? Reply in the thread."
    )
    assert "six for Tue" not in fallback


def test_combined_fallback_plainifies_authored_slack_control_tokens():
    authored = "support <!channel> :wave:"
    plan = [{"emoji": "evergreen_tree", "label": authored}]
    active = combined_practice(
        1,
        14,
        18,
        "six",
        workout=authored,
        notes=authored,
        social=authored,
        plan=plan,
    )
    cancelled = combined_practice(
        2,
        15,
        19,
        "seven",
        status=PracticeStatus.CANCELLED,
        reason=authored,
        workout=authored,
        notes=authored,
        social=authored,
        plan=plan,
    )
    active.location.name = authored
    cancelled.location.name = authored

    fallback = build_combined_fallback_text(
        [active, cancelled], announcement_notice=authored
    )

    assert "<!channel>" not in fallback
    assert ":wave:" not in fallback
    assert "support" in fallback
    assert active.plan_reactions[0]["label"] == authored
    assert cancelled.cancellation_reason == authored


def test_combined_fallback_plainification_is_total_for_long_colon_tokens():
    token = ":" + ("a" * 81) + ":"
    practices = [
        combined_practice(1, 14, 18, "six", workout=f"Workout {token}"),
        combined_practice(2, 15, 19, "seven", workout=f"Workout {token}"),
    ]

    fallback = build_combined_fallback_text(practices)

    assert token not in fallback
    assert "a" * 81 in fallback
    assert practices[0].workout_description == f"Workout {token}"


def test_mixed_cancelled_fallback_maps_only_active_session():
    practices = [
        combined_practice(1, 14, 18, "six"),
        combined_practice(
            2,
            15,
            19,
            "seven",
            status=PracticeStatus.CANCELLED,
            reason="Facility closed",
        ),
    ]
    fallback = build_combined_fallback_text(practices)
    assert "CANCELLED: Facility closed" in fallback
    assert fallback.endswith(
        "RSVP with six for Tue at 6:15 PM so we'll know you'll be there. "
        "Running late? Reply in the thread."
    )
    assert "seven for" not in fallback


def test_long_combined_content_preserves_complete_required_tail():
    plan = [{"emoji": "evergreen_tree", "label": "endurance"}]
    practices = [
        combined_practice(1, 14, 18, "six", workout="w" * 10_000, plan=plan),
        combined_practice(2, 15, 19, "seven", notes="n" * 10_000, plan=plan),
    ]
    fallback = build_combined_fallback_text(practices)
    assert fallback.endswith(
        "RSVP with six for Tue at 6:15 PM or seven for Wed at 7:15 PM "
        "so we'll know you'll be there. Additional reaction: evergreen tree "
        "for endurance. Running late? Reply in the thread."
    )
    assert len(fallback) <= FALLBACK_TEXT_MAX


def test_different_plan_snapshots_hide_shared_plan_legend():
    practices = [
        combined_practice(
            1,
            14,
            18,
            "six",
            plan=[{"emoji": "evergreen_tree", "label": "Endurance"}],
        ),
        combined_practice(
            2,
            15,
            19,
            "seven",
            plan=[{"emoji": "athletic_shoe", "label": "Run"}],
        ),
    ]

    text = rendered_text(build_combined_lift_blocks(practices))

    assert "In addition to your attendance emoji" not in text
    assert ":evergreen_tree:" not in text
    assert ":athletic_shoe:" not in text


def test_assignment_persists_unique_values_without_remapping_saved_values():
    earlier = combined_practice(1, 14, 18, None)
    later = combined_practice(2, 15, 19, "seven")

    with patch("app.models.db") as mock_db:
        result = assign_combined_session_emojis([later, earlier])

    assert result == {"success": True, "emojis": {1: "six", 2: "seven"}}
    assert earlier.slack_session_emoji == "six"
    assert later.slack_session_emoji == "seven"
    mock_db.session.commit.assert_called_once_with()

    with patch("app.models.db") as mock_db:
        reversed_result = assign_combined_session_emojis([earlier, later])

    assert reversed_result == result
    mock_db.session.commit.assert_called_once_with()


def test_duplicate_saved_values_fail_without_mutating_or_committing():
    earlier = combined_practice(1, 14, 18, "six")
    later = combined_practice(2, 15, 19, "six")

    with patch("app.models.db") as mock_db:
        result = assign_combined_session_emojis([earlier, later])

    assert result["success"] is False
    assert "Duplicate combined-session emoji :six:" in result["error"]
    assert (earlier.slack_session_emoji, later.slack_session_emoji) == (
        "six",
        "six",
    )
    mock_db.session.commit.assert_not_called()


def test_lead_confirmation_uses_only_saved_value_or_standalone_default():
    combined = combined_practice(1, 14, 18, "six")
    standalone = combined_practice(2, 15, 19, None)

    assert get_lead_confirmation_emoji_for_practice(combined) == ["six"]
    assert get_lead_confirmation_emoji_for_practice(standalone) == [
        "white_check_mark"
    ]


def test_initial_post_assigns_before_slack_and_seeds_sessions_plus_shared_plan(
    app_context,
):
    from app.slack.practices.announcements import post_combined_lift_announcement

    plan = [{"emoji": "evergreen_tree", "label": "Endurance"}]
    practices = [
        model_practice(1, 14, 18, None, plan=plan),
        model_practice(2, 15, 19, None, plan=plan),
    ]
    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "123.456"}
    events = []

    def assign(items):
        events.append("assign")
        items[0].slack_session_emoji = "six"
        items[1].slack_session_emoji = "seven"
        return {"success": True, "emojis": {1: "six", 2: "seven"}}

    def post(**_kwargs):
        events.append("post")
        return {"ts": "123.456"}

    client.chat_postMessage.side_effect = post
    with patch(
        "app.slack.practices.announcements.assign_combined_session_emojis",
        side_effect=assign,
    ), patch(
        "app.slack.practices.announcements._get_announcement_channel",
        return_value="C-STRENGTH",
    ), patch(
        "app.slack.practices.announcements.get_slack_client",
        return_value=client,
    ), patch(
        "app.slack.practices.announcements.convert_practice_to_info",
        side_effect=lambda item: item,
    ), patch(
        "app.slack.practices.announcements._upsert_combined_details_reply",
        return_value={"success": True, "skipped": "no_details"},
    ), patch("app.slack.practices.announcements.db"):
        result = post_combined_lift_announcement(practices)

    assert result["success"] is True
    assert events == ["assign", "post"]
    assert [
        item.kwargs["name"] for item in client.reactions_add.call_args_list
    ] == ["six", "seven", "evergreen_tree"]
    assert all(item.slack_message_ts == "123.456" for item in practices)
    assert all(item.slack_channel_id == "C-STRENGTH" for item in practices)


def test_combined_seed_uses_active_attendance_and_full_shared_plan_name(
    app_context,
):
    from app.slack.practices.announcements import _seed_combined_reactions

    plan = [{
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    }]
    active = model_practice(1, 14, 18, "six", plan=plan)
    cancelled = model_practice(
        2,
        15,
        19,
        "seven",
        status=PracticeStatus.CANCELLED,
        reason="Facility closed",
        plan=plan,
    )
    for practice in (active, cancelled):
        practice.slack_channel_id = "C-STRENGTH"
        practice.slack_message_ts = "123.456"
    client = MagicMock()

    with patch(
        "app.slack.practices.announcements._shared_plan_names",
        return_value=["older_adult::skin-tone-4"],
    ):
        _seed_combined_reactions(client, [active, cancelled])

    assert [
        item.kwargs["name"] for item in client.reactions_add.call_args_list
    ] == ["six", "older_adult::skin-tone-4"]

    client.reset_mock()
    active.status = PracticeStatus.CANCELLED
    with patch(
        "app.slack.practices.announcements._shared_plan_names"
    ) as shared_plan_names:
        _seed_combined_reactions(client, [active, cancelled])
    shared_plan_names.assert_not_called()
    client.reactions_add.assert_not_called()


def test_unposted_assignment_failure_is_explicitly_safe_to_fallback(app_context):
    from app.slack.practices.announcements import post_combined_lift_announcement

    practices = [
        model_practice(1, 14, 18, None),
        model_practice(2, 15, 19, None),
    ]
    with patch(
        "app.slack.practices.announcements.assign_combined_session_emojis",
        return_value={"success": False, "error": "invalid mapping"},
    ), patch(
        "app.slack.practices.announcements.get_slack_client"
    ) as mock_get_client:
        result = post_combined_lift_announcement(practices)

    assert result == {
        "success": False,
        "error": "invalid mapping",
        "safe_to_fallback": True,
    }
    mock_get_client.assert_not_called()


def test_ambiguous_slack_failure_is_never_safe_to_fallback(app_context):
    from slack_sdk.errors import SlackApiError

    from app.slack.practices.announcements import post_combined_lift_announcement

    practices = [
        model_practice(1, 14, 18, "six"),
        model_practice(2, 15, 19, "seven"),
    ]
    client = MagicMock()
    response = MagicMock()
    response.get.side_effect = lambda key, default=None: (
        "network_error" if key == "error" else default
    )
    client.chat_postMessage.side_effect = SlackApiError("boom", response)
    with patch(
        "app.slack.practices.announcements.assign_combined_session_emojis",
        return_value={"success": True, "emojis": {1: "six", 2: "seven"}},
    ), patch(
        "app.slack.practices.announcements._get_announcement_channel",
        return_value="C-STRENGTH",
    ), patch(
        "app.slack.practices.announcements.get_slack_client",
        return_value=client,
    ), patch(
        "app.slack.practices.announcements.convert_practice_to_info",
        side_effect=lambda item: item,
    ):
        result = post_combined_lift_announcement(practices)

    assert result["success"] is False
    assert "safe_to_fallback" not in result


def test_combined_missing_timestamp_does_not_mutate_links_or_commit(app_context):
    from app.slack.practices.announcements import post_combined_lift_announcement

    practices = [
        model_practice(1, 14, 18, "six"),
        model_practice(2, 15, 19, "seven"),
    ]
    practices[0].slack_channel_id = "C-OLD-1"
    practices[1].slack_channel_id = "C-OLD-2"
    client = MagicMock()
    client.chat_postMessage.return_value = {}
    with patch(
        "app.slack.practices.announcements.assign_combined_session_emojis",
        return_value={"success": True, "emojis": {1: "six", 2: "seven"}},
    ), patch(
        "app.slack.practices.announcements._get_announcement_channel",
        return_value="C-STRENGTH",
    ), patch(
        "app.slack.practices.announcements.get_slack_client",
        return_value=client,
    ), patch(
        "app.slack.practices.announcements.convert_practice_to_info",
        side_effect=lambda item: item,
    ), patch("app.slack.practices.announcements.db") as mock_db:
        result = post_combined_lift_announcement(practices)

    assert result == {
        "success": False,
        "error": "Slack did not return a message timestamp",
    }
    assert [item.slack_channel_id for item in practices] == [
        "C-OLD-1",
        "C-OLD-2",
    ]
    assert [item.slack_message_ts for item in practices] == [None, None]
    mock_db.session.commit.assert_not_called()


@pytest.mark.parametrize("cleanup_error", [None, "cant_delete_message"])
def test_combined_link_commit_failure_restores_links_and_compensates(
    app_context, cleanup_error
):
    from slack_sdk.errors import SlackApiError

    from app.slack.practices.announcements import post_combined_lift_announcement

    practices = [
        model_practice(1, 14, 18, "six"),
        model_practice(2, 15, 19, "seven"),
    ]
    practices[0].slack_channel_id = "C-OLD-1"
    practices[1].slack_channel_id = "C-OLD-2"
    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "123.456"}
    if cleanup_error:
        client.chat_delete.side_effect = SlackApiError(
            "cleanup failed", {"error": cleanup_error}
        )
    with patch(
        "app.slack.practices.announcements.assign_combined_session_emojis",
        return_value={"success": True, "emojis": {1: "six", 2: "seven"}},
    ), patch(
        "app.slack.practices.announcements._get_announcement_channel",
        return_value="C-STRENGTH",
    ), patch(
        "app.slack.practices.announcements.get_slack_client",
        return_value=client,
    ), patch(
        "app.slack.practices.announcements.convert_practice_to_info",
        side_effect=lambda item: item,
    ), patch(
        "app.slack.practices.announcements._upsert_combined_details_reply"
    ) as details, patch(
        "app.slack.practices.announcements._seed_combined_reactions"
    ) as reactions, patch(
        "app.slack.practices.announcements.db"
    ) as mock_db:
        mock_db.session.commit.side_effect = RuntimeError(
            "database commit failed"
        )
        result = post_combined_lift_announcement(practices)

    assert result["success"] is False
    assert "database commit failed" in result["error"]
    assert result["cleanup"]["success"] is (cleanup_error is None)
    assert "safe_to_fallback" not in result
    if cleanup_error:
        assert result["ambiguous_orphan"] == {
            "channel_id": "C-STRENGTH",
            "message_ts": "123.456",
        }
    else:
        assert "ambiguous_orphan" not in result
    assert [item.slack_channel_id for item in practices] == [
        "C-OLD-1",
        "C-OLD-2",
    ]
    assert [item.slack_message_ts for item in practices] == [None, None]
    assert mock_db.session.rollback.call_count == (
        2 if cleanup_error else 1
    )
    client.chat_delete.assert_called_once_with(
        channel="C-STRENGTH", ts="123.456"
    )
    details.assert_not_called()
    reactions.assert_not_called()


def test_standalone_post_clears_abandoned_combined_value(app_context):
    from app.slack.practices.announcements import post_practice_announcement

    practice = model_practice(1, 14, 18, "six")
    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "standalone.1"}
    with patch(
        "app.slack.practices.announcements.get_slack_client",
        return_value=client,
    ), patch(
        "app.slack.practices.announcements._get_announcement_channel",
        return_value="C-STRENGTH",
    ), patch(
        "app.slack.practices.announcements._conditions_for_render",
        return_value=SimpleNamespace(),
    ), patch(
        "app.practices.service.convert_practice_to_info",
        return_value=practice,
    ), patch(
        "app.slack.practices.announcements.build_practice_announcement_blocks",
        return_value=[],
    ), patch(
        "app.slack.practices.announcements.build_practice_fallback_text",
        return_value="fallback",
    ), patch(
        "app.slack.practices.announcements._upsert_details_reply",
        return_value={"success": True},
    ), patch(
        "app.slack.practices.announcements._seed_plan_reactions"
    ), patch(
        "app.slack.practices.coach_review.create_practice_log_thread"
    ), patch("app.slack.practices.announcements.db") as mock_db:
        result = post_practice_announcement(practice)

    assert result["success"] is True
    assert practice.slack_session_emoji is None
    assert practice.slack_message_ts == "standalone.1"
    mock_db.session.commit.assert_called_once_with()


def test_scoped_siblings_filter_by_channel_and_timestamp(app_context):
    from app.slack.practices.announcements import get_announcement_siblings

    practice = model_practice(1, 14, 18, "six")
    practice.slack_channel_id = "C-ONE"
    practice.slack_message_ts = "same.ts"
    query = MagicMock()
    query.filter_by.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = [practice]

    with patch("app.slack.practices.announcements.Practice.query", query):
        result = get_announcement_siblings(practice, exclude_practice_id=99)

    assert result == [practice]
    query.filter_by.assert_called_once_with(
        slack_channel_id="C-ONE", slack_message_ts="same.ts"
    )
    query.filter.assert_called_once()


def test_saved_value_keeps_one_survivor_on_combined_dispatch_path(app_context):
    from app.slack.practices.announcements import is_combined_lift_practice

    practice = model_practice(2, 15, 19, "seven")
    practice.slack_channel_id = "C-STRENGTH"
    practice.slack_message_ts = "root.1"

    with patch(
        "app.slack.practices.announcements.get_announcement_siblings"
    ) as mock_siblings:
        assert is_combined_lift_practice(practice) is True

    mock_siblings.assert_not_called()


def test_duplicate_saved_values_stop_existing_root_before_slack_update(app_context):
    from app.slack.practices.announcements import update_combined_lift_post

    practices = [
        model_practice(1, 14, 18, "six"),
        model_practice(2, 15, 19, "six"),
    ]
    for practice in practices:
        practice.slack_channel_id = "C-STRENGTH"
        practice.slack_message_ts = "root.1"
    with patch(
        "app.slack.practices.announcements.get_announcement_siblings",
        return_value=practices,
    ), patch("app.models.db"), patch(
        "app.slack.practices.announcements.get_slack_client"
    ) as mock_get_client:
        result = update_combined_lift_post(practices[0])

    assert result["success"] is False
    assert "Duplicate combined-session emoji" in result["error"]
    assert [item.slack_session_emoji for item in practices] == ["six", "six"]
    mock_get_client.assert_not_called()


def test_plan_divergence_removes_only_obsolete_bot_seed(app_context):
    from app.slack.practices.announcements import update_combined_lift_post

    practices = [
        model_practice(
            1,
            14,
            18,
            "six",
            plan=[{"emoji": "evergreen_tree", "label": "Endurance"}],
        ),
        model_practice(
            2,
            15,
            19,
            "seven",
            plan=[{"emoji": "athletic_shoe", "label": "Run"}],
        ),
    ]
    for practice in practices:
        practice.slack_channel_id = "C-STRENGTH"
        practice.slack_message_ts = "root.1"
    client = MagicMock()
    with patch(
        "app.slack.practices.announcements.get_announcement_siblings",
        return_value=practices,
    ), patch(
        "app.slack.practices.announcements.assign_combined_session_emojis",
        return_value={"success": True, "emojis": {1: "six", 2: "seven"}},
    ), patch(
        "app.slack.practices.announcements.get_slack_client",
        return_value=client,
    ), patch(
        "app.slack.practices.announcements.convert_practice_to_info",
        side_effect=lambda item: item,
    ), patch(
        "app.slack.practices.announcements._upsert_combined_details_reply",
        return_value={"success": True},
    ):
        result = update_combined_lift_post(
            practices[0],
            previous_plan_reactions=[
                {"emoji": "evergreen_tree", "label": "Endurance"}
            ],
        )

    assert result["success"] is True
    removed = [item.kwargs["name"] for item in client.reactions_remove.call_args_list]
    assert removed == ["athletic_shoe", "evergreen_tree"]
    assert [
        item.kwargs["name"]
        for item in client.reactions_add.call_args_list
    ] == ["six", "seven"]


def test_exclusion_assigns_every_legacy_sibling_before_one_survivor_rebuild(
    app_context,
):
    from app.slack.practices.announcements import update_combined_lift_post

    removed = model_practice(1, 14, 18, None)
    survivor = model_practice(2, 15, 19, None)
    practices = [removed, survivor]
    for practice in practices:
        practice.slack_channel_id = "C-STRENGTH"
        practice.slack_message_ts = "root.1"
    client = MagicMock()
    events = []

    def assign(items):
        events.append(("assign", [item.id for item in items]))
        items[0].slack_session_emoji = "six"
        items[1].slack_session_emoji = "seven"
        return {"success": True, "emojis": {1: "six", 2: "seven"}}

    def sync_details(_client, items):
        events.append(("details", [item.id for item in items]))
        return {"success": True, "skipped": "no_details"}

    def update(**_kwargs):
        events.append(("root", None))

    client.chat_update.side_effect = update
    with patch(
        "app.slack.practices.announcements.get_announcement_siblings",
        return_value=practices,
    ), patch(
        "app.slack.practices.announcements.assign_combined_session_emojis",
        side_effect=assign,
    ), patch(
        "app.slack.practices.announcements.get_slack_client",
        return_value=client,
    ), patch(
        "app.slack.practices.announcements.convert_practice_to_info",
        side_effect=lambda item: item,
    ), patch(
        "app.slack.practices.announcements._upsert_combined_details_reply",
        side_effect=sync_details,
    ):
        result = update_combined_lift_post(
            removed, exclude_practice_id=removed.id
        )

    assert result["success"] is True
    assert events == [
        ("assign", [1, 2]),
        ("details", [2]),
        ("root", None),
    ]
    root_text = rendered_text(client.chat_update.call_args.kwargs["blocks"])
    assert "Choose a session:" not in root_text
    assert "*7:15 PM*" in root_text
    assert "Bop :seven: for 7:15 PM" in root_text
    client.reactions_remove.assert_called_once_with(
        channel="C-STRENGTH", timestamp="root.1", name="six"
    )


def test_exclusion_details_failure_leaves_root_and_removed_seed_untouched(
    app_context,
):
    from app.slack.practices.announcements import update_combined_lift_post

    removed = model_practice(1, 14, 18, "six")
    survivor = model_practice(2, 15, 19, "seven")
    practices = [removed, survivor]
    for practice in practices:
        practice.slack_channel_id = "C-STRENGTH"
        practice.slack_message_ts = "root.1"
    client = MagicMock()
    with patch(
        "app.slack.practices.announcements.get_announcement_siblings",
        return_value=practices,
    ), patch(
        "app.slack.practices.announcements.assign_combined_session_emojis",
        return_value={"success": True, "emojis": {1: "six", 2: "seven"}},
    ), patch(
        "app.slack.practices.announcements.get_slack_client",
        return_value=client,
    ), patch(
        "app.slack.practices.announcements.convert_practice_to_info",
        side_effect=lambda item: item,
    ), patch(
        "app.slack.practices.announcements._upsert_combined_details_reply",
        return_value={"success": False, "error": "details failed"},
    ):
        result = update_combined_lift_post(
            removed, exclude_practice_id=removed.id
        )

    assert result["success"] is False
    assert result["error"] == "Combined Details did not sync; root was not changed"
    client.chat_update.assert_not_called()
    client.reactions_remove.assert_not_called()


def linked_practice(*args, details=None, **kwargs):
    practice = model_practice(*args, **kwargs)
    practice.slack_channel_id = 'C-STRENGTH'
    practice.slack_message_ts = 'root.1'
    practice.slack_details_ts = details
    return practice


def call_remove(practice, client, *, survivors=()):
    from app.slack.practices.announcements import (
        remove_practice_from_announcement,
    )

    with patch(
        'app.slack.practices.announcements.get_announcement_siblings',
        return_value=list(survivors),
    ), patch(
        'app.slack.practices.announcements.get_slack_client',
        return_value=client,
    ), patch('app.slack.practices.announcements.db') as mock_db:
        result = remove_practice_from_announcement(practice)
    return result, mock_db


def test_cancelled_standalone_blocks_and_fallback_are_complete_and_guarded():
    from app.slack.blocks.cancellations import (
        build_cancelled_practice_fallback_text,
    )

    practice = model_practice(
        1, 14, 18, None, status=PracticeStatus.CANCELLED,
        reason='Facility closed ' + ('x' * 5_000),
    )
    blocks = build_practice_cancelled_notice(practice)
    fallback = build_cancelled_practice_fallback_text(practice)

    assert ':x: *CANCELLED* :x:' in rendered_text(blocks)
    assert '~Tuesday, July 14 at 6:15 PM at Balance Fitness~' in rendered_text(
        blocks
    )
    assert max(
        len(block['text']['text']) for block in blocks
        if block['type'] in {'header', 'section'}
    ) <= 3_000
    assert len(fallback) <= 4_000
    assert all(value.lower() in fallback.lower() for value in (
        'Tuesday, July 14', '6:15 PM', 'Balance Fitness', 'cancelled',
        'Facility closed', 'adjust your plans',
    ))


def test_combined_cancellation_rebuild_keeps_active_sibling_in_root(
    app_context,
):
    from app.slack.practices.announcements import update_combined_lift_post

    cancelled = linked_practice(
        1, 14, 18, 'six', status=PracticeStatus.CANCELLED,
        reason='Facility closed',
    )
    survivor = linked_practice(2, 15, 19, 'seven')
    practices = [cancelled, survivor]
    client = MagicMock()
    with patch(
        'app.slack.practices.announcements.get_announcement_siblings',
        return_value=practices,
    ), patch(
        'app.slack.practices.announcements.assign_combined_session_emojis',
        return_value={'success': True, 'emojis': {1: 'six', 2: 'seven'}},
    ), patch(
        'app.slack.practices.announcements.get_slack_client',
        return_value=client,
    ), patch(
        'app.slack.practices.announcements.convert_practice_to_info',
        side_effect=lambda item: item,
    ), patch(
        'app.slack.practices.announcements._upsert_combined_details_reply',
        return_value={'success': True},
    ):
        result = update_combined_lift_post(cancelled)

    assert result['success'] is True
    text = rendered_text(client.chat_update.call_args.kwargs['blocks'])
    assert 'CANCELLED' in text and 'Facility closed' in text
    assert ':six:' not in text
    assert 'Bop :seven: for Wed at 7:15 PM' in text
    assert [
        item.kwargs['name']
        for item in client.reactions_remove.call_args_list
    ] == ['six']
    assert [
        item.kwargs['name']
        for item in client.reactions_add.call_args_list
    ] == ['seven']


def test_all_cancelled_rebuild_removes_attendance_and_shared_plan_seeds(
    app_context,
):
    from app.slack.practices.announcements import update_combined_lift_post

    plan = [{'emoji': 'evergreen_tree', 'label': 'Endurance'}]
    practices = [
        linked_practice(
            1, 14, 18, 'six', status=PracticeStatus.CANCELLED,
            reason='Facility closed', plan=plan,
        ),
        linked_practice(
            2, 15, 19, 'seven', status=PracticeStatus.CANCELLED,
            reason='Facility closed', plan=plan,
        ),
    ]
    client = MagicMock()
    with patch(
        'app.slack.practices.announcements.get_announcement_siblings',
        return_value=practices,
    ), patch(
        'app.slack.practices.announcements.assign_combined_session_emojis',
        return_value={'success': True, 'emojis': {1: 'six', 2: 'seven'}},
    ), patch(
        'app.slack.practices.announcements.get_slack_client',
        return_value=client,
    ), patch(
        'app.slack.practices.announcements.convert_practice_to_info',
        side_effect=lambda item: item,
    ), patch(
        'app.slack.practices.announcements._upsert_combined_details_reply',
        return_value={'success': True},
    ):
        result = update_combined_lift_post(practices[0])

    assert result['success'] is True
    removed = [
        item.kwargs['name']
        for item in client.reactions_remove.call_args_list
    ]
    assert len(removed) == 3
    assert set(removed) == {'six', 'seven', 'evergreen_tree'}
    client.reactions_add.assert_not_called()


def test_mixed_cancelled_rebuild_keeps_visible_shared_plan_seed(app_context):
    from app.slack.practices.announcements import update_combined_lift_post

    plan = [{'emoji': 'evergreen_tree', 'label': 'Endurance'}]
    practices = [
        linked_practice(1, 14, 18, 'six', plan=plan),
        linked_practice(
            2, 15, 19, 'seven', status=PracticeStatus.CANCELLED,
            reason='Facility closed', plan=plan,
        ),
    ]
    client = MagicMock()
    with patch(
        'app.slack.practices.announcements.get_announcement_siblings',
        return_value=practices,
    ), patch(
        'app.slack.practices.announcements.assign_combined_session_emojis',
        return_value={'success': True, 'emojis': {1: 'six', 2: 'seven'}},
    ), patch(
        'app.slack.practices.announcements.get_slack_client',
        return_value=client,
    ), patch(
        'app.slack.practices.announcements.convert_practice_to_info',
        side_effect=lambda item: item,
    ), patch(
        'app.slack.practices.announcements._upsert_combined_details_reply',
        return_value={'success': True},
    ):
        result = update_combined_lift_post(practices[0])

    assert result['success'] is True
    text = rendered_text(client.chat_update.call_args.kwargs['blocks'])
    assert 'Bop :six: for Tue at 6:15 PM' in text
    assert 'In addition to your attendance emoji' in text
    assert ':evergreen_tree:' in text
    assert [
        item.kwargs['name']
        for item in client.reactions_remove.call_args_list
    ] == ['seven']
    assert [
        item.kwargs['name']
        for item in client.reactions_add.call_args_list
    ] == ['evergreen_tree', 'six']


@pytest.mark.parametrize(
    (
        "case",
        "statuses",
        "delete_first",
        "expected_added",
        "expected_removed",
    ),
    [
        (
            "mixed_cancelled",
            [PracticeStatus.SCHEDULED, PracticeStatus.CANCELLED],
            False,
            {"evergreen_tree", "six"},
            {"old_choice", "seven"},
        ),
        (
            "all_cancelled",
            [PracticeStatus.CANCELLED, PracticeStatus.CANCELLED],
            False,
            set(),
            {"old_choice", "evergreen_tree", "six", "seven"},
        ),
        (
            "restoration",
            [PracticeStatus.SCHEDULED, PracticeStatus.CONFIRMED],
            False,
            {"evergreen_tree", "six", "seven"},
            {"old_choice"},
        ),
        (
            "deletion_rebuild",
            [PracticeStatus.SCHEDULED, PracticeStatus.SCHEDULED],
            True,
            {"evergreen_tree", "seven"},
            {"old_choice", "six"},
        ),
    ],
    ids=["mixed_cancelled", "all_cancelled", "restoration", "deletion_rebuild"],
)
def test_malformed_plan_rows_do_not_block_combined_reaction_lifecycle(
    app_context,
    case,
    statuses,
    delete_first,
    expected_added,
    expected_removed,
    caplog,
):
    from app.slack.practices.announcements import (
        remove_practice_from_announcement,
        update_combined_lift_post,
    )

    malformed = {
        "emoji": "white_check_mark",
        "label": "Legacy reserved value",
    }
    current = [
        {"emoji": "evergreen_tree", "label": "Endurance"},
        malformed,
    ]
    previous = [
        {"emoji": "old_choice", "label": "Old choice"},
        malformed,
    ]
    practices = [
        linked_practice(
            1,
            14,
            18,
            "six",
            status=statuses[0],
            reason=(
                "Facility closed"
                if statuses[0] == PracticeStatus.CANCELLED
                else None
            ),
            plan=current,
        ),
        linked_practice(
            2,
            15,
            19,
            "seven",
            status=statuses[1],
            reason=(
                "Facility closed"
                if statuses[1] == PracticeStatus.CANCELLED
                else None
            ),
            plan=current,
        ),
    ]
    practices[1].plan_reactions = [
        current[0],
        {"emoji": "six", "label": "Different malformed legacy value"},
    ]
    if delete_first:
        practices[0].plan_reactions = list(previous)
        siblings = MagicMock(side_effect=[[practices[1]], practices])
    else:
        siblings = MagicMock(return_value=practices)

    client = MagicMock()
    with patch(
        'app.slack.practices.announcements.get_announcement_siblings',
        new=siblings,
    ), patch(
        'app.slack.practices.announcements.assign_combined_session_emojis',
        return_value={'success': True, 'emojis': {1: 'six', 2: 'seven'}},
    ), patch(
        'app.slack.practices.announcements.get_slack_client',
        return_value=client,
    ), patch(
        'app.practices.service.convert_practice_to_info',
        side_effect=lambda item: item,
    ), patch(
        'app.slack.practices.announcements._upsert_combined_details_reply',
        return_value={'success': True},
    ):
        result = (
            remove_practice_from_announcement(practices[0])
            if delete_first
            else update_combined_lift_post(
                practices[0], previous_plan_reactions=previous
            )
        )

    assert result['success'] is True, case
    assert {
        item.kwargs['name'] for item in client.reactions_add.call_args_list
    } == expected_added
    assert {
        item.kwargs['name'] for item in client.reactions_remove.call_args_list
    } == expected_removed
    rendered = client.chat_update.call_args.kwargs
    if any(status != PracticeStatus.CANCELLED for status in statuses):
        assert "evergreen tree for Endurance" in rendered["text"]
    assert "Legacy reserved value" not in str(rendered)
    assert "reserved for attendance" in caplog.text


@pytest.mark.parametrize(
    'restored_status',
    [PracticeStatus.SCHEDULED, PracticeStatus.CONFIRMED],
)
def test_cancelled_session_restoration_readds_active_attendance_seed(
    app_context,
    restored_status,
):
    from app.slack.practices.announcements import update_combined_lift_post

    restored = linked_practice(
        1, 14, 18, 'six', status=PracticeStatus.CANCELLED,
        reason='Facility closed',
    )
    survivor = linked_practice(2, 15, 19, 'seven')
    practices = [restored, survivor]
    client = MagicMock()
    with patch(
        'app.slack.practices.announcements.get_announcement_siblings',
        return_value=practices,
    ), patch(
        'app.slack.practices.announcements.assign_combined_session_emojis',
        return_value={'success': True, 'emojis': {1: 'six', 2: 'seven'}},
    ), patch(
        'app.slack.practices.announcements.get_slack_client',
        return_value=client,
    ), patch(
        'app.slack.practices.announcements.convert_practice_to_info',
        side_effect=lambda item: item,
    ), patch(
        'app.slack.practices.announcements._upsert_combined_details_reply',
        return_value={'success': True},
    ):
        cancelled_result = update_combined_lift_post(restored)
        cancelled_removed = [
            item.kwargs['name']
            for item in client.reactions_remove.call_args_list
        ]
        cancelled_added = [
            item.kwargs['name']
            for item in client.reactions_add.call_args_list
        ]

        restored.status = restored_status
        client.reset_mock()
        restored_result = update_combined_lift_post(restored)

    assert cancelled_result['success'] is True
    assert cancelled_removed == ['six']
    assert cancelled_added == ['seven']
    assert restored_result['success'] is True
    restored_text = rendered_text(client.chat_update.call_args.kwargs['blocks'])
    assert 'Bop :six: for Tue at 6:15 PM or :seven: for Wed at 7:15 PM' in (
        restored_text
    )
    assert [
        item.kwargs['name']
        for item in client.reactions_add.call_args_list
    ] == ['six', 'seven']
    client.reactions_remove.assert_not_called()


def test_delete_survivor_uses_direct_exclusion_api(app_context):
    from app.slack.practices.announcements import (
        remove_practice_from_announcement,
    )

    removed = linked_practice(
        1, 14, 18, 'six',
        plan=[{'emoji': 'evergreen_tree', 'label': 'Endurance'}],
    )
    survivor = linked_practice(2, 15, 19, 'seven')
    with patch(
        'app.slack.practices.announcements.get_announcement_siblings',
        return_value=[survivor],
    ) as mock_siblings, patch(
        'app.slack.practices.announcements.update_combined_lift_post',
        return_value={'success': True},
    ) as mock_update:
        assert remove_practice_from_announcement(removed) == {'success': True}

    mock_siblings.assert_called_once_with(
        removed, exclude_practice_id=removed.id
    )
    mock_update.assert_called_once_with(
        removed, exclude_practice_id=removed.id,
        previous_plan_reactions=removed.plan_reactions,
    )


@pytest.mark.parametrize(
    ('mode', 'details', 'expected', 'calls', 'saved', 'commits'),
    [
        ('success', 'details.1', {'success': True},
         ['details.1', 'root.1'], (None, None, None), 2),
        ('details_error', 'details.1',
         {'success': False, 'error': 'details failed'},
         ['details.1'], ('details.1', 'root.1', 'C-STRENGTH'), 0),
        ('root_error', None, {'success': False, 'error': 'root failed'},
         ['root.1'], (None, 'root.1', 'C-STRENGTH'), 0),
        ('missing', None, {'success': True},
         ['root.1'], (None, None, None), 1),
    ],
)
def test_final_session_delete_order_idempotency_and_retry_state(
    app_context, mode, details, expected, calls, saved, commits,
):
    from slack_sdk.errors import SlackApiError

    practice = linked_practice(1, 14, 18, 'six', details=details)
    client = MagicMock()
    if mode == 'details_error':
        client.chat_delete.side_effect = RuntimeError('details failed')
    elif mode == 'root_error':
        client.chat_delete.side_effect = RuntimeError('root failed')
    elif mode == 'missing':
        client.chat_delete.side_effect = SlackApiError(
            'missing', {'error': 'message_not_found'}
        )

    result, mock_db = call_remove(practice, client)

    assert result == expected
    assert [call.kwargs['ts'] for call in client.chat_delete.call_args_list] == calls
    assert (
        practice.slack_details_ts,
        practice.slack_message_ts,
        practice.slack_channel_id,
    ) == saved
    assert mock_db.session.commit.call_count == commits


def test_combined_cancellation_thread_notice_is_complete_and_guarded(
    app_context,
):
    from app.slack.practices.cancellations import (
        post_combined_cancellation_thread_notice,
    )

    practice = linked_practice(
        1, 14, 18, 'six', status=PracticeStatus.CANCELLED,
        reason='Facility closed ' + ('x' * 5_000),
    )
    client = MagicMock()
    with patch(
        'app.slack.practices.cancellations.get_slack_client',
        return_value=client,
    ):
        assert post_combined_cancellation_thread_notice(practice) == {
            'success': True
        }

    kwargs = client.chat_postMessage.call_args.kwargs
    assert (kwargs['channel'], kwargs['thread_ts'], kwargs['reply_broadcast']) == (
        'C-STRENGTH', 'root.1', False,
    )
    assert len(kwargs['text']) <= 4_000
    assert all(value in kwargs['text'] for value in (
        'Tuesday at 6:15 PM', 'Facility closed', 'unchanged',
    ))


@pytest.mark.parametrize('operation', ['update', 'post'])
def test_standalone_cancellation_writes_complete_builder_fallback(
    app_context, operation,
):
    from app.slack.practices import cancellations

    practice = linked_practice(
        1, 14, 18, None, status=PracticeStatus.CANCELLED,
        reason='Facility closed',
    )
    if operation == 'post':
        practice.slack_message_ts = None
        practice.slack_channel_id = None
    client = MagicMock()
    client.chat_postMessage.return_value = {'ts': 'notice.1'}
    blocks = [{'type': 'section', 'text': {'type': 'mrkdwn', 'text': 'safe'}}]
    with patch(
        'app.slack.practices.cancellations.get_slack_client',
        return_value=client,
    ), patch(
        'app.slack.practices.cancellations._get_announcement_channel',
        return_value='C-STRENGTH',
    ), patch(
        'app.practices.service.convert_practice_to_info',
        return_value=practice,
    ), patch(
        'app.slack.practices.cancellations.build_practice_cancelled_notice',
        return_value=blocks,
    ), patch(
        'app.slack.practices.cancellations.build_cancelled_practice_fallback_text',
        return_value='complete fallback',
    ):
        if operation == 'update':
            result = cancellations.update_practice_as_cancelled(
                practice, 'Admin'
            )
            kwargs = client.chat_update.call_args.kwargs
            assert client.chat_postMessage.call_args.kwargs['text'].startswith(
                'complete fallback'
            )
        else:
            result = cancellations.post_cancellation_notice(practice)
            kwargs = client.chat_postMessage.call_args.kwargs

    assert result['success'] is True
    assert kwargs['blocks'] == blocks
    assert kwargs['text'] == 'complete fallback'
