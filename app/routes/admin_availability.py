"""Admin fallback for two-week lead blocks.

The main path is the block post in #collab-coaches-practices. This page lists
recent blocks, offers Open poll on an unopened one, and can run the block job
by hand (useful on deploy day).
"""

from flask import Blueprint, jsonify

from ..auth import admin_required
from ..practices.availability import block_practices
from ..practices.availability_models import LeadAvailabilityPoll
from ..practices.blocks import open_block_poll, run_block_job

admin_availability_bp = Blueprint(
    "admin_availability", __name__, url_prefix="/admin/availability")


@admin_availability_bp.route("/")
@admin_required
def dashboard():
    polls = LeadAvailabilityPoll.query.order_by(
        LeadAvailabilityPoll.starts_on.desc()).limit(6).all()
    return jsonify({"polls": [{
        "id": p.id,
        "starts_on": p.starts_on.isoformat(),
        "ends_on": p.ends_on.isoformat(),
        "status": p.status,
        "sessions": len(block_practices(p.starts_on, p.ends_on)),
        "posted": bool(p.message_ts),
    } for p in polls]})


@admin_availability_bp.route("/polls/<int:poll_id>/open", methods=["POST"])
@admin_required
def open_poll_route(poll_id):
    result = open_block_poll(poll_id, None)
    if not result.get("success"):
        # Surfaced verbatim: names the exact missing emoji or Slack error.
        return jsonify({"error": result.get("error", "could not open poll")}), 400
    return jsonify(result)


@admin_availability_bp.route("/block-job/run", methods=["POST"])
@admin_required
def run_block_job_route():
    results = run_block_job()
    return jsonify({"results": [{k: str(v) for k, v in r.items()} for r in results]})
