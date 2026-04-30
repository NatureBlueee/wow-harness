#!/usr/bin/env python3
# /mode transition handler (contract-driven, WP-029 prep).
#
# Validates the transition gate for the target mode and, if the gate passes, writes
# `.towow/state/mode` atomically. Never bypasses; a gate failure exits non-zero with
# a specific reason on stderr.
#
# WP-029 changes:
#   - `/mode release` is now a contract-driven orchestrator. Reads
#     `review-contract.yaml` at runtime (contract now ships inside the
#     `towow-review-toolkit` plugin at `.claude/plugins/towow-review-toolkit/contracts/`
#     in consumer repos, WP-037 packaging) and consults every active binding where
#     `applies_when.transition_target == "release"`. For each binding:
#       * reviewer.type == subagent:
#           If the required evidence-packet kind is absent, emit a structured
#           spawn-reviewer directive on stderr and exit 3 (CC-in-loop signal). The
#           host Claude Code session is expected to spawn the named subagent with
#           the declared tool whitelist, have it produce the packet, then re-run
#           `/mode release`.
#           If the packet exists, validate it (schema + blockers) like any other
#           packet.
#       * reviewer.type == human / pane:
#           Require the packet to already exist on disk with valid schema and no
#           block-severity blockers. These types do not spawn; humans/panes must
#           produce evidence before the transition is attempted.
#   - Evidence lookup is unified on the canonical per-run path:
#     `.towow/evidence/<run_id>/*.json`, scanned for `kind` matches. The legacy
#     `.towow/evidence/gates/*.json` path is NOT consulted.
#   - `plan` / `build` / `verify` gates keep their file-presence semantics (they
#     have no `transition_target` bindings against them in the current contract),
#     but read from the canonical per-run path for gate packets.
#   - Fail-closed: any ContractError (unreadable/malformed YAML, missing PyYAML)
#     exits 2 with stderr explanation. Stop is never silently allowed when the
#     contract itself is the source of uncertainty.
#
# Exit codes:
#   0 = transition applied (or no-op if already at target)
#   1 = gate denied (packet missing, invalid, or blocker found; or plan/build file check failed)
#   2 = fail-closed (contract unreadable or usage error)
#   3 = spawn_reviewer directive emitted on stderr; caller (CC) is expected to
#       spawn the subagent, have it emit the packet, and re-run.
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

STATE_DIR = Path(".towow/state")
MODE_FILE = STATE_DIR / "mode"
RUN_FILE = STATE_DIR / "run.json"
EVIDENCE_DIR = Path(".towow/evidence")


def _resolve_contract_path() -> Path:
    """Portable resolution for review-contract.yaml across harness / --plugin-dir / self-repo installs.

    Resolution order:
      1. TOWOW_REVIEW_CONTRACT env var (explicit override; wins if set and exists).
      2. Sibling plugin under a shared plugin-dir parent: <this-plugin-root>/../towow-review-toolkit/contracts/review-contract.yaml.
         Works for `--plugin-dir A --plugin-dir B` when both plugins live side by side (typical),
         and for self-repo installs where both plugins live under `.claude/plugins/` side by side.
      3. Legacy cwd-relative path preserved for backwards compatibility with scripts that drop
         the contract under `.claude/plugins/towow-review-toolkit/...` in cwd.

    WP-039 portability fix: previously a hardcoded cwd-relative path; broke in any repo that is
    not the harness itself (scratch repos, consumer repos loading plugins via --plugin-dir).
    """
    env_override = os.environ.get("TOWOW_REVIEW_CONTRACT")
    if env_override and Path(env_override).exists():
        return Path(env_override)
    self_plugin_root = Path(__file__).resolve().parent.parent.parent  # skills/mode/transition.py → plugin root
    sibling = self_plugin_root.parent / "towow-review-toolkit" / "contracts" / "review-contract.yaml"
    if sibling.exists():
        return sibling
    return Path(".claude/plugins/towow-review-toolkit/contracts/review-contract.yaml")


CONTRACT_PATH = _resolve_contract_path()

PLAN_FILE = Path(".towow/plan/current.md")

VALID_TARGETS = {"plan", "build", "verify", "release"}

EXIT_OK = 0
EXIT_DENIED = 1
EXIT_FAIL_CLOSED = 2
EXIT_SPAWN_REVIEWER = 3


class ContractError(Exception):
    """Raised when review-contract.yaml cannot be loaded or parsed.

    main() converts this to exit 2 (fail-closed). Callers must never treat this
    as a silent allow — the contract is the single source of truth for gates.
    """


# ---------------------------------------------------------------------------
# State IO
# ---------------------------------------------------------------------------

def read_current_mode() -> str:
    try:
        return MODE_FILE.read_text().strip() or "legacy"
    except OSError:
        return "legacy"


def write_mode(target: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = MODE_FILE.with_suffix(".tmp")
    tmp.write_text(target + "\n")
    os.replace(tmp, MODE_FILE)


def current_run() -> dict | None:
    try:
        return json.loads(RUN_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Evidence packet IO
# ---------------------------------------------------------------------------

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
    for path in reversed(sorted(d.glob("*.json"))):
        try:
            p = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if p.get("kind") == kind:
            return p
    return None


# ---------------------------------------------------------------------------
# Contract loading
# ---------------------------------------------------------------------------

def load_active_bindings() -> list[dict]:
    """Load review-contract.yaml and return bindings with active==true.

    Fail-closed: any of missing PyYAML / unreadable file / parse error / missing
    top-level `bindings` raises ContractError (→ exit 2 in main()).
    """
    try:
        import yaml  # noqa: WPS433 — lazy so the rest of the module imports without PyYAML
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
    return [b for b in (raw.get("bindings") or []) if b.get("active") is True]


def bindings_for_transition(target: str) -> list[dict]:
    """Active bindings whose applies_when.transition_target equals target."""
    out = []
    for b in load_active_bindings():
        aw = b.get("applies_when") or {}
        if aw.get("transition_target") == target:
            out.append(b)
    return out


def required_kind_from_binding(binding: dict) -> str | None:
    """Extract the evidence-packet kind a binding's outputs[] declares.

    Schema: review-contract.yaml bindings[].outputs[<n>].evidence_packet.kind.
    Returns None if no outputs entry declares an evidence_packet.
    """
    for out in binding.get("outputs") or []:
        if not isinstance(out, dict):
            continue
        ep = out.get("evidence_packet")
        if isinstance(ep, dict) and "kind" in ep:
            return ep["kind"]
    return None


# ---------------------------------------------------------------------------
# Release orchestrator
# ---------------------------------------------------------------------------

def build_spawn_reviewer_directive(binding: dict, run_id: str, kind: str) -> dict:
    """Serialize a spawn-reviewer directive for the host session (CC-in-loop)."""
    reviewer = binding.get("reviewer") or {}
    return {
        "action": "spawn_reviewer",
        "binding_id": binding.get("id"),
        "subagent_ref": reviewer.get("subagent_ref"),
        "tools_whitelist": reviewer.get("tools_whitelist") or [],
        "forbidden_tools": reviewer.get("forbidden_tools") or [],
        "run_id": run_id,
        "evidence_root": f".towow/evidence/{run_id}/",
        "required_kind": kind,
        "prompt": (
            f"You are the {reviewer.get('subagent_ref', 'reviewer')} subagent invoked "
            f"by binding {binding.get('id')!r} for run {run_id}. Produce an evidence "
            f"packet of kind={kind!r} under .towow/evidence/{run_id}/ that satisfies "
            f"the binding's gating requirements. Do not use tools outside the "
            f"tools_whitelist. When done, emit the packet via evidence-emit and the "
            f"host will re-run `/mode release`."
        ),
    }


def gate_for_release(run_id: str) -> tuple[int, str, dict | None]:
    """Evaluate /mode release against active contract bindings.

    Returns (exit_code, reason, directive).
      - EXIT_OK: all transition-scoped release bindings satisfied.
      - EXIT_DENIED: a packet is present but invalid / has blockers; or a human/pane
        binding has no packet (those types do not spawn).
      - EXIT_SPAWN_REVIEWER: a subagent binding lacks its packet — directive
        attached, caller must spawn, then re-run.
    """
    bindings = bindings_for_transition("release")
    if not bindings:
        return EXIT_OK, "no transition-scoped release binding active", None
    for b in bindings:
        kind = required_kind_from_binding(b)
        if kind is None:
            continue
        reviewer = b.get("reviewer") or {}
        rtype = reviewer.get("type")
        p = latest_packet_for(run_id, kind)
        if p is None:
            if rtype == "subagent":
                directive = build_spawn_reviewer_directive(b, run_id, kind)
                reason = (
                    f"binding {b.get('id')!r} requires {kind!r} packet; none found. "
                    f"Spawning reviewer subagent {reviewer.get('subagent_ref')!r}."
                )
                return EXIT_SPAWN_REVIEWER, reason, directive
            reason = (
                f"binding {b.get('id')!r} ({rtype}) requires {kind!r} packet at "
                f".towow/evidence/{run_id}/; none found. "
                f"{rtype} reviewers do not auto-spawn — produce the packet first."
            )
            return EXIT_DENIED, reason, None
        errs = validate_packet(p)
        if errs:
            return EXIT_DENIED, f"{kind!r} packet invalid: {'; '.join(errs)}", None
        if any(x.get("severity") == "block" for x in (p.get("blockers") or [])):
            return EXIT_DENIED, f"{kind!r} packet has unresolved block-severity blockers", None
    return EXIT_OK, "all release-transition bindings satisfied", None


# ---------------------------------------------------------------------------
# Non-release gates (file-presence checks, unchanged semantics but canonical
# evidence path for verify)
# ---------------------------------------------------------------------------

def gate_for_plan() -> tuple[bool, str]:
    return True, "any → plan is always allowed (mode-contract §4)"


def gate_for_build() -> tuple[bool, str]:
    if not PLAN_FILE.exists():
        return False, (f"build requires a plan file at {PLAN_FILE}. "
                       f"Write the plan first, then re-run `/mode build`.")
    return True, f"plan file present at {PLAN_FILE}"


def gate_for_verify(run_id: str | None) -> tuple[bool, str]:
    if run_id is None:
        return False, (f"verify requires an active run (.towow/state/run.json) and a "
                       f"build-mode 'gate' packet under .towow/evidence/<run_id>/.")
    p = latest_packet_for(run_id, "gate")
    if p is None:
        return False, (f"verify requires a build-mode gate packet under "
                       f".towow/evidence/{run_id}/. Emit the packet via "
                       f"evidence-emit before `/mode verify`.")
    errs = validate_packet(p)
    if errs:
        return False, f"build-mode gate packet invalid: {'; '.join(errs)}"
    if any(x.get("severity") == "block" for x in (p.get("blockers") or [])):
        return False, "build-mode gate packet has unresolved block-severity blockers"
    return True, f"build-mode gate packet present at .towow/evidence/{run_id}/ and valid"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in VALID_TARGETS:
        sys.stderr.write(f"usage: transition.py <{'|'.join(sorted(VALID_TARGETS))}>\n")
        return EXIT_FAIL_CLOSED
    target = argv[1]
    current = read_current_mode()
    if current == target:
        sys.stdout.write(f"mode is already {target!r}; no-op.\n")
        return EXIT_OK

    run = current_run()
    run_id = run["id"] if run and "id" in run else None

    if target == "plan":
        allowed, reason = gate_for_plan()
    elif target == "build":
        allowed, reason = gate_for_build()
    elif target == "verify":
        allowed, reason = gate_for_verify(run_id)
    elif target == "release":
        if run_id is None:
            sys.stderr.write(
                f"transition {current!r} → 'release' denied: no active run "
                f"(.towow/state/run.json missing). Start a run before requesting release.\n"
            )
            return EXIT_DENIED
        try:
            code, reason, directive = gate_for_release(run_id)
        except ContractError as exc:
            sys.stderr.write(
                f"transition {current!r} → 'release' fail-closed: {exc}. "
                f"review-contract.yaml is the single source of truth; cannot "
                f"evaluate release gate without it.\n"
            )
            return EXIT_FAIL_CLOSED
        if code == EXIT_SPAWN_REVIEWER:
            sys.stderr.write(f"{reason}\n")
            sys.stderr.write(json.dumps(directive, sort_keys=True) + "\n")
            return EXIT_SPAWN_REVIEWER
        if code == EXIT_DENIED:
            sys.stderr.write(f"transition {current!r} → 'release' denied: {reason}\n")
            return EXIT_DENIED
        allowed, reason = True, reason
    else:
        sys.stderr.write(f"unknown target mode {target!r}\n")
        return EXIT_FAIL_CLOSED

    if not allowed:
        sys.stderr.write(f"transition {current!r} → {target!r} denied: {reason}\n")
        return EXIT_DENIED

    write_mode(target)
    msg = f"mode: {current!r} → {target!r}. Gate: {reason}\n"
    if target == "plan" and current not in {"legacy", "plan"}:
        msg += (f"note: abort-packet emission for {current!r} → 'plan' is deferred to WP-022 "
                f"(evidence-emit.py). Transition accepted without packet for WP-015.\n")
    sys.stdout.write(msg)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
