"""Admin endpoints for lead availability polls.

Shadow mode is read from `AppConfig` (not a config file) specifically so the
club can leave shadow mode without a deploy. It only governs poll *creation*:
`build_poll(..., is_shadow=...)` bakes the target channel onto the poll at
that moment (see `app.practices.availability._target_channel`), so a poll
created while shadow mode is on always opens against the shadow channel,
regardless of whatever the config flag says later when someone opens it.
"""

from datetime import date

from flask import Blueprint, current_app, jsonify, request

from ..auth import admin_required
from ..models import AppConfig
from ..practices.availability import PollNotReadyError, build_poll, open_poll
from ..practices.availability_emoji import EmojiSupplyError
from ..practices.availability_models import LeadAvailabilityPoll
from ..practices.publishing import publish_blockers, publish_practices

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
            # A closed poll whose practices are still drafts is the failure this
            # surfaces: availability was collected, leads were assigned, and
            # nobody ever sent the block live. Both counts are shown because
            # "2 unpublished, 0 publishable" is a different problem from
            # "2 unpublished, 2 publishable" -- the first needs details filled
            # in, the second just needs the button.
            **_publish_counts(p),
        } for p in polls],
    })


def _poll_practices(poll):
    """The Practice rows a poll covers, in poll order."""
    return [
        mapping.practice for mapping in poll.practices
        if mapping.practice is not None
    ]


def _publish_counts(poll) -> dict:
    practices = _poll_practices(poll)
    drafts = [p for p in practices if p.is_draft]
    return {
        "unpublished": len(drafts),
        "publishable": sum(1 for p in drafts if not publish_blockers(p)),
    }


@admin_availability_bp.route("/polls/<int:poll_id>/publish", methods=["POST"])
@admin_required
def publish_poll_block(poll_id):
    """Send this block's practices live — the one human publish gate.

    The poll is the unit because it is the batch the director already thinks
    in: one block of practices goes out to the leads for availability, gets its
    leads assigned, and then goes live together.

    Deliberately not tied to the coming week. The Sunday evening flow (weekly
    summary + the announcement job, both reading published_practices()) already
    puts the coming week in front of members with no human in the loop, and
    gating that on a click would break a workflow that works. A block is
    published weeks before any of its practices reach their own Sunday.

    Partial success is normal and reported rather than raised: a block with one
    practice still missing its location should send the other eleven, and name
    the one it held back.
    """
    poll = LeadAvailabilityPoll.query.get_or_404(poll_id)
    practices = _poll_practices(poll)
    if not practices:
        return jsonify({"error": f"poll #{poll_id} covers no practices"}), 400

    result = publish_practices(practices)
    current_app.logger.info(
        "Poll %s publish by admin: %d published, %d skipped",
        poll_id, len(result["published"]), len(result["skipped"]),
    )
    return jsonify(result)


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
