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
# boot today; this makes the guarantee structural instead of depending on that
# enumeration staying exhaustive: find_dotenv() can never locate the real .env
# at all, so there is nothing for the fallback load_dotenv() to discover.
dotenv.find_dotenv = lambda *args, **kwargs: ""

from app import create_app  # noqa: E402  (must follow the guard + env load + find_dotenv patch)
from scripts.ui_audit.session_cookie import mint_admin_cookie  # noqa: E402


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5055
    app = create_app()
    name, value = mint_admin_cookie(app)
    print(json.dumps({"cookie_name": name, "cookie_value": value, "port": port}), flush=True)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
