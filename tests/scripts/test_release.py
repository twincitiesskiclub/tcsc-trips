import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "scripts" / "release.sh"


def test_release_runs_upgrade_with_migration_only_and_blank_slack_environment(
    tmp_path,
):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_flask = fake_bin / "flask"
    fake_flask.write_text(
        """#!/bin/sh
{
  printf 'argv=%s\\n' "$*"
  printf 'migration_only=%s\\n' "${TCSC_MIGRATION_ONLY-unset}"
  printf 'bot=%s\\n' "${SLACK_BOT_TOKEN-unset}"
  printf 'app=%s\\n' "${SLACK_APP_TOKEN-unset}"
  printf 'signing=%s\\n' "${SLACK_SIGNING_SECRET-unset}"
} >> "$TCSC_RELEASE_CAPTURE"
""",
        encoding="utf-8",
    )
    fake_flask.chmod(0o755)
    capture = tmp_path / "release-environment.txt"
    environment = os.environ.copy()
    environment.update({
        "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
        "TCSC_RELEASE_CAPTURE": str(capture),
        "TCSC_MIGRATION_ONLY": "0",
        "SLACK_BOT_TOKEN": "must-be-cleared",
        "SLACK_APP_TOKEN": "must-be-cleared",
        "SLACK_SIGNING_SECRET": "must-be-cleared",
    })

    result = subprocess.run(
        ["bash", str(RELEASE)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "argv=db upgrade",
        "migration_only=1",
        "bot=",
        "app=",
        "signing=",
    ]


def test_migration_only_process_starts_no_background_consumers():
    probe = r"""
import json
from unittest.mock import Mock

import app as app_module
import app.scheduler as scheduler_module
import app.slack.bolt_app as bolt_module

app_module.load_stripe_config = lambda: None
create_all = Mock(side_effect=AssertionError("schema mutation"))
init_scheduler = Mock(side_effect=AssertionError("background startup"))
app_module.db.create_all = create_all
app_module.init_scheduler = init_scheduler
application = app_module.create_app()
print(json.dumps({
    "create_all_calls": create_all.call_count,
    "scheduler_calls": init_scheduler.call_count,
    "migrate_registered": "migrate" in application.extensions,
    "bolt_enabled": bolt_module.is_bolt_enabled(),
    "socket_available": bolt_module.is_socket_mode_available(),
    "socket_running": bolt_module.is_socket_mode_running(),
    "scheduler_running": scheduler_module.scheduler.running,
}))
"""
    environment = os.environ.copy()
    environment.update({
        "DATABASE_URL": (
            "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
        ),
        "FLASK_SECRET_KEY": "release-process-test-secret",
        "TCSC_MIGRATION_ONLY": "1",
        "SLACK_BOT_TOKEN": "",
        "SLACK_APP_TOKEN": "",
        "SLACK_SIGNING_SECRET": "",
    })

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    state = json.loads(result.stdout.strip().splitlines()[-1])
    assert state == {
        "create_all_calls": 0,
        "scheduler_calls": 0,
        "migrate_registered": True,
        "bolt_enabled": False,
        "socket_available": False,
        "socket_running": False,
        "scheduler_running": False,
    }
