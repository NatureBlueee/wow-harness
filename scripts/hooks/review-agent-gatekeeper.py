#!/usr/bin/env python3
"""PreToolUse Task hook — physically gate review/audit subagent spawns.

[来源: ADR-038 §4 D11.2 + meta-review (memory: project_adr038_meta_review_findings.md)
       — schema-level isolation for plugin review agents that can't have their
         frontmatter modified]

Why this exists:
- ADR-038 D11 says审查 agent must use schema-level tool isolation (frontmatter
  `tools:` whitelist), not prompt-level constraint. OpenDev arXiv 2603.05344
  showed prompt约束 ~70% adherence vs schema-level 100%.
- Local review agents (.claude/agents/review-readonly.md) use frontmatter ✓
- Plugin review agents (pr-review-toolkit:*, feature-dev:*) can't have their
  frontmatter modified (they live in `.claude/plugins/`). Meta-review flagged
  this as v4's biggest unfixed gap: "形式 50%, 本意 50% — 退回到 prompt level"

What this hook does:
- Fires on PreToolUse Task
- Checks if the spawned subagent is a known review/audit type
- If yes, requires the prompt to contain the read-only directive
- If the prompt is missing the directive, BLOCKS (exit 2) with a clear error
- Writes a session marker to `.wow-harness/active-review-agents/<id>.json` so
  downstream hooks can correlate

This is gate-at-the-spawn-boundary enforcement — schema-level on the only
choke point we control for plugin agents.

Output protocol:
- exit 0: allow the spawn
- exit 2: block the spawn (CC surfaces stderr to user)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = REPO_ROOT / ".wow-harness" / "active-review-agents"

# Plugin review agents from .claude/agents/review-base.yaml application list
REVIEW_SUBAGENT_PATTERNS = (
    "pr-review-toolkit:code-reviewer",
    "pr-review-toolkit:silent-failure-hunter",
    "pr-review-toolkit:type-design-analyzer",
    "pr-review-toolkit:comment-analyzer",
    "pr-review-toolkit:pr-test-analyzer",
    "feature-dev:code-reviewer",
    "feature-dev:code-explorer",
)

# Local review agents are exempt — their frontmatter already enforces it
LOCAL_REVIEW_EXEMPT = (
    "review-readonly",
)

# The required directive — agent prompt must contain at least one of these
REQUIRED_DIRECTIVES = (
    "MUST NOT call Edit",
    "MUST NOT use Edit",
    "read-only reviewer",
    "read-only mode",
    "schema-level read-only",
    "ADR-038 D11",
)


def _is_review_subagent(subagent_type: str) -> bool:
    if not subagent_type:
        return False
    if subagent_type in LOCAL_REVIEW_EXEMPT:
        return False
    return any(subagent_type.startswith(p) or subagent_type == p for p in REVIEW_SUBAGENT_PATTERNS)


def _prompt_has_directive(prompt: str) -> bool:
    if not prompt:
        return False
    return any(d.lower() in prompt.lower() for d in REQUIRED_DIRECTIVES)


def _record_active(subagent_type: str) -> None:
    """Record an active review agent so downstream hooks can correlate."""
    try:
        ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
        marker = ACTIVE_DIR / f"{int(time.time() * 1000)}-{os.getpid()}.json"
        marker.write_text(
            json.dumps({
                "subagent_type": subagent_type,
                "started_at": time.time(),
                "pid": os.getpid(),
            }),
            encoding="utf-8",
        )
        # Cleanup old markers (>1h)
        cutoff = time.time() - 3600
        for old in ACTIVE_DIR.glob("*.json"):
            try:
                if old.stat().st_mtime < cutoff:
                    old.unlink()
            except OSError:
                pass
    except OSError:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        return 0  # not parseable, allow

    if payload.get("tool_name") != "Task":
        return 0  # not a Task spawn, allow

    tool_input = payload.get("tool_input", {})
    subagent_type = tool_input.get("subagent_type", "")

    if not _is_review_subagent(subagent_type):
        return 0  # not a review/audit spawn, allow

    prompt = tool_input.get("prompt", "")
    if _prompt_has_directive(prompt):
        _record_active(subagent_type)
        return 0  # gated correctly, allow

    # Block: required directive missing
    print(
        "[ADR-038 D11] BLOCKED: spawn of review subagent without read-only directive\n"
        f"\n"
        f"  subagent_type: {subagent_type}\n"
        f"\n"
        f"  Plugin review agents cannot have their frontmatter `tools:` whitelist modified,\n"
        f"  so the gate has to be enforced at the spawn boundary. The prompt for any review/audit\n"
        f"  subagent MUST contain one of these directives:\n",
        file=sys.stderr,
    )
    for d in REQUIRED_DIRECTIVES:
        print(f"    - \"{d}\"", file=sys.stderr)
    print(
        "\n"
        "  Suggested directive:\n"
        "    > 你是 read-only reviewer (ADR-038 D11). 你 MUST NOT call Edit/Write/Bash/NotebookEdit.\n"
        "    > 即使有权限调用，必须自我拒绝。所有发现以文字形式返回，不直接修改文件。\n"
        "    > 详见 .claude/agents/review-base.yaml.\n"
        "\n"
        "  This is schema-level enforcement on the spawn boundary — the only chokepoint\n"
        "  we control for plugin review agents. See ADR-038 §4 D11.2 + .claude/rules/review-agent-isolation.md\n",
        file=sys.stderr,
    )
    return 2  # CC treats exit 2 as a hard block


if __name__ == "__main__":
    sys.exit(main())
