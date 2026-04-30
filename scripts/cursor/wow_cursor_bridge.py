#!/usr/bin/env python3
"""wow-harness -> Cursor Hooks bridge.

Reuses the existing wow-harness governance scripts under ``scripts/`` and
translates Claude Code style hook behavior into Cursor third-party hook JSON.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SUBCOMMANDS = frozenset(
    {
        "pre-sanitize",
        "pre-deploy-guard",
        "pre-auto-python3",
        "pre-tool-call-counter",
        "pre-review-gatekeeper",
        "pre-mcp-guard",
        "post-write-bundle",
        "post-tool-failure",
        "subagent-start",
        "subagent-stop",
        "session-start-reset-risk",
        "session-start-harness-banner",
        "session-start-magic-docs",
        "session-start-toolkit-reminder",
        "before-submit-harness-ping",
        "pre-compact",
        "stop-evaluator",
        "session-end-reflection",
        "session-end-trace",
        "session-end-deploy-progress",
    }
)

ACTIVE_REVIEW_DIR = Path(".wow-harness") / "active-review-agents"


def normalize_stdin_for_cc(stdin: str) -> str:
    """Align Cursor payloads with Claude-side hook assumptions where safe."""
    try:
        if not stdin.strip():
            return stdin
        data = json.loads(stdin)
    except json.JSONDecodeError:
        return stdin
    if not isinstance(data, dict):
        return stdin
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    roots = data.get("workspace_roots")
    first_root = roots[0] if isinstance(roots, list) and roots else None
    effective_cwd = data.get("cwd") or tool_input.get("working_directory") or first_root
    if effective_cwd and not data.get("cwd"):
        data = {**data, "cwd": effective_cwd}
    if "session_id" not in data and data.get("conversation_id"):
        data = {**data, "session_id": data["conversation_id"]}
    return json.dumps(data, ensure_ascii=False)


def resolve_repo_root() -> Path:
    env = os.environ.get("CURSOR_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        path = Path(env).resolve()
        if (path / ".wow-harness" / "MANIFEST.yaml").is_file() or (path / "CLAUDE.md").is_file():
            return path
    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".wow-harness" / "MANIFEST.yaml").is_file():
            return candidate
        if (candidate / "CLAUDE.md").is_file():
            return candidate
    return here


def _run(root: Path, argv: list[str], stdin: str, *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        input=stdin,
        text=True,
        capture_output=True,
        cwd=str(root),
        timeout=timeout,
    )


def _append_visible_touch(root: Path, subcommand: str) -> None:
    try:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from scripts.lib.harness_visible import append_touch  # noqa: PLC0415

        append_touch(root, "cursor", subcommand)
    except Exception:
        pass


def cmd_before_submit_harness_ping(root: Path, stdin: str) -> None:
    script = root / "scripts" / "hooks" / "before-submit-harness-ping.py"
    result = _run(root, [sys.executable, str(script)], stdin, timeout=5)
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.stdout:
        sys.stdout.write(result.stdout)
    else:
        print("{}")


def cmd_pre_sanitize(root: Path, stdin: str) -> None:
    script = root / "scripts" / "hooks" / "sanitize-on-read.py"
    result = _run(root, [sys.executable, str(script)], stdin, timeout=30)
    raw = (result.stdout or "").strip()
    try:
        data = json.loads(raw) if raw else {"decision": "approve"}
    except json.JSONDecodeError:
        print(json.dumps({"permission": "allow"}))
        return
    if data.get("decision") == "block":
        reason = data.get("reason", "sanitize-on-read blocked this read")
        print(json.dumps({"permission": "deny", "user_message": reason, "agent_message": reason}, ensure_ascii=False))
        sys.exit(2)
    print(json.dumps({"permission": "allow"}))


def cmd_pre_deploy_guard(root: Path, stdin: str) -> None:
    script = root / "scripts" / "deploy-guard.py"
    result = _run(root, [sys.executable, str(script)], stdin, timeout=15)
    if result.returncode == 1:
        msg = (result.stderr or "").strip() or "deploy-guard blocked this shell command"
        print(json.dumps({"permission": "deny", "user_message": msg, "agent_message": msg}, ensure_ascii=False))
        sys.exit(2)
    print(json.dumps({"permission": "allow"}))


def cmd_pre_auto_python3(root: Path, stdin: str) -> None:
    script = root / "scripts" / "hooks" / "auto-python3.py"
    result = _run(root, [sys.executable, str(script)], stdin, timeout=10)
    raw = (result.stdout or "").strip()
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        print(json.dumps({"permission": "allow"}))
        return
    hso = data.get("hookSpecificOutput") or {}
    updated = hso.get("updatedInput") or hso.get("updated_input")
    if updated:
        print(json.dumps({"permission": "allow", "updated_input": updated}, ensure_ascii=False))
    else:
        print(json.dumps({"permission": "allow"}))


def cmd_pre_tool_call_counter(root: Path, stdin: str) -> None:
    script = root / "scripts" / "hooks" / "tool-call-counter.py"
    result = _run(root, [sys.executable, str(script)], stdin, timeout=10)
    text = (result.stdout or "").strip()
    if text and not text.startswith("{"):
        print(json.dumps({"permission": "allow", "agent_message": text}, ensure_ascii=False))
    else:
        print(json.dumps({"permission": "allow"}))


def cmd_pre_review_gatekeeper(root: Path, stdin: str) -> None:
    script = root / "scripts" / "hooks" / "review-agent-gatekeeper.py"
    result = _run(root, [sys.executable, str(script)], stdin, timeout=10)
    if result.returncode == 2:
        msg = (result.stderr or "").strip() or "review-agent gatekeeper blocked Task spawn"
        print(json.dumps({"permission": "deny", "user_message": msg, "agent_message": msg}, ensure_ascii=False))
        sys.exit(2)
    print(json.dumps({"permission": "allow"}))


def cmd_post_write_bundle(root: Path, stdin: str) -> None:
    chunks: list[str] = []

    guard_feedback = root / "scripts" / "guard-feedback.py"
    result1 = _run(root, [sys.executable, str(guard_feedback)], stdin, timeout=45)
    if result1.returncode == 2 and (result1.stderr or "").strip():
        chunks.append(result1.stderr.strip())

    loop_detection = root / "scripts" / "hooks" / "loop-detection.py"
    result2 = _run(root, [sys.executable, str(loop_detection)], stdin, timeout=10)
    raw2 = (result2.stdout or "").strip()
    try:
        data2 = json.loads(raw2) if raw2 else {}
        hso = data2.get("hookSpecificOutput") or {}
        additional = hso.get("additionalContext") or hso.get("additional_context")
        if additional:
            chunks.append(str(additional))
    except json.JSONDecodeError:
        pass

    risk_tracker = root / "scripts" / "hooks" / "risk-tracker.py"
    _run(root, [sys.executable, str(risk_tracker)], stdin, timeout=15)

    if chunks:
        print(json.dumps({"additional_context": "\n\n---\n\n".join(chunks)}, ensure_ascii=False))
    else:
        print("{}")


def cmd_post_tool_failure(root: Path, stdin: str) -> None:
    script = root / "scripts" / "hooks" / "failure-analyzer.py"
    subprocess.run(
        [sys.executable, str(script)],
        input=stdin,
        text=True,
        cwd=str(root),
        capture_output=True,
        timeout=10,
    )
    print("{}")


def cmd_session_start_fragment(root: Path, stdin: str, script_name: str) -> None:
    script = root / "scripts" / "hooks" / script_name
    result = _run(root, [sys.executable, str(script)], stdin, timeout=15)
    parts = [part for part in ((result.stdout or "").strip(), (result.stderr or "").strip()) if part]
    if parts:
        print(json.dumps({"additional_context": "\n\n".join(parts)}, ensure_ascii=False))
    else:
        print("{}")


def cmd_pre_compact(root: Path, stdin: str) -> None:
    script = root / "scripts" / "hooks" / "precompact.sh"
    result = subprocess.run(
        ["bash", str(script)],
        input=stdin,
        text=True,
        capture_output=True,
        cwd=str(root),
        timeout=15,
    )
    text = (result.stdout or "").strip()
    if text:
        print(json.dumps({"user_message": text}, ensure_ascii=False))
    else:
        print("{}")


def cmd_stop_evaluator(root: Path, stdin: str) -> None:
    script = root / "scripts" / "hooks" / "stop-evaluator.py"
    result = _run(root, [sys.executable, str(script)], stdin, timeout=25)
    if result.returncode == 2 and (result.stderr or "").strip():
        print(json.dumps({"followup_message": (result.stderr or "").strip()}, ensure_ascii=False))
    else:
        print("{}")
    sys.exit(0)


def cmd_pre_mcp_guard(root: Path, stdin: str) -> None:
    script = root / "scripts" / "hooks" / "pre-mcp-guard.py"
    result = _run(root, [sys.executable, str(script)], stdin, timeout=10)
    raw = (result.stdout or "").strip()
    if result.returncode == 2:
        msg = (result.stderr or "").strip() or "pre-mcp-guard blocked this MCP call"
        print(json.dumps({"permission": "deny", "user_message": msg, "agent_message": msg}, ensure_ascii=False))
        sys.exit(2)
    if raw:
        sys.stdout.write(raw + "\n")
    else:
        print(json.dumps({"permission": "allow"}))


def _subagent_marker(root: Path, agent_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in agent_id)[:80] or "unknown"
    return root / ACTIVE_REVIEW_DIR / f"cursor-{safe}.json"


def cmd_subagent_start(root: Path, stdin: str) -> None:
    try:
        data = json.loads(stdin) if stdin.strip() else {}
    except json.JSONDecodeError:
        data = {}
    agent_id = str(data.get("subagent_id") or data.get("agent_id") or data.get("id") or f"pid-{os.getpid()}")
    agent_type = data.get("subagent_type") or data.get("agent_type") or data.get("type") or "unknown"
    try:
        marker_dir = root / ACTIVE_REVIEW_DIR
        marker_dir.mkdir(parents=True, exist_ok=True)
        import time as _t
        _subagent_marker(root, agent_id).write_text(
            json.dumps({"agent_id": agent_id, "agent_type": agent_type, "started_at": _t.time(), "runtime": "cursor"}),
            encoding="utf-8",
        )
    except OSError:
        pass
    print("{}")


def cmd_subagent_stop(root: Path, stdin: str) -> None:
    try:
        data = json.loads(stdin) if stdin.strip() else {}
    except json.JSONDecodeError:
        data = {}
    agent_id = str(data.get("subagent_id") or data.get("agent_id") or data.get("id") or f"pid-{os.getpid()}")
    try:
        marker = _subagent_marker(root, agent_id)
        if marker.exists():
            marker.unlink()
    except OSError:
        pass
    print("{}")


def cmd_session_end(root: Path, stdin: str, script_name: str) -> None:
    script = root / "scripts" / "hooks" / script_name
    subprocess.run(
        [sys.executable, str(script)],
        input=stdin,
        text=True,
        cwd=str(root),
        timeout=60,
    )
    print("{}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in _SUBCOMMANDS:
        print(
            "usage: wow_cursor_bridge.py <subcommand>\n"
            f"subcommands: {', '.join(sorted(_SUBCOMMANDS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    subcommand = sys.argv[1]
    root = resolve_repo_root()
    os.chdir(root)
    stdin = normalize_stdin_for_cc(sys.stdin.read())
    _append_visible_touch(root, subcommand)

    if subcommand == "pre-sanitize":
        cmd_pre_sanitize(root, stdin)
    elif subcommand == "pre-deploy-guard":
        cmd_pre_deploy_guard(root, stdin)
    elif subcommand == "pre-auto-python3":
        cmd_pre_auto_python3(root, stdin)
    elif subcommand == "pre-tool-call-counter":
        cmd_pre_tool_call_counter(root, stdin)
    elif subcommand == "pre-review-gatekeeper":
        cmd_pre_review_gatekeeper(root, stdin)
    elif subcommand == "pre-mcp-guard":
        cmd_pre_mcp_guard(root, stdin)
    elif subcommand == "subagent-start":
        cmd_subagent_start(root, stdin)
    elif subcommand == "subagent-stop":
        cmd_subagent_stop(root, stdin)
    elif subcommand == "post-write-bundle":
        cmd_post_write_bundle(root, stdin)
    elif subcommand == "post-tool-failure":
        cmd_post_tool_failure(root, stdin)
    elif subcommand == "before-submit-harness-ping":
        cmd_before_submit_harness_ping(root, stdin)
    elif subcommand == "session-start-reset-risk":
        subprocess.run([sys.executable, str(root / "scripts" / "hooks" / "session-start-reset-risk.py")], cwd=str(root), timeout=10)
        print("{}")
    elif subcommand == "session-start-harness-banner":
        cmd_session_start_fragment(root, stdin, "session-start-harness-banner.py")
    elif subcommand == "session-start-magic-docs":
        cmd_session_start_fragment(root, stdin, "session-start-magic-docs.py")
    elif subcommand == "session-start-toolkit-reminder":
        cmd_session_start_fragment(root, stdin, "session-start-toolkit-reminder.py")
    elif subcommand == "pre-compact":
        cmd_pre_compact(root, stdin)
    elif subcommand == "stop-evaluator":
        cmd_stop_evaluator(root, stdin)
    elif subcommand == "session-end-reflection":
        cmd_session_end(root, stdin, "session-reflection.py")
    elif subcommand == "session-end-trace":
        subprocess.run(
            [sys.executable, str(root / "scripts" / "hooks" / "trace-analyzer.py"), "analyze", "--days", "1", "--min-samples", "3"],
            cwd=str(root),
            timeout=60,
        )
        print("{}")
    elif subcommand == "session-end-deploy-progress":
        cmd_session_end(root, stdin, "deploy-progress-on-session-end.py")


if __name__ == "__main__":
    main()
