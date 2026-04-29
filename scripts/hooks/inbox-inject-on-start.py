#!/usr/bin/env python3
"""
---
name: inbox-inject-on-start
window_owner: window-0-coordinator
window_owner_since: 2026-04-28T17:00+08:00
window_owner_adr: docs/decisions/ADR-H2-identity-isolation.md
---

SessionStart hook: H9 inbox unread inject + in-flight 残留清理 (PLAN-H9 §4.4 WP-04).

主窗口启动时：
  1. cwd / git-common 检测：必须在主仓 root（与 find-project-root.sh 等价语义）；
     不是则 silent return（subagent / 嵌套仓不应 inject）
  2. .towow/inbox/main/in-flight/ 残留 mv 回 unread/（§6.2 失败模式 2 处置：
     主窗口处理 unread→processed 中途崩溃，msg 还在 in-flight/，启动时回滚到
     unread/ 重新处理；msg_id 幂等，不会重复消费）
  3. 读 .towow/inbox/main/unread/*.md → 列出 sender / msg_id / kind / priority /
     ts / 正文摘要 ≤200 字，注入 additionalContext
  4. 总长度 ≤ 4096 字（CC SystemMessage 友好上限）；超额降级注入"unread overflow，
     请人工 archive"提示（不展开个体消息）

ADR-058 §D1 / hook-output-schema 红线遵守：
- 用 from _hook_output import session_start_inject（SessionStart schema-unverified
  helper，但仍是唯一合法 stdout JSON 出口）
- 无 banned form
- 顶层 try/except BaseException → sys.exit(0) 兜底

注：PLAN-H9 §4.4 spec "systemMessage" 是表述简称，落地形态是 CC SessionStart
hookSpecificOutput.additionalContext（与 §3 Fix-3 + ADR-058 §D1 一致）。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INBOX_ROOT = REPO_ROOT / ".towow" / "inbox"
MAIN_UNREAD = INBOX_ROOT / "main" / "unread"
MAIN_INFLIGHT = INBOX_ROOT / "main" / "in-flight"

MAX_INJECT_BYTES = 4096
BODY_PREVIEW_CHARS = 200


def _emit_inject(context: str) -> None:
    """走 _hook_output helper（唯一合法 stdout JSON 出口）。"""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from _hook_output import session_start_inject  # type: ignore
        session_start_inject(context)
    except Exception:  # noqa: BLE001
        pass


def _is_repo_root() -> bool:
    """与 find-project-root.sh §1 语义等价：cwd 在主仓 root（CLAUDE.md +
    scripts/guard-feedback.py 同时存在）。subagent / 嵌套仓不 inject。"""
    cwd = Path.cwd().resolve()
    if not (cwd / "CLAUDE.md").exists():
        return False
    if not (cwd / "scripts" / "guard-feedback.py").exists():
        return False
    # 与 REPO_ROOT 同一目录
    try:
        return cwd == REPO_ROOT.resolve()
    except OSError:
        return False


def _rollback_inflight() -> int:
    """把 in-flight/ 残留 mv 回 unread/。返回回滚条数。"""
    if not MAIN_INFLIGHT.exists():
        return 0
    rolled = 0
    try:
        candidates = [p for p in MAIN_INFLIGHT.iterdir() if p.suffix == ".md"]
    except OSError:
        return 0
    for src in candidates:
        try:
            dst = MAIN_UNREAD / src.name
            if dst.exists():
                # 已存在同名 (msg_id 幂等保证内容一致)：删 in-flight/ 副本即可
                src.unlink()
            else:
                MAIN_UNREAD.mkdir(parents=True, exist_ok=True)
                src.rename(dst)
            rolled += 1
        except OSError:
            continue
    return rolled


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    try:
        end = text.find("\n---", 3)
        if end < 0:
            return {}
        body = text[3:end].strip()
    except (ValueError, AttributeError):
        return {}
    out: dict[str, str] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def _extract_body_preview(text: str) -> str:
    """取 frontmatter 后的正文 ≤ BODY_PREVIEW_CHARS 字符。"""
    if not text.startswith("---"):
        return text[:BODY_PREVIEW_CHARS]
    try:
        end = text.find("\n---", 3)
        if end < 0:
            return ""
        body = text[end + 4 :].strip()
        return body[:BODY_PREVIEW_CHARS]
    except (ValueError, AttributeError):
        return ""


def _format_message(rel_path: str, fm: dict, preview: str) -> str:
    sender = fm.get("sender", "unknown")
    msg_id = fm.get("msg_id", "unknown")
    kind = fm.get("kind", "unknown")
    priority = fm.get("priority", "P?")
    ts = fm.get("ts", "")
    related_h = fm.get("related_h", "")
    related_wp = fm.get("related_wp", "")
    head = f"- [{priority}] {kind} from {sender} ({msg_id})"
    if related_h or related_wp:
        head += f" — {related_h}"
        if related_wp:
            head += f"/{related_wp}"
    if ts:
        head += f" @ {ts}"
    return f"{head}\n  body: {preview}"


def _build_inject_text(unread_files: list[Path]) -> str:
    if not unread_files:
        return ""

    sections: list[str] = []
    for p in unread_files:
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fm = _parse_frontmatter(text)
        preview = _extract_body_preview(text)
        rel = str(p.relative_to(REPO_ROOT)) if p.is_absolute() else str(p)
        sections.append(_format_message(rel, fm, preview))

    if not sections:
        return ""

    header = (
        f"[H9 inbox] {len(unread_files)} unread message(s) in .towow/inbox/main/unread/.\n"
        "Read each message file directly when ready; ack via "
        "`python3 scripts/hooks/inbox-ack.py --msg-id <id> --sender <window-Hx>`.\n"
    )
    full = header + "\n".join(sections)

    if len(full.encode("utf-8")) <= MAX_INJECT_BYTES:
        return full

    # 超额：降级提示
    return (
        f"[H9 inbox] {len(unread_files)} unread message(s) overflow inject budget "
        f"({MAX_INJECT_BYTES} bytes). Manual archive needed: see .towow/inbox/main/unread/. "
        "Move processed messages to .towow/inbox/main/processed/ and re-run."
    )


def main() -> int:
    # SessionStart payload 当前未使用业务字段；仍然消费 stdin 以避免 broken pipe
    try:
        sys.stdin.read()
    except OSError:
        pass

    if not _is_repo_root():
        return 0  # 非主仓（subagent / 嵌套仓）不 inject

    try:
        _rollback_inflight()
    except Exception:  # noqa: BLE001
        pass

    try:
        if not MAIN_UNREAD.exists():
            return 0
        unread = sorted(p for p in MAIN_UNREAD.iterdir() if p.suffix == ".md")
    except OSError:
        return 0

    inject_text = _build_inject_text(unread)
    if not inject_text:
        return 0  # 无消息：沉默（CC 可空 stdout）

    _emit_inject(inject_text)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException:
        sys.exit(0)
