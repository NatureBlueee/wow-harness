#!/usr/bin/env python3
"""Annex A.1 sanitizer (chokepoint_A, fork-time).

Scans input files/dirs against the 5 Annex A.1 classes defined in
scripts/lib/sanitize_patterns.py, arbitrates per ADR-043 Annex A.1 line
1112 (SECRET > TRADE_SECRET > PII > NETWORK > PROTOCOL_INTERNAL), and
emits .sanitize-report.json.

Exit codes:
  0  clean (or degraded mode with non-fatal hits)
  1  operational error (file not readable, etc.)
  2  strict mode found at least one SECRET or TRADE_SECRET hit

stdlib only per WP-01b AC 8.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make the sibling lib/ importable without requiring package install.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from lib import sanitize_patterns as sp  # noqa: E402


SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}
BINARY_SNIFF_BYTES = 512


def _is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(BINARY_SNIFF_BYTES)
    except OSError:
        return True
    if b"\x00" in chunk:
        return True
    return False


def _iter_files(paths: list[Path]):
    for p in paths:
        if p.is_file():
            yield p
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for name in files:
                    yield Path(root) / name


def _classify_line(line: str) -> list[str]:
    """Return the set of Annex A.1 classes matched by this line."""
    hits: list[str] = []
    for cls, patterns in sp.CLASS_PATTERNS.items():
        for pat in patterns:
            if pat.search(line):
                hits.append(cls)
                break
    return hits


def _arbitrate(hits: list[str]) -> str | None:
    for cls in sp.ARBITRATION_ORDER:
        if cls in hits:
            return cls
    return None


def _apply_rename(line: str) -> tuple[str, bool]:
    """Apply PROTOCOL_INTERNAL dict rename. Returns (new_line, changed)."""
    new = line
    for key, val in sp.RENAME_TABLE.items():
        if key in new:
            new = new.replace(key, val)
    return new, new != line


def _apply_strip(line: str, cls: str) -> str:
    placeholder = sp.PLACEHOLDERS.get(cls, "<REDACTED>")
    out = line
    for pat in sp.CLASS_PATTERNS[cls]:
        out = pat.sub(placeholder, out)
    return out


def _path_is_trade_secret(path: Path) -> bool:
    s = str(path)
    return any(marker in s for marker in sp.TRADE_SECRET_PATH_MARKERS)


def scan_file(path: Path) -> tuple[list[dict], bool]:
    """Scan one file. Returns (records, has_hard_reject)."""
    records: list[dict] = []
    has_hard = False

    if _path_is_trade_secret(path):
        records.append(
            {
                "file": str(path),
                "line": 0,
                "categories": ["TRADE_SECRET"],
                "resolved_as": "TRADE_SECRET",
                "action": "reject_by_path",
                "matched": "(path blacklist)",
            }
        )
        return records, True

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        records.append(
            {
                "file": str(path),
                "line": 0,
                "categories": ["ERROR"],
                "resolved_as": "ERROR",
                "action": "read_error",
                "matched": str(exc),
            }
        )
        return records, False

    for lineno, line in enumerate(text.splitlines(), start=1):
        hits = _classify_line(line)
        if not hits:
            continue
        resolved = _arbitrate(hits)
        record = {
            "file": str(path),
            "line": lineno,
            "categories": hits,
            "resolved_as": resolved,
            "matched": line.rstrip("\n")[:200],
        }
        if resolved in ("SECRET", "TRADE_SECRET"):
            record["action"] = "reject_file"
            has_hard = True
        elif resolved == "PROTOCOL_INTERNAL":
            new_line, _ = _apply_rename(line)
            record["action"] = "rename"
            record["after"] = new_line.rstrip("\n")[:200]
        else:  # PII, NETWORK
            new_line = _apply_strip(line, resolved)
            record["action"] = "strip"
            record["after"] = new_line.rstrip("\n")[:200]
        records.append(record)

    return records, has_hard


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="sanitize.py",
        description=(
            "Annex A.1 five-class sanitizer (chokepoint_A). "
            "Scans files or directories, emits .sanitize-report.json, "
            "exit 2 on SECRET/TRADE_SECRET in strict mode."
        ),
    )
    ap.add_argument(
        "--mode",
        choices=["strict", "degraded"],
        default="strict",
        help="strict (default): exit 2 on SECRET/TRADE_SECRET. "
             "degraded: report but do not fail the run.",
    )
    ap.add_argument(
        "--report-path",
        default=".sanitize-report.json",
        help="Where to write the JSON report (default: .sanitize-report.json).",
    )
    ap.add_argument(
        "paths",
        nargs="+",
        help="Files or directories to scan.",
    )
    args = ap.parse_args(argv)

    targets = [Path(p) for p in args.paths]
    missing = [p for p in targets if not p.exists()]
    if missing:
        print(f"sanitize.py: path not found: {missing}", file=sys.stderr)
        return 1

    all_records: list[dict] = []
    any_hard = False
    files_scanned = 0
    for f in _iter_files(targets):
        if _is_binary(f):
            continue
        recs, hard = scan_file(f)
        all_records.extend(recs)
        any_hard = any_hard or hard
        files_scanned += 1

    totals = {
        "SECRET": 0,
        "TRADE_SECRET": 0,
        "PII": 0,
        "NETWORK": 0,
        "PROTOCOL_INTERNAL": 0,
    }
    for r in all_records:
        resolved = r.get("resolved_as")
        if resolved in totals:
            totals[resolved] += 1

    report = {
        "mode": args.mode,
        "files_scanned": files_scanned,
        "totals": totals,
        "records": all_records,
    }
    Path(args.report_path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if any_hard:
        print(
            f"sanitize.py: SECRET/TRADE_SECRET detected "
            f"(SECRET={totals['SECRET']} TRADE_SECRET={totals['TRADE_SECRET']}). "
            f"See {args.report_path}",
            file=sys.stderr,
        )
        if args.mode == "strict":
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
