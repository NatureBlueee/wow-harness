#!/usr/bin/env python3
"""PostToolUse hook: H9 inbox schema validate (PLAN-H9 §4.3 WP-03).

每次 Edit|Write 命中 .towow/inbox/**/*.md 后用 message-v1.json schema 校验
yaml frontmatter；不合规则把原文件 mv 到 .towow/inbox/quarantine/<basename>-<ts>.md
并 append 一行到 .towow/log/hook/inbox-quarantine.jsonl。

ack 类消息（kind=ack）额外要求 ack_for 字段（schema allOf 已涵盖；本 hook 仅依赖
schema validate 结果，不做 schema 之外的二次判断）。

非阻断：合规文件不动，不合规移走但 hook 仍 exit 0（CC PostToolUse 非零 exit = deny
→ 锁仓）；任何 IO / schema 校验异常吞掉 → exit 0。

ADR-058 §D1 / hook-output-schema 红线遵守：
- 不调用 _hook_output helper（PostToolUse 沉默 = no-op，模型对照 risk-tracker.py）
- 无 banned form（print(json.dumps) / json.dump(..., sys.stdout) / sys.stdout.write(json.dumps)）
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INBOX_ROOT = REPO_ROOT / ".towow" / "inbox"
SCHEMA_PATH = INBOX_ROOT / "schema" / "message-v1.json"
QUARANTINE_DIR = INBOX_ROOT / "quarantine"
QUARANTINE_LOG = REPO_ROOT / ".towow" / "log" / "hook" / "inbox-quarantine.jsonl"

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


def _classify_inbox_path(file_path: str) -> str | None:
    try:
        rel = Path(file_path).resolve().relative_to(INBOX_ROOT.resolve())
    except (ValueError, OSError):
        return None
    rel_str = str(rel)
    if rel_str.endswith(".gitkeep") or not rel_str.endswith(".md"):
        return None
    for prefix in EXCLUDED_PREFIXES:
        if rel_str.startswith(prefix):
            return None
    return rel_str


def _load_schema() -> dict | None:
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_frontmatter(text: str) -> tuple[dict, str | None]:
    """返回 (frontmatter_dict, error_reason or None)。

    使用 PyYAML 安全 loader；缺帧 / yaml 错均返回 ({}, reason)。
    """
    if not text.startswith("---"):
        return ({}, "no_frontmatter")
    try:
        end = text.find("\n---", 3)
        if end < 0:
            return ({}, "frontmatter_unterminated")
        body = text[3:end].strip()
    except (ValueError, AttributeError):
        return ({}, "frontmatter_parse_error")
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(body) or {}
        if not isinstance(data, dict):
            return ({}, "frontmatter_not_mapping")
        # PyYAML 隐式把 ISO 8601 timestamp / date 转为 datetime/date object，
        # 但 message-v1.json schema 把 ts/ts_unix 等定义为 string——必须 stringify。
        # 见 .claude/rules/hook-output-schema 注释 + ADR-H9 §4 类型契约段。
        normalized: dict = {}
        for k, v in data.items():
            if hasattr(v, "isoformat"):
                normalized[k] = v.isoformat()
            else:
                normalized[k] = v
        return (normalized, None)
    except Exception:
        return ({}, "yaml_load_error")


def _validate(fm: dict, schema: dict) -> str | None:
    """返回错误描述或 None（PASS）。"""
    try:
        import jsonschema  # type: ignore
        from jsonschema import Draft202012Validator
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(fm), key=lambda e: e.path)
        if not errors:
            return None
        first = errors[0]
        path = ".".join(str(p) for p in first.path) or "(root)"
        return f"{path}: {first.message}"
    except Exception as exc:  # noqa: BLE001 - hook 必须吞所有异常
        return f"validator_error: {type(exc).__name__}: {exc}"


def _append_jsonl(path: Path, record: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError):
        return


def _quarantine(src: Path, reason: str) -> Path | None:
    """mv src 到 quarantine/<basename>-<ts>.md，返回新路径或 None（mv 失败）。"""
    try:
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%dT%H%M%S")
        dst = QUARANTINE_DIR / f"{src.stem}-{ts}{src.suffix}"
        # 防同秒冲突：若 dst 已存在加随机后缀
        if dst.exists():
            import secrets
            dst = QUARANTINE_DIR / f"{src.stem}-{ts}-{secrets.token_hex(2)}{src.suffix}"
        src.rename(dst)
        return dst
    except OSError:
        return None


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

    src = Path(file_path)
    if not src.exists():
        return 0

    schema = _load_schema()
    if schema is None:
        # schema 加载失败：写 ledger 但不 quarantine（避免 schema bug 误伤合规消息）
        _append_jsonl(
            QUARANTINE_LOG,
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "ts_unix": int(time.time()),
                "rel_path": rel,
                "action": "skip",
                "reason": "schema_load_failed",
            },
        )
        return 0

    try:
        text = src.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    fm, fm_err = _parse_frontmatter(text)
    if fm_err is not None:
        validate_err = fm_err
    else:
        validate_err = _validate(fm, schema)

    if validate_err is None:
        return 0  # 合规：不动文件、不写 ledger（noise 控制）

    # 不合规：移到 quarantine/ 并落 ledger
    dst = _quarantine(src, validate_err)
    _append_jsonl(
        QUARANTINE_LOG,
        {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "ts_unix": int(time.time()),
            "rel_path": rel,
            "action": "quarantine" if dst else "quarantine_failed",
            "quarantine_path": str(dst.relative_to(REPO_ROOT)) if dst else None,
            "reason": validate_err,
            "msg_id": fm.get("msg_id", "unknown"),
            "sender": fm.get("sender", "unknown"),
            "kind": fm.get("kind", "unknown"),
        },
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException:
        sys.exit(0)
