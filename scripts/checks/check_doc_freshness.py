"""Check documentation freshness against actual codebase state.

Detects drift between CLAUDE.md / ROADMAP.md claims and the real
codebase: route counts, test counts, env var coverage, scene lists, etc.

Runs in guard_router write-time path or standalone via:
    python3 scripts/checks/check_doc_freshness.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.checks import Finding


def _count_route_decorators(repo_root: Path) -> int:
    """Count @router.get/post/... decorators in routes/."""
    routes_dir = repo_root / "backend" / "product" / "routes"
    if not routes_dir.is_dir():
        return 0
    count = 0
    for py in routes_dir.glob("*.py"):
        content = py.read_text(encoding="utf-8", errors="ignore")
        count += len(re.findall(r"@router\.(get|post|put|patch|delete|websocket)\(", content))
    return count


def _count_scenes(repo_root: Path) -> int:
    """Count scene directories."""
    scenes_dir = repo_root / "scenes"
    if not scenes_dir.is_dir():
        return 0
    return sum(1 for d in scenes_dir.iterdir() if d.is_dir() and not d.name.startswith("."))


def _count_adrs(repo_root: Path) -> int:
    decisions = repo_root / "docs" / "decisions"
    if not decisions.is_dir():
        return 0
    return sum(1 for f in decisions.glob("ADR-*.md"))


def _count_plans(repo_root: Path) -> int:
    decisions = repo_root / "docs" / "decisions"
    if not decisions.is_dir():
        return 0
    return sum(1 for f in decisions.glob("PLAN-*.md"))


def _extract_claudemd_test_count(repo_root: Path) -> int | None:
    """Extract the test count claim from CLAUDE.md."""
    claude_md = repo_root / "CLAUDE.md"
    if not claude_md.exists():
        return None
    content = claude_md.read_text(encoding="utf-8")
    m = re.search(r"Tests?\s*\((\d+)\s+collectable", content)
    return int(m.group(1)) if m else None


def _extract_roadmap_numbers(repo_root: Path) -> dict[str, str]:
    """Extract claimed numbers from ROADMAP.md Current Numbers table."""
    roadmap = repo_root / "docs" / "ROADMAP.md"
    if not roadmap.exists():
        return {}
    content = roadmap.read_text(encoding="utf-8")
    numbers = {}
    for m in re.finditer(r"\|\s*(\S[^|]+?)\s*\|\s*(\S[^|]+?)\s*\|", content):
        key, val = m.group(1).strip(), m.group(2).strip()
        if key in ("指标", "---"):
            continue
        numbers[key] = val
    return numbers


def _check_magic_docs(repo_root: Path) -> list[Finding]:
    """Run magic doc regenerators in --check mode (ADR-038 D5.1)."""
    findings: list[Finding] = []
    try:
        from scripts.checks import regenerate_magic_docs
    except ImportError:
        return findings  # regenerator not present yet
    for name, fn in regenerate_magic_docs.REGENERATORS.items():
        try:
            rc = fn(check_only=True)
        except Exception as exc:
            findings.append(Finding(
                severity="P1",
                message=f"Magic doc {name} regenerator raised: {exc}",
                file=f"docs/magic/{name}.md",
                category="doc_integrity",
            ))
            continue
        if rc != 0:
            findings.append(Finding(
                severity="P1",
                message=f"Magic doc docs/magic/{name}.md drifted from source. Run: python3 scripts/checks/regenerate_magic_docs.py {name}",
                file=f"docs/magic/{name}.md",
                category="doc_integrity",
            ))
    return findings


def run(repo_root: Path, *, mode: str = "full") -> list[Finding]:
    findings: list[Finding] = []

    # 0. Magic docs check (ADR-038 D5.1)
    findings.extend(_check_magic_docs(repo_root))

    # 1. Route count check (post-D3.1: routes live in .claude/rules/backend-routes.md, not CLAUDE.md)
    actual_routes = _count_route_decorators(repo_root)
    routes_doc = repo_root / ".claude" / "rules" / "backend-routes.md"
    claudemd = repo_root / "CLAUDE.md"  # kept for downstream content checks below
    if routes_doc.exists():
        routes_content = routes_doc.read_text(encoding="utf-8")
        route_claims = re.findall(r"-\s+`(?:GET|POST|PUT|PATCH|DELETE|WS)\s+", routes_content)
        doc_routes = len(route_claims)
        if actual_routes - doc_routes > 5:
            findings.append(Finding(
                severity="P1",
                message=f".claude/rules/backend-routes.md documents {doc_routes} routes but code has {actual_routes} decorators (gap: {actual_routes - doc_routes})",
                file=".claude/rules/backend-routes.md",
                category="doc_integrity",
            ))
    if claudemd.exists():
        content = claudemd.read_text(encoding="utf-8")
    else:
        content = ""

    # 2. Scene count check
    actual_scenes = _count_scenes(repo_root)
    if claudemd.exists():
        # Count scene entries under "├── scenes/" section — lines like "│   ├── ai-gig-market/"
        scenes_section = re.search(r"├── scenes/.*?(?=├── \w|└──)", content, re.DOTALL)
        scene_refs = len(re.findall(r"│\s+[├└]──\s+\S+/", scenes_section.group())) if scenes_section else 0
        if scene_refs > 0 and abs(actual_scenes - scene_refs) > 1:
            findings.append(Finding(
                severity="P2",
                message=f"CLAUDE.md lists {scene_refs} scenes but {actual_scenes} exist on disk",
                file="CLAUDE.md",
                category="doc_integrity",
            ))

    # 3. ADR/PLAN count check against ROADMAP
    roadmap_nums = _extract_roadmap_numbers(repo_root)
    actual_adrs = _count_adrs(repo_root)
    actual_plans = _count_plans(repo_root)

    if "ADR" in roadmap_nums:
        try:
            claimed = int(re.search(r"\d+", roadmap_nums["ADR"]).group())
            if actual_adrs - claimed > 2:
                findings.append(Finding(
                    severity="P2",
                    message=f"ROADMAP claims {claimed} ADRs but {actual_adrs} exist",
                    file="docs/ROADMAP.md",
                    category="doc_integrity",
                ))
        except (ValueError, AttributeError):
            pass

    if "PLAN" in roadmap_nums:
        try:
            claimed = int(re.search(r"\d+", roadmap_nums["PLAN"]).group())
            if actual_plans - claimed > 3:
                findings.append(Finding(
                    severity="P2",
                    message=f"ROADMAP claims {claimed} PLANs but {actual_plans} exist",
                    file="docs/ROADMAP.md",
                    category="doc_integrity",
                ))
        except (ValueError, AttributeError):
            pass

    # 4. Test count staleness (compare CLAUDE.md claim vs age)
    claimed_tests = _extract_claudemd_test_count(repo_root)
    if claimed_tests is not None:
        date_match = re.search(r"Tests?\s*\(\d+\s+collectable\s+as\s+of\s+(\d{4}-\d{2}-\d{2})", content)
        if date_match:
            from datetime import date
            claimed_date = date.fromisoformat(date_match.group(1))
            age_days = (date.today() - claimed_date).days
            if age_days > 7:
                findings.append(Finding(
                    severity="P2",
                    message=f"CLAUDE.md test count is {age_days} days old (from {date_match.group(1)}). Run pytest --collect-only to verify.",
                    file="CLAUDE.md",
                    category="doc_integrity",
                ))

    return findings


if __name__ == "__main__":
    results = run(_REPO_ROOT)
    if results:
        for f in results:
            print(f"[{f.severity}] {f.file}: {f.message}")
        sys.exit(1)
    else:
        print("Doc freshness check: all clear")
        sys.exit(0)
