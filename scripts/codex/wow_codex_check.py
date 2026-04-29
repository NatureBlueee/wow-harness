#!/usr/bin/env python3
"""Codex-side wow-harness feedback pass.

Codex now has official lifecycle hooks wired through ``.codex/hooks.json``.
This script remains the mechanical fallback and Stop-time checker: it gives
Codex a "before you claim completion" pass without making Codex a Gate reviewer.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".wow-harness" / "MANIFEST.yaml").is_file():
            return candidate
    raise SystemExit("wow-codex-check: not inside a wow-harness checkout")


def run_git(root: Path, args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_files(root: Path) -> list[str]:
    tracked = run_git(root, ["diff", "--name-only", "--diff-filter=ACMRTUXB", "HEAD", "--"])
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"])
    return sorted(dict.fromkeys([*tracked, *untracked]))


def normalize_path(root: Path, value: str) -> str | None:
    try:
        p = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
        rel = p.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return rel.as_posix()


def finding_to_dict(finding: object) -> dict:
    if isinstance(finding, dict):
        return finding
    if dataclasses.is_dataclass(finding):
        return dataclasses.asdict(finding)
    return {"severity": "P2", "message": str(finding), "category": "general", "blocking": False}


RISK_ELEVATORS: list[tuple[str, str]] = [
    ("scripts/deploy", "R4"),
    ("backend/product/db/migration", "R4"),
    ("CLAUDE.md", "R3"),
    ("AGENTS.md", "R3"),
    (".wow-harness/", "R3"),
    (".claude/settings.json", "R3"),
    (".claude/skills/", "R3"),
    (".claude/rules/", "R3"),
    (".claude/agents/", "R3"),
    (".codex/", "R3"),
    (".cursor/", "R3"),
    (".opencode/", "R3"),
    ("scripts/codex/", "R3"),
    ("scripts/hooks/", "R3"),
    ("scripts/checks/", "R3"),
    ("scripts/install/", "R3"),
    (".github/", "R3"),
    ("backend/product/routes/", "R2"),
    ("backend/product/config.py", "R2"),
    ("backend/server.py", "R2"),
    ("docs/decisions/ADR-", "R2"),
    ("mcp-server/", "R2"),
    ("mcp-server-node/", "R2"),
    ("website/app/", "R2"),
]


def classify_file(file_path: str) -> str:
    for pattern, risk in RISK_ELEVATORS:
        if file_path.startswith(pattern):
            return risk
    return "R0"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run wow-harness feedback for Codex-managed edits.")
    parser.add_argument("paths", nargs="*", help="Specific repo-relative paths to check. Defaults to changed files.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--full-context", action="store_true", help="Print full context fragment text, not just names.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blocking findings exist.")
    args = parser.parse_args()

    root = repo_root()
    sys.path.insert(0, str(root))

    from scripts.context_router import FALLBACK_FRAGMENTS, load_fragment, match  # noqa: PLC0415
    from scripts.guard_router import route, run_guards  # noqa: PLC0415

    raw_paths = args.paths or changed_files(root)
    paths = [p for p in (normalize_path(root, item) for item in raw_paths) if p]

    records: list[dict] = []
    blocking = False
    for rel in paths:
        fragments = match(rel) or list(FALLBACK_FRAGMENTS)
        guard_names = route(rel)
        findings = [finding_to_dict(item) for item in run_guards(rel)]
        blocking = blocking or any(bool(item.get("blocking")) for item in findings)
        records.append(
            {
                "path": rel,
                "risk": classify_file(rel),
                "fragments": fragments,
                "guards": guard_names,
                "findings": findings,
            }
        )

    payload = {
        "repo": str(root),
        "changed_file_count": len(paths),
        "blocking": blocking,
        "records": records,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("## wow-harness Codex Check")
        print(f"repo: {root}")
        print(f"changed files: {len(paths)}")
        if not records:
            print("No changed files found.")
        for record in records:
            print(f"\n### {record['path']} [{record['risk']}]")
            print(f"context: {', '.join(record['fragments'])}")
            if args.full_context:
                for fragment in record["fragments"]:
                    text = load_fragment(fragment)
                    if text:
                        print(f"\n--- {fragment} ---\n{text}")
            print(f"guards: {', '.join(record['guards']) if record['guards'] else '(none)'}")
            if record["findings"]:
                print("findings:")
                for finding in record["findings"]:
                    tag = " blocking" if finding.get("blocking") else ""
                    print(f"- {finding.get('severity', 'P2')}{tag} {finding.get('category', 'general')}: {finding.get('message', '')}")
            else:
                print("findings: none")

    return 2 if args.strict and blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
