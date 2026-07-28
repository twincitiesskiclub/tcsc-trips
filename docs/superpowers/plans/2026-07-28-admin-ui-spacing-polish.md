# Admin UI Spacing & Padding Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove accumulated spacing drift across every admin surface by introducing a spacing scale and shared component classes, verified by before/after screenshots at three viewports.

**Architecture:** Build a screenshot harness that runs the real app against a seeded database with an offline-minted admin session and four independent layers preventing outbound traffic. Capture every admin route and interactive state, triage into a findings inventory, then fix in two layers — a CSS custom-property spacing scale, then shared classes replacing hand-rolled markup — applied one surface group at a time, each its own PR.

**Tech Stack:** Flask + Jinja2, Tailwind CSS 3.4, vanilla JS (no framework), PostgreSQL 18 in Docker, Playwright 1.62 (Node, global install), Codex CLI (`gpt-5.6-sol`).

## Global Constraints

- **Polish, not redesign.** No color changes, no type-scale changes, no layout restructuring, no new components or features. If a fix requires an element to move to a different place on the page, flag it for the user instead of doing it.
- **Nothing may be sent outbound.** No Slack messages, no Stripe calls, no email, under any circumstance.
- **No production credentials anywhere in this project.** Verification is local-only.
- **No PII on the dev box.** Production is read for orientation only; no rows are copied to disk.
- **Never push to `main`.** Render auto-deploys every commit on `main`. All work lands via PR from `admin-ui-spacing-polish`.
- **Never add a dev-login route to app code.** Admin auth is bypassed only by an offline-signed cookie, never by a code path that could ship.
- Python venv is `.venv-linux/` (the repo's `env/` is Mac-only).
- Postgres is the Docker container `tcsc-postgres`, database `tcsc_trips`, user/password `tcsc`/`tcsc`.
- Node Playwright is a global install; scripts need `NODE_PATH=$(npm root -g)`.
- Spacing scale steps are exactly: `--admin-space-1: 4px`, `-2: 8px`, `-3: 12px`, `-4: 16px`, `-5: 24px`, `-6: 32px`.

**Branch:** all work happens on `admin-ui-spacing-polish` (already created, holds the design doc).

---

## Codex Execution Model

Tasks 9–13 (the five surface-group fix passes) are performed by **Codex agents, not by hand**. Each group is dispatched to its own `codex exec` run at `gpt-5.6-sol` / `model_reasoning_effort=max`.

**Every Codex invocation in this plan uses exactly:**

```
codex exec -m gpt-5.6-sol -c model_reasoning_effort="max"
```

The user's `~/.codex/config.toml` sets `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`, so these runs edit files unattended with no prompts. Three rules follow from that:

1. **Each agent gets its own git worktree.** The five groups touch disjoint file sets, but a runaway agent editing shared files would corrupt a sibling's work. Worktrees make that impossible rather than unlikely.
2. **Each agent is told, in its prompt, exactly which files it may modify** and that `app/static/css/admin_ui.css` is read-only to it. Task 8 owns that file; agents consume the scale, they never extend it.
3. **No agent commits or opens a PR.** Each leaves a dirty worktree. The diff is reviewed, re-captured, and committed by the orchestrator. A bad run is then discarded with `git checkout .` rather than reverted from history.

**Parallelism:** all five can run concurrently once Task 8 has merged, since their file sets are disjoint and each has its own worktree. Task 8 is a hard barrier — every agent depends on the scale existing.

**Worktree setup, run once before Task 9:**

```bash
cd /workspace/tcsc-trips
for group in members payments slack practices catalog; do
  git worktree add ".worktrees/ui-$group" admin-ui-spacing-polish
done
git worktree list
```

**Shared prompt preamble** — every agent prompt in Tasks 9–13 begins with this block verbatim:

```
You are polishing spacing and padding in the TCSC admin UI. This is a polish
pass, NOT a redesign.

HARD RULES:
- Change ONLY spacing and padding: margin, padding, gap, and the spacing-related
  Tailwind utilities (m-*, p-*, gap-*, space-*).
- Do NOT change colors, font sizes, font weights, borders, or layout structure.
- Do NOT move any element to a different position on the page.
- Do NOT add features, refactor logic, or rename anything.
- app/static/css/admin_ui.css is READ-ONLY to you. Use the variables it defines;
  never add, edit, or remove one. If a fix seems to need a value not on the
  scale, leave that finding unfixed and report it instead.
- Do NOT run git commit, git add, or gh. Leave your changes uncommitted.

The spacing scale available to you (defined in app/static/css/admin_ui.css):
  --admin-space-1: 4px    --admin-space-4: 16px
  --admin-space-2: 8px    --admin-space-5: 24px
  --admin-space-3: 12px   --admin-space-6: 32px
  --admin-field-gap (16px), --admin-row-gap (8px),
  --admin-section-gap (24px), --admin-drawer-pad (24px)

Shared component classes available to you (also defined there):
  .admin-ui-form-row, .admin-ui-field-group, .admin-ui-section, .admin-ui-btn-row

Prefer replacing hand-rolled inline spacing with these classes. Where a raw
value is unavoidable, use a var(--admin-space-N) reference, never a bare pixel
value.

When done, output a plain list of every change: file, line, what changed, and
which finding number it addresses. Then list any finding you could NOT fix
within these rules, and why.
```

---

### Task 1: Outbound safety guard

The guard blocks at the socket layer rather than per-library, so it holds for any client — `slack_sdk`, `stripe`, `smtplib`, `requests`, or anything added later. Library-specific patches are layered on top only to produce a clearer error message.

**Files:**
- Create: `scripts/ui_audit/__init__.py`
- Create: `scripts/ui_audit/outbound_guard.py`
- Test: `tests/test_ui_audit_outbound_guard.py`

**Interfaces:**
- Produces: `install_outbound_guard() -> None`, `OutboundBlocked(RuntimeError)`. Both importable from `scripts.ui_audit.outbound_guard`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_audit_outbound_guard.py
import socket
import pytest

from scripts.ui_audit.outbound_guard import OutboundBlocked, install_outbound_guard


@pytest.fixture(autouse=True)
def guard():
    install_outbound_guard()


def test_external_connection_is_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(OutboundBlocked):
        s.connect(("slack.com", 443))


def test_external_connect_ex_is_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(OutboundBlocked):
        s.connect_ex(("api.stripe.com", 443))


def test_loopback_is_allowed():
    """The database and the app server itself must still be reachable."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))  # must not raise
    client.close()
    server.close()


def test_slack_client_raises_named_error():
    from slack_sdk import WebClient

    with pytest.raises(OutboundBlocked) as exc:
        WebClient(token="xoxb-fake").auth_test()
    assert "Slack" in str(exc.value)


def test_smtplib_is_blocked():
    import smtplib

    with pytest.raises(OutboundBlocked):
        smtplib.SMTP("smtp.gmail.com", 587)


def test_install_is_idempotent():
    """Installing twice must not double-wrap and must still allow loopback."""
    install_outbound_guard()
    install_outbound_guard()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    client.close()
    server.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-linux/bin/python -m pytest tests/test_ui_audit_outbound_guard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.ui_audit'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/ui_audit/__init__.py
```
(empty file)

```python
# scripts/ui_audit/outbound_guard.py
"""Hard block on outbound network traffic for the UI audit server.

The admin UI has buttons that send Slack messages to the whole club and capture
Stripe payments. The screenshot harness must never be able to fire one, so this
blocks at the socket layer -- below every HTTP client -- rather than trying to
enumerate the libraries that might reach outward.

Loopback stays open because the app server and PostgreSQL are both local.
"""

import ipaddress
import socket

_INSTALLED = False


class OutboundBlocked(RuntimeError):
    """Raised when code under the UI audit harness attempts to reach the network."""


def _is_loopback(address) -> bool:
    """True when the connect target is on this machine."""
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    if host in ("localhost", "", None):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # A hostname that is not a bare IP literal. Do not resolve it -- resolving
        # is itself a network call, and any non-loopback name is blocked anyway.
        return False


def install_outbound_guard() -> None:
    """Patch sockets, Slack, and SMTP so outbound traffic raises immediately.

    Idempotent: calling more than once will not double-wrap the socket methods.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded_connect(self, address, *args, **kwargs):
        if not _is_loopback(address):
            raise OutboundBlocked(
                f"UI audit harness blocked an outbound connection to {address!r}"
            )
        return real_connect(self, address, *args, **kwargs)

    def guarded_connect_ex(self, address, *args, **kwargs):
        if not _is_loopback(address):
            raise OutboundBlocked(
                f"UI audit harness blocked an outbound connection to {address!r}"
            )
        return real_connect_ex(self, address, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex

    # Named errors for the two clients that would do member-visible damage.
    try:
        from slack_sdk.web.client import WebClient

        def blocked_slack(*args, **kwargs):
            raise OutboundBlocked(
                "UI audit harness blocked a Slack API call. No message was sent."
            )

        WebClient.api_call = blocked_slack
    except ImportError:
        pass

    import smtplib

    def blocked_smtp(*args, **kwargs):
        raise OutboundBlocked("UI audit harness blocked an SMTP connection.")

    smtplib.SMTP.__init__ = blocked_smtp
    smtplib.SMTP_SSL.__init__ = blocked_smtp
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv-linux/bin/python -m pytest tests/test_ui_audit_outbound_guard.py -v`
Expected: PASS, 6 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/ui_audit/__init__.py scripts/ui_audit/outbound_guard.py tests/test_ui_audit_outbound_guard.py
git commit -m "feat(ui-audit): block all outbound network traffic at the socket layer"
```

---

### Task 2: Audit server with an offline-minted admin session

`admin_required` (`app/auth.py:34`) checks only that `session['user']['email']` ends with `@twincitiesskiclub.org`. Flask signs sessions with `SECRET_KEY`, which is controlled locally, so a valid session is mintable offline. This deliberately avoids adding a login route to app code.

**Files:**
- Create: `scripts/ui_audit/session_cookie.py`
- Create: `scripts/ui_audit/serve.py`
- Create: `.env.uiaudit`
- Test: `tests/test_ui_audit_session_cookie.py`

**Interfaces:**
- Consumes: `install_outbound_guard()` from Task 1.
- Produces: `mint_admin_cookie(app) -> tuple[str, str]` returning `(cookie_name, cookie_value)`; `AUDIT_ADMIN_EMAIL = "ui-audit@twincitiesskiclub.org"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_audit_session_cookie.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-linux/bin/python -m pytest tests/test_ui_audit_session_cookie.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.ui_audit.session_cookie'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/ui_audit/session_cookie.py
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
```

```python
# scripts/ui_audit/serve.py
"""Run the app for screenshot capture with outbound traffic sealed off.

Usage:
    .venv-linux/bin/python -m scripts.ui_audit.serve [port]

Prints the admin session cookie as JSON on the first line so the capture runner
can inject it, then serves until interrupted.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from scripts.ui_audit.outbound_guard import install_outbound_guard

# Order matters: the guard is installed before the app is imported so that no
# import-time client can open a connection.
install_outbound_guard()

# The audit env deliberately replaces the real .env -- real tokens are never
# loaded into this process.
load_dotenv(Path(__file__).resolve().parents[2] / ".env.uiaudit", override=True)
os.environ["TCSC_MIGRATION_ONLY"] = "1"  # no APScheduler, no Slack Socket Mode

from app import create_app  # noqa: E402  (must follow the guard + env load)
from scripts.ui_audit.session_cookie import mint_admin_cookie  # noqa: E402


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5055
    app = create_app()
    name, value = mint_admin_cookie(app)
    print(json.dumps({"cookie_name": name, "cookie_value": value, "port": port}), flush=True)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
```

```bash
# .env.uiaudit
# Screenshot-audit environment. Contains NO real credentials by design --
# every outbound value is a deliberate fake, and scripts/ui_audit/outbound_guard.py
# blocks the network regardless.
SECRET_KEY=ui-audit-local-only-not-a-secret
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips
TCSC_MIGRATION_ONLY=1
SLACK_BOT_TOKEN=xoxb-FAKE-ui-audit
SLACK_ADMIN_TOKEN=xoxc-FAKE-ui-audit
SLACK_SIGNING_SECRET=FAKE-ui-audit
STRIPE_SECRET_KEY=sk_test_FAKE_ui_audit
STRIPE_PUBLISHABLE_KEY=pk_test_FAKE_ui_audit
STRIPE_WEBHOOK_SECRET=whsec_FAKE_ui_audit
GOOGLE_CLIENT_ID=fake-ui-audit
GOOGLE_CLIENT_SECRET=fake-ui-audit
```

- [ ] **Step 4: Add `.env.uiaudit` to gitignore, then run the test**

```bash
echo ".env.uiaudit" >> .gitignore
echo ".ui-audit/" >> .gitignore
.venv-linux/bin/python -m pytest tests/test_ui_audit_session_cookie.py -v
```
Expected: PASS, 3 passed

- [ ] **Step 5: Verify the server boots and serves admin**

```bash
npm run tailwind:build
.venv-linux/bin/python -m scripts.ui_audit.serve 5055 &
sleep 4
COOKIE=$(.venv-linux/bin/python -c "
import json,urllib.request
print('placeholder')" )
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5055/admin
```
Expected: `302` (no cookie sent — confirms the route is actually protected). The authenticated 200 is proven by the test in Step 4 and again by the capture runner in Task 6.

- [ ] **Step 6: Commit**

```bash
git add scripts/ui_audit/session_cookie.py scripts/ui_audit/serve.py tests/test_ui_audit_session_cookie.py .gitignore
git commit -m "feat(ui-audit): serve admin locally with an offline-minted session"
```

---

### Task 3: Production orientation query

Read-only, aggregates only. The purpose is knowing which panes render populated and which enum states actually occur, so the seed does not produce screenshots of empty tables or states the club never uses.

**Files:**
- Create: `scripts/ui_audit/survey_prod.py`
- Create (output, gitignored): `.ui-audit/prod-shape.json`

**Interfaces:**
- Produces: `.ui-audit/prod-shape.json` with `{"row_counts": {table: int}, "enums": {"users.status": {value: count}, ...}}`, consumed by Task 4 and Task 5 to pick seed volumes.

- [ ] **Step 1: Write the survey script**

```python
# scripts/ui_audit/survey_prod.py
"""Read production for orientation only -- counts and enum distributions.

No rows, no identifying values, nothing written to disk beyond aggregates.
The output tells the seed script which surfaces need to be populated and at
what volume so no admin pane renders empty during capture.

Usage:
    .venv-linux/bin/python -m scripts.ui_audit.survey_prod
"""

import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
load_dotenv(REPO / ".env")

TABLES = [
    "users", "seasons", "user_seasons", "payments", "trips", "tags", "user_tags",
    "events", "event_registrations", "event_price_options", "event_participants",
    "practices", "practice_leads", "practice_rsvps", "practice_locations",
    "practice_activities", "practice_types", "cancellation_requests",
    "newsletters", "newsletter_prompts", "newsletter_submissions",
    "lead_availability_polls", "lead_availability_responses",
    "slack_users", "status_changes",
]

ENUM_COLUMNS = [
    ("users", "status"),
    ("user_seasons", "status"),
    ("payments", "status"),
    ("payments", "payment_type"),
    ("trips", "status"),
    ("events", "status"),
    ("event_registrations", "status"),
    ("practices", "status"),
]


def main() -> None:
    url = os.environ["PROD_DATABASE_URL"]
    out = {"row_counts": {}, "enums": {}}

    with psycopg2.connect(url, connect_timeout=20, sslmode="require") as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            for table in TABLES:
                try:
                    cur.execute(f'SELECT count(*) FROM "{table}"')
                    out["row_counts"][table] = cur.fetchone()[0]
                except psycopg2.Error:
                    conn.rollback()
                    out["row_counts"][table] = None  # table absent in prod

            for table, column in ENUM_COLUMNS:
                try:
                    cur.execute(
                        f'SELECT "{column}", count(*) FROM "{table}" GROUP BY 1 ORDER BY 2 DESC'
                    )
                    out["enums"][f"{table}.{column}"] = {
                        str(row[0]): row[1] for row in cur.fetchall()
                    }
                except psycopg2.Error:
                    conn.rollback()
                    out["enums"][f"{table}.{column}"] = None

    dest = REPO / ".ui-audit" / "prod-shape.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"wrote {dest}")
    print(json.dumps(out["row_counts"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `.venv-linux/bin/python -m scripts.ui_audit.survey_prod`
Expected: prints `wrote .../.ui-audit/prod-shape.json` followed by a row-count table. `users` should be ~266.

- [ ] **Step 3: Confirm no PII landed on disk**

Run: `grep -ciE "@|[A-Z][a-z]+ [A-Z][a-z]+" .ui-audit/prod-shape.json`
Expected: `0` — the file contains only table names, status strings, and integers. If this is non-zero, inspect the file and remove whatever leaked before continuing.

- [ ] **Step 4: Commit the script only (output is gitignored)**

```bash
git add scripts/ui_audit/survey_prod.py
git commit -m "feat(ui-audit): read prod for row counts and enum distributions only"
```

---

### Task 4: Seed script — core records

**Files:**
- Create: `scripts/ui_audit/seed_fixtures.py`
- Test: `tests/test_ui_audit_seed.py`

**Interfaces:**
- Consumes: `.ui-audit/prod-shape.json` from Task 3 (optional — falls back to built-in defaults if absent).
- Produces: `seed_core(volumes: dict) -> dict` returning `{"users": [User], "seasons": [Season], "trips": [Trip], "tags": [Tag]}` for Task 5 to attach domain records to; `seed_all(volumes: dict | None = None) -> None` as the entry point.

- [ ] **Step 1: Write the failing test**

Note the fixtures. Files directly under `tests/` have no shared `app` fixture — each defines its own (see `tests/test_scheduler_draft_jobs.py`). More importantly, the suite's usual `app` fixture points at the **real local dev database**, and the codebase convention is to avoid writing rows to it. This seed writes hundreds, so it gets a dedicated throwaway database instead.

```python
# tests/test_ui_audit_seed.py
"""Seed script tests.

These run against a dedicated `tcsc_trips_uiaudit_test` database, created and
dropped per session. The suite's usual `app` fixture points at the real local
dev database and the convention is not to write to it -- this seed writes
hundreds of rows, so it needs its own.
"""

import subprocess

import pytest

from app import create_app
from app.models import Payment, Season, Tag, Trip, User, UserSeason, db

TEST_DB = "tcsc_trips_uiaudit_test"
TEST_URL = f"postgresql://tcsc:tcsc@localhost:5432/{TEST_DB}"


def _psql(sql, database="postgres"):
    subprocess.run(
        ["docker", "exec", "tcsc-postgres", "psql", "-U", "tcsc", "-d", database, "-c", sql],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session")
def app():
    _psql(f'DROP DATABASE IF EXISTS "{TEST_DB}"')
    _psql(f'CREATE DATABASE "{TEST_DB}"')

    application = create_app()
    application.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        SQLALCHEMY_DATABASE_URI=TEST_URL,
    )
    with application.app_context():
        subprocess.run(
            ["/workspace/tcsc-trips/.venv-linux/bin/flask", "db", "upgrade"],
            check=True,
            capture_output=True,
            env={"DATABASE_URL": TEST_URL, "TCSC_MIGRATION_ONLY": "1", "PATH": "/usr/bin:/bin"},
            cwd="/workspace/tcsc-trips",
        )
        yield application

    _psql(f'DROP DATABASE IF EXISTS "{TEST_DB}"')


@pytest.fixture
def db_session(app):
    """Empty every table before each test so counts are exact."""
    with app.app_context():
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        yield db.session
        db.session.rollback()


@pytest.fixture
def seeded(db_session):
    from scripts.ui_audit.seed_fixtures import seed_core

    return seed_core({"users": 40, "seasons": 3, "trips": 4, "tags": 8})


def test_every_core_table_is_populated(seeded, db_session):
    assert User.query.count() == 40
    assert Season.query.count() == 3
    assert Trip.query.count() == 4
    assert Tag.query.count() == 8
    assert Payment.query.count() > 0
    assert UserSeason.query.count() > 0


def test_exactly_one_season_is_current(seeded, db_session):
    assert Season.query.filter_by(is_current=True).count() == 1


def test_every_user_status_is_represented(seeded, db_session):
    """Admin filters by status; each filter must have rows behind it."""
    from app.constants import UserStatus

    present = {row.status for row in User.query.all()}
    assert {
        UserStatus.ACTIVE,
        UserStatus.PENDING,
        UserStatus.ALUMNI,
        UserStatus.DROPPED,
    } <= present


def test_some_users_carry_multiple_tags(seeded, db_session):
    """Tag badges wrapping in a table cell is a spacing surface worth capturing."""
    assert any(len(u.tags) >= 2 for u in User.query.all())


def test_seed_is_deterministic(db_session):
    from scripts.ui_audit.seed_fixtures import seed_core

    volumes = {"users": 10, "seasons": 1, "trips": 1, "tags": 4}
    first = [u.email for u in seed_core(volumes)["users"]]

    for table in reversed(db.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()

    second = [u.email for u in seed_core(volumes)["users"]]

    assert first == second
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-linux/bin/python -m pytest tests/test_ui_audit_seed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.ui_audit.seed_fixtures'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/ui_audit/seed_fixtures.py
"""Populate the local database so every admin pane renders with real content.

The bar is "no pane is empty and no table is one row" -- the spacing problems
this seed exists to expose show up under ordinary data, so plausible content at
roughly production volume is enough. Deterministic, so before/after screenshots
are comparable across runs.
"""

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from app.constants import UserStatus, UserSeasonStatus
from app.models import Payment, Season, Tag, Trip, User, UserSeason, UserTag, db

REPO = Path(__file__).resolve().parents[2]
SEED = 20260728  # fixed so runs are reproducible

FIRST_NAMES = [
    "Anna", "Bjorn", "Clara", "Devin", "Elin", "Finn", "Greta", "Hans", "Ingrid",
    "Jonas", "Kari", "Lars", "Maja", "Nils", "Oskar", "Petra", "Quinn", "Rune",
    "Sigrid", "Tobias", "Ulla", "Viktor", "Wren", "Yara", "Zach", "Marguerite",
    "Christopher", "Alexandra",
]
LAST_NAMES = [
    "Andersen", "Berg", "Christensen", "Dahl", "Eriksson", "Fjeld", "Gundersen",
    "Haugen", "Iversen", "Johansen", "Kristiansen", "Lindqvist", "Moen", "Nygaard",
    "Olsen", "Pedersen", "Rasmussen", "Solberg", "Thorsen", "Vasquez-Lindstrom",
]
TAG_SPECS = [
    ("HEAD_COACH", "Head Coach", "🎿", "linear-gradient(135deg,#1c2c44,#3b5578)"),
    ("ASSISTANT_COACH", "Assistant Coach", "⛷️", "linear-gradient(135deg,#2d6a4f,#52b788)"),
    ("BOARD_MEMBER", "Board Member", "🏛️", "linear-gradient(135deg,#6a4c93,#9d78c9)"),
    ("PRACTICE_LEAD", "Practice Lead", "📋", "linear-gradient(135deg,#bc4749,#e07a5f)"),
    ("TRIP_ORGANIZER", "Trip Organizer", "🗺️", "linear-gradient(135deg,#0077b6,#48cae4)"),
    ("WAX_TECH", "Wax Technician", "🧪", "linear-gradient(135deg,#7f5539,#b08968)"),
    ("VOLUNTEER", "Volunteer", "🤝", "linear-gradient(135deg,#606c38,#a3b18a)"),
    ("ALUMNI_MENTOR", "Alumni Mentor", "🎓", "linear-gradient(135deg,#495057,#adb5bd)"),
]
STATUSES = [UserStatus.ACTIVE, UserStatus.PENDING, UserStatus.ALUMNI, UserStatus.DROPPED]
STATUS_WEIGHTS = [0.62, 0.12, 0.18, 0.08]


def default_volumes() -> dict:
    """Volumes from the prod survey when available, otherwise sane defaults."""
    shape_file = REPO / ".ui-audit" / "prod-shape.json"
    fallback = {"users": 266, "seasons": 5, "trips": 6, "tags": len(TAG_SPECS)}
    if not shape_file.exists():
        return fallback
    counts = json.loads(shape_file.read_text()).get("row_counts", {})
    return {
        "users": counts.get("users") or fallback["users"],
        "seasons": counts.get("seasons") or fallback["seasons"],
        "trips": counts.get("trips") or fallback["trips"],
        "tags": max(counts.get("tags") or 0, len(TAG_SPECS)),
    }


def seed_core(volumes: dict) -> dict:
    rng = random.Random(SEED)

    tags = []
    for name, display, emoji, gradient in TAG_SPECS[: volumes["tags"]]:
        tag = Tag(
            name=name,
            display_name=display,
            emoji=emoji,
            gradient=gradient,
            description=f"Members designated as {display.lower()} for the current season.",
        )
        db.session.add(tag)
        tags.append(tag)
    db.session.flush()

    seasons = []
    base_year = 2026 - volumes["seasons"] + 1
    for index in range(volumes["seasons"]):
        year = base_year + index
        season = Season(
            name=f"{year}-{str(year + 1)[2:]} Season",
            season_type="winter",
            year=year,
            start_date=date(year, 11, 1),
            end_date=date(year + 1, 3, 31),
            price_cents=32500,
            returning_start=datetime(year, 8, 1, 12, 0),
            returning_end=datetime(year, 8, 21, 12, 0),
            new_start=datetime(year, 9, 1, 12, 0),
            new_end=datetime(year, 9, 21, 12, 0),
            registration_limit=280,
            description=(
                f"Registration for the {year}-{str(year + 1)[2:]} nordic season, "
                "including coached practices, waxing support, and club trips."
            ),
            is_current=(index == volumes["seasons"] - 1),
        )
        db.session.add(season)
        seasons.append(season)
    db.session.flush()

    trips = []
    for index in range(volumes["trips"]):
        start = datetime(2026, 1, 8) + timedelta(days=21 * index)
        trips.append(
            Trip(
                slug=f"seed-trip-{index + 1}",
                name=["Sisu Ski Fest", "Birkie Week", "Mora Vasaloppet",
                      "Noquemanon Weekend", "Korteloppet Camp",
                      "Boulder Lake Training Camp"][index % 6],
                destination=["Ironwood, MI", "Hayward, WI", "Mora, MN",
                             "Marquette, MI", "Cable, WI", "Duluth, MN"][index % 6],
                slack_channel_name=f"trip-seed-{index + 1}",
                max_participants_standard=40,
                max_participants_extra=10,
                start_date=start,
                end_date=start + timedelta(days=3),
                signup_start=start - timedelta(days=60),
                signup_end=start - timedelta(days=14),
                price_low=18500,
                price_high=27500,
                description=(
                    "Club trip with shared lodging, wax room access, and coached "
                    "sessions on Saturday morning."
                ),
                status=["published", "draft", "closed"][index % 3],
            )
        )
    db.session.add_all(trips)
    db.session.flush()

    users = []
    for index in range(volumes["users"]):
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[(index * 7) % len(LAST_NAMES)]
        status = rng.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        user = User(
            first_name=first,
            last_name=last,
            email=f"{first.lower()}.{last.lower().replace('-', '')}{index}@example.com",
            status=status,
            seasons_since_active=0 if status == UserStatus.ACTIVE else rng.randint(1, 3),
            phone=f"612-555-{1000 + index:04d}",
            date_of_birth=date(1975 + (index % 35), 1 + (index % 12), 1 + (index % 28)),
            pronouns=rng.choice(["she/her", "he/him", "they/them", None]),
            preferred_technique=rng.choice(["classic", "skate", "both"]),
            tshirt_size=rng.choice(["XS", "S", "M", "L", "XL", "XXL"]),
            ski_experience=rng.choice(["beginner", "intermediate", "advanced", "racer"]),
            emergency_contact_name=f"{rng.choice(FIRST_NAMES)} {last}",
            emergency_contact_relation=rng.choice(["spouse", "parent", "sibling", "friend"]),
            emergency_contact_phone=f"612-555-{5000 + index:04d}",
            emergency_contact_email=f"ec{index}@example.com",
            notes=(
                "Requested classic-only groups; prefers Thursday sessions."
                if index % 9 == 0 else None
            ),
        )
        db.session.add(user)
        users.append(user)
    db.session.flush()

    # Tags: most members untagged, a realistic minority carrying two or three.
    for index, user in enumerate(users):
        if index % 6 != 0:
            continue
        for tag in rng.sample(tags, k=rng.choice([1, 2, 2, 3])):
            db.session.add(UserTag(user_id=user.id, tag_id=tag.id))

    current_season = seasons[-1]
    for index, user in enumerate(users):
        if user.status == UserStatus.DROPPED:
            season_status = rng.choice(
                [UserSeasonStatus.DROPPED_VOLUNTARY, UserSeasonStatus.DROPPED_CAUSE]
            )
        elif user.status == UserStatus.PENDING:
            season_status = UserSeasonStatus.PENDING_LOTTERY
        else:
            season_status = UserSeasonStatus.ACTIVE
        db.session.add(
            UserSeason(user_id=user.id, season_id=current_season.id, status=season_status)
        )

        db.session.add(
            Payment(
                payment_intent_id=f"pi_seed_{index:05d}",
                email=user.email,
                name=user.full_name,
                amount=current_season.price_cents,
                status=rng.choice(
                    ["succeeded", "requires_capture", "canceled", "processing"]
                ),
                payment_type="season",
                season_id=current_season.id,
                user_id=user.id,
            )
        )

    # Trip payments so the payments dashboard has more than one payment_type.
    for index, trip in enumerate(trips):
        for offset, user in enumerate(users[index * 5 : index * 5 + 12]):
            db.session.add(
                Payment(
                    payment_intent_id=f"pi_seed_trip_{index}_{offset:03d}",
                    email=user.email,
                    name=user.full_name,
                    amount=trip.price_low,
                    status=rng.choice(["succeeded", "requires_capture", "canceled"]),
                    payment_type="trip",
                    trip_id=trip.id,
                    user_id=user.id,
                )
            )

    db.session.commit()
    return {"users": users, "seasons": seasons, "trips": trips, "tags": tags}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv-linux/bin/python -m pytest tests/test_ui_audit_seed.py -v`
Expected: PASS, 5 passed

If `flask db upgrade` in the fixture fails, check that `tests/_db_guard.py` (which enforces local-only database access) accepts the `tcsc_trips_uiaudit_test` name — it may need adding to its allowlist.

- [ ] **Step 5: Commit**

```bash
git add scripts/ui_audit/seed_fixtures.py tests/test_ui_audit_seed.py
git commit -m "feat(ui-audit): seed users, seasons, trips, tags and payments"
```

---

### Task 5: Seed script — practices, events, newsletter

Split from Task 4 because these models live in separate modules (`app/practices/models.py`, `app/events/models.py`, `app/newsletter/models.py`) and a reviewer could reasonably accept the core seed while rejecting this one.

**Files:**
- Modify: `scripts/ui_audit/seed_fixtures.py`
- Modify: `tests/test_ui_audit_seed.py`

**Interfaces:**
- Consumes: `seed_core(...) -> {"users", "seasons", "trips", "tags"}` from Task 4.
- Produces: `seed_domain(core: dict) -> None`; `seed_all(volumes: dict | None = None) -> None` which calls `seed_core` then `seed_domain`.

- [ ] **Step 1: Read the model definitions before writing code**

```bash
sed -n '39,140p' app/events/models.py
sed -n '38,120p' app/practices/models.py
sed -n '154,250p' app/practices/models.py
sed -n '413,460p' app/newsletter/models.py
```

Note every `nullable=False` column — those are the fields the seed must supply. Do not guess field names; use what these files show.

- [ ] **Step 2: Write the failing test**

```python
# append to tests/test_ui_audit_seed.py

def test_domain_tables_are_populated(db_session):
    from app.events.models import Event, EventPriceOption, EventRegistration
    from app.practices.models import Practice, PracticeLocation, PracticeType
    from app.newsletter.models import NewsletterPrompt
    from scripts.ui_audit.seed_fixtures import seed_core, seed_domain

    core = seed_core({"users": 30, "seasons": 2, "trips": 3, "tags": 8})
    seed_domain(core)

    assert PracticeLocation.query.count() >= 3
    assert PracticeType.query.count() >= 3
    assert Practice.query.count() >= 12
    assert Event.query.count() >= 2
    assert EventPriceOption.query.count() >= 3
    assert EventRegistration.query.count() >= 5
    assert NewsletterPrompt.query.count() >= 1


def test_practices_span_past_and_future(db_session):
    """The practices list and calendar both need populated ranges."""
    from datetime import date

    from app.practices.models import Practice
    from scripts.ui_audit.seed_fixtures import seed_core, seed_domain

    core = seed_core({"users": 10, "seasons": 1, "trips": 1, "tags": 8})
    seed_domain(core)

    dates = [p.date for p in Practice.query.all()]
    today = date.today()
    assert any(d < today for d in dates)
    assert any(d > today for d in dates)


def test_seed_all_runs_end_to_end(db_session):
    from app.models import User
    from scripts.ui_audit.seed_fixtures import seed_all

    seed_all({"users": 20, "seasons": 2, "trips": 2, "tags": 8})
    assert User.query.count() == 20
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv-linux/bin/python -m pytest tests/test_ui_audit_seed.py -v -k domain`
Expected: FAIL — `ImportError: cannot import name 'seed_domain'`

- [ ] **Step 4: Implement `seed_domain` and `seed_all`**

Write `seed_domain(core)` in `scripts/ui_audit/seed_fixtures.py` using the exact column names read in Step 1. It must create, at minimum:

- 3+ `PracticeLocation` rows with real Twin Cities names (Theodore Wirth Park, Hyland Hills, Elm Creek, Battle Creek)
- 3+ `PracticeType` rows (Skate Technique, Classic Distance, Strength & Balance, Trail Run)
- 5+ `PracticeActivity` rows
- 12+ `Practice` rows spanning roughly 6 weeks before today through 6 weeks after, mixing every value present in `prod-shape.json`'s `practices.status` distribution
- `PracticeLead` rows drawn from `core["users"]`, some confirmed and some not, so the lead picker renders both states
- `PracticeRSVP` rows on the past practices
- 2+ `Event` rows, at least one `draft` and one `published`, each with 2+ `EventPriceOption` rows
- 5+ `EventRegistration` rows with mixed statuses, plus `EventParticipant` rows
- 1+ `NewsletterPrompt` rows

Then add the entry point:

```python
def seed_all(volumes: dict | None = None) -> None:
    """Full seed. Safe to re-run: wipes seeded rows first."""
    core = seed_core(volumes or default_volumes())
    seed_domain(core)
```

- [ ] **Step 5: Run the full seed test file**

Run: `.venv-linux/bin/python -m pytest tests/test_ui_audit_seed.py -v`
Expected: PASS, 8 passed

- [ ] **Step 6: Seed the real dev database and eyeball it**

```bash
docker exec tcsc-postgres psql -U tcsc -d tcsc_trips -c "
  TRUNCATE users, seasons, trips, tags, payments, practices, events RESTART IDENTITY CASCADE;"
.venv-linux/bin/python -c "
from app import create_app
from scripts.ui_audit.seed_fixtures import seed_all
app = create_app()
with app.app_context():
    seed_all()
    print('seeded')
"
docker exec tcsc-postgres psql -U tcsc -d tcsc_trips -c "
  SELECT 'users' t, count(*) FROM users
  UNION ALL SELECT 'practices', count(*) FROM practices
  UNION ALL SELECT 'events', count(*) FROM events
  UNION ALL SELECT 'payments', count(*) FROM payments;"
```
Expected: users ~266, practices 12+, events 2+, payments 300+.

- [ ] **Step 7: Commit**

```bash
git add scripts/ui_audit/seed_fixtures.py tests/test_ui_audit_seed.py
git commit -m "feat(ui-audit): seed practices, events and newsletter records"
```

---

### Task 6: Capture harness

**Files:**
- Create: `scripts/ui_audit/surfaces.mjs` (the manifest)
- Create: `scripts/ui_audit/capture.mjs` (the runner)
- Create: `scripts/ui_audit/run.sh`

**Interfaces:**
- Consumes: the JSON line printed by `scripts/ui_audit/serve.py` (`{cookie_name, cookie_value, port}`).
- Produces: `.ui-audit/<label>/<surface>--<state>--<viewport>.png` plus `.ui-audit/<label>/index.json` listing every capture.

- [ ] **Step 1: Write the surface manifest**

```javascript
// scripts/ui_audit/surfaces.mjs
// Every admin surface to capture, and the interactive states to reveal on each.
//
// This list is deliberate rather than crawled so the exact set of interactions is
// reviewable. `open` entries are openers only -- selectors that reveal UI. Nothing
// that submits, saves, deletes, runs, or sends belongs here, and capture.mjs
// aborts every non-GET request as a backstop.

export const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 1024, height: 768 },
  { name: 'mobile', width: 390, height: 844 },
];

export const SURFACES = [
  {
    group: 'shared',
    name: 'dashboard',
    path: '/admin',
    states: [],
  },
  {
    group: 'members',
    name: 'users-list',
    path: '/admin/users',
    states: [
      { name: 'row-drawer', click: 'table tbody tr' },
      { name: 'filters-open', click: '[data-filter-toggle], .admin-ui-filterbar' },
    ],
  },
  {
    group: 'members',
    name: 'user-detail',
    path: '/admin/users/1',
    states: [],
  },
  {
    group: 'members',
    name: 'user-edit',
    path: '/admin/users/1/edit',
    states: [],
  },
  {
    group: 'members',
    name: 'roles',
    path: '/admin/roles',
    states: [
      { name: 'create-tag-modal', click: '[data-open-create-tag], button' },
    ],
  },
  {
    group: 'payments',
    name: 'payments',
    path: '/admin/payments',
    states: [
      { name: 'row-drawer', click: 'table tbody tr' },
    ],
  },
  {
    group: 'slack',
    name: 'slack-sync',
    path: '/admin/slack',
    states: [],
  },
  {
    group: 'slack',
    name: 'channel-sync',
    path: '/admin/channel-sync',
    states: [],
  },
  {
    group: 'slack',
    name: 'scheduled-tasks',
    path: '/admin/scheduled-tasks',
    states: [],
  },
  {
    group: 'slack',
    name: 'skipper',
    path: '/admin/skipper',
    states: [],
  },
  {
    group: 'practices',
    name: 'practices-list',
    path: '/admin/practices',
    states: [],
  },
  {
    group: 'practices',
    name: 'practices-calendar',
    path: '/admin/practices/calendar',
    states: [],
  },
  {
    group: 'practices',
    name: 'practices-config',
    path: '/admin/practices/config',
    states: [],
  },
  {
    group: 'practices',
    name: 'availability',
    path: '/admin/availability',
    states: [],
  },
  {
    group: 'catalog',
    name: 'trips',
    path: '/admin/trips',
    states: [],
  },
  {
    group: 'catalog',
    name: 'trip-new',
    path: '/admin/trips/new',
    states: [],
  },
  {
    group: 'catalog',
    name: 'seasons',
    path: '/admin/seasons',
    states: [],
  },
  {
    group: 'catalog',
    name: 'season-new',
    path: '/admin/seasons/new',
    states: [],
  },
  {
    group: 'catalog',
    name: 'events',
    path: '/admin/events',
    states: [],
  },
  {
    group: 'catalog',
    name: 'newsletter-prompts',
    path: '/admin/newsletter/prompts',
    states: [],
  },
];
```

- [ ] **Step 2: Write the capture runner**

```javascript
// scripts/ui_audit/capture.mjs
// Usage: NODE_PATH=$(npm root -g) node scripts/ui_audit/capture.mjs <label> <serverJson>
//
// <label> names the output directory (e.g. "before", "after-members").
// <serverJson> is the JSON line printed by scripts/ui_audit/serve.py.

import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { SURFACES, VIEWPORTS } from './surfaces.mjs';

const label = process.argv[2];
const server = JSON.parse(process.argv[3]);
if (!label) throw new Error('usage: capture.mjs <label> <serverJson>');

const BASE = `http://127.0.0.1:${server.port}`;
const OUT = `.ui-audit/${label}`;
await mkdir(OUT, { recursive: true });

const browser = await chromium.launch();
const captured = [];

for (const viewport of VIEWPORTS) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 2,
  });

  // Backstop: a misfired click cannot produce a request that mutates anything.
  await context.route('**/*', (route) => {
    const method = route.request().method();
    if (method === 'GET' || method === 'HEAD') return route.continue();
    console.warn(`  BLOCKED ${method} ${route.request().url()}`);
    return route.abort();
  });

  await context.addCookies([
    {
      name: server.cookie_name,
      value: server.cookie_value,
      domain: '127.0.0.1',
      path: '/',
    },
  ]);

  const page = await context.newPage();

  for (const surface of SURFACES) {
    const shoot = async (stateName) => {
      const file = `${surface.name}--${stateName}--${viewport.name}.png`;
      await page.screenshot({ path: `${OUT}/${file}`, fullPage: true });
      captured.push({ group: surface.group, surface: surface.name, state: stateName, viewport: viewport.name, file });
      console.log(`  ${file}`);
    };

    try {
      const response = await page.goto(BASE + surface.path, {
        waitUntil: 'networkidle',
        timeout: 30000,
      });
      if (response && response.status() >= 400) {
        console.warn(`  SKIP ${surface.path} -> HTTP ${response.status()}`);
        continue;
      }
      if (page.url().includes('/login')) {
        throw new Error(`session cookie rejected at ${surface.path}`);
      }
      await page.waitForTimeout(600);
      await shoot('base');

      for (const state of surface.states) {
        try {
          const target = page.locator(state.click).first();
          if ((await target.count()) === 0) {
            console.warn(`  SKIP ${surface.name}/${state.name} -> no match for ${state.click}`);
            continue;
          }
          await target.click({ timeout: 5000 });
          await page.waitForTimeout(700);
          await shoot(state.name);
          await page.keyboard.press('Escape');
          await page.waitForTimeout(300);
        } catch (err) {
          console.warn(`  SKIP ${surface.name}/${state.name} -> ${err.message}`);
        }
      }
    } catch (err) {
      console.warn(`  FAIL ${surface.path} -> ${err.message}`);
    }
  }

  await context.close();
}

await browser.close();
await writeFile(`${OUT}/index.json`, JSON.stringify(captured, null, 2));
console.log(`\n${captured.length} captures -> ${OUT}`);
```

- [ ] **Step 3: Write the run wrapper**

```bash
#!/usr/bin/env bash
# scripts/ui_audit/run.sh — seed (optional), serve, capture, tear down.
# Usage: scripts/ui_audit/run.sh <label> [--seed]
set -euo pipefail
cd "$(dirname "$0")/../.."

LABEL="${1:?usage: run.sh <label> [--seed]}"
PORT=5055

npm run tailwind:build

if [[ "${2:-}" == "--seed" ]]; then
  docker exec tcsc-postgres psql -U tcsc -d tcsc_trips -c \
    "TRUNCATE users, seasons, trips, tags, payments, practices, events RESTART IDENTITY CASCADE;"
  .venv-linux/bin/python -c "
from app import create_app
from scripts.ui_audit.seed_fixtures import seed_all
app = create_app()
with app.app_context():
    seed_all()
"
fi

.venv-linux/bin/python -m scripts.ui_audit.serve "$PORT" > .ui-audit/server.json &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  [[ -s .ui-audit/server.json ]] && break
  sleep 1
done

NODE_PATH="$(npm root -g)" node scripts/ui_audit/capture.mjs "$LABEL" "$(head -1 .ui-audit/server.json)"
```

- [ ] **Step 4: Make it executable and run a capture**

```bash
mkdir -p .ui-audit
chmod +x scripts/ui_audit/run.sh
scripts/ui_audit/run.sh smoke
```
Expected: PNG filenames stream past; final line reports 50+ captures. Any `BLOCKED POST` line in the output is a bug in the manifest — that selector is a submit control and must be removed from `surfaces.mjs`.

- [ ] **Step 5: Verify authentication actually worked**

Run: `.venv-linux/bin/python -c "
from PIL import Image
im = Image.open('.ui-audit/smoke/users-list--base--desktop.png')
print(im.size)
"` — or simply open the file.
Expected: the users list with seeded rows, not a login redirect. If it shows a login page, the cookie domain in `capture.mjs` does not match the host — align them.

- [ ] **Step 6: Commit**

```bash
git add scripts/ui_audit/surfaces.mjs scripts/ui_audit/capture.mjs scripts/ui_audit/run.sh
git commit -m "feat(ui-audit): capture every admin surface at three viewports"
```

---

### Task 7: Expand the manifest and take the baseline

The Task 6 manifest is a skeleton with guessed selectors. This task makes it real by reading the actual markup.

**Files:**
- Modify: `scripts/ui_audit/surfaces.mjs`
- Create: `docs/superpowers/notes/2026-07-28-admin-ui-findings.md`

**Interfaces:**
- Produces: `.ui-audit/before/` (the baseline gallery) and the findings inventory consumed by Tasks 8–13.

- [ ] **Step 1: Find every real interactive opener**

```bash
grep -rnoE "id=\"[a-z-]*(drawer|modal|panel|dialog)[a-z-]*\"" app/templates/admin/ app/static/admin_*.js | sort -u
grep -rnoE "data-[a-z-]*(open|toggle|expand|edit)[a-z-]*" app/templates/admin/ app/static/admin_*.js | sort -u
grep -rnoE "addEventListener\('click'" app/static/admin_*.js | wc -l
```

Replace every guessed selector in `surfaces.mjs` with a real one. Add a state for every drawer, modal, inline editor, expanded row, filter panel, and tab found. Confirm each added selector is an opener, not a submit control.

- [ ] **Step 2: Verify the manifest covers every admin route**

```bash
grep -rhoE "@[a-z_]+\.route\('([^']*)'\)" app/routes/admin*.py \
  | sed -E "s/@[a-z_]+\.route\('//; s/'\)//" | sort -u > /tmp/routes.txt
grep -oE "path: '[^']*'" scripts/ui_audit/surfaces.mjs | sed "s/path: '//; s/'//" | sort -u > /tmp/manifest.txt
comm -23 /tmp/routes.txt /tmp/manifest.txt
```
Expected: only JSON/action endpoints (`/data`, `/status`, `/run`, `/trigger/...`) remain. Any GET page route in the output must be added to the manifest.

- [ ] **Step 3: Take the baseline**

```bash
scripts/ui_audit/run.sh before --seed
```
Expected: 250+ captures in `.ui-audit/before/`, zero `BLOCKED` lines.

- [ ] **Step 4: Triage into a findings inventory**

Review every capture. For each problem, record a row in `docs/superpowers/notes/2026-07-28-admin-ui-findings.md`:

```markdown
| # | Group | Surface | Viewport | Element | Issue | Severity | Source |
|---|-------|---------|----------|---------|-------|----------|--------|
| 1 | members | users-list | desktop | tag badges in name cell | badges touch the name text, no gap | high | admin_users.js:412 |
```

Severity: **high** = elements touch or overlap; **medium** = spacing visibly inconsistent with the same component elsewhere; **low** = off the scale but reads fine.

Use Codex for the dense surfaces where the cause is not obvious from the screenshot alone:

```bash
codex exec -m gpt-5.6-sol -c model_reasoning_effort="max" \
  -i .ui-audit/before/payments--row-drawer--desktop.png \
  "This is the TCSC admin payments drawer. Identify every spacing and padding
   defect: elements too close, inconsistent gaps between sibling rows, padding
   that disagrees with other drawers in this app. The markup is generated in
   app/static/admin_payments.js. For each defect give the element, the specific
   problem, and the line in that file that produces it. Do not propose redesigns
   — spacing and padding only."
```

Review every Codex finding against the screenshot before recording it.

- [ ] **Step 5: Commit the baseline inventory**

```bash
git add scripts/ui_audit/surfaces.mjs docs/superpowers/notes/2026-07-28-admin-ui-findings.md
git commit -m "docs(ui-audit): baseline capture and findings inventory"
```

---

### Task 8: Spacing scale + shared components (PR 1)

**Files:**
- Modify: `app/static/css/admin_ui.css`
- Modify: `app/templates/admin/admin_base.html`
- Modify: `app/templates/admin/partials/header.html`, `app/templates/admin/partials/sidebar.html`

**Interfaces:**
- Produces: CSS custom properties `--admin-space-1` … `--admin-space-6`, semantic aliases `--admin-field-gap`, `--admin-section-gap`, `--admin-drawer-pad`, `--admin-row-gap`; and component classes `.admin-ui-form-row`, `.admin-ui-field-group`, `.admin-ui-section`, `.admin-ui-btn-row`. Tasks 9–13 consume these and must not redefine them.

- [ ] **Step 1: Inventory every hardcoded spacing value**

```bash
grep -oE "(padding|margin|gap|top|bottom|left|right)[a-z-]*: *[0-9.]+px" app/static/css/admin_ui.css \
  | sort | uniq -c | sort -rn
```
Record the output in the findings note. Each distinct value gets mapped to a scale step; anything more than 2px from its nearest step is a judgement call to flag rather than silently snap.

- [ ] **Step 2: Add the scale**

Insert at the top of `app/static/css/admin_ui.css`, after the file's opening comment:

```css
/* --- Spacing scale ---
   Every spacing value in admin surfaces resolves to one of these steps. The
   drift this file accumulated came from ad-hoc pixel values (9px here, 13px
   there) that disagreed between components; the scale is what stops that
   recurring. Semantic aliases exist so a component expresses intent rather
   than a number. */
:root {
  --admin-space-1: 4px;
  --admin-space-2: 8px;
  --admin-space-3: 12px;
  --admin-space-4: 16px;
  --admin-space-5: 24px;
  --admin-space-6: 32px;

  --admin-field-gap: var(--admin-space-4);    /* between form fields */
  --admin-row-gap: var(--admin-space-2);      /* between rows within a field */
  --admin-section-gap: var(--admin-space-5);  /* between titled sections */
  --admin-drawer-pad: var(--admin-space-5);   /* drawer/modal inner padding */
}
```

- [ ] **Step 3: Snap every existing value in `admin_ui.css`**

Replace hardcoded values with scale references. Known cases from the current file:

| Current | Becomes |
|---|---|
| `padding: 16px 20px` (drawer header) | `padding: var(--admin-space-4) var(--admin-space-5)` |
| `padding: 20px` (drawer body) | `padding: var(--admin-drawer-pad)` |
| `margin: 16px 0` (separator) | `margin: var(--admin-space-4) 0` |
| `margin-bottom: 4px` (dw-section) | `margin-bottom: var(--admin-section-gap)` |
| `margin-bottom: 10px` (section title) | `margin-bottom: var(--admin-space-3)` |
| `margin-bottom: 6px` (kv row) | `margin-bottom: var(--admin-row-gap)` |
| `gap: 9px` (drawer footer) | `gap: var(--admin-space-3)` |
| `padding: 13px 18px` (drawer footer) | `padding: var(--admin-space-3) var(--admin-space-5)` |
| `padding: 9px 11px` (dw-desc) | `padding: var(--admin-space-3)` |
| `gap: 8px`, `gap: 6px` (filterbar) | `var(--admin-space-2)` |
| `margin-bottom: 16px` (filterbar) | `var(--admin-space-4)` |

`.admin-ui-dw-section { margin-bottom: 4px }` is the single most likely cause of the reported crowding — titled sections separated by 4px read as one block. Raising it to `--admin-section-gap` (24px) is the largest intentional change in this task; capture it explicitly in the PR description.

Leave `font-size` values alone — type scale is a non-goal.

- [ ] **Step 4: Add the shared component classes**

Append to `app/static/css/admin_ui.css`:

```css
/* --- Shared layout components ---
   The admin_*.js files each hand-rolled these four patterns with slightly
   different spacing, which is where most cross-surface inconsistency came
   from. Consuming surfaces use these classes instead of inline spacing. */
.admin-ui-form-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--admin-field-gap);
  align-items: flex-start;
  margin-bottom: var(--admin-field-gap);
}
.admin-ui-field-group {
  display: flex;
  flex-direction: column;
  gap: var(--admin-row-gap);
  flex: 1 1 220px;
  min-width: 0;
}
.admin-ui-section {
  margin-bottom: var(--admin-section-gap);
}
.admin-ui-section:last-child { margin-bottom: 0; }
.admin-ui-btn-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--admin-space-3);
  margin-top: var(--admin-section-gap);
}
```

- [ ] **Step 5: Re-capture and diff**

```bash
scripts/ui_audit/run.sh after-shared
```
Compare `.ui-audit/before/` against `.ui-audit/after-shared/` for every surface — this task touches shared CSS, so all of them are affected. Confirm each high-severity finding attributable to shared primitives is resolved and nothing new appeared.

- [ ] **Step 6: Run the test suites**

```bash
npm run test:practice-reactions
npm run test:events
.venv-linux/bin/python -m pytest -q
```
Expected: all pass. Markup changes can break JS tests that assert on structure — if one fails, fix the cause, do not adjust the assertion to match.

- [ ] **Step 7: Commit and open PR 1**

```bash
git add app/static/css/admin_ui.css app/templates/admin/admin_base.html app/templates/admin/partials/
git commit -m "style(admin): introduce a spacing scale and shared layout components

Replaces ad-hoc pixel values in admin_ui.css with a six-step scale plus
semantic aliases, and adds shared classes for the four patterns the admin
JS files each hand-rolled: form row, field group, section, button row.

The largest single change is .admin-ui-dw-section margin-bottom 4px -> 24px;
titled drawer sections previously read as one undifferentiated block."
gh pr create --title "Admin UI polish 1/6: spacing scale and shared components" --body "..."
```

PR body must include the before/after gallery and call out the `dw-section` change explicitly.

---

### Task 9: Members surfaces (PR 2)

**Files:**
- Modify: `app/static/admin_users.js`
- Modify: `app/templates/admin/users.html`, `user_detail.html`, `user_edit.html`, `roles.html`

**Interfaces:**
- Consumes: the scale and component classes from Task 8. Do not introduce new spacing values — if a finding needs a value not on the scale, that is a signal the scale is wrong; raise it rather than adding a one-off.

- [ ] **Step 1: Extract this group's findings to a file the agent can read**

```bash
cd /workspace/tcsc-trips
grep -E "^\| *[0-9]+ *\| *members " docs/superpowers/notes/2026-07-28-admin-ui-findings.md \
  > .worktrees/ui-members/FINDINGS.md
wc -l .worktrees/ui-members/FINDINGS.md
```
Expected: one line per members finding. If zero, the findings table's Group column does not read `members` — check Task 7 Step 4's formatting.

- [ ] **Step 2: Dispatch the Codex agent**

```bash
cd /workspace/tcsc-trips/.worktrees/ui-members
codex exec -m gpt-5.6-sol -c model_reasoning_effort="max" \
  -i /workspace/tcsc-trips/.ui-audit/before/users-list--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/users-list--row-drawer--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/user-edit--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/roles--base--desktop.png \
  "$(cat <<'PROMPT'
<SHARED PROMPT PREAMBLE — paste verbatim from the Codex Execution Model section>

YOUR SCOPE: the members surfaces. You may modify ONLY these files:
  app/static/admin_users.js
  app/templates/admin/users.html
  app/templates/admin/user_detail.html
  app/templates/admin/user_edit.html
  app/templates/admin/roles.html

The attached screenshots are the current state of the users list, the user
row drawer, the user edit form, and the roles/tags page at 1440px.

The confirmed defects to fix are in ./FINDINGS.md — read it first. Fix them in
severity order, high first. Also fix any spacing defect you can see in the
screenshots that is not yet listed, and say so in your report.

The most common defect class here: admin_users.js builds markup with template
literals carrying inline Tailwind spacing that disagrees with the same
component elsewhere. For example a row rendered as
    `<div class="flex gap-2 mb-1">`
should become
    `<div class="admin-ui-form-row">`
Apply that substitution wherever the pattern matches, but verify against the
screenshot that the result is the intended spacing rather than assuming.
PROMPT
)"
```

- [ ] **Step 3: Review the agent's diff before trusting anything**

```bash
cd /workspace/tcsc-trips/.worktrees/ui-members
git diff --stat
git diff
```

Reject and re-run if any of these appear — each violates a hard rule:
- a file outside the five listed above
- any change to `app/static/css/admin_ui.css`
- a bare pixel value where a `var(--admin-space-N)` belongs
- a color, `font-size`, `font-weight`, or `border` change
- structural edits that move an element rather than respace it

Discard a bad run with `git checkout .` and re-dispatch with the violation named explicitly in the prompt.

- [ ] **Step 4: Re-capture this group and diff**

Copy the agent's work back into the main checkout so the capture harness sees it, then capture:

```bash
cd /workspace/tcsc-trips
git -C .worktrees/ui-members diff > /tmp/ui-members.patch
git apply /tmp/ui-members.patch
scripts/ui_audit/run.sh after-members
```
Compare every `users-*`, `user-*`, and `roles-*` capture against `.ui-audit/before/`. Every `members` finding must be resolved; no new issue may appear at any of the three viewports. If a fix looks wrong, revert with `git checkout .` and re-dispatch the agent naming the specific regression.

- [ ] **Step 5: Run the test suites**

```bash
npm run test:practice-reactions
npm run test:events
.venv-linux/bin/python -m pytest -q
```
Expected: all pass. If a JS test fails, fix the cause — do not adjust the assertion to match the agent's output.

- [ ] **Step 6: Commit and open PR 2**

The orchestrator commits, never the agent:

```bash
git add app/static/admin_users.js app/templates/admin/users.html app/templates/admin/user_detail.html app/templates/admin/user_edit.html app/templates/admin/roles.html
git commit -m "style(admin): apply the spacing scale to member surfaces"
gh pr create --title "Admin UI polish 2/6: members" --body "..."
```

---

### Task 10: Payments surfaces (PR 3)

**Files:**
- Modify: `app/static/admin_payments.js`
- Modify: `app/templates/admin/payments.html`, `event_registrations.html`

**Interfaces:**
- Consumes: the scale and component classes from Task 8.

- [ ] **Step 1: Extract this group's findings**

```bash
cd /workspace/tcsc-trips
grep -E "^\| *[0-9]+ *\| *payments " docs/superpowers/notes/2026-07-28-admin-ui-findings.md \
  > .worktrees/ui-payments/FINDINGS.md
wc -l .worktrees/ui-payments/FINDINGS.md
```

- [ ] **Step 2: Dispatch the Codex agent**

```bash
cd /workspace/tcsc-trips/.worktrees/ui-payments
codex exec -m gpt-5.6-sol -c model_reasoning_effort="max" \
  -i /workspace/tcsc-trips/.ui-audit/before/payments--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/payments--row-drawer--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/payments--base--tablet.png \
  "$(cat <<'PROMPT'
<SHARED PROMPT PREAMBLE — paste verbatim from the Codex Execution Model section>

YOUR SCOPE: the payments surfaces. You may modify ONLY these files:
  app/static/admin_payments.js
  app/templates/admin/payments.html
  app/templates/admin/event_registrations.html

admin_payments.js is 35KB and is the second-largest generated-markup surface in
this app. Start by listing every function in it that returns or assigns HTML,
then work through them.

The attached screenshots show the payments dashboard and its row drawer at
1440px, plus the dashboard at 1024px where column crowding is worse.

The confirmed defects to fix are in ./FINDINGS.md — read it first. Fix them in
severity order, high first. Also fix any spacing defect visible in the
screenshots that is not yet listed, and say so in your report.

Pay particular attention to the drawer: it uses the .admin-ui-dw-* family, whose
section spacing changed from 4px to 24px in the shared-primitives pass. Any
place this file compensated for the old cramped spacing with its own extra
margin will now be double-spaced. Remove those compensations rather than
adding more.
PROMPT
)"
```

- [ ] **Step 3: Review the agent's diff**

```bash
cd /workspace/tcsc-trips/.worktrees/ui-payments
git diff --stat
git diff
```

Reject and re-run if any appear: a file outside the three listed, any change to `app/static/css/admin_ui.css`, a bare pixel value where a scale variable belongs, a color/font/border change, or a structural edit that moves an element. Discard with `git checkout .` and re-dispatch naming the violation.

- [ ] **Step 4: Re-capture and diff**

```bash
cd /workspace/tcsc-trips
git -C .worktrees/ui-payments diff > /tmp/ui-payments.patch
git apply /tmp/ui-payments.patch
scripts/ui_audit/run.sh after-payments
```
Compare every `payments-*` and `event-registrations-*` capture against the baseline at all three viewports.

- [ ] **Step 5: Run the test suites**

```bash
npm run test:practice-reactions
npm run test:events
.venv-linux/bin/python -m pytest -q
```
Expected: all pass.

- [ ] **Step 6: Commit and open PR 3**

```bash
git add app/static/admin_payments.js app/templates/admin/payments.html app/templates/admin/event_registrations.html
git commit -m "style(admin): apply the spacing scale to payment surfaces"
gh pr create --title "Admin UI polish 3/6: payments" --body "..."
```

---

### Task 11: Slack ops surfaces (PR 4)

**Files:**
- Modify: `app/static/admin_slack.js` (73KB — the largest file in the project), `app/static/admin_skipper.js`
- Modify: `app/templates/admin/slack_sync.html`, `channel_sync.html`, `scheduled_tasks.html`, `skipper.html`

**Interfaces:**
- Consumes: the scale and component classes from Task 8.

- [ ] **Step 1: Extract this group's findings**

```bash
cd /workspace/tcsc-trips
grep -E "^\| *[0-9]+ *\| *slack " docs/superpowers/notes/2026-07-28-admin-ui-findings.md \
  > .worktrees/ui-slack/FINDINGS.md
wc -l .worktrees/ui-slack/FINDINGS.md
```

- [ ] **Step 2: Dispatch the Codex agent**

This is the largest group — `admin_slack.js` alone is 73KB, the biggest file in the project — so the prompt has the agent map the file before editing it.

```bash
cd /workspace/tcsc-trips/.worktrees/ui-slack
codex exec -m gpt-5.6-sol -c model_reasoning_effort="max" \
  -i /workspace/tcsc-trips/.ui-audit/before/slack-sync--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/channel-sync--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/scheduled-tasks--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/skipper--base--desktop.png \
  "$(cat <<'PROMPT'
<SHARED PROMPT PREAMBLE — paste verbatim from the Codex Execution Model section>

YOUR SCOPE: the Slack ops surfaces. You may modify ONLY these files:
  app/static/admin_slack.js
  app/static/admin_skipper.js
  app/templates/admin/slack_sync.html
  app/templates/admin/channel_sync.html
  app/templates/admin/scheduled_tasks.html
  app/templates/admin/skipper.html

app/static/admin_slack.js is 73KB, the largest file in this project. Before
editing anything, produce a table of every function in it that returns or
assigns HTML markup, with line numbers and the spacing-related Tailwind classes
each applies (gap-*, p-*, m-*, space-*). Include that table in your report. Then
work through the findings.

The attached screenshots show slack sync, channel sync, scheduled tasks, and
skipper at 1440px.

The confirmed defects to fix are in ./FINDINGS.md — read it first. Fix them in
severity order, high first. Also fix any spacing defect visible in the
screenshots that is not yet listed, and say so in your report.

These four pages accumulated independently and are the most likely place for
the same conceptual component to be spaced three different ways. Where you find
that, converge them on the shared classes rather than picking one file's
version and copying it.
PROMPT
)"
```

- [ ] **Step 3: Review the agent's diff**

```bash
cd /workspace/tcsc-trips/.worktrees/ui-slack
git diff --stat
git diff
```

Given the size of `admin_slack.js`, read the diff in full rather than skimming the stat. Reject and re-run if any appear: a file outside the six listed, any change to `app/static/css/admin_ui.css`, a bare pixel value where a scale variable belongs, a color/font/border change, or a structural edit that moves an element. Discard with `git checkout .` and re-dispatch naming the violation.

- [ ] **Step 4: Re-capture and diff**

```bash
cd /workspace/tcsc-trips
git -C .worktrees/ui-slack diff > /tmp/ui-slack.patch
git apply /tmp/ui-slack.patch
scripts/ui_audit/run.sh after-slack
```

- [ ] **Step 5: Run the test suites**

```bash
npm run test:practice-reactions
npm run test:events
.venv-linux/bin/python -m pytest -q
```
Expected: all pass.

- [ ] **Step 6: Commit and open PR 4**

```bash
git add app/static/admin_slack.js app/static/admin_skipper.js app/templates/admin/slack_sync.html app/templates/admin/channel_sync.html app/templates/admin/scheduled_tasks.html app/templates/admin/skipper.html
git commit -m "style(admin): apply the spacing scale to Slack ops surfaces"
gh pr create --title "Admin UI polish 4/6: Slack ops" --body "..."
```

---

### Task 12: Practices surfaces (PR 5)

**Files:**
- Modify: `app/static/admin_practices.js`
- Modify: `app/templates/admin/practices/list.html`, `detail.html`, `calendar.html`, `config.html`

**Interfaces:**
- Consumes: the scale and component classes from Task 8.

- [ ] **Step 1: Extract this group's findings**

```bash
cd /workspace/tcsc-trips
grep -E "^\| *[0-9]+ *\| *practices " docs/superpowers/notes/2026-07-28-admin-ui-findings.md \
  > .worktrees/ui-practices/FINDINGS.md
wc -l .worktrees/ui-practices/FINDINGS.md
```

- [ ] **Step 2: Dispatch the Codex agent**

```bash
cd /workspace/tcsc-trips/.worktrees/ui-practices
codex exec -m gpt-5.6-sol -c model_reasoning_effort="max" \
  -i /workspace/tcsc-trips/.ui-audit/before/practices-list--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/practices-calendar--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/practices-config--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/availability--base--desktop.png \
  "$(cat <<'PROMPT'
<SHARED PROMPT PREAMBLE — paste verbatim from the Codex Execution Model section>

YOUR SCOPE: the practices surfaces. You may modify ONLY these files:
  app/static/admin_practices.js
  app/templates/admin/practices/list.html
  app/templates/admin/practices/detail.html
  app/templates/admin/practices/calendar.html
  app/templates/admin/practices/config.html

The attached screenshots show the practices list, calendar, config page, and
the lead-availability page at 1440px.

The confirmed defects to fix are in ./FINDINGS.md — read it first. Fix them in
severity order, high first. Also fix any spacing defect visible in the
screenshots that is not yet listed, and say so in your report.

The availability poll cards and the lead picker live in admin_practices.js and
are among the densest editable surfaces in this app — they stack a heading,
several rows of member names with toggles, and a button row inside a card. That
is exactly the shape .admin-ui-section and .admin-ui-btn-row exist for.

CRITICAL: this surface has the heaviest JS test coverage in the project —
tests/js/lead_picker.test.js and tests/js/draft_publish.test.js assert on the
generated markup. If you change a class attribute those tests read, they will
fail. Run `npm run test:practice-reactions` yourself before reporting done, and
if it fails, fix your change rather than the test.
PROMPT
)"
```

- [ ] **Step 3: Review the agent's diff**

```bash
cd /workspace/tcsc-trips/.worktrees/ui-practices
git diff --stat
git diff
git diff --stat -- tests/
```

The third command must print nothing — the agent was told to fix its own change rather than the tests, and a diff under `tests/` means it did the opposite. That is an automatic reject. Otherwise reject and re-run on the usual violations: a file outside the five listed, any change to `app/static/css/admin_ui.css`, a bare pixel value where a scale variable belongs, a color/font/border change, or a structural edit that moves an element.

- [ ] **Step 4: Re-capture and diff**

```bash
cd /workspace/tcsc-trips
git -C .worktrees/ui-practices diff > /tmp/ui-practices.patch
git apply /tmp/ui-practices.patch
scripts/ui_audit/run.sh after-practices
```

- [ ] **Step 5: Run the test suites**

Practices has the most JS test coverage of any surface, so this step is load-bearing:

```bash
npm run test:practice-reactions
npm run test:events
.venv-linux/bin/python -m pytest -q
```
Expected: all pass, including `tests/js/lead_picker.test.js` and `tests/js/draft_publish.test.js`.

- [ ] **Step 6: Commit and open PR 5**

```bash
git add app/static/admin_practices.js app/templates/admin/practices/
git commit -m "style(admin): apply the spacing scale to practice surfaces"
gh pr create --title "Admin UI polish 5/6: practices" --body "..."
```

---

### Task 13: Catalog surfaces (PR 6)

**Files:**
- Modify: `app/static/admin_trips.js`, `app/static/admin_seasons.js`, `app/static/admin_events.js`
- Modify: `app/templates/admin/trips.html`, `trip_form.html`, `seasons.html`, `season_form.html`, `events.html`, `event_form.html`, `newsletter_prompts.html`

**Interfaces:**
- Consumes: the scale and component classes from Task 8.

- [ ] **Step 1: Extract this group's findings**

```bash
cd /workspace/tcsc-trips
grep -E "^\| *[0-9]+ *\| *catalog " docs/superpowers/notes/2026-07-28-admin-ui-findings.md \
  > .worktrees/ui-catalog/FINDINGS.md
wc -l .worktrees/ui-catalog/FINDINGS.md
```

- [ ] **Step 2: Dispatch the Codex agent**

```bash
cd /workspace/tcsc-trips/.worktrees/ui-catalog
codex exec -m gpt-5.6-sol -c model_reasoning_effort="max" \
  -i /workspace/tcsc-trips/.ui-audit/before/trip-new--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/season-new--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/events--base--desktop.png \
  -i /workspace/tcsc-trips/.ui-audit/before/newsletter-prompts--base--desktop.png \
  "$(cat <<'PROMPT'
<SHARED PROMPT PREAMBLE — paste verbatim from the Codex Execution Model section>

YOUR SCOPE: the catalog surfaces. You may modify ONLY these files:
  app/static/admin_trips.js
  app/static/admin_seasons.js
  app/static/admin_events.js
  app/templates/admin/trips.html
  app/templates/admin/trip_form.html
  app/templates/admin/seasons.html
  app/templates/admin/season_form.html
  app/templates/admin/events.html
  app/templates/admin/event_form.html
  app/templates/admin/newsletter_prompts.html

The attached screenshots show the new-trip form, the new-season form, the events
list, and the newsletter prompts page at 1440px.

The confirmed defects to fix are in ./FINDINGS.md — read it first. Fix them in
severity order, high first. Also fix any spacing defect visible in the
screenshots that is not yet listed, and say so in your report.

event_form.html (196 lines) and trip_form.html (123 lines) are the densest
editable forms in this app — long runs of label/input pairs, several of them
side by side. This is the most likely location of the original complaint that
"fields have a little bit of overlap or are weirdly close to each other." Give
these two files the most attention. Each label/input pair should be an
.admin-ui-field-group, and each horizontal run of them an .admin-ui-form-row.

tests/js/admin_event_scopes.test.js asserts on markup generated by
admin_events.js. Run `npm run test:events` yourself before reporting done, and
if it fails, fix your change rather than the test.
PROMPT
)"
```

- [ ] **Step 3: Review the agent's diff**

```bash
cd /workspace/tcsc-trips/.worktrees/ui-catalog
git diff --stat
git diff
git diff --stat -- tests/
```

The third command must print nothing; a diff under `tests/` is an automatic reject. Otherwise reject and re-run on the usual violations: a file outside the ten listed, any change to `app/static/css/admin_ui.css`, a bare pixel value where a scale variable belongs, a color/font/border change, or a structural edit that moves an element.

- [ ] **Step 4: Re-capture and diff**

```bash
cd /workspace/tcsc-trips
git -C .worktrees/ui-catalog diff > /tmp/ui-catalog.patch
git apply /tmp/ui-catalog.patch
scripts/ui_audit/run.sh after-catalog
```

- [ ] **Step 5: Run the test suites**

```bash
npm run test:practice-reactions
npm run test:events
.venv-linux/bin/python -m pytest -q
```
Expected: all pass, including `tests/js/admin_event_scopes.test.js`.

- [ ] **Step 6: Commit and open PR 6**

```bash
git add app/static/admin_trips.js app/static/admin_seasons.js app/static/admin_events.js app/templates/admin/trips.html app/templates/admin/trip_form.html app/templates/admin/seasons.html app/templates/admin/season_form.html app/templates/admin/events.html app/templates/admin/event_form.html app/templates/admin/newsletter_prompts.html
git commit -m "style(admin): apply the spacing scale to catalog surfaces"
gh pr create --title "Admin UI polish 6/6: catalog" --body "..."
```

---

### Task 14: Final verification sweep

**Files:**
- Modify: `docs/superpowers/notes/2026-07-28-admin-ui-findings.md`

- [ ] **Step 1: Full re-capture against the finished branch**

```bash
scripts/ui_audit/run.sh final --seed
```

- [ ] **Step 2: Confirm every finding is closed**

Walk the findings inventory. Mark each row `fixed`, `deferred`, or `flagged-for-user` (the last for anything that would have required moving an element — a stated non-goal). Every high-severity row must be `fixed`.

- [ ] **Step 3: Confirm no residual hardcoded spacing**

```bash
grep -nE "(padding|margin|gap): *[0-9]+px" app/static/css/admin_ui.css
```
Expected: no output, other than values inside `@media` blocks that intentionally use `env(safe-area-inset-*)` arithmetic.

- [ ] **Step 4: Confirm nothing left the machine**

```bash
grep -rn "BLOCKED\|OutboundBlocked" .ui-audit/*/  2>/dev/null | head
```
Expected: no `BLOCKED` lines from any capture run. If any appear, identify which manifest selector triggered a mutating request and confirm from the app logs that it was aborted in-browser and never reached the server.

- [ ] **Step 5: Confirm no Codex agent escaped its scope**

Each agent was restricted to its group's files. Verify across the whole branch that nothing outside the declared scopes changed:

```bash
git diff --stat main...admin-ui-spacing-polish -- . ':!docs' ':!scripts/ui_audit'
```
Expected: only `app/static/css/admin_ui.css`, `app/static/admin_*.js`, and `app/templates/admin/**`. Anything else was written by an agent that exceeded its scope and must be reviewed individually before it ships.

- [ ] **Step 6: Tear down the agent worktrees**

```bash
cd /workspace/tcsc-trips
for group in members payments slack practices catalog; do
  git worktree remove --force ".worktrees/ui-$group"
done
git worktree prune
git worktree list
```
Expected: only the main checkout remains.

- [ ] **Step 7: Commit the closed inventory**

```bash
git add docs/superpowers/notes/2026-07-28-admin-ui-findings.md
git commit -m "docs(ui-audit): close out the spacing polish findings"
```

---

## Self-Review

**Spec coverage:** Phase 1 → Tasks 3–5. Phase 2 → Tasks 1, 2, 6. Phase 3 → Task 7. Phase 4 layer A → Task 8 Steps 2–3; layer B → Task 8 Step 4 plus Tasks 9–13. Phase 5 → per-task verify steps plus Task 14. All four outbound safety layers appear: env isolation and `TCSC_MIGRATION_ONLY` in Task 2, socket guard in Task 1, non-GET abort in Task 6.

**Division of labour:** Tasks 1–8 and 14 are done by the orchestrator directly — they are harness, safety, and the shared spacing scale, where a mistake corrupts everything downstream. Tasks 9–13, the five surface-group fix passes, are performed by Codex `gpt-5.6-sol` agents at max reasoning effort, one per group, running concurrently in isolated worktrees. Every agent diff is reviewed, re-captured, and committed by the orchestrator; no agent commits or opens a PR. See the Codex Execution Model section.

**Deviation from spec:** the spec called for a single `ui-polish` git worktree for env isolation. That is achieved instead by `.env.uiaudit` + `load_dotenv(override=True)`, so the main checkout is used for Tasks 1–8. Worktrees reappear in Tasks 9–13 for a different reason — isolating five concurrent Codex agents from each other, since they run unattended with `approval_policy = "never"`.

**Verified while writing:** `db` is defined at `app/models.py:8` and imported from there. Blueprint prefixes confirmed — `/admin/practices`, `/admin/skipper`, `/admin/newsletter`, `/admin/availability` carry `url_prefix`; `admin_events_bp` declares absolute paths. All manifest paths correspond to real GET routes. `admin_required` gates on email domain only, so the minted cookie is sufficient. Playwright 1.62 and Chromium are installed globally; the repo venv is `.venv-linux`.

**Known gaps to resolve during execution:** Task 5 Step 1 requires reading the domain models before writing that half of the seed, since their columns are not enumerated here — that is a deliberate read-first step, not a placeholder. Task 6's manifest selectors are guesses that Task 7 Step 1 replaces with real ones found by grepping the templates and JS; Task 6 is not complete without Task 7.

**Convention risk worth watching:** `tests/_db_guard.py` enforces local-only database access and `tests/conftest.py` has an autouse `_enforce_local_db` fixture. The seed tests create a new database (`tcsc_trips_uiaudit_test`), which may need allowlisting. Task 4 Step 4 notes this.
