"""Mint a signed Flask session granting admin access, without OAuth.

app/auth.py:admin_required accepts any session whose user email is on
ALLOWED_EMAIL_DOMAIN. Flask session cookies are itsdangerous-signed with
SECRET_KEY, which the audit environment controls, so a valid admin session can
be produced offline.

This exists instead of a dev-login route on purpose: a route is application code
that can reach production, however carefully it is guarded. A cookie signed with
a local-only key cannot.
"""

import os

from flask import Flask
from flask.sessions import SecureCookieSessionInterface

from app.constants import ALLOWED_EMAIL_DOMAIN

# Finance authorisation is an email allowlist hardcoded in app code
# (app/routes/admin.py:FINANCE_AUTHORIZED_EMAILS). With any other address every
# payment amount, the bulk sum and the drawer's currency rows render as an em
# dash, so the spacing of populated currency cells could never be audited.
# Minting the session as one of those addresses is the only way to reach that UI
# without editing application code or mutating payment rows.
DEFAULT_AUDIT_ADMIN_EMAIL = "admin@twincitiesskiclub.org"

# ...but the payments page has TWO shapes, and the finance-authorised one is the
# one fewer admins see: only two addresses are on that allowlist. The non-finance
# variant is structurally different, not a text swap -- admin_payments.js omits
# the bulk-bar sum element entirely when canViewAmounts is false (one child
# fewer in .pw-modal-summary), and payments.html gives .pw-row-amount
# min-width:72px at desktop but min-width:0 below 768px, so the em-dash rows are
# narrower on mobile. Both shapes have to be auditable, so the identity is an
# override rather than a constant, and the audit takes a second labelled pass as
# a non-finance admin. See scripts/ui_audit/run.sh for the invocation.
AUDIT_EMAIL_ENV_VAR = "TCSC_UI_AUDIT_EMAIL"


def audit_admin_email() -> str:
    """The admin identity to mint a session for, honouring the env override.

    Read at call time, not import time, so the same process/module can be used
    for either pass and so a test can set it without reloading the module.
    """
    email = (os.environ.get(AUDIT_EMAIL_ENV_VAR) or "").strip() or DEFAULT_AUDIT_ADMIN_EMAIL
    if not email.lower().endswith(ALLOWED_EMAIL_DOMAIN):
        # app/auth.py:admin_required gates on the domain. An address outside it
        # mints a cookie that silently bounces every capture to /login, and the
        # run would only fail deep into the first surface.
        raise ValueError(
            f"{AUDIT_EMAIL_ENV_VAR}={email!r} is not on {ALLOWED_EMAIL_DOMAIN}; "
            "the minted session would not be admitted to /admin"
        )
    return email


def mint_admin_cookie(app: Flask) -> tuple[str, str]:
    """Return (cookie_name, cookie_value) for an authenticated admin session."""
    serializer = SecureCookieSessionInterface().get_signing_serializer(app)
    if serializer is None:
        raise RuntimeError("SECRET_KEY is not set; cannot sign a session cookie")

    value = serializer.dumps(
        {
            "user": {
                "email": audit_admin_email(),
                "name": "UI Audit",
            }
        }
    )
    return app.config.get("SESSION_COOKIE_NAME") or "session", value
