#!/bin/bash
# usage: bash scripts/brand-review/run-codex.sh <workstream>
# creates .worktrees/brand-<ws> on branch brand/<ws> from site/brand-review and launches codex
# (gpt-5.6-sol, reasoning max) there in the background. prompt goes on stdin; a file argument does not work.
set -euo pipefail
ws=$1
root=$(cd "$(dirname "$0")/../.." && pwd)
wt=$root/.worktrees/brand-$ws
prompt=$root/docs/superpowers/specs/2026-08-31-site-brand-review/prompts/codex-$ws.md
logdir=${CODEX_LOG_DIR:-/tmp/claude-1000/-workspace-tcsc-trips/01b754ce-3776-4a27-884c-aa04e26de682/scratchpad}
log=$logdir/codex-$ws.log

[ -f "$prompt" ] || { echo "no prompt: $prompt"; exit 1; }
mkdir -p "$logdir"
cd "$root"
if [ ! -d "$wt" ]; then
  git worktree add -b "brand/$ws" "$wt" site/brand-review
fi
[ -e "$wt/site/node_modules" ] || ln -s "$root/site/node_modules" "$wt/site/node_modules"
[ -e "$wt/scripts/brand-review/node_modules" ] || ln -s "$root/scripts/brand-review/node_modules" "$wt/scripts/brand-review/node_modules"

echo "launching codex for $ws in $wt, log: $log"
nohup codex exec -C "$wt" -c model_reasoning_effort="max" - < "$prompt" > "$log" 2>&1 &
echo $! > "$log.pid"
echo "pid $(cat "$log.pid")"
# record the session id once codex prints its header ("session id: <uuid>"), for resume-codex.sh
( for i in $(seq 1 60); do sid=$(grep -m1 -oE 'session id: [0-9a-f-]+' "$log" | awk '{print $3}'); [ -n "$sid" ] && { echo "$ws $sid" >> "$logdir/codex-sessions.txt"; exit 0; }; sleep 5; done ) &
