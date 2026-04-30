#!/usr/bin/env bash
# run-py.sh — cross-platform python resolver used by all runtime hooks.
# Resolves the first WORKING python interpreter and execs the given args.
# Order: WOW_HARNESS_PYTHON env override → python3 → python → py -3 (Windows)
#
# Probes each candidate with `--version` and skips if it fails or produces
# no output (this catches the Microsoft Store python3 launcher stub on
# Windows, which exits non-zero without printing anything).
set -e

_wow_probe() {
  local cmd="$1"
  local out
  out="$("$cmd" --version 2>&1)" || return 1
  [[ -z "$out" ]] && return 1
  return 0
}

_wow_try_exec() {
  local cmd="$1"; shift
  if command -v "$cmd" >/dev/null 2>&1 && _wow_probe "$cmd"; then
    exec "$cmd" "$@"
  fi
  return 1
}

if [[ -n "${WOW_HARNESS_PYTHON:-}" ]]; then
  _wow_try_exec "${WOW_HARNESS_PYTHON}" "$@" || true
fi
_wow_try_exec python3 "$@" || true
_wow_try_exec python  "$@" || true
if command -v py >/dev/null 2>&1; then
  exec py -3 "$@"
fi
echo "wow-harness: no working python interpreter found (tried WOW_HARNESS_PYTHON, python3, python, py -3)" >&2
exit 127
