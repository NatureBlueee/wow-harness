#!/usr/bin/env python3
"""Trace Analyzer — 分析 metrics JSONL，提议 harness 改进

[来源: ADR-038 D10 + LangChain Trace Analyzer Skill
       — 自动 traces → 错误分析 → 提议 harness 变更 → 验证]

设计原则：
1. **不常驻** — 事件触发或 cron 调用，不是 hook
2. **不自动落地** — 输出 .towow/proposals/<timestamp>.md，人工审查后才进入 D6.1
3. **confidence 门槛** — 只有 confidence ≥ 0.8 的建议才推荐合并
4. **不分析单条** — 必须有足够样本才聚类（默认 N≥5）

分析维度：
- **A. 工具失败聚类**：相同 tool + 相似 error 的频率
- **B. Hook 性能漂移**：hook_execution_ms 的 p95 趋势
- **C. Stop 评估器命中率**：mechanical_block vs mechanical_pass 比例
- **D. Fragment 注入效率**：哪些 fragment 反复注入但触发频率高
- **E. Guard findings 聚类**：哪些 guard 反复 fire（可能误报或真实问题）

CLI:
    # 分析过去 7 天 metrics → 写 proposal
    python3 scripts/hooks/trace-analyzer.py analyze [--days 7] [--min-samples 5]

    # 列出现有 proposals
    python3 scripts/hooks/trace-analyzer.py list

    # dry-run（只输出到 stdout，不写 proposal 文件）
    python3 scripts/hooks/trace-analyzer.py analyze --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
METRICS_DIR = REPO_ROOT / ".towow" / "metrics"
PROPOSALS_DIR = REPO_ROOT / ".towow" / "proposals"

METRICS_FILES = {
    "guard": "guard-events.jsonl",
    "tool_failures": "tool-failures.jsonl",
    "stop": "stop-events.jsonl",
    "initializer": "initializer-events.jsonl",
}


# ─── JSONL loading ──────────────────────────────────────────────────────────


def iter_jsonl(name: str, *, since: datetime | None = None) -> Iterator[dict]:
    """Iterate JSONL records, optionally filtered by timestamp."""
    path = METRICS_DIR / name
    if not path.exists():
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if since:
                    ts = record.get("ts") or record.get("timestamp")
                    if ts:
                        try:
                            rec_dt = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
                            if rec_dt < since:
                                continue
                        except ValueError:
                            pass
                yield record
    except OSError:
        return


# ─── Analysis: Tool failure clustering ──────────────────────────────────────


def analyze_tool_failures(since: datetime, min_samples: int) -> list[dict]:
    """A. Cluster tool failures by tool + error pattern."""
    records = list(iter_jsonl(METRICS_FILES["tool_failures"], since=since))
    if len(records) < min_samples:
        return []

    clusters: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in records:
        tool = r.get("tool_name", "unknown")
        error = r.get("error", "")[:80]  # Normalize prefix
        clusters[(tool, error)].append(r)

    findings = []
    for (tool, error), instances in clusters.items():
        if len(instances) < min_samples:
            continue
        # Confidence: log-scale frequency vs total
        total = len(records)
        freq = len(instances) / total
        confidence = min(0.95, 0.5 + freq)
        findings.append({
            "pattern": "tool_failure_cluster",
            "tool": tool,
            "error_prefix": error,
            "count": len(instances),
            "total_failures": total,
            "frequency": round(freq, 2),
            "confidence": round(confidence, 2),
            "proposed_change": (
                f"Investigate why {tool} fails with '{error[:40]}...' — "
                f"consider adding context fragment or guard for this pattern."
            ),
        })
    return sorted(findings, key=lambda x: -x["count"])


# ─── Analysis: Hook performance drift ───────────────────────────────────────


def analyze_hook_performance(since: datetime, min_samples: int) -> list[dict]:
    """B. Detect hook_execution_ms drift over time."""
    records = list(iter_jsonl(METRICS_FILES["guard"], since=since))
    done_records = [r for r in records if r.get("event") == "hook_done" and "elapsed_ms" in r]

    if len(done_records) < min_samples:
        return []

    elapsed_values = [r["elapsed_ms"] for r in done_records]
    elapsed_values.sort()
    n = len(elapsed_values)
    p50 = elapsed_values[n // 2]
    p95 = elapsed_values[int(n * 0.95)]
    p99 = elapsed_values[int(n * 0.99)] if n >= 100 else p95

    findings = []
    if p95 > 100:  # 100ms threshold
        confidence = min(0.9, 0.5 + (p95 - 100) / 1000)
        findings.append({
            "pattern": "hook_performance_warning",
            "samples": n,
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "confidence": round(confidence, 2),
            "proposed_change": (
                f"guard-feedback.py p95 = {p95}ms (samples: {n}). "
                f"Audit guard_router.py for duplicate file IO or expensive checks."
            ),
        })
    return findings


# ─── Analysis: Stop evaluator hit rate ──────────────────────────────────────


def analyze_stop_hit_rate(since: datetime, min_samples: int) -> list[dict]:
    """C. Measure mechanical vs LLM stop evaluation effectiveness."""
    records = list(iter_jsonl(METRICS_FILES["stop"], since=since))
    if len(records) < min_samples:
        return []

    counts = Counter(r.get("event", "?") for r in records)
    mech_block = counts.get("mechanical_block", 0)
    mech_pass = counts.get("mechanical_pass", 0)
    mech_skip = counts.get("mechanical_skip", 0)
    stop_block = counts.get("stop_block", 0)
    stop_pass = counts.get("stop_pass", 0)

    findings = []
    total_mech = mech_block + mech_pass + mech_skip
    if total_mech > 0:
        # If most stops have no progress.json, D8 adoption is low
        skip_rate = mech_skip / total_mech
        if skip_rate > 0.7:
            findings.append({
                "pattern": "d8_low_adoption",
                "mechanical_skip_rate": round(skip_rate, 2),
                "samples": total_mech,
                "confidence": 0.85,
                "proposed_change": (
                    f"D8 progress.json adoption is low ({skip_rate:.0%} of stops have no progress.json). "
                    f"Add reminder in lead skill to call initializer-agent.py at WP start."
                ),
            })
        # If mechanical block rate is high, agents are over-eager to stop
        if mech_block > 0:
            block_rate = mech_block / (mech_block + mech_pass) if (mech_block + mech_pass) else 0
            if block_rate > 0.3:
                findings.append({
                    "pattern": "premature_stop_attempts",
                    "mechanical_block_rate": round(block_rate, 2),
                    "samples": mech_block + mech_pass,
                    "confidence": 0.8,
                    "proposed_change": (
                        f"Agents attempt Stop with failing features {block_rate:.0%} of the time. "
                        f"Strengthen Objective Recitation (D9) or add CLAUDE.md reminder."
                    ),
                })

    return findings


# ─── Analysis: Fragment injection efficiency ────────────────────────────────


def analyze_fragment_efficiency(since: datetime, min_samples: int) -> list[dict]:
    """D. Find fragments that fire repeatedly — potential noise or real issue."""
    records = [r for r in iter_jsonl(METRICS_FILES["guard"], since=since)
               if r.get("event") == "fragment_inject"]
    if len(records) < min_samples:
        return []

    fragment_counts: Counter[str] = Counter()
    fragment_bytes: dict[str, int] = defaultdict(int)
    for r in records:
        for frag in r.get("fragments", []):
            fragment_counts[frag] += 1
            fragment_bytes[frag] += r.get("bytes", 0) // max(len(r.get("fragments", [])), 1)

    findings = []
    for frag, count in fragment_counts.most_common(10):
        if count >= min_samples:
            tokens = fragment_bytes[frag] // 4
            confidence = min(0.85, 0.4 + count / 50)
            findings.append({
                "pattern": "high_frequency_fragment",
                "fragment": frag,
                "injection_count": count,
                "total_tokens": tokens,
                "confidence": round(confidence, 2),
                "proposed_change": (
                    f"Fragment '{frag}' injected {count}x ({tokens} tokens). "
                    f"Consider promoting to CLAUDE.md root or splitting fragment dedup window."
                ),
            })
    return findings


# ─── Analysis: Guard findings clustering ────────────────────────────────────


def analyze_guard_findings(since: datetime, min_samples: int) -> list[dict]:
    """E. Cluster guard findings by category — find systemic issues."""
    records = [r for r in iter_jsonl(METRICS_FILES["guard"], since=since)
               if r.get("event") == "guard_findings"]
    if len(records) < min_samples:
        return []

    category_counts: Counter[str] = Counter()
    blocking_total = 0
    for r in records:
        for cat, count in r.get("categories", {}).items():
            category_counts[cat] += count
        blocking_total += r.get("blocking_count", 0)

    findings = []
    for cat, count in category_counts.most_common(5):
        if count >= min_samples:
            confidence = min(0.85, 0.4 + count / 100)
            findings.append({
                "pattern": "frequent_guard_finding",
                "category": cat,
                "count": count,
                "confidence": round(confidence, 2),
                "proposed_change": (
                    f"Guard category '{cat}' fired {count}x. "
                    f"Either upgrade to blocking guard or add CLAUDE.md prevention rule."
                ),
            })
    return findings


# ─── Proposal markdown generation ───────────────────────────────────────────


def generate_proposal(all_findings: dict[str, list[dict]], days: int) -> str:
    """Generate human-readable markdown proposal."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    total = sum(len(v) for v in all_findings.values())

    lines = [
        f"# Harness Improvement Proposal — {ts}",
        "",
        f"**Generated by**: trace-analyzer.py (ADR-038 D10)",
        f"**Window**: last {days} days",
        f"**Total findings**: {total}",
        f"**High confidence (≥0.8)**: "
        f"{sum(1 for v in all_findings.values() for f in v if f.get('confidence', 0) >= 0.8)}",
        "",
        "> ⚠️ **不自动落地**。这些是 trace 分析的建议，必须人工审查后才能进入 D6.1 self-evolution。",
        "> 只有 confidence ≥ 0.8 的建议才推荐立即处理。",
        "",
        "---",
        "",
    ]

    sections = [
        ("A. 工具失败聚类", "tool_failures"),
        ("B. Hook 性能漂移", "hook_perf"),
        ("C. Stop 评估器命中率", "stop_hit"),
        ("D. Fragment 注入效率", "fragment_eff"),
        ("E. Guard findings 聚类", "guard_findings"),
    ]

    for title, key in sections:
        findings = all_findings.get(key, [])
        lines.append(f"## {title}")
        lines.append("")
        if not findings:
            lines.append("无显著模式（样本不足或全部正常）。")
            lines.append("")
            continue
        for i, f in enumerate(findings, 1):
            conf = f.get("confidence", 0)
            conf_marker = "🟢" if conf >= 0.8 else "🟡" if conf >= 0.6 else "🔴"
            lines.append(f"### {i}. {f.get('pattern', 'unknown')} {conf_marker} (confidence: {conf})")
            lines.append("")
            for k, v in f.items():
                if k in ("pattern", "confidence", "proposed_change"):
                    continue
                lines.append(f"- **{k}**: `{v}`")
            lines.append("")
            lines.append(f"**Proposed change**: {f.get('proposed_change', '?')}")
            lines.append("")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 处理流程")
    lines.append("")
    lines.append("1. 审查每个 finding 的 root cause 假设")
    lines.append("2. 对 confidence ≥ 0.8 的建议建 issue (`docs/issues/...`)")
    lines.append("3. 实施 harness change → 等下次 trace-analyzer 运行验证效果")
    lines.append("4. 验证后归档 proposal 到 `.towow/proposals/archive/`")
    lines.append("")

    return "\n".join(lines)


# ─── Commands ───────────────────────────────────────────────────────────────


def cmd_analyze(args: argparse.Namespace) -> int:
    since = datetime.now() - timedelta(days=args.days)

    all_findings = {
        "tool_failures": analyze_tool_failures(since, args.min_samples),
        "hook_perf": analyze_hook_performance(since, args.min_samples),
        "stop_hit": analyze_stop_hit_rate(since, args.min_samples),
        "fragment_eff": analyze_fragment_efficiency(since, args.min_samples),
        "guard_findings": analyze_guard_findings(since, args.min_samples),
    }

    total = sum(len(v) for v in all_findings.values())
    high_conf = sum(1 for v in all_findings.values() for f in v if f.get("confidence", 0) >= 0.8)

    proposal = generate_proposal(all_findings, args.days)

    if args.dry_run:
        print(proposal)
        print(f"\n[dry-run] {total} findings, {high_conf} high confidence", file=sys.stderr)
        return 0

    if total == 0:
        print("No findings — harness is healthy or sample size insufficient.")
        return 0

    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROPOSALS_DIR / f"{time.strftime('%Y-%m-%d_%H%M%S')}-trace-analysis.md"
    out_path.write_text(proposal, encoding="utf-8")
    print(f"OK: wrote {out_path.relative_to(REPO_ROOT)}")
    print(f"     {total} findings, {high_conf} high-confidence")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    if not PROPOSALS_DIR.exists():
        print("No proposals yet.")
        return 0
    proposals = sorted(PROPOSALS_DIR.glob("*.md"))
    if not proposals:
        print("No proposals yet.")
        return 0
    for p in proposals:
        size = p.stat().st_size
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))
        print(f"  {p.name}  ({size}B, {mtime})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="trace-analyzer",
        description="ADR-038 D10 — Analyze metrics JSONL → propose harness improvements",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_analyze = sub.add_parser("analyze", help="Analyze metrics and write proposal")
    p_analyze.add_argument("--days", type=int, default=7, help="Lookback window in days")
    p_analyze.add_argument("--min-samples", type=int, default=5, help="Minimum cluster size")
    p_analyze.add_argument("--dry-run", action="store_true", help="Print to stdout, no file")
    p_analyze.set_defaults(func=cmd_analyze)

    p_list = sub.add_parser("list", help="List existing proposals")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
