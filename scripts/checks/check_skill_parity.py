"""Check that home ~/.claude/skills/ copies match repo .claude/skills/ versions.

When skills are updated in the repo, the home copies can silently fall behind.
This check detects drift so the user can resync.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.checks import Finding

_HOME_SKILLS = Path.home() / ".claude" / "skills"
_REPO_SKILLS = _REPO_ROOT / ".claude" / "skills"

# Skills that should be kept in sync between repo and home.
# Extend this list for project-specific skills. The harness ships with the
# three pillars (lead / crystal-learn / guardian-fixer) plus the harness-*
# development skeleton from WP-06/07.
_SHARED_SKILLS = [
    "lead",
    "crystal-learn",
    "guardian-fixer",
    "harness-eng",
    "harness-dev",
    "harness-eng-test",
    "harness-dev-handoff",
    "harness-ops",
    "task-arch",
]


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def run(changed_files: list[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []

    for skill_name in _SHARED_SKILLS:
        repo_dir = _REPO_SKILLS / skill_name
        home_dir = _HOME_SKILLS / skill_name

        if not repo_dir.exists():
            continue

        repo_skill = repo_dir / "SKILL.md"
        if not repo_skill.exists():
            continue

        if not home_dir.exists():
            findings.append(Finding(
                severity="P1",
                message=f"Skill '{skill_name}' exists in repo but missing from ~/.claude/skills/",
                file=f".claude/skills/{skill_name}/SKILL.md",
                blocking=False,
                category="skill_parity",
                problem_class="truth_source_split",
                required_skills=["towow-ops"],
            ))
            continue

        home_skill = home_dir / "SKILL.md"
        if not home_skill.exists():
            findings.append(Finding(
                severity="P1",
                message=f"Skill '{skill_name}' home dir exists but SKILL.md missing",
                file=f".claude/skills/{skill_name}/SKILL.md",
                blocking=False,
                category="skill_parity",
                problem_class="truth_source_split",
                required_skills=["towow-ops"],
            ))
            continue

        if _file_hash(repo_skill) != _file_hash(home_skill):
            findings.append(Finding(
                severity="P1",
                message=f"Skill '{skill_name}' differs between repo and home — run: "
                        f"cp -r .claude/skills/{skill_name} ~/.claude/skills/{skill_name}",
                file=f".claude/skills/{skill_name}/SKILL.md",
                blocking=False,
                category="skill_parity",
                problem_class="truth_source_split",
                required_skills=["towow-ops"],
            ))

    return findings
