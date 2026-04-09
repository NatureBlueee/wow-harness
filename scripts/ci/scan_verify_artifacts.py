#!/usr/bin/env python3
"""scan_verify_artifacts.py — metrics allowlist + positive-claim cross-source.

Two modes:

  --metrics <file.jsonl>
      Validate every line against schemas/metrics-jsonl-allowlist.json.
      Unknown fields are rejected (ADR-043 §4.2 / v2 patch_4 security P1#4).

  --claims
      Scan docs for positive existence claims (``已部署``, ``deployed``, etc.)
      using the shared regex in scripts/lib/claim_patterns.py. For each
      claimed path, assert:
        (a) path exists on disk, AND
        (b) path has at least one git log entry
      Either failing = "vapor deploy" — INV-4 re-activation (§13.5).

Both modes share the claim_patterns.py producer, so the positive-claim regex
lives in exactly one file. WP-04 check_file_existence_claims.py is the
first consumer; this script is the second. INV-4 seam owner: WP-04.

Usage:
  python3 scripts/ci/scan_verify_artifacts.py --metrics <file.jsonl>
  python3 scripts/ci/scan_verify_artifacts.py --claims
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ALLOWLIST_PATH = REPO_ROOT / "schemas" / "metrics-jsonl-allowlist.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from lib.claim_patterns import iter_positive_claims  # noqa: E402


def load_allowlist() -> set[str]:
    try:
        schema = json.loads(ALLOWLIST_PATH.read_text())
    except FileNotFoundError:
        print(f"{ALLOWLIST_PATH}: not found", file=sys.stderr)
        sys.exit(2)
    return set(schema.get("properties", {}).keys())


def check_metrics(path: str) -> int:
    allowed = load_allowlist()
    rc = 0
    try:
        lines = open(path, "r", encoding="utf-8").readlines()
    except FileNotFoundError:
        print(f"{path}: file not found", file=sys.stderr)
        return 2
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"{path}:{i}: invalid JSON — {e}", file=sys.stderr)
            rc = 2
            continue
        extra = set(obj.keys()) - allowed
        if extra:
            print(f"{path}:{i}: unknown fields {sorted(extra)}", file=sys.stderr)
            rc = 2
    return rc


def check_claims() -> int:
    scan_targets: list[Path] = []
    verify_dir = REPO_ROOT / "docs" / "verify"
    if verify_dir.is_dir():
        scan_targets.extend(verify_dir.rglob("*.md"))
    for candidate in (
        REPO_ROOT / "reference" / "INDEPENDENT-REVIEW.md",
        REPO_ROOT / "README.md",
    ):
        if candidate.is_file():
            scan_targets.append(candidate)

    rc = 0
    for f in scan_targets:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for marker, claim_path in iter_positive_claims(text):
            fs_path = REPO_ROOT / claim_path
            if not fs_path.exists():
                print(
                    f"{f}: positive claim '{marker}: {claim_path}' — path missing on disk",
                    file=sys.stderr,
                )
                rc = 2
                continue
            result = subprocess.run(
                ["git", "log", "--all", "--format=%H", "--", claim_path],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            if not result.stdout.strip():
                print(
                    f"{f}: positive claim '{marker}: {claim_path}' — no git history (vapor deploy)",
                    file=sys.stderr,
                )
                rc = 2
    return rc


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(
            "usage: scan_verify_artifacts.py [--metrics <file.jsonl>] [--claims]",
            file=sys.stderr,
        )
        return 2

    rc = 0
    if "--metrics" in args:
        idx = args.index("--metrics")
        if idx + 1 >= len(args):
            print("--metrics requires a file argument", file=sys.stderr)
            return 2
        rc |= check_metrics(args[idx + 1])
    if "--claims" in args:
        rc |= check_claims()
    return rc


if __name__ == "__main__":
    sys.exit(main())
