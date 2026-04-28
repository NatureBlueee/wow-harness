#!/usr/bin/env python3
"""SessionStart hook — reset risk snapshot for new session (ADR-044 §4.2).

Risk ratchet is session-scoped: each new session starts at R0.
Without this reset, stale R3/R4 from previous sessions would cause
completion candidate false positives in stop-evaluator.py.

Always exits 0 (advisory, never blocking).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RISK_SNAPSHOTS = (
    REPO_ROOT / ".wow-harness" / "state" / "risk-snapshot.json",
    REPO_ROOT / ".towow" / "state" / "risk-snapshot.json",
)


def main() -> int:
    for risk_snapshot in RISK_SNAPSHOTS:
        if risk_snapshot.exists():
            risk_snapshot.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
