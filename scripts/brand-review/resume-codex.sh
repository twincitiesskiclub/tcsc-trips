#!/bin/bash
# usage: bash scripts/brand-review/resume-codex.sh <workstream> ["extra instruction"]
# resumes the codex session recorded in $logdir/codex-sessions.txt for that workstream, in its worktree.
set -euo pipefail
ws=$1
extra=${2:-}
root=$(cd "$(dirname "$0")/../.." && pwd)
wt=$root/.worktrees/brand-$ws
logdir=${CODEX_LOG_DIR:-/tmp/claude-1000/-workspace-tcsc-trips/01b754ce-3776-4a27-884c-aa04e26de682/scratchpad}
sid=$(awk -v ws="$ws" '$1==ws {print $2}' "$logdir/codex-sessions.txt" | tail -1)
[ -n "$sid" ] || { echo "no session id for $ws"; exit 1; }
log=$logdir/codex-$ws.log
msg="your session was interrupted and has been resumed. continue exactly where you left off. first run \`git status --short\` and \`git log --oneline site/brand-review..HEAD\` in your worktree to see what you already committed and what is still uncommitted; commit any clean uncommitted work with the ledger id it belongs to before continuing. then work through your remaining ledger rows, run the five test/build commands, take your after screenshots, write your report, and commit it. do not redo rows you already committed. $extra"
echo "resuming $ws session $sid in $wt, log: $log"
# -c must precede the resume subcommand; resume takes no -C, so cd into the worktree
(cd "$wt" && nohup codex exec -c model_reasoning_effort="max" resume "$sid" "$msg" >> "$log" 2>&1 &
echo $! > "$log.pid")
sleep 1
echo "pid $(cat "$log.pid")"
