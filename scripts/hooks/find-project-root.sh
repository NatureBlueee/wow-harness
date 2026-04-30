#!/bin/bash
# Walks up from $PWD to find the wow-harness-installed project root.
#
# Anchor priority:
#   1. .wow-harness/MANIFEST.yaml  (primary — declared by installer)
#   2. CLAUDE.md                   (fallback — older projects or pre-install)
#
# Why not scripts/guard-feedback.py like the old towow-specific script?
# Because that created a circular dependency: guard-feedback.py was both
# the anchor AND the target invoked by the hook. Projects that don't ship
# guard-feedback.py (because they disabled it via issue-adapter.yaml) would
# fail to locate their own root. The MANIFEST anchor is independent of any
# specific hook installation.
#
# Prints absolute project root to stdout. Exits 1 if not found.
set -e
d="${PWD}"
while [ "$d" != "/" ] && [ -n "$d" ]; do
  if [ -f "$d/.wow-harness/MANIFEST.yaml" ]; then
    echo "$d"
    exit 0
  fi
  d="$(dirname "$d")"
done

# Fallback 1: walk up again looking for CLAUDE.md alone
d="${PWD}"
while [ "$d" != "/" ] && [ -n "$d" ]; do
  if [ -f "$d/CLAUDE.md" ]; then
    echo "$d"
    exit 0
  fi
  d="$(dirname "$d")"
done

# Fallback 2: CLAUDE_PROJECT_DIR env var set by Claude Code
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  if [ -f "${CLAUDE_PROJECT_DIR}/.wow-harness/MANIFEST.yaml" ] || [ -f "${CLAUDE_PROJECT_DIR}/CLAUDE.md" ]; then
    echo "${CLAUDE_PROJECT_DIR}"
    exit 0
  fi
fi

# Fail-closed: no hardcoded machine-specific path. If you reach here the
# project is either not yet installed or CLAUDE_PROJECT_DIR is unset —
# both cases should surface as an error to the hook caller.
exit 1
