#!/usr/bin/env python3
"""pre_commit_installer.py — install .git/hooks/pre-commit for wow-harness.

WP-11 deliverable, closing WP-SEC-1 deferred AC 13.

Installs a pre-commit hook that runs scan_verify_artifacts.py --claims
before each commit. Idempotent: if hook already exists and contains
our marker, skip.

The hook is a thin shell wrapper, not a Python script — git hooks must
be shell-executable without depending on Python being in PATH for the
git invocation (though our hook does call python3 internally).
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / ".git" / "hooks" / "pre-commit"
MARKER = "# wow-harness pre-commit (WP-11)"

HOOK_CONTENT = f"""\
#!/bin/sh
{MARKER}
# Runs scan_verify_artifacts.py to check positive claims before commit.
# If any claimed path doesn't exist or has no git history → block commit.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [ -f "$REPO_ROOT/scripts/ci/scan_verify_artifacts.py" ]; then
    python3 "$REPO_ROOT/scripts/ci/scan_verify_artifacts.py" --claims
    if [ $? -ne 0 ]; then
        echo "pre-commit: scan_verify_artifacts found vapor claims. Fix before committing." >&2
        exit 1
    fi
fi
"""


def install(dry_run: bool = False) -> bool:
    """Install pre-commit hook. Returns True if installed, False if skipped."""
    if HOOK_PATH.exists():
        existing = HOOK_PATH.read_text()
        if MARKER in existing:
            return False  # already installed, idempotent

        # Existing hook from another tool — append our check
        if not dry_run:
            with HOOK_PATH.open("a") as f:
                f.write(f"\n{HOOK_CONTENT}\n")
            _make_executable(HOOK_PATH)
        return True

    if not dry_run:
        HOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
        HOOK_PATH.write_text(HOOK_CONTENT)
        _make_executable(HOOK_PATH)
    return True


def _make_executable(path: Path):
    """chmod +x."""
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    installed = install(dry_run=args.dry_run)
    action = "would install" if args.dry_run else "installed"
    if installed:
        print(f"pre-commit hook {action} at {HOOK_PATH}")
    else:
        print(f"pre-commit hook already present (idempotent skip)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
