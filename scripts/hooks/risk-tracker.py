#!/usr/bin/env python3
"""PostToolUse hook: L2 Risk Snapshot Tracker (ADR-044 §4)

在每次 Edit|Write 后，根据被修改文件的路径计算风险等级，
写入 .towow/state/risk-snapshot.json。

核心规则（§4.2）：风险只能升，不能降（棘轮）。
核心规则（§4.3）：风险由客观事实（路径）计算，不由 AI 自述。

风险抬升器（§4.4 通用默认版本）：
1. 治理目录 / hook / CI / 安全 → R3
2. route / schema / config / public docs → R2
3. deploy / migration / auth / secret → R4
4. 跨 2+ 核心模块 → R3
5. 同时改"机制层"和"业务层" → R3

Always exits 0. Risk tracking is advisory, never blocking.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = REPO_ROOT / ".towow" / "state" / "risk-snapshot.json"

# ─── Risk level ordering ───
RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}

# ─── Path-based risk elevators (ADR-044 §4.4) ───
# Patterns: (path_prefix, minimum_risk)
# Uses startswith matching to avoid false positives from substring hits
# (e.g. "migration" in "docs/migration-guide.md").
RISK_ELEVATORS: list[tuple[str, str]] = [
    # R4: production side effects
    ("scripts/deploy", "R4"),
    ("backend/product/db/migration", "R4"),

    # R3: governance / hooks / CI / security
    ("CLAUDE.md", "R3"),
    (".claude/settings.json", "R3"),
    (".claude/skills/", "R3"),
    (".claude/rules/", "R3"),
    (".claude/agents/", "R3"),
    ("scripts/hooks/", "R3"),
    ("scripts/checks/", "R3"),
    (".github/", "R3"),

    # R2: public contracts
    ("backend/product/routes/", "R2"),
    ("backend/product/config.py", "R2"),
    ("backend/server.py", "R2"),
    ("docs/decisions/ADR-", "R2"),
    ("mcp-server/", "R2"),
    ("mcp-server-node/", "R2"),
    ("website/app/", "R2"),

    # R1: multi-file changes (handled separately)
]


def read_payload() -> dict:
    """Read CC PostToolUse hook stdin."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, OSError):
        return {}


def load_snapshot() -> dict:
    """Load existing risk snapshot, or default R0."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "risk_level": "R0",
        "risk_sources": [],
        "ratchet_locked": False,
        "files_touched": [],
    }


def save_snapshot(snap: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(snap, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def classify_file(file_path: str) -> str:
    """Return minimum risk level for a file path."""
    for pattern, risk in RISK_ELEVATORS:
        if file_path.startswith(pattern):
            return risk
    return "R0"


def main() -> int:
    payload = read_payload()

    # Extract file path from CC PostToolUse payload
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return 0

    # Make relative
    try:
        rel_path = str(Path(file_path).relative_to(REPO_ROOT))
    except ValueError:
        rel_path = file_path

    # Calculate risk for this file
    file_risk = classify_file(rel_path)

    # Load current snapshot
    snap = load_snapshot()
    current_level = snap.get("risk_level", "R0")
    current_order = RISK_ORDER.get(current_level, 0)
    new_order = RISK_ORDER.get(file_risk, 0)

    # Track file
    files_touched = snap.get("files_touched", [])
    if rel_path not in files_touched:
        files_touched.append(rel_path)

    # R1 escalation: 4+ files touched
    if len(files_touched) >= 4 and current_order < RISK_ORDER["R1"]:
        file_risk = "R1"
        new_order = RISK_ORDER["R1"]

    # Ratchet: only escalate, never de-escalate (§4.2)
    if new_order > current_order:
        snap["risk_level"] = file_risk
        snap["ratchet_locked"] = True
        snap["risk_sources"] = snap.get("risk_sources", [])
        snap["risk_sources"].append({
            "type": "path",
            "value": rel_path,
            "elevated_to": file_risk,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    snap["files_touched"] = files_touched
    snap["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    save_snapshot(snap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
