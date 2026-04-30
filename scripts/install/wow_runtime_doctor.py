#!/usr/bin/env python3
"""Diagnose wow-harness parity across Claude Code, Cursor, OpenCode, and Codex."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def repo_root() -> Path:
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".wow-harness" / "MANIFEST.yaml").is_file():
            return candidate
    raise SystemExit("wow-runtime-doctor: not inside a wow-harness checkout")


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def hook_count(settings: dict) -> int:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    total = 0
    for entries in hooks.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            total += len(entry.get("hooks", [])) if isinstance(entry, dict) else 0
    return total


def cursor_project_hooks(root: Path) -> dict:
    data = read_json(root / ".cursor" / "hooks.json")
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    cli = read_json(root / ".cursor" / "cli.json")
    permissions = cli.get("permissions") if isinstance(cli.get("permissions"), dict) else {}
    denies = permissions.get("deny") if isinstance(permissions.get("deny"), list) else []
    deny_text = json.dumps(denies)
    return {
        "present": bool(data),
        "session_banner": "session-start-harness-banner" in json.dumps(hooks),
        "before_submit": "beforeSubmitPrompt" in hooks,
        "post_write_bundle": "post-write-bundle" in json.dumps(hooks),
        "cli_permissions": bool(permissions),
        "dangerous_shell_deny": "Shell(rm)" in denies and "Shell(dd)" in denies,
        "secret_deny": ".env" in deny_text and ".key" in deny_text,
    }


def codex_project_hooks(root: Path) -> dict:
    data = read_json(root / ".codex" / "hooks.json")
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    config = root / ".codex" / "config.toml"
    config_text = config.read_text(encoding="utf-8", errors="replace") if config.is_file() else ""
    hook_text = json.dumps(hooks)
    return {
        "project_hooks": bool(data),
        "feature_flag": "codex_hooks" in config_text and "true" in config_text.lower(),
        "session_start": "SessionStart" in hooks and "session-start" in hook_text,
        "pre_tool_use": "PreToolUse" in hooks and "pre-sanitize" in hook_text and "pre-deploy-guard" in hook_text,
        "permission_request": "PermissionRequest" in hooks and "permission-request-deploy-guard" in hook_text,
        "post_tool_use": "PostToolUse" in hooks and "post-write-bundle" in hook_text,
        "stop": "Stop" in hooks and "stop-check" in hook_text,
    }


def diagnose(root: Path) -> dict:
    claude_settings = read_json(root / ".claude" / "settings.json")
    opencode_config = read_json(root / "opencode.json")
    opencode_permission = opencode_config.get("permission") if isinstance(opencode_config.get("permission"), dict) else {}
    opencode_plugin = root / ".opencode" / "plugins" / "wow-harness-runtime.js"
    opencode_text = opencode_plugin.read_text(encoding="utf-8", errors="replace") if opencode_plugin.is_file() else ""
    codex_hooks = codex_project_hooks(root)
    return {
        "repo": str(root),
        "claude_code": {
            "project_settings": (root / ".claude" / "settings.json").is_file(),
            "hook_commands": hook_count(claude_settings),
            "native_hooks": True,
        },
        "cursor": {
            **cursor_project_hooks(root),
            "global_dispatcher": (Path.home() / ".wow-agent-hooks" / "wow_agent_dispatch.py").is_file(),
            "agent_wrapper": (Path.home() / ".wow-agent-hooks" / "va-agent-wrap.sh").is_file(),
            "cursor_agent_bin": shutil.which("cursor-agent") or shutil.which("agent"),
        },
        "opencode": {
            "project_config": (root / "opencode.json").is_file(),
            "project_plugin": opencode_plugin.is_file(),
            "permissions": bool(opencode_permission),
            "bash_ask_default": isinstance(opencode_permission.get("bash"), dict)
            and opencode_permission.get("bash", {}).get("*") == "ask",
            "secret_deny": ".env" in json.dumps(opencode_permission)
            and ".key" in json.dumps(opencode_permission),
            "guard_feedback_after_edit": "guard-feedback.py" in opencode_text,
            "visible_log": "harness-visible.jsonl" in opencode_text,
            "global_plugin": (Path.home() / ".config" / "opencode" / "plugins" / "wow-harness-autodispatch.js").is_file(),
        },
        "codex": {
            "agents_md": (root / "AGENTS.md").is_file(),
            "codex_check": (root / "scripts" / "codex" / "wow_codex_check.py").is_file(),
            **codex_hooks,
            "native_hooks": (root / ".codex" / "hooks.json").is_file() and codex_hooks.get("feature_flag", False),
            "review_authority": False,
            "adr_boundary": "ADR-045 supersedes ADR-041 only for advisory Codex lifecycle hooks",
        },
        "activity_log": str(root / ".wow-harness" / "state" / "harness-visible.jsonl"),
    }


def print_human(report: dict) -> None:
    print("## wow-harness Runtime Doctor")
    print(f"repo: {report['repo']}")
    print(f"activity log: {report['activity_log']}")

    claude = report["claude_code"]
    print("\nClaude Code")
    print(f"- native hooks: {'yes' if claude['native_hooks'] else 'no'}")
    print(f"- project hook commands: {claude['hook_commands']}")

    cursor = report["cursor"]
    print("\nCursor / Cursor CLI")
    print(f"- project hooks present: {'yes' if cursor['present'] else 'no'}")
    print(f"- session banner: {'yes' if cursor['session_banner'] else 'no'}")
    print(f"- beforeSubmit visibility: {'yes' if cursor['before_submit'] else 'no'}")
    print(f"- post-write feedback bundle: {'yes' if cursor['post_write_bundle'] else 'no'}")
    print(f"- CLI permissions: {'yes' if cursor['cli_permissions'] else 'no'}")
    print(f"- destructive shell deny: {'yes' if cursor['dangerous_shell_deny'] else 'no'}")
    print(f"- secret read/write deny: {'yes' if cursor['secret_deny'] else 'no'}")
    print(f"- global dispatcher installed: {'yes' if cursor['global_dispatcher'] else 'no'}")
    print(f"- agent wrapper installed: {'yes' if cursor['agent_wrapper'] else 'no'}")

    opencode = report["opencode"]
    print("\nOpenCode")
    print(f"- project config: {'yes' if opencode['project_config'] else 'no'}")
    print(f"- project plugin: {'yes' if opencode['project_plugin'] else 'no'}")
    print(f"- explicit permissions: {'yes' if opencode['permissions'] else 'no'}")
    print(f"- bash ask-by-default: {'yes' if opencode['bash_ask_default'] else 'no'}")
    print(f"- secret read/write deny: {'yes' if opencode['secret_deny'] else 'no'}")
    print(f"- guard-feedback after edits: {'yes' if opencode['guard_feedback_after_edit'] else 'no'}")
    print(f"- visible log writes: {'yes' if opencode['visible_log'] else 'no'}")

    codex = report["codex"]
    print("\nCodex")
    print(f"- AGENTS.md: {'yes' if codex['agents_md'] else 'no'}")
    print(f"- mechanical check: {'yes' if codex['codex_check'] else 'no'}")
    print(f"- project hooks: {'yes' if codex['project_hooks'] else 'no'}")
    print(f"- hook feature flag: {'yes' if codex['feature_flag'] else 'no'}")
    print(f"- session start context: {'yes' if codex['session_start'] else 'no'}")
    print(f"- pre-tool guardrails: {'yes' if codex['pre_tool_use'] else 'no'}")
    print(f"- approval guardrail: {'yes' if codex['permission_request'] else 'no'}")
    print(f"- post-write feedback: {'yes' if codex['post_tool_use'] else 'no'}")
    print(f"- stop check: {'yes' if codex['stop'] else 'no'}")
    print("- review authority: no (Codex remains an execution lane)")
    print("- fallback run: python3 scripts/codex/wow_codex_check.py --strict")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check wow-harness runtime parity.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable output.")
    args = parser.parse_args()
    report = diagnose(repo_root())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
