#!/usr/bin/env python3
"""SessionEnd hook: 自动 reflection
[来源: ADR-038 D6.2, ACE generation-reflection-curation 循环]

会话结束时自动记录：
1. 本次 session 哪些 guard 有用
2. 是否有新失败模式
3. 如果有新模式 → 输出提议（需人确认）
"""
import json
import os
import sys
import time
from pathlib import Path

METRICS_DIR = Path(".towow/metrics")
GUARD_STATE_DIR = Path(".towow/guard")


def collect_session_stats():
    """收集当前会话的 guard 统计数据。"""
    pid = os.getppid()
    session_file = GUARD_STATE_DIR / f"session-{pid}.json"

    if not session_file.exists():
        return None

    try:
        return json.loads(session_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def collect_loop_stats():
    """收集 LoopDetection 数据。"""
    pid = os.getppid()
    loop_file = GUARD_STATE_DIR / f"loop-{pid}.json"

    if not loop_file.exists():
        return None

    try:
        data = json.loads(loop_file.read_text())
        return data.get("counts", {})
    except (json.JSONDecodeError, OSError):
        return None


def main():
    reflection = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "session_pid": os.getppid(),
        "guard_stats": collect_session_stats(),
        "loop_stats": collect_loop_stats(),
    }

    # 写入 metrics JSONL
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_file = METRICS_DIR / "session-reflections.jsonl"

    with open(metrics_file, "a") as f:
        f.write(json.dumps(reflection, ensure_ascii=False) + "\n")

    # 如果有 loop 告警，输出提议
    loop_stats = reflection.get("loop_stats") or {}
    hot_files = {k: v for k, v in loop_stats.items() if v >= 5 and k != "_ts"}

    if hot_files:
        msg = "[SessionEnd Reflection] 本次会话中以下文件被频繁编辑：\n"
        for f, count in sorted(hot_files.items(), key=lambda x: -x[1]):
            msg += f"  - {f}: {count} 次\n"
        msg += "考虑是否需要新的 guard 规则来预防重复编辑模式。"
        sys.stderr.write(msg + "\n")

    # SessionEnd hook 无需 decision 字段（schema 只接受 approve/block）
    # 本 hook 是纯观察性的，不干预会话走向


if __name__ == "__main__":
    main()
