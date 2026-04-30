#!/usr/bin/env python3
"""PostToolUseFailure hook: 自动记录工具失败模式
[来源: ADR-038 D2.7, CC PostToolUseFailure 事件]

工具调用失败时记录失败模式到 JSONL。
累积数据后可识别系统性问题。
"""
import json
import sys
import time
from pathlib import Path

METRICS_DIR = Path(".towow/metrics")


def main():
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        print(json.dumps({"decision": "allow"}))
        return

    failure_record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tool_name": event.get("tool_name", "unknown"),
        "error": str(event.get("error", ""))[:500],  # 截断避免过大
        "tool_input_keys": list(event.get("tool_input", {}).keys()),
    }

    # 追加到 JSONL
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_file = METRICS_DIR / "tool-failures.jsonl"

    with open(metrics_file, "a") as f:
        f.write(json.dumps(failure_record, ensure_ascii=False) + "\n")

    print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
