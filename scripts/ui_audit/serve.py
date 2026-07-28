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
