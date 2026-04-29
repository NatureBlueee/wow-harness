---
adr: ADR-H6
title: 状态文件健康度（state 清单 schema 化 + 健康度指标 + stale 清理 + 抗 compact 接口签字）
status: accepted
date: 2026-04-28
parent_charter: ADR-H0-meta-charter.md
philosophy_inheritance:
  - ADR-041-codex-integration v1.0（"调字不加机制"）
  - ADR-H4 INV-H4-3 反例表（不写 metrics / 不写 dashboard / 不写 hook 治节奏）
  - ADR-H5 INV-H5-3（实际引入检测取代裸 grep；awk 排除 code block 自指悖论修正）
  - ADR-038 D11.2（schema-level 100% > prompt-level 70%）
applies_scope:
  - .claude/plugins/towow-review-toolkit/contracts/review-contract.yaml（增 state_inventory + state_health_indicators 顶层字段）
  - .towow/state/_archived/（新建：归档目录）
  - .towow/state/.DS_Store（删除）
  - .towow/state/completion-proposal-profile-build-cli-archived-20260419-1110.json（移到 _archived/）
  - .towow/state/harness-review-2026-04-14/（移到 _archived/）
  - 本 ADR 自身（自指 dogfood）
not_in_scope:
  - .towow/state/round{1-5}-verdicts/（审计依据，原地保留不动）
  - .towow/proposals/（self-evolution 足迹，只增不删）
  - .towow/guard/（once-flag/loop-counter 活工具态，#4 认知修正）
  - .towow/inbox/（H9 受管，不动）
  - .towow/evidence/（各 PLAN 受管，不动）
  - 任何新 hook（INV-H6-3 红线）
  - ADR-042 D3/D4 写屏障逻辑（仅引用，不改）
---

# ADR-H6：状态文件健康度

## §1 上下文

### 1.1 .towow/ 现状盘点（实测 2026-04-28T19:12）

| 路径 | 当前状态 | 健康度判定 |
|------|---------|-----------|
| `.towow/state/mode` | 6 字节 | ✅ 动态运行期 |
| `.towow/state/run.json` | 3 字节 | ✅ 动态运行期 |
| `.towow/state/locks.json` | 3 字节 | ✅ 动态运行期 |
| `.towow/state/completion-proposal.json` | 6048 字节 / Apr 19 | ✅ 当前 run 提案 |
| `.towow/state/risk-snapshot.json` | 877 字节 / 实测 mtime 当下 | ✅ 由 risk-tracker 实时维护 |
| `.towow/state/round{1-5}-verdicts/` | 5 个目录 / Apr 16-19 | ✅ 审计归档保留 |
| `.towow/state/harness-review-2026-04-14/` | 目录 / Apr 14 | ⚠ 14 天前归档，应移 _archived/ |
| `.towow/state/completion-proposal-profile-build-cli-archived-20260419-1110.json` | 4737 字节 / Apr 19 | ⚠ 文件名已含 archived 但在主目录 |
| `.towow/state/.DS_Store` | 6148 字节 / Apr 16 | ❌ macOS 噪声 |
| `.towow/proposals/` | 265 文件 | ✅ self-evolution 痕迹（只增不删） |
| `.towow/guard/` | 11321 文件 | ✅ once-flag/loop-counter 活工具态（#4 认知修正） |
| `.towow/log/harness-self-symptoms.md` | 1 文件 | ✅ H 系列自指审计 |
| `.towow/log/hook/` | 目录 | ✅ hook ledger |
| `.towow/inbox/**` | H9 受管 | ✅ 不动 |
| `.towow/evidence/**` | 各 PLAN 受管 | ✅ 不动 |

### 1.2 触发动机

H 系列 plan §3.3 给 H6 的 DoD：**state 清单 ≥10 + 健康度指标 ≥3 + ADR-042 D9 接口签字 + 3 stale 清理**。本 ADR 给出 H6 决策本质，不是工程节奏（节奏在 PLAN-H6）。

### 1.3 与 H5 的协同关系

H5 已经在 review-contract.yaml 增加了 `line_caps` + `inflation` + `drafter_reviewer_separation` 三处 schema 字段（commit `872f03ce`）。H6 直接复用同一 yaml 作为 schema 真相源，增加 `state_inventory` + `state_health_indicators` 两处顶层字段——**不再分散到独立 yaml/json**。

## §2 决策本质

**一句话**：把 §1.1 现状清单和"什么算 state 健康"从"散落在 ADR-038/ADR-042/各 plan §6"升级到 review-contract.yaml 顶层 `state_inventory` + `state_health_indicators` 字段——schema-level 真相源。同步把 3 个明确 stale 文件（.DS_Store + archived JSON + Apr 14 review）物理移走或删除。

**只调字（schema 字段 + 文件移动），不加机制**——继承 ADR-041 v1.0 + ADR-H4 INV-H4-3 反例表 + ADR-H5 INV-H5-3 实际引入检测原则。

**抗 compact 接口签字**：本 ADR §6 显式签字"抗 compact 真相源 = ADR-042 D3 (Session-Owner ownership.yaml) + D4 (owner-guard.py 写屏障)"；H6 不重做、不另建。AGENTS.md 渐进加载（ADR-042 D9）作为 Codex 抗 compact 路径同样签字接受。

## §3 INV-H6（不变量，3 条）

### INV-H6-1：state 清单 schema 化

review-contract.yaml 增加顶层 `state_inventory` 字段，列出 §1.1 表的全部 ≥10 条 state 资产（按 dynamic / archived / append-only / managed-by-other-H 四类标注）。

```yaml
state_inventory:
  - id: state-mode
    path: ".towow/state/mode"
    kind: dynamic
    owner: towow-mode-toolkit
  ...
```

**红线**：增加新 state 资产必须在原始 ADR（ADR-038 / ADR-042 / ADR-Hx）中先有声明；H6 不发明新 state。

### INV-H6-2：state 健康度指标 schema 化

review-contract.yaml 增加顶层 `state_health_indicators` 字段，定义 ≥3 条机器可读指标：

```yaml
state_health_indicators:
  - id: schema-validity
    desc: "5 个 dynamic JSON 文件 (mode/run.json/locks.json/completion-proposal.json/risk-snapshot.json) JSON parse 通过 + 必填字段非空"
    check: "python3 -c 'import json; for p in [...]: json.load(open(p))'"
  - id: top-level-no-noise
    desc: ".towow/state/ 顶层无 .DS_Store / 未归档 archived 文件 / 临时文件"
    check: "ls .towow/state/*.DS_Store .towow/state/*archived*.json 2>/dev/null | wc -l == 0（顶层）"
  - id: inbox-unread-volume
    desc: ".towow/inbox/main/unread/ ≤50 文件（H9 ADR 红线复用）"
    check: "ls .towow/inbox/main/unread/ | wc -l ≤ 50"
```

**红线**：指标必须 schema-level 可验证（机器可读 check 命令）；不引入"AI 自我评估"或"主观 health score"。

### INV-H6-3：零机制实际引入（继承 INV-H5-3 修正版）

验证 = 实际引入检测（不是裸 word frequency；反例段豁免，避免 INV-H1-3 自指悖论）：

1. `find .towow/state/_archived .claude/plugins/towow-review-toolkit -newer docs/decisions/ADR-H0-meta-charter.md -name "*.py"` = 0
2. `git diff HEAD~5..HEAD --stat -- 'scripts/hooks/h6*' '.claude/plugins/*/hooks/h6*'` = empty
3. review-contract.yaml diff 中无 `cron:` / `schedule:` / `polling_interval:` / `auto_*:` 等触发字段
4. ADR-H6 + PLAN-H6 § 正文（排除 §3 INV-H6-3 / §7 不做什么 / §9 H0 自检）不引入机制实施动词搭配，搭配定义见以下 fence：

```text
verbs = (创建|启动|调度)
mechanism_nouns = (metrics|dashboard|hook)
violation = verbs.*mechanism_nouns
```

## §4 stale 清理决策表（DoD 3 stale）

| # | 路径 | 大小 / mtime | 决策 | 理由 |
|---|------|-------------|------|------|
| 1 | `.towow/state/.DS_Store` | 6148 / Apr 16 | **物理删除** + 加 `.gitignore` | macOS 噪声，无信息价值；防止再生 |
| 2 | `.towow/state/completion-proposal-profile-build-cli-archived-20260419-1110.json` | 4737 / Apr 19 | **移到 `.towow/state/_archived/`** | 文件名已含 archived 标识，应物理位置匹配 |
| 3 | `.towow/state/harness-review-2026-04-14/` | 目录 / Apr 14 | **移到 `.towow/state/_archived/`** | 14 天前归档；移走后 `.towow/state/` 顶层只剩 dynamic + round{1-5}-verdicts/（仍是审计依据，保留） |

**禁动**：
- `.towow/state/round{1-5}-verdicts/` —— 审计依据，原地保留
- `.towow/proposals/` —— self-evolution 足迹，只增不删
- `.towow/guard/` —— 11321 文件按 #4 认知修正是活工具态（once-flag/loop-counter）

## §5 跳 Gate 决策表（继承 ADR-H5 §4，不重写）

H6 涉及的 Gate 由 ADR-H5 §4 跳 Gate 决策表统一治理。本 ADR 不重复定义跳 Gate 表；引用：
- merge-ready-review binding（含 INV-H5-2 drafter_reviewer_separation）
- line_caps 中本 ADR + PLAN-H6 受 adr-h-series ≤300 / plan-h-series ≤500 限制

## §6 抗 compact 接口签字（plan §3.3 H6 DoD：ADR-042 D9 接口签字）

H6 显式签字接受以下抗 compact 真相源，不重做、不另建：

| 抗 compact 路径 | 真相源 | 签字状态 |
|----------------|--------|---------|
| AI 自识 "我是谁、own 什么" | ADR-042 D3 Session-Owner 真相源 + ownership.yaml + AI 自识协议 | ✅ H6 签字接受 |
| 写权限物理隔离 | ADR-042 D4 owner-guard.py PreToolUse 写屏障 hook | ✅ H6 签字接受（hook 已存在，H6 不动其代码） |
| Codex 渐进加载 | ADR-042 D9 AGENTS.md 渐进加载体系 | ✅ H6 签字接受 |
| H 系列窗口邮箱 cross-session 通信 | ADR-H9 inbox 路径约定 + SessionStart 注入 | ✅ H6 签字接受（H9 受管，不动） |
| state 文件 fresh-load | review-contract.yaml `state_inventory` + 各 owner skill SessionStart 重读 | ✅ H6 提供 schema 真相源 |

**红线**：H6 不重新设计抗 compact 协议；H6 仅做"清单 + 健康度 + 签字接受"。

## §7 不做什么（边界声明）

- ❌ 不写新 hook（INV-H6-3 红线）
- ❌ 不在 verify-gate.py 加新逻辑（schema 字段先存在，消费链路留 H 系列收尾后单独 ADR）
- ❌ 不动 .towow/proposals/（self-evolution 足迹）
- ❌ 不动 .towow/guard/（活工具态）
- ❌ 不动 .towow/inbox/（H9 受管）
- ❌ 不动 .towow/evidence/（各 PLAN 受管）
- ❌ 不重做 ADR-042 D3/D4/D9 抗 compact 协议
- ❌ 不引入 metrics/dashboard/AI 自评估 health score（INV-H6-3）
- ❌ 不动 .towow/state/round{1-5}-verdicts/（审计依据）

## §8 受管资产（scope 锁死）

| # | 路径 | 动作 | 限额 |
|---|------|------|------|
| 1 | `.claude/plugins/towow-review-toolkit/contracts/review-contract.yaml` | 增 `state_inventory` + `state_health_indicators` 顶层字段 | ≤300 行（H5 后 171 → 目标 ≤270） |
| 2 | `docs/decisions/ADR-H6-state-file-health.md` | 本 ADR | ≤300 行 |
| 3 | `docs/decisions/PLAN-H6-state-file-health.md` | 工程计划 | ≤500 行 |
| 4 | `docs/decisions/tasks/PLAN-H6/WP-04/dogfood-output-*.md` | dogfood 产出 | ≤80 行 |
| 5 | `docs/decisions/tasks/PLAN-H6/WP-05/reviewer-verdict-*.md` | reviewer signoff | reviewer 决定 |
| 6 | `.towow/state/_archived/` | 新建目录 | — |
| 7 | `.gitignore` | 加 `.towow/state/.DS_Store` 规则 | — |
| 8 | `.towow/state/.DS_Store` | 删除 | — |
| 9 | `.towow/state/completion-proposal-profile-build-cli-archived-20260419-1110.json` | git mv → `_archived/` | — |
| 10 | `.towow/state/harness-review-2026-04-14/` | git mv → `_archived/` | — |

## §9 H0 自检

| 条款 | 内容 | 状态 |
|------|------|------|
| H0.1 施工隔离 | scope 显式列出 | ✅ §8 + frontmatter applies_scope/not_in_scope |
| H0.2 节流限速 | ADR ≤300 行 | 待终稿 wc -l 验证（estimated 230-260） |
| H0.3 执检分离 | 起草人 ≠ 签字人 | ✅ WP-05 reviewer subagent 独立 |
| H0.4 自指禁止 | 不重现要修的症状 | ✅ INV-H6-3 继承 H5 修正版；不重现"自指 false positive" |
| H0.5 跨 H 协调 | 共改文件冲突表 | ✅ §7 不做什么 + §3 跨 H 协调（H6 仅改 review-contract.yaml + state/，不撞其他 H） |
| H0.6 证据机械化 | DoD 证据机器可生成 | ✅ §3 INV + §4 stale 表 + §6 抗 compact 表均给 grep/find/yaml field 校验 |
| H0.meta | 不引未来 H | ✅（H8 已存在不算未来；下方 grep 验证） |

H0.meta 验证命令（继承 H5 awk 排除 code block 模板）：
```bash
awk '/^```/{f=!f; next} !f' docs/decisions/ADR-H6-state-file-health.md | grep -cE "\bH(7|10|11|12)\b"
# 应为 0（H7 退役不算未来；H10+ 是未来 H）
```

## §10 dogfood 规划

PLAN-H6 WP-04 用 H6 起草过程自身做输入：
- ADR-H6 + PLAN-H6 + review-contract.yaml diff 满足 INV-H6-3 4 项检测
- 3 stale 清理动作的 git mv / git rm 物理结果可机器验证
- WP-04 输出文件 ≤80 行，自身受 INV-H6-1 line-cap 约束

## §11 与现行 vNext 共存

按 H 系列 plan §3.3.3：
- review-contract.yaml 修改后跑 yaml.safe_load 验证（PLAN-H6 WP-03 DoD）
- 4 active binding + H5 三字段（line_caps / inflation / drafter_reviewer_separation）不动
- `.towow/state/_archived/` 新建对 verify-gate.py / transition.py / capability-router.py 透明（不会影响 mode/run.json/locks.json 读取路径）
- 3 stale 文件移动用 `git mv`（保留历史）+ git rm（仅 .DS_Store）
