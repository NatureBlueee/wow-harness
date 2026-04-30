#!/usr/bin/env python3
# Towow vNext — PreToolUse hook: capability-router.
#
# Routes tool calls by the current run's mode. The mode file (.towow/state/mode) is the single
# runtime source of truth. No prompt text governs what tools are available; this hook does.
#
# Addresses Phase 1 §6.3 (mode collapse), §3.1 (CLAUDE.md overloaded constitution), §3.2 (six
# unfielded agents inherit everything). Grounded in Phase 2 §1.3 (hooks deny/defer/ask/allow),
# §2.1 (Codex sandboxing as the reference capability-layer model).
#
# Decision precedence at PreToolUse: deny > defer > ask > allow. This hook emits the lowest
# precedence result that fits. "defer" is used instead of "deny" whenever a mode transition would
# legitimately unblock the call — so the model gets a recoverable signal.
#
# WP-014 install-mode semantics:
#   - Default mode is `legacy`, which allows every tool (full pass-through). Installing the router
#     in `legacy` is a no-behavior-change step; enforcement is added by later WPs flipping the mode.
#   - The router lazily creates `.towow/state/mode` = `legacy` on first call if missing, and also
#     lazily seeds `.towow/state/run.json` and `.towow/state/locks.json` as empty JSON objects.
#     `.towow/state/*` is .gitignored (with `.gitkeep` preserved), so these writes never appear in
#     `git status` as tracked changes.
#
# WP-016 shadow-run semantics:
#   - When the environment variable SHADOW=1 is set, any `deny` or `defer` decision is downgraded
#     to `allow` at the decision boundary, and the *would-have* outcome is appended as one JSON
#     line to `.towow/metrics/router-shadow.jsonl` (schema: §1.4.1 canonical 9-field form; runtime
#     rows are tagged `source: "canary"`). `.towow/metrics/` is .gitignored, so the log never
#     dirties the working tree.
#   - The blocking WP-016 exit gate is the §1.4 synthetic-probe evidence triple under
#     `.towow/evidence/wp-016/` (router-shadow.jsonl with `source: "probe"`, coverage-summary.json
#     with every ratio == 1.0, shadow-ready.json countersigned by a human reviewer). Probes are
#     produced deterministically by `scripts/probes/router/probe.py`; coverage + gate signal by
#     `scripts/probes/router/coverage.py`. See docs/decisions/decision-shadow-router-synthetic-
#     probe-2026-04-16.md.
#   - Real-world / canary observation (via `shadow-saturation.py` + the runtime SHADOW=1 log) is
#     optional, non-blocking post-gate signal per 10-execution-controller.md §1.4; does NOT block
#     WP-017.
#   - Shadow mode is the default during WP-016; WP-017+ flip SHADOW off for one mode at a time.
#     Unsetting SHADOW=1 restores full enforcement.
#
# WP-017 rewrite (CC-schema-compliant output; replaces failed 0eedbd0c):
#   - Every router exit site converts from the internal {decision: allow|deny|defer} to CC's
#     hookSpecificOutput form per cc_mapping_contract (11-execution-state.json →
#     accepted_planning_patches[0]):
#       internal allow → permissionDecision: allow
#       internal deny  → permissionDecision: deny
#       internal defer → permissionDecision: deny + mode-switch hint (interactive, default)
#                        permissionDecision: ask (non-interactive, TOWOW_NONINTERACTIVE=1)
#   - Legacy {decision: approve|block} form is NOT used (no ask path, weaker reason passthrough).
#   - ENFORCED_MODES: set of modes graduated out of shadow. When mode in ENFORCED_MODES, the
#     SHADOW=1 downgrade is bypassed and the CC-mapped deny/ask flows through to the caller.
#     WP-017 adds "plan"; WP-018/019/020 extend one mode at a time.
#   - Concept informed by 0eedbd0c but implemented fresh (not transplanted).
#
# WP-018 extension (build-mode enforcement + finding WP-017-AXIS-3-F-001 remediation):
#   - ENFORCED_MODES += "build". In build mode, SHADOW=1's deny/ask→allow downgrade is bypassed;
#     RULES strictly apply via cc_mapping_contract.
#   - Finding WP-017-AXIS-3-F-001 (axis-3, medium, non-blocking for WP-017 exit): the `plan` mode
#     ruleset did not whitelist the mode-transition handlers, so an agent in plan mode could not
#     self-advance to build via `bash .claude/skills/mode/build.sh` or
#     `python3 .claude/skills/mode/transition.py build`. Only a human slash-command could unlock
#     it. That is a capability gap, not a deliberate write-freeze — plan→build is a legitimate
#     allowed transition per mode-contract §4.
#     Remediation (option a from runtime-signoff.json): add narrow bash globs for the mode skill
#     handlers to both plan.bash_allow AND build.bash_allow (symmetric, so any enforced mode can
#     transition to any other enforced mode). Rationale for option a over option b (adding
#     `Skill` to plan.allow): option a keeps the surface minimal — only the exact handler paths
#     — and preserves plan's write-freeze posture on every other Bash command.
#   - deploy-guard.py: referenced by the WP-018 backlog special note, but NOT present in this
#     chain's scripts/hooks/ directory. No double-denial concern exists today. If a future WP
#     reintroduces deploy-guard.py, hook ordering between router and deploy-guard should be
#     validated via a follow-up planning patch (per backlog special note) — do NOT reshuffle
#     hook order from inside a mode-enforcement WP.
#
# WP-018a extension (RULES table gains target-path scoping; carry-in from WP-018 axis-3):
#   - RULES schema gains a new optional field per mode: `write_path_allow: list[str] | None`.
#     When set, Write/Edit target paths (tool_input["file_path"]) are matched against the
#     list using fnmatch.fnmatchcase; on match → allow; on no-match → deny with a
#     write-path-deny rule identity. When `write_path_allow` is absent or None, the field is
#     not consulted (preserves today's tool-name-only semantics for modes that don't opt in).
#   - decide() is extended so that for tool in {"Write", "Edit"} AND `tool in rule["allow"]`
#     AND `rule.get("write_path_allow") is not None`, the target path is consulted before
#     returning allow. If it is outside the allowed glob set, the result is a terminal deny
#     (no cross-mode path-defer — the agent reads the reason string and switches mode itself;
#     adding cross-mode path-defer adds complexity for marginal UX gain).
#   - Per-mode `write_path_allow` populated per WP-018a scope:
#       plan:    [".towow/plan/**", "docs/plans/**", "docs/decisions/**"]
#       build:   ["**"]  — explicit broad; preserves today's behavior, makes scope visible
#       verify:  [".towow/evidence/**", "docs/reports/**"]
#       release: [".towow/release/**", "CHANGELOG.md", "VERSION"]
#       legacy:  not set — pass-through already handles via rule["allow"] == "*"
#   - plan.allow / verify.allow / release.allow gain Write + Edit (gated by write_path_allow).
#     build.allow already has them; its write_path_allow = ["**"] is a no-op at runtime but
#     makes the "build can write anywhere" decision visible (so future narrowing is a RULES
#     edit, not a schema migration).
#   - verify.bash_allow / release.bash_allow gain the `bash .claude/skills/mode/*` and
#     `python3 .claude/skills/mode/transition.py*` pair (findings WP-018-AXIS-3-SIB-003/004 —
#     symmetric to the plan/build remediation landed in WP-018).
#   - release.allow no longer contains the dead `"Bash"` entry (finding WP-018-AXIS-3-SIB-005).
#     decide() special-cases Bash via bash_allow; the dead entry never influenced runtime.
#   - Bash path-target analysis is explicitly OUT OF SCOPE for this pass. A Bash command that
#     writes to a file (via `>`, `>>`, `tee`, `cp`, `mv`, `dd`, etc.) is NOT checked against
#     write_path_allow — coverage relies on bash_allow/bash_deny as today. Future WPs may add
#     a best-effort Bash-write extractor; until then, modes with a narrow bash_allow are the
#     trust boundary. See docs/contracts/rules-schema.md §Ambiguous Bash targets.
#   - Glob semantics: fnmatch.fnmatchcase (Python stdlib) — `*` matches any string INCLUDING
#     `/`, so `**` is equivalent to `*`. This is deliberately different from shell globbing.
#     Patterns are matched against the file_path as provided by CC (normalized: absolute paths
#     under cwd are shortened to relative).

from __future__ import annotations

import fnmatch
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ADR-058 §D1 / PLAN-098 WP-05: import shared CC PreToolUse helpers from scripts/hooks/.
# Plugin hook lives 4 levels deep under repo_root (.claude/plugins/<plugin>/hooks/<file>.py),
# so we extend sys.path here rather than rely on cwd. CC invokes us as
# `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/capability-router.py"` from the workspace cwd
# (verified by `.towow/state/*` relative paths working historically), but we anchor to
# __file__ so non-cwd-rooted callers (probes, fixtures) keep working.
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts" / "hooks"))
from _hook_output import pre_tool_use_allow, pre_tool_use_ask, pre_tool_use_deny  # noqa: E402

STATE_DIR = Path(".towow/state")
MODE_FILE = STATE_DIR / "mode"
RUN_FILE = STATE_DIR / "run.json"
LOCKS_FILE = STATE_DIR / "locks.json"
METRICS_DIR = Path(".towow/metrics")
SHADOW_LOG = METRICS_DIR / "router-shadow.jsonl"
DEFAULT_MODE = "legacy"

# Ambient utilities — low-risk, high-frequency read/probe commands that are legitimately needed
# in both build (develop-then-test loop) and verify (validate-then-report loop). Added in the
# WP-016 shadow canary follow-up after `build|Bash|curl` surfaced as a false-positive would-deny.
# Selection criteria: (1) read-only or probe-only in typical use, (2) commonly invoked mid-flow
# where a mode-switch round-trip would be pure overhead, (3) not already covered by a more
# specific rule. Higher-risk probes (`nc` listeners, `kill`, `env` secret exposure, `rm`/`mv`
# outside /tmp) are deliberately excluded — add them via an explicit ADR, not by expanding this
# list silently.
AMBIENT_ALLOW = [
    "curl*",      # GET/HEAD/probe APIs; side-effectful POST/DELETE still flow through but are
                  #   audit-visible via PostToolUse logs (Phase E evidence-emit.py).
    "wget*",      # fetch test fixtures, release notes, etc.
    "tail*",      # read log tails
    "head*",      # read file heads
    "less*",      # scripted less usage is rare; pager is non-destructive
    "ps*",        # process inspection
    "lsof*",      # open-file / open-port inspection
    "which*",     # command path resolution
    "whereis*",   # same
    "type*",      # shell builtin for command lookup
    "file*",      # classify file type
    "stat*",      # file metadata
    "wc*",        # line/word counts
    "sort*", "uniq*",  # read-only text pipelines
    "jq*", "yq*",      # structured-data read tools
]

# Mode -> per-tool allow rules. Bash is matched by command-prefix globs.
# `legacy` uses the sentinel "*" to mean "allow everything" (pass-through).
# Every other mode: anything not explicitly allowed is denied.
RULES: dict[str, dict] = {
    "legacy": {
        "allow": "*",
        "bash_allow": ["*"],
        # write_path_allow intentionally absent — legacy short-circuits on allow == "*"
    },
    "plan": {
        "allow": {"Read", "Glob", "Grep", "WebFetch", "WebSearch", "AskUserQuestion",
                  # WP-018a: Write + Edit are mode-permitted but path-gated via write_path_allow
                  "Write", "Edit",
                  # WP-039 portability fix: Skill tool is the canonical invocation path for
                  # mode transitions via plugin-loaded skills. Must be allowed symmetrically
                  # across all enforced modes so /mode <target> flips work.
                  "Skill"},
        # WP-018a: plan authors plans and decisions; nothing else.
        "write_path_allow": [".towow/plan/**", "docs/plans/**", "docs/decisions/**"],
        "bash_allow": [
            "git log*", "git status*", "git diff*", "git show*",
            "ls*", "pwd", "cat .towow/*", "cat docs/*",
            # WP-018: mode-transition handlers (finding WP-017-AXIS-3-F-001 remediation).
            # Narrow globs — only the exact mode-skill entry points, not arbitrary bash/python.
            "bash .claude/skills/mode/*",
            "python3 .claude/skills/mode/transition.py*",
            # WP-039 portability fix: when plugins load via `--plugin-dir`, mode handlers
            # resolve to `<plugin-dir>/skills/mode/*.sh` rather than `.claude/skills/mode/*`.
            # Accept both — the legacy self-repo-install path and any plugin-dir path.
            "bash */skills/mode/*",
            "python3 */skills/mode/transition.py*",
        ],
    },
    "build": {
        "allow": {"Read", "Glob", "Grep", "WebFetch", "WebSearch", "AskUserQuestion",
                  "Edit", "Write", "Agent", "Monitor", "TaskCreate", "TaskUpdate", "TaskList",
                  # WP-039 portability fix (see plan.allow note).
                  "Skill"},
        # WP-018a (finding WP-018-AXIS-3-SIB-006): explicit broad — preserves today's "build can
        # write anywhere" behavior but makes the scope visible. Future narrowing is a RULES edit,
        # not a schema migration. Still subject to bash_allow on Bash-path writes.
        "write_path_allow": ["**"],
        "bash_allow": [
            "git log*", "git status*", "git diff*", "git add*",
            "pytest*", "npm test*", "cargo check*", "cargo test*",
            "python*", "node*", "npm run*", "tsc*", "ruff*", "mypy*",
            "mkdir -p*", "rm /tmp/*",  # scoped rm only
            # WP-018: mode-transition handlers — symmetric with plan.bash_allow so build can
            # return to plan or forward to verify/release without a human round-trip.
            "bash .claude/skills/mode/*",
            "python3 .claude/skills/mode/transition.py*",
            # WP-039 portability fix: plugin-dir handler paths (see plan.bash_allow note).
            "bash */skills/mode/*",
            "python3 */skills/mode/transition.py*",
            *AMBIENT_ALLOW,
        ],
    },
    "verify": {
        "allow": {"Read", "Glob", "Grep", "WebFetch", "Agent", "AskUserQuestion",
                  # WP-018a (finding WP-018-AXIS-3-SIB-001/002): verify emits evidence files.
                  # Write + Edit are mode-permitted but path-gated via write_path_allow.
                  "Write", "Edit",
                  # WP-039 portability fix (see plan.allow note).
                  "Skill"},
        # WP-018a: verify's primary outputs — evidence packets and reports.
        "write_path_allow": [".towow/evidence/**", "docs/reports/**"],
        "bash_allow": [
            "git log*", "git status*", "git diff*", "git show*",
            "pytest*", "npm test*", "cargo test*",
            # WP-018a (finding WP-018-AXIS-3-SIB-003): mode-transition handlers — symmetric with
            # plan/build so verify can return to build (e.g. for a rebaseline) or advance to
            # release without a human round-trip.
            "bash .claude/skills/mode/*",
            "python3 .claude/skills/mode/transition.py*",
            # WP-039 portability fix: plugin-dir handler paths + test-harness helpers under
            # .towow/bin/ (finalize-reviewer-packet, etc. — scoped to .towow/bin/ so this is
            # not a general `python3 *` widening).
            "bash */skills/mode/*",
            "python3 */skills/mode/transition.py*",
            "python3 .towow/bin/*",
            *AMBIENT_ALLOW,
        ],
    },
    "release": {
        # WP-018a (finding WP-018-AXIS-3-SIB-005): the dead "Bash" entry is removed — decide()
        # special-cases Bash via bash_allow and never reads this set for Bash anyway.
        # Write + Edit added (path-gated) so release can land CHANGELOG bumps / tagged artifacts.
        "allow": {"Read", "AskUserQuestion", "Write", "Edit",
                  # WP-039 portability fix (see plan.allow note).
                  "Skill"},
        # WP-018a: release's narrow write surface — release tree, changelog, version file.
        "write_path_allow": [".towow/release/**", "CHANGELOG.md", "VERSION"],
        "bash_allow": [
            "git commit*", "git push*", "git tag*",
            "deploy*", "./scripts/deploy*",
            # WP-018a (finding WP-018-AXIS-3-SIB-004): mode-transition handlers — symmetric with
            # the others; lets the agent roll back to build/verify or drop to plan if a release
            # needs to be paused, without a human round-trip.
            "bash .claude/skills/mode/*",
            "python3 .claude/skills/mode/transition.py*",
            # WP-039 portability fix: plugin-dir handler paths (see plan.bash_allow note).
            "bash */skills/mode/*",
            "python3 */skills/mode/transition.py*",
        ],
    },
}

# Modes graduated out of shadow. When the active mode is in this set, SHADOW=1's
# deny/ask→allow downgrade is skipped — the CC-mapped decision flows through.
# Grows one mode at a time per WP-017..WP-020; never includes "legacy" (pass-through).
ENFORCED_MODES: set[str] = {"plan", "build", "verify", "release"}  # WP-020 (added "release"; WP-019 added "verify"; WP-018 added "build"; WP-017 added "plan"); Phase D complete — all four active modes enforced; legacy remains pass-through


def ensure_state_files() -> str:
    """Ensure STATE_DIR exists and lazily seed required runtime files. Returns the current mode.

    Write failures are swallowed silently and the router falls back to DEFAULT_MODE — the router
    must never block a tool call due to a filesystem hiccup. `.towow/state/*` is .gitignored, so
    lazy creation never dirties the index.
    """
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return DEFAULT_MODE
    if not MODE_FILE.exists():
        try:
            MODE_FILE.write_text(DEFAULT_MODE + "\n")
        except OSError:
            pass
    if not RUN_FILE.exists():
        try:
            RUN_FILE.write_text("{}\n")
        except OSError:
            pass
    if not LOCKS_FILE.exists():
        try:
            LOCKS_FILE.write_text("{}\n")
        except OSError:
            pass
    try:
        return (MODE_FILE.read_text().strip() or DEFAULT_MODE)
    except OSError:
        return DEFAULT_MODE


def bash_match(cmd: str, patterns: list[str]) -> str | None:
    """Return the first glob in *patterns* that matches *cmd*, else None.

    Callers use the matched pattern as a rule-identity marker (see `rule_matched`
    in the §1.4.1 canonical shadow-log schema).
    """
    for pat in patterns:
        if fnmatch.fnmatchcase(cmd, pat):
            return pat
    return None


def normalize_write_path(file_path: str) -> str:
    """Normalize a write target path for matching against write_path_allow.

    Absolute paths under the current working directory are shortened to relative.
    Paths outside cwd are returned verbatim (they will simply not match any
    relative-prefixed glob). Non-string / empty input returns "".
    """
    if not file_path or not isinstance(file_path, str):
        return ""
    try:
        p = Path(file_path)
        if p.is_absolute():
            try:
                return str(p.relative_to(Path.cwd()))
            except ValueError:
                return file_path
        return file_path
    except (OSError, ValueError):
        return file_path


def write_path_match(file_path: str, patterns: list[str]) -> str | None:
    """Match *file_path* against the first glob in *patterns* (fnmatch semantics).

    Per RULES schema docs: `*` matches any string INCLUDING `/`, so `**` is
    equivalent to `*`. This is deliberately different from shell globbing; the
    schema doc at docs/contracts/rules-schema.md is the authoritative reference.
    """
    rel = normalize_write_path(file_path)
    if not rel:
        return None
    for pat in patterns:
        if fnmatch.fnmatchcase(rel, pat):
            return pat
    return None


def summarize_input(tool: str, tool_input: dict) -> str:
    """Single-line synthesis of tool_input for the shadow-log row.

    Required by §1.4.1 (`tool_input_summary`). Kept short (<=120 chars) so the
    jsonl stays line-oriented; callers that need the raw input inspect the
    tool_input dict directly via PostToolUse evidence.
    """
    if tool == "Bash":
        return (tool_input.get("command", "") or "")[:120]
    for key in ("file_path", "url", "query", "path", "pattern"):
        val = tool_input.get(key)
        if val:
            return f"{tool}:{val}"[:120]
    return tool


def decide(mode: str, tool: str, tool_input: dict) -> dict:
    rule = RULES.get(mode)
    if rule is None:
        return {"decision": "deny", "reason": f"unknown mode {mode!r}", "rule_matched": None}
    if rule["allow"] == "*":
        return {"decision": "allow", "reason": f"mode {mode!r} is pass-through", "rule_matched": f"pass-through:{mode}"}
    if tool == "Bash":
        cmd = tool_input.get("command", "")
        match = bash_match(cmd, rule["bash_allow"])
        if match is not None:
            return {"decision": "allow", "rule_matched": f"bash-allow:{match}"}
        for other_mode, other_rule in RULES.items():
            if other_mode == mode or other_rule["allow"] == "*":
                continue
            match = bash_match(cmd, other_rule["bash_allow"])
            if match is not None:
                return {
                    "decision": "defer",
                    "systemMessage": f"Bash command fits mode {other_mode!r}; current mode is {mode!r}. "
                                     f"Switch mode (requires gate) or pick an in-mode command.",
                    "rule_matched": f"bash-defer-from:{other_mode}:{match}",
                }
        return {"decision": "deny", "reason": f"Bash command not allowed in mode {mode!r}: {cmd[:80]}", "rule_matched": None}
    if tool in rule["allow"]:
        # WP-018a: for Write/Edit, consult write_path_allow when present. Modes without the
        # field (or with None) keep today's tool-name-only semantics. Modes with the field
        # get a terminal allow-or-deny based on the target path; no cross-mode path-defer.
        if tool in {"Write", "Edit"}:
            wpa = rule.get("write_path_allow")
            if wpa is not None:
                fp = tool_input.get("file_path", "") or ""
                match = write_path_match(fp, wpa)
                if match is None:
                    return {
                        "decision": "deny",
                        "reason": (
                            f"{tool} to {fp[:120]!r} is not in mode {mode!r}.write_path_allow "
                            f"({wpa}); switch mode or target an allowed path."
                        ),
                        "rule_matched": f"write-path-deny:{mode}:out-of-scope",
                    }
                return {
                    "decision": "allow",
                    "rule_matched": f"write-path-allow:{mode}:{match}",
                }
        return {"decision": "allow", "rule_matched": f"tool-allow:{tool}"}
    for other_mode, other_rule in RULES.items():
        if other_mode == mode or other_rule["allow"] == "*":
            continue
        if tool in other_rule["allow"]:
            return {
                "decision": "defer",
                "systemMessage": f"Tool {tool!r} fits mode {other_mode!r}; current mode is {mode!r}.",
                "rule_matched": f"tool-defer-from:{other_mode}:{tool}",
            }
    return {"decision": "deny", "reason": f"tool {tool!r} not allowed in mode {mode!r}", "rule_matched": None}


def bash_prefix(cmd: str) -> str:
    """First non-flag token of a bash command, used as a saturation bucket key."""
    for tok in cmd.split():
        if not tok.startswith("-"):
            return tok
    return ""


def _is_interactive() -> bool:
    """Detect whether the caller is an interactive CC session.

    Default is interactive (defer collapses to deny). Non-interactive callers
    (e.g. subagents that can surface an ask prompt) declare themselves via
    TOWOW_NONINTERACTIVE=1. When detection is ambiguous, assume interactive
    per cc_mapping_contract.
    """
    return os.environ.get("TOWOW_NONINTERACTIVE") != "1"


def _map_internal_to_cc(internal: dict) -> tuple[str, str]:
    """Convert internal decide() result to a (cc_decision, reason) pair.

    Per cc_mapping_contract (accepted planning patch 2026-04-16):
      allow → permissionDecision: allow
      deny  → permissionDecision: deny
      defer → deny + mode-switch hint (interactive) or ask (non-interactive)
    Legacy {decision: approve|block} form is NOT used. PLAN-098 WP-05 swapped the
    hand-rolled envelope output for ``pre_tool_use_{allow,deny,ask}`` helper
    dispatch in ``main()``; this function stays as a pure mapping utility so
    shadow-log probe parity (§1.4 evidence model) remains testable.
    """
    decision = internal.get("decision", "allow")
    reason = internal.get("reason", "")

    if decision == "defer":
        reason = internal.get("systemMessage", reason)
        return ("deny" if _is_interactive() else "ask"), reason
    if decision in ("allow", "deny"):
        return decision, reason
    return "deny", f"unknown internal decision {decision!r}"


def shadow_log(mode: str, tool: str, tool_input: dict, result: dict) -> None:
    """Append one JSON line capturing what the router *would have* done.

    Schema is the §1.4.1 canonical 9-field form (ts, mode, tool, tool_input_summary,
    bash_prefix, decision_now, decision_would_be, rule_matched, source). Runtime rows
    are tagged `source: "canary"` per §1.4's shadow-gate evidence model; synthetic
    probe rows (written by scripts/probes/router/probe.py directly to the evidence
    path) use `source: "probe"` and are the only rows counted by the gate.

    Swallows every IO error — a shadow-log hiccup must never block the tool call.
    """
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": mode,
            "tool": tool,
            "tool_input_summary": summarize_input(tool, tool_input),
            "bash_prefix": bash_prefix(tool_input.get("command", "")) if tool == "Bash" else None,
            "decision_now": "log",
            "decision_would_be": result.get("decision", ""),
            "rule_matched": result.get("rule_matched"),
            "source": "canary",
        }
        with SHADOW_LOG.open("a") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    mode = ensure_state_files()
    internal = decide(mode, tool, tool_input)
    cc_decision, reason = _map_internal_to_cc(internal)
    if (os.environ.get("SHADOW") == "1"
            and mode not in ENFORCED_MODES
            and cc_decision in {"deny", "ask"}):
        shadow_log(mode, tool, tool_input, internal)
        reason = f"[SHADOW] would-{cc_decision}: {reason}"
        cc_decision = "allow"
    if cc_decision == "allow":
        pre_tool_use_allow(reason=reason or None)
    elif cc_decision == "deny":
        pre_tool_use_deny(reason)
    elif cc_decision == "ask":
        pre_tool_use_ask(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
