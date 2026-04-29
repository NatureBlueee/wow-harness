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
    return {
        "present": bool(data),
        "session_banner": "session-start-harness-banner" in json.dumps(hooks),
        "before_submit": "beforeSubmitPrompt" in hooks,
        "post_write_bundle": "post-write-bundle" in json.dumps(hooks),
    }


def diagnose(root: Path) -> dict:
    claude_settings = read_json(root / ".claude" / "settings.json")
    opencode_plugin = root / ".opencode" / "plugins" / "wow-harness-runtime.js"
    opencode_text = opencode_plugin.read_text(encoding="utf-8", errors="replace") if opencode_plugin.is_file() else ""
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
            "guard_feedback_after_edit": "guard-feedback.py" in opencode_text,
            "visible_log": "harness-visible.jsonl" in opencode_text,
            "global_plugin": (Path.home() / ".config" / "opencode" / "plugins" / "wow-harness-autodispatch.js").is_file(),
        },
        "codex": {
            "agents_md": (root / "AGENTS.md").is_file(),
            "codex_check": (root / "scripts" / "codex" / "wow_codex_check.py").is_file(),
            "native_hooks": False,
            "adr_041_boundary": "no Codex router hook without a superseding ADR",
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
    print(f"- global dispatcher installed: {'yes' if cursor['global_dispatcher'] else 'no'}")
    print(f"- agent wrapper installed: {'yes' if cursor['agent_wrapper'] else 'no'}")

    opencode = report["opencode"]
    print("\nOpenCode")
    print(f"- project config: {'yes' if opencode['project_config'] else 'no'}")
    print(f"- project plugin: {'yes' if opencode['project_plugin'] else 'no'}")
    print(f"- guard-feedback after edits: {'yes' if opencode['guard_feedback_after_edit'] else 'no'}")
    print(f"- visible log writes: {'yes' if opencode['visible_log'] else 'no'}")

    codex = report["codex"]
    print("\nCodex")
    print(f"- AGENTS.md: {'yes' if codex['agents_md'] else 'no'}")
    print(f"- mechanical check: {'yes' if codex['codex_check'] else 'no'}")
    print("- native hooks: no (ADR-041 keeps Codex as an execution lane)")
    print("- run: python3 scripts/codex/wow_codex_check.py --strict")


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
