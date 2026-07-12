"""Regression tests for the Flask browser-security baseline."""

import re

import pytest
from flask import Blueprint, Flask, jsonify, render_template_string

from app import create_app
from app.security import csrf, init_security


def build_security_app(environment="production"):
    app = Flask(__name__)
    app.secret_key = "security-test-secret"
    init_security(app, environment)

    @app.get("/token")
    def token():
        return render_template_string("{{ csrf_meta_tag() }}")

    @app.post("/mutate")
    def mutate():
        return jsonify({"ok": True})

    @app.post("/signed-webhook")
    @csrf.exempt
    def signed_webhook():
        return jsonify({"ok": True})

    trips = Blueprint("trips", __name__)

    @trips.get("/trip")
    def get_trip_page():
        return "trip"

    app.register_blueprint(trips)

    @app.get("/admin/example")
    def admin_example():
        return "admin"

    return app


def csrf_token_from(response):
    match = re.search(rb'name="csrf-token" content="([^"]+)"', response.data)
    assert match, response.data
    return match.group(1).decode()


def test_production_headers_and_cookie_defaults():
    app = build_security_app()
    client = app.test_client()

    response = client.get("/token", base_url="https://tcsc.test")

    assert response.headers["Strict-Transport-Security"] == "max-age=31536000"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    cookie = response.headers["Set-Cookie"]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert app.permanent_session_lifetime.total_seconds() == 12 * 60 * 60
    assert app.config["WTF_CSRF_TIME_LIMIT"] == 12 * 60 * 60


def test_development_omits_hsts_and_secure_cookie():
    app = build_security_app("development")
    response = app.test_client().get("/token")

    assert "Strict-Transport-Security" not in response.headers
    assert "Secure" not in response.headers["Set-Cookie"]
    assert "SameSite=Lax" in response.headers["Set-Cookie"]


def test_csrf_rejects_missing_token_and_accepts_header_token():
    app = build_security_app()
    client = app.test_client()
    base_url = "https://tcsc.test"

    missing = client.post("/mutate", json={}, base_url=base_url)
    assert missing.status_code == 400
    assert "security token" in missing.get_json()["error"]

    token = csrf_token_from(client.get("/token", base_url=base_url))
    accepted = client.post(
        "/mutate",
        json={},
        base_url=base_url,
        headers={
            "X-CSRFToken": token,
            "Referer": f"{base_url}/token",
        },
    )
    assert accepted.status_code == 200


def test_signed_webhook_can_be_narrowly_exempted():
    app = build_security_app()
    response = app.test_client().post("/signed-webhook", json={})
    assert response.status_code == 200


def test_csp_is_strict_publicly_and_stripe_compatible_on_payment_pages():
    app = build_security_app()
    client = app.test_client()

    public_csp = client.get("/token").headers["Content-Security-Policy"]
    assert "script-src 'self'" in public_csp
    public_script_policy = public_csp.split("script-src", 1)[1].split(";", 1)[0]
    assert "'unsafe-inline'" not in public_script_policy

    payment_csp = client.get("/trip").headers["Content-Security-Policy"]
    assert "https://js.stripe.com" in payment_csp
    assert "https://hooks.stripe.com" in payment_csp

    admin_csp = client.get("/admin/example").headers["Content-Security-Policy"]
    assert "script-src 'self' 'unsafe-inline'" in admin_csp
    assert "'unsafe-eval'" not in admin_csp
    assert "cdn.jsdelivr.net" not in admin_csp


def test_create_app_fails_fast_without_session_secret(monkeypatch):
    monkeypatch.setattr("app.load_stripe_config", lambda: None)
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="FLASK_SECRET_KEY"):
        create_app()
