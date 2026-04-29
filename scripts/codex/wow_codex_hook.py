#!/usr/bin/env python3
"""Codex native hook adapter for wow-harness.

Codex now exposes lifecycle hooks, so wow-harness can project the same
advisory feedback plane into Codex that Claude Code gets through hooks:
session context, Bash guardrails, post-edit guard feedback, and a Stop check.

This is deliberately not a Codex router and not a review authority. It only
calls existing repository scripts and translates their output into Codex hook
JSON shapes.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class RunResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


PATCH_PATH_MARKERS = (
    "*** Add File:",
    "*** Update File:",
    "*** Delete File:",
    "*** Move to:",
)


def read_payload() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def repo_root(payload: dict) -> Path:
    candidates: list[Path] = []
    raw_cwd = payload.get("cwd")
    if isinstance(raw_cwd, str) and raw_cwd:
        candidates.append(Path(raw_cwd).resolve())
    candidates.append(Path.cwd().resolve())

    seen: set[Path] = set()
    for start in candidates:
        for candidate in (start, *start.parents):
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / ".wow-harness" / "MANIFEST.yaml").is_file():
                return candidate

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except OSError:
        pass
    return Path.cwd().resolve()


def run_process(root: Path, argv: list[str], stdin: str, timeout: int) -> RunResult:
    try:
        result = subprocess.run(
            argv,
            input=stdin,
            text=True,
            capture_output=True,
            cwd=str(root),
            timeout=timeout,
            check=False,
        )
        return RunResult(result.returncode, result.stdout or "", result.stderr or "")
    except subprocess.TimeoutExpired as exc:
        return RunResult(
            124,
            exc.stdout or "",
            exc.stderr or f"timed out after {timeout}s",
            True,
        )
    except OSError as exc:
        return RunResult(127, "", str(exc))


def run_py(root: Path, relative: str, stdin: str, timeout: int) -> RunResult:
    return run_process(root, ["python3", str(root / relative)], stdin, timeout)


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def pretool_deny(reason: str) -> None:
    print_json(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )


def permission_request_deny(reason: str) -> None:
    print_json(
        {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {
                    "behavior": "deny",
                    "message": reason,
                },
            }
        }
    )


def post_tool_context(text: str) -> None:
    print_json(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": text,
            }
        }
    )


def stop_continue(reason: str) -> None:
    print_json({"decision": "block", "reason": reason})


def append_visible(root: Path, subcommand: str, **extra: object) -> None:
    try:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)
        from scripts.lib.harness_visible import append_touch  # noqa: PLC0415

        append_touch(root, "codex", subcommand, **extra)
    except Exception:
        pass


def normalize_payload(payload: dict, root: Path) -> str:
    data = dict(payload)
    data.setdefault("cwd", str(root))
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        data["tool_input"] = {}
    return json.dumps(data, ensure_ascii=False)


def parse_json_object(text: str) -> dict:
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def cmd_session_start(root: Path, stdin: str) -> int:
    scripts = [
        ("scripts/hooks/session-start-reset-risk.py", 10),
        ("scripts/hooks/session-start-harness-banner.py", 15),
        ("scripts/hooks/session-start-magic-docs.py", 15),
        ("scripts/hooks/session-start-toolkit-reminder.py", 15),
    ]
    parts = [
        "## wow-harness Codex hooks active\n\n"
        "Codex is still an execution lane, not a Gate reviewer. Native Codex hooks "
        "now provide advisory session context, Bash guardrails, post-edit feedback, "
        "and a Stop-time mechanical check. If hooks are disabled or untrusted, run "
        "`python3 scripts/codex/wow_codex_check.py --strict` before claiming completion."
    ]
    for script, timeout in scripts:
        result = run_py(root, script, stdin, timeout)
        text = (result.stdout or "").strip()
        if text:
            parts.append(text)
    print_json(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "\n\n---\n\n".join(parts),
            }
        }
    )
    return 0


def cmd_pre_sanitize(root: Path, stdin: str) -> int:
    result = run_py(root, "scripts/hooks/sanitize-on-read.py", stdin, 30)
    data = parse_json_object(result.stdout)
    if data.get("decision") == "block":
        pretool_deny(str(data.get("reason") or result.stderr or "sanitize-on-read blocked this command"))
        return 0
    print_json({})
    return 0


def cmd_pre_deploy_guard(root: Path, stdin: str) -> int:
    result = run_py(root, "scripts/deploy-guard.py", stdin, 15)
    if result.returncode == 1:
        pretool_deny((result.stderr or "deploy-guard blocked this command").strip())
        return 0
    print_json({})
    return 0


def cmd_permission_request_deploy_guard(root: Path, stdin: str) -> int:
    result = run_py(root, "scripts/deploy-guard.py", stdin, 15)
    if result.returncode == 1:
        permission_request_deny((result.stderr or "deploy-guard blocked this approval").strip())
        return 0
    print_json({})
    return 0


def extract_patch_text(payload: dict) -> str:
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    tool_response = payload.get("tool_response") if isinstance(payload.get("tool_response"), dict) else {}
    candidates = [
        tool_input.get("command"),
        tool_input.get("patch"),
        tool_input.get("patchText"),
        tool_response.get("patch"),
        tool_response.get("patchText"),
    ]
    args = tool_response.get("args") if isinstance(tool_response.get("args"), dict) else {}
    candidates.extend([args.get("patch"), args.get("patchText")])
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
    return ""


def extract_patch_paths(text: str) -> list[str]:
    paths: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        for marker in PATCH_PATH_MARKERS:
            if stripped.startswith(marker):
                path = stripped[len(marker):].strip()
                if path:
                    paths.append(path)
                break
    return list(dict.fromkeys(paths))


def direct_tool_paths(payload: dict) -> list[str]:
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    tool_response = payload.get("tool_response") if isinstance(payload.get("tool_response"), dict) else {}
    candidates = [
        tool_input.get("file_path"),
        tool_input.get("path"),
        tool_input.get("target"),
        tool_response.get("file_path"),
        tool_response.get("path"),
        tool_response.get("target"),
    ]
    paths = [item for item in candidates if isinstance(item, str) and item]
    for key in ("files", "paths"):
        value = tool_input.get(key)
        if isinstance(value, list):
            paths.extend(item for item in value if isinstance(item, str) and item)
    return list(dict.fromkeys(paths))


def normalize_repo_path(root: Path, raw_path: str) -> str | None:
    cleaned = raw_path.strip().strip("\"'")
    if not cleaned:
        return None
    try:
        path = Path(cleaned)
        resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
        rel = resolved.relative_to(root)
        return rel.as_posix()
    except (OSError, RuntimeError, ValueError):
        return None


def changed_paths(root: Path, payload: dict) -> list[str]:
    tool_name = str(payload.get("tool_name") or "")
    raw_paths: list[str] = []
    if tool_name == "apply_patch":
        raw_paths.extend(extract_patch_paths(extract_patch_text(payload)))
    raw_paths.extend(direct_tool_paths(payload))
    normalized = [item for item in (normalize_repo_path(root, raw) for raw in raw_paths) if item]
    return list(dict.fromkeys(normalized))


def edit_payload(root: Path, rel_path: str) -> str:
    return json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(root / rel_path)},
            "cwd": str(root),
        },
        ensure_ascii=False,
    )


def cmd_post_write_bundle(root: Path, payload: dict) -> int:
    chunks: list[str] = []
    paths = changed_paths(root, payload)

    for rel_path in paths:
        stdin = edit_payload(root, rel_path)

        guard = run_py(root, "scripts/guard-feedback.py", stdin, 45)
        guard_text = (guard.stderr or guard.stdout or "").strip()
        if guard.returncode == 2 and guard_text:
            chunks.append(guard_text)

        loop = run_py(root, "scripts/hooks/loop-detection.py", stdin, 10)
        loop_data = parse_json_object(loop.stdout)
        hso = loop_data.get("hookSpecificOutput") if isinstance(loop_data.get("hookSpecificOutput"), dict) else {}
        additional = hso.get("additionalContext") or hso.get("additional_context")
        if additional:
            chunks.append(str(additional))

        run_py(root, "scripts/hooks/risk-tracker.py", stdin, 15)

    deduped = list(dict.fromkeys(chunk for chunk in chunks if chunk))
    if deduped:
        post_tool_context("\n\n---\n\n".join(deduped))
    else:
        print_json({})
    return 0


def cmd_stop_check(root: Path, payload: dict) -> int:
    if payload.get("stop_hook_active") is True:
        print_json({})
        return 0
    result = run_process(
        root,
        ["python3", str(root / "scripts" / "codex" / "wow_codex_check.py"), "--strict"],
        "",
        45,
    )
    text = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part).strip()
    if result.returncode != 0 and text:
        stop_continue(text)
        return 0
    print_json({})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="wow-harness Codex hook adapter")
    parser.add_argument(
        "subcommand",
        choices=[
            "session-start",
            "pre-sanitize",
            "pre-deploy-guard",
            "permission-request-deploy-guard",
            "post-write-bundle",
            "stop-check",
        ],
    )
    args = parser.parse_args()

    payload = read_payload()
    root = repo_root(payload)
    append_visible(root, args.subcommand, event=payload.get("hook_event_name"))
    stdin = normalize_payload(payload, root)

    if args.subcommand == "session-start":
        return cmd_session_start(root, stdin)
    if args.subcommand == "pre-sanitize":
        return cmd_pre_sanitize(root, stdin)
    if args.subcommand == "pre-deploy-guard":
        return cmd_pre_deploy_guard(root, stdin)
    if args.subcommand == "permission-request-deploy-guard":
        return cmd_permission_request_deploy_guard(root, stdin)
    if args.subcommand == "post-write-bundle":
        return cmd_post_write_bundle(root, payload)
    if args.subcommand == "stop-check":
        return cmd_stop_check(root, payload)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
