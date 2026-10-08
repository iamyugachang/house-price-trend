#!/bin/bash
# Weekly refresh of house-price-trend GH Pages data (market_grid -> JSON -> push).
# Silent on success (no data change or clean push); nonzero exit + stderr on failure.
set -uo pipefail

REPO="$HOME/workspace/house-price-trend"
PY="$HOME/workspace/tw-house-daily/.venv/bin/python"

cd "$REPO" || { echo "repo not found"; exit 1; }

# 1) regenerate JSON (quiet)
if ! "$PY" scripts/export_trend_data.py >/tmp/hpt_export.log 2>&1; then
  echo "export failed:"; cat /tmp/hpt_export.log; exit 1
fi

# 2) commit + push only when data actually changed
if ! git diff --quiet -- docs/data; then
  git add docs/data
  git -c user.name="iamyugachang" -c user.email="iamyugachang@gmail.com" \
      commit -qm "data refresh $(date '+%Y-%m-%d %H:%M')"
  if ! git push -q origin main 2>/tmp/hpt_push.log; then
    echo "push failed:"; cat /tmp/hpt_push.log; exit 1
  fi
fi
exit 0
