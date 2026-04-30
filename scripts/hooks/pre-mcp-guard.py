#!/usr/bin/env python3
"""pre-mcp-guard.py — sanitize MCP tool arguments before execution.

Mirrors sanitize-on-read.py for the beforeMCPExecution hook surface. Walks
the MCP tool_input payload, classifies any string values via the canonical
sanitize_patterns lib, and blocks (exit 2) when SECRET / TRADE_SECRET hits
appear. PII / NETWORK / PROTOCOL_INTERNAL only warn.

Sensitive path heuristics (.env, *.pem, *.key, credentials, id_rsa) are
flagged as SECRET because the canonical regex set targets file content,
not file paths — MCP tool args frequently are paths to such files.

Exit codes:
  0   clean / unparseable / not an MCP event (fail-open on parse error)
  2   SECRET or TRADE_SECRET detected → block
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from lib import sanitize_patterns as sp  # noqa: E402

SENSITIVE_PATH_RE = re.compile(
    r"(?:(^|[\\/])\.env(\.|$)|\.pem$|\.key$|/id_rsa(\.|$)|credentials\.json$|bridge\.env$)",
    re.IGNORECASE,
)


def _walk_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_strings(v)


def _classify(text: str) -> str | None:
    for cls in sp.ARBITRATION_ORDER:
        for pat in sp.CLASS_PATTERNS.get(cls, []):
            if pat.search(text):
                return cls
    if SENSITIVE_PATH_RE.search(text):
        return "SECRET"
    return None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"permission": "allow"}))
        return 0

    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, (dict, list)):
        tool_input = payload

    worst: str | None = None
    sample: str = ""
    for s in _walk_strings(tool_input):
        cls = _classify(s)
        if cls and (worst is None or sp.ARBITRATION_ORDER.index(cls) < sp.ARBITRATION_ORDER.index(worst)):
            worst = cls
            sample = s[:120]
            if worst == "SECRET":
                break

    if worst in ("SECRET", "TRADE_SECRET"):
        tool_name = (payload or {}).get("tool_name", "<mcp>") if isinstance(payload, dict) else "<mcp>"
        reason = f"pre-mcp-guard BLOCKED: {worst} content in MCP tool args ({tool_name}). Sample: {sample!r}"
        sys.stderr.write(f"[pre-mcp-guard] {reason}\n")
        print(json.dumps({"permission": "deny", "user_message": reason, "agent_message": reason}, ensure_ascii=False))
        return 2

    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
