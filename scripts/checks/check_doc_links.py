"""Check for dead links in documentation files.

Detects two patterns:
  1. Markdown links: [text](relative/path)
  2. Inline backtick paths: `path/to/file.md`
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.checks import Finding

# Patterns
_MD_LINK = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
_BACKTICK_PATH = re.compile(r'`([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+)`')

# Directories/files to scan
_SCAN_FILES = ["MEMORY.md", "CLAUDE.md"]
_SCAN_DIRS = ["docs"]
# Subdirectories to skip — contain historical/archived content with intentionally stale paths
_SKIP_SUBDIRS = {"docs/archive"}
# Subdirectories where backtick paths are design-time snapshots (skip P2 backtick check, keep P1 link check)
_DESIGN_DOC_DIRS = {"docs/decisions", "docs/design-logs", "docs/engineering", "docs/reviews", "docs/research"}

# Paths to ignore (external URLs, anchors, images from web)
_IGNORE_PREFIXES = ("http://", "https://", "mailto:", "#", "data:")
# Extensions that are likely paths (not code identifiers)
_PATH_EXTENSIONS = {".md", ".py", ".ts", ".tsx", ".js", ".json", ".yaml", ".yml", ".toml", ".sh", ".css", ".html"}


def _is_strikethrough_line(line: str, match_start: int) -> bool:
    """Check if the match is inside a strikethrough (~~deleted~~)."""
    before = line[:match_start]
    after = line[match_start:]
    return before.count("~~") % 2 == 1 or "~~" in before and "~~" in after


def _check_file(md_path: Path, repo_root: Path, *, skip_backtick: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    try:
        content = md_path.read_text(encoding="utf-8")
    except OSError:
        return findings

    rel_md = str(md_path.relative_to(repo_root))

    for line_num, line in enumerate(content.splitlines(), 1):
        # Skip strikethrough lines (already marked as deleted)
        if "~~" in line:
            continue

        # 1. Markdown links
        for m in _MD_LINK.finditer(line):
            target = m.group(2).split("#")[0].strip()
            if not target or any(target.startswith(p) for p in _IGNORE_PREFIXES):
                continue
            # Skip obvious placeholder/example links
            if target in ("relative/path", "path", "path/to/file", "path/to/file.md", "url"):
                continue
            # Resolve relative to the markdown file's directory
            resolved = (md_path.parent / target).resolve()
            if not resolved.exists():
                findings.append(Finding(
                    severity="P1",
                    message=f"Dead link: [{m.group(1)}]({m.group(2)})",
                    file=rel_md,
                    line=line_num,
                ))

        # 2. Backtick paths (only if they look like file paths)
        if skip_backtick:
            continue
        for m in _BACKTICK_PATH.finditer(line):
            path_str = m.group(1)
            suffix = Path(path_str).suffix
            if suffix not in _PATH_EXTENSIONS:
                continue
            if "/" not in path_str:
                continue  # Single filename without directory — likely a code reference
            # Try relative to the markdown file's directory first, then repo root
            resolved_local = (md_path.parent / path_str).resolve()
            resolved_root = (repo_root / path_str).resolve()
            if not resolved_local.exists() and not resolved_root.exists():
                findings.append(Finding(
                    severity="P2",
                    message=f"Possible dead path: `{path_str}`",
                    file=rel_md,
                    line=line_num,
                ))

    return findings


def run(repo_root: Path, mode: str = "full") -> list[Finding]:
    findings: list[Finding] = []

    # Scan specific top-level files
    for name in _SCAN_FILES:
        f = repo_root / name
        if f.exists():
            findings.extend(_check_file(f, repo_root))

    # Scan docs directory
    for dir_name in _SCAN_DIRS:
        scan_dir = repo_root / dir_name
        if scan_dir.is_dir():
            for md in sorted(scan_dir.rglob("*.md")):
                rel = str(md.relative_to(repo_root))
                if any(rel.startswith(s) for s in _SKIP_SUBDIRS):
                    continue
                if md.name == "LOG.md":
                    continue
                is_design = any(rel.startswith(d) for d in _DESIGN_DOC_DIRS)
                findings.extend(_check_file(md, repo_root, skip_backtick=is_design))

    return findings


if __name__ == "__main__":
    results = run(_REPO_ROOT)
    for f in results:
        loc = f"{f.file}:{f.line}" if f.line else f.file
        print(f"[{f.severity}] {loc}: {f.message}")
    print(f"\n--- {len(results)} findings ---")
    sys.exit(1 if any(f.severity == "P0" for f in results) else 0)
