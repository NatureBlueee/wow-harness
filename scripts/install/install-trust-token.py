#!/usr/bin/env python3
"""install-trust-token.py — HMAC sign/verify for install trust chain (v2 patch_2).

Trust token lifecycle:
  1. sign()   — installer creates token at start of phase2_auto.py
  2. verify() — each install step verifies token is still valid
  3. refresh() — successful steps refresh sliding_deadline

Security model:
  - HMAC key from env WOW_HARNESS_INSTALL_HMAC_KEY (禁止 file-based key)
  - Key must be >= 32 bytes raw (hex >= 64 chars)
  - sliding_deadline: now+30min, refreshed on each successful step
  - absolute_deadline: now+6h, never refreshed
  - expired → fail-closed, no renewal

stdlib only per ADR-043 §7.4.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

TOKEN_FILE = ".wow-harness/install-trust-token.json"
ENV_KEY = "WOW_HARNESS_INSTALL_HMAC_KEY"
MIN_KEY_HEX_LEN = 64  # 32 bytes = 64 hex chars
SLIDING_WINDOW_SEC = 30 * 60  # 30 minutes
ABSOLUTE_WINDOW_SEC = 6 * 60 * 60  # 6 hours


def _get_key() -> bytes:
    """Read HMAC key from env. Fail-closed if missing or too short."""
    raw = os.environ.get(ENV_KEY, "")
    if not raw:
        print(
            f"fail-closed: {ENV_KEY} not set. "
            "Generate one with: export WOW_HARNESS_INSTALL_HMAC_KEY=$(openssl rand -hex 32)",
            file=sys.stderr,
        )
        sys.exit(2)
    if len(raw) < MIN_KEY_HEX_LEN:
        print(
            f"fail-closed: insufficient entropy in {ENV_KEY} "
            f"(got {len(raw)} hex chars, need >= {MIN_KEY_HEX_LEN}). "
            "Generate one with: openssl rand -hex 32",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        return bytes.fromhex(raw)
    except ValueError:
        print(
            f"fail-closed: {ENV_KEY} is not valid hex. "
            "Generate one with: openssl rand -hex 32",
            file=sys.stderr,
        )
        sys.exit(2)


def _compute_mac(key: bytes, payload: dict) -> str:
    """HMAC-SHA256 of the canonical JSON payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(key, canonical.encode(), hashlib.sha256).hexdigest()


def sign(repo_root: Path) -> Path:
    """Create a new install trust token. Returns path to token file."""
    key = _get_key()
    now = time.time()
    payload = {
        "issued_at": now,
        "sliding_deadline": now + SLIDING_WINDOW_SEC,
        "absolute_deadline": now + ABSOLUTE_WINDOW_SEC,
        "repo_root": str(repo_root.resolve()),
    }
    mac = _compute_mac(key, payload)
    token = {"payload": payload, "mac": mac}
    token_path = repo_root / TOKEN_FILE
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(token, indent=2) + "\n")
    return token_path


def verify(repo_root: Path) -> dict:
    """Verify install trust token. Returns payload if valid, exits 2 if not."""
    key = _get_key()
    token_path = repo_root / TOKEN_FILE
    if not token_path.exists():
        print("fail-closed: install-trust-token.json not found", file=sys.stderr)
        sys.exit(2)

    try:
        token = json.loads(token_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"fail-closed: cannot read trust token: {e}", file=sys.stderr)
        sys.exit(2)

    payload = token.get("payload", {})
    stored_mac = token.get("mac", "")
    expected_mac = _compute_mac(key, payload)

    if not hmac.compare_digest(stored_mac, expected_mac):
        print("fail-closed: trust token MAC verification failed", file=sys.stderr)
        sys.exit(2)

    now = time.time()
    if now > payload.get("absolute_deadline", 0):
        print(
            "fail-closed: trust token absolute deadline expired (6h hard limit). "
            "Re-run the installer to start fresh.",
            file=sys.stderr,
        )
        sys.exit(2)

    if now > payload.get("sliding_deadline", 0):
        print(
            "fail-closed: trust token sliding deadline expired (30min idle). "
            "Re-run the installer to start fresh.",
            file=sys.stderr,
        )
        sys.exit(2)

    return payload


def refresh(repo_root: Path):
    """Refresh sliding deadline after a successful step."""
    key = _get_key()
    token_path = repo_root / TOKEN_FILE
    token = json.loads(token_path.read_text())
    payload = token["payload"]
    payload["sliding_deadline"] = time.time() + SLIDING_WINDOW_SEC
    token["mac"] = _compute_mac(key, payload)
    token_path.write_text(json.dumps(token, indent=2) + "\n")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("sign")
    sub.add_parser("verify")
    sub.add_parser("refresh")
    args = parser.parse_args()

    repo_root = Path.cwd()
    if args.cmd == "sign":
        p = sign(repo_root)
        print(f"Token signed: {p}")
    elif args.cmd == "verify":
        payload = verify(repo_root)
        print(f"Token valid. Expires: absolute={payload['absolute_deadline']}")
    elif args.cmd == "refresh":
        refresh(repo_root)
        print("Sliding deadline refreshed.")
    else:
        parser.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
