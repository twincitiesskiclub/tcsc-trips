#!/usr/bin/env bash
# scripts/ui_audit/run.sh -- build CSS, serve the app sealed off, capture, tear down.
# Usage: scripts/ui_audit/run.sh <label>
#
# The database is seeded exactly once, by hand, via scripts/ui_audit/seed_fixtures.py.
# This script deliberately has no --seed flag: seed_all() anchors practice, poll and
# event dates to today_central(), so re-seeding shifts which practices are cancelled,
# which fall in the draft block, and what the calendar renders. Those shifts show up
# in every later before/after comparison looking exactly like spacing changes.
set -euo pipefail
cd "$(dirname "$0")/../.."

LABEL="${1:?usage: run.sh <label>}"
PORT="${TCSC_UI_AUDIT_PORT:-5055}"

mkdir -p .ui-audit

# The admin UI is unstyled without this; tailwind-output.css is 0 bytes in the
# tree because build output is not committed.
npm run tailwind:build

# Chromium in ~/.cache/ms-playwright cannot start on this box until its shared
# libraries are staged. No-op once the sysroot exists.
SYSROOT="$(scripts/ui_audit/browser_deps.sh)"
export LD_LIBRARY_PATH="$SYSROOT/usr/lib/x86_64-linux-gnu:$SYSROOT/lib/x86_64-linux-gnu:$SYSROOT/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

rm -f .ui-audit/server.json
# The request log goes to a file: at ~250 captures it is thousands of lines, and
# interleaved on the terminal it buries the SKIP/BLOCKED lines that matter.
PYTHONPATH="$PWD" .venv-linux/bin/python -m scripts.ui_audit.serve "$PORT" \
  > .ui-audit/server.json 2> .ui-audit/server.log &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  [[ -s .ui-audit/server.json ]] && break
  sleep 1
done
if [[ ! -s .ui-audit/server.json ]]; then
  echo "server did not start; the traceback is in .ui-audit/server.log" >&2
  exit 1
fi

NODE_PATH="$(npm root -g)" node scripts/ui_audit/capture.mjs "$LABEL" "$(head -1 .ui-audit/server.json)"
