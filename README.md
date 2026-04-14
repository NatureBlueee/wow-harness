[中文](README.zh-CN.md) | English

# wow-harness

> "How do you let AI handle so much development with so little supervision?"

This is the answer.

wow-harness is a governance layer for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). It makes AI agents reliable enough that you can set direction, walk away, and trust the work actually lands — with review gates, completion verification, and mechanical enforcement that no amount of prompting can replicate.

## The Problem

Claude Code is remarkably capable. But left unsupervised, it has structural biases:

- **Claims completion prematurely** — "all tests pass" (didn't run them)
- **Skips review** — "this change is simple enough" (it wasn't)
- **Drifts from plans** — starts fixing one bug, ends up refactoring three files
- **Self-evaluation bias** — asks itself "did I do a good job?", answers "yes"

You end up supervising more than you saved in development time. The 80% it does well makes the 20% it silently drops even harder to catch.

## The Insight

```
CLAUDE.md instruction compliance:  ~20%
PreToolUse hook enforcement:       100%
```

Instructions don't reliably change AI behavior. Mechanical constraints do.

A review agent told "don't modify files" obeys ~70% of the time. A review agent whose tool manifest doesn't list Edit/Write obeys 100% of the time — it physically can't call what isn't there.

wow-harness applies this principle everywhere: if it matters, enforce it with a hook, not a sentence.

## What Changes

| Without wow-harness | With wow-harness |
|---|---|
| "Did you run the tests?" → "Yes" (didn't) | Mechanical gate checks `progress.json` — can't fake evidence |
| AI stops mid-chat, injects completion checklist | Stop hook parses session transcript — only triggers when uncommitted writes exist |
| Review agent "helpfully" edits what it reviews | Review agent physically cannot call Edit/Write (schema-level isolation) |
| "This PR is simple, let's skip review" | Gates 2/4/6/8 mechanically require independent review — no exceptions |
| Parallel AI sessions contaminate each other | Each session's scope is isolated via its own transcript file |
| Agent drifts into unrelated fixes | Context routing injects domain-specific rules only for files being edited |

## How It Works

### Hooks: enforcement at the moment of action

16 hooks across 7 lifecycle stages. They intercept *as things happen*, not after:

```
SessionStart  →  Load context, reset risk state, surface tools
PreToolUse    →  Block unsafe deploys, gate review agents, sanitize reads
PostToolUse   →  Route context on edit, detect loops, track risk
Stop          →  Verify completion candidate exists (transcript × git diff)
SessionEnd    →  Reflect, analyze traces, persist progress
```

### The 8-Gate State Machine

Every significant change flows through gates. Even-numbered gates require independent review — not the same agent checking its own work:

```
G0 Problem  →  G1 Design  →  G2 Review*
  →  G3 Plan  →  G4 Review+Lock*
  →  G5 Tasks  →  G6 Review*
  →  G7 Execute+Log  →  G8 Final Review*

* = Independent reviewer (separate context, read-only tools)
```

### Automated Checks

15 validators run on file changes: API type consistency, doc freshness, security patterns, fragment integrity, hook registration, and more. They catch drift before it compounds.

### Skills

16 specialized behaviors — from architecture design (`arch`) to failure pattern extraction (`crystal-learn`) to structured bug triage (`bug-triage`). Skills install judgment frameworks, not rule lists, so the agent can navigate situations the skill didn't explicitly cover.

Each skill has `{{PLACEHOLDER}}` structural slots designed to be filled with your project's context during installation.

## Install

**Prerequisites:** generate an install key before running the installer:

```bash
export WOW_HARNESS_INSTALL_HMAC_KEY=$(openssl rand -hex 32)
```

Then clone and run:

```bash
git clone https://github.com/NatureBlueee/wow-harness.git
cd /path/to/your/project
python3 /path/to/wow-harness/scripts/install/phase2_auto.py --auto --tier drop-in --scope current
```

### Three Tiers

| Tier | Trust level | What happens |
|------|-------------|-------------|
| **drop-in** | Minimal | Installs hooks + skills as-is. Try it, see what happens. |
| **adapt** | Medium | Reads your README + docs, customizes skills to your project. |
| **mine** | Full | Reads your work transcripts, deeply adapts to your patterns. |

### What Gets Installed

```
your-project/
├── .claude/
│   ├── settings.json    # Hook registrations (appends, won't clobber)
│   ├── skills/          # 16 agent behavior definitions
│   └── rules/           # Path-scoped context (auto-loaded by file path)
├── scripts/
│   ├── hooks/           # 16 lifecycle hooks
│   └── checks/          # 15 automated validators
└── CLAUDE.md            # Governance guide (generated, yours to edit)
```

The installer is idempotent — run it twice, get the same result.

## Design Principles

1. **Hooks over instructions** — If compliance matters, don't ask. Enforce.
2. **Schema-level isolation** — Review agents' tool manifests exclude write tools. Not "please don't" — *can't*.
3. **Fail-open where safe** — A hook that can't read its data injects *more* checks, not fewer. The failure mode is always "too cautious," never "silently skipped."
4. **Session isolation** — Completion detection uses per-session transcript parsing. No shared mutable state between parallel sessions.
5. **Structural slots over blank space** — Project-specific content becomes `{{PLACEHOLDER}}` with meta-instructions (what to put, why it matters, how to discover it), not empty fields you forget to fill.

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- Python 3.9+
- Git
- `WOW_HARNESS_INSTALL_HMAC_KEY` environment variable (generate with `openssl rand -hex 32`)

## Origin

Born from 6 months of production use on [Towow](https://towow.net), an agent collaboration protocol. The governance layer kept proving independently valuable — every AI-assisted project needs it, not just ours. So we extracted it.

The hooks, gates, and isolation patterns were designed by getting burned first, then building the guard. Every rule in this system exists because an AI agent found a creative way to not follow the previous rule.

## License

MIT
