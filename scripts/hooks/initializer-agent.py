#!/usr/bin/env python3
"""Initializer Agent — WP 启动时生成严格 schema 的 progress.json

[来源: ADR-038 D8 + Anthropic "Effective Harnesses for Long-Running Agents"
       — 严格 JSON 防自改 + 单特性/会话约束]

核心设计：
1. progress.json 是 WP 进度的**机械化真相源**
2. `objective` 字段写入后 read-only（SHA256 hash 校验，绕过即失败）
3. `status` 字段是严格枚举：failing / passing / blocked
4. Stop hook 读 progress.json 做机械化第一关（零 LLM 成本）
5. precompact.sh 读 progress.json 做 Objective Recitation

CLI 接口（被 dev skill / Initializer Agent 调用）：
    # 1. 初始化 WP（写入后 objective 不可改）
    initializer-agent.py init --wp-id WP-XXX --json-file plan.json

    # 2. 更新 feature 状态
    initializer-agent.py update --feature F1 --status passing --evidence "..."

    # 3. 查询当前状态（机器可读）
    initializer-agent.py status [--wp-id WP-XXX] [--json]

    # 4. 校验 schema 与不变量
    initializer-agent.py validate

    # 5. Stop hook 用：检查所有 feature 是否 passing（exit 0=ok / exit 1=fail）
    initializer-agent.py stop-check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROGRESS_DIR = REPO_ROOT / ".towow" / "progress"
CURRENT_LINK = PROGRESS_DIR / "current.json"
OBJECTIVE_HASH_DIR = PROGRESS_DIR / ".objective_hashes"
METRICS_DIR = REPO_ROOT / ".towow" / "metrics"

VALID_STATUSES = {"failing", "passing", "blocked"}
SCHEMA_VERSION = "v4.1-d8-steps"  # v4 → v4.1: 加入 Anthropic 第二篇 steps[] + verification_command + evidence 强制

# D24 (meta-review fix): Anthropic 第二篇 effective-harnesses 文章的 feature 完整 schema
# 包含 category / description / steps[] / passes (我们用 status enum 替代 passes boolean)
# 我们在此基础上加 ADR §4 D8.1 的 verification_command + evidence，超越 Anthropic 原文
OPTIONAL_FEATURE_FIELDS = {
    "category": str,           # Anthropic: e.g. "functional" / "ux" / "performance"
    "description": str,         # Anthropic: 比 subject 更长的人话描述
    "steps": list,              # Anthropic 核心: 可机械化验证的步骤序列
    "verification_command": str,  # ADR §4 D8.1: 怎么跑 steps（pytest 命令等）
    "evidence": str,            # ADR §4 D8.1: 验证后填的产物引用
}


# ─── Metrics (ADR-038 D1) ───────────────────────────────────────────────────


def emit_metric(event: str, **data: Any) -> None:
    """Append a JSONL metric line. Never raises."""
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "session_pid": os.getppid(),
            "event": event,
            **data,
        }
        with open(METRICS_DIR / "initializer-events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ─── Schema validation ──────────────────────────────────────────────────────


def validate_schema(data: dict, *, strict: bool = True) -> tuple[bool, list[str]]:
    """Validate progress.json schema. Returns (ok, errors)."""
    errors: list[str] = []

    required = ["wp_id", "objective", "features"]
    for field in required:
        if field not in data:
            errors.append(f"missing required field: {field}")

    if not errors:
        if not isinstance(data["wp_id"], str) or not data["wp_id"]:
            errors.append("wp_id must be non-empty string")
        if not isinstance(data["objective"], str) or not data["objective"]:
            errors.append("objective must be non-empty string")
        if not isinstance(data["features"], list):
            errors.append("features must be list")
        elif not data["features"] and strict:
            errors.append("features list cannot be empty")

        for i, feat in enumerate(data.get("features", [])):
            if not isinstance(feat, dict):
                errors.append(f"features[{i}] must be dict")
                continue
            for f in ["id", "subject", "status"]:
                if f not in feat:
                    errors.append(f"features[{i}] missing {f}")
            if "status" in feat and feat["status"] not in VALID_STATUSES:
                errors.append(
                    f"features[{i}].status='{feat['status']}' not in {sorted(VALID_STATUSES)}"
                )

            # D24: validate optional Anthropic + ADR fields if present
            for fname, ftype in OPTIONAL_FEATURE_FIELDS.items():
                if fname in feat and feat[fname] is not None:
                    if not isinstance(feat[fname], ftype):
                        errors.append(
                            f"features[{i}].{fname} must be {ftype.__name__}, "
                            f"got {type(feat[fname]).__name__}"
                        )
            # steps[] elements must all be strings (Anthropic schema)
            if "steps" in feat and isinstance(feat["steps"], list):
                for j, step in enumerate(feat["steps"]):
                    if not isinstance(step, str):
                        errors.append(f"features[{i}].steps[{j}] must be string")
                    elif not step.strip():
                        errors.append(f"features[{i}].steps[{j}] cannot be empty")

    return len(errors) == 0, errors


# ─── Objective immutability (SHA256 hash) ───────────────────────────────────


def objective_hash(objective: str) -> str:
    return hashlib.sha256(objective.encode("utf-8")).hexdigest()


def store_objective_hash(wp_id: str, objective: str) -> None:
    """Store objective hash on first init. Subsequent calls verify against it."""
    OBJECTIVE_HASH_DIR.mkdir(parents=True, exist_ok=True)
    hash_file = OBJECTIVE_HASH_DIR / f"{wp_id}.sha256"
    hash_file.write_text(objective_hash(objective), encoding="utf-8")


def verify_objective_hash(wp_id: str, objective: str) -> bool:
    """Verify objective hasn't been mutated. Returns True if matches or first write."""
    hash_file = OBJECTIVE_HASH_DIR / f"{wp_id}.sha256"
    if not hash_file.exists():
        return True  # First write — caller must call store_objective_hash after
    expected = hash_file.read_text(encoding="utf-8").strip()
    return objective_hash(objective) == expected


# ─── Progress file IO ───────────────────────────────────────────────────────


def progress_path(wp_id: str) -> Path:
    return PROGRESS_DIR / f"{wp_id}.json"


def load_progress(wp_id: str | None = None) -> dict | None:
    """Load progress for given wp_id, or current active WP."""
    if wp_id:
        path = progress_path(wp_id)
    else:
        path = CURRENT_LINK
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_progress(data: dict) -> None:
    """Write progress.json atomically + update current.json symlink."""
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    wp_id = data["wp_id"]
    path = progress_path(wp_id)

    # Atomic write
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

    # Update current.json (regular file copy — symlink creates portability headaches)
    CURRENT_LINK.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Commands ───────────────────────────────────────────────────────────────


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize new WP progress file from JSON input."""
    if args.json_file:
        data = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    elif not sys.stdin.isatty():
        data = json.loads(sys.stdin.read())
    else:
        print("ERROR: must provide --json-file or stdin JSON", file=sys.stderr)
        return 1

    # Validate schema
    ok, errors = validate_schema(data)
    if not ok:
        print("ERROR: schema validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        emit_metric("init_failed", reason="schema_invalid", errors=errors)
        return 1

    wp_id = data["wp_id"]

    # Check if already initialized — if yes, verify objective unchanged
    existing = load_progress(wp_id)
    if existing:
        if not verify_objective_hash(wp_id, data["objective"]):
            print(
                f"ERROR: objective for {wp_id} already initialized with different hash. "
                f"Cannot mutate (D8 immutability rule).",
                file=sys.stderr,
            )
            emit_metric("init_failed", wp_id=wp_id, reason="objective_mutation_attempt")
            return 1
        print(f"NOTE: {wp_id} already initialized with matching objective. Updating non-objective fields only.", file=sys.stderr)
        # Preserve immutable fields from existing
        data["objective"] = existing["objective"]  # belt + suspenders
        data["started_at"] = existing.get("started_at", data.get("started_at"))

    # Stamp metadata
    if "started_at" not in data:
        data["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    data["session_pid"] = os.getppid()
    data["schema_version"] = SCHEMA_VERSION

    # Default constraints if missing
    # D24: 升级 must_pass_before_stop 为 D8 本意 — 不只 status passing，还需要 evidence
    data.setdefault("constraints", {
        "max_features_per_session": 1,
        "must_pass_before_stop": [
            "all features status == passing",
            "all features evidence != null",
        ],
    })

    # D24: warn about missing Anthropic-style steps[] (mechanical verification core)
    missing_steps = []
    missing_verify = []
    for feat in data["features"]:
        if not feat.get("steps"):
            missing_steps.append(feat["id"])
        if not feat.get("verification_command"):
            missing_verify.append(feat["id"])
    if missing_steps:
        print(
            f"WARNING: features {missing_steps} have no steps[] — D8 best practice "
            f"(Anthropic effective-harnesses) requires acceptance test step sequence.",
            file=sys.stderr,
        )
    if missing_verify:
        print(
            f"WARNING: features {missing_verify} have no verification_command — "
            f"ADR §4 D8.1 requires mechanical run instruction.",
            file=sys.stderr,
        )

    # Write + lock objective
    write_progress(data)
    store_objective_hash(wp_id, data["objective"])

    print(f"OK: progress.json initialized for {wp_id} ({len(data['features'])} features)")
    emit_metric(
        "init_ok",
        wp_id=wp_id,
        feature_count=len(data["features"]),
        with_steps=len(data["features"]) - len(missing_steps),
        with_verify_cmd=len(data["features"]) - len(missing_verify),
    )
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Update feature status. Cannot modify objective."""
    data = load_progress(args.wp_id)
    if not data:
        print(f"ERROR: no progress for {args.wp_id or 'current'}", file=sys.stderr)
        return 1

    # Verify objective immutability
    if not verify_objective_hash(data["wp_id"], data["objective"]):
        print(
            f"FATAL: objective hash mismatch for {data['wp_id']} — file tampered.",
            file=sys.stderr,
        )
        emit_metric("update_failed", wp_id=data["wp_id"], reason="objective_tampered")
        return 2

    if args.status not in VALID_STATUSES:
        print(f"ERROR: status must be one of {sorted(VALID_STATUSES)}", file=sys.stderr)
        return 1

    found = False
    for feat in data["features"]:
        if feat["id"] == args.feature:
            feat["status"] = args.status
            if args.evidence:
                feat["evidence"] = args.evidence
            elif args.status == "passing" and not feat.get("evidence"):
                print(
                    f"WARNING: marking {args.feature} passing without evidence — "
                    f"D8 best practice requires evidence for passing features.",
                    file=sys.stderr,
                )
            feat["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            found = True
            break

    if not found:
        print(f"ERROR: feature {args.feature} not found in {data['wp_id']}", file=sys.stderr)
        return 1

    write_progress(data)
    print(f"OK: {data['wp_id']}.{args.feature} -> {args.status}")
    emit_metric(
        "feature_update",
        wp_id=data["wp_id"],
        feature=args.feature,
        status=args.status,
        has_evidence=bool(args.evidence),
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show current progress (human or machine readable)."""
    data = load_progress(args.wp_id)
    if not data:
        if args.json:
            print(json.dumps({"error": "no_progress"}))
        else:
            print(f"NO progress.json for {args.wp_id or 'current'}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    # Human-readable summary
    print(f"WP: {data['wp_id']}")
    print(f"Started: {data.get('started_at', '?')}")
    print(f"Schema: {data.get('schema_version', '?')}")
    print(f"Objective: {data['objective']}")
    print()
    print(f"Features ({len(data['features'])}):")
    counts = {"passing": 0, "failing": 0, "blocked": 0}
    for feat in data["features"]:
        status = feat["status"]
        marker = {"passing": "✓", "failing": "✗", "blocked": "▣"}.get(status, "?")
        category = f" ({feat['category']})" if feat.get("category") else ""
        print(f"  {marker} [{status}] {feat['id']}: {feat['subject']}{category}")
        if feat.get("description"):
            print(f"     desc: {feat['description']}")
        # D24: show steps[] (Anthropic mechanical verification core)
        if feat.get("steps"):
            print(f"     steps:")
            for step in feat["steps"]:
                print(f"       • {step}")
        if feat.get("verification_command"):
            print(f"     verify: {feat['verification_command']}")
        if feat.get("evidence"):
            print(f"     evidence: {feat['evidence'][:120]}{'...' if len(feat['evidence']) > 120 else ''}")
        counts[status] = counts.get(status, 0) + 1
    print()
    print(f"Summary: {counts['passing']} passing / {counts['failing']} failing / {counts['blocked']} blocked")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate progress.json schema and invariants."""
    data = load_progress(args.wp_id)
    if not data:
        print("ERROR: no progress to validate", file=sys.stderr)
        return 1

    ok, errors = validate_schema(data)
    if not ok:
        print("FAIL: schema invalid:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if not verify_objective_hash(data["wp_id"], data["objective"]):
        print(f"FAIL: objective hash mismatch for {data['wp_id']}", file=sys.stderr)
        return 1

    print(f"OK: {data['wp_id']} schema valid + objective immutable")
    return 0


def cmd_stop_check(args: argparse.Namespace) -> int:
    """Stop hook 用：检查所有 feature 是否 passing。

    返回值：
        0 = 所有 features passing，可以 Stop
        1 = 有 features failing/blocked，不应 Stop
        2 = 无 progress.json（D8 未初始化，回退到 LLM 评估）
    """
    data = load_progress(args.wp_id)
    if not data:
        emit_metric("stop_check", result="no_progress")
        return 2  # Fall through to LLM evaluator

    # D24: 强化机械化检查 — 不只 status passing，还需要 evidence
    # 这是 Anthropic 第二篇 schema 的本意：passes:true 必须有可机械化验证的 steps + evidence
    pending = [f for f in data["features"] if f["status"] != "passing"]
    no_evidence = [
        f for f in data["features"]
        if f["status"] == "passing" and not f.get("evidence")
    ]

    if pending or no_evidence:
        for f in pending:
            print(
                f"BLOCKING: [{f['status']}] {f['id']}: {f['subject']}",
                file=sys.stderr,
            )
        for f in no_evidence:
            print(
                f"BLOCKING: [passing-no-evidence] {f['id']}: {f['subject']}\n"
                f"          → D8 本意要求 passing features 必须有 evidence != null\n"
                f"          → 用 `update --feature {f['id']} --status passing --evidence <output>`",
                file=sys.stderr,
            )
        emit_metric(
            "stop_check",
            result="blocked",
            pending_count=len(pending),
            no_evidence_count=len(no_evidence),
            wp_id=data["wp_id"],
        )
        return 1

    emit_metric("stop_check", result="passing", wp_id=data["wp_id"])
    return 0


# ─── Main ───────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="initializer-agent",
        description="ADR-038 D8 — strict JSON progress tracking for WP execution",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize WP progress (objective becomes immutable)")
    p_init.add_argument("--json-file", help="Path to JSON file with WP definition")
    p_init.set_defaults(func=cmd_init)

    p_update = sub.add_parser("update", help="Update feature status")
    p_update.add_argument("--wp-id", help="WP ID (default: current)")
    p_update.add_argument("--feature", required=True, help="Feature ID (e.g., F1)")
    p_update.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    p_update.add_argument("--evidence", help="Evidence text (test output, command, etc.)")
    p_update.set_defaults(func=cmd_update)

    p_status = sub.add_parser("status", help="Show progress")
    p_status.add_argument("--wp-id", help="WP ID (default: current)")
    p_status.add_argument("--json", action="store_true", help="JSON output")
    p_status.set_defaults(func=cmd_status)

    p_val = sub.add_parser("validate", help="Validate schema and immutability")
    p_val.add_argument("--wp-id", help="WP ID (default: current)")
    p_val.set_defaults(func=cmd_validate)

    p_stop = sub.add_parser("stop-check", help="Stop hook mechanical first-pass check")
    p_stop.add_argument("--wp-id", help="WP ID (default: current)")
    p_stop.set_defaults(func=cmd_stop_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
