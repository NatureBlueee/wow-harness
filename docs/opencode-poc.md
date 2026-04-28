# OpenCode Compatibility PoC

This repository now includes an **experimental OpenCode compatibility layer**.

The goal is not to claim full parity with the Claude Code runtime. The goal is to prove that the wow-harness governance model can be ported onto another agent runtime with:

- tool lifecycle interception
- session lifecycle events
- compaction context injection
- read-only reviewer isolation

## Why OpenCode

OpenCode exposes the primitives that wow-harness needs most:

- plugins loaded from `.opencode/plugins/`
- tool hooks: `tool.execute.before`, `tool.execute.after`
- session events such as `session.created`, `session.idle`, `session.compacted`
- compaction hook: `experimental.session.compacting`
- project-level agents in `.opencode/agents/`
- per-agent permissions in `opencode.json`

This makes it a strong candidate for proving that wow-harness is a reusable governance layer, not just a Claude Code add-on.

## What this PoC implements

### 1. Runtime bootstrap plugin

File: `.opencode/plugins/wow-harness-runtime.js`

Current behavior:

- ensures runtime directories exist for both:
  - canonical: `.wow-harness/state/*`
  - legacy mirror: `.towow/*`
- resets `risk-snapshot.json` on `session.created`
- blocks `.env` reads through `tool.execute.before`
- updates `risk-snapshot.json` after `edit` / `write`
- appends lightweight session and guard metrics JSONL files
- injects wow-harness continuation reminders into compaction
- **stop hook** (`stop`): generates `completion-proposal.json`, blocks completion when:
  - high risk level (R3/R4) detected
  - progress not marked as done
  - uses `client.session.prompt` to re-enter loop with blocking reasons

### 2. Read-only reviewer agent

File: `.opencode/agents/wow-reviewer.md`

This agent is designed to mimic wow-harness independent review behavior:

- no edit access
- no webfetch access
- bash restricted to read-only repo inspection commands

### 3. Project-level OpenCode config

File: `opencode.json`

Current behavior:

- `build` may call `general`, `explore`, and ask before invoking `wow-reviewer`
- `plan` is explicitly restricted to non-editing, inspection-oriented bash commands

## What is intentionally not implemented yet

This PoC does **not** yet provide full parity for:

- ~~stop-hook completion gating equivalent to `stop-evaluator.py`~~ ✅ implemented
- transcript-aware completion proposal generation
- review-agent active marker tracking
- deploy guard parity
- full context-router / guard-router injection logic
- installer support for `.opencode/*`

## Suggested next steps

1. ~~Add stop/completion interception parity~~ ✅ done
2. Move runtime path handling into a shared helper so Claude/Cursor/OpenCode do not duplicate state path logic.
3. Add installer support that can optionally scaffold:
   - `.opencode/plugins/`
   - `.opencode/agents/`
   - `opencode.json`
4. Add smoke tests that simulate:
   - `session.created`
   - `tool.execute.before` on `.env`
   - `tool.execute.after` on `edit`
   - compaction context injection
   - `stop` hook generating completion proposal and blocking incomplete work

## Manual usage

From the repository root:

```bash
opencode .
```

OpenCode should automatically load:

- `opencode.json`
- `.opencode/plugins/wow-harness-runtime.js`
- `.opencode/agents/wow-reviewer.md`

Then:

1. use the default `build` agent for coding
2. use `@wow-reviewer` for independent review
3. inspect `.wow-harness/state/` to confirm runtime artifacts are written
