#!/usr/bin/env python3
"""PostToolUse hook: LoopDetection middleware
[来源: ADR-038 D4.5, LangChain — 52.8%→66.5% 提升的三个组件之一]

追踪 per-file edit count。当同一文件被编辑超过阈值次数时，
通过 additionalContext 注入提醒让 agent 考虑换方法。
"""
import json
import os
import sys
import time
from pathlib import Path

from _hook_output import post_tool_use_inject

LOOP_THRESHOLD = 5  # 同一文件编辑超过此次数则提醒
STATE_DIR = Path(".towow/guard")
STATE_FILE_PREFIX = "loop-"
TTL_SECONDS = 3600  # 1 小时后重置计数


def get_state_file():
    """获取当前会话的 loop 状态文件。"""
    pid = os.getppid()
    return STATE_DIR / f"{STATE_FILE_PREFIX}{pid}.json"


def load_state():
    """加载文件编辑计数状态。

    Reviewer #2 P1 (Gate 8): JSONDecodeError 区别于 OSError。前者 = 状态文件
    被并发 session 写穿、磁盘满中断、或人手 vim 编辑后留空——必须 unlink 自
    愈+留 stderr 痕迹（否则 LoopDetection counter 永远归零，5 阈值再也不触
    发）。后者 = 文件正常缺失或权限异常，是 fail-open 期望路径，silent。
    """
    state_file = get_state_file()
    if not state_file.exists():
        return {}
    try:
        data = json.loads(state_file.read_text())
        if time.time() - data.get("_ts", 0) > TTL_SECONDS:
            return {}
        return data
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[loop-detection] corrupt state {state_file}: {exc!r}; resetting\n")
        try:
            state_file.unlink(missing_ok=True)
        except OSError:
            pass
        return {}
    except OSError:
        return {}


def save_state(state):
    """保存文件编辑计数状态。

    Reviewer #2 P1 (Gate 8): write_text OSError 必须 stderr 留痕——磁盘满 /
    .towow/guard/ 被另一 session lock 时，counter 静默丢失等于关闭 LoopDetection。
    """
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state["_ts"] = time.time()
        get_state_file().write_text(json.dumps(state))
    except OSError as exc:
        sys.stderr.write(f"[loop-detection] save_state OSError: {exc!r}; counter not persisted\n")


def main():
    # PostToolUse schema 不接受 "decision" 字段（那是 PreToolUse 专属）。
    # 合法输出：空 stdout + exit 0，或 {"hookSpecificOutput": {...}} 注入后置 context。
    # See docs/issues/guard-20260424-1034-posttooluse-hook-schema-violation.md
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})

    if tool_name not in ("Write", "Edit"):
        return

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    state = load_state()
    counts = state.get("counts", {})
    counts[file_path] = counts.get(file_path, 0) + 1
    state["counts"] = counts
    save_state(state)

    count = counts[file_path]

    if count >= LOOP_THRESHOLD:
        post_tool_use_inject(
            f"[LoopDetection] 你已经编辑 {file_path} {count} 次了。"
            f"考虑换一个方法或退一步重新思考整体方案。"
            f"[来源: LangChain LoopDetection middleware]"
        )


if __name__ == "__main__":
    main()
