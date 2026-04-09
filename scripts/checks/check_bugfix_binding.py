#!/usr/bin/env python3
"""Check that bugfix commits include an issue document.

Local version: reads commit message + staged files.
Invoked by .githooks/commit-msg when message matches fix/bugfix/hotfix pattern.

Convention (harness-level, project-configurable):
    commit prefix: fix|bugfix|hotfix (case-insensitive, optional scope)
    required artifact: at least one docs/issues/*.md change in same commit
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.checks import Finding

_BUGFIX_PATTERN = re.compile(r'^(fix|bugfix|hotfix)(\(.+\))?:', re.IGNORECASE)
_ISSUE_PATTERN = re.compile(r'^docs/issues/.*\.md$')


def _staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=_REPO_ROOT,
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def check_binding(commit_msg: str, staged: list[str]) -> list[Finding]:
    """Check if a bugfix commit has an accompanying issue doc."""
    first_line = commit_msg.strip().split("\n")[0]
    if not _BUGFIX_PATTERN.match(first_line):
        return []

    has_issue = any(_ISSUE_PATTERN.match(f) for f in staged)
    if has_issue:
        return []

    return [Finding(
        severity="P1",
        message=(
            f'Bugfix commit "{first_line}" has no accompanying issue document. '
            f"Add or modify a docs/issues/*.md file describing the bug and fix."
        ),
        file="docs/issues/",
        blocking=True,
        category="artifact_linkage",
        required_skills=["lead"],
    )]


def run(repo_root: Path, mode: str = "full") -> list[Finding]:
    """Coherence check entry point. Enforcement lives in commit-msg hook."""
    return []


def main():
    """Called from .githooks/commit-msg."""
    if "--commit-msg" in sys.argv:
        idx = sys.argv.index("--commit-msg")
        if idx + 1 < len(sys.argv):
            msg_file = sys.argv[idx + 1]
            commit_msg = Path(msg_file).read_text(encoding="utf-8")
            staged = _staged_files()
            findings = check_binding(commit_msg, staged)

            for f in findings:
                print(f"[{f.severity}] {f.message}", file=sys.stderr)

            sys.exit(1 if any(f.blocking for f in findings) else 0)

    print("Usage: check_bugfix_binding.py --commit-msg <path>", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
