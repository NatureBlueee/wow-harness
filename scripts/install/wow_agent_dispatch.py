#!/usr/bin/env python3
"""Global entrypoint: resolve wow-harness project root and run the right hook script.

Installed to ~/.wow-agent-hooks/wow_agent_dispatch.py by wow_global_hooks.py.
See docs/dual-cli-global-hooks.md.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

CURSOR_SUBCOMMANDS = frozenset(
    {
        "pre-sanitize",
        "pre-deploy-guard",
        "pre-auto-python3",
        "pre-tool-call-counter",
        "pre-review-gatekeeper",
        "post-write-bundle",
        "post-tool-failure",
        "session-start-reset-risk",
        "session-start-harness-banner",
        "session-start-magic-docs",
        "session-start-toolkit-reminder",
        "pre-compact",
        "stop-evaluator",
        "session-end-reflection",
        "session-end-trace",
        "session-end-deploy-progress",
        "before-submit-harness-ping",
    }
)

CLAUDE_SUBCOMMANDS = frozenset(
    {
        "pre-sanitize",
        "pre-deploy-guard",
        "pre-auto-python3",
        "pre-tool-call-counter",
        "pre-review-gatekeeper",
        "post-guard-feedback",
        "post-loop-detection",
        "post-risk-tracker",
        "post-tool-failure",
        "session-start-reset-risk",
        "session-start-harness-banner",
        "session-start-magic-docs",
        "session-start-toolkit-reminder",
        "pre-compact",
        "stop-evaluator",
        "session-end-reflection",
        "session-end-trace",
        "session-end-deploy-progress",
    }
)


def noop(runtime: str, subcommand: str) -> None:
    _log_event(runtime, subcommand, mode="noop")
    if runtime == "cursor":
        if subcommand.startswith("pre-"):
            print(json.dumps({"permission": "allow"}))
        else:
            print("{}")
    else:
        if subcommand in {"pre-sanitize", "pre-auto-python3"}:
            print(json.dumps({}))
        else:
            print("", end="")
    sys.exit(0)


def read_stdin() -> str:
    try:
        return sys.stdin.read()
    except OSError:
        return ""


def normalize_stdin_for_cursor(stdin: str) -> str:
    """Align Cursor hook payloads with Claude-side expectations where safe.

    Cursor often puts the shell working directory in ``tool_input.working_directory``
    while also providing ``workspace_roots``; some scripts only read top-level ``cwd``.
    We synthesize ``cwd`` when missing so downstream hooks resolve relative paths
    consistently (especially sanitize-on-read for Shell).
    """
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


def resolve_repo_root() -> Path | None:
    env = os.environ.get("CURSOR_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).resolve())
    here = Path.cwd().resolve()
    candidates.extend([here, *here.parents])

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / ".wow-harness" / "MANIFEST.yaml").is_file():
            return candidate
    return None


def has_project_cursor_hooks(root: Path) -> bool:
    return (root / ".cursor" / "hooks.json").is_file()


def _running_global_cursor_dispatcher() -> bool:
    """True when this process is the user-level copy under ``~/.wow-agent-hooks/``."""
    try:
        return Path(__file__).resolve().parent == Path.home() / ".wow-agent-hooks"
    except OSError:
        return False


def cursor_global_should_yield_to_project_hooks(root: Path) -> bool:
    """Global autodispatch must noop when the repo already has project Cursor hooks.

    When ``hooks.json`` invokes the **in-repo** ``scripts/install/wow_agent_dispatch.py``
    (phase2 bundle), we must still run the bridge — only the **global** dispatcher
    installed to ``~/.wow-agent-hooks/`` should yield to avoid double execution.
    """
    return _running_global_cursor_dispatcher() and has_project_cursor_hooks(root)


def has_project_claude_hooks(root: Path) -> bool:
    settings = root / ".claude" / "settings.json"
    if not settings.is_file():
        return False
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("hooks"))


def script_path(root: Path, relative: str) -> Path:
    return root / relative


def run_script(root: Path, argv: list[str], stdin: str, timeout: int | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        input=stdin,
        text=True,
        capture_output=True,
        cwd=str(root),
        timeout=timeout,
    )


def passthrough(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    sys.exit(result.returncode)


def _log_event(runtime: str, subcommand: str, *, mode: str, root: Path | None = None, detail: str | None = None) -> None:
    """Best-effort JSONL logging for debugging autodispatch behavior."""
    try:
        log_dir = Path.home() / ".wow-agent-hooks" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "runtime": runtime,
            "subcommand": subcommand,
            "mode": mode,
        }
        if root is not None:
            record["repo_root"] = str(root)
        if detail:
            record["detail"] = detail
        with open(log_dir / "dispatch.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _append_visible_touch(root: Path, runtime: str, subcommand: str) -> None:
    """Project-local JSONL + optional stderr trace so users see harness activity."""
    try:
        scripts_dir = root / "scripts" / "lib"
        sd = str(scripts_dir)
        if sd not in sys.path:
            sys.path.insert(0, sd)
        from harness_visible import append_touch  # noqa: PLC0415

        append_touch(root, runtime, subcommand)
    except Exception:
        pass
    try:
        if os.environ.get("WOW_HARNESS_STDERR_TRACE", "").strip().lower() in ("1", "true", "yes", "on"):
            print(f"[wow-harness] {runtime} → {subcommand}", file=sys.stderr)
    except Exception:
        pass


def run_cursor_bridge(root: Path, subcommand: str, stdin: str) -> None:
    _log_event("cursor", subcommand, mode="run_global_bridge", root=root)
    _append_visible_touch(root, "cursor", subcommand)
    py = sys.executable
    if subcommand == "before-submit-harness-ping":
        result = run_script(
            root,
            [py, str(script_path(root, "scripts/hooks/before-submit-harness-ping.py"))],
            stdin,
            5,
        )
        if result.stderr:
            sys.stderr.write(result.stderr)
        if result.stdout:
            sys.stdout.write(result.stdout)
        else:
            print("{}")
        sys.exit(result.returncode)

    if subcommand == "pre-sanitize":
        result = run_script(root, [py, str(script_path(root, "scripts/hooks/sanitize-on-read.py"))], stdin, 30)
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
        return

    if subcommand == "pre-deploy-guard":
        result = run_script(root, [py, str(script_path(root, "scripts/deploy-guard.py"))], stdin, 15)
        if result.returncode == 1:
            msg = (result.stderr or "").strip() or "deploy-guard blocked this shell command"
            print(json.dumps({"permission": "deny", "user_message": msg, "agent_message": msg}, ensure_ascii=False))
            sys.exit(2)
        print(json.dumps({"permission": "allow"}))
        return

    if subcommand == "pre-auto-python3":
        result = run_script(root, [py, str(script_path(root, "scripts/hooks/auto-python3.py"))], stdin, 10)
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
        return

    if subcommand == "pre-tool-call-counter":
        result = run_script(root, [py, str(script_path(root, "scripts/hooks/tool-call-counter.py"))], stdin, 10)
        text = (result.stdout or "").strip()
        if text and not text.startswith("{"):
            print(json.dumps({"permission": "allow", "agent_message": text}, ensure_ascii=False))
        else:
            print(json.dumps({"permission": "allow"}))
        return

    if subcommand == "pre-review-gatekeeper":
        result = run_script(root, [py, str(script_path(root, "scripts/hooks/review-agent-gatekeeper.py"))], stdin, 10)
        if result.returncode == 2:
            msg = (result.stderr or "").strip() or "review-agent gatekeeper blocked Task spawn"
            print(json.dumps({"permission": "deny", "user_message": msg, "agent_message": msg}, ensure_ascii=False))
            sys.exit(2)
        print(json.dumps({"permission": "allow"}))
        return

    if subcommand == "post-write-bundle":
        chunks: list[str] = []
        result1 = run_script(root, [py, str(script_path(root, "scripts/guard-feedback.py"))], stdin, 45)
        if result1.returncode == 2 and (result1.stderr or "").strip():
            chunks.append(result1.stderr.strip())
        result2 = run_script(root, [py, str(script_path(root, "scripts/hooks/loop-detection.py"))], stdin, 10)
        raw2 = (result2.stdout or "").strip()
        try:
            data2 = json.loads(raw2) if raw2 else {}
            hso = data2.get("hookSpecificOutput") or {}
            additional = hso.get("additionalContext") or hso.get("additional_context")
            if additional:
                chunks.append(str(additional))
        except json.JSONDecodeError:
            pass
        run_script(root, [py, str(script_path(root, "scripts/hooks/risk-tracker.py"))], stdin, 15)
        if chunks:
            print(json.dumps({"additional_context": "\n\n---\n\n".join(chunks)}, ensure_ascii=False))
        else:
            print("{}")
        return

    if subcommand == "post-tool-failure":
        run_script(root, [py, str(script_path(root, "scripts/hooks/failure-analyzer.py"))], stdin, 10)
        print("{}")
        return

    if subcommand in {
        "session-start-harness-banner",
        "session-start-magic-docs",
        "session-start-toolkit-reminder",
    }:
        filename = {
            "session-start-harness-banner": "session-start-harness-banner.py",
            "session-start-magic-docs": "session-start-magic-docs.py",
            "session-start-toolkit-reminder": "session-start-toolkit-reminder.py",
        }[subcommand]
        result = run_script(root, [py, str(script_path(root, f"scripts/hooks/{filename}"))], stdin, 15)
        parts = [x for x in ((result.stdout or "").strip(), (result.stderr or "").strip()) if x]
        if parts:
            print(json.dumps({"additional_context": "\n\n".join(parts)}, ensure_ascii=False))
        else:
            print("{}")
        return

    if subcommand == "session-start-reset-risk":
        subprocess.run([py, str(script_path(root, "scripts/hooks/session-start-reset-risk.py"))], cwd=str(root), timeout=10)
        print("{}")
        return

    if subcommand == "pre-compact":
        result = subprocess.run(
            ["bash", str(script_path(root, "scripts/hooks/precompact.sh"))],
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
        return

    if subcommand == "stop-evaluator":
        result = run_script(root, [py, str(script_path(root, "scripts/hooks/stop-evaluator.py"))], stdin, 25)
        if result.returncode == 2 and (result.stderr or "").strip():
            print(json.dumps({"followup_message": (result.stderr or "").strip()}, ensure_ascii=False))
        else:
            print("{}")
        sys.exit(0)

    if subcommand == "session-end-reflection":
        subprocess.run([py, str(script_path(root, "scripts/hooks/session-reflection.py"))], input=stdin, text=True, cwd=str(root), timeout=60)
        print("{}")
        return

    if subcommand == "session-end-trace":
        subprocess.run(
            [py, str(script_path(root, "scripts/hooks/trace-analyzer.py")), "analyze", "--days", "1", "--min-samples", "3"],
            cwd=str(root),
            timeout=60,
        )
        print("{}")
        return

    if subcommand == "session-end-deploy-progress":
        subprocess.run([py, str(script_path(root, "scripts/hooks/deploy-progress-on-session-end.py"))], input=stdin, text=True, cwd=str(root), timeout=60)
        print("{}")
        return

    noop("cursor", subcommand)


def run_claude_bridge(root: Path, subcommand: str, stdin: str) -> None:
    _log_event("claude", subcommand, mode="run_global_bridge", root=root)
    _append_visible_touch(root, "claude", subcommand)
    py = sys.executable
    mapping = {
        "pre-sanitize": [py, str(script_path(root, "scripts/hooks/sanitize-on-read.py"))],
        "pre-deploy-guard": [py, str(script_path(root, "scripts/deploy-guard.py"))],
        "pre-auto-python3": [py, str(script_path(root, "scripts/hooks/auto-python3.py"))],
        "pre-tool-call-counter": [py, str(script_path(root, "scripts/hooks/tool-call-counter.py"))],
        "pre-review-gatekeeper": [py, str(script_path(root, "scripts/hooks/review-agent-gatekeeper.py"))],
        "post-guard-feedback": [py, str(script_path(root, "scripts/guard-feedback.py"))],
        "post-loop-detection": [py, str(script_path(root, "scripts/hooks/loop-detection.py"))],
        "post-risk-tracker": [py, str(script_path(root, "scripts/hooks/risk-tracker.py"))],
        "post-tool-failure": [py, str(script_path(root, "scripts/hooks/failure-analyzer.py"))],
        "session-start-reset-risk": [py, str(script_path(root, "scripts/hooks/session-start-reset-risk.py"))],
        "session-start-harness-banner": [py, str(script_path(root, "scripts/hooks/session-start-harness-banner.py"))],
        "session-start-magic-docs": [py, str(script_path(root, "scripts/hooks/session-start-magic-docs.py"))],
        "session-start-toolkit-reminder": [py, str(script_path(root, "scripts/hooks/session-start-toolkit-reminder.py"))],
        "pre-compact": ["bash", str(script_path(root, "scripts/hooks/precompact.sh"))],
        "stop-evaluator": [py, str(script_path(root, "scripts/hooks/stop-evaluator.py"))],
        "session-end-reflection": [py, str(script_path(root, "scripts/hooks/session-reflection.py"))],
        "session-end-trace": [py, str(script_path(root, "scripts/hooks/trace-analyzer.py")), "analyze", "--days", "1", "--min-samples", "3"],
        "session-end-deploy-progress": [py, str(script_path(root, "scripts/hooks/deploy-progress-on-session-end.py"))],
    }
    argv = mapping.get(subcommand)
    if not argv:
        noop("claude", subcommand)
    result = run_script(root, argv, stdin, 60)
    passthrough(result)


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: wow_agent_dispatch.py <cursor|claude> <subcommand>", file=sys.stderr)
        sys.exit(1)

    runtime = sys.argv[1]
    subcommand = sys.argv[2]
    stdin = read_stdin()

    if runtime == "cursor":
        if subcommand not in CURSOR_SUBCOMMANDS:
            sys.exit(1)
        stdin = normalize_stdin_for_cursor(stdin)
    elif runtime == "claude":
        if subcommand not in CLAUDE_SUBCOMMANDS:
            sys.exit(1)
    else:
        sys.exit(1)

    root = resolve_repo_root()
    if root is None:
        _log_event(runtime, subcommand, mode="noop_no_wow")
        noop(runtime, subcommand)

    if runtime == "cursor" and cursor_global_should_yield_to_project_hooks(root):
        _log_event(runtime, subcommand, mode="noop_project_override", root=root, detail="project .cursor/hooks.json present")
        noop(runtime, subcommand)
    if runtime == "claude" and has_project_claude_hooks(root):
        _log_event(runtime, subcommand, mode="noop_project_override", root=root, detail="project .claude/settings.json hooks present")
        noop(runtime, subcommand)

    if runtime == "cursor":
        run_cursor_bridge(root, subcommand, stdin)
    else:
        run_claude_bridge(root, subcommand, stdin)


if __name__ == "__main__":
    main()
