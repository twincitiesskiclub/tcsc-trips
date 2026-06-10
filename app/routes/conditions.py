"""Public conditions API consumed by the marketing site."""
from __future__ import annotations

import logging
import time
from threading import Lock, Thread

from flask import Blueprint, current_app, jsonify, request

from app.conditions.service import build_conditions_response

logger = logging.getLogger(__name__)

bp = Blueprint('conditions', __name__, url_prefix='/api')

_CACHE_TTL_SECONDS = 300
_RETRY_TTL_SECONDS = 60

_ALLOWED_ORIGINS = {
    'https://twincitiesskiclub.org',
    'https://www.twincitiesskiclub.org',
    # Staging origin (Render Static service for the marketing site). The
    # conditions strip shows "Conditions unavailable" on staging until this
    # Flask side deploys; with this origin allowlisted it then works there too.
    'https://tcsc-marketing.onrender.com',
}

# Cached payload plus rebuild bookkeeping. Requests never block on a refresh:
# an expired body is served as-is while a daemon thread rebuilds it (same
# daemon-thread pattern this repo uses for post-ack Slack work), so a hanging
# upstream cannot tie up gunicorn workers. Only a true cold start (no body at
# all) builds synchronously.
_cache: dict[str, object] = {'body': None, 'expires_at': 0}
_rebuilding = False
_rebuild_thread: Thread | None = None
_lock = Lock()


def _store_rebuild_result(body: dict | None) -> None:
    """Swap a rebuild result into the cache without clobbering good data."""
    global _rebuilding
    with _lock:
        now = time.time()
        if body is not None and 'error' not in body:
            _cache['body'] = body
            _cache['expires_at'] = now + _CACHE_TTL_SECONDS
        else:
            # Failed rebuild: keep the last good body and retry sooner than
            # the full TTL. An error body is only stored when no good body
            # exists (cold start straight into an outage).
            current = _cache['body']
            if body is not None and (current is None or 'error' in current):
                _cache['body'] = body
            _cache['expires_at'] = now + _RETRY_TTL_SECONDS
        _rebuilding = False


def _rebuild_cache() -> None:
    """Build a fresh body and swap it in. Safe to run off-request."""
    try:
        body = build_conditions_response()
    except Exception:
        logger.exception("Conditions cache rebuild failed")
        body = None
    _store_rebuild_result(body)


def _get_response_body() -> dict:
    """Return the cached body, refreshing in the background when expired."""
    global _rebuilding, _rebuild_thread
    cold_build = False
    with _lock:
        body = _cache['body']
        if body is not None:
            if time.time() >= _cache['expires_at'] and not _rebuilding:
                _rebuilding = True
                _rebuild_thread = Thread(target=_rebuild_cache, daemon=True)
                _rebuild_thread.start()
            # Serve immediately, even when stale; the daemon thread swaps in
            # fresh data for later requests.
            return body
        if not _rebuilding:
            _rebuilding = True
            cold_build = True
    if not cold_build:
        # Rare race: another request is building the first body. Build a
        # throwaway copy rather than blocking on the other build.
        return build_conditions_response()
    _rebuild_cache()
    with _lock:
        body = _cache['body']
    if body is not None:
        return body
    # Defensive: build raised and nothing was cached.
    return {'updated_at': None, 'locations': [], 'error': 'upstream unavailable'}


def _origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    if origin in _ALLOWED_ORIGINS:
        return True
    # Astro dev server (e.g. http://localhost:4321), debug/development only
    if current_app.debug and origin.startswith('http://localhost:'):
        return True
    return False


@bp.route('/conditions', methods=['GET'])
def get_conditions():
    body = _get_response_body()
    resp = jsonify(body)
    # Always vary on Origin so shared caches never serve an ACAO-bearing
    # response to a different origin.
    resp.headers['Vary'] = 'Origin'
    origin = request.headers.get('Origin', '')
    if _origin_allowed(origin):
        resp.headers['Access-Control-Allow-Origin'] = origin
    resp.headers['Cache-Control'] = f'public, max-age={_CACHE_TTL_SECONDS}'
    return resp
