---
name: mode
description: Flip the Towow vNext run mode (`.towow/state/mode`) with transition-gate checks. Provides `/mode plan`, `/mode build`, `/mode verify`, `/mode release`. Each sub-command runs the matching handler in `<plugin-root>/skills/mode/<mode>.sh`; the handler calls `transition.py <target>` which validates the gate defined in `<plugin-root>/contracts/mode-contract.md` §4 and, if it passes, writes the new mode value. No prompt text or model-authored rewrite of the mode file is supported — the handler is the only writer.
status: active
tier: infrastructure
owner: nature
last_audited: 2026-04-16
---

# /mode — runtime mode control

## What this does

The mode is **the** runtime state variable (`<plugin-root>/contracts/mode-contract.md`).
It lives at `.towow/state/mode` as a single word. `<plugin-root>/hooks/capability-router.py` reads
that file on every `PreToolUse` to decide what's allowed. This skill is the user-controlled write
path for that file. Direct editing is not supported; gates would be bypassed.

## Sub-commands

| Command | Target mode | Gate (checked before writing `mode` file) |
|---|---|---|
| `/mode plan` | `plan` | always allowed (per mode-contract §4 row `any → plan`, abort-current-run). Abort-packet emission when leaving a non-`plan`, non-`legacy` mode is deferred to `evidence-emit.py` (WP-022). |
| `/mode build` | `build` | a plan file exists at `.towow/plan/current.md`. (Full approval binding via `review-contract.yaml` lands in Phase E; until then the gate is plan-file presence.) |
| `/mode verify` | `verify` | a build-mode `kind=gate` evidence packet exists under `.towow/evidence/<run_id>/` and validates against the evidence-packet schema (WP-029 canonicalization — no more `.towow/evidence/gates/build-to-verify.json` lookup). |
| `/mode release` | `release` | contract-driven orchestrator. Reads every active binding in `review-contract.yaml` with `applies_when.transition_target == "release"` and checks its declared evidence-packet kind under `.towow/evidence/<run_id>/`. If a `subagent`-type binding lacks its packet, `transition.py` exits **3** and emits a structured `spawn_reviewer` directive on stderr — the host CC session is expected to spawn the named subagent with the declared tool whitelist, have it emit the packet, and re-run `/mode release`. If a `human`/`pane`-type binding lacks its packet, the transition is denied (exit 1); those reviewer types do not auto-spawn. |
| `/mode shadow-review` | *(no mode flip)* | force-emit `.towow/metrics/shadow-ready.json` with `saturation_signal: "manual_override"`; still enforces the hard lower bound (>= 2 non-legacy modes observed). WP-016 exit signal; see `docs/decisions/decision-shadow-router-saturation-2026-04-16.md`. |

Reverse transitions:
- `build → plan` and `verify → build` are allowed (per contract §4 "allowed transitions" column) and go through the same `/mode plan` or `/mode build` invocation.
- `release → plan` is automatic on release success in a later WP; users can also invoke `/mode plan` to abort.

## How to invoke

When the user types `/mode <target>`:

1. Look up `<target>` in the table above.
2. Run the matching handler shell script: `bash <plugin-root>/skills/mode/<target>.sh`. The handler is a one-liner that invokes `transition.py`.
3. The script prints the outcome and exits `0` on success. Exit codes:
   - `0` — transition applied (or no-op).
   - `1` — gate denied (missing/invalid packet, blocker, or missing plan/run). Report stderr verbatim to the user.
   - `2` — fail-closed (contract YAML unreadable, PyYAML missing, or usage error). Report stderr verbatim; do NOT retry silently.
   - `3` — **spawn-reviewer directive** on stderr (only from `/mode release` when a `subagent`-type binding lacks its packet). The host CC session must parse the JSON directive from stderr (last line), spawn the named subagent with the declared tool whitelist, have it emit the evidence packet, then re-run `/mode release`. Do NOT write the mode file manually.

Do not write `.towow/state/mode` by any other means.

## Non-goals

- **No enforcement change.** WP-016 runs the router in shadow mode (`SHADOW=1`): every would-deny / would-defer is logged to `.towow/metrics/router-shadow.jsonl` and still allowed through. Enforcement per mode flips one mode at a time in WP-017..WP-020. This `/mode` skill only writes the mode file; it does not alter router rules.
- **No evidence-packet schema validation.** Handler checks file presence only. Schema enforcement is WP-023 (verify-gate.py).
- **No multi-run support.** A future WP introduces `.towow/state/<run-id>/mode` per mode-contract §6; this skill writes the single-run path only.

## Rollback

`git rm -r <plugin-root>/skills/mode/` (see WP-015 rollback in `07-migration-backlog.md`; plugin-ified in WP-038).
