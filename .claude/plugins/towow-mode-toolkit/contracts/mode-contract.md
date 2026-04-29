# Towow vNext Mode Contract

> Companion to `../03-design.md` §7. Addresses Phase 1 §6.3 (mode collapse — brainstorm / build / verify / release not first-class). Grounded in Phase 2 §1.1 (CC Plan Mode), §3.2 (Cursor checkpoints), §3.7 synthesis ("mode is runtime state, not prose").

The mode is **the** runtime state variable. It lives at `.towow/state/mode` as a single word. Every hook, every capability check, and every review binding reads that file to decide what is allowed.

## Four modes

| Mode | Purpose | Tool profile | Allowed transitions |
|---|---|---|---|
| `plan` | brainstorm, explore, write a plan, ask clarifying questions | read-only: Read, Glob, Grep, Bash(git log:\*), WebFetch, WebSearch, AskUserQuestion | → build |
| `build` | make code changes against an approved plan | Read + Write + Edit + Bash(scoped) | → verify, ← plan |
| `verify` | run tests, inspect diffs, accumulate evidence, no new edits | Read + Bash(test:\*) + Bash(git diff:\*) | → release, ← build |
| `release` | commit / push / deploy / retire assets | Write + Bash(git commit:\*) + Bash(git push:\*) + Bash(deploy:\*) | → plan (new run) |

Mode is set by: (1) explicit user command (`/mode build`), (2) plan-approval gate (plan → build), (3) verify-gate pass (verify → release), or (4) auto-reset to `plan` after release. **No prompt text ever sets mode.**

## Default value when absent

If `.towow/state/mode` does not exist when the router reads it, the router treats the mode as `legacy` (pass-through) and lazily creates the file with content `legacy`. The default is enforced at read time; no runtime state file is ever committed.

## Per-mode capability profile

Each mode maps to a tool allowlist and a review binding. `capability-router.py` (see `../hooks/capability-router.py`) reads `.towow/state/mode` on every `PreToolUse` and denies tool calls that do not fit the current mode's profile.

### `plan`

- **Permits:** Read, Glob, Grep, WebFetch, WebSearch, AskUserQuestion, Bash(git log:\*), Bash(git status), Bash(git diff:\*)
- **Denies:** Edit, Write, Bash(git commit:\*), Bash(git push:\*), Bash(rm:\*), Bash(deploy:\*), Edit-like MCP tools, SendMessage to execution agents
- **Emits:** on transition out of plan, one evidence packet (`kind: gate`) with the plan file's sha256 and the human approver's id
- **Typical duration:** minutes to hours
- **Compact behavior:** tiny kernel reload; plan file itself is the resume pointer

### `build`

- **Permits:** plan's permissions + Edit, Write, Bash(pytest:\*), Bash(npm test:\*), Bash(cargo check:\*), subagent spawn (executor)
- **Denies:** Bash(git push:\*), Bash(git commit:\*) (commits happen at release), Bash(deploy:\*), Bash(rm:\*) unless path in `/tmp/`, SendMessage outside run
- **Emits:** per-edit step evidence (`kind: step`); at transition to verify, one gate packet
- **Typical duration:** hours
- **Compact behavior:** kernel + pointer to current run.json; evidence files are the durable state

### `verify`

- **Permits:** Read, Glob, Grep, Bash(git diff:\*), Bash(test:\*), reviewer subagent spawn
- **Denies:** Edit, Write, Bash(git commit:\*), Bash(git push:\*), Bash(deploy:\*)
- **Emits:** one `merge_ready` packet at transition to release
- **Typical duration:** minutes
- **Compact behavior:** verify should not outlast a single compact window; if it does, the verify run aborts and re-starts from the last gate packet

### `release`

- **Permits:** Bash(git commit:\*), Bash(git push:\*), Bash(deploy:\*), asset retirement via `/retire` command
- **Denies:** Edit (code changes) — if a change is needed, mode must return to `build`
- **Emits:** release-level evidence packet with commit sha and (if applicable) deploy id
- **Typical duration:** minutes
- **Compact behavior:** out of scope; release does not survive compact — it either completes or aborts

## Transition gates

| From | To | Gate |
|---|---|---|
| plan | build | human approval of plan file (design-review binding in `review-contract.yaml`) |
| build | verify | gate packet exists and passes `verify-gate.py` schema check |
| verify | release | `merge_ready` packet exists, CI green, all UNKNOWNs resolved or explicitly deferred |
| release | plan | automatic on release success; new run.json is created |
| any | plan | allowed (abort current run — produces an abort packet with reason) |

## What mode is **not**

- Mode is not a prompt string. CLAUDE.md-vnext does not describe modes — it points the model at `.towow/state/mode` and the router hook does the rest.
- Mode is not a skill. `lead` skill's 0–8 gate state machine (Phase 1 §3.4) is an example of mode-as-prose; it is **retired** (see `../03-design.md` §12 matrix).
- Mode is not per-subagent. Subagents inherit the parent run's mode; a subagent cannot self-elevate.
- Mode is not per-team. Parallel runs each have their own `.towow/state/<run-id>/mode` file.

## Multi-task parallelism under the mode model

The brief requires parallel-multitask support. The mode contract supports parallelism with one rule:

> **Parallel runs share nothing except the repo.** Each parallel run gets a unique run_id, its own `.towow/state/<run-id>/mode`, its own evidence tree, and its own subagent context. Mode is per-run, not global.

Two builds can run simultaneously on disjoint file paths. If they intersect, the second run's `PreToolUse` on a conflicting path is denied by `capability-router.py` reading a file-lock table at `.towow/state/locks.json`. No prompt-level "don't step on each other" rule.

## What the human sees

The mode name is rendered in the session status line by a SessionStart hook. Nothing else needs to remind the model — the router and the verify-gate do.
