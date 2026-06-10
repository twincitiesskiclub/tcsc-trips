"""Public conditions API consumed by the marketing site."""
from __future__ import annotations
import time
from threading import Lock
from flask import Blueprint, jsonify, request, current_app

from app.conditions.service import build_conditions_response

bp = Blueprint('conditions', __name__, url_prefix='/api')

_CACHE_TTL_SECONDS = 300
_ALLOWED_ORIGIN = 'https://twincitiesskiclub.org'

_cache: dict[str, object] = {'expires_at': 0, 'body': None}
_lock = Lock()


def _get_cached_response() -> dict:
    now = time.time()
    if _cache['body'] is None or now >= _cache['expires_at']:
        with _lock:
            if _cache['body'] is None or now >= _cache['expires_at']:
                _cache['body'] = build_conditions_response()
                _cache['expires_at'] = now + _CACHE_TTL_SECONDS
    return _cache['body']  # type: ignore[return-value]


@bp.route('/conditions', methods=['GET'])
def get_conditions():
    body = _get_cached_response()
    resp = jsonify(body)
    origin = request.headers.get('Origin', '')
    if origin == _ALLOWED_ORIGIN or current_app.config.get('CONDITIONS_CORS_ALLOW_ANY'):
        resp.headers['Access-Control-Allow-Origin'] = origin or _ALLOWED_ORIGIN
        resp.headers['Vary'] = 'Origin'
    resp.headers['Cache-Control'] = f'public, max-age={_CACHE_TTL_SECONDS}'
    return resp
