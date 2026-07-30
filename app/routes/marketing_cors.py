"""CORS policy shared by every public endpoint the marketing site consumes.

Lived privately in ``conditions.py`` until the season API needed the same
allowlist. Two copies of an origin allowlist is one copy too many: adding a
staging origin to one and not the other fails silently and only in a browser.
"""
from __future__ import annotations

from flask import current_app

ALLOWED_ORIGINS = {
    'https://twincitiesskiclub.org',
    'https://www.twincitiesskiclub.org',
    # Staging origin (Render Static service for the marketing site). The
    # conditions strip shows "Conditions unavailable" on staging until this
    # Flask side deploys; with this origin allowlisted it then works there too.
    'https://tcsc-marketing.onrender.com',
}


def origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    if origin in ALLOWED_ORIGINS:
        return True
    # Astro dev server (e.g. http://localhost:4321), debug/development only.
    if current_app.debug and origin.startswith('http://localhost:'):
        return True
    return False


def apply_marketing_cors(resp, origin: str):
    """Always vary on Origin so shared caches never serve an ACAO-bearing
    response to a different origin."""
    resp.headers['Vary'] = 'Origin'
    if origin_allowed(origin):
        resp.headers['Access-Control-Allow-Origin'] = origin
    return resp
