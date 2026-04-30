#!/usr/bin/env python3
"""
ADR / PLAN 编号唯一性预防（pre-commit chokepoint）.

来源: H 系列收尾 + Nature 反馈"plan/adr 序号老是容易重复"
设计: ADR-038 D11 schema-level 100% 遵从（不靠 prompt）
红线: 不引入 metrics / dashboard / AI 自检；纯 grep 级机制（ADR-041 v1.0）

检测逻辑：
- 扫描 staged 中 docs/decisions/(ADR|PLAN)-NNN-*.md
- 跳过 H 系列（ADR-Hx / PLAN-Hx 是独立命名空间）
- 跳过子文档（EXECUTION-/REVIEW-GATE/gate-verdict/followup/v0/v1/...）
- 同号同前缀 + 不同主题后缀 → 阻断
- 给出下一个可用号

退出码：0 通过 / 1 阻断
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

DECISIONS_DIR = Path("docs/decisions")

# 主文件名规约：ADR-001 / PLAN-001 / ADR-039A / PLAN-039A（数字 + 可选大写字母 sub-id）
PRINCIPAL_PATTERN = re.compile(
    r"^(ADR|PLAN)-(?P<num>\d{3}[A-Z]?)-(?P<suffix>[a-zA-Z0-9][a-zA-Z0-9_.-]*)\.md$"
)

# H 系列单独命名空间，不参与全局编号管控
H_SERIES_PATTERN = re.compile(r"^(ADR|PLAN)-H[0-9]+-")

# 子文档后缀（与同号主文档共存视为合法）
SUBDOC_SUFFIX_PATTERNS = [
    re.compile(r"^EXECUTION([-_].+)?$", re.IGNORECASE),     # PLAN-036-EXECUTION-LOG
    re.compile(r"^REVIEW[-_]GATE\d+$", re.IGNORECASE),       # PLAN-066-REVIEW-GATE2
    re.compile(r"^[Gg]ate\d+[-_]verdict$"),                  # PLAN-086-gate6-verdict
    re.compile(r"^followup([-_].+)?$", re.IGNORECASE),       # PLAN-094-followup-...
    re.compile(r"^v\d+(\.\d+)?([-_].+)?$"),                  # PLAN-094-v0-... / -v0.1-... / -v2
]


def is_h_series(name: str) -> bool:
    return bool(H_SERIES_PATTERN.match(name))


def is_subdoc_suffix(suffix: str) -> bool:
    """suffix 是否属于"子文档"白名单（首段 token 命中即可）."""
    first_token = suffix.split("-", 1)[0]
    for pat in SUBDOC_SUFFIX_PATTERNS:
        if pat.match(first_token) or pat.match(suffix):
            return True
    return False


def get_staged_files() -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            text=True,
        )
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def collect_existing_principal(num_with_kind: dict[tuple[str, str], list[str]]) -> None:
    """收集"主文档"。识别规则：
    - 同号下没有非子文档 → 当前所有文件都视为 principal（用于碰撞检测）
    - 同号下存在非子文档 → 仅它们是 principal
    """
    if not DECISIONS_DIR.is_dir():
        return

    by_num: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for entry in sorted(DECISIONS_DIR.iterdir()):
        if not entry.is_file():
            continue
        name = entry.name
        if is_h_series(name):
            continue
        m = PRINCIPAL_PATTERN.match(name)
        if not m:
            continue
        key = (m.group(1), m.group("num"))
        by_num.setdefault(key, []).append((name, m.group("suffix")))

    for key, files in by_num.items():
        non_sub = [n for n, s in files if not is_subdoc_suffix(s)]
        if non_sub:
            num_with_kind.setdefault(key, []).extend(non_sub)
        else:
            # 只有 sub-doc 形式（如 ADR-011-v2-intent-field 单独存在）→ 视为 principal
            num_with_kind.setdefault(key, []).extend(n for n, _ in files)


def collect_all_used_numbers(kind: str) -> set[int]:
    """扫盘 docs/decisions/ 下所有 ADR-NNN / PLAN-NNN 出现过的纯数字号（含 H 系列除外的全集）."""
    used: set[int] = set()
    if not DECISIONS_DIR.is_dir():
        return used
    pat = re.compile(rf"^{kind}-(\d{{3}})[A-Z]?-")
    for entry in DECISIONS_DIR.iterdir():
        if not entry.is_file() or is_h_series(entry.name):
            continue
        m = pat.match(entry.name)
        if m:
            used.add(int(m.group(1)))
    return used


def next_available(kind: str) -> str:
    """给出"max + 1"作为下一个可用号（贴合 Nature 既有发号习惯，不抢历史空洞）."""
    used = collect_all_used_numbers(kind)
    n = (max(used) + 1) if used else 1
    return f"{n:03d}"


def main() -> int:
    repo_root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
    os.chdir(repo_root)

    staged = get_staged_files()
    decision_files = [
        f for f in staged
        if f.startswith(f"{DECISIONS_DIR}/") and f.endswith(".md")
    ]
    if not decision_files:
        return 0

    existing: dict[tuple[str, str], list[str]] = {}
    collect_existing_principal(existing)

    blocks: list[str] = []
    for path in decision_files:
        name = Path(path).name
        if is_h_series(name):
            continue
        m = PRINCIPAL_PATTERN.match(name)
        if not m:
            continue

        kind = m.group(1)
        num = m.group("num")
        suffix = m.group("suffix")
        if is_subdoc_suffix(suffix):
            continue

        key = (kind, num)
        siblings = [s for s in existing.get(key, []) if s != name]
        if not siblings:
            continue

        # 命中：同号 + 主文档 + 不同主题后缀
        # 收紧规则：若 siblings 存在不同 suffix，则视为冲突
        for sib in siblings:
            sib_m = PRINCIPAL_PATTERN.match(sib)
            if not sib_m:
                continue
            if sib_m.group("suffix") == suffix:
                # 同名（说明是 amend / rename 场景），放行
                continue
            blocks.append(
                f"  {kind}-{num} 冲突：\n"
                f"    新文件: {name}\n"
                f"    已存在: {sib}\n"
            )
            break

    if blocks:
        kinds_blocked = {b.lstrip().split("-", 1)[0] for b in blocks}
        suggestions: list[str] = []
        for kind in ("ADR", "PLAN"):
            if kind in kinds_blocked:
                nxt = next_available(kind)
                suggestions.append(f"  {kind}: 下一个可用号 {kind}-{nxt}")

        sys.stderr.write(
            "\n========================================\n"
            "ADR/PLAN 编号唯一性: 阻断\n"
            "========================================\n\n"
            "检出同号 + 不同主题的命名冲突：\n\n"
            + "\n".join(blocks)
            + "\n建议：\n"
            + "\n".join(suggestions)
            + "\n\n白名单（不会触发）：\n"
            "  - 子文档：-EXECUTION-* / -REVIEW-GATE* / -gateN-verdict / -followup-* / -vN[.M]-*\n"
            "  - H 系列：ADR-Hx / PLAN-Hx（独立命名空间）\n"
            "  - 字母 sub-id：ADR-039A / PLAN-039A（视为独立编号）\n\n"
            "若确属合法子文档，使用上述后缀命名再提交。\n"
            "若确为新议题，请改用建议的下一个可用号。\n\n"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
