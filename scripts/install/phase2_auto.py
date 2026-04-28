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
import shutil
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


# Bundle directories/files to copy to target project
BUNDLE_DIRS = [".claude", ".wow-harness", "scripts", "schemas"]
BUNDLE_FILES = ["AGENTS.md"]
# Files/dirs to exclude from bundle copy (install-specific, not needed in target)
BUNDLE_EXCLUDE = {
    "__pycache__", ".git", "install-trust-token.json",
    "reference",  # snapshot is source material, not runtime
}


def _copy_bundle(target_root: Path, dry_run: bool = False) -> bool:
    """Step 5a: copy bundle dirs/files from wow-harness to target project.

    Copies .claude/, .wow-harness/, scripts/, schemas/, and AGENTS.md to target.
    Idempotent: only copies files that don't exist or are older.
    Returns True if any files were copied.
    """
    copied_count = 0
    for file_name in BUNDLE_FILES:
        src_file = REPO_ROOT / file_name
        if not src_file.is_file():
            continue
        dst_file = target_root / file_name
        if dst_file.exists():
            if (dst_file.stat().st_size == src_file.stat().st_size
                    and dst_file.stat().st_mtime >= src_file.stat().st_mtime):
                continue
        if dry_run:
            copied_count += 1
            continue
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        copied_count += 1

    for dir_name in BUNDLE_DIRS:
        src_dir = REPO_ROOT / dir_name
        dst_dir = target_root / dir_name
        if not src_dir.is_dir():
            continue

        for src_file in src_dir.rglob("*"):
            if not src_file.is_file():
                continue
            # Skip excluded
            if any(part in BUNDLE_EXCLUDE for part in src_file.parts):
                continue

            rel = src_file.relative_to(REPO_ROOT)
            dst_file = target_root / rel

            # Idempotent: skip if dst exists and is same size + newer
            if dst_file.exists():
                if (dst_file.stat().st_size == src_file.stat().st_size
                        and dst_file.stat().st_mtime >= src_file.stat().st_mtime):
                    continue

            if dry_run:
                copied_count += 1
                continue

            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            copied_count += 1

    return copied_count > 0


# ─── Scaffold + .gitignore (Gap 1 fix) ───

SCAFFOLD_DIR = REPO_ROOT / "templates" / "scaffold"
GITIGNORE_APPEND = SCAFFOLD_DIR / ".gitignore.append"


def _copy_scaffold(target_root: Path, dry_run: bool = False) -> list[str]:
    """Copy project scaffold directories to target (idempotent).

    Creates docs/issues/, docs/decisions/tasks/, .towow/state/, etc.
    Only creates directories and copies files that don't already exist.
    Returns list of created paths (relative to target_root).
    """
    created = []
    if not SCAFFOLD_DIR.is_dir():
        return created

    for src_file in SCAFFOLD_DIR.rglob("*"):
        # Skip the .gitignore.append — handled separately
        if src_file.name == ".gitignore.append":
            continue
        rel = src_file.relative_to(SCAFFOLD_DIR)
        dst = target_root / rel

        if src_file.is_dir():
            if not dst.exists():
                if not dry_run:
                    dst.mkdir(parents=True, exist_ok=True)
                created.append(str(rel) + "/")
        elif src_file.is_file():
            if not dst.exists():
                if not dry_run:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dst)
                created.append(str(rel))

    return created


def _append_gitignore(target_root: Path, dry_run: bool = False) -> bool:
    """Append wow-harness runtime entries to target .gitignore (idempotent).

    Reads .gitignore.append from scaffold template and appends any lines
    not already present in the target's .gitignore.
    Returns True if entries were added (or would be in dry_run).
    """
    if not GITIGNORE_APPEND.exists():
        return False

    append_lines = GITIGNORE_APPEND.read_text().strip().splitlines()
    target_gitignore = target_root / ".gitignore"

    existing = set()
    if target_gitignore.exists():
        existing = set(target_gitignore.read_text().splitlines())

    new_lines = [line for line in append_lines if line not in existing]
    if not new_lines:
        return False

    if dry_run:
        return True

    with target_gitignore.open("a") as f:
        f.write("\n")
        for line in new_lines:
            f.write(line + "\n")

    return True


def _rewrite_hook_paths(settings_path: Path, target_root: Path) -> bool:
    """Legacy path rewrite for settings.json with hardcoded absolute paths.

    With relative paths (Gap 2 fix), this is a no-op for new installs.
    Kept for backward compatibility with older wow-harness versions that
    shipped absolute paths.
    """
    content = settings_path.read_text()
    src_prefix = str(REPO_ROOT)
    dst_prefix = str(target_root.resolve())
    if src_prefix == dst_prefix:
        return False
    if src_prefix not in content:
        return False
    new_content = content.replace(src_prefix, dst_prefix)
    settings_path.write_text(new_content)
    return True


def _hook_signature(hook: dict) -> str:
    """Extract a stable identity for a hook command.

    Uses the script filename from the command (e.g. "risk-tracker.py")
    as the signature, since paths may vary between source and target.
    """
    cmd = hook.get("command", "")
    # Extract the last python3/bash script name from the command
    for part in reversed(cmd.split()):
        if part.endswith((".py", ".sh")):
            return part.split("/")[-1]
    return cmd


def _merge_hooks(settings_path: Path, dry_run: bool = False) -> list[str]:
    """Step 5b: merge source hooks into target settings.json.

    Compares source (wow-harness) and target settings.json hook registrations.
    For each hook stage (PostToolUse, PreToolUse, etc.), detects hooks present
    in source but missing in target, and appends them.

    Idempotent: hooks already present (matched by script filename) are skipped.
    Returns list of added hook descriptions.
    """
    src_settings_path = REPO_ROOT / SETTINGS_REL
    if not src_settings_path.exists() or not settings_path.exists():
        return []

    src_settings = json.loads(src_settings_path.read_text())
    dst_settings = json.loads(settings_path.read_text())

    src_hooks = src_settings.get("hooks", {})
    dst_hooks = dst_settings.setdefault("hooks", {})

    added = []

    for stage, src_entries in src_hooks.items():
        dst_entries = dst_hooks.setdefault(stage, [])

        # Build set of existing hook signatures in target (per matcher)
        existing_sigs: dict[str, set[str]] = {}
        for entry in dst_entries:
            matcher = entry.get("matcher", "*")
            sigs = existing_sigs.setdefault(matcher, set())
            for hook in entry.get("hooks", []):
                sigs.add(_hook_signature(hook))

        for src_entry in src_entries:
            matcher = src_entry.get("matcher", "*")
            target_sigs = existing_sigs.get(matcher, set())

            # Find hooks in this source entry that are missing from target
            missing_hooks = []
            for hook in src_entry.get("hooks", []):
                sig = _hook_signature(hook)
                if sig not in target_sigs:
                    missing_hooks.append(hook)

            if not missing_hooks:
                continue

            if dry_run:
                for hook in missing_hooks:
                    added.append(f"{stage} {matcher}: {_hook_signature(hook)}")
                continue

            # Find or create matching entry in target
            target_entry = None
            for entry in dst_entries:
                if entry.get("matcher") == matcher:
                    target_entry = entry
                    break

            if target_entry is None:
                # New matcher — append entire entry
                dst_entries.append(src_entry)
                for hook in missing_hooks:
                    added.append(f"{stage} {matcher}: {_hook_signature(hook)}")
            else:
                # Existing matcher — append missing hooks
                for hook in missing_hooks:
                    target_entry["hooks"].append(hook)
                    added.append(f"{stage} {matcher}: {_hook_signature(hook)}")

    if added and not dry_run:
        settings_path.write_text(
            json.dumps(dst_settings, indent=2, ensure_ascii=False) + "\n"
        )

    return added


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
        print(f"\nInstalling to {project_root} (tier={args.tier})...")

        # 5a: copy bundle to target
        action = "would copy" if args.dry_run else "copied"
        bundle_copied = _copy_bundle(project_root, dry_run=args.dry_run)
        if bundle_copied:
            print(f"  {action} bundle files (AGENTS.md .claude/ .wow-harness/ scripts/ schemas/)")
            if not args.dry_run:
                _log_event(project_root, "bundle_copied", f"tier={args.tier}")
        else:
            print("  bundle files already up to date (idempotent skip)")

        # 5a-2: copy project scaffold (docs/issues/, docs/decisions/, .towow/state/, etc.)
        scaffold_created = _copy_scaffold(project_root, dry_run=args.dry_run)
        if scaffold_created:
            action = "would create" if args.dry_run else "created"
            print(f"  {action} scaffold: {', '.join(scaffold_created[:5])}"
                  + (f" (+{len(scaffold_created)-5} more)" if len(scaffold_created) > 5 else ""))
            if not args.dry_run:
                _log_event(project_root, "scaffold_created", f"paths={len(scaffold_created)}")
        else:
            print("  scaffold directories already exist (idempotent skip)")

        # 5a-3: append .gitignore entries for runtime directories
        gitignore_appended = _append_gitignore(project_root, dry_run=args.dry_run)
        if gitignore_appended:
            action = "would append" if args.dry_run else "appended"
            print(f"  {action} wow-harness runtime entries to .gitignore")
            if not args.dry_run:
                _log_event(project_root, "gitignore_appended")
        else:
            print("  .gitignore entries already present (idempotent skip)")

        settings_path = project_root / SETTINGS_REL

        # 5a-4: rewrite hardcoded paths in settings.json (legacy compat)
        if not args.dry_run and settings_path.exists():
            rewritten = _rewrite_hook_paths(settings_path, project_root)
            if rewritten:
                print(f"  rewrote hook paths → {project_root}")

        # 5b: merge hooks from source to target settings.json
        merged = _merge_hooks(settings_path, dry_run=args.dry_run)
        if merged:
            action = "would add" if args.dry_run else "added"
            print(f"  {action} {len(merged)} hooks:")
            for desc in merged:
                print(f"    + {desc}")
            if not args.dry_run:
                count = _count_commands(settings_path)
                print(f"  settings.json command count: {count}")
                _log_event(project_root, "hooks_merged", f"added={len(merged)} total={count}")
                itt.refresh(REPO_ROOT)
        else:
            print(f"  all hooks already in {settings_path} (idempotent skip)")

        # 5c: INDEX slot fill
        filled = _fill_index_slot(project_root, dry_run=args.dry_run)
        if filled:
            print(f"  {action} install-wow-harness.md to INDEX.md")
            if not args.dry_run:
                _log_event(project_root, "index_slot_filled")
                itt.refresh(REPO_ROOT)

    # Step 6: mine transcripts if tier=mine (output to first target project)
    if policy.can_read_transcripts and policy.named_projects and not args.dry_run:
        from transcript_miner import mine_transcripts  # noqa: E402
        target_proposals = project_paths[0] / ".wow-harness" / "proposals" if project_paths else None
        result = mine_transcripts(policy.named_projects, output_dir=target_proposals)
        if result:
            print(f"\n  Transcript mining seed: {result}")
            _log_event(project_paths[0], "transcript_mined", f"seed={result.name}")

    # Step 7: register projects
    if not args.dry_run:
        register_projects(project_paths, args.tier)
        for pr in project_paths:
            _log_event(pr, "install_complete", f"tier={args.tier} projects={len(project_paths)}")

    # Verification: second dry-run should show no changes
    if not args.dry_run:
        print("\nInstall complete. Run with --dry-run to verify idempotency.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
