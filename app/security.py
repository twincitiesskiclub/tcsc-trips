"""Application security defaults shared by every Flask response."""

import os
from datetime import timedelta

from flask import jsonify, request
from flask_wtf.csrf import CSRFError, CSRFProtect


csrf = CSRFProtect()


_PUBLIC_CSP = (
    "default-src 'self'; "
    "base-uri 'none'; "
    "connect-src 'self'; "
    "font-src 'self' data:; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "frame-src 'none'; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'"
)

_PAYMENT_CSP = (
    "default-src 'self'; "
    "base-uri 'none'; "
    "connect-src 'self' https://api.stripe.com https://*.stripe.com "
    "https://*.stripe.network https://link.com https://*.link.com "
    "https://maps.googleapis.com; "
    "font-src 'self' data:; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "frame-src https://js.stripe.com https://*.js.stripe.com "
    "https://hooks.stripe.com https://link.com https://*.link.com; "
    "img-src 'self' data: https://*.stripe.com; "
    "object-src 'none'; "
    "script-src 'self' https://js.stripe.com https://*.js.stripe.com "
    "https://maps.googleapis.com; "
    "style-src 'self' 'unsafe-inline'"
)

# Admin templates still contain inline scripts and handlers. Keeping this
# compatibility allowance is safer than deploying a policy that silently
# breaks mutations; the external/eval-based Alpine dependency is removed.
_ADMIN_CSP = (
    "default-src 'self'; "
    "base-uri 'none'; "
    "connect-src 'self'; "
    "font-src 'self' data:; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "frame-src 'none'; "
    "img-src 'self' data: https://staticmap.openstreetmap.de; "
    "object-src 'none'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'"
)

_PAYMENT_PAGE_ENDPOINTS = {
    "registration.season_register",
    "socials.get_social_event_page",
    "trips.get_trip_page",
}


def _is_production(environment):
    """Recognize both the app setting and Render's built-in environment flag."""
    return environment == "production" or os.getenv("RENDER", "").lower() == "true"


def init_security(app, environment):
    """Configure cookies, CSRF protection, and browser response headers."""
    production = _is_production(environment)

    app.config.update(
        SESSION_COOKIE_SECURE=production,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        WTF_CSRF_CHECK_DEFAULT=False,
        WTF_CSRF_TIME_LIMIT=12 * 60 * 60,
        WTF_CSRF_SSL_STRICT=True,
    )
    csrf.init_app(app)

    @app.before_request
    def protect_state_changing_requests():
        # Existing unit tests exercise route behavior without managing browser
        # sessions. Dedicated security tests keep TESTING false and verify CSRF.
        if app.testing or not app.config.get("WTF_CSRF_ENABLED", True):
            return None
        return csrf.protect(apply_exemptions=True)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        message = "Your session expired or the security token was missing. Refresh and try again."
        if request.is_json or request.accept_mimetypes.best == "application/json":
            return jsonify({"error": message}), 400
        return message, 400, {"Content-Type": "text/plain; charset=utf-8"}

    @app.after_request
    def add_security_headers(response):
        if request.path.startswith("/admin"):
            csp = _ADMIN_CSP
        elif request.endpoint in _PAYMENT_PAGE_ENDPOINTS:
            csp = _PAYMENT_CSP
        else:
            csp = _PUBLIC_CSP

        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response
