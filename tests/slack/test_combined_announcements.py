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
from app.slack.client import (
    assign_combined_session_emojis,
    get_lead_confirmation_emoji_for_practice,
)


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
    status=PracticeStatus.SCHEDULED,
    reason=None,
    workout="3 x 8 strength circuit",
    notes="Bring indoor shoes",
    social=None,
    plan=None,
):
    return SimpleNamespace(
        id=practice_id,
        date=datetime(2026, 7, day, hour, 15),
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


def test_combined_uses_saved_session_map_and_shared_plan_grammar():
    plan = [{"emoji": "evergreen_tree", "label": "Endurance instead"}]
    practices = [
        combined_practice(1, 14, 18, "six", plan=plan),
        combined_practice(2, 15, 19, "seven", plan=plan),
    ]

    text = rendered_text(build_combined_lift_blocks(practices))

    assert "Strength practices · July 14–15" in text
    assert "Choose a session:" in text
    assert ":six: *Tuesday" in text
    assert ":seven: *Wednesday" in text
    assert "Your Practice Plan:" in text
    assert ":evergreen_tree: Endurance instead" in text
    assert "Optional:" not in text
    assert " | " not in text


def test_cancelled_slot_and_fallback_keep_every_session_distinct():
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

    text = rendered_text(build_combined_lift_blocks(practices))
    fallback = build_combined_fallback_text(practices)

    assert "CANCELLED" in text and "Facility closed" in text
    for value in (
        "Tuesday",
        "6:15 PM",
        "Balance Fitness",
        ":six:",
        "Wednesday",
        "7:15 PM",
        "CANCELLED",
        "Facility closed",
        ":seven:",
    ):
        assert value in fallback


def test_one_survivor_keeps_combined_grammar_and_saved_reaction():
    text = rendered_text(
        build_combined_lift_blocks([combined_practice(2, 15, 19, "seven")])
    )

    assert "Choose a session:" in text
    assert ":seven: *Wednesday" in text
    assert "✅" not in text


def test_post_creation_divergence_keeps_each_sessions_content_visible():
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

    text = rendered_text(build_combined_lift_blocks(practices))

    for value in (
        "Session A circuit",
        "Session B circuit",
        "Shoes A",
        "Shoes B",
        "Cafe A",
        "Cafe B",
        ":six:",
        ":seven:",
    ):
        assert value in text


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

    assert "Your Practice Plan:" not in text
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
    client.reactions_add.assert_not_called()


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
    assert "Choose a session:" in root_text
    assert ":seven: *Wednesday" in root_text
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
