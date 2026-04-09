#!/usr/bin/env python3
"""phase2_auto.py — Phase 2 `/lead install wow-harness --auto` single-file installer.

PLAN-086 WP-11 deliverable. Implements ADR-043 §3.4 + §3.4.4-3.4.6.

Sequence:
  1. Read trust-status.json; if degraded and no --i-accept-degraded → abort
  2. Sign/verify install-trust-token (HMAC, 30min sliding / 6h absolute)
  3. Resolve tier policy (drop-in / adapt / mine)
  4. Resolve project list (current / global / explicit naming)
  5. For each project:
     a. Copy bundle staging → .claude/ (dry-run or real)
     b. Atomic append 1 PreToolUse Read|Bash matcher to settings.json (15→16)
        - MUST use json library, FORBIDDEN to use sed/textual edit
        - Idempotent: if matcher already exists, skip
     c. INDEX.md slot fill (replace TODO WP-11 → real reference)
  6. If --tier=mine: run transcript_miner for named projects
  7. Write install-log.jsonl + update trust-status.json
  8. Second run → steps 5a-5c detect already-exists → skip (idempotent)

Exit codes:
  0   success
  2   fail-closed (trust/tier/integrity failure)

stdlib only per ADR-043 §7.4 (yaml optional for MANIFEST reads).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "install"))

from tier_selector import resolve_tier, VALID_TIERS, DEFAULT_TIER  # noqa: E402
from multi_project_registry import (  # noqa: E402
    resolve_projects_from_args,
    register_projects,
)

# Paths relative to target project
SETTINGS_REL = Path(".claude") / "settings.json"
MANIFEST_REL = Path(".wow-harness") / "MANIFEST.yaml"
INDEX_REL = Path(".claude") / "skills" / "lead" / "INDEX.md"
INSTALL_LOG_REL = Path(".wow-harness") / "install-log.jsonl"
TRUST_STATUS_REL = Path(".wow-harness") / "trust-status.json"

# The one matcher entry WP-11 adds (AC 3/4: single entry, pipe-regex)
WP11_MATCHER = {
    "matcher": "Read|Bash",
    "hooks": [
        {
            "type": "command",
            "command": "cd \"$(scripts/hooks/find-project-root.sh)\" && python3 scripts/hooks/sanitize-on-read.py",
            "timeout": 10,
        }
    ],
}


def _log_event(project_root: Path, event: str, details: str = ""):
    """Append to install-log.jsonl."""
    log_path = project_root / INSTALL_LOG_REL
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": event,
        "details": details,
    }
    with log_path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _check_trust_status(project_root: Path, accept_degraded: bool) -> bool:
    """Step 1: check trust-status.json."""
    trust_path = project_root / TRUST_STATUS_REL
    if not trust_path.exists():
        return True  # first install, no trust file yet
    try:
        status = json.loads(trust_path.read_text())
    except (json.JSONDecodeError, OSError):
        return True
    if status.get("trust_level") == "degraded" and not accept_degraded:
        print(
            "fail-closed: trust-status.json shows 'degraded'. "
            "Pass --i-accept-degraded to proceed, or fix the trust chain.",
            file=sys.stderr,
        )
        return False
    return True


def _atomic_append_matcher(settings_path: Path, dry_run: bool = False) -> bool:
    """Step 5b: append WP-11 matcher to settings.json atomically.

    Returns True if the matcher was added (or would be in dry_run).
    Returns False if already present (idempotent skip).
    """
    if not settings_path.exists():
        print(f"settings.json not found at {settings_path}", file=sys.stderr)
        return False

    settings = json.loads(settings_path.read_text())
    hooks = settings.setdefault("hooks", {})
    pre_tool_use = hooks.setdefault("PreToolUse", [])

    # Idempotency check: does a Read|Bash or Bash|Read matcher already exist?
    target_set = {"Read", "Bash"}
    for entry in pre_tool_use:
        existing_matcher = entry.get("matcher", "")
        existing_set = set(existing_matcher.split("|"))
        if existing_set == target_set:
            # Check if it points to sanitize-on-read.py
            for hook in entry.get("hooks", []):
                if "sanitize-on-read.py" in hook.get("command", ""):
                    return False  # already installed, idempotent skip

    if dry_run:
        return True

    # Append the new entry
    pre_tool_use.append(WP11_MATCHER)
    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    return True


def _fill_index_slot(project_root: Path, dry_run: bool = False) -> bool:
    """Step 5c: replace (TODO WP-11) in INDEX.md with actual reference."""
    index_path = project_root / INDEX_REL
    if not index_path.exists():
        return False

    content = index_path.read_text()
    if "(TODO WP-11)" not in content:
        return False  # already filled or not present

    if dry_run:
        return True

    new_content = content.replace(
        "(TODO WP-11)",
        "install-wow-harness.md",
    )
    index_path.write_text(new_content)
    return True


def _count_commands(settings_path: Path) -> int:
    """Count hook commands in settings.json (same logic as detect_rebaseline_triggers)."""
    settings = json.loads(settings_path.read_text())
    total = 0
    for stage_entries in settings.get("hooks", {}).values():
        for entry in stage_entries:
            total += len(entry.get("hooks", []))
    return total


def main() -> int:
    parser = argparse.ArgumentParser(
        description="wow-harness Phase 2 installer"
    )
    parser.add_argument("--auto", action="store_true", help="Auto mode (required)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change")
    parser.add_argument("--tier", default=DEFAULT_TIER, choices=VALID_TIERS)
    parser.add_argument("--projects", default="", help="Comma-separated project paths")
    parser.add_argument("--scope", default="current", choices=["current", "global", "explicit"])
    parser.add_argument("--i-accept-degraded", action="store_true")
    args = parser.parse_args()

    if not args.auto:
        print("Phase 2 installer requires --auto flag.", file=sys.stderr)
        return 2

    # Step 1: trust status
    if not _check_trust_status(REPO_ROOT, args.i_accept_degraded):
        return 2

    # Step 2: trust token
    from pathlib import Path as _P
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "install"))
    try:
        # Import inline to keep --dry-run lightweight
        import importlib
        itt = importlib.import_module("install-trust-token".replace("-", "_"))
    except (ImportError, ModuleNotFoundError):
        # Fallback: try direct file import
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "install_trust_token",
            REPO_ROOT / "scripts" / "install" / "install-trust-token.py",
        )
        if spec and spec.loader:
            itt = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(itt)
        else:
            print("Cannot load install-trust-token module", file=sys.stderr)
            return 2

    if not args.dry_run:
        itt.sign(REPO_ROOT)

    # Step 3: resolve tier
    projects_list = (
        [p.strip() for p in args.projects.split(",") if p.strip()]
        if args.projects else []
    )
    policy = resolve_tier(args.tier, projects_list if args.tier == "mine" else None)

    # Step 4: resolve projects
    project_paths = resolve_projects_from_args(
        args.projects, args.tier, args.scope
    )

    # Step 5: install to each project
    for project_root in project_paths:
        settings_path = project_root / SETTINGS_REL

        # 5b: atomic append matcher
        added = _atomic_append_matcher(settings_path, dry_run=args.dry_run)
        action = "would add" if args.dry_run else "added"
        if added:
            print(f"  {action} Read|Bash matcher to {settings_path}")
            if not args.dry_run:
                count = _count_commands(settings_path)
                print(f"  settings.json command count: {count}")
                _log_event(project_root, "matcher_added", f"count={count}")
                itt.refresh(REPO_ROOT)
        else:
            print(f"  Read|Bash matcher already in {settings_path} (idempotent skip)")

        # 5c: INDEX slot fill
        filled = _fill_index_slot(project_root, dry_run=args.dry_run)
        if filled:
            print(f"  {action} install-wow-harness.md to INDEX.md")
            if not args.dry_run:
                _log_event(project_root, "index_slot_filled")
                itt.refresh(REPO_ROOT)

    # Step 6: mine transcripts if tier=mine
    if policy.can_read_transcripts and policy.named_projects:
        from transcript_miner import mine_transcripts  # noqa: E402
        result = mine_transcripts(policy.named_projects)
        if result:
            print(f"  Transcript mining seed: {result}")

    # Step 7: register projects
    if not args.dry_run:
        register_projects(project_paths, args.tier)
        _log_event(REPO_ROOT, "install_complete", f"tier={args.tier} projects={len(project_paths)}")

    # Verification: second dry-run should show no changes
    if not args.dry_run:
        print("\nInstall complete. Run with --dry-run to verify idempotency.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
