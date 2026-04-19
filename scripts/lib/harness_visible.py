"""Append-only log for \"harness actually ran\" — human + machine readable.

Each line is one JSON object: ts, runtime, hook, optional detail.
Written under ``<repo>/.wow-harness/state/harness-visible.jsonl``.

Disable with env ``WOW_HARNESS_QUIET=1`` (truthy).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def _quiet() -> bool:
    v = os.environ.get("WOW_HARNESS_QUIET", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def append_touch(repo_root: Path, runtime: str, subcommand: str, **extra: object) -> None:
    """Best-effort append; never raises."""
    if _quiet() or repo_root is None:
        return
    try:
        state = repo_root / ".wow-harness" / "state"
        state.mkdir(parents=True, exist_ok=True)
        path = state / "harness-visible.jsonl"
        record: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "runtime": runtime,
            "hook": subcommand,
        }
        record.update(extra)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass
