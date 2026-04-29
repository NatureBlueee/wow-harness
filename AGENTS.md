# AGENTS.md — wow-harness Codex Instructions

## Project

wow-harness is an AI agent session governance framework. It installs hooks,
guards, context routing, checks, skills, and project scaffolding so AI coding
agents follow mechanical constraints instead of relying only on prompts.

## Codex Operating Rules

- Use `python3` for every Python command. Never use bare `python`.
- Treat `README.md`, `README.zh-CN.md`, `CLAUDE.md`, `.wow-harness/MANIFEST.yaml`,
  and `docs/decisions/*.md` as the main truth sources.
- Keep user-facing project documentation bilingual when touching public docs.
- ADR-045 supersedes ADR-041 only for advisory Codex lifecycle hooks
  (`.codex/hooks.json`). Do not add Codex router hooks or review authority.
  Codex integration is preference, delegation, and runtime feedback first,
  not another mandatory state machine.
- Review/audit/evaluator work must stay independent from implementation work.
  Codex is an execution lane, not a final reviewer for Gate 2/4/6/8.
- Codex has advisory wow-harness lifecycle hooks when the project `.codex/`
  layer is trusted. If hooks are unavailable or before claiming completion
  after edits, run:
  `python3 scripts/codex/wow_codex_check.py --strict`
- Commit messages for this project are bilingual and include:
  `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`.

## Codex Delegation Fit

Codex is preferred for bounded execution tasks:

- Batch string replacement and i18n extraction.
- CSS or Tailwind class cleanup that does not require visual taste calls.
- Pure technical refactors such as renaming, dead-code removal, type fixes, and
  small performance cleanups.
- Adding tests inside an existing test framework.
- Documentation updates, shell scripts, and CI guard scripts.

## Codex Red Lines

Do not route these to Codex without explicit human direction:

- Frontend React component structure, interaction logic, new pages, or new
  user-facing features.
- Cross-module data-flow changes that pass through frontend, API, persistence,
  or deployment boundaries.
- Aesthetic decisions, product voice decisions, or any `nature-designer` flow.

## Verification

Prefer local, mechanical verification before claiming completion:

- `PYTHONPYCACHEPREFIX=/tmp/wow-harness-pycache python3 -m compileall -q scripts`
- `python3 scripts/codex/wow_codex_check.py --strict`
- `bash scripts/ci/count-components.sh`
- `python3 scripts/ci/scan_verify_artifacts.py --claims`
- `python3 scripts/ci/detect_rebaseline_triggers.py`
