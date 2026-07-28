from app import create_app
from scripts.ui_audit.session_cookie import AUDIT_ADMIN_EMAIL, mint_admin_cookie


def test_minted_cookie_grants_admin_access(monkeypatch):
    monkeypatch.setenv("TCSC_MIGRATION_ONLY", "1")
    app = create_app()
    app.config["SECRET_KEY"] = "ui-audit-test-key"

    name, value = mint_admin_cookie(app)
    assert name == "session"

    client = app.test_client()
    client.set_cookie(name, value, domain="localhost")
    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 200, (
        f"expected the minted session to reach the admin dashboard, "
        f"got {response.status_code} -> {response.headers.get('Location')}"
    )


def test_email_is_on_the_allowed_domain():
    from app.constants import ALLOWED_EMAIL_DOMAIN

    assert AUDIT_ADMIN_EMAIL.endswith(ALLOWED_EMAIL_DOMAIN)


def test_without_the_cookie_admin_redirects_to_login(monkeypatch):
    monkeypatch.setenv("TCSC_MIGRATION_ONLY", "1")
    app = create_app()
    app.config["SECRET_KEY"] = "ui-audit-test-key"

    response = app.test_client().get("/admin", follow_redirects=False)
    assert response.status_code == 302
