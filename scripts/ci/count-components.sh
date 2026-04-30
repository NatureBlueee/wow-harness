#!/bin/bash
# count-components.sh — WP-03 AC 1 primary judge + WP-SEC-1 meta-self-check.
#
# Emits three lines that WP-SEC-1 CI asserts against MANIFEST.yaml:
#   command_instances=<N>   # count of "command": entries in .claude/settings.json
#   unique_scripts=<N>      # deduped scripts referenced by those commands
#   physical_files=<N>      # hook + root-script files on disk (L1 registry)
#
# Meta-self-check (§13.5 INV-4 activation 5):
#   After set -e, the script verifies (a) its own file still exists, and
#   (b) .github/workflows/ci.yml — if present — still references this script
#   by name. If either check fails, exit 2 with the message
#   "count-components.sh meta-self-check failed: the chokepoint itself is vapor".
#
# Run from repo root. Reads .claude/settings.json, scripts/hooks/, scripts/.

set -e

# --- meta-self-check ---------------------------------------------------------
SELF_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
test -f "${SELF_PATH}" || {
  echo "count-components.sh meta-self-check failed: the chokepoint itself is vapor" >&2
  exit 2
}

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CI_WORKFLOW="${REPO_ROOT}/.github/workflows/ci.yml"
if [ -f "${CI_WORKFLOW}" ] && ! grep -q 'count-components.sh' "${CI_WORKFLOW}"; then
  echo "count-components.sh meta-self-check failed: the chokepoint itself is vapor" >&2
  exit 2
fi
# -----------------------------------------------------------------------------

cd "${REPO_ROOT}"

# command_instances: every "command" key in settings.json's hooks[]
# Count the total commands across all hook stages.
if command -v jq >/dev/null 2>&1; then
  CMD_INSTANCES=$(jq '[
    .hooks.PreToolUse[]?.hooks[]?,
    .hooks.PostToolUse[]?.hooks[]?,
    .hooks.PostToolBatch[]?.hooks[]?,
    .hooks.PreCompact[]?.hooks[]?,
    .hooks.SessionStart[]?.hooks[]?,
    .hooks.SessionEnd[]?.hooks[]?,
    .hooks.Stop[]?.hooks[]?,
    .hooks.PostToolUseFailure[]?.hooks[]?,
    .hooks.UserPromptSubmit[]?.hooks[]?,
    .hooks.WorktreeCreate[]?.hooks[]?
  ] | length' .claude/settings.json)
else
  # Fallback: line-grep. Less precise but works without jq.
  CMD_INSTANCES=$(grep -c '"command":' .claude/settings.json || echo 0)
fi

# unique_scripts: distinct hook scripts referenced by those commands.
# Two forms:
#   bash scripts/lib/run-py.sh scripts/X/Y.py  → extract token after run-py.sh
#   python3|bash scripts/X/Y.py                → extract the scripts/ token directly
UNIQUE_SCRIPTS=$(
  {
    grep '"command":' .claude/settings.json \
      | grep 'run-py\.sh' \
      | grep -oE 'run-py\.sh scripts/[^ "\\]+' \
      | sed 's|run-py\.sh ||'
    grep '"command":' .claude/settings.json \
      | grep -v 'run-py\.sh' \
      | grep -oE '(python3|bash) scripts/[^ "\\]+' \
      | awk '{print $2}'
  } | sort -u | wc -l | tr -d ' '
)

# physical_files: hooks dir + 2 root scripts
HOOKS_COUNT=$(ls scripts/hooks/*.py scripts/hooks/*.sh scripts/hooks/*.md 2>/dev/null | wc -l | tr -d ' ')
ROOT_COUNT=$(ls scripts/guard-feedback.py scripts/deploy-guard.py 2>/dev/null | wc -l | tr -d ' ')
PHYSICAL=$((HOOKS_COUNT + ROOT_COUNT))

echo "command_instances=${CMD_INSTANCES}"
echo "unique_scripts=${UNIQUE_SCRIPTS}"
echo "physical_files=${PHYSICAL}"
