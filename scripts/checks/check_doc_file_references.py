#!/usr/bin/env python3
"""INV-4 guard: verify backtick-quoted path/arXiv references in docs resolve.

Scans markdown files for inline references like:

    `docs/decisions/ADR-043-wow-harness-open-sourcing.md`
    `scripts/checks/check_versions.py`
    `arXiv:2603.05344`

For filesystem paths (docs/, scripts/, backend/, frontend/, website/,
mcp-server/, .claude/), asserts the path exists on disk. For arXiv IDs,
optionally fetches the abstract page (CI only, with network) to confirm
the ID resolves; in local mode (no network / $CI unset), prints a
`[skipped]` warning but does NOT fail.

Usage:
    python3 check_doc_file_references.py path/to/doc.md [doc2.md ...]

Exit codes:
    0 — all references resolve
    1 — IO error / bad input
    2 — at least one dead reference (AssertionError)

Environment:
    CI=1 enables arXiv WebFetch mode; unset = local skip.
"""
from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.lib.claim_patterns import iter_doc_refs  # noqa: E402


_ARXIV_RE = re.compile(r"^arXiv:(\d{4}\.\d{4,5})$")


class DeadReference(AssertionError):
    pass


def _check_arxiv(arxiv_id: str) -> tuple[bool, str]:
    """Return (ok, message). In local mode, ok=True + message marks skip."""
    if not os.environ.get("CI"):
        return True, f"[skipped: local mode] arXiv:{arxiv_id}"
    # CI mode: attempt WebFetch via urllib (no external deps).
    try:
        import urllib.request
        url = f"https://arxiv.org/abs/{arxiv_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "wow-harness-check/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            if resp.status == 200:
                body = resp.read(8192).decode("utf-8", errors="ignore")
                if arxiv_id in body:
                    return True, f"arXiv:{arxiv_id} OK"
                return False, f"arXiv:{arxiv_id} fetched 200 but body missing id"
            return False, f"arXiv:{arxiv_id} HTTP {resp.status}"
    except Exception as exc:  # noqa: BLE001
        return False, f"arXiv:{arxiv_id} fetch error: {exc}"


def check_file(doc_path: Path, repo_root: Path) -> list[str]:
    violations: list[str] = []
    try:
        text = doc_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return [f"{doc_path}: IO error: {exc}"]

    for ref in iter_doc_refs(text):
        arxiv_m = _ARXIV_RE.match(ref)
        if arxiv_m:
            ok, msg = _check_arxiv(arxiv_m.group(1))
            if not ok:
                violations.append(f"{doc_path}: dead arXiv reference: {msg}")
            elif msg.startswith("[skipped"):
                # Informational, non-failing
                print(f"WARN  {doc_path}: {msg}", file=sys.stderr)
            continue

        target = repo_root / ref
        if not target.exists():
            violations.append(
                f"{doc_path}: dead doc reference: `{ref}` (expected at {target})"
            )

    return violations


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: check_doc_file_references.py DOC [DOC ...]", file=sys.stderr)
        return 1

    paths: list[Path] = []
    for arg in argv:
        expanded = glob.glob(arg)
        if not expanded:
            paths.append(Path(arg))
        else:
            paths.extend(Path(p) for p in expanded)

    repo_root = _REPO_ROOT
    all_violations: list[str] = []
    for p in paths:
        if not p.exists():
            all_violations.append(f"{p}: input file does not exist")
            continue
        all_violations.extend(check_file(p, repo_root))

    if all_violations:
        print("Dead doc references:", file=sys.stderr)
        for v in all_violations:
            print(f"  - {v}", file=sys.stderr)
        raise DeadReference(
            f"{len(all_violations)} dead reference(s) across {len(paths)} file(s)"
        )

    print(f"OK: {len(paths)} file(s) scanned, no dead references")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DeadReference as exc:
        print(f"AssertionError: {exc}", file=sys.stderr)
        sys.exit(2)
