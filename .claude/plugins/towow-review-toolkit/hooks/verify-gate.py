#!/usr/bin/env python3
# Towow vNext — Stop hook: verify-gate (contract-driven).
#
# Replaces `stop-evaluator.py` (Phase 1 §3.3). Stop is allowed only when the current mode's
# active review-contract bindings have their required evidence packet present, schema-valid,
# and clear of block-severity blockers.
#
# WP-029 prep (contract-driven refactor):
#   - Reads `review-contract.yaml` at runtime (plugin-relative: `<plugin-root>/contracts/`).
#     The YAML is the single source of truth for which bindings fire. Flipping
#     `active: true/false` in YAML changes behaviour without touching code.
#   - Packaged as plugin `towow-review-toolkit` at WP-037. Paths SCHEMA_PATH / CONTRACT_PATH
#     resolve relative to this script's location (see _PLUGIN_ROOT below).
#   - Stop only consults bindings whose `applies_when.mode == current_mode` AND whose
#     `applies_when` carries NO `transition_target`. Bindings with transition_target gate
#     mode transitions (handled by `.claude/plugins/towow-mode-toolkit/skills/mode/transition.py`), not Stop.
#     This resolves the historical Stop/transition conflation in which `mode=verify` Stop
#     demanded a merge_ready packet — merge_ready is a verify→release transition gate,
#     not a Stop gate. Stop ≠ Completion.
#   - Output uses the official Claude Code Stop-hook schema:
#       allow → stdout systemMessage + exit 0 (no top-level "decision").
#       block → stdout `{"decision": "block", "reason": "..."}` + exit 0.
#       fail-closed → exit 2 + stderr. Used when the contract YAML is unreadable.
#     The prior `{"decision": "defer"}` form is NOT a valid Stop-hook decision
#     (Claude Code hooks only accept "block" for Stop). It was a latent no-op since
#     WP-024; removed here.
#   - SHADOW=1 mode preserved: a would-be block downgrades to allow with a
#     `[SHADOW]` systemMessage and a one-line log entry.
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ADR-058 §D1 / PLAN-098 WP-06: import shared CC Stop helpers from scripts/hooks/.
# Plugin hook anchored via __file__ (parents[4] = repo_root), independent of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts" / "hooks"))
from _hook_output import stop_block, stop_inject_system_message  # noqa: E402

STATE_DIR = Path(".towow/state")
EVIDENCE_DIR = Path(".towow/evidence")
LOG_DIR = Path(".towow/log")
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = _PLUGIN_ROOT / "contracts" / "evidence-packet-schema.json"
CONTRACT_PATH = _PLUGIN_ROOT / "contracts" / "review-contract.yaml"
SHADOW = os.environ.get("SHADOW", "0") == "1"


class ContractError(Exception):
    """Raised when review-contract.yaml cannot be loaded or parsed.

    Callers treat this as fail-closed: Stop is not permitted to continue when the
    contract itself is unreadable (surface as exit 2, not a silent allow).
    """


def current_run() -> dict | None:
    try:
        return json.loads((STATE_DIR / "run.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None


def current_mode() -> str | None:
    try:
        return (STATE_DIR / "mode").read_text().strip()
    except OSError:
        return None


def canonical_digest(packet: dict) -> str:
    p = {k: v for k, v in packet.items() if k != "digest"}
    blob = json.dumps(p, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def validate_packet(packet: dict) -> list[str]:
    errs: list[str] = []
    required = {"packet_id", "run_id", "step_id", "mode", "kind", "claims", "evidence", "digest"}
    for k in required:
        if k not in packet:
            errs.append(f"missing field {k!r}")
    if "claims" in packet and "evidence" in packet:
        n_claims = len(packet["claims"])
        covered = {e["claim_index"] for e in packet["evidence"] if "claim_index" in e}
        for i in range(n_claims):
            if i not in covered:
                errs.append(f"claim[{i}] has no evidence entry")
    if "digest" in packet:
        want = canonical_digest(packet)
        got = packet["digest"].get("value") if isinstance(packet["digest"], dict) else None
        if got != want:
            errs.append(f"digest mismatch: expected {want}, got {got}")
    if packet.get("kind") in ("merge_ready", "gate") and "unknowns" not in packet:
        errs.append("merge_ready/gate packets must declare 'unknowns' (may be empty list)")
    return errs


def latest_packet_for(run_id: str, kind: str) -> dict | None:
    d = EVIDENCE_DIR / run_id
    if not d.exists():
        return None
    candidates = sorted(d.glob("*.json"))
    for path in reversed(candidates):
        try:
            p = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if p.get("kind") == kind:
            return p
    return None


def load_active_bindings() -> list[dict]:
    """Load review-contract.yaml and return bindings with active==true.

    Fail-closed: missing PyYAML, OSError, yaml parse error, or malformed top-level
    structure all raise ContractError. main() converts this to exit 2.
    """
    try:
        import yaml  # noqa: WPS433 — lazy import so scripts without PyYAML still parse
    except ImportError as exc:
        raise ContractError(f"PyYAML not available: {exc}")
    try:
        raw = yaml.safe_load(CONTRACT_PATH.read_text())
    except OSError as exc:
        raise ContractError(f"contract unreadable at {CONTRACT_PATH}: {exc}")
    except yaml.YAMLError as exc:
        raise ContractError(f"contract YAML parse error: {exc}")
    if not isinstance(raw, dict) or "bindings" not in raw:
        raise ContractError("contract missing top-level 'bindings' list")
    bindings = raw.get("bindings") or []
    return [b for b in bindings if b.get("active") is True]


def bindings_for_stop(mode: str) -> list[dict]:
    """Active bindings that gate Stop at the current mode.

    Rule: include only bindings where applies_when.mode == current_mode AND
    applies_when carries NO transition_target. Transition-scoped bindings
    (e.g. merge-ready-review with transition_target=release) gate mode
    transitions — not Stop. They are handled by
    .claude/plugins/towow-mode-toolkit/skills/mode/transition.py.
    """
    out = []
    for b in load_active_bindings():
        aw = b.get("applies_when") or {}
        if aw.get("mode") != mode:
            continue
        if "transition_target" in aw:
            continue
        out.append(b)
    return out


def required_kind_from_binding(binding: dict) -> str | None:
    """Extract the evidence-packet kind a binding's outputs[] declares.

    Schema: review-contract.yaml bindings[].outputs[<n>].evidence_packet.kind.
    Returns None if no outputs entry declares an evidence_packet (human-only
    bindings, for instance). Such bindings are not Stop-gatable.
    """
    for out in binding.get("outputs") or []:
        if not isinstance(out, dict):
            continue
        ep = out.get("evidence_packet")
        if isinstance(ep, dict) and "kind" in ep:
            return ep["kind"]
    return None


def gate_passes(mode: str, run_id: str) -> tuple[bool, str]:
    """Evaluate Stop gate for current mode against the contract.

    Returns (allow, reason). Raises ContractError when contract unloadable.
    Never consults transition-scoped bindings (separation of Stop vs transition).
    """
    bindings = bindings_for_stop(mode)
    if not bindings:
        return True, f"mode {mode!r}: no Stop-side binding active"
    for b in bindings:
        kind = required_kind_from_binding(b)
        if kind is None:
            continue
        p = latest_packet_for(run_id, kind)
        if p is None:
            return False, f"binding {b.get('id', '?')!r} requires {kind!r} packet; none found"
        errs = validate_packet(p)
        if errs:
            return False, f"{kind!r} packet invalid: {'; '.join(errs)}"
        if any(x.get("severity") == "block" for x in (p.get("blockers") or [])):
            return False, f"{kind!r} packet has unresolved block-severity blockers"
    return True, f"mode {mode!r} Stop gate ok (all active bindings satisfied)"


def log_shadow(run_id: str, mode: str, reason: str) -> None:
    """Append one line to .towow/log/verify-gate-shadow.log describing a would-be block."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        line = json.dumps({"ts": ts, "run_id": run_id, "mode": mode, "would_block_reason": reason})
        with (LOG_DIR / "verify-gate-shadow.log").open("a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def main() -> int:
    try:
        _event = json.load(sys.stdin)
    except json.JSONDecodeError:
        _event = {}
    run = current_run()
    mode = current_mode()
    if run is None or mode is None:
        stop_inject_system_message("verify-gate: no active run; Stop allowed")
        return 0
    try:
        ok, reason = gate_passes(mode, run["id"])
    except ContractError as exc:
        sys.stderr.write(
            f"verify-gate fail-closed: {exc}. "
            f"review-contract.yaml is the single source of truth; cannot evaluate Stop "
            f"gate without it.\n"
        )
        return 2
    if ok:
        stop_inject_system_message(f"verify-gate: {reason}")
        return 0
    if SHADOW:
        log_shadow(run["id"], mode, reason)
        stop_inject_system_message(
            f"[SHADOW] verify-gate would have blocked Stop — {reason}. "
            f"Logged to .towow/log/verify-gate-shadow.log. SHADOW=1 passes anyway."
        )
        return 0
    # Real block via stop_block helper (emits CC Stop schema decision=block + reason
    # alongside hookSpecificOutput.hookEventName per ADR-058 §D1).
    stop_block(
        f"Stop blocked — {reason}. "
        f"Produce the missing/valid evidence packet under "
        f".towow/evidence/{run['id']}/ and retry."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
