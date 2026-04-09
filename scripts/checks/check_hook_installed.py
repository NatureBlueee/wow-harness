"""Check that the pre-commit hook is installed.

Reports a P0 blocking finding when git core.hooksPath is not set to
.githooks/.  Skips automatically in CI / deploy / ci-mode environments
to avoid false positives from deploy.sh or CI runners.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.checks import Finding


def run(repo_root: Path, mode: str = "full") -> list[Finding]:
    # Skip in CI, deploy, or ci-mode — hook enforcement is irrelevant there
    if mode == "ci":
        return []
    if os.environ.get("CI", "").lower() == "true":
        return []
    if os.environ.get("DEPLOY", "").lower() == "true":
        return []

    try:
        result = subprocess.run(
            ["git", "config", "core.hooksPath"],
            capture_output=True, text=True, cwd=repo_root,
        )
        hooks_path = result.stdout.strip()
    except Exception:
        hooks_path = ""

    if hooks_path == ".githooks" or hooks_path == ".githooks/":
        return []

    return [
        Finding(
            severity="P0",
            message=(
                "pre-commit hook not installed. "
                "Run: git config core.hooksPath .githooks"
            ),
            file=".githooks/pre-commit",
            blocking=True,
            category="governance",
            problem_class="missing-guard",
        ),
    ]


if __name__ == "__main__":
    results = run(_REPO_ROOT)
    for f in results:
        print(f"[{f.severity}] {f.file}: {f.message}")
    print(f"\n--- {len(results)} findings ---")
    sys.exit(1 if results else 0)
