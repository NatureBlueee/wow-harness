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

METRICS_DIR = Path(".wow-harness/state/metrics")
GUARD_STATE_DIR = Path(".wow-harness/state/guard")


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

    # Gate 8 PASS forced reflection loop (ADR-043 §3.4.6, WP-11)
    # Check if a plan just completed Gate 8 → spawn crystal-learn agent
    _check_gate8_reflection()


def _check_gate8_reflection():
    """If Gate 8 PASS was recorded in this session, emit a reflection trigger.

    We check for .wow-harness/state/gate8-pass-pending.json written by
    the lead state machine when Gate 8 transitions to PASS. If found,
    we write a trigger file that the main CC agent picks up to spawn
    a crystal-learn background agent.

    Why a trigger file instead of direct Agent spawn?
    - This hook runs as a subprocess, not inside CC's agent loop
    - It cannot call Agent() directly
    - Instead it writes a proposal trigger that the session-start hook
      or lead skill picks up on next session start

    Tier check: only fires for adapt/mine, not drop-in.
    """
    gate8_marker = Path(".wow-harness/state/gate8-pass-pending.json")
    if not gate8_marker.exists():
        return

    try:
        data = json.loads(gate8_marker.read_text())
    except (json.JSONDecodeError, OSError):
        return

    plan_id = data.get("plan_id", "unknown")
    tier = data.get("install_tier", "adapt")

    if tier == "drop-in":
        # drop-in users don't want reflection
        gate8_marker.unlink(missing_ok=True)
        return

    # Write reflection trigger for next session pickup
    proposals_dir = Path(".wow-harness/proposals")
    proposals_dir.mkdir(parents=True, exist_ok=True)

    trigger = {
        "type": "gate8_reflection",
        "plan_id": plan_id,
        "tier": tier,
        "requested_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "instruction": (
            "spawn crystal-learn background agent with: "
            f"Agent(subagent_type='crystal-learn', run_in_background=true, "
            f"prompt='Reflect on plan {plan_id} completion. "
            "Read all WP LOG.md files and Gate 8 review results. "
            "Produce proposals for new invariants, rules, or hook improvements.')"
        ),
    }

    trigger_path = proposals_dir / f"{plan_id}-reflection-trigger.json"
    trigger_path.write_text(json.dumps(trigger, indent=2, ensure_ascii=False) + "\n")

    sys.stderr.write(
        f"[session-reflection] Gate 8 PASS detected for {plan_id}. "
        f"Reflection trigger written to {trigger_path}\n"
    )

    # Clean up marker so we don't re-trigger
    gate8_marker.unlink(missing_ok=True)

    # Log the event
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": "gate8_reflection_triggered",
        "plan_id": plan_id,
        "tier": tier,
    }
    with open(METRICS_DIR / "session-reflections.jsonl", "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
