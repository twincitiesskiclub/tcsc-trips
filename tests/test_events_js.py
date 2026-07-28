"""Run the events registration JavaScript suite from pytest.

Mirrors tests/practices/test_practice_plan_reaction_js.py so the jsdom
coverage for per-option question scoping runs with the Python suite.
"""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_events_javascript_suite():
    result = subprocess.run(
        ["npm", "run", "test:events"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
