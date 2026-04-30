#!/usr/bin/env python3
"""WorktreeCreate — enforce H0.1 施工隔离: H-series worktrees must live in .worktrees/hanis-*/."""
from __future__ import annotations

import json
import re
import sys

_H_TOKEN = re.compile(r"(?:^|[/\-_])(hanis|H[0-9])(?:[/\-_]|$)", re.IGNORECASE)
_VALID_PREFIX = re.compile(r"(?:^|/)\.worktrees/hanis-[\w\-]+(?:/|$)")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, OSError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    path = str(payload.get("worktree_path") or payload.get("path") or "")
    if not path:
        return 0
    norm = path.replace("\\", "/")
    if not _H_TOKEN.search(norm):
        return 0
    if _VALID_PREFIX.search(norm):
        return 0
    sys.stderr.write(
        f"[wow-harness] H0.1 violation: H-series worktree '{path}' must be under .worktrees/hanis-*/\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
