#!/usr/bin/env python3
"""Install user-level Cursor + Claude + (optional) OpenCode hooks that delegate to a wow-harness checkout.

Copies bundled ``wow_agent_dispatch.py`` and ``va-agent-wrap.sh`` to ``~/.wow-agent-hooks/``,
registers the dispatcher in ``~/.cursor/hooks.json`` and ``~/.claude/settings.json``,
and appends a managed ``agent()`` shell shim to ``~/.bashrc`` / ``~/.zshrc`` when present.
OpenCode plugin is optional (see ``scripts/install/templates/wow-harness-autodispatch.js``).

Usage (from any directory, after wow-harness is installed in a project or you use global dispatch):

  python3 scripts/install/wow_global_hooks.py install
  python3 scripts/install/wow_global_hooks.py uninstall
  python3 scripts/install/wow_global_hooks.py status

See docs/dual-cli-global-hooks.md.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path


def ts() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    b = path.with_suffix(path.suffix + f".bak.{ts()}")
    b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, b)
    return b


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def install_dir() -> Path:
    return Path(__file__).resolve().parent


def bundled_dispatcher() -> Path:
    return install_dir() / "wow_agent_dispatch.py"


def bundled_va_agent_wrap() -> Path:
    return install_dir() / "va-agent-wrap.sh"


def installed_dispatcher() -> Path:
    return Path.home() / ".wow-agent-hooks" / "wow_agent_dispatch.py"


def installed_va_agent_wrap() -> Path:
    return Path.home() / ".wow-agent-hooks" / "va-agent-wrap.sh"


SHIM_MARKER = (
    "# wow-harness-universal-agent-shim-v2 (managed by wow_global_hooks.py; do not edit by hand)"
)


def shim_body() -> str:
    return f"""{SHIM_MARKER}
if [[ -x "$HOME/.wow-agent-hooks/va-agent-wrap.sh" ]]; then
  wow_harness_agent_dispatch() {{
    "$HOME/.wow-agent-hooks/va-agent-wrap.sh" "$@"
  }}
  if ! [[ "$(type -t agent 2>/dev/null)" == function ]]; then
    agent() {{ wow_harness_agent_dispatch "$@"; }}
  fi
fi"""


def cursor_hooks_path() -> Path:
    return Path.home() / ".cursor" / "hooks.json"


def claude_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def opencode_plugins_dir() -> Path:
    return Path.home() / ".config" / "opencode" / "plugins"


def opencode_plugin_path() -> Path:
    return opencode_plugins_dir() / "wow-harness-autodispatch.js"


def opencode_template_path() -> Path:
    return install_dir() / "templates" / "wow-harness-autodispatch.js"


def copy_bundled_dispatcher() -> Path:
    src = bundled_dispatcher()
    if not src.is_file():
        raise SystemExit(f"Bundled dispatcher missing: {src}")
    dst = installed_dispatcher()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def copy_va_agent_wrap() -> Path | None:
    src = bundled_va_agent_wrap()
    if not src.is_file():
        return None
    dst = installed_va_agent_wrap()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    mode = dst.stat().st_mode
    dst.chmod(mode | 0o111)
    return dst


def strip_legacy_voiceagent_block(text: str) -> str:
    """Remove the old VoiceAgent-only ~/.bashrc / ~/.zshrc shim (if present)."""
    marker = "wow-harness VoiceAgent agent shim"
    if marker not in text:
        return text
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        if marker in lines[i]:
            i += 1
            prev_non_empty = ""
            while i < len(lines):
                li = lines[i]
                s = li.strip()
                if s and not s.startswith("#"):
                    prev_non_empty = li
                if s == "fi" and "agent()" in prev_non_empty and "_voiceagent_agent_shim" in prev_non_empty:
                    i += 1
                    break
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "".join(out)


def _strip_v2_shim_block(text: str) -> str:
    if SHIM_MARKER not in text:
        return text
    before, after = text.split(SHIM_MARKER, 1)
    lines = after.splitlines(keepends=True)
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        return before.rstrip() + "\n"
    first = lines[i].strip()
    if not (first.startswith("if [[") and "va-agent-wrap" in lines[i]):
        return text
    depth = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("if ") and s.endswith("then"):
            depth += 1
        elif depth > 0 and s == "fi":
            depth -= 1
            i += 1
            if depth == 0:
                break
            continue
        i += 1
    tail = "".join(lines[i:])
    merged = (before.rstrip() + "\n" + tail).replace("\n\n\n\n", "\n\n\n")
    return merged


def install_shell_shims() -> None:
    """Append a universal `agent` shell function that delegates to ~/.wow-agent-hooks/va-agent-wrap.sh."""
    body = shim_body().rstrip() + "\n"
    home = Path.home()
    for name in (".bashrc", ".zshrc"):
        rc = home / name
        if not rc.is_file():
            continue
        raw = rc.read_text(encoding="utf-8", errors="replace")
        text = raw.replace("\r\n", "\n")
        text = strip_legacy_voiceagent_block(text)
        text = _strip_v2_shim_block(text)
        if SHIM_MARKER in text:
            rc.write_text(text, encoding="utf-8", newline="\n")
            continue
        new_text = text.rstrip() + "\n\n" + body
        rc.write_text(new_text, encoding="utf-8", newline="\n")


def uninstall_shell_shims() -> None:
    home = Path.home()
    for name in (".bashrc", ".zshrc"):
        rc = home / name
        if not rc.is_file():
            continue
        raw = rc.read_text(encoding="utf-8", errors="replace")
        text = _strip_v2_shim_block(raw.replace("\r\n", "\n"))
        text = strip_legacy_voiceagent_block(text)
        rc.write_text(text, encoding="utf-8", newline="\n")


def uninstall_va_agent_wrap() -> None:
    p = installed_va_agent_wrap()
    backup(p)
    if p.exists():
        p.unlink()


def install_cursor_global_hooks(dispatcher: Path) -> None:
    hooks = {
        "version": 1,
        "hooks": {
            "sessionStart": [
                {"command": f'python3 "{dispatcher}" cursor session-start-reset-risk', "timeout": 5},
                {"command": f'python3 "{dispatcher}" cursor session-start-harness-banner', "timeout": 6},
                {"command": f'python3 "{dispatcher}" cursor session-start-magic-docs', "timeout": 15},
                {"command": f'python3 "{dispatcher}" cursor session-start-toolkit-reminder', "timeout": 10},
            ],
            "beforeSubmitPrompt": [
                {
                    "command": f'python3 "{dispatcher}" cursor before-submit-harness-ping',
                    "matcher": "UserPromptSubmit",
                    "timeout": 5,
                }
            ],
            "preToolUse": [
                {"command": f'python3 "{dispatcher}" cursor pre-deploy-guard', "matcher": "Shell", "timeout": 15, "failClosed": False},
                {"command": f'python3 "{dispatcher}" cursor pre-auto-python3', "matcher": "Shell", "timeout": 10},
                {"command": f'python3 "{dispatcher}" cursor pre-tool-call-counter', "timeout": 5},
                {"command": f'python3 "{dispatcher}" cursor pre-review-gatekeeper', "matcher": "Task", "timeout": 10, "failClosed": False},
                {"command": f'python3 "{dispatcher}" cursor pre-sanitize', "matcher": "Read", "timeout": 15, "failClosed": True},
                {"command": f'python3 "{dispatcher}" cursor pre-sanitize', "matcher": "Shell", "timeout": 15, "failClosed": True},
            ],
            "postToolUse": [
                {"command": f'python3 "{dispatcher}" cursor post-write-bundle', "matcher": "Write|Edit", "timeout": 60},
            ],
            "postToolUseFailure": [
                {"command": f'python3 "{dispatcher}" cursor post-tool-failure', "timeout": 10},
            ],
            "preCompact": [
                {"command": f'python3 "{dispatcher}" cursor pre-compact', "timeout": 15},
            ],
            "stop": [
                {"command": f'python3 "{dispatcher}" cursor stop-evaluator', "timeout": 30, "loop_limit": 10},
            ],
            "sessionEnd": [
                {"command": f'python3 "{dispatcher}" cursor session-end-reflection', "timeout": 15},
                {"command": f'python3 "{dispatcher}" cursor session-end-trace', "timeout": 45},
                {"command": f'python3 "{dispatcher}" cursor session-end-deploy-progress', "timeout": 10},
            ],
        },
    }

    path = cursor_hooks_path()
    backup(path)
    write_json(path, hooks)


def install_claude_global_hooks(dispatcher: Path) -> None:
    path = claude_settings_path()
    current = read_json(path) if path.exists() else {}
    backup(path)

    hooks = {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {"type": "command", "command": f'python3 "{dispatcher}" claude pre-deploy-guard', "timeout": 10},
                    {"type": "command", "if": "Bash(python *)", "command": f'python3 "{dispatcher}" claude pre-auto-python3', "timeout": 5},
                ],
            },
            {
                "matcher": "*",
                "hooks": [{"type": "command", "command": f'python3 "{dispatcher}" claude pre-tool-call-counter', "timeout": 3}],
            },
            {
                "matcher": "Task",
                "hooks": [{"type": "command", "command": f'python3 "{dispatcher}" claude pre-review-gatekeeper', "timeout": 5}],
            },
            {
                "matcher": "Read|Bash",
                "hooks": [{"type": "command", "command": f'python3 "{dispatcher}" claude pre-sanitize', "timeout": 10}],
            },
        ],
        "PostToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {"type": "command", "command": f'python3 "{dispatcher}" claude post-guard-feedback', "timeout": 30},
                    {"type": "command", "command": f'python3 "{dispatcher}" claude post-loop-detection', "timeout": 5},
                    {"type": "command", "command": f'python3 "{dispatcher}" claude post-risk-tracker', "timeout": 3},
                ],
            }
        ],
        "PreCompact": [
            {"matcher": "*", "hooks": [{"type": "command", "command": f'python3 "{dispatcher}" claude pre-compact', "timeout": 5}]}
        ],
        "SessionStart": [
            {
                "matcher": "*",
                    "hooks": [
                    {"type": "command", "command": f'python3 "{dispatcher}" claude session-start-reset-risk', "timeout": 3},
                    {"type": "command", "command": f'python3 "{dispatcher}" claude session-start-harness-banner', "timeout": 5},
                    {"type": "command", "command": f'python3 "{dispatcher}" claude session-start-magic-docs', "timeout": 10},
                    {"type": "command", "command": f'python3 "{dispatcher}" claude session-start-toolkit-reminder', "timeout": 5},
                ],
            }
        ],
        "Stop": [
            {"matcher": "*", "hooks": [{"type": "command", "command": f'python3 "{dispatcher}" claude stop-evaluator', "timeout": 10}]}
        ],
        "SessionEnd": [
            {
                "matcher": "*",
                "hooks": [
                    {"type": "command", "command": f'python3 "{dispatcher}" claude session-end-reflection', "timeout": 10},
                    {"type": "command", "command": f'python3 "{dispatcher}" claude session-end-trace', "timeout": 30},
                    {"type": "command", "command": f'python3 "{dispatcher}" claude session-end-deploy-progress', "timeout": 5},
                ],
            }
        ],
        "PostToolUseFailure": [
            {"matcher": "*", "hooks": [{"type": "command", "command": f'python3 "{dispatcher}" claude post-tool-failure', "timeout": 5}]}
        ],
    }

    merged = {**current, "hooks": hooks}
    write_json(path, merged)


def uninstall_cursor_global_hooks() -> None:
    path = cursor_hooks_path()
    backup(path)
    if path.exists():
        path.unlink()


def uninstall_claude_global_hooks() -> None:
    path = claude_settings_path()
    current = read_json(path) if path.exists() else {}
    if "hooks" not in current:
        return
    backup(path)
    current.pop("hooks", None)
    write_json(path, current)


def install_opencode_global_plugin() -> None:
    template = opencode_template_path()
    if not template.is_file():
        return
    target = opencode_plugin_path()
    backup(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template, target)


def uninstall_opencode_global_plugin() -> None:
    target = opencode_plugin_path()
    backup(target)
    if target.exists():
        target.unlink()


def status() -> int:
    d = installed_dispatcher()
    wrap = installed_va_agent_wrap()
    cursor = cursor_hooks_path()
    claude = claude_settings_path()
    opencode = opencode_plugin_path()
    bundled = bundled_dispatcher()
    bundled_wrap = bundled_va_agent_wrap()
    print(f"bundled dispatcher (repo): {bundled} ({'ok' if bundled.is_file() else 'missing'})")
    print(f"bundled va-agent-wrap (repo): {bundled_wrap} ({'ok' if bundled_wrap.is_file() else 'missing'})")
    print(f"installed dispatcher: {d} ({'ok' if d.exists() else 'missing'})")
    print(f"installed va-agent-wrap: {wrap} ({'ok' if wrap.exists() else 'missing'})")
    print(f"cursor hooks: {cursor} ({'ok' if cursor.exists() else 'missing'})")
    print(f"claude settings: {claude} ({'ok' if claude.exists() else 'missing'})")
    print(f"opencode plugin: {opencode} ({'ok' if opencode.exists() else 'missing'})")
    if claude.exists():
        data = read_json(claude)
        print(f"claude hooks enabled: {bool(data.get('hooks'))}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Install/uninstall global wow-harness autodispatch hooks for Cursor + Claude.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("install")
    sub.add_parser("uninstall")
    sub.add_parser("status")
    args = p.parse_args()

    if args.cmd == "status":
        return status()

    if args.cmd == "install":
        dispatcher = copy_bundled_dispatcher()
        wrap_dst = copy_va_agent_wrap()
        install_cursor_global_hooks(dispatcher)
        install_claude_global_hooks(dispatcher)
        install_opencode_global_plugin()
        install_shell_shims()
        wrap_msg = f" + {wrap_dst}" if wrap_dst is not None else ""
        if opencode_template_path().is_file():
            print(f"ok: installed global hooks (Cursor + Claude + OpenCode plugin){wrap_msg}")
        else:
            print(f"ok: installed global hooks (Cursor + Claude); OpenCode template not bundled, skipped{wrap_msg}")
        return 0

    if args.cmd == "uninstall":
        uninstall_cursor_global_hooks()
        uninstall_claude_global_hooks()
        uninstall_opencode_global_plugin()
        uninstall_va_agent_wrap()
        uninstall_shell_shims()
        print("ok: removed global hooks configuration (Cursor + Claude + OpenCode plugin if present)")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
