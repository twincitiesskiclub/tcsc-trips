"""Admin endpoints for lead availability polls.

Shadow mode is read from `AppConfig` (not a config file) specifically so the
club can leave shadow mode without a deploy. It only governs poll *creation*:
`build_poll(..., is_shadow=...)` bakes the target channel onto the poll at
that moment (see `app.practices.availability._target_channel`), so a poll
created while shadow mode is on always opens against the shadow channel,
regardless of whatever the config flag says later when someone opens it.
"""

from datetime import date

from flask import Blueprint, jsonify, request

from ..auth import admin_required
from ..models import AppConfig
from ..practices.availability import PollNotReadyError, build_poll, open_poll
from ..practices.availability_emoji import EmojiSupplyError
from ..practices.availability_models import LeadAvailabilityPoll

admin_availability_bp = Blueprint(
    "admin_availability", __name__, url_prefix="/admin/availability")


def _shadow_mode() -> bool:
    # Defaults to True (shadow ON) with no config row -- the rollout plan is
    # a shadow month first, and there is no UI that writes this key, so an
    # unset key must resolve to the safe channel. An explicit `False` row is
    # a deliberate act, not the out-of-the-box behavior of every environment.
    return bool(AppConfig.get("lead_availability.shadow_mode", True))


@admin_availability_bp.route("/")
@admin_required
def dashboard():
    polls = LeadAvailabilityPoll.query.order_by(
        LeadAvailabilityPoll.created_at.desc()).limit(10).all()
    return jsonify({
        "shadow_mode": _shadow_mode(),
        "polls": [{
            "id": p.id,
            "starts_on": p.starts_on.isoformat(),
            "ends_on": p.ends_on.isoformat(),
            "status": p.status,
            "is_shadow": p.is_shadow,
            "sessions": len(p.practices),
        } for p in polls],
    })


@admin_availability_bp.route("/polls/create", methods=["POST"])
@admin_required
def create_poll():
    data = request.get_json() or {}
    try:
        starts_on = date.fromisoformat(data["starts_on"])
        ends_on = date.fromisoformat(data["ends_on"])
    except (KeyError, ValueError):
        return jsonify({"error": "starts_on and ends_on must be YYYY-MM-DD"}), 400

    try:
        poll = build_poll(starts_on, ends_on, is_shadow=_shadow_mode())
    except PollNotReadyError as exc:
        # Surfaced verbatim: the director needs to know which practice to fix.
        return jsonify({"error": str(exc)}), 400
    except EmojiSupplyError as exc:
        # A range with more sessions than there are configured letter emoji is
        # bad input, not a server fault -- and the message names the two real
        # fixes (add letters, or split the block), so it has to reach the
        # director rather than becoming an opaque 500.
        return jsonify({"error": str(exc)}), 400

    # channel_id/is_shadow are surfaced so the admin UI can name the target
    # channel in a confirmation step before the caller hits /open and
    # actually posts -- see app/static/admin_practices.js's
    # openAvailabilityPoll().
    return jsonify({
        "success": True,
        "poll_id": poll.id,
        "channel_id": poll.channel_id,
        "is_shadow": poll.is_shadow,
    })


@admin_availability_bp.route("/polls/<int:poll_id>/open", methods=["POST"])
@admin_required
def open_poll_route(poll_id):
    poll = LeadAvailabilityPoll.query.get_or_404(poll_id)
    result = open_poll(poll)
    if not result.get("success"):
        # Surfaced verbatim: names the exact missing emoji or Slack error.
        return jsonify({"error": result.get("error", "could not open poll")}), 400
    return jsonify(result)
