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

LOOP_THRESHOLD = 5  # 同一文件编辑超过此次数则提醒
STATE_DIR = Path(".towow/guard")
STATE_FILE_PREFIX = "loop-"
TTL_SECONDS = 3600  # 1 小时后重置计数


def get_state_file():
    """获取当前会话的 loop 状态文件。"""
    pid = os.getppid()
    return STATE_DIR / f"{STATE_FILE_PREFIX}{pid}.json"


def load_state():
    """加载文件编辑计数状态。"""
    state_file = get_state_file()
    if not state_file.exists():
        return {}
    try:
        data = json.loads(state_file.read_text())
        # 检查 TTL
        if time.time() - data.get("_ts", 0) > TTL_SECONDS:
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    """保存文件编辑计数状态。"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["_ts"] = time.time()
    get_state_file().write_text(json.dumps(state))


def main():
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        print(json.dumps({"decision": "allow"}))
        return

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})

    # 只追踪 Write 和 Edit 操作
    if tool_name not in ("Write", "Edit"):
        print(json.dumps({"decision": "allow"}))
        return

    file_path = tool_input.get("file_path", "")
    if not file_path:
        print(json.dumps({"decision": "allow"}))
        return

    # 更新计数
    state = load_state()
    counts = state.get("counts", {})
    counts[file_path] = counts.get(file_path, 0) + 1
    state["counts"] = counts
    save_state(state)

    count = counts[file_path]

    if count >= LOOP_THRESHOLD:
        # 注入提醒
        print(json.dumps({
            "decision": "allow",
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"[LoopDetection] 你已经编辑 {file_path} {count} 次了。"
                    f"考虑换一个方法或退一步重新思考整体方案。"
                    f"[来源: LangChain LoopDetection middleware]"
                )
            }
        }))
    else:
        print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
