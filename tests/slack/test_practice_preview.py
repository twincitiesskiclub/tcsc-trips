"""Contracts for the discard-only Slack Practice Preview."""

from contextlib import nullcontext
from datetime import datetime
from unittest.mock import MagicMock, patch

import app.slack.bolt_app as bolt_module
from app.slack.modals import (
    build_practice_create_modal,
    build_practice_preview_modal,
)


PREVIEW_DATE = datetime(2026, 7, 14, 18, 15)
PREVIEW_REACTIONS = [
    {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"},
    {"emoji": "hatching_chick", "label": "new rollerskier"},
    {
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    },
    {"emoji": "athletic_shoe", "label": "runner"},
]


def _blocks_by_id(modal):
    return {
        block["block_id"]: block
        for block in modal["blocks"]
        if "block_id" in block
    }


def _expected_create_modal():
    return build_practice_create_modal(
        PREVIEW_DATE,
        "18:15",
        locations=[(1, "Theodore Wirth - Trailhead")],
        all_activities=[(1, "Rollerski"), (2, "Running")],
        all_types=[(1, "Intervals"), (2, "Technique")],
        slot_defaults={
            "location_id": 1,
            "activity_ids": [1],
            "type_ids": [1],
            "coach_ids": [1],
            "lead_ids": [2],
        },
        eligible_coaches=[(1, "Preview Coach", "U_PREVIEW_COACH")],
        eligible_leads=[(2, "Preview Lead", "U_PREVIEW_LEAD")],
        initial_plan_reactions=PREVIEW_REACTIONS,
    )


def _preview_command(**overrides):
    command = {
        "text": "practice-preview",
        "channel_id": "C07G9RTMRT3",
        "user_id": "U_PREVIEWER",
        "user_name": "previewer",
        "trigger_id": "TRIGGER_PREVIEW",
    }
    command.update(overrides)
    return command


def test_preview_wraps_the_production_create_modal():
    expected = _expected_create_modal()
    expected.update({
        "title": {"type": "plain_text", "text": "Practice Preview"},
        "submit": {"type": "plain_text", "text": "Close Preview"},
        "callback_id": "practice_preview",
        "private_metadata": "",
    })

    assert build_practice_preview_modal(PREVIEW_DATE) == expected


def test_preview_prefills_synthetic_options_and_all_reaction_lines():
    blocks = _blocks_by_id(build_practice_preview_modal(PREVIEW_DATE))

    assert blocks["time_block"]["element"]["initial_time"] == "18:15"
    assert blocks["location_block"]["element"]["initial_option"]["value"] == "1"
    assert [
        option["value"]
        for option in blocks["activities_block"]["element"]["initial_options"]
    ] == ["1"]
    assert [
        option["value"]
        for option in blocks["types_block"]["element"]["initial_options"]
    ] == ["1"]
    assert [
        option["value"]
        for option in blocks["coaches_block"]["element"]["initial_options"]
    ] == ["1"]
    assert [
        option["value"]
        for option in blocks["leads_block"]["element"]["initial_options"]
    ] == ["2"]
    assert blocks["plan_reactions_block"]["element"]["initial_value"] == (
        ":evergreen_tree: Endurance instead of intervals\n"
        ":hatching_chick: new rollerskier\n"
        ":older_adult::skin-tone-4: experienced rollerskier\n"
        ":athletic_shoe: runner"
    )


def test_preview_command_rejects_every_other_channel_before_opening_a_view():
    ack = MagicMock()
    client = MagicMock()

    bolt_module._handle_tcsc_command(
        ack=ack,
        command=_preview_command(channel_id="C_OTHER"),
        client=client,
        logger=MagicMock(),
    )

    ack.assert_called_once_with()
    client.views_open.assert_not_called()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C_OTHER",
        user="U_PREVIEWER",
        text=":warning: Practice Preview is available only in the test channel.",
    )


def test_preview_command_reports_a_missing_trigger_without_building_or_opening():
    ack = MagicMock()
    client = MagicMock()
    logger = MagicMock()

    with patch("app.slack.modals.build_practice_preview_modal") as build_preview:
        bolt_module._handle_tcsc_command(
            ack=ack,
            command=_preview_command(trigger_id=""),
            client=client,
            logger=logger,
        )

    ack.assert_called_once_with()
    build_preview.assert_not_called()
    client.views_open.assert_not_called()
    logger.error.assert_called_once()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C07G9RTMRT3",
        user="U_PREVIEWER",
        text=":warning: Could not open Practice Preview. Please try again.",
    )


def test_preview_command_acks_before_opening_the_synthetic_view():
    events = []
    client = MagicMock()
    modal = {"type": "modal", "callback_id": "practice_preview"}

    def record_ack():
        events.append("ack")

    def record_open(**kwargs):
        events.append("views_open")
        assert kwargs == {"trigger_id": "TRIGGER_PREVIEW", "view": modal}

    client.views_open.side_effect = record_open
    with patch(
        "app.utils.now_central_naive", return_value=PREVIEW_DATE
    ), patch(
        "app.slack.modals.build_practice_preview_modal", return_value=modal
    ) as build_preview:
        bolt_module._handle_tcsc_command(
            ack=record_ack,
            command=_preview_command(),
            client=client,
            logger=MagicMock(),
        )

    assert events == ["ack", "views_open"]
    build_preview.assert_called_once_with(PREVIEW_DATE)
    client.chat_postEphemeral.assert_not_called()


def test_preview_command_reports_views_open_failure_ephemerally():
    ack = MagicMock()
    client = MagicMock()
    client.views_open.side_effect = RuntimeError("Slack unavailable")
    logger = MagicMock()

    with patch(
        "app.slack.modals.build_practice_preview_modal",
        return_value={"type": "modal", "callback_id": "practice_preview"},
    ):
        bolt_module._handle_tcsc_command(
            ack=ack,
            command=_preview_command(),
            client=client,
            logger=logger,
        )

    ack.assert_called_once_with()
    logger.exception.assert_called_once()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C07G9RTMRT3",
        user="U_PREVIEWER",
        text=":warning: Could not open Practice Preview. Please try again.",
    )


def test_ordinary_tcsc_command_keeps_the_existing_processor_path(monkeypatch):
    ack = MagicMock()
    client = MagicMock()
    response = {"text": "Existing help", "blocks": [{"type": "divider"}]}
    monkeypatch.setattr(bolt_module, "get_app_context", lambda: nullcontext())

    with patch(
        "app.slack.commands.handle_tcsc_command", return_value=response
    ) as process_command:
        bolt_module._handle_tcsc_command(
            ack=ack,
            command=_preview_command(text="help", channel_id="C_MEMBER"),
            client=client,
            logger=MagicMock(),
        )

    ack.assert_called_once_with()
    process_command.assert_called_once_with("help", "U_PREVIEWER", "previewer")
    client.views_open.assert_not_called()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C_MEMBER",
        user="U_PREVIEWER",
        text="Existing help",
        blocks=[{"type": "divider"}],
    )


def test_preview_command_requires_an_exact_subcommand(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(bolt_module, "get_app_context", lambda: nullcontext())

    with patch(
        "app.slack.commands.handle_tcsc_command",
        return_value={"text": "Unknown command", "blocks": None},
    ) as process_command:
        bolt_module._handle_tcsc_command(
            ack=MagicMock(),
            command=_preview_command(text="practice-preview extra"),
            client=client,
            logger=MagicMock(),
        )

    process_command.assert_called_once_with(
        "practice-preview extra", "U_PREVIEWER", "previewer"
    )
    client.views_open.assert_not_called()


def test_preview_submission_only_acknowledges_and_closes():
    ack = MagicMock()

    with patch.object(
        bolt_module,
        "_parse_practice_authoring_values",
        side_effect=AssertionError("preview must not parse create fields"),
    ), patch.object(
        bolt_module,
        "get_app_context",
        side_effect=AssertionError("preview must not open an app context"),
    ):
        bolt_module._handle_practice_preview_submission(ack)

    ack.assert_called_once_with()
