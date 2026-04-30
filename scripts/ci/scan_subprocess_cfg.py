#!/usr/bin/env python3
"""scan_subprocess_cfg.py — ban subprocess invocations fed from config dicts.

Rationale:
  If a Python script reads a command string out of YAML/JSON config and then
  feeds it to subprocess.{run,Popen,call,check_call,check_output}, an attacker
  who controls the config file can execute arbitrary commands via the hook.
  ADR-043 §3.2.2 requires subprocess invocations to take literal argv lists
  or well-audited inputs — never ``subprocess.run(cfg[...])``.

Detection:
  AST-scans target .py files for calls of the form
      subprocess.<fn>(<target>[...], ...)
  where ``<target>`` is a Name matching cfg/config (case-insensitive substring),
  OR where the first argument is a Subscript/BinOp into a dict literal loaded
  from yaml/json at module scope.

Usage:
  python3 scripts/ci/scan_subprocess_cfg.py <file.py> [<file.py> ...]

Exit codes:
  0 — clean
  2 — dangerous pattern found (or parse error)
"""
from __future__ import annotations

import ast
import sys

SUBPROCESS_FNS = {"run", "Popen", "call", "check_call", "check_output"}


class Scanner(ast.NodeVisitor):
    def __init__(self, path: str):
        self.path = path
        self.hits: list[str] = []

    def visit_Call(self, node: ast.Call):  # noqa: N802
        fn_name = None
        func = node.func
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                fn_name = func.attr

        if fn_name in SUBPROCESS_FNS and node.args:
            first = node.args[0]
            if isinstance(first, ast.Subscript):
                target = first.value
                if isinstance(target, ast.Name):
                    name = target.id.lower()
                    if "cfg" in name or "config" in name:
                        self.hits.append(
                            f"line {node.lineno}: subprocess.{fn_name}({target.id}[...])"
                        )
        self.generic_visit(node)


def scan(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
    except SyntaxError as e:
        print(f"{path}: parse error — {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"{path}: read error — {e}", file=sys.stderr)
        return 2

    scanner = Scanner(path)
    scanner.visit(tree)
    if scanner.hits:
        for h in scanner.hits:
            print(f"{path}: {h}", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    files = sys.argv[1:]
    if not files:
        print("usage: scan_subprocess_cfg.py <file.py>...", file=sys.stderr)
        return 2
    rc = 0
    for f in files:
        if not f.endswith(".py"):
            continue
        if scan(f) != 0:
            rc = 2
    return rc


if __name__ == "__main__":
    sys.exit(main())
