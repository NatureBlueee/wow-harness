#!/usr/bin/env python3
"""PreToolUse hook: 自动将 python 命令替换为 python3
[来源: ADR-038 D2.2, CC updatedInput 能力]

当检测到 Bash 工具使用裸 `python` 命令时，
通过 updatedInput 自动替换为 python3。
"""
import json
import sys
import re

from _hook_output import pre_tool_use_allow


def main():
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return

    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")

    if re.search(r'(?:^|[\s;&|])python(?:\s)', command):
        new_command = re.sub(r'(?:^|(?<=[\s;&|]))python(?=\s)', 'python3', command)
        pre_tool_use_allow(updated_input={"command": new_command})


if __name__ == "__main__":
    main()
