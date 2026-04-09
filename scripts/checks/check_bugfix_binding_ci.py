#!/usr/bin/env python3
"""CI version of bugfix binding check.

Parses PR commit range (origin/main..HEAD) to find bugfix commits,
then verifies the PR includes at least one docs/issues/*.md change.
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


def run(repo_root: Path, mode: str = "full") -> list[Finding]:
    """Check PR commits for bugfix binding."""
    if mode != "ci":
        return []

    result = subprocess.run(
        ["git", "log", "--oneline", "origin/main..HEAD"],
        capture_output=True, text=True, cwd=repo_root,
    )
    if result.returncode != 0:
        return []

    commits = result.stdout.strip().splitlines()
    bugfix_commits = []
    for line in commits:
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        msg = parts[1]
        if _BUGFIX_PATTERN.match(msg):
            bugfix_commits.append(msg)

    if not bugfix_commits:
        return []

    diff_result = subprocess.run(
        ["git", "diff", "origin/main..HEAD", "--name-only"],
        capture_output=True, text=True, cwd=repo_root,
    )
    changed_files = [f.strip() for f in diff_result.stdout.splitlines() if f.strip()]
    has_issue = any(_ISSUE_PATTERN.match(f) for f in changed_files)

    if has_issue:
        return []

    return [Finding(
        severity="P1",
        message=(
            f"PR contains {len(bugfix_commits)} bugfix commit(s) but no issue document. "
            f"Bugfix commits: {', '.join(bugfix_commits[:3])}"
            + (f" (and {len(bugfix_commits) - 3} more)" if len(bugfix_commits) > 3 else "")
            + ". Add a docs/issues/*.md file."
        ),
        file="docs/issues/",
        blocking=True,
        category="artifact_linkage",
        required_skills=["lead"],
    )]


if __name__ == "__main__":
    results = run(Path(__file__).resolve().parent.parent.parent, mode="ci")
    for f in results:
        print(f"[{f.severity}] {f.message}")
    if not results:
        print("No bugfix binding issues found.")
    sys.exit(1 if any(f.blocking for f in results) else 0)
