---
plan: PLAN-H5
adr_ref: ADR-H5-gate-quantization.md
status: in-progress
date: 2026-04-28
parent_plan: H 系列 plan §3.3（H5 行）
philosophy_inheritance:
  - ADR-041 v1.0
  - ADR-H0 §H0.1-H0.6 + H0.meta
  - ADR-H4 INV-H4-3 反例表
  - ADR-038 D11.2
applies_scope:
  - .claude/plugins/towow-review-toolkit/contracts/review-contract.yaml
  - docs/decisions/ADR-H5-gate-quantization.md
  - docs/decisions/PLAN-H5-gate-quantization.md
  - docs/decisions/tasks/PLAN-H5/**
not_in_scope:
  - 任何 hook 文件（INV-H5-3 红线）
  - .claude/skills/lead/SKILL.md（H4 占位）
  - verify-gate.py / transition.py（仅作为"读 yaml 字段"的消费方，不改其代码）
---

# PLAN-H5：Gate 量纲化工程计划

## §1 上下文与基线锁定

### 1.1 工程目标

把 ADR-H5 的 3 条 INV（行数限额 schema 化 / 执检分离 binding 化 / 零机制实际引入）落地到 review-contract.yaml；不动任何 hook、不写任何 metrics、不引入任何新机制。

### 1.2 基线锁定（带行数 + 时间戳，避免 §4.7/§4.8 同根复现）

| # | 资产 | 起草前实测 | 限额 | 时间戳（git log）|
|---|------|------------|------|------------------|
| 1 | `.claude/plugins/towow-review-toolkit/contracts/review-contract.yaml` | 132 行 / 4 active binding | ≤220 行 | 当前 HEAD ⇒ 末改 commit `c81xxxxx`（PLAN-098 时期） |
| 2 | `docs/decisions/ADR-H5-gate-quantization.md` | 212 行（已起草） | ≤300 | 本 PLAN commit 同步 |
| 3 | `docs/decisions/PLAN-H5-gate-quantization.md` | 本文件 | ≤500 | 同上 |
| 4 | `.claude/plugins/towow-review-toolkit/agents/reviewer.md` | 仅引用，不改 | — | — |
| 5 | `verify-gate.py` | 仅消费方，不改 | — | — |
| 6 | reviewer signoff 历史路径形态 | H1 在 WP-05/，H2/3/4 在 PLAN-Hx/ 根 | INV-H5-2 锁定为 WP-05/ | 4 文件已存在，不迁移 |
| 7 | 行数限额散落处 | ADR-H0 §H0.2 / ADR-H1 / ADR-H3 / ADR-H4 共 4 处 | INV-H5-1 收口为 yaml `line_caps` 顶层字段 | 4 ADR 不改文本，本 H 仅做 ref |

### 1.3 已知 race risk

`docs/handoffs/ownership.yaml` 在 git status 中显示 modified（其他 session）；`backend/product/admin/**` 多个未 commit 文件（PLAN-096 owning dev session）；任何 H5 commit 必须用 `git commit --only <H5 路径>` 隔离（§4.4 + §4.9 教训复用）。

## §2 WP 拆解（5 WP）

### WP-01 现状盘点（已完成 in 2026-04-28T18:50 session）
- DoD：基线表 §1.2 7 行齐全 + race risk §1.3 列出
- 实测：✅ 已完成（本 PLAN §1.2/§1.3 即证据）

### WP-02 起草 ADR-H5 + PLAN-H5（已完成）
- DoD：ADR-H5 ≤300 + PLAN-H5 ≤500 + INV ≥3 + 跳 Gate 决策表 ≥5 行 + inflation 规则 ≥3 条
- 实测：✅ ADR-H5 212 行 + 跳 Gate 表 6 行 + inflation 规则 3 条

### WP-03 修改 review-contract.yaml（待执行）

**目标**：在 review-contract.yaml 增加 3 处 schema 字段：

1. **顶层 `line_caps` 字段**（INV-H5-1）：
```yaml
line_caps:
  - id: adr-h-series
    glob: "docs/decisions/ADR-H*.md"
    max_lines: 300
    source_adr: "ADR-H0 §H0.2"
  - id: plan-h-series
    glob: "docs/decisions/PLAN-H*.md"
    max_lines: 500
    source_adr: "ADR-H0 §H0.2"
  - id: lead-skill-h-segment
    glob: ".claude/skills/lead/SKILL.md"
    max_lines: 220
    source_adr: "ADR-H1 受管资产 + ADR-H4 INV-H4-1"
  - id: memory-master-index
    glob: "~/.claude/projects/-Users-nature------Towow/memory/MEMORY.md"
    max_lines: 200
    source_adr: "ADR-H3 INV-H3-2 v1.1"
```

2. **`merge-ready-review` binding 增加 `drafter_reviewer_separation` 子字段**（INV-H5-2）：
```yaml
drafter_reviewer_separation:
  required: true
  rationale: "ADR-H0 §H0.3 执检分离"
  evidence_path_pattern: "docs/decisions/tasks/PLAN-{plan}/WP-05/reviewer-verdict-*.md"
  reviewer_subagent_whitelist:
    - "pr-review-toolkit:code-reviewer"
    - "towow-review-toolkit:reviewer"
```

3. **顶层 `inflation` 字段**（ADR-H5 §5 三条规则）：
```yaml
inflation:
  no_grow_now_clean_later: true
  drafter_reviewer_must_differ_session: true
  h0_self_check_segment_required: true
```

**DoD**：
- yaml diff 仅新增 3 处字段；不删任何已有字段；4 active binding 字段不动
- yaml 总行数 ≤220
- `python3 -c "import yaml; yaml.safe_load(open('.claude/plugins/towow-review-toolkit/contracts/review-contract.yaml'))"` 无 SyntaxError
- verify-gate.py 不修改；如新字段被读取需要后续 ADR

**race-safe commit**：`git commit --only .claude/plugins/towow-review-toolkit/contracts/review-contract.yaml`

### WP-04 dogfood — H5 自身走 Gate（自指自检）

**目标**：以本 PLAN-H5 起草过程为输入，验证 H5 的 3 条 INV 是否对自己生效。

**输入材料**：
- 本次 H5 起草过程的 git log（c356106b..H5 closure 时刻）
- ADR-H5 / PLAN-H5 / review-contract.yaml diff
- INV-H5-3 验证命令实际执行结果

**期望输出**（`docs/decisions/tasks/PLAN-H5/WP-04/dogfood-output-<ts>.md` ≤80 行）：

```markdown
---
plan: PLAN-H5
wp: WP-04
trigger: ADR-H5 §10 dogfood 规划
date: <ts>
status: self-check-result
---

# H5 自指自检结果

## INV-H5-1（行数 schema 化）
- review-contract.yaml line_caps 字段是否包含本 ADR-H5 + PLAN-H5 的 cap？
- 实测：[verify by grep + diff]

## INV-H5-2（执检分离 binding 化）
- WP-05 verdict 文件路径是否匹配 evidence_path_pattern？
- 实测：[verify by ls]

## INV-H5-3（零机制实际引入）
- find newer .py files = 0?
- git diff hook stat = empty?
- yaml diff cron/schedule fields = 0?
- 反例段排除后正文动词搭配 = 0?
- 实测：[四项 grep + find 命令实际执行结果]

## 自指悖论修正
- 本 dogfood 文档自身受 INV-H5 约束吗？
- 评估：[是/否 + 理由]
```

**DoD**：
- 文件存在 ≤80 行
- 4 项 INV-H5-3 检测命令实际执行（不是 placeholder）
- 自指悖论评估段非空

### WP-05 reviewer signoff（独立 subagent）

**目标**：spawn `pr-review-toolkit:code-reviewer` 独立 subagent（read-only directive），独立于本 session 起草人验收。

**verdict 文件路径**：`docs/decisions/tasks/PLAN-H5/WP-05/reviewer-verdict-<ts>.md`

**reviewer 验证 14 维度**（与 H1 WP-05 一致结构 + H5 特化项）：

| # | 维度 | 验证命令 |
|---|------|----------|
| 1 | ADR-H5 ≤300 | `wc -l docs/decisions/ADR-H5-gate-quantization.md` |
| 2 | PLAN-H5 ≤500 | `wc -l docs/decisions/PLAN-H5-gate-quantization.md` |
| 3 | review-contract.yaml ≤220 | `wc -l .claude/plugins/towow-review-toolkit/contracts/review-contract.yaml` |
| 4 | INV-H5-1 line_caps ≥4 项 | `python3 -c "import yaml; print(len(yaml.safe_load(open(...))['line_caps']))"` |
| 5 | INV-H5-2 binding 字段存在 | `python3 -c "...['bindings'][1]['drafter_reviewer_separation']"` |
| 6 | INV-H5-3 检测 1: find newer .py | `find docs/decisions/tasks/PLAN-H5 .claude/plugins/towow-review-toolkit -newer ADR-H0 -name "*.py" \| wc -l` = 0 |
| 7 | INV-H5-3 检测 2: hook diff | `git diff HEAD~5..HEAD --stat -- 'scripts/hooks/h5*' '.claude/plugins/*/hooks/h5*' \| wc -l` = 0 |
| 8 | INV-H5-3 检测 3: yaml field | `grep -cE "^\s*(cron\|schedule\|polling_interval\|auto_spawn_reviewer):" review-contract.yaml` = 0 |
| 9 | INV-H5-3 检测 4: awk 排除反例段后动词搭配 | `awk -v RS='## §' 'NR!=4 && NR!=8' ADR-H5 \| grep -cE "(创建\|启动\|调度).*(metrics\|dashboard\|hook)"` = 0 |
| 10 | yaml 语法合法 | `python3 -c "import yaml; yaml.safe_load(open(...))"` 无异常 |
| 11 | yaml 4 active binding 未破坏 | grep `active: true` count ≥4 |
| 12 | 跳 Gate 决策表 ≥5 行 | grep ADR-H5 §4 表 row count |
| 13 | inflation 规则 ≥3 | grep ADR-H5 §5 规则 count |
| 14 | H0.meta H[6-8] grep（排除 code block） | `awk '/^\`\`\`/{f=!f;next} !f' ADR-H5 \| grep -cE "\bH[6-8]\b"` = 0 |

**DoD**：14 维度全 PASS；零 P0 / 零 P1；P2/P3 转 issue 不阻塞 H5 闭合。

## §3 跨 H 冲突协调

按 H 系列 plan §3.4 冲突表：

| 文件 | H5 × 哪个 H | 处置 |
|------|------------|------|
| review-contract.yaml | H5 唯一 | 无冲突 |
| ADR-H0 §H0.2 行数限额 | H5 仅 ref，不改 | 无冲突 |
| 历史 reviewer-verdict 文件 | H1/2/3/4 已存在 | INV-H5-2 仅约束未来；不迁移历史 |
| `verify-gate.py` | H5 不改 | 无冲突；如未来要消费 line_caps 字段，单独 ADR |

**§4.9 cross-plan-class race 防御**：起草本 PLAN 期间检查 `git status` 无 merge state；commit 前再核一次。

## §4 race-safe commit 计划

| commit | 内容 | 命令 |
|--------|------|------|
| 1 | ADR-H5 + PLAN-H5 起草 + WP-04 dogfood 输出 | `git add docs/decisions/ADR-H5-gate-quantization.md docs/decisions/PLAN-H5-gate-quantization.md docs/decisions/tasks/PLAN-H5/WP-04/*.md && git commit --only <those paths>` |
| 2 | review-contract.yaml schema 修改 | `git commit --only .claude/plugins/towow-review-toolkit/contracts/review-contract.yaml` |
| 3 | WP-05 reviewer signoff verdict | `git add <verdict>.md && git commit --only <verdict>.md` |

**与 §4.9 教训对齐**：每个 commit 前 `git status` 核 merge state；如撞他 session merge，按 §4.9 处置（restore --staged + 推迟）。

## §5 H0 自检（条款逐项）

| 条款 | 状态 |
|------|------|
| H0.1 施工隔离 | ✅ scope 明确（review-contract.yaml + 本 H 文档；禁动 hook/SKILL.md/MEMORY.md） |
| H0.2 行数限额 | 待 wc -l 终稿验证（estimated 250-300） |
| H0.3 执检分离 | ✅ WP-05 独立 subagent + verdict 文件 |
| H0.4 自指禁止 | ✅ INV-H5-3 修正 INV-H1-3 朴素 grep；不重现"自指 false positive" 症状 |
| H0.5 跨 H 协调 | ✅ §3 冲突表（H5 唯一改 review-contract.yaml） |
| H0.6 证据机械化 | ✅ §2 WP-05 14 维度全部给出 grep/wc/python3 命令 |
| H0.meta | ✅ awk 排除 code block 后 grep H[6-8] = 0 |

## §6 与现行 vNext 共存（H 系列 plan §3.3.3）

- review-contract.yaml 修改前 4 active binding 状态实测：`grep -c "active: true" review-contract.yaml` = 4
- 修改后跑 mock evidence packet 通过 verify-gate.py（如条件允许；否则 §4 commit 2 后第一次实际 mode transition 即验证）
- 如发现 verify-gate.py 因新字段崩溃 → §4 commit 2 revert + 字段位置重新设计

## §7 参考链接

- ADR-H0 §H0.1-H0.6: docs/decisions/ADR-H0-meta-charter.md
- ADR-H4 INV-H4-3 反例表: docs/decisions/ADR-H4-prompt-governance.md §3
- review-contract schema 文档: .claude/plugins/towow-review-toolkit/contracts/review-contract.yaml header comment
- evidence-packet schema: .claude/plugins/towow-review-toolkit/contracts/evidence-packet-schema.json
- ADR-038 D11.2 schema-level vs prompt-level: docs/decisions/ADR-038-harness-rebase.md
- H1 WP-05 verdict 模板（结构参考）: docs/decisions/tasks/PLAN-H1/WP-05/reviewer-verdict-20260428-183611.md

## §8 进度

- [x] WP-01 现状盘点（2026-04-28T18:55）
- [x] WP-02 起草 ADR-H5 + PLAN-H5（2026-04-28T19:00）
- [ ] WP-03 修改 review-contract.yaml ← 当前
- [ ] WP-04 dogfood
- [ ] WP-05 reviewer signoff
