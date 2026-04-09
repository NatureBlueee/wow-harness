"""Check referential integrity between CONTEXT_MAP and context-fragment files.

Two-directional:
  1. Forward: every fragment name referenced in CONTEXT_MAP must have a .md file  (P1 blocking)
  2. Reverse: every .md file in context-fragments/ must be referenced by some route (P2 warning)
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.checks import Finding
from scripts.context_router import CONTEXT_MAP, FALLBACK_FRAGMENTS, FRAGMENTS_DIR


def _referenced_fragments() -> set[str]:
    """Collect all fragment names referenced by CONTEXT_MAP + FALLBACK_FRAGMENTS."""
    names: set[str] = set()
    for fragments in CONTEXT_MAP.values():
        names.update(fragments)
    names.update(FALLBACK_FRAGMENTS)
    return names


def run(repo_root: Path, mode: str = "full") -> list[Finding]:
    findings: list[Finding] = []
    referenced = _referenced_fragments()
    fragments_dir = repo_root / "scripts" / "context-fragments"

    # Forward: every referenced fragment must have a .md file
    for name in sorted(referenced):
        path = fragments_dir / f"{name}.md"
        if not path.is_file():
            findings.append(Finding(
                severity="P1",
                message=f"Referenced fragment missing: {name}.md",
                file=f"scripts/context-fragments/{name}.md",
                blocking=True,
                category="fragment_integrity",
                problem_class="missing_fragment",
            ))

    # Reverse: every .md file must be referenced
    if fragments_dir.is_dir():
        on_disk = {p.stem for p in fragments_dir.glob("*.md")}
        orphans = on_disk - referenced
        for name in sorted(orphans):
            findings.append(Finding(
                severity="P2",
                message=f"Orphan fragment not referenced by any route: {name}.md",
                file=f"scripts/context-fragments/{name}.md",
                blocking=False,
                category="fragment_integrity",
                problem_class="orphan_fragment",
            ))

    return findings


if __name__ == "__main__":
    results = run(_REPO_ROOT)
    for f in results:
        print(f"[{f.severity}] {f.file}: {f.message}")
    print(f"\n--- {len(results)} findings ---")
    sys.exit(1 if any(f.blocking for f in results) else 0)
