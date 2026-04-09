#!/usr/bin/env python3
"""sanitize-on-read.py — chokepoint_B runtime sanitizer (PreToolUse Read|Bash).

WP-11 deliverable. Scans file content BEFORE Claude reads it. Uses the
same regex classes as chokepoint_A (sanitize.py) via shared
scripts/lib/sanitize_patterns.py — single truth source, no INV-4 drift.

For Read tool: reads the target file, classifies lines.
For Bash tool: only activates on read-like commands (keywords from
  MANIFEST.yaml bash_read_keywords), then scans referenced file paths.

Exit codes:
  0   clean or degraded (PII/NETWORK/PROTOCOL_INTERNAL = warn, don't block)
  2   SECRET or TRADE_SECRET found → hard block

CC hook protocol: JSON to stdout with "decision" field.
  {"decision": "block", "reason": "..."} → Claude cannot read the file
  {"decision": "approve"}               → proceed normally

stdlib only per ADR-043 §7.4.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from lib import sanitize_patterns as sp  # noqa: E402

# Load bash_read_keywords from MANIFEST if available.
_MANIFEST_PATH = REPO_ROOT / ".wow-harness" / "MANIFEST.yaml"
BASH_READ_KEYWORDS: list[str] = []
try:
    import yaml as _yaml
    if _MANIFEST_PATH.exists():
        _m = _yaml.safe_load(_MANIFEST_PATH.read_text())
        BASH_READ_KEYWORDS = _m.get("bash_read_keywords", [])
except ImportError:
    # Fallback: hardcoded subset (MANIFEST is truth, this is degraded)
    BASH_READ_KEYWORDS = [
        "cat", "head", "tail", "less", "git log", "git show",
        "rg", "grep", "jq", "cut", "awk", "sed",
    ]

# Zero-width and bidi chars per ADR-043 §3.2.1 step 0.
_ZERO_WIDTH_RE = re.compile(
    "[\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff\U000e0000-\U000e007f\ufe00-\ufe0f]"
)
_BIDI_RE = re.compile("[\u202a-\u202e]")


def _strip_smuggling(text: str) -> str:
    """Step 0+1: strip zero-width + bidi chars, then NFKC normalize."""
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _BIDI_RE.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    return text


def _classify_line(line: str) -> list[str]:
    """Return list of Annex A.1 class names matching this line."""
    hits: list[str] = []
    for cls, patterns in sp.CLASS_PATTERNS.items():
        for pat in patterns:
            if pat.search(line):
                hits.append(cls)
                break
    return hits


def _arbitrate(hits: list[str]) -> str | None:
    """Pick highest-severity class per ADR-043 Annex A.1 line 1112."""
    for cls in sp.ARBITRATION_ORDER:
        if cls in hits:
            return cls
    return None


def _scan_text(text: str) -> tuple[str | None, list[dict]]:
    """Scan text, return (resolved_class, findings).

    resolved_class: highest-severity class found, or None if clean.
    findings: list of {line_num, classes, resolved} for reporting.
    """
    cleaned = _strip_smuggling(text)
    findings: list[dict] = []
    worst: str | None = None

    for i, line in enumerate(cleaned.splitlines(), 1):
        hits = _classify_line(line)
        if not hits:
            continue
        resolved = _arbitrate(hits)
        findings.append({"line": i, "classes": hits, "resolved": resolved})
        if resolved and (worst is None or
                         sp.ARBITRATION_ORDER.index(resolved) <
                         sp.ARBITRATION_ORDER.index(worst)):
            worst = resolved

    return worst, findings


def _is_read_command(command: str) -> bool:
    """Check if a Bash command is read-like (matches MANIFEST bash_read_keywords)."""
    cmd_lower = command.lower()
    return any(kw.lower() in cmd_lower for kw in BASH_READ_KEYWORDS)


def _extract_paths_from_command(command: str) -> list[Path]:
    """Best-effort extract file paths from a Bash read command."""
    paths: list[Path] = []
    for token in command.split():
        if token.startswith("-"):
            continue
        candidate = Path(token)
        if candidate.is_file():
            paths.append(candidate)
    return paths


def _read_file_safe(path: Path, max_bytes: int = 1_048_576) -> str | None:
    """Read a file, skip binary/huge files."""
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > max_bytes:
            return None
        with path.open("rb") as f:
            chunk = f.read(512)
            if b"\x00" in chunk:
                return None  # binary
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return None


def _output_decision(decision: str, reason: str = ""):
    """Write CC hook decision JSON to stdout."""
    result = {"decision": decision}
    if reason:
        result["reason"] = reason
    print(json.dumps(result))


def main() -> int:
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        _output_decision("approve")
        return 0

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Determine what to scan
    file_path: Path | None = None
    scan_paths: list[Path] = []

    if tool_name == "Read":
        raw_path = tool_input.get("file_path", "")
        if raw_path:
            file_path = Path(raw_path)
            scan_paths = [file_path]

    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if not _is_read_command(command):
            _output_decision("approve")
            return 0
        scan_paths = _extract_paths_from_command(command)
        if not scan_paths:
            # Command is read-like but we can't extract file paths
            # (e.g. piped commands) — allow, we can't pre-scan output
            _output_decision("approve")
            return 0

    else:
        _output_decision("approve")
        return 0

    # Scan all target files
    all_findings: list[dict] = []
    worst_overall: str | None = None

    for sp_path in scan_paths:
        text = _read_file_safe(sp_path)
        if text is None:
            continue
        worst, findings = _scan_text(text)
        if findings:
            for f in findings:
                f["file"] = str(sp_path)
            all_findings.extend(findings)
        if worst and (worst_overall is None or
                      sp.ARBITRATION_ORDER.index(worst) <
                      sp.ARBITRATION_ORDER.index(worst_overall)):
            worst_overall = worst

    if not all_findings:
        _output_decision("approve")
        return 0

    # Decision based on severity
    if worst_overall in ("SECRET", "TRADE_SECRET"):
        reason = (
            f"sanitize-on-read BLOCKED: {worst_overall} content detected in "
            f"{scan_paths[0] if scan_paths else 'unknown'}. "
            f"{len(all_findings)} finding(s). "
            "This file contains sensitive material that must not enter the AI context."
        )
        sys.stderr.write(f"[sanitize-on-read] {reason}\n")
        _output_decision("block", reason)
        return 2

    # PII / NETWORK / PROTOCOL_INTERNAL → warn but allow
    categories = {f["resolved"] for f in all_findings if f.get("resolved")}
    sys.stderr.write(
        f"[sanitize-on-read] WARNING: {categories} content in "
        f"{scan_paths[0] if scan_paths else 'unknown'} "
        f"({len(all_findings)} finding(s)). Allowed but logged.\n"
    )
    _output_decision("approve")

    # Write metrics event
    _write_metric(worst_overall, all_findings, scan_paths)
    return 0


def _write_metric(category: str | None, findings: list, paths: list[Path]):
    """Append sanitize event to metrics JSONL."""
    import time
    metrics_dir = REPO_ROOT / ".wow-harness" / "state" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": "sanitize_on_read",
        "category": category or "CLEAN",
        "file_path": str(paths[0]) if paths else "",
        "outcome": "block" if category in ("SECRET", "TRADE_SECRET") else "warn",
        "reason": f"{len(findings)} finding(s)",
    }
    with open(metrics_dir / "sanitize-events.jsonl", "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    sys.exit(main())
