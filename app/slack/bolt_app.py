"""Slack Bolt app for handling all Slack interactions.

This module provides a Bolt-based Slack app that handles:
- Slash commands (/tcsc)
- Block actions (button clicks)
- View submissions (modal forms)
- Events (app_home_opened, reaction_added)

Supports two modes:
1. Socket Mode (local dev): Uses WebSocket connection, no public URL needed
   - Requires SLACK_APP_TOKEN (xapp-...) with connections:write scope
2. HTTP Mode (production): Uses SlackRequestHandler with Flask routes
   - Requires SLACK_SIGNING_SECRET for request verification
"""

import copy
import os
import logging
import threading
from collections.abc import Mapping
from datetime import datetime
from types import SimpleNamespace
from typing import Optional

logger = logging.getLogger(__name__)

# Initialize Bolt app with signing secret for request verification
_bot_token = os.environ.get("SLACK_BOT_TOKEN")
_app_token = os.environ.get("SLACK_APP_TOKEN")  # For Socket Mode (xapp-...)
_signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
_FULL_EDIT_UNSYNCED_ERROR = (
    "Practice changes were saved, but the Slack announcement was not updated. "
    "Retry the edit or refresh the announcement."
)
_PRACTICE_PREVIEW_CHANNEL_ID = "C07G9RTMRT3"
_PRACTICE_PREVIEW_CHANNEL_ONLY_TEXT = (
    ":warning: Practice Preview is available only in the test channel."
)
_PRACTICE_PREVIEW_RETRY_TEXT = (
    ":warning: Could not open Practice Preview. Please try again."
)


class _AuthoritativePracticeReactionLoadError(Exception):
    """Server-owned practice reaction data could not be loaded safely."""

# Module-level variables
bolt_app = None
handler = None  # HTTP handler (for production)
socket_mode_handler = None  # Socket Mode handler (for local dev)
_socket_mode_started = False
_flask_app = None  # Reference for background HTTP/lazy and Socket Mode workers

_PRACTICE_REACTION_ACTION_ID_ORDER = (
    "activity_ids",
    "type_ids",
    "practice_reaction_edit",
    "practice_reaction_remove",
    "practice_reaction_undo",
    "practice_reaction_add",
    "practice_reaction_catalog_select",
    "practice_reaction_restore",
)


def bind_flask_app(flask_app) -> None:
    """Bind the Flask application used by Bolt background workers."""
    global _flask_app

    _flask_app = flask_app


def _ack_practice_reaction_action(ack) -> None:
    """Primary Bolt action listener: send the transport acknowledgment only."""
    ack()


def _run_practice_reaction_action_lazy(body, action, client, logger) -> None:
    """Shared lazy worker for all structured practice-reaction actions."""
    _handle_practice_reaction_action(
        lambda: None,
        body,
        action,
        client,
        logger,
    )


def _register_practice_reaction_action_listeners(app, *, worker=None) -> None:
    """Register eight ack-only actions with one shared Bolt lazy worker."""
    lazy_worker = worker or _run_practice_reaction_action_lazy
    for action_id in _PRACTICE_REACTION_ACTION_ID_ORDER:
        app.action(action_id)(
            ack=_ack_practice_reaction_action,
            lazy=[lazy_worker],
        )

# Only initialize Bolt if we have the required token
# This allows the app to start without Slack credentials (e.g., for migrations)
if _bot_token:
    logger.info(
        "Slack Bolt enabled: bot token configured=%s, signing secret configured=%s",
        bool(_bot_token),
        bool(_signing_secret),
    )

    from slack_bolt import App
    from slack_bolt.adapter.flask import SlackRequestHandler

    bolt_app = App(
        token=_bot_token,
        signing_secret=_signing_secret,
        # Process events synchronously before returning response
        # This ensures we're still in Flask's request context
        process_before_response=True
    )
    handler = SlackRequestHandler(bolt_app)
    logger.info("Slack Bolt app initialized (HTTP mode)")

    # If we have an app token, also set up Socket Mode
    if _app_token:
        from slack_bolt.adapter.socket_mode import SocketModeHandler
        socket_mode_handler = SocketModeHandler(bolt_app, _app_token)
        logger.info("Socket Mode handler ready (will start when start_socket_mode() is called)")

    # =========================================================================
    # Global error handler — surfaces unhandled listener exceptions in the logs.
    #
    # With process_before_response=True, any exception raised AFTER ack() (DB
    # writes, refresh_practice_posts, Slack/weather API calls) is swallowed by
    # Bolt and shows the user "there was an error connecting" with no detail.
    # This logs the full traceback plus enough payload context to identify the
    # interaction (callback_id / action_id / user) that failed.
    # =========================================================================
    @bolt_app.error
    def handle_global_error(error, body, logger):
        try:
            payload = body if isinstance(body, dict) else {}
            interaction_type = payload.get("type")
            view = payload.get("view") or {}
            callback_id = view.get("callback_id")
            actions = payload.get("actions") or []
            action_ids = [a.get("action_id") for a in actions if isinstance(a, dict)]
            user = (payload.get("user") or {}).get("id")
            private_metadata = view.get("private_metadata")
        except Exception:
            interaction_type = callback_id = user = private_metadata = None
            action_ids = []

        logger.exception(
            "Unhandled Slack listener error: %s | type=%s callback_id=%s "
            "action_ids=%s user=%s private_metadata=%s",
            error, interaction_type, callback_id, action_ids, user, private_metadata,
        )

    # =========================================================================
    # Slash Commands
    # =========================================================================

    @bolt_app.command("/tcsc")
    def handle_tcsc_command(ack, command, client, logger):
        """Handle /tcsc slash commands, including the test-only preview."""
        _handle_tcsc_command(ack, command, client, logger)

    @bolt_app.command("/dispatch")
    def handle_dispatch_command(ack, command, client, logger):
        """Handle /dispatch slash command - opens submission modal.

        Opens a modal for members to submit content to the Weekly Dispatch
        newsletter (member spotlights, stories, events, announcements).
        """
        ack()

        user_id = command.get("user_id", "")
        trigger_id = command.get("trigger_id")

        if not trigger_id:
            logger.error("No trigger_id in /dispatch command")
            client.chat_postEphemeral(
                channel=command["channel_id"],
                user=user_id,
                text=":warning: Could not open submission form. Please try again."
            )
            return

        from app.newsletter.modals import build_dispatch_submission_modal

        modal = build_dispatch_submission_modal()

        try:
            client.views_open(trigger_id=trigger_id, view=modal)
        except Exception as e:
            logger.error(f"Failed to open dispatch modal: {e}")
            client.chat_postEphemeral(
                channel=command["channel_id"],
                user=user_id,
                text=":warning: Could not open submission form. Please try again."
            )

    # =========================================================================
    # Block Actions (Button Clicks)
    # =========================================================================

    @bolt_app.action("open_dispatch_modal")
    def handle_open_dispatch_modal(ack, body, action, client, logger):
        """Handle 'Submit to Dispatch' button from App Home."""
        ack()

        user_id = body["user"]["id"]
        trigger_id = body.get("trigger_id")

        if not trigger_id:
            logger.error("No trigger_id in open_dispatch_modal action")
            return

        from app.newsletter.modals import build_dispatch_submission_modal

        modal = build_dispatch_submission_modal()

        try:
            client.views_open(trigger_id=trigger_id, view=modal)
        except Exception as e:
            logger.error(f"Failed to open dispatch modal from App Home: {e}")

    @bolt_app.action("rsvp_going")
    @bolt_app.action("rsvp_not_going")
    @bolt_app.action("rsvp_maybe")
    def handle_rsvp_action(ack, body, action, client, logger):
        """Handle RSVP button clicks."""
        ack()

        user_id = body["user"]["id"]
        user_name = body["user"].get("name", "Unknown")
        action_id = action["action_id"]
        practice_id = int(action["value"])

        status_map = {
            "rsvp_going": "going",
            "rsvp_not_going": "not_going",
            "rsvp_maybe": "maybe"
        }
        status = status_map[action_id]

        with get_app_context():
            result = _process_rsvp(practice_id, status, user_id, user_name)

        # Get channel ID safely - may not exist for actions from certain contexts
        channel_id = body.get("channel", {}).get("id")

        if result.get("success"):
            if result.get("toggled_off"):
                # User clicked same status again - they're no longer RSVP'd
                message = ":wave: You're no longer marked as going. Click again if you change your mind!"
            else:
                # User is now RSVP'd
                message = ":white_check_mark: You're going! See you there."

            if channel_id:
                client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text=message
                )
        else:
            if channel_id:
                client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text=f":warning: {result.get('error', 'Could not record RSVP')}"
                )

    @bolt_app.action("home_rsvp")
    def handle_home_rsvp_action(ack, body, action, client, logger):
        """Handle RSVP from App Home tab - opens modal for status selection."""
        ack()

        user_id = body["user"]["id"]
        practice_id = int(action["value"])
        trigger_id = body.get("trigger_id")

        if not trigger_id:
            logger.error("No trigger_id in home_rsvp action")
            return

        with get_app_context():
            from app.practices.models import Practice, PracticeRSVP
            from app.practices.service import convert_practice_to_info
            from app.slack.modals import build_rsvp_modal
            from app.models import User

            practice = Practice.query.get(practice_id)
            if not practice:
                logger.error(f"Practice {practice_id} not found")
                return

            # Get current RSVP status if exists
            current_status = None
            user = User.query.join(User.slack_user).filter_by(slack_uid=user_id).first()
            if user:
                rsvp = PracticeRSVP.query.filter_by(
                    practice_id=practice_id,
                    user_id=user.id
                ).first()
                if rsvp:
                    current_status = rsvp.status

            # Convert to PracticeInfo and build modal
            practice_info = convert_practice_to_info(practice)
            modal = build_rsvp_modal(practice_info, current_status=current_status)

            # Open the modal
            client.views_open(trigger_id=trigger_id, view=modal)

    @bolt_app.action("cancellation_approve")
    @bolt_app.action("cancellation_reject")
    def handle_cancellation_decision(ack, body, action, client, logger):
        """Handle cancellation approval/rejection buttons."""
        return _handle_cancellation_decision_action(
            ack=ack,
            body=body,
            action=action,
            client=client,
        )

    @bolt_app.action("lead_confirm")
    @bolt_app.action("lead_need_sub")
    def handle_lead_confirmation(ack, body, action, client, logger):
        """Handle lead confirmation/substitution request buttons."""
        ack()

        user_id = body["user"]["id"]
        action_id = action["action_id"]
        practice_id = int(action["value"])
        confirmed = (action_id == "lead_confirm")

        with get_app_context():
            result = _process_lead_confirmation(practice_id, confirmed, user_id)

        if confirmed:
            client.chat_postMessage(
                channel=user_id,
                text=":white_check_mark: Thanks for confirming! See you at practice."
            )
        else:
            client.chat_postMessage(
                channel=user_id,
                text=":sos: Substitution request received. The practices team will find a replacement."
            )

    @bolt_app.action("approve_practice")
    def handle_approve_practice(ack, body, action, client, logger):
        """Handle practice approval button click from collab channel."""
        ack()

        user_id = body["user"]["id"]
        practice_id = int(action["value"])

        with get_app_context():
            from app.practices.models import Practice
            from app.slack.practices import update_collab_post
            from app.models import db

            practice = Practice.query.get(practice_id)
            if not practice:
                logger.error(f"Practice {practice_id} not found")
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=user_id,
                    text=":warning: Practice not found."
                )
                return

            # Set approval fields
            practice.coach_approved = True
            practice.approved_by_slack_uid = user_id
            practice.approved_at = datetime.utcnow()
            db.session.commit()

            # Update the collab post to show approved state
            result = update_collab_post(practice)

            if result.get("success"):
                # Post thread reply confirming approval
                from app.slack.client import get_slack_client
                from app.slack.practices import COLLAB_CHANNEL_ID
                slack_client = get_slack_client()
                try:
                    slack_client.chat_postMessage(
                        channel=COLLAB_CHANNEL_ID,
                        thread_ts=practice.slack_collab_message_ts,
                        text=f":white_check_mark: Approved by <@{user_id}>",
                        unfurl_links=False,
                        unfurl_media=False
                    )
                except Exception as e:
                    logger.warning(f"Could not post approval thread: {e}")

                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=user_id,
                    text=":white_check_mark: Practice approved! It will be posted at the scheduled time."
                )
            else:
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=user_id,
                    text=f":warning: Could not update post: {result.get('error')}"
                )

    @bolt_app.action("edit_practice_full")
    def handle_edit_practice_full(ack, body, action, client, logger):
        """Handle edit button click from collab channel - opens full edit modal."""
        ack()

        user_id = body["user"]["id"]
        practice_id = int(action["value"])
        trigger_id = body.get("trigger_id")

        if not trigger_id:
            logger.error("No trigger_id in edit_practice_full action")
            return

        with get_app_context():
            from app.practices.models import Practice, PracticeLocation, PracticeActivity, PracticeType
            from app.practices.plan_reaction_editor import (
                build_plan_reaction_editor_state,
            )
            from app.practices.plan_reaction_queries import (
                load_all_plan_reaction_sources,
                load_selected_plan_reaction_sources,
            )
            from app.practices.plan_reactions import build_plan_reaction_catalog
            from app.practices.service import convert_practice_to_info
            from app.slack.modals import build_practice_edit_full_modal
            from app.models import db, Tag, User

            practice = Practice.query.get(practice_id)
            if not practice:
                logger.error(f"Practice {practice_id} not found")
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=user_id,
                    text=":warning: Practice not found."
                )
                return

            # Get all locations for dropdown (include spot if available)
            locations = []
            for loc in PracticeLocation.query.order_by(PracticeLocation.name).all():
                display_name = f"{loc.name} - {loc.spot}" if loc.spot else loc.name
                locations.append((loc.id, display_name))

            # Get eligible coaches (users with HEAD_COACH or ASSISTANT_COACH tags)
            coach_tags = Tag.query.filter(Tag.name.in_(['HEAD_COACH', 'ASSISTANT_COACH'])).all()
            coach_tag_ids = [t.id for t in coach_tags]
            eligible_coaches = [
                (u.id, f"{u.first_name} {u.last_name}", u.slack_user.slack_uid if u.slack_user else None)
                for u in User.query.filter(User.tags.any(Tag.id.in_(coach_tag_ids))).order_by(User.first_name).all()
                if u.slack_user and u.slack_user.slack_uid
            ]

            # Get eligible leads (users with PRACTICES_LEAD tag)
            lead_tags = Tag.query.filter(Tag.name.in_(['PRACTICES_LEAD'])).all()
            lead_tag_ids = [t.id for t in lead_tags]
            eligible_leads = [
                (u.id, f"{u.first_name} {u.last_name}", u.slack_user.slack_uid if u.slack_user else None)
                for u in User.query.filter(User.tags.any(Tag.id.in_(lead_tag_ids))).order_by(User.first_name).all()
                if u.slack_user and u.slack_user.slack_uid
            ]

            # Get all activities for multi-select
            all_activities = [
                (a.id, a.name)
                for a in PracticeActivity.query.order_by(PracticeActivity.name).all()
            ]

            # Get all types for multi-select
            all_types = [
                (t.id, t.name)
                for t in PracticeType.query.order_by(PracticeType.name).all()
            ]

            selected_sources = load_selected_plan_reaction_sources(
                db.session,
                activity_ids=[item.id for item in practice.activities],
                type_ids=[item.id for item in practice.practice_types],
            )
            all_reaction_sources = load_all_plan_reaction_sources(db.session)
            reaction_editor = build_plan_reaction_editor_state(
                practice_types=selected_sources.practice_types,
                activities=selected_sources.activities,
                saved_snapshot=practice.plan_reactions or [],
            ).state
            reaction_catalog = build_plan_reaction_catalog(
                all_reaction_sources.practice_types,
                all_reaction_sources.activities,
            )

            # Convert to PracticeInfo and build modal
            practice_info = convert_practice_to_info(practice)
            modal = build_practice_edit_full_modal(
                practice_info,
                locations=locations,
                eligible_coaches=eligible_coaches,
                eligible_leads=eligible_leads,
                all_activities=all_activities,
                all_types=all_types,
                reaction_editor=reaction_editor,
                reaction_catalog=reaction_catalog,
            )

            # Open the modal
            client.views_open(trigger_id=trigger_id, view=modal)

    @bolt_app.action("newsletter_approve")
    def handle_newsletter_approve(ack, body, action, client, logger):
        """Handle newsletter approval button click.

        1. Ack immediately
        2. Get newsletter from action value (newsletter_id)
        3. Update newsletter status to APPROVED
        4. Publish to announcement channel
        5. Update living post to remove buttons
        6. Send confirmation
        """
        ack()

        user_id = body["user"]["id"]
        newsletter_id = int(action["value"])

        with get_app_context():
            from app.newsletter.models import Newsletter
            from app.newsletter.interfaces import NewsletterStatus
            from app.models import db

            newsletter = Newsletter.query.get(newsletter_id)
            if not newsletter:
                channel_id = body.get("channel", {}).get("id")
                if channel_id:
                    client.chat_postEphemeral(
                        channel=channel_id,
                        user=user_id,
                        text=":warning: Newsletter not found."
                    )
                return

            if newsletter.status == NewsletterStatus.PUBLISHED.value:
                channel_id = body.get("channel", {}).get("id")
                if channel_id:
                    client.chat_postEphemeral(
                        channel=channel_id,
                        user=user_id,
                        text=":information_source: This newsletter has already been published."
                    )
                return

            # Update status to approved
            newsletter.status = NewsletterStatus.APPROVED.value
            newsletter.published_by_slack_uid = user_id
            db.session.commit()

            # Publish to announcement channel
            try:
                from app.newsletter.slack_actions import publish_to_announcement_channel
                result = publish_to_announcement_channel(newsletter)

                if result.success:
                    newsletter.status = NewsletterStatus.PUBLISHED.value
                    newsletter.published_at = datetime.utcnow()
                    db.session.commit()

                    # Send confirmation
                    channel_id = body.get("channel", {}).get("id")
                    if channel_id:
                        client.chat_postEphemeral(
                            channel=channel_id,
                            user=user_id,
                            text=":white_check_mark: Newsletter published to #announcements-general!"
                        )
                    logger.info(f"Newsletter {newsletter_id} published by {user_id}")
                else:
                    channel_id = body.get("channel", {}).get("id")
                    if channel_id:
                        client.chat_postEphemeral(
                            channel=channel_id,
                            user=user_id,
                            text=f":warning: Failed to publish: {result.error}"
                        )
            except ImportError:
                # slack_actions module not yet implemented
                logger.warning("newsletter.slack_actions not available - skipping publish")
                channel_id = body.get("channel", {}).get("id")
                if channel_id:
                    client.chat_postEphemeral(
                        channel=channel_id,
                        user=user_id,
                        text=":warning: Newsletter approved but publish module not available."
                    )

    @bolt_app.action("newsletter_request_changes")
    def handle_newsletter_request_changes(ack, body, action, client, logger):
        """Handle request changes button - opens feedback modal.

        1. Ack immediately
        2. Open modal for feedback input
        """
        ack()

        user_id = body["user"]["id"]
        newsletter_id = int(action["value"])
        trigger_id = body.get("trigger_id")

        if not trigger_id:
            logger.error("No trigger_id in newsletter_request_changes action")
            return

        # Build and open feedback modal
        modal = {
            "type": "modal",
            "callback_id": "newsletter_feedback",
            "private_metadata": str(newsletter_id),
            "title": {"type": "plain_text", "text": "Request Changes"},
            "submit": {"type": "plain_text", "text": "Submit Feedback"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "feedback_block",
                    "label": {"type": "plain_text", "text": "What changes would you like?"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "feedback_text",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "Describe the changes needed..."}
                    }
                }
            ]
        }

        client.views_open(trigger_id=trigger_id, view=modal)

    @bolt_app.action("section_edit")
    def handle_section_edit_button(ack, body, client, logger):
        """Handle click on section Edit button.

        Opens modal with current section content for editing.
        Button value format: "newsletter_id:section_id:section_type"
        """
        ack()

        try:
            value = body['actions'][0]['value']
            newsletter_id, section_id, section_type = value.split(':')
            newsletter_id = int(newsletter_id)
            # Note: section_id is parsed for validation but not used for the query.
            # Sections are fetched by newsletter_id + section_type, not by ID,
            # since section_type is unique per newsletter.
            _ = int(section_id)  # Validate it's a valid integer
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid section edit button value: {e}")
            return

        trigger_id = body.get('trigger_id')
        if not trigger_id:
            logger.error("No trigger_id for section edit")
            return

        with get_app_context():
            from app.newsletter.section_editor import (
                build_section_edit_modal,
                get_section_for_editing,
            )

            section = get_section_for_editing(newsletter_id, section_type)
            if not section:
                client.chat_postEphemeral(
                    channel=body['channel']['id'],
                    user=body['user']['id'],
                    text=":x: Could not find section to edit"
                )
                return

            modal = build_section_edit_modal(
                section_type=section.section_type,
                current_content=section.content or "",
                newsletter_id=newsletter_id,
                section_id=section.id,
                ai_draft=section.ai_draft
            )

            client.views_open(trigger_id=trigger_id, view=modal)

    @bolt_app.action("create_practice_from_summary")
    def handle_create_practice_from_summary(ack, body, action, client, logger):
        """Handle Add Practice button click from weekly summary placeholder.

        Opens a modal to create a new practice for the specified date.
        Button value format: "2025-01-23|thursday|18:00" (date|day|time)
        or legacy format: "2025-01-23" (date only).
        """
        ack()

        user_id = body["user"]["id"]
        action_value = action["value"]
        trigger_id = body.get("trigger_id")

        if not trigger_id:
            logger.error("No trigger_id in create_practice_from_summary action")
            return

        with get_app_context():
            from app.models import AppConfig, db
            from app.practices.plan_reaction_editor import (
                build_plan_reaction_editor_state,
            )
            from app.practices.plan_reaction_queries import (
                load_all_plan_reaction_sources,
                load_selected_plan_reaction_sources,
            )
            from app.practices.plan_reactions import (
                PlanReactionValidationError,
                build_plan_reaction_catalog,
            )
            from app.slack.modals import build_practice_create_modal

            # Parse button value: "2025-01-23|thursday|18:00" or legacy "2025-01-23"
            parts = action_value.split('|')
            date_str = parts[0]
            slot_day = parts[1] if len(parts) > 1 else None
            slot_time = parts[2] if len(parts) > 2 else None

            # Parse the date
            try:
                practice_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                logger.error(f"Invalid date format: {date_str}")
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=user_id,
                    text=":warning: Invalid date format."
                )
                return

            # Match config entry by (day, time) to find defaults
            expected_days = AppConfig.get('practice_days', [])
            default_time = "18:00"
            slot_defaults = None

            if slot_day and slot_time:
                for day_config in expected_days:
                    if (day_config.get('day', '').lower() == slot_day.lower() and
                            day_config.get('time') == slot_time):
                        default_time = day_config.get('time', '18:00')
                        slot_defaults = day_config.get('defaults')
                        break
            else:
                # Legacy button values (date only) -- match by day name, take first match
                day_name = practice_date.strftime('%A').lower()
                for day_config in expected_days:
                    if day_config.get('day', '').lower() == day_name:
                        default_time = day_config.get('time', '18:00')
                        slot_defaults = day_config.get('defaults')
                        break

            # Load ref data (locations, activities, types) + eligible people
            locations, all_activities, all_types = _load_modal_ref_data()
            eligible_coaches, eligible_leads = _load_eligible_people()

            activity_ids = (slot_defaults or {}).get("activity_ids", [])
            type_ids = (slot_defaults or {}).get("type_ids", [])
            try:
                selected_sources = load_selected_plan_reaction_sources(
                    db.session,
                    activity_ids=activity_ids,
                    type_ids=type_ids,
                )
                all_reaction_sources = load_all_plan_reaction_sources(
                    db.session
                )
                reaction_editor = build_plan_reaction_editor_state(
                    practice_types=selected_sources.practice_types,
                    activities=selected_sources.activities,
                    saved_snapshot=None,
                ).state
                reaction_catalog = build_plan_reaction_catalog(
                    all_reaction_sources.practice_types,
                    all_reaction_sources.activities,
                )
            except PlanReactionValidationError as exc:
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=user_id,
                    text=f":warning: Plan reaction defaults need attention: {exc}",
                )
                return

            # Get channel and message_ts from the source message for updating
            channel_id = body.get("channel", {}).get("id")
            message_ts = body.get("message", {}).get("ts")

            # social_location_id is still applied silently (no UI control for it
            # here). Coaches/leads are now chosen in the modal, pre-filled from
            # the slot defaults (coach_ids / lead_ids).
            silent_defaults = {}
            if slot_defaults and slot_defaults.get('social_location_id'):
                silent_defaults['social_location_id'] = slot_defaults['social_location_id']

            # Build and open the modal
            modal = build_practice_create_modal(
                practice_date, default_time, locations,
                channel_id=channel_id, message_ts=message_ts,
                all_activities=all_activities, all_types=all_types,
                slot_defaults=slot_defaults,
                silent_defaults=silent_defaults if silent_defaults else None,
                eligible_coaches=eligible_coaches, eligible_leads=eligible_leads,
                reaction_editor=reaction_editor,
                reaction_catalog=reaction_catalog,
            )
            client.views_open(trigger_id=trigger_id, view=modal)

    _register_practice_reaction_action_listeners(bolt_app)

    # =========================================================================
    # View Submissions (Modal Forms)
    # =========================================================================

    @bolt_app.view("practice_preview")
    def handle_practice_preview_submission(ack):
        """Close Practice Preview without parsing or persisting its fields."""
        _handle_practice_preview_submission(ack)

    @bolt_app.view("practice_create")
    def handle_practice_create_submission(ack, body, view, client, logger):
        """Delegate Create to the always-importable validated controller."""
        return _handle_practice_create_submission(
            ack,
            body,
            view,
            client,
            logger,
        )

    @bolt_app.view("practice_edit")
    def handle_practice_edit_submission(ack, body, view, client, logger):
        """Handle practice edit modal submission."""
        ack()

        user_id = body["user"]["id"]
        practice_id = int(view.get("private_metadata") or "0")
        values = _safe_get(view, "state", "values", default={})

        with get_app_context():
            from app.practices.models import Practice
            from app.models import db

            practice = Practice.query.get(practice_id)
            if not practice:
                logger.error(f"Practice {practice_id} not found")
                return

            date_value = _safe_get(values, "date_block", "practice_date", "selected_date_time")
            workout = _safe_get(values, "workout_block", "workout_description", "value", default="")

            if date_value:
                practice.date = datetime.fromtimestamp(date_value)
                practice.day_of_week = practice.date.strftime("%A")

            practice.workout_description = workout

            db.session.commit()
            logger.info(f"Practice {practice_id} updated by {user_id}")

            from app.slack.practices import refresh_practice_posts
            refresh_practice_posts(practice, change_type='edit', actor_slack_id=user_id)

    @bolt_app.view("practice_edit_full")
    def handle_practice_edit_full_submission(ack, body, view, client, logger):
        """Handle full practice edit modal submission from collab channel.

        Updates practice details, then updates both #practices and collab posts,
        and adds thread replies noting who updated.
        """
        return _handle_practice_edit_full_submission(
            ack=ack,
            body=body,
            view=view,
            client=client,
            logger=logger,
            post_save_dispatcher=_dispatch_practice_edit_full_post_save,
        )

    @bolt_app.view("practice_rsvp")
    def handle_rsvp_modal_submission(ack, body, view, client, logger):
        """Handle RSVP modal submission with notes."""
        user_id = body["user"]["id"]
        practice_id = int(view.get("private_metadata") or "0")
        values = _safe_get(view, "state", "values", default={})

        status = _safe_get(values, "status_block", "rsvp_status", "selected_option", "value")
        notes = _safe_get(values, "notes_block", "rsvp_notes", "value", default="")

        if not status:
            ack(response_action="errors", errors={"status_block": "Please select a status"})
            return

        ack()
        with get_app_context():
            _process_rsvp_with_notes(practice_id, status, user_id, notes)

            # Refresh App Home to show updated RSVP status
            from app.slack.practices import publish_app_home
            try:
                publish_app_home(user_id)
            except Exception as e:
                logger.warning(f"Could not refresh App Home: {e}")

    @bolt_app.view("workout_entry")
    def handle_workout_submission(ack, body, view, client, logger):
        """Handle workout entry modal submission."""
        ack()

        user_id = body["user"]["id"]
        practice_id = int(view.get("private_metadata") or "0")
        values = _safe_get(view, "state", "values", default={})

        with get_app_context():
            from app.practices.models import Practice
            from app.practices.interfaces import PracticeStatus
            from app.models import db

            practice = Practice.query.get(practice_id)
            if not practice:
                logger.error(f"Practice {practice_id} not found")
                return

            workout = _safe_get(values, "workout_block", "workout_description", "value", default="")
            notes = _safe_get(values, "notes_block", "logistics_notes", "value", default="")

            practice.workout_description = workout
            practice.logistics_notes = notes or None

            practice.status = PracticeStatus.CONFIRMED.value

            db.session.commit()
            logger.info(f"Workout posted for practice {practice_id} by {user_id}")

            from app.slack.practices import refresh_practice_posts
            refresh_practice_posts(practice, change_type='workout', actor_slack_id=user_id)

    @bolt_app.view("lead_substitution")
    def handle_substitution_submission(ack, body, view, client, logger):
        """Handle lead substitution request modal submission."""
        user_id = body["user"]["id"]
        practice_id = int(view.get("private_metadata") or "0")
        values = _safe_get(view, "state", "values", default={})

        reason = _safe_get(values, "reason_block", "substitution_reason", "value", default="")

        if not reason:
            ack(response_action="errors", errors={"reason_block": "Please provide a reason"})
            return

        ack()

        with get_app_context():
            from app.practices.models import Practice
            from app.slack.practices import post_substitution_request

            practice = Practice.query.get(practice_id)
            if practice:
                result = post_substitution_request(practice, user_id, reason)
                if result.get("success"):
                    logger.info(f"Substitution request posted for practice {practice_id}")
                else:
                    logger.error(f"Failed to post substitution request: {result.get('error')}")

    @bolt_app.view("dispatch_submission")
    def handle_dispatch_submission(ack, body, view, client, logger):
        """Handle dispatch modal submission - saves to database.

        Creates a NewsletterSubmission record and sends a confirmation
        ephemeral message to the user.
        """
        ack()

        user_id = body["user"]["id"]
        user_name = body["user"].get("name", "Unknown")
        values = _safe_get(view, "state", "values", default={})

        # Extract form values
        submission_type = _safe_get(
            values, "type_block", "submission_type", "selected_option", "value",
            default="content"
        )
        content = _safe_get(
            values, "content_block", "submission_content", "value",
            default=""
        )

        # Check attribution checkbox
        attribution_options = _safe_get(
            values, "attribution_block", "permission_to_name", "selected_options",
            default=[]
        )
        permission_to_name = any(
            opt.get("value") == "include_name" for opt in attribution_options
        )

        if not content or len(content.strip()) < 10:
            logger.warning(f"Dispatch submission from {user_id} was empty or too short")
            return

        with get_app_context():
            from app.newsletter.models import NewsletterSubmission, Newsletter
            from app.newsletter.interfaces import SubmissionType, SubmissionStatus
            from app.models import db

            # Get display name from Slack profile if available
            display_name = user_name
            try:
                user_info = client.users_info(user=user_id)
                if user_info.get("ok"):
                    profile = user_info.get("user", {}).get("profile", {})
                    display_name = (
                        profile.get("display_name") or
                        profile.get("real_name") or
                        user_name
                    )
            except Exception as e:
                logger.warning(f"Could not fetch user profile for {user_id}: {e}")

            # Get current newsletter if exists (submissions can also be unattached)
            current_newsletter = Newsletter.get_current_week()
            newsletter_id = current_newsletter.id if current_newsletter else None

            # Create submission record
            submission = NewsletterSubmission(
                newsletter_id=newsletter_id,
                slack_user_id=user_id,
                display_name=display_name,
                submission_type=submission_type,
                content=content.strip(),
                permission_to_name=permission_to_name,
                status=SubmissionStatus.PENDING.value
            )
            db.session.add(submission)
            db.session.commit()

            logger.info(
                f"Newsletter submission #{submission.id} created: "
                f"type={submission_type}, user={user_id}, permission_to_name={permission_to_name}"
            )

            # Send confirmation message
            from app.newsletter.modals import build_dispatch_confirmation_blocks

            content_preview = content[:100].strip()
            confirmation_blocks = build_dispatch_confirmation_blocks(
                submission_type=submission_type,
                content_preview=content_preview,
                permission_to_name=permission_to_name
            )

            try:
                client.chat_postMessage(
                    channel=user_id,  # DM to user
                    text="Your submission to the Weekly Dispatch has been received!",
                    blocks=confirmation_blocks
                )
            except Exception as e:
                logger.warning(f"Could not send dispatch confirmation DM to {user_id}: {e}")

    @bolt_app.view("newsletter_feedback")
    def handle_newsletter_feedback_submission(ack, body, view, client, logger):
        """Handle feedback modal submission.

        1. Save feedback to newsletter.admin_feedback
        2. Trigger regeneration with feedback
        3. Confirm to user
        """
        ack()

        user_id = body["user"]["id"]
        newsletter_id = int(view.get("private_metadata") or "0")
        values = _safe_get(view, "state", "values", default={})

        feedback = _safe_get(values, "feedback_block", "feedback_text", "value", default="")

        if not feedback or len(feedback.strip()) < 5:
            logger.warning(f"Newsletter feedback from {user_id} was empty or too short")
            return

        with get_app_context():
            from app.newsletter.models import Newsletter
            from app.models import db

            newsletter = Newsletter.query.get(newsletter_id)
            if not newsletter:
                logger.error(f"Newsletter {newsletter_id} not found for feedback")
                return

            # Save feedback
            newsletter.admin_feedback = feedback.strip()
            db.session.commit()

            logger.info(f"Newsletter {newsletter_id} feedback received from {user_id}")

            # Post feedback to thread (if slack_actions module is available)
            try:
                from app.newsletter.slack_actions import post_feedback_request
                post_feedback_request(newsletter, feedback.strip())
            except ImportError:
                logger.warning("newsletter.slack_actions not available - skipping thread post")

            # Note: Regeneration can be triggered by:
            # 1. The next daily scheduled job which will pick up the feedback
            # 2. Or manually triggering regeneration
            # The service module (when implemented) can handle:
            # generate_newsletter_version(newsletter, context, trigger='feedback')

            # Send DM confirmation to the user who submitted feedback
            try:
                client.chat_postMessage(
                    channel=user_id,
                    text=(
                        ":memo: Your feedback has been recorded for the Weekly Dispatch.\n"
                        f"*Feedback:* {feedback[:200]}{'...' if len(feedback) > 200 else ''}\n\n"
                        "The newsletter will be regenerated with your feedback incorporated."
                    )
                )
            except Exception as e:
                logger.warning(f"Could not send feedback confirmation DM to {user_id}: {e}")

    @bolt_app.view("section_edit_submit")
    def handle_section_edit_submit(ack, body, client, view, logger):
        """Handle section edit modal submission.

        Saves the edited content and updates the living post.
        """
        ack()

        try:
            # Parse metadata
            metadata = view.get('private_metadata', '')
            newsletter_id, section_id, section_type = metadata.split(':')
            newsletter_id = int(newsletter_id)
            section_id = int(section_id)

            # Get submitted content
            values = view.get('state', {}).get('values', {})
            new_content = values.get('content_block', {}).get('section_content', {}).get('value', '')

            editor_uid = body['user']['id']

        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing section edit submission: {e}")
            return

        with get_app_context():
            from app.newsletter.section_editor import save_section_edit

            # Save the edit
            result = save_section_edit(section_id, new_content, editor_uid)

            if not result.get('success'):
                logger.error(f"Failed to save section edit: {result.get('error')}")
                return

            # Notify user
            try:
                client.chat_postMessage(
                    channel=editor_uid,
                    text=f":white_check_mark: *{result['section_type'].replace('_', ' ').title()}* section updated!"
                )
            except Exception as e:
                logger.warning(f"Could not send edit confirmation DM to {editor_uid}: {e}")

            logger.info(f"Section {section_type} edited by {editor_uid}")

    # =========================================================================
    # Events
    # =========================================================================

    @bolt_app.event("app_home_opened")
    def handle_app_home_opened(event, client, logger):
        """Handle app home tab opened event."""
        user_id = event.get("user")

        if not user_id:
            return

        from app.slack.practices import publish_app_home
        try:
            with get_app_context():
                publish_app_home(user_id)
        except Exception as e:
            logger.error(f"Error publishing app home: {e}")

    @bolt_app.event("reaction_added")
    def handle_reaction_added(event, logger):
        """Delegate an added reaction event to attendance routing."""
        return _delegate_reaction_event(event, removed=False)

    @bolt_app.event("reaction_removed")
    def handle_reaction_removed(event, logger):
        """Delegate a removed reaction event to attendance routing."""
        return _handle_reaction_removed(event)

    # =========================================================================
    # Custom Functions (Workflow Builder Custom Steps)
    # =========================================================================

    @bolt_app.function("reactivate_membership")
    def handle_reactivate_membership(inputs, complete, fail, logger):
        """Handle reactivation workflow custom step.

        Triggered by Workflow Builder when an SCG user clicks the
        reactivation workflow in #tcsc-reactivate-me.
        """
        user_id = inputs.get("user_id")
        if not user_id:
            fail("No user_id provided")
            return

        logger.info(f"Reactivation request from {user_id}")

        with get_app_context():
            from datetime import datetime
            from app.models import User, SlackUser, db
            from app.slack.channel_sync import load_channel_config
            from app.slack.client import get_team_id, get_channel_maps
            from app.slack.admin_api import change_user_role, ROLE_MCG
            from app.notifications.slack import send_tier_transition_notification

            slack_user = SlackUser.query.filter_by(slack_uid=user_id).first()
            if not slack_user or not slack_user.user:
                fail("No linked TCSC account found for your Slack user. Please contact an admin.")
                return

            user = slack_user.user

            if user.status != 'ALUMNI' or user.seasons_since_active < 2:
                fail("Your account is not eligible for reactivation. You may already have full access.")
                return

            try:
                config = load_channel_config()
                channel_name_to_id, _ = get_channel_maps()
                team_id = get_team_id()

                mcg_channel_names = config.get('channels', {}).get('multi_channel_guest', [])
                mcg_channel_ids = []
                for name in mcg_channel_names:
                    cid = channel_name_to_id.get(name)
                    if cid:
                        mcg_channel_ids.append(cid)

                change_user_role(
                    user_id=user_id,
                    email=user.email,
                    target_role=ROLE_MCG,
                    team_id=team_id,
                    dry_run=False,
                    channel_ids=mcg_channel_ids,
                )

                # Grace period: stamp last_slack_activity so the next sync doesn't
                # immediately re-demote them. The user clicked the reactivation
                # workflow, which is its own implicit "I'm active" signal.
                slack_user.last_slack_activity = datetime.utcnow()
                db.session.commit()

                send_tier_transition_notification(
                    name=user.full_name,
                    email=user.email,
                    from_tier='single_channel_guest',
                    to_tier='multi_channel_guest',
                    reason='self-service reactivation',
                )

                logger.info(f"Reactivated {user.email} from SCG to MCG")
                complete(outputs={})

            except Exception as e:
                logger.error(f"Reactivation failed for {user.email}: {e}")
                fail(f"Reactivation failed. Please try again or contact an admin.")

    @bolt_app.event("message")
    def handle_message_events(body, logger):
        """Handle message events (including DMs)."""
        pass

else:
    logger.info(
        "Slack Bolt disabled: bot token configured=%s, signing secret configured=%s",
        bool(_bot_token),
        bool(_signing_secret),
    )


# =============================================================================
# Helper Functions (always defined)
# =============================================================================

def _handle_tcsc_command(ack, command: dict, client, logger) -> None:
    """Route /tcsc while keeping Practice Preview isolated from persistence."""
    ack()

    command_text = command.get("text", "")
    user_id = command.get("user_id", "")
    user_name = command.get("user_name", "")
    channel_id = command.get("channel_id", "")

    if command_text.strip().lower() == "practice-preview":
        if channel_id != _PRACTICE_PREVIEW_CHANNEL_ID:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=_PRACTICE_PREVIEW_CHANNEL_ONLY_TEXT,
            )
            return

        trigger_id = command.get("trigger_id")
        if not trigger_id:
            logger.error("No trigger_id in /tcsc practice-preview command")
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=_PRACTICE_PREVIEW_RETRY_TEXT,
            )
            return

        from app.slack.modals import build_practice_preview_modal
        from app.utils import now_central_naive

        practice_date = now_central_naive().replace(
            hour=18, minute=15, second=0, microsecond=0
        )
        modal = build_practice_preview_modal(practice_date)
        try:
            client.views_open(trigger_id=trigger_id, view=modal)
        except Exception:
            logger.exception("Could not open Practice Preview")
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=_PRACTICE_PREVIEW_RETRY_TEXT,
            )
        return

    from app.slack.commands import handle_tcsc_command as process_command

    with get_app_context():
        response = process_command(command_text, user_id, user_name)

    client.chat_postEphemeral(
        channel=channel_id,
        user=user_id,
        text=response.get("text", ""),
        blocks=response.get("blocks"),
    )


def _handle_practice_preview_submission(ack) -> None:
    """Dismiss the synthetic preview without reading or saving its state."""
    ack()


_PRACTICE_REACTION_ACTION_IDS = frozenset(
    _PRACTICE_REACTION_ACTION_ID_ORDER
)
_PRACTICE_REACTION_CALLBACKS = {
    "preview": "practice_preview",
    "create": "practice_create",
    "edit": "practice_edit_full",
}
_PRACTICE_REACTION_SELECTOR_MISSING = object()


def _parse_practice_reaction_selector_ids(
    values,
    *,
    block_id: str,
    action_id: str,
):
    """Parse a selector as present-valid, present-invalid, or missing."""
    if not isinstance(values, Mapping):
        raise ValueError("Invalid practice reaction selector state")
    if block_id not in values:
        return _PRACTICE_REACTION_SELECTOR_MISSING
    block = values.get(block_id)
    selection = block.get(action_id) if isinstance(block, Mapping) else None
    options = (
        selection.get("selected_options")
        if isinstance(selection, Mapping)
        else None
    )
    if not isinstance(options, list):
        raise ValueError("Invalid practice reaction selector state")

    result = []
    seen = set()
    for option in options:
        raw = option.get("value") if isinstance(option, Mapping) else None
        if (
            not isinstance(raw, str)
            or not raw.isascii()
            or not raw.isdecimal()
            or raw == "0"
            or raw != str(int(raw))
        ):
            raise ValueError("Invalid practice reaction selector state")
        value = int(raw)
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return tuple(result)


def _strict_practice_reaction_selector_ids(
    values,
    *,
    block_id: str,
    action_id: str,
) -> tuple[int, ...]:
    """Parse one complete Slack multi-select value without coercion."""
    result = _parse_practice_reaction_selector_ids(
        values,
        block_id=block_id,
        action_id=action_id,
    )
    if result is _PRACTICE_REACTION_SELECTOR_MISSING:
        raise ValueError("Invalid practice reaction selector state")
    return result


def _resolve_practice_reaction_selector_ids(
    parsed,
    *,
    authoritative_sources,
    last_valid_ids,
) -> tuple[int, ...]:
    if parsed is not _PRACTICE_REACTION_SELECTOR_MISSING:
        return parsed
    if not tuple(authoritative_sources or ()) and not tuple(last_valid_ids or ()):
        return ()
    raise ValueError("Invalid practice reaction selector state")


def _require_canonical_practice_reaction_selector_ids(
    view,
    parsed,
    *,
    block_id: str,
    action_id: str,
) -> None:
    """Reject selector IDs that were not options in Slack's current view."""
    if parsed is _PRACTICE_REACTION_SELECTOR_MISSING:
        return
    blocks = view.get("blocks") if isinstance(view, Mapping) else None
    if not isinstance(blocks, list):
        raise ValueError("Invalid practice reaction selector options")
    block = next(
        (
            item
            for item in blocks
            if isinstance(item, Mapping) and item.get("block_id") == block_id
        ),
        None,
    )
    element = block.get("element") if isinstance(block, Mapping) else None
    if not isinstance(element, Mapping) or element.get("action_id") != action_id:
        raise ValueError("Invalid practice reaction selector options")
    options = element.get("options")
    if not isinstance(options, list):
        raise ValueError("Invalid practice reaction selector options")
    canonical = {
        option.get("value")
        for option in options
        if isinstance(option, Mapping) and isinstance(option.get("value"), str)
    }
    if any(str(value) not in canonical for value in parsed):
        raise ValueError("Invalid practice reaction selector options")


def _preview_practice_reaction_sources(preview_config):
    practice_types = tuple(
        SimpleNamespace(**source)
        for source in preview_config["practice_types"]
    )
    activities = tuple(
        SimpleNamespace(**source)
        for source in preview_config["activities"]
    )
    return practice_types, activities


def _selected_practice_reaction_sources(
    all_sources,
    selected_ids: tuple[int, ...],
):
    by_id = {source.id: source for source in all_sources}
    if any(source_id not in by_id for source_id in selected_ids):
        raise ValueError("Unknown practice reaction selector ID")
    return tuple(by_id[source_id] for source_id in selected_ids)


def _practice_reaction_add_allowed(state) -> bool:
    from app.practices.plan_reaction_editor import (
        reserved_plan_reaction_slots,
    )
    from app.practices.plan_reactions import MAX_PLAN_REACTIONS

    return (
        (
            state.effective_inherited_count == 0
            or bool(state.unconfigured_activity_names)
        )
        and not state.blocking_error
        and reserved_plan_reaction_slots(state) < MAX_PLAN_REACTIONS
    )


def _apply_practice_reaction_action(
    state,
    *,
    action,
    activity_ids: tuple[int, ...],
    type_ids: tuple[int, ...],
    selected_activities,
    selected_types,
    catalog,
    mode: str,
):
    from app.practices.plan_reaction_editor import (
        add_catalog_plan_reaction,
        reconcile_plan_reaction_editor_state,
        remove_plan_reaction,
        restore_plan_reaction_defaults,
        undo_plan_reaction,
    )
    from app.practices.plan_reactions import PlanReactionValidationError

    action_id = action.get("action_id")
    if action_id not in _PRACTICE_REACTION_ACTION_IDS:
        raise PlanReactionValidationError("Unknown practice reaction action")

    if action_id in {"activity_ids", "type_ids"}:
        return reconcile_plan_reaction_editor_state(
            state,
            practice_types=selected_types,
            activities=selected_activities,
        ).state

    if action_id == "practice_reaction_restore":
        if mode != "edit":
            raise PlanReactionValidationError("Restore is available only in Edit")
        return restore_plan_reaction_defaults(
            state,
            practice_types=selected_types,
            activities=selected_activities,
        ).state

    if (
        frozenset(activity_ids) != frozenset(state.last_valid_activity_ids)
        or frozenset(type_ids) != frozenset(state.last_valid_type_ids)
    ):
        raise PlanReactionValidationError(
            "Stale practice reaction selector state"
        )

    if action_id == "practice_reaction_edit":
        working = copy.deepcopy(state)
        working.editor_expanded = True
        working.add_open = False
        return working

    if action_id == "practice_reaction_remove":
        row_id = action.get("value")
        row = next(
            (
                item
                for item in state.rows
                if item.row_id == row_id and not item.removed
            ),
            None,
        )
        if not isinstance(row_id, str) or row is None:
            raise PlanReactionValidationError("Unknown reaction row")
        return remove_plan_reaction(state, row_id)

    if action_id == "practice_reaction_undo":
        row_id = action.get("value")
        if not isinstance(row_id, str):
            raise PlanReactionValidationError("Unknown removed reaction row")
        return undo_plan_reaction(state, row_id)

    if not _practice_reaction_add_allowed(state):
        raise PlanReactionValidationError("Cannot add a Plan reaction")

    available_catalog = tuple(
        item
        for item in catalog
        if not any(row.emoji == item.emoji for row in state.rows)
    )
    if len(catalog) > 100 or not available_catalog:
        raise PlanReactionValidationError(
            "No configured Plan reactions are available"
        )

    if action_id == "practice_reaction_add":
        working = copy.deepcopy(state)
        working.add_open = True
        return working

    if not state.add_open:
        raise PlanReactionValidationError("Reaction catalog is not open")
    selected = action.get("selected_option")
    option_id = (
        selected.get("value") if isinstance(selected, Mapping) else None
    )
    option = next(
        (
            item
            for item in available_catalog
            if isinstance(option_id, str) and item.option_id == option_id
        ),
        None,
    )
    if option is None or any(row.emoji == option.emoji for row in state.rows):
        raise PlanReactionValidationError("Unknown reaction catalog option")
    return add_catalog_plan_reaction(state, option)


def _build_preview_practice_reaction_view(
    *,
    preview_config,
    state,
    catalog,
    values,
):
    from app.slack.modals import build_practice_create_modal

    modal = build_practice_create_modal(
        datetime.strptime(preview_config["practice_date"], "%Y-%m-%d"),
        preview_config["default_time"],
        locations=[
            (location["id"], location["name"])
            for location in preview_config["locations"]
        ],
        all_activities=[
            (source["id"], source["name"])
            for source in preview_config["activities"]
        ],
        all_types=[
            (source["id"], source["name"])
            for source in preview_config["practice_types"]
        ],
        slot_defaults=preview_config["slot_defaults"],
        eligible_coaches=[
            (person["user_id"], person["name"], person["slack_uid"])
            for person in preview_config["eligible_coaches"]
        ],
        eligible_leads=[
            (person["user_id"], person["name"], person["slack_uid"])
            for person in preview_config["eligible_leads"]
        ],
        reaction_editor=state,
        reaction_catalog=catalog,
        current_values=values,
        view_mode="preview",
        preview_config=preview_config,
    )
    modal.update({
        "title": {"type": "plain_text", "text": "Practice Preview"},
        "submit": {"type": "plain_text", "text": "Close Preview"},
        "callback_id": "practice_preview",
    })
    return modal


def load_selected_plan_reaction_sources(session, *, activity_ids, type_ids):
    """Late-import the strict source loader for always-importable handlers."""
    from app.practices.plan_reaction_queries import (
        load_selected_plan_reaction_sources as load_selected,
    )

    return load_selected(
        session,
        activity_ids=activity_ids,
        type_ids=type_ids,
    )


def load_all_plan_reaction_sources(session):
    """Late-import the authoritative Settings loader."""
    from app.practices.plan_reaction_queries import (
        load_all_plan_reaction_sources as load_all,
    )

    return load_all(session)


def _build_production_practice_reaction_view(
    *,
    mode,
    context,
    state,
    action,
    activity_selection,
    type_selection,
    values,
    build_plan_reaction_catalog,
):
    from app.models import db
    from app.practices.models import Practice
    from app.practices.service import convert_practice_to_info
    from app.slack.modals import (
        build_practice_create_modal,
        build_practice_edit_full_modal,
    )

    try:
        all_sources = load_all_plan_reaction_sources(db.session)
    except Exception as exc:
        raise _AuthoritativePracticeReactionLoadError(
            "Could not load practice reaction Settings"
        ) from exc
    activity_ids = _resolve_practice_reaction_selector_ids(
        activity_selection,
        authoritative_sources=all_sources.activities,
        last_valid_ids=state.last_valid_activity_ids,
    )
    type_ids = _resolve_practice_reaction_selector_ids(
        type_selection,
        authoritative_sources=all_sources.practice_types,
        last_valid_ids=state.last_valid_type_ids,
    )
    try:
        selected_sources = load_selected_plan_reaction_sources(
            db.session,
            activity_ids=activity_ids,
            type_ids=type_ids,
        )
    except Exception as exc:
        raise _AuthoritativePracticeReactionLoadError(
            "Could not load selected practice reaction sources"
        ) from exc
    practice = None
    if mode == "edit":
        try:
            practice = db.session.get(Practice, context["practice_id"])
        except Exception as exc:
            raise _AuthoritativePracticeReactionLoadError(
                "Could not load practice reaction Edit target"
            ) from exc
        if practice is None:
            raise _AuthoritativePracticeReactionLoadError(
                "Unknown practice reaction Edit target"
            )

    try:
        catalog = build_plan_reaction_catalog(
            all_sources.practice_types,
            all_sources.activities,
        )
    except Exception as exc:
        raise _AuthoritativePracticeReactionLoadError(
            "Could not normalize practice reaction Settings"
        ) from exc
    state = _apply_practice_reaction_action(
        state,
        action=action,
        activity_ids=activity_ids,
        type_ids=type_ids,
        selected_activities=selected_sources.activities,
        selected_types=selected_sources.practice_types,
        catalog=catalog,
        mode=mode,
    )
    try:
        locations, all_activities, all_types = _load_modal_ref_data()
        eligible_coaches, eligible_leads = _load_eligible_people()
    except Exception as exc:
        raise _AuthoritativePracticeReactionLoadError(
            "Could not load practice modal reference data"
        ) from exc

    if mode == "edit":
        try:
            return build_practice_edit_full_modal(
                convert_practice_to_info(practice),
                locations=locations,
                eligible_coaches=eligible_coaches,
                eligible_leads=eligible_leads,
                all_activities=all_activities,
                all_types=all_types,
                reaction_editor=state,
                reaction_catalog=catalog,
                current_values=values,
            )
        except Exception as exc:
            raise _AuthoritativePracticeReactionLoadError(
                "Could not rebuild practice Edit modal"
            ) from exc

    current_time = _safe_get(
        values,
        "time_block",
        "practice_time",
        "selected_time",
        default="18:00",
    )
    if not isinstance(current_time, str):
        current_time = "18:00"
    try:
        return build_practice_create_modal(
            datetime.strptime(context["date"], "%Y-%m-%d"),
            current_time,
            locations=locations,
            channel_id=context["channel_id"],
            message_ts=context["message_ts"],
            all_activities=all_activities,
            all_types=all_types,
            slot_defaults={
                "activity_ids": list(activity_ids),
                "type_ids": list(type_ids),
            },
            silent_defaults=context.get("silent"),
            eligible_coaches=eligible_coaches,
            eligible_leads=eligible_leads,
            reaction_editor=state,
            reaction_catalog=catalog,
            current_values=values,
        )
    except Exception as exc:
        raise _AuthoritativePracticeReactionLoadError(
            "Could not rebuild practice Create modal"
        ) from exc


def _update_practice_reaction_view(
    client,
    logger,
    *,
    view_id,
    view_hash,
    rebuilt,
):
    try:
        client.views_update(
            view_id=view_id,
            hash=view_hash,
            view=rebuilt,
        )
    except Exception:
        logger.exception("Failed to update practice reaction editor view")


def _handle_practice_reaction_action(ack, body, action, client, logger) -> None:
    """Handle all Create, Edit, and Preview reaction-editor actions."""
    ack()
    from app.practices.plan_reactions import (
        PlanReactionValidationError,
        build_plan_reaction_catalog,
    )
    from app.slack.practice_reaction_editor import (
        decode_practice_reaction_metadata,
        merge_practice_reaction_inputs,
    )

    try:
        if not isinstance(body, Mapping) or body.get("type") != "block_actions":
            raise ValueError("Invalid practice reaction action body")
        if not isinstance(action, Mapping):
            raise ValueError("Invalid practice reaction action payload")
        user = body.get("user")
        if (
            not isinstance(user, Mapping)
            or not isinstance(user.get("id"), str)
            or not user["id"]
        ):
            raise ValueError("Invalid practice reaction action user")
        view = body.get("view")
        if not isinstance(view, Mapping):
            raise ValueError("Missing practice reaction action view")
        view_id = view.get("id")
        view_hash = view.get("hash")
        callback_id = view.get("callback_id")
        metadata = view.get("private_metadata")
        values = _safe_get(view, "state", "values")
        if not all(isinstance(item, str) and item for item in (
            view_id,
            view_hash,
            callback_id,
            metadata,
        )):
            raise ValueError("Invalid practice reaction action view")

        mode, context, state, preview_config = (
            decode_practice_reaction_metadata(metadata)
        )
        if callback_id != _PRACTICE_REACTION_CALLBACKS[mode]:
            raise ValueError("Practice reaction mode/callback mismatch")
        activity_selection = _parse_practice_reaction_selector_ids(
            values,
            block_id="activities_block",
            action_id="activity_ids",
        )
        type_selection = _parse_practice_reaction_selector_ids(
            values,
            block_id="types_block",
            action_id="type_ids",
        )
        _require_canonical_practice_reaction_selector_ids(
            view,
            activity_selection,
            block_id="activities_block",
            action_id="activity_ids",
        )
        _require_canonical_practice_reaction_selector_ids(
            view,
            type_selection,
            block_id="types_block",
            action_id="type_ids",
        )
        state = merge_practice_reaction_inputs(state, values)

        if mode == "preview":
            all_types, all_activities = _preview_practice_reaction_sources(
                preview_config
            )
            activity_ids = _resolve_practice_reaction_selector_ids(
                activity_selection,
                authoritative_sources=all_activities,
                last_valid_ids=state.last_valid_activity_ids,
            )
            type_ids = _resolve_practice_reaction_selector_ids(
                type_selection,
                authoritative_sources=all_types,
                last_valid_ids=state.last_valid_type_ids,
            )
            selected_types = _selected_practice_reaction_sources(
                all_types,
                type_ids,
            )
            selected_activities = _selected_practice_reaction_sources(
                all_activities,
                activity_ids,
            )
            catalog = build_plan_reaction_catalog(all_types, all_activities)
            state = _apply_practice_reaction_action(
                state,
                action=action,
                activity_ids=activity_ids,
                type_ids=type_ids,
                selected_activities=selected_activities,
                selected_types=selected_types,
                catalog=catalog,
                mode=mode,
            )
            rebuilt = _build_preview_practice_reaction_view(
                preview_config=preview_config,
                state=state,
                catalog=catalog,
                values=values,
            )
        else:
            try:
                with get_app_context():
                    rebuilt = _build_production_practice_reaction_view(
                        mode=mode,
                        context=context,
                        state=state,
                        action=action,
                        activity_selection=activity_selection,
                        type_selection=type_selection,
                        values=values,
                        build_plan_reaction_catalog=(
                            build_plan_reaction_catalog
                        ),
                    )
            except _AuthoritativePracticeReactionLoadError:
                logger.exception(
                    "Could not load authoritative practice reaction Settings"
                )
                try:
                    with get_app_context():
                        from app.models import db

                        db.session.rollback()
                except Exception:
                    logger.exception(
                        "Could not roll back failed practice reaction load"
                    )
                from app.slack.practice_reaction_editor import (
                    build_retryable_practice_reaction_error_view,
                )

                retry_view = build_retryable_practice_reaction_error_view(
                    view,
                    values,
                    "Could not load reaction Settings. Try again.",
                )
                _update_practice_reaction_view(
                    client,
                    logger,
                    view_id=view_id,
                    view_hash=view_hash,
                    rebuilt=retry_view,
                )
                return
    except (KeyError, TypeError, ValueError, PlanReactionValidationError) as exc:
        logger.warning("Ignoring invalid practice reaction action: %s", exc)
        return

    _update_practice_reaction_view(
        client,
        logger,
        view_id=view_id,
        view_hash=view_hash,
        rebuilt=rebuilt,
    )


def _safe_get(d: dict, *keys, default=None):
    """Safely get nested dictionary values, handling None values.

    Args:
        d: Dictionary to search
        *keys: Keys to traverse
        default: Default value if any key is missing or None

    Returns:
        Value at nested key path, or default if not found
    """
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key)
        if d is None:
            return default
    return d if d is not None else default


def _parse_practice_authoring_values(
    values: dict,
    *,
    include_logistics_notes: bool = False,
) -> tuple[dict, dict[str, str]]:
    def read_text(block_id, action_id, label):
        block = values.get(block_id) if isinstance(values, Mapping) else None
        action = block.get(action_id) if isinstance(block, Mapping) else None
        if not isinstance(action, Mapping) or "value" not in action:
            return "", f"{label} must be text"
        value = action["value"]
        if value is None:
            return "", None
        if not isinstance(value, str):
            return "", f"{label} must be text"
        return value, None

    workout, workout_error = read_text(
        "workout_block",
        "workout_description",
        "Workout",
    )
    fields = {"workout_description": workout}
    errors = {}
    if workout_error:
        errors["workout_block"] = workout_error
    if len(fields["workout_description"]) > 2500:
        errors["workout_block"] = "Workout must be 2,500 characters or fewer"

    if include_logistics_notes:
        notes, notes_error = read_text(
            "notes_block",
            "logistics_notes",
            "Notes / Logistics",
        )
        fields["logistics_notes"] = notes
        if notes_error:
            errors["notes_block"] = notes_error
        if len(fields["logistics_notes"]) > 2500:
            errors["notes_block"] = (
                "Notes / Logistics must be 2,500 characters or fewer"
            )
    return fields, errors


def _strict_optional_practice_ids(
    values,
    *,
    block_id: str,
    action_id: str,
) -> tuple[int, ...]:
    if not isinstance(values, Mapping) or block_id not in values:
        return ()
    return _strict_practice_reaction_selector_ids(
        values,
        block_id=block_id,
        action_id=action_id,
    )


def _strict_practice_action_state(values, *, block_id, action_id):
    block = values.get(block_id) if isinstance(values, Mapping) else None
    action = block.get(action_id) if isinstance(block, Mapping) else None
    if not isinstance(action, Mapping):
        raise ValueError("Invalid practice form state")
    return action


def _strict_practice_location_id(values):
    action = _strict_practice_action_state(
        values,
        block_id="location_block",
        action_id="location_id",
    )
    if "selected_option" in action:
        selected = action["selected_option"]
        raw = selected.get("value") if isinstance(selected, Mapping) else None
        if (
            not isinstance(raw, str)
            or not raw.isascii()
            or not raw.isdecimal()
            or raw == "0"
            or raw != str(int(raw))
        ):
            raise ValueError("Invalid practice location")
        return int(raw)
    if "value" in action and isinstance(action["value"], str):
        return None
    raise ValueError("Invalid practice location")


def _strict_practice_option_values(
    values,
    *,
    block_id,
    action_id,
    allowed,
):
    action = _strict_practice_action_state(
        values,
        block_id=block_id,
        action_id=action_id,
    )
    selected = action.get("selected_options")
    if not isinstance(selected, list):
        raise ValueError("Invalid practice option state")
    result = []
    for option in selected:
        value = option.get("value") if isinstance(option, Mapping) else None
        if not isinstance(value, str) or value not in allowed:
            raise ValueError("Invalid practice option state")
        result.append(value)
    if len(set(result)) != len(result):
        raise ValueError("Invalid practice option state")
    return tuple(result)


def _practice_reaction_error_block(state, view, exc) -> str:
    emoji = getattr(exc, "emoji", None)
    row = next(
        (item for item in state.rows if item.emoji == emoji and not item.removed),
        next((item for item in state.rows if not item.removed), None),
    )
    preferred = (
        f"practice_reaction_row_{row.row_id}"
        if row is not None
        else "location_block"
    )
    return _practice_submission_error_block(view, preferred)


def _practice_source_error_block(view, exc) -> str:
    preferred = (
        "activities_block"
        if getattr(exc, "field", None) == "activities"
        else "types_block"
        if getattr(exc, "field", None) == "types"
        else "location_block"
    )
    return _practice_submission_error_block(view, preferred)


def _practice_view_input_block_ids(view) -> tuple[str, ...]:
    """Return the real input block IDs Slack can attach submission errors to."""
    blocks = view.get("blocks") if isinstance(view, Mapping) else None
    if not isinstance(blocks, list):
        return ()
    return tuple(
        block_id
        for block in blocks
        if isinstance(block, Mapping)
        and block.get("type") == "input"
        and isinstance((block_id := block.get("block_id")), str)
        and block_id
    )


def _practice_submission_error_block(view, preferred: str) -> str:
    """Choose an input block that is actually present in the submitted view."""
    input_block_ids = _practice_view_input_block_ids(view)
    if preferred in input_block_ids:
        return preferred
    for fallback in (
        "location_block",
        "workout_block",
        "notes_block",
        "flags_block",
    ):
        if fallback in input_block_ids:
            return fallback
    if input_block_ids:
        return input_block_ids[0]
    return "location_block"


def _practice_reaction_submission_state_errors(
    state,
    view,
    *,
    activity_ids: tuple[int, ...],
    type_ids: tuple[int, ...],
    include_blocking_without_mismatch: bool = True,
) -> dict[str, str]:
    """Reject blocked or stale selector metadata before authorization/mutation."""
    errors = {}
    message = state.blocking_error or (
        "The Activity or Workout Type selection changed unexpectedly. "
        "Please choose it again."
    )
    activity_mismatch = frozenset(activity_ids) != frozenset(
        state.last_valid_activity_ids
    )
    type_mismatch = frozenset(type_ids) != frozenset(
        state.last_valid_type_ids
    )
    input_block_ids = _practice_view_input_block_ids(view)
    if activity_mismatch and "activities_block" in input_block_ids:
        errors["activities_block"] = message
    if type_mismatch and "types_block" in input_block_ids:
        errors["types_block"] = message
    if include_blocking_without_mismatch and state.blocking_error and not errors:
        errors[_practice_submission_error_block(view, "location_block")] = message
    elif (activity_mismatch or type_mismatch) and not errors:
        errors[_practice_submission_error_block(view, "location_block")] = message
    return errors


def _handle_practice_create_submission(
    ack,
    body,
    view,
    client,
    logger,
):
    """Validate the complete structured Create submission before mutation."""
    from app.practices.plan_reactions import (
        PlanReactionValidationError,
        build_plan_reaction_catalog,
        resolve_plan_reaction_defaults,
        validate_authorized_plan_reactions,
    )
    from app.slack.practice_reaction_editor import (
        decode_practice_reaction_metadata,
        parse_practice_reaction_submission,
    )

    values = _safe_get(view, "state", "values")
    authoring, errors = _parse_practice_authoring_values(values)
    if errors:
        ack(response_action="errors", errors=errors)
        return None

    try:
        if not isinstance(body, Mapping) or not isinstance(view, Mapping):
            raise ValueError("Invalid Create submission")
        user = body.get("user")
        user_id = user.get("id") if isinstance(user, Mapping) else None
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("Invalid Create submission user")
        if view.get("callback_id") != "practice_create":
            raise ValueError("Invalid Create submission callback")
        mode, context, state, preview_config = (
            decode_practice_reaction_metadata(view.get("private_metadata"))
        )
        if mode != "create" or preview_config is not None:
            raise ValueError("Invalid Create submission mode")
    except (KeyError, TypeError, ValueError, PlanReactionValidationError) as exc:
        logger.warning("Invalid practice Create submission: %s", exc)
        ack(response_action="errors", errors={
            "location_block": (
                "Something went wrong reading the form. Please try again."
            )
        })
        return None

    try:
        activity_selection = _parse_practice_reaction_selector_ids(
            values,
            block_id="activities_block",
            action_id="activity_ids",
        )
    except (TypeError, ValueError):
        ack(response_action="errors", errors={
            _practice_submission_error_block(view, "activities_block"): (
                "Invalid Activity selection. Please try again."
            )
        })
        return None
    try:
        type_selection = _parse_practice_reaction_selector_ids(
            values,
            block_id="types_block",
            action_id="type_ids",
        )
    except (TypeError, ValueError):
        ack(response_action="errors", errors={
            _practice_submission_error_block(view, "types_block"): (
                "Invalid Workout Type selection. Please try again."
            )
        })
        return None

    with get_app_context():
        from app.models import User, db
        from app.practices.models import (
            Practice,
            PracticeLead,
            PracticeLocation,
        )

        try:
            all_sources = load_all_plan_reaction_sources(db.session)
        except Exception:
            db.session.rollback()
            logger.exception("Could not validate practice Create Settings")
            ack(response_action="errors", errors={
                "location_block": (
                    "Could not load reaction Settings. Please try again."
                )
            })
            return None

        try:
            activity_ids = _resolve_practice_reaction_selector_ids(
                activity_selection,
                authoritative_sources=all_sources.activities,
                last_valid_ids=state.last_valid_activity_ids,
            )
        except ValueError:
            ack(response_action="errors", errors={
                _practice_submission_error_block(
                    view,
                    "activities_block",
                ): "Invalid Activity selection. Please try again."
            })
            return None
        try:
            type_ids = _resolve_practice_reaction_selector_ids(
                type_selection,
                authoritative_sources=all_sources.practice_types,
                last_valid_ids=state.last_valid_type_ids,
            )
        except ValueError:
            ack(response_action="errors", errors={
                _practice_submission_error_block(
                    view,
                    "types_block",
                ): "Invalid Workout Type selection. Please try again."
            })
            return None

        state_errors = _practice_reaction_submission_state_errors(
            state,
            view,
            activity_ids=activity_ids,
            type_ids=type_ids,
            include_blocking_without_mismatch=False,
        )
        if state_errors:
            ack(response_action="errors", errors=state_errors)
            return None

        try:
            selected_sources = load_selected_plan_reaction_sources(
                db.session,
                activity_ids=activity_ids,
                type_ids=type_ids,
            )
            resolve_plan_reaction_defaults(
                selected_sources.practice_types,
                selected_sources.activities,
            )
        except PlanReactionValidationError as exc:
            ack(response_action="errors", errors={
                _practice_source_error_block(view, exc): str(exc)
            })
            return None
        except Exception:
            db.session.rollback()
            logger.exception("Could not load practice Create reaction sources")
            ack(response_action="errors", errors={
                "location_block": (
                    "Could not load reaction Settings. Please try again."
                )
            })
            return None

        state_errors = _practice_reaction_submission_state_errors(
            state,
            view,
            activity_ids=activity_ids,
            type_ids=type_ids,
        )
        if state_errors:
            ack(response_action="errors", errors=state_errors)
            return None

        try:
            catalog = build_plan_reaction_catalog(
                all_sources.practice_types,
                all_sources.activities,
            )
        except Exception:
            db.session.rollback()
            logger.exception("Could not validate practice Create Settings")
            ack(response_action="errors", errors={
                "location_block": (
                    "Could not load reaction Settings. Please try again."
                )
            })
            return None

        submitted_rows, reaction_errors = parse_practice_reaction_submission(
            state,
            values,
        )
        if reaction_errors:
            ack(response_action="errors", errors=reaction_errors)
            return None
        try:
            plan_reactions = validate_authorized_plan_reactions(
                submitted_rows,
                catalog=catalog,
                protected_snapshot=(),
            )
        except PlanReactionValidationError as exc:
            ack(response_action="errors", errors={
                _practice_reaction_error_block(state, view, exc): str(exc)
            })
            return None

        try:
            location_id = _strict_practice_location_id(values)
            if (
                location_id is not None
                and db.session.get(PracticeLocation, location_id) is None
            ):
                raise ValueError("Unknown practice location")

            time_str = _safe_get(
                values,
                "time_block",
                "practice_time",
                "selected_time",
            )
            if not isinstance(time_str, str):
                raise ValueError("Invalid practice time")
            parsed_time = datetime.strptime(time_str, "%H:%M")
            practice_date = datetime.strptime(context["date"], "%Y-%m-%d")
            practice_datetime = practice_date.replace(
                hour=parsed_time.hour,
                minute=parsed_time.minute,
            )

            flag_values = _strict_practice_option_values(
                values,
                block_id="flags_block",
                action_id="practice_flags",
                allowed={"is_dark_practice", "has_social"},
            )

            coach_ids = _strict_optional_practice_ids(
                values,
                block_id="coaches_block",
                action_id="coach_ids",
            )
            lead_ids = _strict_optional_practice_ids(
                values,
                block_id="leads_block",
                action_id="lead_ids",
            )
            wanted_ids = set(coach_ids) | set(lead_ids)
            existing_user_ids = (
                {
                    item.id
                    for item in db.session.query(User).filter(
                        User.id.in_(wanted_ids)
                    ).all()
                }
                if wanted_ids
                else set()
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Invalid practice Create values: %s", exc)
            ack(response_action="errors", errors={
                "location_block": (
                    "Something went wrong reading the form. Please try again."
                )
            })
            return None
        except Exception:
            db.session.rollback()
            logger.exception(
                "Could not validate practice Create location and people"
            )
            ack(response_action="errors", errors={
                _practice_submission_error_block(
                    view,
                    "location_block",
                ): "Could not validate practice details. Please try again."
            })
            return None

        channel_id = context["channel_id"]
        message_ts = context["message_ts"]
        has_social = "has_social" in flag_values
        silent = context.get("silent") or {}
        social_location_id = (
            silent.get("social_location_id") if has_social else None
        )
        try:
            practice = Practice(
                date=practice_datetime,
                day_of_week=practice_datetime.strftime("%A"),
                status="scheduled",
                location_id=location_id,
                social_location_id=social_location_id,
                is_dark_practice="is_dark_practice" in flag_values,
                slack_coach_summary_ts=message_ts,
                workout_description=authoring["workout_description"],
                plan_reactions=plan_reactions,
            )
            practice.activities = list(selected_sources.activities)
            practice.practice_types = list(selected_sources.practice_types)
            db.session.add(practice)
            db.session.flush()
            for role, selected_ids in (
                ("coach", coach_ids),
                ("lead", lead_ids),
            ):
                for selected_id in selected_ids:
                    if selected_id in existing_user_ids:
                        db.session.add(PracticeLead(
                            practice_id=practice.id,
                            user_id=selected_id,
                            role=role,
                        ))
                    else:
                        logger.warning(
                            "Skipping %s: user %s not found",
                            role,
                            selected_id,
                        )
            db.session.commit()
            practice_id = practice.id
        except Exception:
            db.session.rollback()
            logger.exception("practice_create: failed to create practice")
            ack(response_action="errors", errors={
                "location_block": (
                    "Could not create the practice. Please try again."
                )
            })
            return None

        logger.info(
            "Practice #%s created by %s for %s",
            practice_id,
            user_id,
            practice_datetime,
        )

    ack()
    confirm_text = (
        ":white_check_mark: Created practice for "
        f"{practice_datetime.strftime('%A, %B %-d at %-I:%M %p')}"
    )
    threading.Thread(
        target=_post_practice_create_updates,
        args=(
            client,
            channel_id,
            message_ts,
            practice_date,
            user_id,
            confirm_text,
        ),
        daemon=True,
        name="practice-create-post",
    ).start()
    return None


def _run_practice_edit_full_post_save(
    *,
    practice_id,
    user_id,
    should_notify,
    had_root,
    previous_date,
    previous_location_id,
    previous_plan_reactions,
    client,
    logger,
):
    """Refresh announcements after save while owning an application context."""
    with get_app_context():
        from app.models import db
        from app.practices.models import Practice
        from app.slack.practices import refresh_practice_posts
        from app.slack.practices.announcements import (
            build_announcement_change_notice,
        )

        reload_failed = False
        try:
            practice = db.session.get(Practice, practice_id)
        except Exception:
            db.session.rollback()
            logger.exception(
                "Practice %s was saved but reload failed before refresh",
                practice_id,
            )
            practice = None
            reload_failed = True
        if practice is None:
            if not reload_failed:
                logger.error(
                    "Practice %s was saved but could not be reloaded for refresh",
                    practice_id,
                )
            refresh_results = {
                "announcement": {
                    "success": False,
                    "error": "Saved practice could not be reloaded",
                }
            }
        else:
            announcement_notice = build_announcement_change_notice(
                previous_date=previous_date,
                previous_location_id=previous_location_id,
                practice=practice,
            )
            try:
                refresh_results = refresh_practice_posts(
                    practice,
                    change_type="edit",
                    actor_slack_id=user_id,
                    notify=should_notify,
                    announcement_notice=announcement_notice,
                    previous_plan_reactions=previous_plan_reactions,
                )
            except Exception as exc:
                logger.exception(
                    "Practice %s was saved but refresh raised", practice_id
                )
                refresh_results = {
                    "announcement": {"success": False, "error": str(exc)},
                }

        announcement = (refresh_results or {}).get("announcement") or {}
        if had_root and announcement.get("success") is not True:
            if client is not None:
                try:
                    client.chat_postMessage(
                        channel=user_id,
                        text=(
                            ":warning: Your "
                            + _FULL_EDIT_UNSYNCED_ERROR[0].lower()
                            + _FULL_EDIT_UNSYNCED_ERROR[1:]
                        ),
                    )
                except Exception:
                    logger.warning(
                        "Could not DM saved-but-unsynced practice edit to %s",
                        user_id,
                        exc_info=True,
                    )
            return {
                "success": False,
                "practice_updated": True,
                "error": _FULL_EDIT_UNSYNCED_ERROR,
                "refresh_results": refresh_results,
            }

        return {
            "success": True,
            "practice_updated": True,
            "refresh_results": refresh_results,
        }


def _dispatch_practice_edit_full_post_save(work) -> None:
    """Run committed Full Edit Slack synchronization off the response path."""
    threading.Thread(
        target=work,
        daemon=True,
        name="practice-edit-post-save",
    ).start()


def _handle_practice_edit_full_submission(
    ack,
    body,
    view,
    logger,
    client=None,
    *,
    post_save_dispatcher=None,
):
    """Validate and persist the active full-edit modal submission."""
    from app.practices.plan_reactions import (
        PlanReactionValidationError,
        build_plan_reaction_catalog,
        resolve_plan_reaction_defaults,
        validate_authorized_plan_reactions,
    )
    from app.slack.practice_reaction_editor import (
        decode_practice_reaction_metadata,
        parse_practice_reaction_submission,
    )

    values = _safe_get(view, "state", "values")
    authoring, errors = _parse_practice_authoring_values(
        values,
        include_logistics_notes=True,
    )
    if errors:
        ack(response_action="errors", errors=errors)
        return None

    try:
        if not isinstance(body, Mapping) or not isinstance(view, Mapping):
            raise ValueError("Invalid Full Edit submission")
        user = body.get("user")
        user_id = user.get("id") if isinstance(user, Mapping) else None
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("Invalid Full Edit user")
        if view.get("callback_id") != "practice_edit_full":
            raise ValueError("Invalid Full Edit callback")
        mode, context, state, preview_config = (
            decode_practice_reaction_metadata(view.get("private_metadata"))
        )
        if mode != "edit" or preview_config is not None:
            raise ValueError("Invalid Full Edit mode")
        practice_id = context["practice_id"]
    except (KeyError, TypeError, ValueError, PlanReactionValidationError) as exc:
        logger.warning("Invalid practice Full Edit submission: %s", exc)
        ack(response_action="errors", errors={
            "location_block": (
                "Something went wrong reading the form. Please try again."
            )
        })
        return None

    try:
        activity_selection = _parse_practice_reaction_selector_ids(
            values,
            block_id="activities_block",
            action_id="activity_ids",
        )
    except (TypeError, ValueError):
        ack(response_action="errors", errors={
            _practice_submission_error_block(view, "activities_block"): (
                "Invalid Activity selection. Please try again."
            )
        })
        return None
    try:
        type_selection = _parse_practice_reaction_selector_ids(
            values,
            block_id="types_block",
            action_id="type_ids",
        )
    except (TypeError, ValueError):
        ack(response_action="errors", errors={
            _practice_submission_error_block(view, "types_block"): (
                "Invalid Workout Type selection. Please try again."
            )
        })
        return None

    with get_app_context():
        from app.practices.models import (
            Practice,
            PracticeLead,
            PracticeLocation,
        )
        from app.models import User, db
        try:
            practice = db.session.get(Practice, practice_id)
        except Exception:
            db.session.rollback()
            logger.exception("Could not load practice %s for Full Edit", practice_id)
            ack(response_action="errors", errors={
                "location_block": (
                    "Could not load the practice. Please try again."
                )
            })
            return None
        if not practice:
            logger.error("Practice %s not found", practice_id)
            ack(response_action="errors", errors={
                "location_block": "Practice not found. Close and try again."
            })
            return None

        try:
            all_sources = load_all_plan_reaction_sources(db.session)
        except Exception:
            db.session.rollback()
            logger.exception("Could not validate practice Full Edit Settings")
            ack(response_action="errors", errors={
                "location_block": (
                    "Could not load reaction Settings. Please try again."
                )
            })
            return None

        try:
            activity_ids = _resolve_practice_reaction_selector_ids(
                activity_selection,
                authoritative_sources=all_sources.activities,
                last_valid_ids=state.last_valid_activity_ids,
            )
        except ValueError:
            ack(response_action="errors", errors={
                _practice_submission_error_block(
                    view,
                    "activities_block",
                ): "Invalid Activity selection. Please try again."
            })
            return None
        try:
            type_ids = _resolve_practice_reaction_selector_ids(
                type_selection,
                authoritative_sources=all_sources.practice_types,
                last_valid_ids=state.last_valid_type_ids,
            )
        except ValueError:
            ack(response_action="errors", errors={
                _practice_submission_error_block(
                    view,
                    "types_block",
                ): "Invalid Workout Type selection. Please try again."
            })
            return None

        state_errors = _practice_reaction_submission_state_errors(
            state,
            view,
            activity_ids=activity_ids,
            type_ids=type_ids,
            include_blocking_without_mismatch=False,
        )
        if state_errors:
            ack(response_action="errors", errors=state_errors)
            return None

        try:
            selected_sources = load_selected_plan_reaction_sources(
                db.session,
                activity_ids=activity_ids,
                type_ids=type_ids,
            )
            resolve_plan_reaction_defaults(
                selected_sources.practice_types,
                selected_sources.activities,
            )
        except PlanReactionValidationError as exc:
            ack(response_action="errors", errors={
                _practice_source_error_block(view, exc): str(exc)
            })
            return None
        except Exception:
            db.session.rollback()
            logger.exception("Could not load practice Full Edit reaction sources")
            ack(response_action="errors", errors={
                "location_block": (
                    "Could not load reaction Settings. Please try again."
                )
            })
            return None

        state_errors = _practice_reaction_submission_state_errors(
            state,
            view,
            activity_ids=activity_ids,
            type_ids=type_ids,
        )
        if state_errors:
            ack(response_action="errors", errors=state_errors)
            return None

        try:
            catalog = build_plan_reaction_catalog(
                all_sources.practice_types,
                all_sources.activities,
            )
        except Exception:
            db.session.rollback()
            logger.exception("Could not validate practice Full Edit Settings")
            ack(response_action="errors", errors={
                "location_block": (
                    "Could not load reaction Settings. Please try again."
                )
            })
            return None

        submitted_rows, reaction_errors = parse_practice_reaction_submission(
            state,
            values,
        )
        if reaction_errors:
            ack(response_action="errors", errors=reaction_errors)
            return None
        try:
            plan_reactions = validate_authorized_plan_reactions(
                submitted_rows,
                catalog=catalog,
                protected_snapshot=practice.plan_reactions or [],
            )
        except PlanReactionValidationError as exc:
            ack(response_action="errors", errors={
                _practice_reaction_error_block(state, view, exc): str(exc)
            })
            return None

        try:
            location_id = _strict_practice_location_id(values)
            if (
                location_id is not None
                and db.session.get(PracticeLocation, location_id) is None
            ):
                raise ValueError("Unknown practice location")

            flag_values = _strict_practice_option_values(
                values,
                block_id="flags_block",
                action_id="practice_flags",
                allowed={"is_dark_practice", "has_social"},
            )
            notify_values = _strict_practice_option_values(
                values,
                block_id="notify_block",
                action_id="notify_update",
                allowed={"notify"},
            )
            should_notify = "notify" in notify_values

            coach_user_ids = _strict_optional_practice_ids(
                values,
                block_id="coaches_block",
                action_id="coach_ids",
            )
            lead_user_ids = _strict_optional_practice_ids(
                values,
                block_id="leads_block",
                action_id="lead_ids",
            )
            wanted_user_ids = set(coach_user_ids) | set(lead_user_ids)
            existing_user_ids = (
                {
                    item.id
                    for item in db.session.query(User).filter(
                        User.id.in_(wanted_user_ids)
                    ).all()
                }
                if wanted_user_ids
                else set()
            )
            if existing_user_ids != wanted_user_ids:
                raise ValueError("Unknown selected coach or lead")
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Invalid practice Full Edit values: %s", exc)
            ack(response_action="errors", errors={
                "location_block": (
                    "Something went wrong reading the form. Please try again."
                )
            })
            return None
        except Exception:
            db.session.rollback()
            logger.exception(
                "Could not validate practice Full Edit location and people"
            )
            ack(response_action="errors", errors={
                _practice_submission_error_block(
                    view,
                    "location_block",
                ): "Could not validate practice details. Please try again."
            })
            return None

        had_root = bool(practice.slack_message_ts)
        previous_date = practice.date
        previous_location_id = practice.location_id
        previous_plan_reactions = [
            dict(item) for item in (practice.plan_reactions or [])
        ]

        try:
            if location_id is not None:
                practice.location_id = location_id
            practice.workout_description = authoring["workout_description"]
            practice.logistics_notes = authoring["logistics_notes"] or None
            practice.plan_reactions = plan_reactions
            practice.is_dark_practice = "is_dark_practice" in flag_values
            if "has_social" not in flag_values:
                practice.social_location_id = None

            if "coaches_block" in values:
                PracticeLead.query.filter_by(
                    practice_id=practice.id, role="coach"
                ).delete()
                for user_id_value in coach_user_ids:
                    db.session.add(PracticeLead(
                        practice_id=practice.id,
                        user_id=user_id_value,
                        role="coach",
                    ))

            if "leads_block" in values:
                PracticeLead.query.filter_by(
                    practice_id=practice.id, role="lead"
                ).delete()
                for user_id_value in lead_user_ids:
                    db.session.add(PracticeLead(
                        practice_id=practice.id,
                        user_id=user_id_value,
                        role="lead",
                    ))

            practice.activities = list(selected_sources.activities)
            practice.practice_types = list(selected_sources.practice_types)
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("Practice %s Full Edit failed to save", practice_id)
            ack(response_action="errors", errors={
                "location_block": (
                    "Could not save practice changes. Please try again."
                )
            })
            return {
                "success": False,
                "practice_updated": False,
                "error": "Could not save practice changes. Please try again.",
            }
        logger.info(f"Practice {practice_id} fully updated by {user_id}")
        ack()
        post_save_work = lambda: _run_practice_edit_full_post_save(
            practice_id=practice_id,
            user_id=user_id,
            should_notify=should_notify,
            had_root=had_root,
            previous_date=previous_date,
            previous_location_id=previous_location_id,
            previous_plan_reactions=previous_plan_reactions,
            client=client,
            logger=logger,
        )
        if post_save_dispatcher is not None:
            post_save_dispatcher(post_save_work)
            return {"success": True, "practice_updated": True}
        return post_save_work()


def _load_modal_ref_data():
    """Load reference data for practice modal dropdowns.

    Returns:
        Tuple of (locations, all_activities, all_types) where each is a list of (id, name) tuples.
    """
    from app.practices.models import PracticeLocation, PracticeActivity, PracticeType
    locations = [
        (l.id, f"{l.name} - {l.spot}" if l.spot else l.name)
        for l in PracticeLocation.query.order_by(PracticeLocation.name).all()
    ]
    all_activities = [
        (a.id, a.name) for a in PracticeActivity.query.order_by(PracticeActivity.name).all()
    ]
    all_types = [
        (t.id, t.name) for t in PracticeType.query.order_by(PracticeType.name).all()
    ]
    return locations, all_activities, all_types


def _load_eligible_people():
    """Load eligible coaches and leads for practice modal pickers.

    Returns:
        Tuple of (eligible_coaches, eligible_leads), each a list of
        (user_id, "First Last", slack_uid) tuples for Slack-linked users only.
    """
    from app.models import Tag, User
    coach_tag_ids = [t.id for t in Tag.query.filter(
        Tag.name.in_(['HEAD_COACH', 'ASSISTANT_COACH'])).all()]
    lead_tag_ids = [t.id for t in Tag.query.filter(
        Tag.name.in_(['PRACTICES_LEAD'])).all()]

    def _people(tag_ids):
        return [
            (u.id, f"{u.first_name} {u.last_name}", u.slack_user.slack_uid)
            for u in User.query.filter(User.tags.any(Tag.id.in_(tag_ids)))
            .order_by(User.first_name).all()
            if u.slack_user and u.slack_user.slack_uid
        ]

    return _people(coach_tag_ids), _people(lead_tag_ids)


def _post_practice_create_updates(client, channel_id, message_ts, practice_date,
                                  user_id, confirm_text):
    """Refresh the weekly coach-summary post and post a confirmation.

    Runs in a background thread (see handle_practice_create_submission) so the
    slow Slack API calls stay off the view_submission request path and the ack
    returns within Slack's ~3s limit. All work is best-effort.
    """
    from datetime import timedelta
    from app.practices.models import Practice
    from app.practices.service import convert_practice_to_info
    from app.models import AppConfig
    from app.slack.blocks import build_coach_weekly_summary_blocks

    with get_app_context():
        if channel_id and message_ts:
            try:
                # Week starts on Monday
                days_since_monday = practice_date.weekday()
                week_start = (practice_date - timedelta(days=days_since_monday)).replace(
                    hour=0, minute=0, second=0, microsecond=0)
                week_end = week_start + timedelta(days=7)

                practices = Practice.query.filter(
                    Practice.date >= week_start,
                    Practice.date < week_end,
                ).order_by(Practice.date).all()

                expected_days = AppConfig.get('practice_days', [
                    {"day": "tuesday", "time": "18:00", "active": True},
                    {"day": "thursday", "time": "18:00", "active": True},
                    {"day": "saturday", "time": "09:00", "active": True},
                ])

                practice_infos = [convert_practice_to_info(p) for p in practices]
                blocks = build_coach_weekly_summary_blocks(practice_infos, expected_days, week_start)

                client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    blocks=blocks,
                    text=f"Coach Review: Week of {week_start.strftime('%B %-d')}",
                )
                logger.info(f"Updated summary post in {channel_id}")
            except Exception as e:
                logger.error(f"Failed to update summary post: {e}")

        if channel_id:
            try:
                client.chat_postEphemeral(channel=channel_id, user=user_id, text=confirm_text)
            except Exception as e:
                logger.warning(f"Could not send ephemeral confirmation: {e}")


def _delegate_reaction_event(event, *, removed):
    """Validate one Bolt reaction envelope and delegate attendance routing."""
    item = event.get("item", {})
    if item.get("type") != "message":
        return
    from app.slack.practices.reactions import handle_attendance_reaction

    with get_app_context():
        return handle_attendance_reaction(
            channel=item.get("channel"),
            message_ts=item.get("ts"),
            reaction=event.get("reaction"),
            slack_user_id=event.get("user"),
            removed=removed,
        )


def _handle_reaction_removed(event):
    return _delegate_reaction_event(event, removed=True)


def _process_rsvp(practice_id: int, status: str, user_id: str, user_name: str) -> dict:
    """Process an RSVP for a practice."""
    from app.models import db, User
    from app.practices.models import Practice, PracticeRSVP
    from app.practices.interfaces import RSVPStatus
    from app.slack.practices import update_practice_rsvp_counts, log_rsvp_action

    # Validate status
    valid_statuses = {RSVPStatus.GOING.value, RSVPStatus.NOT_GOING.value, RSVPStatus.MAYBE.value}
    if status not in valid_statuses:
        return {"success": False, "error": f"Invalid status: {status}"}

    practice = Practice.query.get(practice_id)
    if not practice:
        return {"success": False, "error": "Practice not found"}

    user = User.query.join(User.slack_user).filter_by(slack_uid=user_id).first()

    if not user:
        return {
            "success": False,
            "error": "Your Slack account is not linked to a TCSC membership. Please contact an admin."
        }

    rsvp = PracticeRSVP.query.filter_by(
        practice_id=practice_id,
        user_id=user.id
    ).first()

    toggled_off = False
    if rsvp:
        if rsvp.status == status:
            # Toggle off - delete the RSVP if clicking same status
            db.session.delete(rsvp)
            toggled_off = True
        else:
            # Change to new status
            rsvp.status = status
            rsvp.responded_at = datetime.utcnow()
    else:
        rsvp = PracticeRSVP(
            practice_id=practice_id,
            user_id=user.id,
            status=status,
            slack_user_id=user_id,
            responded_at=datetime.utcnow()
        )
        db.session.add(rsvp)

    db.session.commit()

    try:
        update_practice_rsvp_counts(practice)
    except Exception as e:
        logger.warning(f"Could not update RSVP counts: {e}")

    # Log RSVP action to #tcsc-logging
    try:
        log_action = 'removed' if toggled_off else 'going'
        log_rsvp_action(practice, user_id, log_action)
    except Exception as e:
        logger.warning(f"Could not log RSVP action: {e}")

    return {"success": True, "toggled_off": toggled_off}


def _process_rsvp_with_notes(practice_id: int, status: str, user_id: str, notes: str) -> dict:
    """Process an RSVP with notes."""
    from app.models import db, User
    from app.practices.models import Practice, PracticeRSVP
    from app.practices.interfaces import RSVPStatus
    from app.slack.practices import update_practice_rsvp_counts, log_rsvp_action

    # Validate status
    valid_statuses = {RSVPStatus.GOING.value, RSVPStatus.NOT_GOING.value, RSVPStatus.MAYBE.value}
    if status not in valid_statuses:
        return {"success": False, "error": f"Invalid status: {status}"}

    practice = Practice.query.get(practice_id)
    if not practice:
        return {"success": False, "error": "Practice not found"}

    user = User.query.join(User.slack_user).filter_by(slack_uid=user_id).first()

    if not user:
        return {
            "success": False,
            "error": "Your Slack account is not linked to a TCSC membership. Please contact an admin."
        }

    rsvp = PracticeRSVP.query.filter_by(
        practice_id=practice_id,
        user_id=user.id
    ).first()

    if rsvp:
        rsvp.status = status
        rsvp.notes = notes
        rsvp.responded_at = datetime.utcnow()
    else:
        rsvp = PracticeRSVP(
            practice_id=practice_id,
            user_id=user.id,
            status=status,
            slack_user_id=user_id,
            notes=notes,
            responded_at=datetime.utcnow()
        )
        db.session.add(rsvp)

    db.session.commit()

    # Update the main message going count
    try:
        update_practice_rsvp_counts(practice)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not update RSVP counts: {e}")

    # Log RSVP action to #tcsc-logging
    try:
        log_action = 'going' if status == 'going' else 'removed'
        log_rsvp_action(practice, user_id, log_action)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not log RSVP action: {e}")

    return {"success": True}


def _cancellation_decision_feedback(result, approved):
    if result.get("success") is True:
        decision = "approved" if approved else "rejected"
        return f"Decision recorded. Cancellation {decision}."
    if result.get("practice_cancelled") is True:
        return (
            ":warning: Cancellation was saved, but the Slack announcement "
            "was not updated. Retry the announcement refresh."
        )
    known_errors = {
        "Proposal not found": (
            "Cancellation proposal not found. No decision was recorded."
        ),
        "Already decided": (
            "Cancellation proposal was already decided. No new decision was "
            "recorded."
        ),
    }
    return known_errors.get(
        result.get("error"),
        "Cancellation decision was not recorded: "
        f"{result.get('error') or 'Unknown error'}",
    )


def _handle_cancellation_decision_action(ack, body, action, client):
    """Process one cancellation action and report its actual outcome."""
    ack()
    user_id = body["user"]["id"]
    user_name = body["user"].get("name", "Unknown")
    approved = action["action_id"] == "cancellation_approve"
    proposal_id = int(action["value"])

    with get_app_context():
        result = _process_cancellation_decision(
            proposal_id,
            approved,
            user_id,
            user_name,
        )

    channel_id = body.get("channel", {}).get("id")
    if channel_id:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=_cancellation_decision_feedback(result, approved),
        )
    return result


def _process_cancellation_decision(
    proposal_id: int,
    approved: bool,
    user_id: str,
    user_name: str
) -> dict:
    """Process cancellation approval/rejection."""
    from app.models import db, User
    from app.practices.models import CancellationRequest, Practice
    from app.practices.interfaces import CancellationStatus, PracticeStatus
    proposal = CancellationRequest.query.get(proposal_id)
    if not proposal:
        return {"success": False, "error": "Proposal not found"}

    if proposal.status != CancellationStatus.PENDING.value:
        return {"success": False, "error": "Already decided"}

    proposal.status = CancellationStatus.APPROVED.value if approved else CancellationStatus.REJECTED.value
    proposal.decided_at = datetime.utcnow()
    proposal.decided_by_slack_uid = user_id

    user = User.query.join(User.slack_user).filter_by(slack_uid=user_id).first()
    if user:
        proposal.decided_by_user_id = user.id

    practice = proposal.practice
    had_root = bool(practice.slack_message_ts)
    if approved:
        practice.status = PracticeStatus.CANCELLED.value
        practice.cancellation_reason = proposal.reason_summary

    db.session.commit()

    if approved:
        from app.slack.practices import refresh_practice_posts
        try:
            refresh_results = refresh_practice_posts(
                practice,
                change_type='cancel',
                actor_slack_id=user_id,
            )
        except Exception as exc:
            refresh_results = {
                "announcement": {"success": False, "error": str(exc)},
            }
        announcement = (refresh_results or {}).get("announcement") or {}
        if had_root and announcement.get("success") is not True:
            return {
                "success": False,
                "practice_cancelled": True,
                "error": (
                    "Practice was cancelled, but its Slack announcement did "
                    "not update"
                ),
                "refresh_results": refresh_results,
            }
        return {
            "success": True,
            "practice_cancelled": True,
            "refresh_results": refresh_results,
        }

    return {"success": True, "practice_cancelled": False}


def _process_lead_confirmation(practice_id: int, confirmed: bool, slack_user_id: str) -> dict:
    """Process lead confirmation or substitution request."""
    from app.models import db, User
    from app.practices.models import Practice, PracticeLead
    from app.slack.practices import post_substitution_request

    practice = Practice.query.get(practice_id)
    if not practice:
        return {"success": False, "error": "Practice not found"}

    user = User.query.join(User.slack_user).filter_by(slack_uid=slack_user_id).first()
    if not user:
        return {"success": False, "error": "User not found"}

    lead_assignment = PracticeLead.query.filter_by(
        practice_id=practice_id,
        user_id=user.id
    ).first()

    if not lead_assignment:
        return {"success": False, "error": "Lead assignment not found"}

    if confirmed:
        lead_assignment.confirmed = True
        lead_assignment.confirmed_at = datetime.utcnow()
        db.session.commit()

        from app.slack.practices import refresh_practice_posts
        refresh_practice_posts(practice, change_type='edit')

        return {"success": True, "message": "Confirmed"}
    else:
        result = post_substitution_request(
            practice,
            slack_user_id,
            "Lead indicated they cannot make it (reason not provided)"
        )
        return result


def get_flask_handler():
    """Get the Flask request handler for the Bolt app.

    Returns None if Bolt is not configured (missing SLACK_BOT_TOKEN).
    """
    return handler


def is_bolt_enabled():
    """Check if Bolt app is enabled and configured."""
    return bolt_app is not None


def is_socket_mode_available():
    """Check if Socket Mode is available (SLACK_APP_TOKEN is set)."""
    return socket_mode_handler is not None


def is_socket_mode_running():
    """Check if Socket Mode is currently running."""
    return _socket_mode_started


def start_socket_mode(flask_app=None):
    """Start Socket Mode connection in a background thread.

    Socket Mode allows the app to receive events via WebSocket,
    eliminating the need for a public URL during local development.

    Args:
        flask_app: Flask application instance for context in handlers.
                   Required for handlers that access the database.

    Returns True if started successfully, False if not available or already running.
    """
    global _socket_mode_started

    if flask_app is not None:
        bind_flask_app(flask_app)

    if not socket_mode_handler:
        logger.warning("Socket Mode not available - SLACK_APP_TOKEN not set")
        return False

    if _socket_mode_started:
        logger.info("Socket Mode already running")
        return True

    def run_socket_mode():
        global _socket_mode_started
        try:
            logger.info("Starting Socket Mode connection...")
            _socket_mode_started = True
            socket_mode_handler.start()
        except Exception as e:
            logger.error(f"Socket Mode error: {e}")
            _socket_mode_started = False

    # Start in background thread so it doesn't block Flask
    thread = threading.Thread(target=run_socket_mode, daemon=True)
    thread.start()
    logger.info("Socket Mode started in background thread")
    return True


def get_app_context():
    """Get Flask app context for use in Bolt background workers.

    Returns a context manager that can be used with 'with' statement.
    Falls back to no-op if Flask app is not available.
    """
    if _flask_app:
        return _flask_app.app_context()
    # Fallback: try to get current_app (works in HTTP mode)
    try:
        from flask import current_app
        return current_app.app_context()
    except RuntimeError:
        # No app context available, return a no-op context manager
        from contextlib import nullcontext
        return nullcontext()


def stop_socket_mode():
    """Stop the Socket Mode connection."""
    global _socket_mode_started

    if socket_mode_handler and _socket_mode_started:
        try:
            socket_mode_handler.close()
            _socket_mode_started = False
            logger.info("Socket Mode stopped")
        except Exception as e:
            logger.error(f"Error stopping Socket Mode: {e}")
