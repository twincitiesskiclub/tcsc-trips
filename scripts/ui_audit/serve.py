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

import dotenv
import dotenv.main
from dotenv import load_dotenv

from scripts.ui_audit.outbound_guard import install_outbound_guard

# Order matters: the guard is installed before the app is imported so that no
# import-time client can open a connection.
install_outbound_guard()

# The audit env deliberately replaces the real .env -- real tokens are never
# loaded into this process.
load_dotenv(Path(__file__).resolve().parents[2] / ".env.uiaudit", override=True)
os.environ["TCSC_MIGRATION_ONLY"] = "1"  # no APScheduler, no Slack Socket Mode

# app/config.py's load_stripe_config() calls load_dotenv(find_dotenv()) with
# override=False *inside* create_app(), after the override=True load above.
# override=False only fills in keys not already set, so any credential this
# process doesn't already have -- because .env.uiaudit's enumeration missed a
# key the real .env later grew -- would otherwise be silently backfilled with
# the real value. Enumerating every key defends against what the app needs to
# boot today; this patch makes the specific two-step call pattern
# load_dotenv(find_dotenv()) structurally unable to find the real .env,
# instead of depending on that enumeration staying exhaustive.
#
# Two bindings must both be patched, not one: `dotenv.find_dotenv` is the
# package-level re-export that code doing `from dotenv import find_dotenv`
# (app/config.py's pattern) picks up. `dotenv.main.find_dotenv` is the
# separate, original binding that dotenv.main.load_dotenv() resolves against
# its own module globals internally -- when called bare, with no arguments,
# it calls find_dotenv() itself to locate a path. Patching only the
# package-level name leaves that bare-call path free to discover the real
# .env. This covers both; it does not make every possible way to reach a .env
# file safe (e.g. an explicit hardcoded path would still work) -- only calls
# that go through find_dotenv() resolution.
dotenv.main.find_dotenv = dotenv.find_dotenv = lambda *args, **kwargs: ""

from app import create_app  # noqa: E402  (must follow the guard + env load + find_dotenv patch)
from scripts.ui_audit.session_cookie import (  # noqa: E402
    audit_admin_email,
    mint_admin_cookie,
)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5055
    app = create_app()
    name, value = mint_admin_cookie(app)
    # The identity travels with the handshake so capture.mjs can record it in
    # index.json. Which admin took a screenshot is part of what the screenshot
    # means -- the payments page renders a different DOM for a finance-authorised
    # admin than for anyone else.
    print(
        json.dumps(
            {
                "cookie_name": name,
                "cookie_value": value,
                "port": port,
                "admin_email": audit_admin_email(),
            }
        ),
        flush=True,
    )
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
