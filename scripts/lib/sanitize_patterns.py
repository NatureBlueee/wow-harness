"""Single source of truth for Annex A.1 sanitization regex classes.

Consumers:
  - scripts/sanitize.py (WP-01b chokepoint_A fork-time)
  - scripts/hooks/sanitize-on-read.py (WP-11 chokepoint_B runtime)
  - scripts/ci/scan_verify_artifacts.py (WP-SEC-1 CI verifier)

Any regex drift between these consumers is an INV-4 truth-source split.
If you change a pattern here, run the full AC battery in all three WPs.

Class definitions mirror ADR-043 Annex A.1 line 1104-1110. Conflict
arbitration order is enforced by sanitize.py, not here:
  SECRET > TRADE_SECRET > PII > NETWORK > PROTOCOL_INTERNAL
"""

import re

# -------- SECRET (hard reject, integral-file) --------
# ADR-043 Annex A.1 line 1106. Include the specific prod IP 47.118.31.230
# as a SECRET sample (hardcoded prod infra is an info leak, not mere network).
SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-or-[A-Za-z0-9_-]{20,}"),
    re.compile(r"47\.118\.31\.230"),
    re.compile(r"CLAUDE_CODE_OAUTH_TOKEN\s*=\s*\S+"),
    re.compile(r"ANTHROPIC_API_KEY\s*=\s*\S+"),
    re.compile(r"OPENROUTER_API_KEY\s*=\s*\S+"),
    re.compile(r"SECONDME_CLIENT_(ID|SECRET)\s*=\s*\S+"),
    re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
]

# -------- TRADE_SECRET (hard reject by content + path blacklist) --------
# ADR-043 Annex A.1 line 1108. Path-based classification happens in
# sanitize.py by inspecting the file path; this regex list is the
# content-level signature for embedded references.
TRADE_SECRET_PATTERNS = [
    re.compile(r"ADR-017"),
    re.compile(r"ADR-018"),
    re.compile(r"ADR-040"),
    re.compile(r"PLAN-022"),
]
TRADE_SECRET_PATH_MARKERS = (
    "ADR-017",
    "ADR-018",
    "ADR-040",
    "PLAN-022",
    "bridge.env",
    "credentials.json",
)

# -------- PII (rename or strip) --------
# ADR-043 Annex A.1 line 1107. Real user handles from the Towow user pool.
PII_PATTERNS = [
    re.compile(r"Natalie\s*Xu"),
    re.compile(r"\u5764\u8d28"),
    re.compile(r"\u5f20\u6668\u66e6"),
    re.compile(r"[A-Za-z0-9_.+-]+@towow\.net"),
]

# -------- NETWORK (strip to placeholder) --------
# ADR-043 Annex A.1 line 1110 + line 1112 arbitration example. Note that
# 47.118.31.230 is intentionally registered under BOTH SECRET (hardcoded
# prod infra leak) and NETWORK (Alibaba Cloud IP geolocation signal).
# Line 1112 conflict example requires the fixture
# "https://47.118.31.230/formulation/xyz" to match SECRET + NETWORK +
# PROTOCOL_INTERNAL simultaneously (3 classes). Arbitration picks SECRET.
# Removing the duplicate below breaks WP-02 test 7 + WP-SEC-1 test 11
# categories.length >= 3 assertion.
NETWORK_PATTERNS = [
    re.compile(r"47\.118\.31\.230"),  # dual-registered per ADR line 1112
    re.compile(r"towow\.net(?:\.cn)?"),
    re.compile(r"/opt/towow/demos"),
]

# -------- PROTOCOL_INTERNAL (rename via dict) --------
# ADR-043 Annex A.1 line 1109 rename table.
RENAME_TABLE = {
    "formulation": "clarification-session",
    "nomination": "recommendation",
    "crystallization": "convergence",
    "discovery": "matching",
    "scenes/kunzhi-coach": "scenes/example-coach",
    "\u81ea\u822a\u8239": "example-coach",
}
PROTOCOL_INTERNAL_PATTERNS = [
    re.compile(re.escape(key)) for key in RENAME_TABLE
]

# -------- Arbitration order (most severe first) --------
# Used by sanitize.py to pick resolved_as when a line matches multiple classes.
ARBITRATION_ORDER = (
    "SECRET",
    "TRADE_SECRET",
    "PII",
    "NETWORK",
    "PROTOCOL_INTERNAL",
)

# Map class name -> compiled patterns for iteration.
CLASS_PATTERNS = {
    "SECRET": SECRET_PATTERNS,
    "TRADE_SECRET": TRADE_SECRET_PATTERNS,
    "PII": PII_PATTERNS,
    "NETWORK": NETWORK_PATTERNS,
    "PROTOCOL_INTERNAL": PROTOCOL_INTERNAL_PATTERNS,
}

# Placeholder strings used for strip-style classes.
PLACEHOLDERS = {
    "NETWORK": "<NETWORK_REDACTED>",
    "PII": "<PII_REDACTED>",
}
