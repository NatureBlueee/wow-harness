#!/bin/sh
# 起草 ADR / PLAN 时给出下一个可用号（与 pre-commit numbering check 对齐）.
#
# 用法:
#   scripts/checks/next_decision_number.sh ADR
#   scripts/checks/next_decision_number.sh PLAN
#
# 来源: H 系列收尾 + Nature feedback "plan/adr 序号老是容易重复".

set -e

KIND="${1:-}"
case "$KIND" in
    ADR|PLAN) ;;
    *)
        echo "Usage: $0 {ADR|PLAN}" >&2
        exit 2
        ;;
esac

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    echo "Not in a git repo." >&2
    exit 2
fi

cd "$REPO_ROOT"

DECISIONS_DIR="docs/decisions"
if [ ! -d "$DECISIONS_DIR" ]; then
    echo "No $DECISIONS_DIR/ found." >&2
    exit 2
fi

# 取所有非 H 系列 ADR/PLAN-NNN 主号（剥落字母 sub-id），找最大值 +1
MAX=$(ls "$DECISIONS_DIR" 2>/dev/null \
    | grep -E "^${KIND}-[0-9]{3}[A-Z]?-" \
    | grep -vE '^(ADR|PLAN)-H[0-9]+-' \
    | sed -E "s/^${KIND}-([0-9]{3})[A-Z]?-.*/\1/" \
    | sort -n | tail -1)

if [ -z "$MAX" ]; then
    NEXT=1
else
    NEXT=$((10#$MAX + 1))
fi

printf "%s-%03d\n" "$KIND" "$NEXT"
