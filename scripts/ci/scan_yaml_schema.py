#!/usr/bin/env python3
"""scan_yaml_schema.py — ban command-templating keys in harness YAML/JSON configs.

Rationale (ADR-043 §3.2.2):
  All hook commands in .claude/settings.json MUST be literal shell strings.
  Any key that implies runtime templating (``cmd_template``, ``exec``,
  ``shell_template``, ``command_template``) opens an injection lane where
  an attacker who can edit the config executes arbitrary code via the hook.

Usage:
  python3 scripts/ci/scan_yaml_schema.py <file1> [<file2> ...]

Exit codes:
  0 — all files clean
  2 — at least one banned key found (or parse error)

Accepts both .yaml and .json (YAML 1.2 is a JSON superset, so ``yaml.safe_load``
handles JSON transparently — this is why we can point the scanner at
.claude/settings.json as AC 4 requires).
"""
from __future__ import annotations

import sys

try:
    import yaml
except ImportError:
    print("scan_yaml_schema.py: PyYAML not installed", file=sys.stderr)
    sys.exit(2)

BANNED_KEYS = {"cmd_template", "exec", "shell_template", "command_template"}


def walk(node, path=""):
    """Yield banned-key hits as 'path.key' strings."""
    if isinstance(node, dict):
        for k, v in node.items():
            key_path = f"{path}.{k}" if path else k
            if k in BANNED_KEYS:
                yield key_path
            yield from walk(v, key_path)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")


def scan(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"{path}: parse error — {e}", file=sys.stderr)
        return 2

    hits = list(walk(data))
    if hits:
        for h in hits:
            print(f"{path}: BANNED KEY at {h}", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    files = sys.argv[1:]
    if not files:
        print("usage: scan_yaml_schema.py <file>...", file=sys.stderr)
        return 2
    rc = 0
    for f in files:
        if scan(f) != 0:
            rc = 2
    return rc


if __name__ == "__main__":
    sys.exit(main())
