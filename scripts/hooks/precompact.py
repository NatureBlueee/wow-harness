#!/usr/bin/env python3
# Towow vNext — PreCompact hook.
# Replaces the current Towow precompact.sh / precompact constitutional reinjection (Phase 1 §3.3 bad).
# Grounded in Phase 2 §1.5 (compact mechanics + prompt-cache invalidation cost) and §1.3 hook guide
# ("keep additionalContext payloads small — <1KB").
#
# Design intent: a compact boundary should SHRINK context, not enlarge it. We emit one pointer line
# to the active run's state files. The model re-learns everything else by reading those files on demand.
#
# Emits at most ~400 bytes of additionalContext. No constitutional recitation. No objective re-echo.

import json
import sys
from pathlib import Path

from _hook_output import pre_compact_inject

STATE_DIR = Path(".towow/state")
MAX_BYTES = 512  # hard cap; enforced below


def run_pointer() -> dict:
    run_file = STATE_DIR / "run.json"
    mode_file = STATE_DIR / "mode"
    if not run_file.exists() or not mode_file.exists():
        return {}
    try:
        run = json.loads(run_file.read_text())
        mode = mode_file.read_text().strip()
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[precompact] corrupt run.json: {exc!r}; emitting empty pointer\n")
        return {}
    except OSError:
        return {}
    return {
        "run_id": run.get("id"),
        "mode": mode,
        "task_ref": run.get("task_ref"),
        "evidence_root": run.get("evidence_root"),
        "last_packet": run.get("last_packet"),
    }


def format_pointer(p: dict) -> str:
    if not p:
        return "No active run. Enter plan mode with /mode plan before any edit."
    return (
        f"Active run {p['run_id']} in mode={p['mode']}. "
        f"Task: {p.get('task_ref', '<unset>')}. "
        f"Read .towow/state/run.json for details; "
        f"read .towow/evidence/{p['run_id']}/ for prior step evidence. "
        f"Last packet: {p.get('last_packet', '<none>')}."
    )


def main() -> int:
    try:
        _event = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[precompact] stdin JSON decode error: {exc!r}; ignoring event\n")
        _event = {}
    pointer = run_pointer()
    line = format_pointer(pointer)
    if len(line.encode()) > MAX_BYTES:
        line = line[:MAX_BYTES - 3] + "..."
    pre_compact_inject(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
