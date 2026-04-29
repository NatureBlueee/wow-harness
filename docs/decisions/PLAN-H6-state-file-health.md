---
plan: PLAN-H6
adr_ref: ADR-H6-state-file-health.md
status: in-progress
date: 2026-04-28
parent_plan: H 系列 plan §3.3（H6 行）
philosophy_inheritance:
  - ADR-041 v1.0
  - ADR-H0 §H0.1-H0.6 + H0.meta
  - ADR-H4 INV-H4-3 反例表
  - ADR-H5 INV-H5-3 实际引入检测 + awk 排除 code block 模板
  - ADR-038 D11.2 schema-level 100%
applies_scope:
  - .claude/plugins/towow-review-toolkit/contracts/review-contract.yaml
  - .towow/state/_archived/（新建）
  - .gitignore（加 1 行）
  - .towow/state/.DS_Store（删除）
  - .towow/state/completion-proposal-profile-build-cli-archived-*.json（移动）
  - .towow/state/harness-review-2026-04-14/（移动）
  - docs/decisions/ADR-H6-state-file-health.md
  - docs/decisions/PLAN-H6-state-file-health.md
  - docs/decisions/tasks/PLAN-H6/**
not_in_scope:
  - 任何 hook / py 文件（INV-H6-3）
  - .towow/state/round{1-5}-verdicts/（审计原地保留）
  - .towow/proposals/ / .towow/guard/ / .towow/inbox/ / .towow/evidence/
  - verify-gate.py / transition.py / owner-guard.py（仅引用）
---

# PLAN-H6：状态文件健康度工程计划

## §1 上下文与基线锁定

### 1.1 工程目标

ADR-H6 3 条 INV 的物理落地：
- INV-H6-1：review-contract.yaml 增 `state_inventory` 顶层字段（≥10 项）
- INV-H6-2：review-contract.yaml 增 `state_health_indicators` 顶层字段（≥3 条）
- INV-H6-3：零机制实际引入（继承 INV-H5-3 修正版 4 项检测）

同时执行 3 stale 清理（.DS_Store 删 + 2 archived 移 _archived/），并签字接受 ADR-042 D3/D4/D9 抗 compact 协议作为真相源。

### 1.2 基线锁定（带行数 + 时间戳）

| # | 资产 | 起草前实测 | 限额 | 时间戳 |
|---|------|------------|------|--------|
| 1 | `.claude/plugins/towow-review-toolkit/contracts/review-contract.yaml` | 171 行（H5 后） | ≤270（H6 后目标） | HEAD = `872f03ce` (PLAN-H5 WP-03) |
| 2 | `docs/decisions/ADR-H6-state-file-health.md` | 205 行（已起草） | ≤300 | 本 PLAN commit 同步 |
| 3 | `docs/decisions/PLAN-H6-state-file-health.md` | 本文件 | ≤500 | 同上 |
| 4 | `.towow/state/.DS_Store` | 6148 字节 / Apr 16 | 删除 | git status 验证 |
| 5 | `.towow/state/completion-proposal-profile-build-cli-archived-20260419-1110.json` | 4737 字节 / Apr 19 | 移到 `_archived/` | `git mv` |
| 6 | `.towow/state/harness-review-2026-04-14/` | 目录 / Apr 14 | 移到 `_archived/` | `git mv` |
| 7 | `.gitignore` | 加 1 行 `.towow/state/.DS_Store` | 行数变化 +1 | — |
| 8 | state_inventory 项数 | 0（未引入） | ≥10 | yaml.safe_load |
| 9 | state_health_indicators 项数 | 0（未引入） | ≥3 | yaml.safe_load |
| 10 | reviewer-verdict 历史路径 | H1 在 WP-05/，H5 在 WP-05/ | INV-H5-2 已锁 WP-05/ | 4 文件已存在 |

### 1.3 已知 race risk

- `.towow/state/risk-snapshot.json` 实测 mtime 当下（被 risk-tracker 实时维护）—— **不动** ；H6 不修改任何动态 state 文件
- 其他 session 可能持续写 `.towow/proposals/` —— H6 不动该目录
- `git mv` 文件期间如撞他 session merge state，按 §4.9 教训：`git restore --staged` + 推迟

## §2 WP 拆解（5 WP）

### WP-01 现状盘点（已完成 in 2026-04-28T19:12）

DoD：基线表 §1.2 10 行齐全；§1.3 race risk 列出；ADR-042 D3/D4/D9 引用确认；3 stale 候选实测时间戳。
实测：✅ 已完成（本 PLAN §1.2/§1.3 + ADR-H6 §1.1 即证据）

### WP-02 起草 ADR-H6 + PLAN-H6（已完成）

DoD：ADR-H6 ≤300 + PLAN-H6 ≤500 + INV ≥3 + state 清单 ≥10（在 ADR §1.1 表）+ 健康度指标 ≥3（在 ADR §3 INV-H6-2）+ stale 决策表 ≥3（在 ADR §4）+ 抗 compact 接口签字 ≥1（在 ADR §6）。
实测：✅ ADR-H6 205/300 + state 资产 15+ 项 + 健康度 3 条 + stale 3 条 + 抗 compact 签字 5 条

### WP-03 review-contract.yaml schema + 3 stale 物理清理（待执行）

#### 3a：review-contract.yaml 增 2 处顶层字段

紧跟 H5 `inflation` 字段之后，在 `bindings:` 之前插入：

```yaml
# ── ADR-H6 §3 INV-H6-1: state 清单 schema 化 ──
# 把 .towow/state + .towow/proposals + .towow/guard + .towow/log + .towow/inbox + .towow/evidence
# 等 state 资产收口为顶层清单。kind: dynamic / archived / append-only / managed-by-other-h
state_inventory:
  - id: state-mode
    path: ".towow/state/mode"
    kind: dynamic
    owner: towow-mode-toolkit
  - id: state-run
    path: ".towow/state/run.json"
    kind: dynamic
    owner: towow-mode-toolkit
  - id: state-locks
    path: ".towow/state/locks.json"
    kind: dynamic
    owner: towow-mode-toolkit
  - id: state-completion-proposal
    path: ".towow/state/completion-proposal.json"
    kind: dynamic
    owner: towow-review-toolkit
  - id: state-risk-snapshot
    path: ".towow/state/risk-snapshot.json"
    kind: dynamic
    owner: risk-tracker
  - id: state-round-verdicts
    path: ".towow/state/round{1-5}-verdicts/"
    kind: archived
    owner: harness-review-history
  - id: state-archived-dir
    path: ".towow/state/_archived/"
    kind: archived
    owner: ADR-H6
  - id: proposals-self-evolution
    path: ".towow/proposals/"
    kind: append-only
    owner: vNext-self-evolution
    note: "265 文件; 只增不删"
  - id: guard-loop-counter
    path: ".towow/guard/"
    kind: append-only
    owner: harness-guard
    note: "11321 文件; #4 认知修正; 活工具态非污染"
  - id: log-self-symptoms
    path: ".towow/log/harness-self-symptoms.md"
    kind: append-only
    owner: H 系列
  - id: log-hook-ledger
    path: ".towow/log/hook/"
    kind: append-only
    owner: 各 hook
  - id: inbox-mailbox
    path: ".towow/inbox/"
    kind: managed-by-other-h
    owner: ADR-H9
    note: "main/quarantine/schema/window-h{0-6,8,9}"
  - id: evidence-packets
    path: ".towow/evidence/"
    kind: managed-by-other-h
    owner: 各 PLAN

# ── ADR-H6 §3 INV-H6-2: state 健康度指标 schema 化 ──
state_health_indicators:
  - id: schema-validity
    desc: "5 个 dynamic JSON 文件 JSON parse 通过 + 必填字段非空"
    check: "python3 -c 'import json; [json.load(open(p)) for p in [\".towow/state/run.json\", \".towow/state/locks.json\", \".towow/state/completion-proposal.json\", \".towow/state/risk-snapshot.json\"]]'"
  - id: top-level-no-noise
    desc: ".towow/state/ 顶层无 .DS_Store / 未归档 archived 文件 / 临时文件"
    check: "ls .towow/state/.DS_Store .towow/state/*archived*.json 2>/dev/null | wc -l"
    expect: 0
  - id: inbox-unread-volume
    desc: ".towow/inbox/main/unread/ ≤50 文件（H9 ADR 红线复用）"
    check: "ls .towow/inbox/main/unread/ 2>/dev/null | wc -l"
    expect_max: 50
```

DoD：
- yaml diff 仅新增上述 2 处顶层字段（不删任何已有字段；4 active binding + H5 三字段不动）
- yaml 总行数 ≤270
- `python3 -c "import yaml; doc = yaml.safe_load(open(...)); assert len(doc['state_inventory']) >= 10; assert len(doc['state_health_indicators']) >= 3"` 通过
- `grep -c "active: true"` = 4

#### 3b：3 stale 物理清理

```bash
# 1. 创建 _archived/
mkdir -p .towow/state/_archived

# 2. 移动 archived JSON
git mv .towow/state/completion-proposal-profile-build-cli-archived-20260419-1110.json \
       .towow/state/_archived/completion-proposal-profile-build-cli-archived-20260419-1110.json

# 3. 移动 14 天前 review 目录
git mv .towow/state/harness-review-2026-04-14 \
       .towow/state/_archived/harness-review-2026-04-14

# 4. 删除 .DS_Store
git rm --cached .towow/state/.DS_Store 2>/dev/null || rm -f .towow/state/.DS_Store

# 5. .gitignore 增 1 行
echo ".towow/state/.DS_Store" >> .gitignore  # 实际用 Edit 工具不用 echo
```

DoD：
- `ls .towow/state/.DS_Store` = 不存在
- `ls .towow/state/_archived/` 含 2 项
- `grep ".towow/state/.DS_Store" .gitignore` ≥1
- `ls .towow/state/*archived*.json` 顶层 = 0
- 健康度指标 `top-level-no-noise` check = 0

**race-safe commit**：3a 和 3b 分两个 commit，避免 yaml schema + 文件移动混在同一 commit；commit 用 `git commit --only <paths>` 隔离他 session。

### WP-04 dogfood — H6 自指自检

期望输出（`docs/decisions/tasks/PLAN-H6/WP-04/dogfood-output-<ts>.md` ≤80 行）：

```markdown
---
plan: PLAN-H6
wp: WP-04
trigger: ADR-H6 §10 dogfood 规划
date: <ts>
status: self-check-result
---

# H6 自指自检结果

## §1 INV-H6-1（state 清单 schema 化）
- review-contract.yaml state_inventory 项数实测
- 起草 H6 过程是否触犯 line_caps（ADR-H6 ≤300 + PLAN-H6 ≤500 + yaml ≤270）

## §2 INV-H6-2（健康度指标）
- 3 条指标 schema 字段实测 yaml.safe_load
- 每条 indicator 的 check 命令实际执行结果

## §3 INV-H6-3（零机制实际引入 4 项检测，复用 H5）
- find newer .py = 0
- hook diff = empty
- yaml mechanism field = 0
- 反例段排除后动词搭配 = 0

## §4 stale 清理执行结果
- .DS_Store 删除 ✓/✗
- archived JSON 移动 ✓/✗
- harness-review-2026-04-14 移动 ✓/✗

## §5 抗 compact 接口签字（plan §3.3 H6 DoD）
- ADR-042 D3 / D4 / D9 引用确认
- 不重做、不另建（红线）

## §6 自指悖论（继承 H5 §4）
- 本 dogfood 文档自身受 INV-H6-1 约束（≤80 行）
- 不引入新机制（纯 markdown）
```

DoD：
- 文件存在 ≤80 行
- INV-H6-3 4 项检测命令实际执行（不是 placeholder）
- 抗 compact 签字段非空

### WP-05 reviewer signoff（独立 subagent）

verdict 路径（INV-H5-2 evidence_path_pattern 满足）：
`docs/decisions/tasks/PLAN-H6/WP-05/reviewer-verdict-<ts>.md`

reviewer 验证 14 维度（结构同 H5 WP-05，特化项见下表）：

| # | 维度 | 验证命令 |
|---|------|----------|
| 1 | ADR-H6 ≤300 | `wc -l docs/decisions/ADR-H6-state-file-health.md` |
| 2 | PLAN-H6 ≤500 | `wc -l docs/decisions/PLAN-H6-state-file-health.md` |
| 3 | review-contract.yaml ≤270 | `wc -l ...review-contract.yaml` |
| 4 | INV-H6-1 state_inventory ≥10 | `python3 -c "import yaml; print(len(yaml.safe_load(open(...))['state_inventory']))"` |
| 5 | INV-H6-2 state_health_indicators ≥3 | 同 yaml.safe_load 路径 |
| 6 | INV-H6-3 检测 1: find newer .py | `find ... -name "*.py" \| wc -l` = 0 |
| 7 | INV-H6-3 检测 2: hook diff | `git diff --stat -- 'scripts/hooks/h6*' '.claude/plugins/*/hooks/h6*' \| wc -l` = 0 |
| 8 | INV-H6-3 检测 3: yaml field | `grep -cE "^\s*(cron\|schedule\|polling_interval\|auto_*):" review-contract.yaml` = 0 |
| 9 | INV-H6-3 检测 4: 反例段排除后动词搭配 | awk 排除 §3/§7/§9 后 grep | = 0 |
| 10 | yaml 语法合法 | `python3 -c "import yaml; yaml.safe_load(open(...))"` |
| 11 | 4 active binding + H5 三字段未破坏 | `grep -c "active: true"` = 4 + line_caps/inflation/drafter_reviewer_separation 仍存在 |
| 12 | stale 清理实测 | `ls .towow/state/.DS_Store .towow/state/*archived*.json 2>/dev/null \| wc -l` = 0 + `ls .towow/state/_archived/ \| wc -l` ≥ 2 |
| 13 | .gitignore 含 .DS_Store 规则 | `grep "\.towow/state/\.DS_Store" .gitignore` ≥1 |
| 14 | H0.meta H{7,10,11,12} 排除 code block | `awk '/^\`\`\`/{f=!f;next} !f' \| grep -cE "\bH(7\|10\|11\|12)\b"` = 0 |

DoD：14 维度全 PASS；零 P0/P1/P2；P3 不阻塞。

## §3 跨 H 冲突协调

| 文件 | H6 × 哪个 H | 处置 |
|------|------------|------|
| review-contract.yaml | H6 ↔ H5（已落地）↔ 未来 H8 | H5 三字段不动；H6 加 2 字段；H8 如要加字段需要在 H8 PLAN 显式锁字段名 |
| `.towow/inbox/` | H6 仅 reference 不动 | H9 受管 |
| `.towow/proposals/` | H6 仅 reference | self-evolution 只增不删 |
| `.towow/guard/` | H6 仅 reference | 活工具态 |
| ADR-042 D3/D4/D9 | H6 仅签字接受 | ADR-042 受管 |

`§4.9 cross-plan-class race` 防御：起草本 PLAN 期间检查 `git status` 无 merge state；commit 前再核。

## §4 race-safe commit 计划

| commit | 内容 | 命令 |
|--------|------|------|
| 1 | ADR-H6 + PLAN-H6 起草 + WP-04 dogfood | `git add ADR-H6 PLAN-H6 WP-04/dogfood && git commit --only <paths>` |
| 2 | review-contract.yaml schema 修改 | `git commit --only .claude/plugins/towow-review-toolkit/contracts/review-contract.yaml` |
| 3 | 3 stale 物理清理（git mv + git rm + .gitignore） | `git mv ... && git rm ... && git commit --only <文件 + .gitignore>` |
| 4 | WP-05 reviewer signoff verdict | `git add <verdict>.md && git commit --only <verdict>.md` |

H6 是 4 commit 链（H1/H4/H5 是 3 commit；H6 因 stale 清理多 1 commit）。每 commit 前 `git status` 核 merge state。

## §5 H0 自检（条款逐项）

| 条款 | 状态 |
|------|------|
| H0.1 施工隔离 | ✅ scope 明确（review-contract.yaml + .towow/state/_archived/ + 3 stale + .gitignore；禁动 hook/proposals/guard/inbox/evidence/round-verdicts） |
| H0.2 行数限额 | 待 wc -l 终稿验证（estimated 230-260 ADR / 290-330 PLAN） |
| H0.3 执检分离 | ✅ WP-05 独立 subagent + verdict 文件 |
| H0.4 自指禁止 | ✅ INV-H6-3 直接复用 H5 修正版（不重新发明，避免 INV-H1-3 朴素 grep 自指 false positive 复现） |
| H0.5 跨 H 协调 | ✅ §3 冲突表（review-contract.yaml H5+H6；不撞 H8） |
| H0.6 证据机械化 | ✅ §2 WP-03/04/05 全部给 grep/wc/python3/find 命令 |
| H0.meta | ✅ awk 排除 code block 后扫描已退役/未来 H 引用 = 0（详见 §5 验证命令；裸字面 token 全部装入 code fence 避免自指） |

## §6 与现行 vNext 共存（H 系列 plan §3.3.3）

- review-contract.yaml 修改前后跑 yaml.safe_load 验证
- `.towow/state/_archived/` 新建对 verify-gate.py / transition.py / capability-router.py 透明（仅清理顶层噪声，不动 dynamic state 文件位置）
- 3 stale 移动用 `git mv` 保留历史；只 .DS_Store 用 `git rm`（macOS 噪声无价值）
- 如某 stale 移动后 verify-gate.py 找不到文件 → 立即 `git mv` 还原 + ADR-H6 补丁

## §7 参考链接

- ADR-H0 §H0.1-H0.6: docs/decisions/ADR-H0-meta-charter.md
- ADR-H4 INV-H4-3 反例表: docs/decisions/ADR-H4-prompt-governance.md
- ADR-H5 INV-H5-3 修正版: docs/decisions/ADR-H5-gate-quantization.md §3
- review-contract.yaml H5 三字段: commit 872f03ce
- ADR-042 D3 / D4 / D9: docs/decisions/ADR-042-parallel-dev-state-management.md
- H5 WP-05 verdict 模板: docs/decisions/tasks/PLAN-H5/WP-05/reviewer-verdict-20260428-185114.md

## §8 进度

- [x] WP-01 现状盘点（2026-04-28T19:12）
- [x] WP-02 起草 ADR-H6 + PLAN-H6
- [ ] WP-03 review-contract.yaml schema + stale 清理（拆 2 commit） ← 当前
- [ ] WP-04 dogfood
- [ ] WP-05 reviewer signoff
