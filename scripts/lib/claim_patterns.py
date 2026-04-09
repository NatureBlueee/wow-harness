"""Shared INV-4 claim regex (single source of truth).

Producer: WP-04 of PLAN-086 (first consumer owns the shared lib, closing
Gate 6 Round 2's arch-reviewer finding about INV-7 shared-lib-no-owner).

Consumers:
  - scripts/checks/check_file_existence_claims.py (first consumer)
  - scripts/checks/check_doc_file_references.py
  - scripts/ci/scan_verify_artifacts.py (WP-SEC-1, future)

Rationale for centralization: INV-4 ("truth source split") is itself
prevented by not splitting the regex definitions across multiple files.
If these patterns were duplicated in each consumer, a change to one would
silently diverge from the others. Same bug, different file. So this
module IS the claim pattern truth source.

Regex design notes:
  - `negative_patterns` match claims that something does NOT exist or has
    been removed. The check then asserts the referenced path is actually
    absent.
  - `positive_patterns` match claims that something DOES exist or has been
    deployed. The check then asserts the path is actually present AND has
    at least one commit in git history (defends against "vapor deploy":
    claiming deployment for a file that was never committed).
  - `doc_ref_pattern` matches backtick-wrapped paths in markdown/docs:
    `docs/**`, `scripts/**`, or `arXiv:<id>`. The check then asserts
    filesystem existence (or for arXiv IDs: reachability, with local skip).
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Negative existence claims ("this is gone / doesn't exist / verified absent")
# ---------------------------------------------------------------------------
# Match phrases like:
#   - 经核实不存在: scripts/foo.py
#   - 已删除 `backend/old.py`
#   - grep-verified: docs/legacy.md
#   - 确认不存在：scripts/bar.sh
#   - not found in repo: path/to/file
#
# Captures: (marker, path)
NEGATIVE_CLAIM_RE = re.compile(
    r"(经核实不存在|已删除|grep-?verified|确认不存在|not found in repo)"
    r"\s*[:：]?\s*`?([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+)`?",
    re.UNICODE,
)

# ---------------------------------------------------------------------------
# Positive existence claims ("this is shipped / deployed / wired up")
# ---------------------------------------------------------------------------
# This is the half we missed in rounds 1-4 of PLAN-086 INV-4 activations:
# "经核实不存在" was caught by humans, but "已部署 scripts/fake.sh" slid
# through because nobody thought to verify *positive* claims. Round 5
# (§13.5 of ADR-043) added this lane.
#
# Match phrases like:
#   - 已部署 scripts/ci/deploy.sh
#   - 已接入：`backend/api/new.py`
#   - now live: scripts/prod.sh
#   - deployed: infra/terraform/main.tf
#   - verified in CI: scripts/ci/check.sh
#   - is enforced: scripts/hooks/guard.py
#   - wired up: backend/routes/new.py
POSITIVE_CLAIM_RE = re.compile(
    r"(已部署|已接入|已落地|now live|deployed|verified in CI|is enforced|now wire-?up|wired up)"
    r"\s*[:：]?\s*`?([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+)`?",
    re.UNICODE,
)

# ---------------------------------------------------------------------------
# Doc-level path references (backtick-quoted paths and arXiv IDs)
# ---------------------------------------------------------------------------
# Match patterns like `docs/foo/bar.md`, `scripts/checks/x.py`,
# `arXiv:2603.05344`. Only backtick-wrapped to avoid accidentally matching
# prose like "see docs for details".
DOC_REF_RE = re.compile(
    r"`((?:docs|scripts|backend|frontend|website|mcp-server|\.claude)/[^`\s]+"
    r"|arXiv:[0-9]{4}\.[0-9]{4,5})`"
)


def iter_negative_claims(text: str):
    """Yield (marker, path) tuples for every negative existence claim."""
    for m in NEGATIVE_CLAIM_RE.finditer(text):
        yield m.group(1), m.group(2)


def iter_positive_claims(text: str):
    """Yield (marker, path) tuples for every positive existence claim."""
    for m in POSITIVE_CLAIM_RE.finditer(text):
        yield m.group(1), m.group(2)


def iter_doc_refs(text: str):
    """Yield each backtick-wrapped doc reference (path or arXiv id)."""
    for m in DOC_REF_RE.finditer(text):
        yield m.group(1)


__all__ = [
    "NEGATIVE_CLAIM_RE",
    "POSITIVE_CLAIM_RE",
    "DOC_REF_RE",
    "iter_negative_claims",
    "iter_positive_claims",
    "iter_doc_refs",
]
