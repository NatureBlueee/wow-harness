"""Security boundary regression checks (template shell).

Template for project-level security invariant checks. This file ships empty
in wow-harness because security invariants are inherently project-specific:
what counts as a boundary violation depends on the project's architecture
(which routes, which redirect flows, which transport layers).

To extend for your project, add one `_check_*()` function per security
invariant and call it from `run()`. Each check should:
  1. Import the target module (fail gracefully on ImportError)
  2. Exercise the invariant with a known-bad input
  3. Append a Finding if the invariant is violated

Conventions:
  - severity P0 = boundary violation (ship-blocker)
  - severity P1 = hardening issue (not blocking)
  - severity P2 = style/observability issue
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.checks import Finding  # noqa: E402


def run(repo_root: Path, mode: str = "full") -> list[Finding]:
    """Entry point called by the harness check runner.

    Empty by default — extend per project. See module docstring for pattern.
    """
    findings: list[Finding] = []
    # Add project-specific _check_*() invocations here.
    return findings


if __name__ == "__main__":
    result = run(_REPO_ROOT)
    if result:
        for f in result:
            print(f"[{f.severity}] {f.file}: {f.message}")
        sys.exit(1 if any(f.severity == "P0" for f in result) else 0)
    sys.exit(0)
