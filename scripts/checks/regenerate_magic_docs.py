#!/usr/bin/env python3
"""Regenerate Magic Docs from source-of-truth code state.

[来源: ADR-038 §4 D5.1 — Magic Docs auto-update pattern]

Magic Docs live under `docs/magic/*.md` and contain machine-derived
metadata about the codebase. This script regenerates them from the
canonical sources so they don't drift.

Usage:
    python3 scripts/checks/regenerate_magic_docs.py api-routes
    python3 scripts/checks/regenerate_magic_docs.py all
    python3 scripts/checks/regenerate_magic_docs.py --check         # report-only, exit 1 on drift

Each magic doc has a corresponding regenerator function below.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MAGIC_DIR = REPO_ROOT / "docs" / "magic"


# ─── api-routes magic doc ──────────────────────────────────────────────────


def _collect_route_counts() -> tuple[dict[str, int], int]:
    routes_dir = REPO_ROOT / "backend" / "product" / "routes"
    counts: dict[str, int] = {}
    if not routes_dir.is_dir():
        return counts, 0
    for py in sorted(routes_dir.glob("*.py")):
        if py.name == "__init__.py":
            continue
        content = py.read_text(encoding="utf-8", errors="ignore")
        n = len(re.findall(r"@router\.(get|post|put|patch|delete|websocket)\(", content))
        if n > 0:
            counts[py.name] = n
    return counts, sum(counts.values())


def _render_api_routes(counts: dict[str, int], total: int) -> str:
    today = date.today().isoformat()
    rows = "\n".join(f"| {name} | {count} |" for name, count in sorted(counts.items()))
    return f"""# MAGIC DOC: API Routes Stats

_instructions_: Auto-derived from `backend/product/routes/*.py` — counts each `@router.<verb>(...)` decorator per file. **Do not hand-edit the count column.** Regenerate via `python3 scripts/checks/regenerate_magic_docs.py api-routes` whenever any router file changes. The freshness check (`scripts/checks/check_doc_freshness.py`) fires P1 if these counts diverge from disk.

_source_of_truth_: `backend/product/routes/*.py` decorators
_regenerator_: `scripts/checks/regenerate_magic_docs.py api-routes`
_freshness_check_: `scripts/checks/check_doc_freshness.py` (auto-runs in PostToolUse Edit/Write hook)
_last_sync_: {today}

## Counts by router file

| Router | Count |
|---|---|
{rows}
| **Total** | **{total}** |

## Why this file exists

This is a Magic Doc per ADR-038 §4 D5.1. Magic Docs are machine-derived metadata that:

1. **Live separately from human narrative** — `CLAUDE.md` is the curated narrative layer; this file is the machine-derived count layer. Two layers, not two sources of truth.
2. **Carry self-instructions** — the `_instructions_` line tells any AI agent reading this file how to maintain it.
3. **Get watched** — `check_doc_freshness.py` compares the count column against actual decorators on every Edit/Write to `backend/product/routes/`.

When you change a route file, do one of:
- Run `python3 scripts/checks/regenerate_magic_docs.py api-routes` (one-shot)
- Or let the next session's SessionStart hook flag the drift and regenerate

[来源: ADR-038-harness-optimization-strategy.md §4 D5.1 + Anthropic CC Magic Docs pattern]
"""


def regenerate_api_routes(*, check_only: bool = False) -> int:
    """Return 0 on no-drift, 1 on drift (or write success when not check_only)."""
    target = MAGIC_DIR / "api-routes.md"
    counts, total = _collect_route_counts()
    if not counts:
        print("ERROR: no routes found in backend/product/routes/", file=sys.stderr)
        return 2
    rendered = _render_api_routes(counts, total)

    if check_only:
        if not target.exists():
            print(f"DRIFT: {target.relative_to(REPO_ROOT)} missing", file=sys.stderr)
            return 1
        existing = target.read_text(encoding="utf-8")
        # Compare ignoring _last_sync_ line (date is volatile)
        norm_existing = re.sub(r"_last_sync_:.*", "_last_sync_:", existing)
        norm_new = re.sub(r"_last_sync_:.*", "_last_sync_:", rendered)
        if norm_existing.strip() == norm_new.strip():
            return 0
        print(f"DRIFT: {target.relative_to(REPO_ROOT)} content differs from generator", file=sys.stderr)
        return 1

    MAGIC_DIR.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    print(f"Wrote {target.relative_to(REPO_ROOT)} ({total} routes across {len(counts)} files)")
    return 0


# ─── registry ───────────────────────────────────────────────────────────────

REGENERATORS = {
    "api-routes": regenerate_api_routes,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="magic doc name (e.g. api-routes) or 'all'")
    parser.add_argument("--check", action="store_true", help="report drift only, do not write")
    args = parser.parse_args(argv)

    if args.name == "all":
        targets = list(REGENERATORS.values())
    else:
        fn = REGENERATORS.get(args.name)
        if not fn:
            print(f"unknown magic doc: {args.name}. Known: {sorted(REGENERATORS)}", file=sys.stderr)
            return 2
        targets = [fn]

    rc = 0
    for fn in targets:
        rc |= fn(check_only=args.check)
    return rc


if __name__ == "__main__":
    sys.exit(main())
