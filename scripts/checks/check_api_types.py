"""Check API type consistency between Pydantic models and generated TypeScript.

Verifies that generated/api-types.ts is up-to-date with backend models.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.checks import Finding

_TS_INTERFACE = re.compile(r'export interface (\w+) \{')
_TS_FIELD = re.compile(r'^\s+(\w+)\??\s*:\s*(.+);', re.MULTILINE)


def run(repo_root: Path, mode: str = "full") -> list[Finding]:
    findings: list[Finding] = []

    ts_file = repo_root / "generated" / "api-types.ts"
    if not ts_file.exists():
        findings.append(Finding(
            severity="P1",
            message="generated/api-types.ts does not exist — run scripts/export_api_types.py",
            file="generated/api-types.ts",
        ))
        return findings

    content = ts_file.read_text(encoding="utf-8")
    interfaces = _TS_INTERFACE.findall(content)

    if not interfaces:
        findings.append(Finding(
            severity="P1",
            message="generated/api-types.ts contains no interfaces",
            file="generated/api-types.ts",
        ))
        return findings

    # Try importing backend models to compare
    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    try:
        from product.routes.protocol import ProtocolAgentResponse
        # Compare ProtocolAgentResponse fields with TypeScript
        py_fields = set(ProtocolAgentResponse.model_fields.keys())

        # Extract TS fields for ProtocolAgentResponse
        ts_block = re.search(
            r'export interface ProtocolAgentResponse \{([^}]+)\}',
            content,
        )
        if ts_block:
            ts_fields = set(_TS_FIELD.findall(ts_block.group(1)))
            ts_field_names = {f[0] for f in ts_fields}

            py_only = py_fields - ts_field_names
            ts_only = ts_field_names - py_fields

            for f in sorted(py_only):
                findings.append(Finding(
                    severity="P1",
                    message=f"ProtocolAgentResponse field '{f}' in Pydantic but not in TypeScript",
                    file="generated/api-types.ts",
                ))
            for f in sorted(ts_only):
                findings.append(Finding(
                    severity="P1",
                    message=f"ProtocolAgentResponse field '{f}' in TypeScript but not in Pydantic",
                    file="generated/api-types.ts",
                ))

    except (ImportError, TypeError):
        findings.append(Finding(
            severity="P2",
            message="Cannot import backend models for comparison (Python 3.10+ required)",
            file="backend/product/routes/protocol.py",
        ))

    return findings


if __name__ == "__main__":
    results = run(_REPO_ROOT)
    for f in results:
        loc = f"{f.file}:{f.line}" if f.line else f.file
        print(f"[{f.severity}] {loc}: {f.message}")
    print(f"\n--- {len(results)} findings ---")
    sys.exit(1 if any(f.severity == "P0" for f in results) else 0)
