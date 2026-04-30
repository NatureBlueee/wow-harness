#!/usr/bin/env bash
# /mode shadow-review — operator-invoked force-emit of .towow/metrics/shadow-ready.json.
#
# Usage: `/mode shadow-review` (maps to `bash <plugin-root>/skills/mode/shadow-review.sh`).
# Runs `shadow-saturation.py --manual` which skips S1/S2 coverage checks but still enforces the
# hard lower bound (>= 2 non-legacy modes observed). Used when the operator has reviewed
# router-shadow.jsonl by hand and wants to close WP-016 without waiting for auto-saturation.
#
# WP-038 note: this handler now lives 4 dirs deep inside the plugin; the pre-WP-038 hard-coded
# `../../..` depth no longer reaches the repo root. Use find-towow-root.sh for deterministic
# source-tree-independent root resolution.
set -euo pipefail
ROOT="$(cd "$(/Users/nature/个人项目/Towow/scripts/hooks/find-towow-root.sh)" && pwd)"
exec python3 "$ROOT/scripts/hooks/shadow-saturation.py" --manual "$@"
