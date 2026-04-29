#!/usr/bin/env python3
"""Context Router — 文件路径 → 上下文片段路由表。

ADR-030 机制 A（主动投影）的核心。根据被编辑文件的路径，
确定性地返回该文件相关的上下文片段名列表。

Usage:
    from scripts.context_router import match, load_fragment, FALLBACK_FRAGMENTS

    fragments = match("bridge_agent/agent.py")
    # → ["bridge-constitution"]
"""
from __future__ import annotations

import os
from pathlib import Path

FRAGMENTS_DIR = Path(__file__).resolve().parent / "context-fragments"
_FRAGMENTS_DIR_RESOLVED = FRAGMENTS_DIR.resolve()

# ── 路由表：文件路径前缀 → 上下文片段名列表 ──
# 完全按 ADR-030 Section 3.4.1 定义
CONTEXT_MAP: dict[str, list[str]] = {
    # Bridge
    "bridge_agent/":                        ["bridge-constitution"],
    "backend/product/bridge/":              ["bridge-constitution"],

    # MCP 双端
    "mcp-server/":                          ["mcp-parity"],
    "mcp-server-node/":                     ["mcp-parity"],

    # 协议 API（多消费方契约）
    "backend/product/routes/protocol.py":   ["protocol-consumers", "contract-consumers"],
    "backend/product/protocol/":            ["protocol-consumers"],

    # API 路由层（契约定义点）
    "backend/product/routes/":              ["contract-consumers"],

    # run_events（6 个消费方的共享结构）
    "backend/product/db/crud_events.py":    ["run-events-consumers"],

    # 认证（消费方安全约定 + SecondMe OAuth）
    "backend/product/auth/":                ["auth-consumers"],

    # DB 层（共享数据结构约定）
    "backend/product/db/":                  ["db-shared-structures"],

    # 分布式协商核心
    "backend/product/catalyst/":            ["catalyst-distributed"],

    # Issue / 修复
    "docs/issues/":                         ["fixed-three-layers", "closure-checklist"],

    # 场景
    "scenes/":                              ["scene-fidelity", "two-language"],
    "website/app/[scene]/":                 ["scene-fidelity", "two-language"],
    "website/components/scene/":            ["scene-fidelity", "two-language"],

    # 真相源文件
    "CLAUDE.md":                            ["truth-source-hierarchy"],
    "MEMORY.md":                            ["truth-source-hierarchy"],
    "docs/INDEX.md":                        ["truth-source-hierarchy"],

    # 版本号
    "mcp-server/pyproject.toml":            ["version-sources"],
    "mcp-server-node/package.json":         ["version-sources"],

    # 前端通用
    "website/":                             ["two-language"],

    # 文档
    "docs/decisions/":                      ["artifact-linkage"],

    # Issue-first 工作流 — 编辑业务代码时提醒先建 issue
    "backend/product/":                     ["issue-first"],
    "backend/server.py":                    ["issue-first"],
    "mcp-server/towow_mcp/":               ["issue-first"],
    "mcp-server-node/src/":                ["issue-first"],
    "website/app/":                         ["issue-first"],
}

# 未匹配任何路由的文件，由 guard-feedback.py 注入此 fallback
FALLBACK_FRAGMENTS = ["general-dev-principles"]


def match(file_path: str) -> list[str]:
    """返回匹配的上下文片段名列表。最长前缀优先，去重保序。

    契约：输入必须是已规范化的 repo-relative path。包含 ``..``
    traversal 或绝对路径的输入会被拒绝，返回空列表——防止
    ``backend/product/../../../../etc/passwd`` 这类路径冒充
    ``backend/product/`` 前缀匹配。

    See: docs/issues/guard-20260405-0110-guard-feedback-path-escape.md
    """
    if not file_path:
        return []
    # 拒绝绝对路径
    if os.path.isabs(file_path):
        return []
    # Normalize 并拒绝 .. traversal
    normalized = os.path.normpath(file_path).replace(os.sep, "/")
    if normalized.startswith("../") or normalized == ".." or "/../" in normalized:
        return []

    matched: list[str] = []
    for pattern, fragments in sorted(
        CONTEXT_MAP.items(), key=lambda x: -len(x[0])
    ):
        if normalized.startswith(pattern) or normalized.endswith(pattern):
            matched.extend(fragments)
    # 去重保序
    return list(dict.fromkeys(matched))


def load_fragment(name: str) -> str:
    """加载片段文件内容。返回空字符串如果文件不存在或路径越界。

    契约：``name`` 经拼接 + ``.md`` 后必须位于 ``FRAGMENTS_DIR`` 内。
    ``resolve()`` 后再校验 containment，防止 ``../../etc/passwd`` 之类
    的 name 逃逸到 fragments 目录以外。

    See: docs/issues/guard-20260405-0110-guard-feedback-path-escape.md
    """
    if not name:
        return ""
    candidate = (FRAGMENTS_DIR / f"{name}.md")
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError):
        return ""
    # 必须仍在 FRAGMENTS_DIR 内（containment check）
    try:
        resolved.relative_to(_FRAGMENTS_DIR_RESOLVED)
    except ValueError:
        return ""
    if resolved.is_file():
        return resolved.read_text(encoding="utf-8").strip()
    return ""
