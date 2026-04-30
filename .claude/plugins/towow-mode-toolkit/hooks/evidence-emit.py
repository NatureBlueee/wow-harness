#!/usr/bin/env python3
# Towow vNext — PostToolUse hook: evidence-emit.
# Captures per-step evidence after code-change tools (Edit, Write, Bash-commits). Writes one packet
# per tool call to .towow/evidence/<run-id>/<step-id>.json.
#
# Grounded in Phase 2 §4.4 (step-level PRM evidence) and Phase 1 §6.1 (affordance — cheapest wrong
# path beats expensive right path; making the right path cheap means making evidence automatic).
#
# This is *not* a verifier. It is a stenographer. The verify-gate.py hook is the verifier.
# Separation of roles (capture vs gate) is deliberate — Phase 2 §3.8 cross-compare reviewer models.
#
# WP-023 copy-time compat shim: `from __future__ import annotations` defers annotation
# evaluation so PEP-604 union syntax (`dict | None`) works on Python 3.9 as well as 3.10+.
# The upstream prototype uses 3.10+ syntax; this shim preserves that syntax at source level
# while keeping the runtime 3.9-portable. No runtime behavior change. See
# docs/decisions/decision-wp-023-evidence-emit-hook-2026-04-17.md §Compat shim.
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(".towow/state")
EVIDENCE_DIR = Path(".towow/evidence")

# Tools whose output is worth capturing as evidence. Read/Grep/Glob are skipped — they don't change state.
CAPTURE_TOOLS = {"Edit", "Write", "Bash"}


def canonical_digest(packet: dict) -> str:
    p = {k: v for k, v in packet.items() if k != "digest"}
    blob = json.dumps(p, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def current_run() -> dict | None:
    try:
        return json.loads((STATE_DIR / "run.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None


def current_mode() -> str:
    try:
        return (STATE_DIR / "mode").read_text().strip()
    except OSError:
        return "unknown"


def evidence_entries_for(tool: str, tool_input: dict, tool_output: dict) -> tuple[list[str], list[dict]]:
    claims: list[str] = []
    evidence: list[dict] = []
    if tool in ("Edit", "Write"):
        file_path = tool_input.get("file_path", "<unknown>")
        claims.append(f"modified file at {file_path}")
        try:
            h = hashlib.sha256(Path(file_path).read_bytes()).hexdigest() if Path(file_path).exists() else "absent"
        except OSError:
            h = "unreadable"
        evidence.append({"claim_index": 0, "type": "file_hash", "ref": f"{file_path}@sha256:{h}"})
    elif tool == "Bash":
        cmd = tool_input.get("command", "")
        exit_code = tool_output.get("exit_code")
        claims.append(f"ran bash command: {cmd[:120]}")
        evidence.append({
            "claim_index": 0,
            "type": "command_output",
            "ref": cmd[:240],
            "pass": exit_code == 0 if exit_code is not None else None,
            "summary": (tool_output.get("stdout", "") or "")[:240],
        })
    return claims, evidence


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool = event.get("tool_name", "")
    if tool not in CAPTURE_TOOLS:
        return 0
    run = current_run()
    if run is None:
        return 0  # silent — capture-nothing outside a run is correct
    run_id = run["id"]
    out_dir = EVIDENCE_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    step_id = uuid.uuid4().hex[:12]
    claims, evidence = evidence_entries_for(tool, event.get("tool_input", {}), event.get("tool_output", {}))
    if not claims:
        return 0
    packet = {
        "packet_id": "",  # filled below
        "run_id": run_id,
        "step_id": step_id,
        "mode": current_mode(),
        "kind": "step",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "author": {"kind": "hook", "id": os.path.basename(__file__)},
        "claims": claims,
        "evidence": evidence,
        "unknowns": [],
        "predecessors": [run.get("last_packet")] if run.get("last_packet") else [],
        "digest": {"algorithm": "sha256", "value": ""},
    }
    pid = canonical_digest(packet)
    packet["packet_id"] = pid
    packet["digest"]["value"] = pid
    (out_dir / f"{step_id}.json").write_text(json.dumps(packet, indent=2))
    # Update run.json's last_packet pointer (best-effort; a lost update just means next step
    # links to an earlier predecessor — the DAG still closes via on-disk files).
    run["last_packet"] = pid
    (STATE_DIR / "run.json").write_text(json.dumps(run, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
