#!/usr/bin/env python3
"""PreToolUse hook: 自动将 python 命令替换为 python3
[来源: ADR-038 D2.2, CC updatedInput 能力]

当检测到 Bash 工具使用裸 `python` 命令时，
通过 updatedInput 自动替换为 python3。
"""
import json
import sys
import re


def main():
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        print(json.dumps({"decision": "allow"}))
        return

    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")

    # 匹配裸 python 命令（不匹配 python3、ipython 等）
    # 模式：行首或空格后的 python 后跟空格/参数
    if re.search(r'(?:^|[\s;&|])python(?:\s)', command):
        new_command = re.sub(r'(?:^|(?<=[\s;&|]))python(?=\s)', 'python3', command)
        print(json.dumps({
            "decision": "allow",
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": {"command": new_command}
            }
        }))
    else:
        print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
