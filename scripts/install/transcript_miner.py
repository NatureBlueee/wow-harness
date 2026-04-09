#!/usr/bin/env python3
"""transcript_miner.py — mine tier transcript reader (ADR-043 §3.4.4).

Only activated when --tier=mine. Reads Claude Code transcript .jsonl files
from EXPLICITLY NAMED project directories (not auto-discovered).

Produces crystal-learn style proposal seeds in .wow-harness/proposals/.

Hard constraints:
  - NEVER scans ~/.claude/projects/ to discover project dirs
  - ONLY reads transcripts for projects in the named_projects list
  - Sanitizes transcript content through sanitize_patterns before output
  - Output is proposals (markdown), not direct rule/hook modifications

stdlib only per ADR-043 §7.4.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from lib import sanitize_patterns as sp  # noqa: E402

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
MAX_TRANSCRIPT_BYTES = 5 * 1024 * 1024  # 5 MB per transcript
MAX_MESSAGES_PER_TRANSCRIPT = 200


def _project_slug(project_path: str) -> str:
    """Convert project path to Claude Code's slug format (- separated)."""
    return project_path.replace("/", "-").replace(" ", "-").lstrip("-")


def _find_transcripts(named_projects: list[str]) -> list[Path]:
    """Find transcript .jsonl files for explicitly named projects only."""
    transcripts: list[Path] = []
    for project_path in named_projects:
        slug = _project_slug(project_path)
        project_dir = CLAUDE_PROJECTS_DIR / slug
        if not project_dir.is_dir():
            sys.stderr.write(
                f"[transcript_miner] No Claude projects dir for {project_path} "
                f"(expected {project_dir}), skipping\n"
            )
            continue
        for jsonl in sorted(project_dir.glob("*.jsonl")):
            if jsonl.stat().st_size <= MAX_TRANSCRIPT_BYTES:
                transcripts.append(jsonl)
    return transcripts


def _extract_user_intents(transcript_path: Path) -> list[str]:
    """Extract user messages from a transcript .jsonl, filtering noise."""
    intents: list[str] = []
    noise_prefixes = (
        "/clear", "/model", "/help", "local-command", "/compact",
    )
    try:
        with transcript_path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= MAX_MESSAGES_PER_TRANSCRIPT:
                    break
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("role") != "user":
                    continue
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    )
                content = content.strip()
                if not content or len(content) < 10:
                    continue
                if any(content.startswith(p) for p in noise_prefixes):
                    continue
                # Sanitize: strip SECRET/TRADE_SECRET content
                safe = True
                for cls in ("SECRET", "TRADE_SECRET"):
                    for pat in sp.CLASS_PATTERNS.get(cls, []):
                        if pat.search(content):
                            safe = False
                            break
                    if not safe:
                        break
                if safe:
                    intents.append(content[:500])  # cap length
    except (OSError, UnicodeDecodeError):
        pass
    return intents


def mine_transcripts(
    named_projects: list[str],
    output_dir: Path | None = None,
) -> Path | None:
    """Mine transcripts and produce a proposal seed document.

    Returns path to the generated proposal, or None if no data.
    """
    transcripts = _find_transcripts(named_projects)
    if not transcripts:
        sys.stderr.write("[transcript_miner] No transcripts found for named projects\n")
        return None

    all_intents: list[str] = []
    for t in transcripts:
        intents = _extract_user_intents(t)
        all_intents.extend(intents)

    if not all_intents:
        return None

    # Produce proposal seed
    if output_dir is None:
        output_dir = REPO_ROOT / ".wow-harness" / "proposals"
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d-%H%M%S")
    proposal_path = output_dir / f"mine-{ts}-seed.md"
    with proposal_path.open("w") as f:
        f.write(f"# Transcript Mining Seed — {ts}\n\n")
        f.write(f"Source: {len(transcripts)} transcript(s) from {len(named_projects)} project(s)\n")
        f.write(f"Intents extracted: {len(all_intents)}\n\n")
        f.write("## User Intent Patterns\n\n")
        # Group by frequency of similar intents (simple dedup)
        seen: set[str] = set()
        for intent in all_intents[:50]:  # cap output
            key = intent[:80].lower()
            if key in seen:
                continue
            seen.add(key)
            f.write(f"- {intent[:200]}\n")
        f.write("\n---\n")
        f.write("*This is a seed document for crystal-learn. It requires human review before any rules or hooks are derived from it.*\n")

    return proposal_path


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects", required=True, help="Comma-separated project paths")
    args = parser.parse_args()

    projects = [p.strip() for p in args.projects.split(",") if p.strip()]
    result = mine_transcripts(projects)
    if result:
        print(f"Proposal seed: {result}")
    else:
        print("No transcript data found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
