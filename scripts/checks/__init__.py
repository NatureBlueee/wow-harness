"""Coherence check primitives."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Finding:
    severity: str  # "P0" | "P1" | "P2"
    message: str
    file: str  # relative path from repo root
    line: int | None = None
    blocking: bool = False
    category: str = "general"
    problem_class: str = "unknown"
    required_skills: list[str] = field(default_factory=list)
    required_reads: list[str] = field(default_factory=list)
