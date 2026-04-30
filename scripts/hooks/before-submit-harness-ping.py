#!/usr/bin/env python3
"""beforeSubmitPrompt — 在用户每条消息发出前打点，让 CLI/终端侧也能「看见」harness。

Cursor：事件 ``beforeSubmitPrompt``（matcher 通常为 ``UserPromptSubmit``）。
stdout 必须输出合法 JSON（此处 ``{}``）；**人类可读提示走 stderr**，便于
`agent` TTY 与 Hooks 输出通道观察。

活动日志写入由 ``wow_agent_dispatch`` 在桥接入口统一打点；本脚本只负责
stderr 提示，避免重复 JSONL 行。项目级 ``hooks.json`` 也可直接调用本脚本
（此时不会自动写 harness-visible，仅 stderr）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, OSError, ValueError):
        pass
    print(
        "[wow-harness] beforeSubmitPrompt：本条用户消息已进入钩子链；"
        "SessionStart 的说明在模型上下文里，终端 ASCII 横幅不一定显示。"
        " 活动日志: tail -f .wow-harness/state/harness-visible.jsonl",
        file=sys.stderr,
    )
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
