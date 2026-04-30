#!/usr/bin/env python3
"""UserPromptSubmit — inject context fragments at prompt time (not just session start).

Reads JSON from stdin (Claude Code format: ``{"prompt": "...", ...}``).
Lightly scans the prompt for repo-relative file path tokens and routes them
through ``scripts.context_router`` to inject the matching fragments. If no
path-like tokens are found, prints a single banner line so the prompt still
sees a "wow-harness active" signal.

Always exit 0 — never block prompt submission.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Token that looks like a repo-relative path: at least one slash, no spaces,
# made of path-safe chars. Permits leading ``./``.
_PATH_RE = re.compile(r"(?:\./)?[\w\-./]+/[\w\-./]+")


def _extract_paths(prompt: str) -> list[str]:
    if not prompt:
        return []
    seen: list[str] = []
    for tok in _PATH_RE.findall(prompt):
        cleaned = tok.lstrip("./")
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen[:8]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, OSError, ValueError):
        payload = {}

    prompt = ""
    if isinstance(payload, dict):
        prompt = str(payload.get("prompt") or payload.get("user_prompt") or "")

    fragments_emitted: list[str] = []
    try:
        from scripts.context_router import load_fragment, match  # noqa: WPS433
    except Exception:
        load_fragment = None  # type: ignore[assignment]
        match = None  # type: ignore[assignment]

    if match is not None and load_fragment is not None:
        seen: set[str] = set()
        for path in _extract_paths(prompt):
            for name in match(path):
                if name in seen:
                    continue
                seen.add(name)
                text = load_fragment(name)
                if text:
                    fragments_emitted.append(f"### context-fragment: {name}\n\n{text}")

    if fragments_emitted:
        print("## wow-harness routed context\n")
        print("\n\n---\n\n".join(fragments_emitted))
    else:
        print("[wow-harness] active (UserPromptSubmit) — fragments injected on file-path mention")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
