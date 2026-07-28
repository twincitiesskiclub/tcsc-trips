import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

from app import create_app
from scripts.ui_audit.session_cookie import AUDIT_ADMIN_EMAIL, mint_admin_cookie

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_real_dotenv_cannot_leak_into_the_audit_process():
    """The .env.uiaudit enumeration is a snapshot, not the safety mechanism.

    app/config.py's load_stripe_config() calls load_dotenv(find_dotenv()) with
    override=False *inside* create_app() -- after serve.py's own override=True
    load of .env.uiaudit. override=False only fills in keys that aren't
    already set, so any key the real .env defines that .env.uiaudit's list
    doesn't happen to cover would otherwise be silently backfilled with the
    real value the moment someone adds it. scripts/ui_audit/serve.py closes
    this for any call resolved through find_dotenv() by monkeypatching both
    dotenv.find_dotenv (the package-level re-export app/config.py's pattern
    uses) and dotenv.main.find_dotenv (the separate binding a *bare*
    load_dotenv() resolves against internally -- see
    test_bare_load_dotenv_also_cannot_discover_the_real_dotenv below). This
    does not make every conceivable way to reach a file safe -- an explicit
    hardcoded path would still work -- only calls that go through find_dotenv().

    This test doesn't hardcode which keys .env.uiaudit covers -- it reads
    whatever the real .env contains right now and proves none of those values
    reach the audit process, so it keeps catching the failure mode even after
    the real .env grows a key nobody thought to fake. Runs create_app() in a
    subprocess (via serve.py, so the same guard + dotenv-load + find_dotenv
    patch path main() uses runs first) rather than in-process, since a
    successful run mutates os.environ and monkeypatches dotenv module-wide --
    side effects that must not leak into the rest of the suite.
    """
    real_env_path = REPO_ROOT / ".env"
    if not real_env_path.exists():
        pytest.skip("no real .env in this checkout (fresh clone) -- nothing to leak")

    real_values = {k: v for k, v in dotenv_values(real_env_path).items() if v is not None}
    if not real_values:
        pytest.skip("real .env has no keys to test against")

    probe = (
        "import json, os\n"
        "from scripts.ui_audit.serve import create_app\n"
        "create_app()\n"
        "print(json.dumps(dict(os.environ)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    audit_environ = json.loads(result.stdout.strip().splitlines()[-1])

    leaked = {
        key: value
        for key, value in real_values.items()
        if audit_environ.get(key) == value
        # Excludes a key that already matched in *this* process's ambient
        # environment before the subprocess ran -- that would be a pre-existing
        # coincidence, not something serve.py leaked.
        and os.environ.get(key) != value
    }
    assert not leaked, (
        f"real .env values leaked into the audit process for: {sorted(leaked)} -- "
        "the find_dotenv patch in scripts/ui_audit/serve.py has a gap"
    )


def test_bare_load_dotenv_also_cannot_discover_the_real_dotenv():
    """A distinct code path from test_real_dotenv_cannot_leak_into_the_audit_process
    above -- this one exists because that test alone missed a real gap.

    dotenv.main.load_dotenv(), when called with no arguments, resolves its
    path via a *bare* find_dotenv() call inside its own function body. Because
    that name is a free variable, Python looks it up in dotenv.main's own
    module globals at call time -- a binding entirely separate from
    dotenv.find_dotenv, the package-level re-export that
    `from dotenv import find_dotenv` (app/config.py's pattern) picks up.
    Patching only the package-level name leaves this bare-call path free to
    find the real .env. Nothing in the app currently calls load_dotenv() bare,
    but app/config.py's load_dotenv(find_dotenv()) looks redundant to a casual
    reader, and a future "simplification" -- or any new module entering the
    app's import chain with a bare load_dotenv() -- would reopen it silently.

    This test calls the bare form directly, independent of whatever
    app/config.py happens to do today, so it keeps covering the mechanism
    even if create_app()'s own call sites change.
    """
    real_env_path = REPO_ROOT / ".env"
    if not real_env_path.exists():
        pytest.skip("no real .env in this checkout (fresh clone) -- nothing to leak")

    real_values = {k: v for k, v in dotenv_values(real_env_path).items() if v is not None}
    if not real_values:
        pytest.skip("real .env has no keys to test against")

    probe = (
        "import json, os\n"
        "from scripts.ui_audit.serve import create_app\n"  # runs the guard/env/patch setup
        "import dotenv\n"
        "dotenv.load_dotenv()\n"  # the exact bare call a reviewer caught leaking
        "print(json.dumps(dict(os.environ)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    audit_environ = json.loads(result.stdout.strip().splitlines()[-1])

    leaked = {
        key: value
        for key, value in real_values.items()
        if audit_environ.get(key) == value
        and os.environ.get(key) != value
    }
    assert not leaked, (
        f"a bare load_dotenv() call leaked real .env values into the audit "
        f"process for: {sorted(leaked)} -- dotenv.main.find_dotenv is not "
        "patched in scripts/ui_audit/serve.py"
    )
