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

import os
import logging
import threading
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Initialize Bolt app with signing secret for request verification
_bot_token = os.environ.get("SLACK_BOT_TOKEN")
_app_token = os.environ.get("SLACK_APP_TOKEN")  # For Socket Mode (xapp-...)
_signing_secret = os.environ.get("SLACK_SIGNING_SECRET")

# Module-level variables
bolt_app = None
handler = None  # HTTP handler (for production)
socket_mode_handler = None  # Socket Mode handler (for local dev)
_socket_mode_started = False
_flask_app = None  # Reference to Flask app for Socket Mode context

# Only initialize Bolt if we have the required token
# This allows the app to start without Slack credentials (e.g., for migrations)
if _bot_token:
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
    # Slash Commands
    # =========================================================================

    @bolt_app.command("/tcsc")
    def handle_tcsc_command(ack, command, client, logger):
        """Handle /tcsc slash command."""
        ack()

        from app.slack.commands import handle_tcsc_command as process_command

        command_text = command.get("text", "")
        user_id = command.get("user_id", "")
        user_name = command.get("user_name", "")

        with get_app_context():
            response = process_command(command_text, user_id, user_name)

        client.chat_postEphemeral(
            channel=command["channel_id"],
            user=user_id,
            text=response.get("text", ""),
            blocks=response.get("blocks")
        )

    # =========================================================================
    # Block Actions (Button Clicks)
    # =========================================================================

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
        ack()

        user_id = body["user"]["id"]
        user_name = body["user"].get("name", "Unknown")
        action_id = action["action_id"]
        proposal_id = int(action["value"])
        approved = (action_id == "cancellation_approve")

        with get_app_context():
            result = _process_cancellation_decision(proposal_id, approved, user_id, user_name)

        decision_text = "approved" if approved else "rejected"
        channel_id = body.get("channel", {}).get("id")
        if channel_id:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"Decision recorded. Cancellation {decision_text}."
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
            from app.practices.models import Practice, PracticeLocation
            from app.practices.service import convert_practice_to_info
            from app.slack.modals import build_practice_edit_full_modal

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

            # Convert to PracticeInfo and build modal
            practice_info = convert_practice_to_info(practice)
            modal = build_practice_edit_full_modal(practice_info, locations=locations)

            # Open the modal
            client.views_open(trigger_id=trigger_id, view=modal)

    # =========================================================================
    # View Submissions (Modal Forms)
    # =========================================================================

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
            warmup = _safe_get(values, "warmup_block", "warmup_description", "value", default="")
            workout = _safe_get(values, "workout_block", "workout_description", "value", default="")
            cooldown = _safe_get(values, "cooldown_block", "cooldown_description", "value", default="")

            if date_value:
                practice.date = datetime.fromtimestamp(date_value)
                practice.day_of_week = practice.date.strftime("%A")

            practice.warmup_description = warmup
            practice.workout_description = workout
            practice.cooldown_description = cooldown

            db.session.commit()
            logger.info(f"Practice {practice_id} updated by {user_id}")

    @bolt_app.view("practice_edit_full")
    def handle_practice_edit_full_submission(ack, body, view, client, logger):
        """Handle full practice edit modal submission from collab channel.

        Updates practice details, then updates both #practices and collab posts,
        and adds thread replies noting who updated.
        """
        ack()

        user_id = body["user"]["id"]
        practice_id = int(view.get("private_metadata") or "0")
        values = _safe_get(view, "state", "values", default={})

        with get_app_context():
            from app.practices.models import Practice
            from app.models import db
            from app.slack.practices import (
                update_practice_post,
                update_collab_post,
                log_practice_edit,
                log_collab_edit
            )

            practice = Practice.query.get(practice_id)
            if not practice:
                logger.error(f"Practice {practice_id} not found")
                return

            # Extract form values
            # Location is a dropdown (static_select)
            location_id = _safe_get(values, "location_block", "location_id", "selected_option", "value")
            warmup = _safe_get(values, "warmup_block", "warmup_description", "value", default="")
            workout = _safe_get(values, "workout_block", "workout_description", "value", default="")
            cooldown = _safe_get(values, "cooldown_block", "cooldown_description", "value", default="")

            # Extract checkbox flags
            selected_flags = _safe_get(values, "flags_block", "practice_flags", "selected_options", default=[])
            flag_values = [opt.get("value") for opt in selected_flags]
            is_dark_practice = "is_dark_practice" in flag_values
            has_social = "has_social" in flag_values

            # Update database
            if location_id:
                practice.location_id = int(location_id)
            practice.warmup_description = warmup
            practice.workout_description = workout
            practice.cooldown_description = cooldown
            practice.is_dark_practice = is_dark_practice
            practice.has_social = has_social

            db.session.commit()
            logger.info(f"Practice {practice_id} fully updated by {user_id}")

            # Update the #practices post
            if practice.slack_message_ts:
                try:
                    update_practice_post(practice)
                    log_practice_edit(practice, user_id)
                except Exception as e:
                    logger.warning(f"Could not update #practices post: {e}")

            # Update the collab post
            if practice.slack_collab_message_ts:
                try:
                    update_collab_post(practice)
                    log_collab_edit(practice, user_id)
                except Exception as e:
                    logger.warning(f"Could not update collab post: {e}")

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

            warmup = _safe_get(values, "warmup_block", "warmup_description", "value", default="")
            workout = _safe_get(values, "workout_block", "workout_description", "value", default="")
            cooldown = _safe_get(values, "cooldown_block", "cooldown_description", "value", default="")
            notes = _safe_get(values, "notes_block", "workout_notes", "value", default="")

            practice.warmup_description = warmup
            practice.workout_description = workout
            practice.cooldown_description = cooldown

            if notes:
                if practice.workout_description:
                    practice.workout_description += f"\n\n**Notes:** {notes}"
                else:
                    practice.workout_description = f"**Notes:** {notes}"

            practice.status = PracticeStatus.CONFIRMED.value

            db.session.commit()
            logger.info(f"Workout posted for practice {practice_id} by {user_id}")

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
    def handle_reaction_added(event, client, logger):
        """Handle emoji reaction as RSVP."""
        reaction = event.get("reaction")
        user_id = event.get("user")
        item = event.get("item", {})

        if item.get("type") != "message":
            return

        channel = item.get("channel")
        message_ts = item.get("ts")

        reaction_map = {
            "white_check_mark": "going",
            "+1": "going",
            "thumbsup": "going",
            "heavy_check_mark": "going",
            "raised_hands": "going",
            "muscle": "going",
            "ski": "going",
            "skier": "going",
            "question": "maybe",
            "thinking_face": "maybe",
            "shrug": "maybe",
            "x": "not_going",
            "-1": "not_going",
            "thumbsdown": "not_going",
        }

        status = reaction_map.get(reaction)
        if not status:
            return

        with get_app_context():
            _process_reaction_rsvp(channel, message_ts, status, user_id)

    @bolt_app.event("message")
    def handle_message_events(body, logger):
        """Handle message events (including DMs)."""
        pass

else:
    logger.warning("SLACK_BOT_TOKEN not set - Slack Bolt app disabled")


# =============================================================================
# Helper Functions (always defined)
# =============================================================================

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


def _process_rsvp(practice_id: int, status: str, user_id: str, user_name: str) -> dict:
    """Process an RSVP for a practice."""
    from app.models import db, User
    from app.practices.models import Practice, PracticeRSVP
    from app.practices.interfaces import RSVPStatus
    from app.slack.practices import update_practice_rsvp_counts, update_going_list_thread, log_rsvp_action

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

    # Update the going list thread reply
    try:
        update_going_list_thread(practice)
    except Exception as e:
        logger.warning(f"Could not update going list thread: {e}")

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
    from app.slack.practices import update_going_list_thread, update_practice_rsvp_counts, log_rsvp_action

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

    # Update the going list thread reply
    try:
        update_going_list_thread(practice)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not update going list thread: {e}")

    # Log RSVP action to #tcsc-logging
    try:
        log_action = 'going' if status == 'going' else 'removed'
        log_rsvp_action(practice, user_id, log_action)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not log RSVP action: {e}")

    return {"success": True}


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
    from app.slack.practices import update_cancellation_decision, post_cancellation_notice

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
    if approved:
        practice.status = PracticeStatus.CANCELLED.value
        practice.cancellation_reason = proposal.reason_summary

    db.session.commit()

    decided_by_name = f"<@{user_id}>"
    update_cancellation_decision(proposal, approved, decided_by_name)

    if approved:
        post_cancellation_notice(practice)

    return {"success": True}


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
        return {"success": True, "message": "Confirmed"}
    else:
        result = post_substitution_request(
            practice,
            slack_user_id,
            "Lead indicated they cannot make it (reason not provided)"
        )
        return result


def _process_reaction_rsvp(channel: str, message_ts: str, status: str, user_id: str):
    """Process emoji reaction as RSVP."""
    from app.models import db, User
    from app.practices.models import Practice, PracticeRSVP
    from app.slack.practices import update_practice_rsvp_counts, update_going_list_thread

    practice = Practice.query.filter_by(
        slack_message_ts=message_ts,
        slack_channel_id=channel
    ).first()

    if not practice:
        return

    user = User.query.join(User.slack_user).filter_by(slack_uid=user_id).first()

    if not user:
        # User's Slack account is not linked - silently ignore reaction RSVPs
        # (no way to send error message for reaction events)
        logger.debug(f"Ignoring reaction RSVP from unlinked user {user_id}")
        return

    rsvp = PracticeRSVP.query.filter_by(
        practice_id=practice.id,
        user_id=user.id
    ).first()

    if rsvp:
        rsvp.status = status
        rsvp.responded_at = datetime.utcnow()
    else:
        rsvp = PracticeRSVP(
            practice_id=practice.id,
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
        logger.warning(f"Could not update RSVP counts after reaction: {e}")

    # Update the going list thread reply
    try:
        update_going_list_thread(practice)
    except Exception as e:
        logger.warning(f"Could not update going list thread after reaction: {e}")

    logger.info(f"RSVP via reaction: {user_id} -> {status} for practice #{practice.id}")


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
    global _socket_mode_started, _flask_app

    if not socket_mode_handler:
        logger.warning("Socket Mode not available - SLACK_APP_TOKEN not set")
        return False

    if _socket_mode_started:
        logger.info("Socket Mode already running")
        return True

    # Store Flask app reference for handlers
    if flask_app:
        _flask_app = flask_app

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
    """Get Flask app context for use in Socket Mode handlers.

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
