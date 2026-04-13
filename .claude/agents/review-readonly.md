---
name: review-readonly
description: >
  Read-only review agent — schema-level tool isolation per ADR-038 D11.1.
  Use as the base definition for any local review, audit, or gate-keeper agent.
  Cannot call Edit, Write, Bash, or NotebookEdit.
tools:
  - Read
  - Glob
  - Grep
  - WebFetch
---

# review-readonly — Reference Implementation (ADR-038 D11.1)

This is the **reference implementation** for local review agent schema-level tool
isolation. Referenced by `.claude/rules/review-agent-isolation.md`.

## What this is

A Claude Code local agent definition whose `tools:` frontmatter physically excludes
write tools. The agent *cannot* call `Edit`, `Write`, `Bash`, or `NotebookEdit` —
they are not in its tool manifest.

This is D11.1 of ADR-038. D11.2 (plugin review agents) is enforced separately via
`scripts/hooks/review-agent-gatekeeper.py`.

## Why schema-level matters

| Enforcement method | Adherence |
|-------------------|-----------|
| Prompt constraint ("do not modify files") | ~70% |
| Schema-level exclusion (tool not in `tools:`) | 100% |

Source: OpenDev arXiv:2603.05344 — Plan mode planner schema-level read-only exclusion.

## How to create a project-specific review agent

Create a new file in `.claude/agents/` with the same `tools:` whitelist:

```markdown
---
name: gate-2-reviewer
description: Gate 2 architecture reviewer. Read-only.
tools:
  - Read
  - Glob
  - Grep
  - WebFetch
---

# Gate 2 Architecture Reviewer

[Your review instructions here — the agent physically cannot write files.]
```

## What NOT to add

Do not add `Edit`, `Write`, `Bash`, or `NotebookEdit` to any review agent's `tools:`
list without a documented deviation reason (see `review-agent-isolation.md` §"例外申请").