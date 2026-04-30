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

RISK_SNAPSHOT = (
    Path(__file__).resolve().parent.parent.parent
    / ".towow" / "state" / "risk-snapshot.json"
)


def main() -> int:
    if RISK_SNAPSHOT.exists():
        RISK_SNAPSHOT.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
