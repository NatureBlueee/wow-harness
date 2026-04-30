#!/usr/bin/env python3
"""Stop hook: PreCompletionChecklist 注入

[来源: ADR-038 D2.1 + D4 + LangChain PreCompletionChecklist (52.8%→66.5% 提升的三个组件之一)]

CC Stop hook 协议：
- exit 2 + stderr → 阻止 Stop 并把 stderr 作为"还需要做的事"反馈给 agent
- exit 0 → 允许 Stop

策略：
1. 第一次 Stop 尝试 → 注入 stop-evaluator.md 检查清单 + exit 2
2. 第二次起 → exit 0（避免无限阻塞）
3. 同一 session（按 ppid）只阻塞一次

注意：这是"软评估"——父 agent 自评，仍有 self-evaluation bias。
真正的独立 Evaluator subagent 等 CC agent-type hook 验证后升级。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EVALUATOR_MD = REPO_ROOT / "scripts" / "hooks" / "stop-evaluator.md"
INITIALIZER_AGENT = REPO_ROOT / "scripts" / "hooks" / "initializer-agent.py"
STATE_DIR = REPO_ROOT / ".towow" / "guard"
METRICS_DIR = REPO_ROOT / ".towow" / "metrics"
TTL_SECONDS = 3600  # 1 小时后允许重新阻塞


def emit_metric(event: str, session_key: str, **data) -> None:
    """Append a JSONL metric line. Never raises."""
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "session_key": session_key,
            "event": event,
            **data,
        }
        with open(METRICS_DIR / "stop-events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_hook_payload() -> dict:
    """解析 CC Stop hook stdin JSON payload。

    CC Stop hook schema (2026-04)：
    - session_id: str          — 稳定 session 标识（真相源）
    - transcript_path: str     — 当前会话 transcript
    - hook_event_name: "Stop"
    - stop_hook_active: bool   — 前一次 stop hook 已经触发 continue 时为 true

    旧实现用 os.getppid() 做 dedup key，但 CC 给 hook 传的 ppid 是短命子进程，
    每次调用都不同 → dedup 失效 → 无限注入 checklist。修复：用 session_id。
    """
    try:
        raw = sys.stdin.read()
        if not raw:
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def get_session_key(payload: dict) -> str:
    """从 payload 提取稳定 session key，fallback 到 ppid（仅兜底）。"""
    sid = payload.get("session_id")
    if isinstance(sid, str) and sid:
        return sid
    return f"ppid-{os.getppid()}"


def get_state_file(session_key: str) -> Path:
    # session_id 可能含特殊字符，做简单清洗
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_key)[:64]
    return STATE_DIR / f"stop-{safe}.flag"


def already_blocked(session_key: str) -> bool:
    """检查本 session 是否已经被阻塞过一次。"""
    state_file = get_state_file(session_key)
    if not state_file.exists():
        return False
    try:
        ts = float(state_file.read_text(encoding="utf-8").strip())
        return time.time() - ts < TTL_SECONDS
    except (ValueError, OSError):
        return False


def mark_blocked(session_key: str) -> None:
    """记录本 session 已被阻塞。"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    get_state_file(session_key).write_text(str(time.time()), encoding="utf-8")


def mechanical_first_pass(session_key: str) -> tuple[int, str]:
    """ADR-038 D8.2 — 机械化第一关：检查 progress.json 所有 feature 是否 passing。

    返回 (exit_code, stderr_message)：
    - (0, "") → 全部 passing 或无 progress.json，可进入 LLM 评估
    - (2, "...") → 有 failing/blocked features，立即阻塞 Stop（零 LLM 成本）
    """
    if not INITIALIZER_AGENT.exists():
        return 0, ""  # D8 未部署，跳过

    try:
        result = subprocess.run(
            ["python3", str(INITIALIZER_AGENT), "stop-check"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return 0, ""  # 机械化关失败不能阻塞 hook 主流程

    if result.returncode == 0:
        emit_metric("mechanical_pass", session_key, reason="all_features_passing")
        return 0, ""
    if result.returncode == 2:
        emit_metric("mechanical_skip", session_key, reason="no_progress_json")
        return 0, ""  # 无 progress.json，回退到 LLM 评估

    # returncode == 1 → blocking
    msg = (
        "## D8 机械化第一关失败 (零 LLM 成本)\n\n"
        "progress.json 显示以下 features 未达到 passing 状态：\n\n"
        f"{result.stderr.strip()}\n\n"
        "**继续工作**：\n"
        "1. 完成上述每个 feature 的实现\n"
        "2. 通过 `python3 scripts/hooks/initializer-agent.py update --feature <id> --status passing --evidence <...>` 标记完成\n"
        "3. 必须提供 evidence（命令输出、测试结果等）\n"
        "4. 不得直接编辑 progress.json — objective 字段有 SHA256 校验\n\n"
        "**绝对禁止**：在 features 全部 passing 前 Stop 或假装完成。\n"
    )
    emit_metric("mechanical_block", session_key, reason="features_not_passing")
    return 2, msg


def main() -> None:
    # 解析 CC hook stdin JSON payload（含 session_id + stop_hook_active）
    payload = read_hook_payload()
    session_key = get_session_key(payload)

    # ─── Step -1: CC 官方防循环字段 ───
    # 当 stop_hook_active == true 时，说明 CC 是因为前一次 stop hook exit 2 才 continue 的，
    # 再阻塞会形成无限循环。这是 CC 官方推荐的硬兜底。
    if payload.get("stop_hook_active") is True:
        emit_metric("stop_pass", session_key, reason="stop_hook_active_guard")
        sys.exit(0)

    if already_blocked(session_key):
        emit_metric("stop_pass", session_key, reason="already_blocked_once")
        sys.exit(0)

    # ─── Step 0: D8.2 机械化第一关 ───
    # progress.json 真相源 — 零 LLM 成本，零 self-eval bias
    mech_code, mech_msg = mechanical_first_pass(session_key)
    if mech_code == 2:
        sys.stderr.write(mech_msg)
        mark_blocked(session_key)
        sys.exit(2)

    # 读取 evaluator 检查清单
    if not EVALUATOR_MD.exists():
        emit_metric("stop_skip", session_key, reason="evaluator_md_missing")
        sys.exit(0)

    try:
        checklist = EVALUATOR_MD.read_text(encoding="utf-8")
    except OSError:
        emit_metric("stop_skip", session_key, reason="evaluator_md_read_error")
        sys.exit(0)

    # 注入检查清单 + 阻止 Stop（exit 2 + stderr）
    sys.stderr.write(checklist + "\n")
    mark_blocked(session_key)
    emit_metric("stop_block", session_key, reason="first_attempt_inject_checklist")
    sys.exit(2)


if __name__ == "__main__":
    main()
