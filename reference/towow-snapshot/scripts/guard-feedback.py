#!/usr/bin/env python3
"""Guard Feedback — Claude Code PostToolUse/PreToolUse hook 目标脚本。

ADR-030 Governance Reload 的实际执行入口，同时承担：
- 机制 A（上下文路由）：每次 Edit/Write 后，注入相关上下文片段
- 机制 B（guard 检查）：运行相关 guard，报告 findings

Fragment 去重（CC alreadySurfaced pattern）：同一 fragment 在一个编辑 session
内只注入一次，后续编辑静默（exit 0），大幅减少 token 消耗。

Usage:
    # 正常模式（PostToolUse hook 调用，从 stdin JSON 读取输入）
    echo '{"tool_name":"Edit","tool_input":{"file_path":"bridge_agent/agent.py"}}' | python3 scripts/guard-feedback.py

    # Check-only 模式（PreToolUse hook 调用）
    echo '{"tool_name":"Read","tool_input":{"file_path":"bridge_agent/agent.py"}}' | python3 scripts/guard-feedback.py --check-only --once

    # Dry-run 模式（测试用，从命令行参数获取路径）
    python3 scripts/guard-feedback.py --dry-run bridge_agent/agent.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.context_router import FALLBACK_FRAGMENTS, load_fragment, match  # noqa: E402
from scripts.guard_router import read_all_signals, run_guards, write_session_signal  # noqa: E402

# ── Fragment dedup (CC alreadySurfaced pattern) ──
# Track which fragments have been injected in the current editing session.
# Same fragment is only injected once → near-zero token cost on repeat edits.
# Uses a single file with TTL (no PID — hook spawns vary across shells).
_INJECTED_TTL = 3600  # 1 hour session window
_INJECTED_FILE = REPO_ROOT / ".towow" / "guard" / "injected.json"

# ── JSONL metrics (ADR-038 D1) ──
# Append-only event log for harness observability.
# 数据自然积累，离线用 jq 分析；不做实时聚合。
# [来源: ADR-038 D1, LangChain LangSmith traces, Trail of Bits log-gam.sh JSONL pattern]
_METRICS_DIR = REPO_ROOT / ".towow" / "metrics"
_METRICS_FILE = _METRICS_DIR / "guard-events.jsonl"


def emit_metric(event: str, **data) -> None:
    """Append a single JSONL metric line. Never raises — observability must not break the hook."""
    try:
        _METRICS_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "session_pid": os.getppid(),
            "event": event,
            **data,
        }
        with open(_METRICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Metrics 失败绝不能阻塞 hook 主流程
        pass


def _read_injected() -> set[str]:
    """Read the set of already-injected fragment names for this session."""
    if not _INJECTED_FILE.exists():
        return set()
    try:
        data = json.loads(_INJECTED_FILE.read_text(encoding="utf-8"))
        if time.time() - data.get("timestamp", 0) > _INJECTED_TTL:
            return set()
        return set(data.get("fragments", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _write_injected(fragments: set[str]) -> None:
    """Persist the set of injected fragment names for this session."""
    guard_dir = REPO_ROOT / ".towow" / "guard"
    guard_dir.mkdir(parents=True, exist_ok=True)
    data = {"timestamp": time.time(), "fragments": sorted(fragments)}
    _INJECTED_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def get_file_path() -> str | None:
    """从 stdin JSON 或命令行参数获取文件路径。"""
    if "--dry-run" in sys.argv:
        idx = sys.argv.index("--dry-run")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
        return None

    # Claude Code hook 协议：stdin JSON
    try:
        hook_input = json.load(sys.stdin)
        tool_input = hook_input.get("tool_input", {})
        return tool_input.get("file_path", "") or tool_input.get("path", "") or None
    except (json.JSONDecodeError, EOFError, ValueError):
        return None


def make_relative(file_path: str) -> str:
    """将绝对路径转换为相对于 REPO_ROOT 的路径。"""
    try:
        return str(Path(file_path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return file_path


def append_findings(output_parts: list[str], findings: list[object]) -> None:
    """将 findings 格式化为 Guard Findings 输出块。"""
    output_parts.append("\n\n## Guard Findings\n")
    for raw in findings:
        if isinstance(raw, dict):
            severity = raw.get("severity", "P2")
            blocking = raw.get("blocking", False)
            category = raw.get("category", "general")
            message = raw.get("message", "")
            required_skills = raw.get("required_skills") or []
        else:
            severity = raw.severity
            blocking = raw.blocking
            category = raw.category
            message = raw.message
            required_skills = raw.required_skills

        blocking_tag = " [blocking]" if blocking else ""
        skills = ", ".join(required_skills)
        skills_line = f"\n  required_skills: {skills}" if skills else ""
        output_parts.append(
            f"- {severity}{blocking_tag} {category}: {message}{skills_line}"
        )


def main() -> None:
    start_ms = time.time() * 1000
    check_only = "--check-only" in sys.argv
    once = "--once" in sys.argv
    dry_run = "--dry-run" in sys.argv

    # 每次 hook 触发记录 — 即使后续 early-exit 也算一次触发
    # [ADR-038 D1: hook_trigger_count metric]
    emit_metric(
        "hook_trigger",
        mode=("check_only" if check_only else "post_tool_use"),
        once=once,
        dry_run=dry_run,
    )

    # --once: 同一进程只运行一次
    if once:
        guard_dir = REPO_ROOT / ".towow" / "guard"
        session_file = guard_dir / f"once-{os.getppid()}.flag"
        if session_file.exists():
            # 检查是否过期（1 小时）
            try:
                ts = float(session_file.read_text(encoding="utf-8").strip())
                if time.time() - ts < 3600:
                    sys.exit(0)
            except (ValueError, OSError):
                pass
        # 首次运行后写 flag
        guard_dir.mkdir(parents=True, exist_ok=True)
        session_file.write_text(str(time.time()), encoding="utf-8")

    output_parts: list[str] = []

    if check_only:
        # PID 作用域：只读当前 session 的 signal，不读其他 session 的陈旧 findings
        signal = read_all_signals(pid=os.getpid())
        findings = signal.get("findings", [])
        if findings:
            append_findings(output_parts, findings)
            sys.stderr.write("\n".join(output_parts) + "\n")
            emit_metric("check_only_findings", findings_count=len(findings),
                        elapsed_ms=int(time.time() * 1000 - start_ms))
            # PreToolUse:Read 只做提醒，不阻塞（exit 2 会级联阻塞 Edit/Write）
            sys.exit(0)
        sys.exit(0)

    file_path = get_file_path()
    if not file_path:
        sys.exit(0)

    file_path = make_relative(file_path)

    # ── Fragment dedup: only inject new fragments ──
    already_injected = _read_injected()

    # 机制 A（主动投影） — 只注入本 session 未见过的 fragment
    fragments = match(file_path)
    if not fragments:
        fragments = list(FALLBACK_FRAGMENTS) if isinstance(FALLBACK_FRAGMENTS, list) else [FALLBACK_FRAGMENTS]

    new_fragments = [f for f in fragments if f not in already_injected]

    content_parts: list[str] = []
    for name in new_fragments:
        text = load_fragment(name)
        if text:
            content_parts.append(text)

    # Fragment 注入 metrics
    # [ADR-038 D1: fragment_inject_count + fragment_token_cost (按字节/4 近似)]
    if new_fragments:
        total_bytes = sum(len(p.encode("utf-8")) for p in content_parts)
        emit_metric(
            "fragment_inject",
            file_path=file_path,
            fragments=new_fragments,
            count=len(new_fragments),
            bytes=total_bytes,
            est_tokens=total_bytes // 4,
        )

    if content_parts:
        output_parts.append("## Context\n")
        output_parts.append("\n\n---\n\n".join(content_parts))
        # Update injected set
        already_injected.update(new_fragments)
        _write_injected(already_injected)

    # 机制 B（guard 检查） — 有问题才报（不受 dedup 影响，每次都检查）
    findings = run_guards(file_path)

    if findings:
        # Findings metrics — 按 severity/blocking/category 分类
        # [ADR-038 D1: guard_findings_count + guard_blocking_count]
        blocking_count = sum(
            1 for f in findings
            if (isinstance(f, dict) and f.get("blocking"))
            or (not isinstance(f, dict) and getattr(f, "blocking", False))
        )
        categories: dict[str, int] = {}
        severities: dict[str, int] = {}
        for f in findings:
            cat = f.get("category", "general") if isinstance(f, dict) else getattr(f, "category", "general")
            sev = f.get("severity", "P2") if isinstance(f, dict) else getattr(f, "severity", "P2")
            categories[cat] = categories.get(cat, 0) + 1
            severities[sev] = severities.get(sev, 0) + 1
        emit_metric(
            "guard_findings",
            file_path=file_path,
            findings_count=len(findings),
            blocking_count=blocking_count,
            categories=categories,
            severities=severities,
        )

        write_session_signal(findings)
        append_findings(output_parts, findings)

    # 性能 metrics — 每次都记录，便于观察 hook 整体开销
    # [ADR-038 D1: hook_execution_ms]
    emit_metric(
        "hook_done",
        file_path=file_path,
        had_output=bool(output_parts),
        elapsed_ms=int(time.time() * 1000 - start_ms),
    )

    if output_parts:
        sys.stderr.write("\n".join(output_parts) + "\n")
        sys.exit(2)  # Claude Code hook 协议：exit 2 = 有反馈

    sys.exit(0)


if __name__ == "__main__":
    main()
