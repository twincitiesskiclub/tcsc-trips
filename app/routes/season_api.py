"""Public season API consumed by the marketing site.

Returns registration windows as timestamps and no computed open/closed state.
The marketing site is a static build: a state decided here would be baked into
HTML and keep being served after the window boundary it described had passed.
The site re-derives state in the browser from these timestamps instead.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from app.models import Season
from app.routes.marketing_cors import apply_marketing_cors
from app.seasons.payload import build_season_payload

bp = Blueprint('season_api', __name__, url_prefix='/api')

_CACHE_MAX_AGE_SECONDS = 300


def _all_seasons():
    """Seam for tests, which cover shaping without seeding rows."""
    return Season.query.all()


@bp.route('/season', methods=['GET'])
def get_season():
    body = build_season_payload(_all_seasons(), datetime.utcnow())
    resp = jsonify(body)
    apply_marketing_cors(resp, request.headers.get('Origin', ''))
    resp.headers['Cache-Control'] = f'public, max-age={_CACHE_MAX_AGE_SECONDS}'
    return resp
