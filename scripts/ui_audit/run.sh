#!/usr/bin/env bash
# scripts/ui_audit/run.sh -- build CSS, serve the app sealed off, capture, tear down.
# Usage: scripts/ui_audit/run.sh <label>
#
# Environment:
#   TCSC_UI_AUDIT_ONLY   comma-separated surface and/or group names; capture only
#                        those, leaving the rest of <label> as it was. A full run
#                        is ~11 minutes, a single surface about three.
#   TCSC_UI_AUDIT_EMAIL  the admin identity the session cookie is minted for.
#                        Defaults to a FINANCE_AUTHORIZED_EMAILS address so
#                        payment amounts render. Only two addresses are on that
#                        allowlist, so most real admins see a structurally
#                        different payments page -- no bulk-bar sum element, and
#                        narrower em-dash amount cells on mobile where
#                        .pw-row-amount drops to min-width:0. Capture that
#                        variant as its own labelled pass:
#
#   TCSC_UI_AUDIT_ONLY=payments \
#     TCSC_UI_AUDIT_EMAIL=uiaudit@twincitiesskiclub.org \
#     scripts/ui_audit/run.sh before-nonfinance
#
#                        A separate label rather than a suffixed state name: the
#                        two passes are two different admin identities, not two
#                        states of one, and keeping them in separate directories
#                        means neither run's index.json can claim to describe
#                        the other's captures.
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

# Start the label directory empty. Without this, a run after a manifest edit
# leaves PNGs for renamed or removed states sitting next to the new ones, absent
# from index.json -- and triage is done by browsing this directory, so those
# orphans get reviewed as if they were current.
#
# Not done for a subset run: that would delete the surfaces this run is not
# recapturing. capture.mjs removes exactly the selected surfaces' PNGs instead,
# and carries the rest of index.json forward.
if [[ -z "${TCSC_UI_AUDIT_ONLY:-}" ]]; then
  rm -rf ".ui-audit/$LABEL"
fi

# The admin UI is unstyled without this; tailwind-output.css is 0 bytes in the
# tree because build output is not committed.
npm run tailwind:build

# Chromium in ~/.cache/ms-playwright cannot start on this box until its shared
# libraries are staged. No-op once the sysroot exists.
SYSROOT="$(scripts/ui_audit/browser_deps.sh)"
export LD_LIBRARY_PATH="$SYSROOT/usr/lib/x86_64-linux-gnu:$SYSROOT/lib/x86_64-linux-gnu:$SYSROOT/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# The same sysroot holds the fonts. Without this, fontconfig only sees the
# image's six DejaVu faces, none of which has emoji coverage, and every emoji in
# the admin UI captures as a tofu box -- a box whose intrinsic width is not the
# glyph's, so spacing triaged against it is triaged against the wrong pixels.
export FONTCONFIG_FILE="$SYSROOT/fonts.conf"
if ! FONTCONFIG_FILE="$FONTCONFIG_FILE" fc-list ':charset=1f3f7' family 2>/dev/null | grep -qi emoji; then
  echo "no emoji-capable font visible to fontconfig; captures would show tofu boxes" >&2
  exit 1
fi

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
