#!/usr/bin/env python3
"""multi_project_registry.py — explicit project naming for wow-harness install.

ADR-043 §3.4.5: installer asks user which projects to install into.
Three modes:
  [1] Current directory ($PWD)
  [2] User-level global (~/.claude/ plugin) — no per-project install
  [3] Explicit list — user names project paths

Hard constraints:
  - Installer NEVER auto-scans ~/.claude/projects/ to infer candidates
  - --tier=mine + mode 2 (global) is FORBIDDEN (fail-closed)
  - Registry persisted to ~/.wow-harness/installed-projects.yaml (idempotent)
  - Second run reads same file → no change (diff = empty)

stdlib only per ADR-043 §7.4 (yaml optional, falls back to json).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REGISTRY_DIR = Path.home() / ".wow-harness"
REGISTRY_FILE = REGISTRY_DIR / "installed-projects.yaml"
REGISTRY_FILE_JSON = REGISTRY_DIR / "installed-projects.json"  # fallback


def _load_registry() -> dict:
    """Load existing registry, or empty dict."""
    # Try yaml first, then json fallback
    if REGISTRY_FILE.exists():
        try:
            import yaml
            return yaml.safe_load(REGISTRY_FILE.read_text()) or {}
        except ImportError:
            pass
    if REGISTRY_FILE_JSON.exists():
        try:
            return json.loads(REGISTRY_FILE_JSON.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_registry(data: dict):
    """Save registry (yaml preferred, json fallback)."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
        REGISTRY_FILE.write_text(yaml.dump(data, default_flow_style=False))
    except ImportError:
        REGISTRY_FILE_JSON.write_text(json.dumps(data, indent=2) + "\n")


def resolve_projects_interactive(tier: str) -> list[Path]:
    """Interactive project selection. Returns list of resolved project paths.

    For non-interactive (CI / --auto), use resolve_projects_from_args().
    """
    print("wow-harness 要装到哪些项目？")
    print(f"  [1] 当前目录 ({os.getcwd()})")
    print("  [2] 用户级全局 (~/.claude/ plugin) — 不触碰具体项目")
    print("  [3] 显式点名几个项目 — 输入路径列表")
    choice = input("> ").strip()

    if choice == "1":
        return [Path.cwd().resolve()]

    if choice == "2":
        if tier == "mine":
            print(
                "ERROR: mine + global forbidden — "
                "全局安装 + transcript 挖掘 = 隐私灾难。"
                "请选 [3] 并显式点名项目。",
                file=sys.stderr,
            )
            sys.exit(2)
        return []  # global install, no per-project paths

    if choice == "3":
        print("请输入项目绝对路径，每行一个，空行结束：")
        paths: list[Path] = []
        while True:
            line = input("> ").strip()
            if not line:
                break
            p = Path(line).resolve()
            if not p.is_dir():
                print(f"  WARNING: {p} 不存在或不是目录，跳过", file=sys.stderr)
                continue
            paths.append(p)
        if not paths:
            print("ERROR: 没有有效的项目路径", file=sys.stderr)
            sys.exit(2)
        return paths

    print(f"Unknown choice: {choice}", file=sys.stderr)
    sys.exit(2)


def resolve_projects_from_args(
    projects_csv: str, tier: str, scope: str = "current"
) -> list[Path]:
    """Non-interactive project resolution for --auto mode.

    Args:
        projects_csv: Comma-separated project paths (from --projects=).
        tier: Install tier (drop-in / adapt / mine).
        scope: 'current' (cwd), 'global', or 'explicit' (from --projects).

    Returns:
        List of resolved project paths.
    """
    if scope == "global":
        if tier == "mine":
            print(
                "fail-closed: mine + global forbidden per ADR-043 §3.4.5",
                file=sys.stderr,
            )
            sys.exit(2)
        return []

    if scope == "current" or not projects_csv:
        return [Path.cwd().resolve()]

    # scope == "explicit"
    paths: list[Path] = []
    for raw in projects_csv.split(","):
        raw = raw.strip()
        if not raw:
            continue
        p = Path(raw).resolve()
        if not p.is_dir():
            print(f"WARNING: project path {p} does not exist, skipping", file=sys.stderr)
            continue
        paths.append(p)

    if not paths:
        print("ERROR: no valid project paths in --projects", file=sys.stderr)
        sys.exit(2)
    return paths


def register_projects(projects: list[Path], tier: str) -> bool:
    """Register installed projects. Returns True if registry changed."""
    existing = _load_registry()
    changed = False

    for p in projects:
        key = str(p)
        if key not in existing.get("projects", {}):
            existing.setdefault("projects", {})[key] = {"tier": tier}
            changed = True

    if changed:
        _save_registry(existing)
    return changed


def main() -> int:
    """CLI entry for testing."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", default="adapt")
    parser.add_argument("--projects", default="")
    parser.add_argument("--scope", default="current", choices=["current", "global", "explicit"])
    args = parser.parse_args()

    projects = resolve_projects_from_args(args.projects, args.tier, args.scope)
    changed = register_projects(projects, args.tier)
    print(f"projects={[str(p) for p in projects]}")
    print(f"registry_changed={changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
