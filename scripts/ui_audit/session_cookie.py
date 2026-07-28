"""Mint a signed Flask session granting admin access, without OAuth.

app/auth.py:admin_required accepts any session whose user email is on
ALLOWED_EMAIL_DOMAIN. Flask session cookies are itsdangerous-signed with
SECRET_KEY, which the audit environment controls, so a valid admin session can
be produced offline.

This exists instead of a dev-login route on purpose: a route is application code
that can reach production, however carefully it is guarded. A cookie signed with
a local-only key cannot.
"""

from flask import Flask
from flask.sessions import SecureCookieSessionInterface

AUDIT_ADMIN_EMAIL = "ui-audit@twincitiesskiclub.org"


def mint_admin_cookie(app: Flask) -> tuple[str, str]:
    """Return (cookie_name, cookie_value) for an authenticated admin session."""
    serializer = SecureCookieSessionInterface().get_signing_serializer(app)
    if serializer is None:
        raise RuntimeError("SECRET_KEY is not set; cannot sign a session cookie")

    value = serializer.dumps(
        {
            "user": {
                "email": AUDIT_ADMIN_EMAIL,
                "name": "UI Audit",
            }
        }
    )
    return app.config.get("SESSION_COOKIE_NAME") or "session", value
