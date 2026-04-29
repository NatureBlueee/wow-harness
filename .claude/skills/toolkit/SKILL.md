---
name: toolkit
description: Pull-surface slash command for `.towow/` tooling that is not auto-triggered. Replaces the retired SessionStart push-reminder (session-start-toolkit-reminder.py, retired in WP-031). Reads `.towow/toolkit-index.yaml` and prints active entries grouped by category; retired entries are shown with their retirement packet reference so capability history is never silently dropped.
status: active
tier: usability
owner: nature
window_owner: shared
window_owner_since: 2026-04-28T17:00+08:00
window_owner_adr: docs/decisions/ADR-H2-identity-isolation.md
last_audited: 2026-04-19
---

# /toolkit — harness toolkit index

## What this does

Prints the contents of `.towow/toolkit-index.yaml` in a human-readable layout. The index lists
`.towow/` tooling that users occasionally need but is NOT auto-triggered by any hook — for
example: trace-analyzer proposals, magic-doc rebuild, doc-freshness scan, metrics inspection.

This is a **pull surface**, not a push notification. The predecessor hook
`session-start-toolkit-reminder.py` injected the same content every ~3 hours whether the user
wanted it or not; that push channel was retired in WP-031 and replaced by this on-demand
readout. Discoverability is preserved (the kernel CLAUDE.md points at `/toolkit`); context
pollution is eliminated (zero bytes cost until the user invokes).

## Sub-commands

| Command | Behavior |
|---|---|
| `/toolkit` | List all active entries grouped by category; show retired entries with their retirement packet reference at the bottom. |
| `/toolkit all` | Same as above but without the retired/active split — single chronological list. |

## Invocation handler

The handler is `list.sh`. It reads `.towow/toolkit-index.yaml` via `python3 -c "import yaml;
..."` (PyYAML is available; used elsewhere in the harness), formats entries, and prints to
stdout. No network, no side effects. Exit 0 on success, 1 on missing index, 2 on yaml parse
error.

## Why this exists (WP-031 context)

Retiring `session-start-toolkit-reminder.py` without providing a pull channel would leave a
silent regression for:

1. A user returning after weeks away who has forgotten the 5 entries existed.
2. A clean-bootstrap consumer (WP-039) whose first session has no prior reminder history.
3. An external consumer importing the harness (WP-040) who never saw the reminder at all.

`/toolkit` is the minimal pull-side substitute. The invariant is: every capability listed in
the retired hook is either (a) surfaced here, or (b) retired with a retirement packet
referenced in the index entry — no capability becomes undiscoverable.

## Amendment

When a new `.towow/` pull-tool ships or an existing one retires, update
`.towow/toolkit-index.yaml`. Do NOT edit this skill to describe specific entries — the skill
is a renderer, the yaml is the data.
