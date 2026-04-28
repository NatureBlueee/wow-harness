---
name: codex-dev
description: Delegate bounded implementation work to Codex when the task is execution-heavy and does not require independent review judgment.
tools: Read, Grep, Glob, Bash, Edit, MultiEdit, Write
---

# codex-dev

Use this agent for bounded implementation work that can be specified with clear
inputs, expected outputs, and verification commands.

## Red Lines

Do not use `codex-dev` for these without explicit human approval:

1. Frontend React component structure, interaction logic, new pages, or new
   user-facing features.
2. Cross-module data-flow changes that pass through frontend, API, persistence,
   or deployment boundaries.
3. Aesthetic decisions, product voice decisions, or any `nature-designer` flow.

## Good Fits

- Batch replacements, i18n extraction, and mechanical doc updates.
- CSS/Tailwind cleanup that does not require visual judgment.
- Pure technical refactors: naming, dead code, typing, local performance cleanup.
- Adding tests within an existing framework.
- Small scripts and CI checks with clear input/output contracts.

## Required Prompt Shape

When delegating to `codex-dev`, include:

- The exact files or directories it owns.
- The expected behavioral outcome.
- The verification command it must run.
- A reminder not to revert edits made by other agents or the user.

## Boundary

Codex is an execution lane. It must not be used as the independent reviewer for
Gate 2/4/6/8. Review remains a separate judgment role.
