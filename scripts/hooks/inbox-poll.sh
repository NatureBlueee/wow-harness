#!/bin/bash
# H9 inbox poll：状态检查 + 下次 wake 间隔推荐（PLAN-H9 §4.5 WP-05）。
#
# Spec letter 工程修订（disclosure）：
#   PLAN-H9 §4.5 原文写"shell 脚本 ... 内部调用 ScheduleWakeup MCP"。落地阶段
#   发现 ScheduleWakeup 是 CC agent loop 内部 tool API，shell 进程没有合法 RPC
#   入口直接调用——必须由 CC agent（主窗口）调用。本脚本因此切分为：
#     [shell 层] inbox-poll.sh = 状态检查 + 推荐间隔 → stdout 状态
#     [agent 层] 主 agent 读 stdout 后自行决定下一次 ScheduleWakeup 时机
#   切分边界已在 PLAN-H9 §4.5 + §11 letter 对齐时点明，记入 ADR-H9 修订建议。
#
# 输出：纯 KV 文本（不是 hook IO JSON），主 agent 解读后调度。
#   unread_count=<int>
#   p0_exists=<true|false>
#   oldest_unread_age_seconds=<int|0>
#   recommended_wake_seconds=<int>
#
# Hook IO 红线：本文件**不是** CC hook（不在 .claude/settings.json 注册），
# 是主 agent 用 Bash tool 主动调用的检查脚本。无 print(json.dumps) / echo
# permissionDecision / echo systemMessage 等 banned form——由 PLAN-H9 §8 显式
# grep DoD 物理校验。

set -euo pipefail

# 主仓 root 检测（与 find-project-root.sh 语义对齐）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
INBOX_ROOT="${REPO_ROOT}/.towow/inbox"
MAIN_UNREAD="${INBOX_ROOT}/main/unread"

# 默认间隔常量（见 ADR-H9 §6.3 ScheduleWakeup 边界）
NORMAL_WAKE_SECONDS="${INBOX_POLL_NORMAL_WAKE:-1200}"   # 20 分钟（cache 友好）
P0_WAKE_SECONDS="${INBOX_POLL_P0_WAKE:-300}"            # 5 分钟（CC ScheduleWakeup 最短允许下限）

# unread 计数
unread_count=0
if [ -d "${MAIN_UNREAD}" ]; then
  unread_count="$(find "${MAIN_UNREAD}" -maxdepth 1 -type f -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"
fi

# 是否存在 priority=P0 消息
p0_exists=false
if [ "${unread_count}" -gt 0 ]; then
  if grep -lE '^priority:[[:space:]]*P0[[:space:]]*$' "${MAIN_UNREAD}"/*.md 2>/dev/null | head -1 | grep -q .; then
    p0_exists=true
  fi
fi

# 最旧 unread 的 mtime delta（秒）
oldest_age=0
if [ "${unread_count}" -gt 0 ]; then
  oldest_file="$(ls -1tr "${MAIN_UNREAD}"/*.md 2>/dev/null | head -1 || true)"
  if [ -n "${oldest_file}" ] && [ -f "${oldest_file}" ]; then
    if stat --version >/dev/null 2>&1; then
      # GNU stat (Linux)
      oldest_mtime="$(stat -c %Y "${oldest_file}" 2>/dev/null || echo 0)"
    else
      # BSD stat (macOS)
      oldest_mtime="$(stat -f %m "${oldest_file}" 2>/dev/null || echo 0)"
    fi
    now="$(date +%s)"
    oldest_age="$((now - oldest_mtime))"
  fi
fi

# 推荐 wake 间隔
if [ "${p0_exists}" = "true" ]; then
  recommended="${P0_WAKE_SECONDS}"
else
  recommended="${NORMAL_WAKE_SECONDS}"
fi

# 输出（KV 纯文本，主 agent 用 grep / awk 解读）
printf 'unread_count=%s\n' "${unread_count}"
printf 'p0_exists=%s\n' "${p0_exists}"
printf 'oldest_unread_age_seconds=%s\n' "${oldest_age}"
printf 'recommended_wake_seconds=%s\n' "${recommended}"
printf 'note=ScheduleWakeup MCP must be invoked by main agent (shell cannot reach CC internal tool API)\n'
