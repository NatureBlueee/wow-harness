#!/usr/bin/env python3
"""detect_rebaseline_triggers.py — structural drift detector (plan-freeze level).

Reads ``rebaseline_triggers`` from ``.wow-harness/MANIFEST.yaml`` and verifies:

  1. Every listed trigger path exists on disk (if a trigger file was deleted,
     the plan's rebaseline assumption is broken).

  2. ``MANIFEST.physical_files`` matches ``count-components.sh`` live output.
     Divergence = a hook or root script was added/removed without updating
     MANIFEST — the plan's L1 registry is stale and must be rebaselined.

  3. ``len(MANIFEST.settings_command_registry) == live command count in
     .claude/settings.json``. Divergence = a command entry drifted relative
     to the declared 15 (post WP-03) / 16 (post WP-11) contract.

On any divergence, writes ``.wow-harness/rebaseline-required.flag`` and
exits 2 (CI fail).

Scope note (v2.1 patch § rebaseline detector):
  This detector is **plan-freeze-level only**. Normal hook/skill/ADR content
  edits are not rebaseline triggers. Only structural shifts in registries
  or physical file counts trigger. The trigger list must be explicitly
  enumerated in MANIFEST.rebaseline_triggers — no regex-based fuzzy matching.

Data source policy (anti-INV-4):
  The detector NEVER hard-codes 15 / 16 / 17 / 18. All numbers come from
  MANIFEST.yaml, which is the single source of truth. The detector's job is
  to cross-check MANIFEST against live repo state, not to enforce its own
  expectations.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("detect_rebaseline_triggers.py: PyYAML not installed", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = REPO_ROOT / ".wow-harness" / "MANIFEST.yaml"
FLAG_PATH = REPO_ROOT / ".wow-harness" / "rebaseline-required.flag"
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"
COUNT_SCRIPT = REPO_ROOT / "scripts" / "ci" / "count-components.sh"


def count_settings_commands(settings: dict) -> int:
    total = 0
    for stage_entries in settings.get("hooks", {}).values():
        for entry in stage_entries:
            total += len(entry.get("hooks", []))
    return total


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(f"{MANIFEST_PATH}: not found", file=sys.stderr)
        return 2
    data = yaml.safe_load(MANIFEST_PATH.read_text())
    rc = 0
    reasons: list[str] = []

    # 1. trigger path existence
    for trig in data.get("rebaseline_triggers", []):
        if not (REPO_ROOT / trig).exists():
            msg = f"rebaseline trigger path missing: {trig}"
            print(msg, file=sys.stderr)
            reasons.append(msg)
            rc = 2

    # 2. physical_files MANIFEST vs live
    declared_physical = data.get("physical_files")
    try:
        result = subprocess.run(
            ["bash", str(COUNT_SCRIPT)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"count-components.sh failed: {e.stderr}", file=sys.stderr)
        return 2

    live_physical = None
    for line in result.stdout.splitlines():
        if line.startswith("physical_files="):
            live_physical = int(line.split("=", 1)[1])
    if live_physical is None:
        print("count-components.sh did not emit physical_files", file=sys.stderr)
        return 2
    if live_physical != declared_physical:
        msg = f"physical_files drift: MANIFEST declares {declared_physical} but live is {live_physical}"
        print(f"REBASELINE REQUIRED: {msg}", file=sys.stderr)
        reasons.append(msg)
        rc = 2

    # 3. settings_command_registry length vs live settings.json
    declared_cmds = len(data.get("settings_command_registry", []))
    if SETTINGS_PATH.exists():
        settings = json.loads(SETTINGS_PATH.read_text())
        live_cmds = count_settings_commands(settings)
        if live_cmds != declared_cmds:
            msg = (
                f"settings_command_registry length drift: "
                f"MANIFEST declares {declared_cmds} but settings.json has {live_cmds}"
            )
            print(f"REBASELINE REQUIRED: {msg}", file=sys.stderr)
            reasons.append(msg)
            rc = 2

    if rc != 0:
        FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
        FLAG_PATH.write_text("\n".join(reasons) + "\n")

    return rc


if __name__ == "__main__":
    sys.exit(main())
