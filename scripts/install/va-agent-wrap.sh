#!/usr/bin/env bash
# 由 wow_global_hooks.py 安装到 ~/.wow-agent-hooks/va-agent-wrap.sh
# 任意 Git 仓库：若根目录存在 .wow-harness/MANIFEST.yaml，则在启动 Cursor agent 前打印提示；
# 若仓库自带 scripts/va-agent，则优先使用（可定制文案）。
set -euo pipefail
AGENT_BIN="${WOW_AGENT_BIN:-$HOME/.local/bin/agent}"
if [[ ! -x "$AGENT_BIN" ]]; then
  AGENT_BIN="$(command -v agent 2>/dev/null || true)"
fi
if [[ ! -x "${AGENT_BIN:-}" ]]; then
  echo "wow-harness: 找不到 Cursor agent（试过 \$HOME/.local/bin/agent 与 PATH）。请安装 Cursor CLI 或设置 WOW_AGENT_BIN。" >&2
  exit 127
fi

TOP="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${TOP:-}" ]]; then
  exec "$AGENT_BIN" "$@"
fi

if [[ -x "$TOP/scripts/va-agent" ]]; then
  exec "$TOP/scripts/va-agent" "$@"
fi

if [[ ! -f "$TOP/.wow-harness/MANIFEST.yaml" ]]; then
  exec "$AGENT_BIN" "$@"
fi

if [[ -t 2 ]]; then
  printf '\033[1m\033[36m━━ wow-harness · %s ━━\033[0m\n' "$(basename "$TOP")" >&2
else
  printf '━━ wow-harness · %s ━━\n' "$(basename "$TOP")" >&2
fi
printf '  路径: %s\n' "$TOP" >&2
printf '  活动日志: tail -f %s\n' "$TOP/.wow-harness/state/harness-visible.jsonl" >&2
printf '  更新全局 hooks: 在 wow-harness 源仓库执行: python3 scripts/install/wow_global_hooks.py install\n' >&2
printf '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' >&2
exec "$AGENT_BIN" "$@"
