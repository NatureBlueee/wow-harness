#!/usr/bin/env python3
"""主窗口手动调用：mv unread → processed + 写 ack 文件回送 (PLAN-H9 §4.6 WP-06).

CLI 用法（由主 agent / Nature 在主窗口手动调用，**不是** CC hook）：

    python3 scripts/hooks/inbox-ack.py --msg-id <orig-msg-id> --sender <window-Hx>

参数说明：
- `--msg-id`：被 ack 的原消息 msg_id（match schema pattern `^(main|h[0-9])-[0-9]{8}-[0-9]{6}-[a-z0-9]{3,12}$`）
- `--sender`：原消息 sender window-Hx（ack 文件落到 `.towow/inbox/<sender>/acks/`）

行为：
1. 找原消息（先 unread/，回退 processed/），读 frontmatter 取 related_h
2. 反扫 `<sender>/acks/` 已有 ack：若有 frontmatter `ack_for == --msg-id` 的 ack
   文件 → 幂等退出（不重复写）
3. mv `main/unread/<msg-id>.md` → `main/processed/<msg-id>.md`（已 processed 则跳过）
4. 若步骤 2 无已有 ack：写新 ack 文件到 `<sender>/acks/<new-msg-id>.md`

ADR-058 §D1 / hook-output-schema 红线遵守：
- 不调用 `_hook_output` helper（CLI 工具，不是 hook，不出 stdout JSON）
- 无 banned form
- stderr 输出人类可读 error 信息（参数错误用，不是 hook decision）
- 顶层 try/except BaseException → sys.exit(0) 兜底
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INBOX_ROOT = REPO_ROOT / ".towow" / "inbox"
MAIN_UNREAD = INBOX_ROOT / "main" / "unread"
MAIN_PROCESSED = INBOX_ROOT / "main" / "processed"

VALID_SENDERS = frozenset(
    {f"window-h{n}" for n in (0, 1, 2, 3, 4, 5, 6, 8, 9)}
)


def _parse_frontmatter(text: str) -> dict:
    """最小 yaml frontmatter 解析（与 inbox-write-ledger / inbox-inject-on-start 同实现）。"""
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


def _find_existing_ack(acks_dir: Path, orig_msg_id: str) -> Path | None:
    """反扫 acks/，返回 frontmatter `ack_for == orig_msg_id` 且 `kind == ack` 的文件。"""
    if not acks_dir.exists():
        return None
    try:
        candidates = [p for p in acks_dir.iterdir() if p.suffix == ".md"]
    except OSError:
        return None
    for p in candidates:
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fm = _parse_frontmatter(text)
        if fm.get("kind") == "ack" and fm.get("ack_for") == orig_msg_id:
            return p
    return None


def _read_related_h(orig_msg_id: str) -> str:
    """从 unread/ 或 processed/ 取原消息 related_h；找不到 fallback H9（本 PLAN 自身）。"""
    for base in (MAIN_UNREAD, MAIN_PROCESSED):
        p = base / f"{orig_msg_id}.md"
        if p.exists():
            try:
                fm = _parse_frontmatter(p.read_text(encoding="utf-8"))
                related_h = fm.get("related_h", "")
                if related_h:
                    return related_h
            except (OSError, UnicodeDecodeError):
                continue
    return "H9"


def _gen_ack_msg_id(orig_msg_id: str) -> str:
    """格式：main-<YYYYMMDD>-<HHMMSS>-<6 char hash of orig>。

    用 sha256[:6] 而不是随机 hex：同秒重 ack 同 orig 生成同 msg_id → 直接撞名
    被 acks/ 已有文件捕获（Step 2 反扫），不会双写。
    """
    now = time.strftime("%Y%m%d-%H%M%S")
    suffix = hashlib.sha256(orig_msg_id.encode("utf-8")).hexdigest()[:6]
    return f"main-{now}-{suffix}"


def _write_ack(
    acks_dir: Path,
    ack_msg_id: str,
    orig_msg_id: str,
    related_h: str,
) -> Path:
    """写 ack 文件到 acks/<ack_msg_id>.md。schema-v1 兼容 frontmatter。"""
    acks_dir.mkdir(parents=True, exist_ok=True)
    ts_iso = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    ts_unix = int(time.time())
    pid = os.getpid()
    body = (
        "---\n"
        "sender: main\n"
        f"sender_pid: {pid}\n"
        f'ts: "{ts_iso}"\n'
        f"ts_unix: {ts_unix}\n"
        f"msg_id: {ack_msg_id}\n"
        "kind: ack\n"
        "priority: P2\n"
        f"related_h: {related_h}\n"
        "ack_required: false\n"
        f"ack_for: {orig_msg_id}\n"
        "---\n\n"
        f"主窗口已处理 {orig_msg_id}（mv unread → processed）。本文件是 ack 回执。\n"
    )
    dst = acks_dir / f"{ack_msg_id}.md"
    dst.write_text(body, encoding="utf-8")
    return dst


def main() -> int:
    parser = argparse.ArgumentParser(
        description="harness inbox ack (PLAN-H9 WP-06): mv unread→processed + write ack to <sender>/acks/",
    )
    parser.add_argument(
        "--msg-id",
        required=True,
        help="被 ack 的原消息 msg_id（schema pattern: main|h0..h9 prefix）",
    )
    parser.add_argument(
        "--sender",
        required=True,
        help="原消息 sender window-Hx；ack 文件落到 .towow/inbox/<sender>/acks/",
    )
    args = parser.parse_args()

    if args.sender not in VALID_SENDERS:
        sys.stderr.write(
            f"inbox-ack: invalid --sender {args.sender!r}; expected one of {sorted(VALID_SENDERS)}\n",
        )
        return 0

    orig_msg_id = args.msg_id
    src = MAIN_UNREAD / f"{orig_msg_id}.md"
    acks_dir = INBOX_ROOT / args.sender / "acks"

    # Step 1: 取原消息 related_h（unread/ → processed/ → fallback H9）
    related_h = _read_related_h(orig_msg_id)

    # Step 2: 幂等性反扫
    existing = _find_existing_ack(acks_dir, orig_msg_id)

    # Step 3: mv unread/ → processed/（已 processed 则 noop）
    if src.exists():
        try:
            MAIN_PROCESSED.mkdir(parents=True, exist_ok=True)
            dst = MAIN_PROCESSED / src.name
            if dst.exists():
                # 极少数同名碰撞（msg_id 幂等保证内容一致）：删 unread 副本
                src.unlink()
            else:
                src.rename(dst)
        except OSError as exc:
            sys.stderr.write(f"inbox-ack: mv unread→processed failed: {exc}\n")

    # Step 4: 写 ack（除非已存在）
    if existing is None:
        try:
            ack_msg_id = _gen_ack_msg_id(orig_msg_id)
            _write_ack(acks_dir, ack_msg_id, orig_msg_id, related_h)
        except OSError as exc:
            sys.stderr.write(f"inbox-ack: write ack failed: {exc}\n")
            return 0

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException:
        sys.exit(0)
