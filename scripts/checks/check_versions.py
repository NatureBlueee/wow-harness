"""Check for hardcoded version strings that drift from source of truth.

Sources of truth:
  - mcp-server/pyproject.toml  (Python MCP version)
  - mcp-server-node/package.json  (Node MCP version)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.checks import Finding

# Directories to skip
_SKIP_DIRS = {"node_modules", "venv", ".venv", ".git", "__pycache__", ".open-next", "dist", "build", ".next", ".towow"}
# Directories where 'version:' fields refer to their own artifacts, not MCP
_SKIP_VERSION_DIRS = {".claude/agents", ".claude/skills"}
# File extensions to scan
_SCAN_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".md", ".yaml", ".yml", ".toml", ".json"}
# Files that ARE the truth source — skip them
_TRUTH_SOURCES = {
    "mcp-server/pyproject.toml",
    "mcp-server-node/package.json",
}


def _read_python_version(repo_root: Path) -> str | None:
    pyproject = repo_root / "mcp-server" / "pyproject.toml"
    if not pyproject.exists():
        return None
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        m = re.match(r'^version\s*=\s*"([^"]+)"', line)
        if m:
            return m.group(1)
    return None


def _read_node_version(repo_root: Path) -> str | None:
    pkg = repo_root / "mcp-server-node" / "package.json"
    if not pkg.exists():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        return data.get("version")
    except (json.JSONDecodeError, OSError):
        return None


def _should_skip(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root)
    parts = rel.parts
    return any(p in _SKIP_DIRS for p in parts)


def run(repo_root: Path, mode: str = "full") -> list[Finding]:
    findings: list[Finding] = []

    py_ver = _read_python_version(repo_root)
    node_ver = _read_node_version(repo_root)

    if py_ver is None:
        findings.append(Finding(
            severity="P0",
            message="Cannot read version from mcp-server/pyproject.toml",
            file="mcp-server/pyproject.toml",
        ))
        return findings

    if node_ver is None:
        findings.append(Finding(
            severity="P0",
            message="Cannot read version from mcp-server-node/package.json",
            file="mcp-server-node/package.json",
        ))
        return findings

    if py_ver != node_ver:
        findings.append(Finding(
            severity="P0",
            message=f"Version mismatch: Python={py_ver}, Node={node_ver}",
            file="mcp-server/pyproject.toml",
        ))

    # Scan for hardcoded old version patterns (previous versions)
    # Build regex for common version patterns that might be stale
    current = py_ver
    # Match patterns like: version = "0.3.x", "version": "0.3.x", v0.3.x
    version_pattern = re.compile(
        r'(?:version["\s:=]+["\']?)(\d+\.\d+\.\d+)',
        re.IGNORECASE,
    )

    for ext in _SCAN_EXTENSIONS:
        for f in repo_root.rglob(f"*{ext}"):
            if _should_skip(f, repo_root):
                continue
            rel = str(f.relative_to(repo_root))
            if rel in _TRUTH_SOURCES:
                continue
            # Skip dirs where 'version:' is the artifact's own version, not MCP
            if any(rel.startswith(d) for d in _SKIP_VERSION_DIRS):
                continue
            # Skip lock files
            if f.name in ("package-lock.json", "poetry.lock", "Pipfile.lock"):
                continue
            # Skip development logs — version refs are historical snapshots
            if f.name == "LOG.md":
                continue

            try:
                content = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for line_num, line in enumerate(content.splitlines(), 1):
                for m in version_pattern.finditer(line):
                    found_ver = m.group(1)
                    # Only flag if it looks like an MCP version but doesn't match current
                    if found_ver.startswith(current[:4]) and found_ver != current:
                        findings.append(Finding(
                            severity="P1",
                            message=f"Possible stale version '{found_ver}' (current: {current})",
                            file=rel,
                            line=line_num,
                        ))

    return findings


if __name__ == "__main__":
    results = run(_REPO_ROOT)
    for f in results:
        loc = f"{f.file}:{f.line}" if f.line else f.file
        print(f"[{f.severity}] {loc}: {f.message}")
    print(f"\n--- {len(results)} findings ---")
    sys.exit(1 if any(f.severity == "P0" for f in results) else 0)
