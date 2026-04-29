#!/usr/bin/env python3
"""
---
name: inbox-write-ledger
window_owner: window-0-coordinator
window_owner_since: 2026-04-28T17:00+08:00
window_owner_adr: docs/decisions/ADR-H2-identity-isolation.md
---

PostToolUse hook: H9 inbox write ledger (PLAN-H9 §4.2 WP-02).

每次 Edit|Write 命中 .towow/inbox/**/*.md 后，把消息元数据 append 到
`.towow/log/hook/inbox-write.jsonl`；同时检测 main/unread/ 是否堆积
≥ INBOX_OVERFLOW_THRESHOLD（默认 50），若是则 append 到
`.towow/log/hook/inbox-overflow.jsonl`。

非阻断 hook（ledger only）—— 任何代码路径都必须返回 0：
  * stdin 解析失败、tool_input 缺 file_path → 直接 return 0
  * 路径不在 inbox/ scope（schema/、processed/、quarantine/、.gitkeep）→ return 0
  * 读文件 / parse yaml / 写 ledger 失败 → 吞异常，return 0

不调用 `_hook_output` helper：本 hook 设计上沉默（CC 对 PostToolUse 空
stdout 视为 no-op），无 additionalContext 注入需求。lint-hook-output.py
扫到本文件不会报 banned form（无 print(json.dumps) / 无 sys.stdout.write），
因此即便不 import 也不触发 BLOCK；这与 risk-tracker.py 的契约一致。

ADR-H9-mailbox §6.1 / PLAN-H9-mailbox §4.2 WP-02 是真相源。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INBOX_ROOT = REPO_ROOT / ".towow" / "inbox"
LEDGER_PATH = REPO_ROOT / ".towow" / "log" / "hook" / "inbox-write.jsonl"
OVERFLOW_PATH = REPO_ROOT / ".towow" / "log" / "hook" / "inbox-overflow.jsonl"
UNREAD_DIR = INBOX_ROOT / "main" / "unread"

# 阈值可由环境变量覆盖，便于演练 / 测试
INBOX_OVERFLOW_THRESHOLD = int(os.environ.get("INBOX_OVERFLOW_THRESHOLD", "50"))

# scope 排除表（前缀匹配 inbox 相对路径）
EXCLUDED_PREFIXES: tuple[str, ...] = (
    "schema/",
    "main/processed/",
    "main/in-flight/",
    "quarantine/",
)


def _read_payload() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _parse_frontmatter(text: str) -> dict:
    """最小 YAML frontmatter 解析；故意避开 PyYAML 依赖以保 hook 启动 < 50ms。

    只支持 key: value 单行 + 字符串/数字两种 scalar；够 message-v1 7 必填字段用。
    若 frontmatter 残缺 → 返回空 dict，调用方按 'unknown' 兜底。
    """
    if not text.startswith("---"):
        return {}
    try:
        end = text.find("\n---", 3)
        if end < 0:
            return {}
        body = text[3:end].strip()
    except (ValueError, AttributeError):
        return {}
    out: dict[str, str | int] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip().strip('"').strip("'")
        if val.isdigit():
            out[key.strip()] = int(val)
        else:
            out[key.strip()] = val
    return out


def _classify_inbox_path(file_path: str) -> str | None:
    """把绝对/工程相对路径标准化成 inbox 相对路径；out-of-scope → None。"""
    try:
        rel = Path(file_path).resolve().relative_to(INBOX_ROOT.resolve())
    except (ValueError, OSError):
        return None
    rel_str = str(rel)
    if rel_str.endswith("/.gitkeep") or rel_str.endswith(".gitkeep"):
        return None
    if not rel_str.endswith(".md"):
        return None
    for prefix in EXCLUDED_PREFIXES:
        if rel_str.startswith(prefix):
            return None
    return rel_str


def _append_jsonl(path: Path, record: dict) -> None:
    """jsonl append；任何 IO 异常吞掉（hook 不能 raise）。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except (OSError, TypeError, ValueError):
        return


def _check_overflow() -> None:
    try:
        if not UNREAD_DIR.exists():
            return
        unread_files = [p for p in UNREAD_DIR.iterdir() if p.suffix == ".md"]
        count = len(unread_files)
    except OSError:
        return
    if count < INBOX_OVERFLOW_THRESHOLD:
        return
    _append_jsonl(
        OVERFLOW_PATH,
        {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z") or time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ts_unix": int(time.time()),
            "unread_count": count,
            "threshold": INBOX_OVERFLOW_THRESHOLD,
            "kind": "overflow",
        },
    )


def main() -> int:
    payload = _read_payload()
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        return 0
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "") or ""
    if not file_path:
        return 0
    rel = _classify_inbox_path(file_path)
    if rel is None:
        return 0

    # 读文件 + frontmatter（best-effort）
    fm: dict = {}
    size_bytes = 0
    try:
        p = Path(file_path)
        if p.exists():
            text = p.read_text(encoding="utf-8")
            size_bytes = len(text.encode("utf-8"))
            fm = _parse_frontmatter(text)
    except (OSError, UnicodeDecodeError):
        pass

    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z") or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ts_unix": int(time.time()),
        "rel_path": rel,
        "tool": tool_name,
        "size_bytes": size_bytes,
        "sender": fm.get("sender", "unknown"),
        "msg_id": fm.get("msg_id", "unknown"),
        "kind": fm.get("kind", "unknown"),
        "priority": fm.get("priority", "unknown"),
        "related_h": fm.get("related_h", "unknown"),
    }
    _append_jsonl(LEDGER_PATH, record)
    _check_overflow()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException:
        # 顶层 catch-all：任何意外都不能让 CC 拿到非零 exit（非零 = deny → 工作流锁死）
        sys.exit(0)
