"""Check that code changes are accompanied by artifact documentation.

Phase 3 presence gate: if staged/PR files include code changes (.py, .ts, .tsx,
.js, .jsx) but no docs/issues/ or docs/decisions/ file, emit a P1 blocking
finding.  Skipped in full (deploy) mode — artifact linkage is a commit-time
check.

Phase 4 scope binding: if artifact docs have a ``scope`` field in YAML
frontmatter, verify that every changed code file is covered by at least one
artifact's scope prefixes.  Uncovered files emit a P2 non-blocking warning.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.checks import Finding

_CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}
_CONFIG_EXTENSIONS = {".json", ".yml", ".yaml", ".toml"}
_TEST_PREFIXES = ("tests/", "test_")
_ARTIFACT_PREFIXES = ("docs/issues/", "docs/decisions/")
# Build output directories — not authored code, should not trigger artifact linkage
_BUILD_DIRS = {".open-next", "dist", "build", ".next", "node_modules"}


def _is_code_file(path: str) -> bool:
    """Return True if *path* is a non-test, non-config, non-build code file."""
    p = Path(path)
    if p.suffix not in _CODE_EXTENSIONS:
        return False
    if any(part.startswith("test_") or part == "tests" for part in p.parts):
        return False
    if any(part in _BUILD_DIRS for part in p.parts):
        return False
    return True


def _is_artifact_file(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _ARTIFACT_PREFIXES) and path.endswith(".md")


def _extract_scope(artifact_path: Path) -> list[str]:
    """Extract ``scope`` list from YAML frontmatter of an artifact doc.

    Returns an empty list if the file has no frontmatter or no scope field.
    """
    try:
        text = artifact_path.read_text(encoding="utf-8")
    except OSError:
        return []

    if not text.startswith("---"):
        return []

    end = text.find("\n---", 3)
    if end == -1:
        return []

    frontmatter = text[3:end]

    # Minimal YAML list parsing for the scope field — avoids PyYAML dependency.
    scopes: list[str] = []
    in_scope = False
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("scope:"):
            value = stripped[len("scope:"):].strip()
            if value and not value.startswith("["):
                # inline scalar (single value)
                scopes.append(value)
                in_scope = False
            elif value.startswith("["):
                # inline list: scope: [a, b]
                inner = value.strip("[] ")
                scopes.extend(s.strip().strip("\"'") for s in inner.split(",") if s.strip())
                in_scope = False
            else:
                # block list follows
                in_scope = True
            continue
        if in_scope:
            if stripped.startswith("- "):
                scopes.append(stripped[2:].strip().strip("\"'"))
            elif stripped and not stripped.startswith("#"):
                # new key — stop collecting
                in_scope = False

    return [s for s in scopes if s]


def _check_scope_binding(
    code_files: list[str],
    artifact_files: list[str],
    repo_root: Path,
) -> list[Finding]:
    """Check that each code file is covered by at least one artifact's scope."""
    all_scopes: list[str] = []
    for af in artifact_files:
        all_scopes.extend(_extract_scope(repo_root / af))

    if not all_scopes:
        # No artifact has scope defined — skip scope binding (backwards compat)
        return []

    uncovered: list[str] = []
    for cf in code_files:
        if not any(cf.startswith(scope) for scope in all_scopes):
            uncovered.append(cf)

    if not uncovered:
        return []

    return [Finding(
        severity="P2",
        message=(
            f"Scope binding gap: {len(uncovered)} code file(s) not covered by "
            f"any artifact scope. Uncovered: {', '.join(uncovered[:5])}"
            + (f" (and {len(uncovered) - 5} more)" if len(uncovered) > 5 else "")
            + ". Add a scope field to the relevant artifact doc."
        ),
        file=uncovered[0],
        blocking=False,
        category="scope_binding",
        required_skills=["lead"],
    )]


def _changed_files(mode: str) -> list[str]:
    """Get changed file list via git."""
    if mode == "staged":
        cmd = ["git", "diff", "--cached", "--name-only"]
    elif mode == "ci":
        cmd = ["git", "diff", "origin/main..HEAD", "--name-only"]
    else:
        return []

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO_ROOT)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def run(repo_root: Path, mode: str = "full") -> list[Finding]:
    if mode == "full":
        return []

    files = _changed_files(mode)
    if not files:
        return []

    code_files = [f for f in files if _is_code_file(f)]
    artifact_files = [f for f in files if _is_artifact_file(f)]
    has_code = bool(code_files)
    has_artifact = bool(artifact_files)

    findings: list[Finding] = []

    # Phase 3: presence gate
    if has_code and not has_artifact:
        findings.append(Finding(
            severity="P1",
            message=(
                f"Code changes without artifact documentation. "
                f"{len(code_files)} code file(s) changed but no docs/issues/ or "
                f"docs/decisions/ file included. Add an issue or decision doc."
            ),
            file=code_files[0],
            blocking=True,
            category="artifact_linkage",
            required_skills=["lead"],
        ))
        return findings  # no point checking scope if no artifact present

    # Phase 4: scope binding
    if has_code and has_artifact:
        findings.extend(_check_scope_binding(code_files, artifact_files, repo_root))

    return findings


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check artifact linkage for code changes")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", help="Check staged files (pre-commit)")
    group.add_argument("--ci", action="store_true", help="Check PR diff vs origin/main (CI)")
    args = parser.parse_args()

    if args.staged:
        mode = "staged"
    elif args.ci:
        mode = "ci"
    else:
        mode = "full"

    results = run(_REPO_ROOT, mode=mode)
    for f in results:
        print(f"[{f.severity}] {f.file}: {f.message}")
    if not results:
        print("No artifact linkage issues found.")
    sys.exit(1 if any(f.blocking for f in results) else 0)
