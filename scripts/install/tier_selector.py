#!/usr/bin/env python3
"""tier_selector.py — install tier policy resolver (ADR-043 §3.4.4).

Parses --tier={drop-in,adapt,mine} and produces a TierPolicy dataclass
that phase2_auto.py consumes to enforce read/write boundaries.

Three tiers:
  drop-in:  Bundle files only. No project doc reading. No transcript mining.
  adapt:    Reads README.md + docs/**/*.md (50KB cap). No transcripts.
  mine:     adapt + reads transcripts from explicitly named projects only.

All tiers run the same Gate 0→8 fail-closed flow. Tier only controls
input scope and write scope, never review bypass.

stdlib only per ADR-043 §7.4.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

VALID_TIERS = ("drop-in", "adapt", "mine")
DEFAULT_TIER = "adapt"
DOC_READ_LIMIT_BYTES = 50 * 1024  # 50 KB per ADR-043 §3.3 line 284


@dataclass
class TierPolicy:
    """Resolved install tier policy."""
    tier: str
    can_read_project_docs: bool = False
    can_read_transcripts: bool = False
    can_spawn_reflection: bool = False
    doc_read_limit_bytes: int = DOC_READ_LIMIT_BYTES
    named_projects: list[str] = field(default_factory=list)

    def validate_read(self, path: Path, repo_root: Path) -> bool:
        """Check if a file read is allowed under this tier."""
        str_path = str(path.resolve())
        str_root = str(repo_root.resolve())

        # Transcript detection (both inside and outside repo)
        if ".claude/projects/" in str_path and str_path.endswith(".jsonl"):
            if not self.can_read_transcripts:
                return False
            # mine: must be from a named project
            if self.named_projects:
                return any(
                    str_path.startswith(str(Path(p).resolve()))
                    for p in self.named_projects
                )
            return self.can_read_transcripts

        # Bundle files always readable
        if str_path.startswith(str_root):
            if not self.can_read_project_docs:
                # drop-in: only bundle dirs
                rel = path.resolve().relative_to(repo_root.resolve())
                parts = rel.parts
                if parts and parts[0] in (".wow-harness", ".claude", "scripts", "schemas"):
                    return True
                return False
            return True

        return False


def resolve_tier(tier_str: str | None, projects: list[str] | None = None) -> TierPolicy:
    """Resolve a tier string into a TierPolicy.

    Args:
        tier_str: One of 'drop-in', 'adapt', 'mine', or None (=default).
        projects: List of project paths (required for 'mine').

    Returns:
        TierPolicy with all boundaries set.

    Raises:
        SystemExit(2) if tier is invalid or mine without projects.
    """
    tier = tier_str or DEFAULT_TIER
    if tier not in VALID_TIERS:
        print(
            f"Unknown tier '{tier}'. Valid: {', '.join(VALID_TIERS)}",
            file=sys.stderr,
        )
        sys.exit(2)

    projects = projects or []

    if tier == "drop-in":
        return TierPolicy(
            tier="drop-in",
            can_read_project_docs=False,
            can_read_transcripts=False,
            can_spawn_reflection=False,
            named_projects=[],
        )

    if tier == "adapt":
        return TierPolicy(
            tier="adapt",
            can_read_project_docs=True,
            can_read_transcripts=False,
            can_spawn_reflection=True,
            named_projects=[],
        )

    # tier == "mine"
    if not projects:
        print(
            "ERROR: --tier=mine requires --projects=<p1>,<p2>,... "
            "(mine + global forbidden — fail-closed per ADR-043 §3.4.5)",
            file=sys.stderr,
        )
        sys.exit(2)

    return TierPolicy(
        tier="mine",
        can_read_project_docs=True,
        can_read_transcripts=True,
        can_spawn_reflection=True,
        named_projects=list(projects),
    )


def main() -> int:
    """CLI entry for testing."""
    import argparse
    parser = argparse.ArgumentParser(description="Resolve install tier policy")
    parser.add_argument("--tier", default=DEFAULT_TIER, choices=VALID_TIERS)
    parser.add_argument("--projects", default="", help="Comma-separated project paths")
    args = parser.parse_args()

    projects = [p.strip() for p in args.projects.split(",") if p.strip()] if args.projects else []
    policy = resolve_tier(args.tier, projects)
    print(f"tier={policy.tier}")
    print(f"can_read_project_docs={policy.can_read_project_docs}")
    print(f"can_read_transcripts={policy.can_read_transcripts}")
    print(f"can_spawn_reflection={policy.can_spawn_reflection}")
    print(f"named_projects={policy.named_projects}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
