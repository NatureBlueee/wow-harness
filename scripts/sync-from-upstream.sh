#!/bin/bash
# sync-from-upstream.sh — Sync hook files from Towow (upstream) to wow-harness.
#
# Purpose: Towow is the development/incubation repo where hooks are written
# and tested. This script copies updated hooks to wow-harness and reports
# any discrepancies in settings.json hook registrations.
#
# What it does:
#   1. Copy shared hook scripts from Towow → wow-harness (skip Towow-only files)
#   2. Replace find-towow-root.sh references → find-project-root.sh in copied files
#   3. Compare settings.json hook registrations and report differences
#   4. Sync shared scripts (guard-feedback.py, deploy-guard.py, context_router.py, guard_router.py)
#   5. Sync context-fragments/ directory
#
# Usage:
#   ./scripts/sync-from-upstream.sh                     # default Towow path
#   ./scripts/sync-from-upstream.sh /path/to/Towow      # explicit upstream path
#   ./scripts/sync-from-upstream.sh --dry-run            # show what would change

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HARNESS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
UPSTREAM_DEFAULT="$(cd "$HARNESS_ROOT/../Towow" 2>/dev/null && pwd || echo "")"

# Parse args
DRY_RUN=false
UPSTREAM=""

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        *) UPSTREAM="$arg" ;;
    esac
done

if [ -z "$UPSTREAM" ]; then
    UPSTREAM="$UPSTREAM_DEFAULT"
fi

if [ -z "$UPSTREAM" ] || [ ! -d "$UPSTREAM/scripts/hooks" ]; then
    echo "ERROR: Cannot find upstream Towow repo."
    echo "Usage: $0 [--dry-run] [/path/to/Towow]"
    exit 1
fi

echo "=== wow-harness sync-from-upstream ==="
echo "Upstream: $UPSTREAM"
echo "Target:   $HARNESS_ROOT"
echo "Dry run:  $DRY_RUN"
echo ""

# ─── Files that exist only in Towow (not synced) ───
TOWOW_ONLY=(
    "find-towow-root.sh"  # Towow-specific root finder
)

# ─── Files that exist only in wow-harness (not overwritten) ───
HARNESS_ONLY=(
    "find-project-root.sh"  # Generic root finder
    "sanitize-on-read.py"   # WP-11 addition
)

# ─── Step 1: Copy shared hooks ───
echo "── Step 1: Sync hook scripts ──"
COPIED=0
SKIPPED=0
UNCHANGED=0

for src_file in "$UPSTREAM/scripts/hooks/"*; do
    [ -f "$src_file" ] || continue  # skip directories (e.g. __pycache__)
    filename="$(basename "$src_file")"

    # Skip Towow-only files
    skip=false
    for excl in "${TOWOW_ONLY[@]}"; do
        if [ "$filename" = "$excl" ]; then
            skip=true
            break
        fi
    done
    if $skip; then
        echo "  SKIP (Towow-only): $filename"
        ((SKIPPED++))
        continue
    fi

    # Skip harness-only files (don't overwrite)
    for excl in "${HARNESS_ONLY[@]}"; do
        if [ "$filename" = "$excl" ]; then
            skip=true
            break
        fi
    done
    if $skip; then
        echo "  SKIP (harness-only): $filename"
        ((SKIPPED++))
        continue
    fi

    dst_file="$HARNESS_ROOT/scripts/hooks/$filename"

    # Check if content differs
    if [ -f "$dst_file" ]; then
        if diff -q "$src_file" "$dst_file" > /dev/null 2>&1; then
            ((UNCHANGED++))
            continue
        fi
    fi

    if $DRY_RUN; then
        echo "  WOULD COPY: $filename"
    else
        cp "$src_file" "$dst_file"
        echo "  COPIED: $filename"
    fi
    ((COPIED++))
done

echo ""
echo "  Results: $COPIED copied, $SKIPPED skipped, $UNCHANGED unchanged"

# ─── Step 2: Replace find-towow-root.sh references ───
echo ""
echo "── Step 2: Path references ──"
PATCHED=0

for hook_file in "$HARNESS_ROOT/scripts/hooks/"*.py "$HARNESS_ROOT/scripts/hooks/"*.sh; do
    [ -f "$hook_file" ] || continue
    filename="$(basename "$hook_file")"

    # Skip harness-only files
    skip=false
    for excl in "${HARNESS_ONLY[@]}"; do
        if [ "$filename" = "$excl" ]; then
            skip=true
            break
        fi
    done
    if $skip; then continue; fi

    if grep -q "find-towow-root.sh" "$hook_file" 2>/dev/null; then
        if $DRY_RUN; then
            echo "  WOULD PATCH: $filename (find-towow-root.sh → find-project-root.sh)"
        else
            # Use perl for reliable in-place replace (macOS sed -i differs from GNU)
            perl -pi -e 's/find-towow-root\.sh/find-project-root.sh/g' "$hook_file"
            echo "  PATCHED: $filename"
        fi
        ((PATCHED++))
    fi
done

if [ "$PATCHED" -eq 0 ]; then
    echo "  No path references to patch"
fi

# ─── Step 3: Compare settings.json hook registrations ───
echo ""
echo "── Step 3: Hook registration diff ──"

# Extract hook script names from settings.json
extract_hooks() {
    python3 -c "
import json, sys
with open('$1') as f:
    d = json.load(f)
hooks = []
for stage, entries in d.get('hooks', {}).items():
    for entry in entries:
        matcher = entry.get('matcher', '*')
        for h in entry.get('hooks', []):
            cmd = h.get('command', '')
            # Extract script name
            for part in reversed(cmd.split()):
                if part.endswith(('.py', '.sh')):
                    hooks.append(f'{stage}|{matcher}|{part.split(\"/\")[-1]}')
                    break
for h in sorted(set(hooks)): print(h)
" 2>/dev/null
}

UPSTREAM_HOOKS=$(extract_hooks "$UPSTREAM/.claude/settings.json")
HARNESS_HOOKS=$(extract_hooks "$HARNESS_ROOT/.claude/settings.json")

# Find hooks only in upstream
ONLY_UPSTREAM=$(comm -23 <(echo "$UPSTREAM_HOOKS") <(echo "$HARNESS_HOOKS"))
ONLY_HARNESS=$(comm -13 <(echo "$UPSTREAM_HOOKS") <(echo "$HARNESS_HOOKS"))

if [ -n "$ONLY_UPSTREAM" ]; then
    echo "  ⚠ Only in Towow (missing from wow-harness):"
    echo "$ONLY_UPSTREAM" | while IFS='|' read -r stage matcher script; do
        echo "    $stage $matcher: $script"
    done
fi

if [ -n "$ONLY_HARNESS" ]; then
    echo "  ℹ Only in wow-harness (expected for harness-specific hooks):"
    echo "$ONLY_HARNESS" | while IFS='|' read -r stage matcher script; do
        echo "    $stage $matcher: $script"
    done
fi

if [ -z "$ONLY_UPSTREAM" ] && [ -z "$ONLY_HARNESS" ]; then
    echo "  ✓ Hook registrations in sync"
fi

# ─── Step 4: Check for other synced files ───
echo ""
echo "── Step 4: Other shared files ──"

# Scripts in scripts/ root that are shared with Towow
for shared_file in "guard-feedback.py" "deploy-guard.py" "context_router.py" "guard_router.py"; do
    src="$UPSTREAM/scripts/$shared_file"
    dst="$HARNESS_ROOT/scripts/$shared_file"
    if [ -f "$src" ] && [ -f "$dst" ]; then
        if ! diff -q "$src" "$dst" > /dev/null 2>&1; then
            if $DRY_RUN; then
                echo "  WOULD COPY: scripts/$shared_file"
            else
                cp "$src" "$dst"
                echo "  COPIED: scripts/$shared_file"
            fi
        fi
    elif [ -f "$src" ] && [ ! -f "$dst" ]; then
        echo "  ⚠ MISSING in harness: scripts/$shared_file"
    fi
done

# ─── Step 5: Sync context-fragments/ directory ───
echo ""
echo "── Step 5: Context fragments ──"
FRAG_COPIED=0
FRAG_UNCHANGED=0

src_frag_dir="$UPSTREAM/scripts/context-fragments"
dst_frag_dir="$HARNESS_ROOT/scripts/context-fragments"

if [ -d "$src_frag_dir" ]; then
    if [ ! -d "$dst_frag_dir" ]; then
        if $DRY_RUN; then
            echo "  WOULD CREATE: scripts/context-fragments/"
        else
            mkdir -p "$dst_frag_dir"
            echo "  CREATED: scripts/context-fragments/"
        fi
    fi

    for src_frag in "$src_frag_dir/"*; do
        [ -f "$src_frag" ] || continue
        frag_name="$(basename "$src_frag")"
        dst_frag="$dst_frag_dir/$frag_name"

        if [ -f "$dst_frag" ]; then
            if diff -q "$src_frag" "$dst_frag" > /dev/null 2>&1; then
                ((FRAG_UNCHANGED++))
                continue
            fi
        fi

        if $DRY_RUN; then
            echo "  WOULD COPY: context-fragments/$frag_name"
        else
            cp "$src_frag" "$dst_frag"
            echo "  COPIED: context-fragments/$frag_name"
        fi
        ((FRAG_COPIED++))
    done

    echo "  Results: $FRAG_COPIED copied, $FRAG_UNCHANGED unchanged"
else
    echo "  ⚠ Upstream context-fragments/ not found"
fi

# ─── Step 6: H series decisions (ADR-Hx + PLAN-Hx) ───
# H 系列治理产物 — 9 站收口 meta-program。脱敏（DP-2=A 推荐）保留
# Nature 作 governance 主体，替换 K/boattosea/EvoMap/SacredPlay 等业务名。
echo ""
echo "── Step 6: H series decisions (ADR-Hx + PLAN-Hx) ──"
H_COPIED=0
H_UNCHANGED=0
H_TOTAL=0

mkdir -p "$HARNESS_ROOT/docs/decisions"

for src in "$UPSTREAM/docs/decisions/"ADR-H*.md "$UPSTREAM/docs/decisions/"PLAN-H*.md; do
    [ -f "$src" ] || continue
    ((H_TOTAL++))
    fname="$(basename "$src")"
    dst="$HARNESS_ROOT/docs/decisions/$fname"

    if [ -f "$dst" ] && diff -q "$src" "$dst" > /dev/null 2>&1; then
        ((H_UNCHANGED++))
        continue
    fi

    if $DRY_RUN; then
        echo "  WOULD COPY: docs/decisions/$fname"
    else
        cp "$src" "$dst"
        # 轻脱敏 (DP-2=A): 业务名 → 通用占位
        perl -pi -e '
            s/kunzhi-coach|自航船/业务场景示例/g;
            s/boattosea/业务集成示例/g;
            s/Sacred Play/Demo 网站/g;
            s/EvoMap/能力图示例/g;
            s/imakemy\.world/example.com/g;
            s|47\.118\.31\.230|<server-ip>|g;
        ' "$dst"
        echo "  COPIED + DESENSITIZED: docs/decisions/$fname"
    fi
    ((H_COPIED++))
done

echo "  Results: $H_COPIED to copy, $H_UNCHANGED unchanged, $H_TOTAL total found upstream"

# ─── Step 7: hanis-protocol rule ───
echo ""
echo "── Step 7: .claude/rules/hanis-protocol.md ──"

src_rule="$UPSTREAM/.claude/rules/hanis-protocol.md"
dst_rule="$HARNESS_ROOT/.claude/rules/hanis-protocol.md"

if [ -f "$src_rule" ]; then
    mkdir -p "$HARNESS_ROOT/.claude/rules"
    if [ -f "$dst_rule" ] && diff -q "$src_rule" "$dst_rule" > /dev/null 2>&1; then
        echo "  ✓ unchanged"
    elif $DRY_RUN; then
        echo "  WOULD COPY: .claude/rules/hanis-protocol.md"
    else
        cp "$src_rule" "$dst_rule"
        echo "  COPIED: .claude/rules/hanis-protocol.md"
    fi
else
    echo "  ⚠ Upstream hanis-protocol.md not found"
fi

# ─── Step 8: H9 inbox schema + 5 hooks ───
echo ""
echo "── Step 8: H9 inbox infrastructure ──"

# 8a. inbox schema
src_schema="$UPSTREAM/.towow/inbox/schema/message-v1.json"
dst_schema_dir="$HARNESS_ROOT/.towow/inbox/schema"
dst_schema="$dst_schema_dir/message-v1.json"

if [ -f "$src_schema" ]; then
    mkdir -p "$dst_schema_dir"
    if [ -f "$dst_schema" ] && diff -q "$src_schema" "$dst_schema" > /dev/null 2>&1; then
        echo "  ✓ schema unchanged"
    elif $DRY_RUN; then
        echo "  WOULD COPY: .towow/inbox/schema/message-v1.json"
    else
        cp "$src_schema" "$dst_schema"
        echo "  COPIED: .towow/inbox/schema/message-v1.json"
    fi
else
    echo "  ⚠ Upstream inbox schema not found at $src_schema"
fi

# 8b. 5 inbox hooks (write-ledger / validate / inject-on-start / poll / ack)
INBOX_HOOKS=(
    "inbox-write-ledger.py"
    "inbox-validate.py"
    "inbox-inject-on-start.py"
    "inbox-poll.sh"
    "inbox-ack.py"
)

INBOX_COPIED=0
INBOX_UNCHANGED=0

for hook_name in "${INBOX_HOOKS[@]}"; do
    src_hook="$UPSTREAM/scripts/hooks/$hook_name"
    dst_hook="$HARNESS_ROOT/scripts/hooks/$hook_name"

    if [ ! -f "$src_hook" ]; then
        echo "  ⚠ Upstream missing: $hook_name"
        continue
    fi

    if [ -f "$dst_hook" ] && diff -q "$src_hook" "$dst_hook" > /dev/null 2>&1; then
        ((INBOX_UNCHANGED++))
        continue
    fi

    if $DRY_RUN; then
        echo "  WOULD COPY: scripts/hooks/$hook_name"
    else
        cp "$src_hook" "$dst_hook"
        # 路径替换在 Step 2 已统一处理（find-towow-root.sh → find-project-root.sh）
        perl -pi -e 's/find-towow-root\.sh/find-project-root.sh/g' "$dst_hook"
        echo "  COPIED + PATCHED: scripts/hooks/$hook_name"
    fi
    ((INBOX_COPIED++))
done

echo "  Results: $INBOX_COPIED to copy, $INBOX_UNCHANGED unchanged"

# ─── Step 9: ADR/PLAN 编号唯一性 chokepoint ───
# pre-commit gate that prevents future ADR/PLAN number collisions.
# 来源: Towow commit dff58afb / docs/issues/guard-20260429-1706-*
echo ""
echo "── Step 9: ADR/PLAN numbering uniqueness ──"

NUMBERING_FILES=(
    "scripts/checks/check_adr_plan_numbering.py"
    "scripts/checks/next_decision_number.sh"
)

NUM_COPIED=0
NUM_UNCHANGED=0

for rel_path in "${NUMBERING_FILES[@]}"; do
    src_num="$UPSTREAM/$rel_path"
    dst_num="$HARNESS_ROOT/$rel_path"

    if [ ! -f "$src_num" ]; then
        echo "  ⚠ Upstream missing: $rel_path"
        continue
    fi

    mkdir -p "$(dirname "$dst_num")"

    if [ -f "$dst_num" ] && diff -q "$src_num" "$dst_num" > /dev/null 2>&1; then
        ((NUM_UNCHANGED++))
        continue
    fi

    if $DRY_RUN; then
        echo "  WOULD COPY: $rel_path"
    else
        cp "$src_num" "$dst_num"
        # next_decision_number.sh 是可执行 shell
        if [[ "$rel_path" == *.sh ]]; then chmod +x "$dst_num"; fi
        echo "  COPIED: $rel_path"
    fi
    ((NUM_COPIED++))
done

echo "  Results: $NUM_COPIED to copy, $NUM_UNCHANGED unchanged"
echo "  ℹ 集成到 .githooks/pre-commit 需 Nature 决定 (DP-补)："
echo "    选项 A: wow-harness 启用 core.hooksPath = .githooks 模式（推荐，跟 Towow 对齐）"
echo "    选项 B: 手装到 .git/hooks/pre-commit"

# ─── Step 10: MANIFEST.yaml physical_files 自检 ───
# 不自动改 manifest（schema-driven，需手工校准 L registry），仅给出当前
# 计数与建议增量。
echo ""
echo "── Step 10: MANIFEST.yaml physical_files audit ──"

MANIFEST="$HARNESS_ROOT/.wow-harness/MANIFEST.yaml"
if [ -f "$MANIFEST" ]; then
    CURRENT_COUNT=$(grep -E "^physical_files:" "$MANIFEST" | sed -E 's/^physical_files:[[:space:]]*([0-9]+).*/\1/')
    echo "  Current physical_files: $CURRENT_COUNT"

    # H 系列新增预估 (5 inbox hooks + 2 numbering scripts + hanis-protocol.md
    # + inbox schema + 9 ADR + 8 PLAN = 26)
    ESTIMATED_DELTA=26
    echo "  Estimated H series delta: +$ESTIMATED_DELTA"
    echo "    - 5 inbox hooks (scripts/hooks/inbox-*.{py,sh})"
    echo "    - 2 numbering scripts (scripts/checks/check_adr_plan_numbering.py + next_decision_number.sh)"
    echo "    - 1 rule (.claude/rules/hanis-protocol.md)"
    echo "    - 1 schema (.towow/inbox/schema/message-v1.json)"
    echo "    - 9 ADR-Hx + 8 PLAN-Hx = 17 decisions"
    echo "  ➜ Suggested new physical_files: $((CURRENT_COUNT + ESTIMATED_DELTA))"
    echo "  ➜ Update L1/L3 registries + physical_files manually after sync."
else
    echo "  ⚠ MANIFEST.yaml not found at $MANIFEST"
fi

# ─── Step 11: vNext / WP-040 plugins backport ───
# H 系列 ADR/PLAN 引用消费的中间层。先有 wow-harness（v1）→ 然后有 vNext
# （v2，WP-040 backport）→ 然后有 H 系列（v3）。这一步把 v2 落地到
# wow-harness，让 H5/H6 在 review-contract.yaml 上的 schema 落地点真实存在。
# vNext 文件不含业务术语（harness 层抽象），无需脱敏。
echo ""
echo "── Step 11: vNext / WP-040 plugins backport ──"

VNEXT_FILES=(
    ".claude/plugins/towow-review-toolkit/.claude-plugin/plugin.json"
    ".claude/plugins/towow-review-toolkit/agents/reviewer.md"
    ".claude/plugins/towow-review-toolkit/contracts/evidence-packet-schema.json"
    ".claude/plugins/towow-review-toolkit/contracts/review-contract.yaml"
    ".claude/plugins/towow-review-toolkit/hooks/verify-gate.py"
    ".claude/plugins/towow-mode-toolkit/.claude-plugin/plugin.json"
    ".claude/plugins/towow-mode-toolkit/contracts/mode-contract.md"
    ".claude/plugins/towow-mode-toolkit/hooks/capability-router.py"
    ".claude/plugins/towow-mode-toolkit/hooks/evidence-emit.py"
    ".claude/plugins/towow-mode-toolkit/skills/mode/SKILL.md"
    ".claude/plugins/towow-mode-toolkit/skills/mode/transition.py"
    ".claude/plugins/towow-mode-toolkit/skills/mode/build.sh"
    ".claude/plugins/towow-mode-toolkit/skills/mode/plan.sh"
    ".claude/plugins/towow-mode-toolkit/skills/mode/release.sh"
    ".claude/plugins/towow-mode-toolkit/skills/mode/shadow-review.sh"
    ".claude/plugins/towow-mode-toolkit/skills/mode/verify.sh"
    ".claude/skills/toolkit/SKILL.md"
    ".claude/skills/toolkit/list.sh"
    ".claude/agents/review-base.yaml"
    ".towow/toolkit-index.yaml"
)

VNEXT_COPIED=0
VNEXT_UNCHANGED=0
for rel_path in "${VNEXT_FILES[@]}"; do
    src_v="$UPSTREAM_ROOT/$rel_path"
    dst_v="$HARNESS_ROOT/$rel_path"
    [ -f "$src_v" ] || { echo "  ⚠ MISSING upstream: $rel_path"; continue; }

    if [ -f "$dst_v" ] && diff -q "$src_v" "$dst_v" > /dev/null 2>&1; then
        ((VNEXT_UNCHANGED++))
        continue
    fi

    if $DRY_RUN; then
        echo "  WOULD COPY: $rel_path"
    else
        mkdir -p "$(dirname "$dst_v")"
        cp "$src_v" "$dst_v"
        if [[ "$rel_path" == *.py || "$rel_path" == *.sh ]]; then
            chmod +x "$dst_v"
        fi
        echo "  COPIED: $rel_path"
    fi
    ((VNEXT_COPIED++))
done

echo "  Results: $VNEXT_COPIED to copy, $VNEXT_UNCHANGED unchanged"
echo "  ℹ 集成提示："
echo "    - reviewer agent: schema-level read-only (frontmatter tools 不含 Edit/Write)"
echo "    - verify-gate.py: Stop hook (plugin.json 自注册)"
echo "    - capability-router.py: PreToolUse hook (按 .towow/state/mode 决定 deny/defer/ask/allow)"
echo "    - /mode plan|build|verify|release: 用户走完整生命周期的入口"

echo ""
echo "=== Sync complete ==="
