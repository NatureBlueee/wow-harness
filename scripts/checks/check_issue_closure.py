"""Check issue doc closure semantics via YAML frontmatter.

Ensures that issues marked as 'fixed' have proper prevention_status
and mechanism_layer declarations per ADR-030 closure semantics.

Schema (harness-level convention, not project-specific):
    status: open | in-progress | fixed
    prevention_status: open | closed      # required when status: fixed
    mechanism_layer: L0 | L1 | L2 | ...   # recommended when status: fixed

Projects that do not use docs/issues/*.md can disable this check via
.wow-harness.yaml checks.disable list.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.checks import Finding

_CATEGORY = "closure_semantics"
_REQUIRED_SKILLS = ["lead", "harness-ops"]


def parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter delimited by --- markers."""
    if not content.startswith("---"):
        return {}
    try:
        end = content.index("---", 3)
    except ValueError:
        return {}
    lines = content[3:end].strip().split("\n")
    result = {}
    for line in lines:
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def _check_issue(path: Path, repo_root: Path) -> list[Finding]:
    """Check a single issue document for closure semantics."""
    findings: list[Finding] = []
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return findings

    rel = str(path.relative_to(repo_root))
    fm = parse_frontmatter(content)

    if not fm:
        findings.append(Finding(
            severity="P2",
            message="Issue doc missing YAML frontmatter",
            file=rel,
            line=1,
            blocking=False,
            category=_CATEGORY,
            required_skills=_REQUIRED_SKILLS,
        ))
        return findings

    status = fm.get("status", "")
    prevention = fm.get("prevention_status")
    mechanism = fm.get("mechanism_layer")

    if status != "fixed":
        return findings

    if prevention is None:
        findings.append(Finding(
            severity="P1",
            message="Fixed but missing prevention_status declaration",
            file=rel,
            line=1,
            blocking=True,
            category=_CATEGORY,
            required_skills=_REQUIRED_SKILLS,
        ))
    elif prevention == "open":
        findings.append(Finding(
            severity="P1",
            message="Fixed but prevention_status still open (recurrence path not closed)",
            file=rel,
            line=1,
            blocking=True,
            category=_CATEGORY,
            required_skills=_REQUIRED_SKILLS,
        ))

    if mechanism is None:
        findings.append(Finding(
            severity="P2",
            message="Fixed but missing mechanism_layer declaration",
            file=rel,
            line=1,
            blocking=False,
            category=_CATEGORY,
            required_skills=_REQUIRED_SKILLS,
        ))

    return findings


def _head_frontmatter(path: Path, repo_root: Path) -> dict | None:
    """Read frontmatter from HEAD version of a file. Returns None if not in HEAD."""
    rel = str(path.relative_to(repo_root))
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{rel}"],
            capture_output=True, text=True, cwd=repo_root,
        )
        if result.returncode != 0:
            return None
        return parse_frontmatter(result.stdout)
    except Exception:
        return None


def run(repo_root: Path, mode: str = "full") -> list[Finding]:
    """Scan issue docs and check closure semantics.

    Args:
        repo_root: Repository root path.
        mode: "full" scans all issue docs; "staged" downgrades pre-existing findings.
    """
    findings: list[Finding] = []
    issues_dir = repo_root / "docs" / "issues"
    if not issues_dir.is_dir():
        return findings

    for md in sorted(issues_dir.glob("*.md")):
        file_findings = _check_issue(md, repo_root)

        if mode == "staged" and file_findings:
            head_fm = _head_frontmatter(md, repo_root)
            head_was_blocking = False
            if head_fm is None:
                head_was_blocking = False
            elif not head_fm or not head_fm.get("status"):
                head_was_blocking = True
            elif head_fm.get("status") == "fixed" and head_fm.get("prevention_status") in ("open", None):
                head_was_blocking = True

            if head_was_blocking:
                for f in file_findings:
                    if f.blocking:
                        f.blocking = False
                        f.message = f"[pre-existing] {f.message}"

        findings.extend(file_findings)

    return findings


if __name__ == "__main__":
    results = run(_REPO_ROOT)
    for f in results:
        loc = f"{f.file}:{f.line}" if f.line else f.file
        print(f"[{f.severity}] {loc}: {f.message}")
    print(f"\n--- {len(results)} findings ---")
    sys.exit(1 if any(f.blocking for f in results) else 0)
