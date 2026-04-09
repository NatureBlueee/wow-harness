#!/usr/bin/env python3
"""INV-4 guard: verify file existence claims against the filesystem.

Scans ADR / PLAN / LOG markdown files for two classes of claims:

  NEGATIVE ("this does NOT exist"):
    Phrases like "经核实不存在", "已删除", "grep-verified", "not found in repo".
    The check asserts the referenced path is ACTUALLY ABSENT on disk.
    If the path does exist, the claim is a hallucination → fail.

  POSITIVE ("this DOES exist / is deployed"):
    Phrases like "已部署", "now live", "wired up", "verified in CI".
    The check asserts the path is present on disk AND has at least one
    commit in git history. A file that exists but was never committed
    could still be "vapor deployed" (claim in doc, file created post-hoc
    to silence the check). Both tests must pass.

This guard is itself the product of PLAN-086 §13.3 (four rounds of INV-4
activation during ADR-043 drafting) + §13.5 (the fifth round — positive
claims were the blind spot). Running it on its own ADR (ADR-043-*.md) is
the B-14 release-gate acceptance condition: the guard must catch the
hallucinations that motivated its existence.

Usage:
    python3 check_file_existence_claims.py path/to/doc.md [doc2.md ...]

Exit codes:
    0 — all claims verified
    1 — IO error / bad input
    2 — at least one claim violation (AssertionError)

grep backend fallback chain (for "grep-verified" class):
    1. rg -l <match> <repo_root>            # preferred
    2. git grep -l <match> HEAD             # fallback if rg missing
    3. pure-Python pathlib.rglob string scan # last resort
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Make scripts/ importable so we can pull the shared claim-pattern library.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.lib.claim_patterns import (  # noqa: E402
    iter_negative_claims,
    iter_positive_claims,
)


class ClaimViolation(AssertionError):
    """Raised when a claim contradicts filesystem/git reality."""


def _grep_verify(needle: str, repo_root: Path) -> bool:
    """Return True if `needle` is findable in `repo_root` by any backend.

    Fallback chain: rg -> git grep -> pathlib.rglob.
    """
    # 1. rg (preferred)
    if shutil.which("rg"):
        try:
            r = subprocess.run(
                ["rg", "-l", "--fixed-strings", needle, str(repo_root)],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0 and r.stdout.strip():
                return True
            # rg returncode 1 = no matches; 2 = error
            if r.returncode == 1:
                return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # 2. git grep
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_root), "grep", "-l", "--fixed-strings", needle, "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0 and r.stdout.strip():
            return True
        if r.returncode == 1:
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        pass

    # 3. pure Python fallback
    try:
        for p in repo_root.rglob("*"):
            if not p.is_file():
                continue
            if ".git" in p.parts or "__pycache__" in p.parts:
                continue
            try:
                if needle in p.read_text(errors="ignore"):
                    return True
            except (OSError, UnicodeDecodeError):
                continue
    except OSError:
        pass

    # All three backends produced no match → report as "unable to verify"
    # by raising, distinguishable from "verified absent".
    raise RuntimeError(
        f"no grep backend available to verify claim for '{needle}'"
    )


def _path_in_git_history(path: str, repo_root: Path) -> bool:
    """Return True if `path` has appeared in any commit on any branch."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_root), "log", "--all",
             "--format=", "--name-only", "--", path],
            capture_output=True, text=True, timeout=30,
        )
        return bool(r.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_file(doc_path: Path, repo_root: Path) -> list[str]:
    """Return list of violation messages for `doc_path`. Empty = clean."""
    violations: list[str] = []
    try:
        text = doc_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return [f"{doc_path}: IO error: {exc}"]

    # --- Negative claims: asserted absent ---
    for marker, path_str in iter_negative_claims(text):
        target = repo_root / path_str
        marker_lc = marker.lower().replace("-", "")
        if "grepverified" in marker_lc:
            # "grep-verified" means the author claims to have grepped and
            # NOT found it → we verify the opposite is also true.
            try:
                found = _grep_verify(path_str, repo_root)
            except RuntimeError as exc:
                violations.append(
                    f"{doc_path}: {exc} (claim: '{marker} {path_str}')"
                )
                continue
            if found:
                violations.append(
                    f"{doc_path}: negative claim '{marker} {path_str}' "
                    f"contradicted — grep found the path in repo"
                )
        else:
            # "不存在" / "已删除" / "not found" → filesystem must agree
            if target.exists():
                violations.append(
                    f"{doc_path}: negative claim '{marker} {path_str}' "
                    f"contradicted — file exists at {target}"
                )

    # --- Positive claims: asserted present ---
    for marker, path_str in iter_positive_claims(text):
        target = repo_root / path_str
        if not target.exists():
            violations.append(
                f"{doc_path}: positive existence claim not backed by filesystem "
                f"('{marker} {path_str}' → {target} missing)"
            )
            continue
        if not _path_in_git_history(path_str, repo_root):
            violations.append(
                f"{doc_path}: positive existence claim not backed by git history "
                f"('{marker} {path_str}' → no commits touching this path). "
                f"Defends against vapor-deploy claims."
            )

    return violations


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: check_file_existence_claims.py DOC [DOC ...]", file=sys.stderr)
        return 1

    # Expand globs so callers can pass `docs/decisions/ADR-*.md`.
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
        print("INV-4 claim violations:", file=sys.stderr)
        for v in all_violations:
            print(f"  - {v}", file=sys.stderr)
        raise ClaimViolation(
            f"{len(all_violations)} claim violation(s) across {len(paths)} file(s)"
        )

    print(f"OK: {len(paths)} file(s) scanned, no claim violations")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ClaimViolation as exc:
        print(f"AssertionError: {exc}", file=sys.stderr)
        sys.exit(2)
