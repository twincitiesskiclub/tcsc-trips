#!/bin/bash
# usage: bash scripts/brand-review/ledger-rows.sh <workstream>  -> prints the open ledger blocks for that workstream
ws=$1
awk -v ws="$ws" '
  /^## rejected/ {exit}
  /^### L-/ {if (blk && keep) printf "%s\n", blk; blk=$0 "\n"; keep=0; next}
  blk {blk=blk $0 "\n"; if ($0 ~ "^- workstream: " ws "$") keep=1}
  END {if (blk && keep) printf "%s\n", blk}
' "$(dirname "$0")/../../docs/superpowers/specs/2026-08-31-site-brand-review/ledger.md"
