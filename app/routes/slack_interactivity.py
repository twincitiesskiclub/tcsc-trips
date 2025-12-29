"""Slack interactivity webhook endpoints using Slack Bolt.

This module provides Flask endpoints that delegate to the Slack Bolt app
for handling all Slack interactions (events, commands, interactions).

Bolt handles:
- Request signature verification
- Event parsing and routing
- Acknowledgement of requests
"""

from flask import Blueprint, request, jsonify

from app.slack.bolt_app import get_flask_handler, is_bolt_enabled

slack_bp = Blueprint('slack', __name__, url_prefix='/slack')

# Get the handler at module load time so Bolt initializes at startup
_handler = get_flask_handler()


def _handle_request():
    """Handle a Slack request, returning 503 if Bolt is not configured."""
    if _handler is None:
        return jsonify({"error": "Slack integration not configured"}), 503
    return _handler.handle(request)


@slack_bp.route('/events', methods=['POST'])
def slack_events():
    """Handle Slack Event API callbacks.

    Delegates to Bolt app which handles:
    - URL verification challenge
    - app_home_opened events
    - reaction_added events
    - message events
    """
    return _handle_request()


@slack_bp.route('/commands', methods=['POST'])
def slack_commands():
    """Handle Slack slash commands.

    Delegates to Bolt app which handles:
    - /tcsc command and subcommands
    """
    return _handle_request()


@slack_bp.route('/interactions', methods=['POST'])
def slack_interactions():
    """Handle Slack interactive components.

    Delegates to Bolt app which handles:
    - Button clicks (block_actions)
    - Modal submissions (view_submission)
    - Shortcuts
    """
    return _handle_request()


@slack_bp.route('/options', methods=['POST'])
def slack_options():
    """Handle Slack dynamic select options.

    Delegates to Bolt app for handling external select menus.
    """
    return _handle_request()
