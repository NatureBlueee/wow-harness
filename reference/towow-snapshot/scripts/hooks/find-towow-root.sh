#!/bin/bash
# Walks up from $PWD to find the Towow repo root.
# Identifies it by presence of BOTH CLAUDE.md and scripts/guard-feedback.py.
# This handles nested git repos (e.g. towow-progress/) that would confuse
# `git rev-parse --show-toplevel`.
#
# Prints the absolute path to stdout. Exits 1 if not found.
set -e
d="${PWD}"
while [ "$d" != "/" ] && [ -n "$d" ]; do
  if [ -f "$d/CLAUDE.md" ] && [ -f "$d/scripts/guard-feedback.py" ]; then
    echo "$d"
    exit 0
  fi
  d="$(dirname "$d")"
done
# Fallback: check if CLAUDE_PROJECT_DIR is set by Claude Code
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -f "${CLAUDE_PROJECT_DIR}/scripts/guard-feedback.py" ]; then
  echo "${CLAUDE_PROJECT_DIR}"
  exit 0
fi
# Final hardcoded fallback (this machine)
if [ -f "/Users/nature/个人项目/Towow/scripts/guard-feedback.py" ]; then
  echo "/Users/nature/个人项目/Towow"
  exit 0
fi
exit 1
