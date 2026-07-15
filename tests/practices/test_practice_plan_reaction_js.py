from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def test_admin_practice_reaction_javascript_suite():
    result = subprocess.run(
        ["npm", "run", "test:practice-reactions"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
