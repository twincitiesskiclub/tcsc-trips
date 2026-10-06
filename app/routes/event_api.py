"""Public event API consumed by the marketing site.

Returns one event per series (selection in app/events/selection.py) as
timestamps and public facts. The registration link is a path, not a URL:
the app has no ProxyFix, so url_for(_external=True) can say http:// behind
Render. The site resolves the path against the API's own origin.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, abort, jsonify, request, url_for

from app.events.models import Event
from app.events.public_payload import serialize_public_event
from app.events.selection import select_public_event
from app.routes.marketing_cors import apply_marketing_cors
from app.seasons.payload import _iso

bp = Blueprint("event_api", __name__, url_prefix="/api")

SERIES = {"dry-tri": "dry_tri"}
_CACHE_MAX_AGE_SECONDS = 300


def _all_events():
    """Seam for tests, which cover shaping without seeding rows."""
    return Event.query.all()


@bp.route("/events/<series>", methods=["GET"])
def get_event_series(series):
    template_key = SERIES.get(series)
    if template_key is None:
        abort(404)
    now = datetime.utcnow()
    event = select_public_event(_all_events(), template_key, now)
    body = {
        "generated_at": _iso(now),
        "event": (
            serialize_public_event(
                event, url_for("events.get_event_page", slug=event.slug)
            )
            if event is not None
            else None
        ),
    }
    resp = jsonify(body)
    apply_marketing_cors(resp, request.headers.get("Origin", ""))
    resp.headers["Cache-Control"] = f"public, max-age={_CACHE_MAX_AGE_SECONDS}"
    return resp
