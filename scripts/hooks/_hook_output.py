"""CC hook output schema single source of truth (CC 2.1.105).

This helper is the **only** sanctioned way for any `scripts/hooks/*.py` or
`.claude/plugins/*/hooks/*.py` to emit JSON to stdout. Hand-rolling
`print(json.dumps(...))` from a hook is a lint BLOCK (see
`scripts/checks/lint-hook-output.py`).

ADR-058 §D1 is the truth source for this module's public API. PLAN-098 §5
WP-00 is the implementation plan. Gate 4/6 PASS_WITH_NOTES inline fixes pin
every guarantee in this file. If you need a new helper signature, **stop**
and route the change through the WP-00 seam_owner — never in-place patch.

Hard guarantees (reviewer rollback-safety F-RB-1 / F-RS-01):

1. Every event function wraps its single `print(json.dumps(...))` +
   `sys.stdout.flush()` in `try/except OSError: pass` so a closed stdout
   pipe cannot crash the hook process.
2. Every event function adds a catch-all `except BaseException: emit_raw(...)`
   so any helper-internal error (TypeError / AttributeError / unexpected
   subclass) still produces a syntactically valid stdout line and lets the
   hook process exit 0. Non-zero exit from a CC hook is interpreted as
   `deny` and would lock the entire workspace.
3. `emit_raw()` itself swallows every exception silently. **It must never
   raise and must never recursively invoke another helper.** This breaks
   the catch-all → emit_raw → catch-all → ... cascade that would otherwise
   compound into an infinite loop on a stdout-closed pipe.
4. PreToolUse helpers always set `hookSpecificOutput.permissionDecision`.
   The legacy top-level `permissionDecision` field is never emitted —
   downstream lint will WARN if it sees one. This is the F-P1-7 contract
   (ADR-058 §D1 PreToolUse routing hard constraint).
5. Six events (Stop / SubagentStop / SessionStart / SessionEnd /
   Notification / PreCompact) have schemas that CC's public docs do not
   pin and the local jsonl history could not extract. Their helpers fall
   back to emit_raw with a `# schema-unverified` docstring marker. When
   schemas are confirmed (e.g. through a future jsonl grep round) update
   the helper body and drop the marker.

Performance budget: importing this module + 10 helper calls < 50ms (Gate
8 F-P3-6 smoke).

Naming convention (ADR-058 §D1): every "context-injecting" helper carries
the `_inject` suffix to signal that calling it appends data to the model's
next-turn context. Decision-style helpers (`*_allow / *_deny / *_ask /
*_defer / *_block / *_approve / *_suppress`) describe a control-flow
verdict instead. Mixing the two flavors is a contract violation.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Mapping, Optional

__all__ = [
    "__CC_SCHEMA_VERSION__",
    "emit_raw",
    "pre_tool_use_allow",
    "pre_tool_use_deny",
    "pre_tool_use_ask",
    "pre_tool_use_defer",
    "post_tool_use_inject",
    "user_prompt_submit_inject",
    "stop_block",
    "stop_approve",
    "stop_inject_system_message",
    "subagent_stop_block",
    "subagent_stop_approve",
    "session_start_inject",
    "session_end_inject",
    "notification_suppress",
    "pre_compact_inject",
]

__CC_SCHEMA_VERSION__ = "2.1.105"


def emit_raw(payload: Mapping[str, Any]) -> None:
    """Last-resort emitter. Never raises, never recurses.

    This is the catch-all sink that every other helper falls back to on
    BaseException. Its body must therefore be **simpler than every other
    helper combined**:

      - one `json.dumps`
      - one `print` + `flush` wrapped in try/except OSError
      - a final BaseException guard that just `pass`-es

    Crucially, this function is forbidden from calling any other helper
    in this module. If json.dumps raises (a non-serializable payload),
    we fall through to the BaseException branch and emit nothing. That
    is acceptable — the alternative (recursive emit_raw) would risk an
    unbounded loop and is the explicit F-RS-01 closure target.
    """

    try:
        try:
            line = json.dumps(payload)
        except (TypeError, ValueError):
            line = "{\"hookSpecificOutput\": {}}"
        try:
            print(line)
            sys.stdout.flush()
        except OSError:
            pass
    except BaseException:
        pass


def _emit_event(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload))
        sys.stdout.flush()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# PreToolUse (4 helpers) — F-P1-7 contract: hookSpecificOutput.permissionDecision only.


def pre_tool_use_allow(
    updated_input: Optional[Mapping[str, Any]] = None,
    reason: Optional[str] = None,
) -> None:
    """PreToolUse → allow.

    Emits ``hookSpecificOutput.permissionDecision = "allow"``. The legacy
    top-level ``permissionDecision`` field is never set (F-P1-7 contract).

    ``updated_input`` is the auto-python3 / capability-router rewrite path:
    when set, CC forwards this dict back as the actual ``tool_input`` for
    the about-to-run tool call. Only ``hookSpecificOutput.permissionDecision``
    can carry it (the legacy top-level field cannot), which is why the
    PreToolUse helpers funnel through this one shape.
    """

    try:
        hook_specific: dict[str, Any] = {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
        if reason is not None:
            hook_specific["permissionDecisionReason"] = reason
        if updated_input is not None:
            hook_specific["updatedInput"] = dict(updated_input)
        _emit_event({"hookSpecificOutput": hook_specific})
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


def pre_tool_use_deny(reason: str) -> None:
    """PreToolUse → deny. CC runtime treats this as a real block of the
    pending tool call (ADR-042 §D4 write barrier chokepoint).

    ``reason`` is required: it surfaces in the CC UI and tells the AI what
    to do next. Empty / missing reasons leave the user staring at a silent
    block, which is the failure mode owner-guard repeatedly drifted into.
    """

    try:
        _emit_event(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


def pre_tool_use_ask(reason: str) -> None:
    """PreToolUse → ask (interactive prompt to user). ``reason`` is required."""

    try:
        _emit_event(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                }
            }
        )
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


def pre_tool_use_defer(reason: Optional[str] = None) -> None:
    """PreToolUse → defer. The tool call is held until a later trigger
    (used by capability-router for mode-gated lifecycle moves).

    ``defer`` is the only PreToolUse decision that CC's hookSpecificOutput
    schema accepts but the legacy top-level field does not — which is why
    capability-router must go through this helper, not hand-rolled JSON.
    """

    try:
        hook_specific: dict[str, Any] = {
            "hookEventName": "PreToolUse",
            "permissionDecision": "defer",
        }
        if reason is not None:
            hook_specific["permissionDecisionReason"] = reason
        _emit_event({"hookSpecificOutput": hook_specific})
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


# ---------------------------------------------------------------------------
# PostToolUse (1 helper) — context injection.


def post_tool_use_inject(context: str) -> None:
    """PostToolUse → inject ``additionalContext`` into the model's next turn.

    ``context`` is required by ADR-058 §D1: a PostToolUse hook that wants
    to emit anything must inject context. If you have nothing to inject,
    return early with empty stdout (CC PostToolUse interprets that as a
    no-op, no decision needed). This is the contract loop-detection.py
    relies on for its 4 allow branches (PLAN-098 §5 WP-02 DoD 5).
    """

    try:
        _emit_event(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": context,
                }
            }
        )
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


# ---------------------------------------------------------------------------
# UserPromptSubmit (1 helper).


def user_prompt_submit_inject(context: str) -> None:
    """UserPromptSubmit → inject ``additionalContext`` into the prompt.

    ``context`` is required by the schema. UserPromptSubmit is the one
    event whose hookSpecificOutput.additionalContext is documented and
    grep-confirmed — no schema-unverified marker.
    """

    try:
        _emit_event(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": context,
                }
            }
        )
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


# ---------------------------------------------------------------------------
# Stop (3 helpers) — schema-unverified except for documented top-level fields.


def stop_approve(reason: Optional[str] = None) -> None:
    """Stop → approve (let CC stop normally).

    Per ADR-058 §50, Stop's top-level ``decision`` field accepts both
    ``"block"`` and ``"approve"`` (Stop-specific, not the PreToolUse
    ``decision``). Emitting ``decision: "approve"`` makes the helper name
    align with payload semantics; pre-fix the helper produced no decision
    at all, leaving callers staring at a name that promised more than the
    payload delivered. R1 P2-2 (Gate 8 followup) closure decision: option
    B over rename — zero production callers + ADR §50 already pinned it.

    ``reason`` is optional and surfaces alongside ``decision`` (mirrors
    the ``stop_block`` shape — symmetric helper API).
    """

    try:
        payload: dict[str, Any] = {
            "decision": "approve",
            "hookSpecificOutput": {"hookEventName": "Stop"},
        }
        if reason is not None:
            payload["reason"] = reason
        _emit_event(payload)
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


def stop_block(reason: str) -> None:  # schema-unverified
    """Stop → block (request that CC continue rather than stop).

    ``reason`` is required (matches verify-gate.py existing call shape).
    Schema-unverified — see ``stop_approve``. Emits the legacy top-level
    ``decision``/``reason`` fields (which CC has historically accepted for
    Stop events) alongside ``hookSpecificOutput.hookEventName``. If a future
    jsonl grep pins a richer schema, update this body.
    """

    try:
        _emit_event(
            {
                "decision": "block",
                "reason": reason,
                "hookSpecificOutput": {"hookEventName": "Stop"},
            }
        )
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


def stop_inject_system_message(msg: str) -> None:  # schema-unverified
    """Stop → inject a systemMessage shown to the user.

    Schema-unverified. ``systemMessage`` is the documented top-level field
    name across multiple events; pair it with ``hookSpecificOutput.hookEventName``
    to satisfy CC's validator. Distinct from ``stop_block`` — block flips
    CC's decision; inject_system_message is a UI affordance with no decision
    impact (verify-gate.py uses both).
    """

    try:
        _emit_event(
            {"systemMessage": msg, "hookSpecificOutput": {"hookEventName": "Stop"}}
        )
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


# ---------------------------------------------------------------------------
# SubagentStop (2 helpers) — same shape as Stop, ADR-058 §D1 new.


def subagent_stop_approve(reason: Optional[str] = None) -> None:
    """SubagentStop → approve. Symmetric to ``stop_approve``: emits
    top-level ``decision: "approve"`` per ADR-058 §50 (Stop-family
    semantics inherited by SubagentStop). ``reason`` optional, mirrors
    ``subagent_stop_block``."""

    try:
        payload: dict[str, Any] = {
            "decision": "approve",
            "hookSpecificOutput": {"hookEventName": "SubagentStop"},
        }
        if reason is not None:
            payload["reason"] = reason
        _emit_event(payload)
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


def subagent_stop_block(reason: str) -> None:  # schema-unverified
    """SubagentStop → block. ``reason`` is required, see ``stop_block``."""

    try:
        _emit_event(
            {
                "decision": "block",
                "reason": reason,
                "hookSpecificOutput": {"hookEventName": "SubagentStop"},
            }
        )
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


# ---------------------------------------------------------------------------
# SessionStart / SessionEnd (2 helpers) — schema-unverified.


def session_start_inject(context: str) -> None:  # schema-unverified
    """SessionStart → inject ``additionalContext``. Schema-unverified;
    some CC builds accept additionalContext on SessionStart as well.
    ``context`` is required by ADR-058 §D1 — if you have nothing to
    inject, do not call this helper (return empty stdout instead).
    """

    try:
        _emit_event(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                }
            }
        )
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


def session_end_inject(
    context: Optional[str] = None,
    stop_reason: Optional[str] = None,
) -> None:  # schema-unverified
    """SessionEnd → inject context / stop_reason. Schema-unverified.

    Both parameters optional: SessionEnd is the only event where ADR-058
    §D1 explicitly allows a no-op call (helper still emits a syntactically
    valid envelope tagged with ``hookEventName`` to satisfy CC's validator).
    ``stop_reason`` is surfaced via top-level field; ``context`` via
    hookSpecificOutput.
    """

    try:
        hook_specific: dict[str, Any] = {"hookEventName": "SessionEnd"}
        if context is not None:
            hook_specific["additionalContext"] = context
        payload: dict[str, Any] = {"hookSpecificOutput": hook_specific}
        if stop_reason is not None:
            payload["stopReason"] = stop_reason
        _emit_event(payload)
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


# ---------------------------------------------------------------------------
# Notification (1 helper) — schema-unverified, ADR-058 §D1 new.


def notification_suppress(reason: Optional[str] = None) -> None:  # schema-unverified
    """Notification → suppress CC's default notification UI for this event.

    Schema-unverified. ``reason`` is optional — when provided, attached as a
    top-level ``reason`` field for best-effort UI surfacing (some CC builds
    show it, others ignore — the helper falls through to emit_raw on any
    serialization failure). Reviewer #1 P3 (Gate 8) flagged signature drift
    between the rule doc table (``notification_suppress(reason=None)``) and
    the helper, this aligns them.
    """

    try:
        payload: dict[str, Any] = {"hookSpecificOutput": {"hookEventName": "Notification"}}
        if reason is not None:
            payload["reason"] = reason
        _emit_event(payload)
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})


# ---------------------------------------------------------------------------
# PreCompact (1 helper) — schema-unverified.


def pre_compact_inject(context: str) -> None:  # schema-unverified
    """PreCompact → inject ``additionalContext`` ahead of CC compaction.
    Schema-unverified. ``context`` required by ADR-058 §D1.
    """

    try:
        _emit_event(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreCompact",
                    "additionalContext": context,
                }
            }
        )
    except BaseException:
        emit_raw({"hookSpecificOutput": {}})
