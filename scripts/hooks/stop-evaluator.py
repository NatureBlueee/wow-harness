#!/usr/bin/env python3
"""Stop hook: L3 Completion Gate (ADR-044 §3.4)

[来源: ADR-044 §3.4 + ADR-038 D2.1 + D4]

核心原则（ADR-044 §3.4.1）：
  Stop ≠ Completion。Stop 只是 transport 事件。
  只有存在 completion candidate 时才触发 L3 检查。

Completion candidate 定义（§3.4.2）：
  1. 本 session transcript 中有 Edit/Write/NotebookEdit 工具调用
  2. 且这些文件在 git 工作区有未提交变更（transcript ∩ git_dirty）
  3. 或有已暂存的变更（git diff --cached）
  4. progress.json 存在未验收产物（D8 机械化第一关）

不是 completion candidate 的场景：
  纯聊天、纯研究、纯规划、纯 Read/Grep 浏览 → 静默放行。

CC Stop hook 协议：
- exit 2 + stderr → 阻止 Stop 并注入反馈
- exit 0 → 允许 Stop
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


def extract_edited_files(transcript_path: str) -> set[str] | None:
    """从 CC transcript JSONL 提取本 session 写过的文件路径。

    Returns:
      set[str] — repo-relative paths of files written by this session
      None — transcript 不可读 → 调用方应 fail-open

    CC transcript 天然 session 隔离：每个 session 独立 .jsonl 文件。
    相比 risk-snapshot.json（repo 级共享状态），不会被并行 session 污染，
    也不受 /clear 影响（/clear 不清 transcript）。
    """
    WRITE_TOOLS = {"Edit", "Write", "NotebookEdit"}
    if not transcript_path:
        return None
    try:
        files: set[str] = set()
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                msg = rec.get("message", {})
                if msg.get("role") != "assistant":
                    continue
                for block in msg.get("content", []):
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use" and block.get("name") in WRITE_TOOLS:
                        fp = block.get("input", {}).get("file_path", "")
                        if fp:
                            try:
                                rel = str(Path(fp).relative_to(REPO_ROOT))
                                files.add(rel)
                            except ValueError:
                                pass
        return files
    except (OSError, json.JSONDecodeError):
        return None  # fail-open：读不到 transcript 时由调用方决定


def is_completion_candidate(transcript_path: str) -> tuple[bool, str]:
    """ADR-044 §3.4.2 — session-scoped completion candidate 判定。

    返回 (is_candidate, reason)。
    reason 用于 metrics，不注入 agent context。

    核心逻辑：transcript_writes ∩ git_dirty 交集。
    - transcript 天然 session 隔离（每个 CC session 独立 .jsonl）
    - 只提取 Edit/Write/NotebookEdit tool_use（精确、无 grep 假阳性）
    - git_dirty 过滤已 commit 的文件
    - 交集同时排除两类假阳性

    场景覆盖：
    - 纯聊天/研究 → transcript 无写操作 → 放行
    - 编辑后已全部 commit → 交集空 → 放行
    - 编辑后未 commit → 交集非空 → 触发 completion review
    - pre-existing 脏文件 → 不在 transcript → 不触发
    - /clear 后首条消息 → transcript 无写操作 → 放行
    - 并行 session → 各自 transcript 独立 → 不互相污染
    """
    # Step 1: 从 transcript 提取本 session 写过的文件
    session_files = extract_edited_files(transcript_path)
    if session_files is None:
        return True, "transcript_unreadable_failopen"  # fail-open
    if not session_files:
        return False, "no_session_writes"

    # Step 2: 与 git dirty 状态取交集
    git_dirty: set[str] = set()
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, timeout=5,
            cwd=str(REPO_ROOT),
        )
        if result.returncode == 0 and result.stdout.strip():
            git_dirty = set(result.stdout.strip().splitlines())
    except (subprocess.SubprocessError, OSError):
        pass

    uncommitted = session_files & git_dirty
    if uncommitted:
        return True, "uncommitted_session_changes"

    # Step 3: 已暂存但未 commit（git add 后未 commit）
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5,
            cwd=str(REPO_ROOT),
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, "staged_changes"
    except (subprocess.SubprocessError, OSError):
        pass

    return False, "all_committed"


def main() -> None:
    # 解析 CC hook stdin JSON payload（含 session_id + stop_hook_active）
    payload = read_hook_payload()
    session_key = get_session_key(payload)

    # ─── Step -1: CC 官方防循环字段 ───
    if payload.get("stop_hook_active") is True:
        emit_metric("stop_pass", session_key, reason="stop_hook_active_guard")
        sys.exit(0)

    if already_blocked(session_key):
        emit_metric("stop_pass", session_key, reason="already_blocked_once")
        sys.exit(0)

    # ─── Step 0: D8.2 机械化第一关（无条件硬门） ───
    # progress.json 真相源 — 零 LLM 成本，零 self-eval bias
    # D8 先于 candidate 检查执行：如果 progress.json 有 failing features，
    # 必须阻断，不管 session 是否有 completion candidate。
    mech_code, mech_msg = mechanical_first_pass(session_key)
    if mech_code == 2:
        sys.stderr.write(mech_msg)
        mark_blocked(session_key)
        sys.exit(2)

    # ─── Step 1: ADR-044 §3.4.2 — Completion Candidate 门控 ───
    # 没有 completion candidate → 静默放行，不注入任何文本
    is_candidate, reason = is_completion_candidate(payload.get("transcript_path", ""))
    if not is_candidate:
        emit_metric("stop_pass", session_key, reason=reason)
        sys.exit(0)

    # ─── Step 2: 注入 L3 检查清单 ───
    if not EVALUATOR_MD.exists():
        emit_metric("stop_skip", session_key, reason="evaluator_md_missing")
        sys.exit(0)

    try:
        checklist = EVALUATOR_MD.read_text(encoding="utf-8")
    except OSError:
        emit_metric("stop_skip", session_key, reason="evaluator_md_read_error")
        sys.exit(0)

    sys.stderr.write(checklist + "\n")
    mark_blocked(session_key)
    emit_metric("stop_block", session_key, reason=f"completion_candidate_{reason}")
    sys.exit(2)


if __name__ == "__main__":
    main()
