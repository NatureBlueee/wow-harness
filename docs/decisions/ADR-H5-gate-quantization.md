---
adr: ADR-H5
title: Gate 量纲化（行数硬限 schema 化 + 执检分离 binding 化 + 跳 Gate 决策表）
status: accepted
date: 2026-04-28
parent_charter: ADR-H0-meta-charter.md
philosophy_inheritance:
  - ADR-041-codex-integration v1.0（"调字不加机制"）
  - ADR-H4 INV-H4-3 反例表第 2 条（不写 metrics / 不写 dashboard / 不写 hook 治节奏）
  - ADR-038 D11.2（schema-level 100% 遵从 >> prompt-level 70%）
applies_scope:
  - .claude/plugins/towow-review-toolkit/contracts/review-contract.yaml
  - .claude/plugins/towow-review-toolkit/agents/reviewer.md（仅引用，不改）
  - 本 ADR 自身（自指 dogfood）
not_in_scope:
  - .claude/skills/lead/SKILL.md（H4 占位；本 H 不动）
  - 任何新 hook（INV-H5-3 红线）
  - .towow/state/ 下新增 metrics 文件（INV-H5-3 红线）
---

# ADR-H5：Gate 量纲化

## §1 上下文

### 1.1 已有的"Gate 真相源"（review-contract.yaml）

`.claude/plugins/towow-review-toolkit/contracts/review-contract.yaml` 当前 4 个 active binding：

| binding | applies_when | reviewer.type | 阻塞何处 |
|---------|-------------|---------------|----------|
| `default-build-review` | mode=build, task_kind=code_change | pane | mode → verify |
| `merge-ready-review` | mode=verify, transition→release | subagent (`reviewer`) | mode → release |
| `design-review` | mode=plan, transition→build | human | mode → build |
| `retirement-review` | operation=retire_asset | pane | retire 动作 |

`verify-gate.py` Stop hook 按 binding 校验 evidence packet → 决定 stop allow/block；`transition.py` 按 transition_target 校验。**这是已有的 schema-level 真相源**——H5 不重建，H5 是"补字段"。

### 1.2 散落的行数限额（4 个 ADR、4 处口径）

| 来源 | 限额 | 适用 |
|------|------|------|
| ADR-H0 §H0.2 | ADR ≤300 / PLAN ≤500 | 所有 H 子计划文档 |
| ADR-H1 INV-H1-1 + 受管资产 | lead/SKILL.md "## 触发节奏（H1）" 段 ≤30 行；全文 ≤220 | H1 嵌入段 |
| ADR-H3 INV-H3-2 v1.1 | MEMORY.md `## ` 父段 ≤80 / `### ` 子段 ≤50 / 主索引 ≤200 | MEMORY.md |
| ADR-H4 INV-H4-1 | lead/dev/nature-designer skill prompt 段 ≤30 行 | H4 受管 SKILL.md 段 |

各 ADR 独立写、独立约束、独立验证（每个 ADR 自己的 §H0 自检表手动 wc -l），**没有 schema-level 收口**。reviewer 必须人脑读每个 ADR 才知道某文件应该限多少行，prompt-level 70% 遵从。

### 1.3 已发生的 4 次"非起草人 reviewer signoff"

| H | verdict 文件 | 路径形态 |
|---|-------------|---------|
| H2 | reviewer-verdict-20260428-1730.md | tasks/PLAN-H2/（根） |
| H3 | reviewer-verdict-20260428-1741.md | tasks/PLAN-H3/（根） |
| H4 | reviewer-verdict-20260428-1810.md | tasks/PLAN-H4/（根） |
| H1 | reviewer-verdict-20260428-183611.md | tasks/PLAN-H1/WP-05/（WP 子目录） |

**两个一致 + 两个不一致**：路径形态发散；reviewer subagent 类型一致（都是 `pr-review-toolkit:code-reviewer`），但 spawn 方式无 contract 约束——靠"上次怎么做这次照做"的 prompt-level 模式复用，70% 遵从。

### 1.4 触发动机

H 系列 PLAN §3.3 给 H5 的 DoD：**Gate 清单 ≥5 + inflation 规则 ≥3 + 跳 Gate 决策表 + 自指自检**。本 ADR 给出 H5 决策本质，不是工程节奏（节奏在 PLAN-H5）。

## §2 决策本质（Decision Substance）

**一句话**：把 §1.2 的行数限额和 §1.3 的执检分离从"散落 prompt + 人脑遵从"升级到 review-contract.yaml 的 `inflation` 子字段，让 verify-gate.py 直接读 schema 判定，不再需要 reviewer 人脑遍历 ADR。

**只调字（schema 字段），不加机制（不写新 hook、不写 metrics、不建 dashboard）**——继承 ADR-041 v1.0 + ADR-H4 INV-H4-3 反例表第 2/3 条。

**与 H4 边界**（H 系列 plan §3.3.1 表）：
- H4 = prompt 治理（lead/SKILL.md 行为偏好段，纯文字，prompt-level 70%）
- H5 = Gate 量纲化（review-contract.yaml inflation 字段，纯 yaml，schema-level 100%）
- 不交叉：H5 不动 SKILL.md prompt 段；H4 不动 review-contract.yaml

## §3 INV-H5（不变量，3 条）

### INV-H5-1：行数硬限 schema 化

review-contract.yaml 增加 top-level `line_caps` 字段（注：不是每个 binding 重复写，而是顶层一次性定义、binding 通过 ref 引用），列出 §1.2 4 处散落的限额，**作为 verify-gate.py 校验 evidence packet 时的可读字段**。每条 cap 字段格式：
```yaml
line_caps:
  - id: adr-h-series
    glob: "docs/decisions/ADR-H*.md"
    max_lines: 300
    source_adr: ADR-H0 §H0.2
  ...
```

**红线**：
- 修改限额数值不算 H5 工作面（数值由各原始 ADR 决定，H5 仅做收口聚合 + ref 指针）
- 增加新 cap 项必须在原始 ADR 中先有"≤N 行"明文规定

### INV-H5-2：执检分离 binding 化

review-contract.yaml 的 `merge-ready-review` binding 增加 `drafter_reviewer_separation` 子字段：

```yaml
drafter_reviewer_separation:
  required: true
  rationale: ADR-H0 §H0.3 执检分离
  evidence_path_pattern: "docs/decisions/tasks/PLAN-{plan}/WP-05/reviewer-verdict-*.md"
  reviewer_subagent_whitelist:
    - pr-review-toolkit:code-reviewer
    - towow-review-toolkit:reviewer
```

**统一 verdict 路径形态为 `WP-05/`** —— H1 的形态（已经发生，不改 H1/2/3/4 的历史 verdict 文件位置）；新一轮起草必须遵守。

**红线**：
- 不实施"自动 spawn reviewer"逻辑（H5 仅声明 schema，spawn 仍由起草人手动触发——这是 ADR-H4 INV-H4-3 反例表第 4 条 ❌"加 SKILL.md 教 AI 自己识别推卸"的反向预防）

### INV-H5-3：零机制实际引入（不只是关键词）

**验证 = 实际引入检测**（不是裸 word frequency；反例声明 / 验证命令字符串自身不算违反，避免自指悖论）：

1. `find docs/decisions/tasks/PLAN-H5 .claude/plugins/towow-review-toolkit -newer docs/decisions/ADR-H0-meta-charter.md -name "*.py"` = 0（H5 工作面无新增 hook py 文件）
2. `git diff --stat HEAD~10..HEAD -- 'scripts/hooks/h5*' '.claude/plugins/*/hooks/h5*'` = empty（无 H5 命名的 hook 引入）
3. review-contract.yaml diff 中无 `cron:` / `schedule:` / `polling_interval:` / `auto_spawn_reviewer:` 等 schema 字段
4. ADR-H5 + PLAN-H5 § 正文（排除 §3 INV-H5-3 / §7 不做什么 / §9 H0 自检验证命令字符串）不引入机制实施动词（"创建"/"启动"/"调度"+ metrics|dashboard|hook 名词搭配）

**等价于 INV-H1-3 的 H5 翻版** + **修正 INV-H1-3 朴素 grep 的自指 false positive**：把 ADR-H4 INV-H4-3 反例表升级到 schema-检查级。

## §4 跳 Gate 决策表（DoD ≥5 行）

| # | 场景 | 是否可跳 | 需要什么签字 | 证据落地 |
|---|------|----------|-------------|---------|
| 1 | binding active=false（review-contract.yaml 中显式声明非活跃） | ✅ 跳 | yaml `active: false` 即声明 | yaml diff 即证据 |
| 2 | retirement-review 类高放射半径动作 | ❌ 不可跳 | human attestation | evidence packet kind=retire |
| 3 | merge-ready-review 起草人 = reviewer 同体 | ❌ 不可跳 | INV-H5-2 binding 强制 | WP-05/ verdict 文件存在性 |
| 4 | line_caps 超限 | ⚠ 条件跳 | 起草人显式 disclosure（ADR §H0 自检段写"已知超限 N 行 + 理由"）+ Nature 单签 | ADR diff 显式 disclosure 段 |
| 5 | design-review (plan→build transition) | ❌ 永不可跳（review-contract.yaml `bypass_requires: never`） | — | yaml 即证据 |
| 6 | hot-fix（生产 P0 issue） | ⚠ 24h 内补 reviewer signoff | Nature 口头授权 + issue 文档 | docs/issues/guard-*.md + 24h 内 reviewer-verdict-*.md |

**红线**：跳 Gate ≠ 不留证据。任何跳过路径必须有可机器读的痕迹（yaml 字段 / disclosure 段 / issue 文档）——满足 ADR-H0 §H0.6 证据机械化。

## §5 inflation 规则（DoD ≥3 条）

### 规则 1：行数硬限优先于"先合并再清理"
ADR-H0 §H0.2 已有，本 ADR 强化为 review-contract.yaml `inflation.no_grow_now_clean_later` 字段。任何 PR 提交 line_caps 超限 → verify-gate.py 直接 block，不接受"merge 后下个 PR 拆"理由。

### 规则 2：非起草人 reviewer 强制
INV-H5-2 已声明 schema；本规则补充：reviewer 与起草人必须不同 session（H0.3 执检分离的实操）；`pr-review-toolkit:code-reviewer` subagent 自身就是不同 session，物理满足。

### 规则 3：自指自检段必填
任何 ADR-Hx 必须包含 `## §H0 自检` 段，列出 H0.1-H0.6 + H0.meta 7 条逐条勾选状态——本 ADR §10 即为示范。verify-gate.py 通过 grep `^## .*H0 自检` 校验存在性。

## §6 H4 vs H5 边界（再次强调）

| 关注点 | H4（已闭合） | H5（本 ADR） |
|--------|-------------|-------------|
| 改的文件 | lead/SKILL.md（prompt） | review-contract.yaml（schema） |
| 治什么 | 行为偏好（黑话/推卸/过度 review） | 节奏/限速/执检分离 |
| 遵从层级 | prompt-level 70% | schema-level 100% |
| 哲学 | 调字不加机制 | 调字（yaml 是"字"）不加机制 |

H5 不撤销 H4，也不重写 H4 的 prompt 段。两者并行生效。

## §7 不做什么（边界声明）

- ❌ 不写新 hook（INV-H5-3 红线）
- ❌ 不在 verify-gate.py 加新逻辑（仅靠 yaml schema 字段读取，原有 contract-driven 框架已够用；如果某字段需要解释，由后续单独 ADR 决定）
- ❌ 不动 H4 的 SKILL.md prompt 段
- ❌ 不动 H1 的"## 来自 crystal-learn 的门禁"接收段
- ❌ 不引入 metrics/dashboard（INV-H5-3）
- ❌ 不"自动 spawn reviewer"——人手起 subagent 仍是当前模式（70% 遵从足够；schema 级别只规范"必须发生"和"形态"，不规范"如何触发"）

## §8 受管资产（scope 锁死）

| # | 路径 | 动作 | 限额 |
|---|------|------|------|
| 1 | `.claude/plugins/towow-review-toolkit/contracts/review-contract.yaml` | 增加 `line_caps` 顶层字段 + 在 `merge-ready-review` binding 增加 `drafter_reviewer_separation` 子字段 + `inflation` 顶层字段 | 当前 132 行 → 目标 ≤220 行 |
| 2 | `docs/decisions/ADR-H5-gate-quantization.md` | 本 ADR | ≤300 行 |
| 3 | `docs/decisions/PLAN-H5-gate-quantization.md` | 工程计划 | ≤500 行 |
| 4 | `docs/decisions/tasks/PLAN-H5/WP-04/dogfood-output-*.md` | dogfood 产出 | ≤80 行 |
| 5 | `docs/decisions/tasks/PLAN-H5/WP-05/reviewer-verdict-*.md` | reviewer signoff | 由 reviewer 决定 |

**禁动**：
- `.claude/skills/lead/SKILL.md`（H4 受管）
- `~/.claude/skills/towow-crystal-learn/SKILL.md`（H1 受管）
- `~/.claude/projects/-Users-nature------Towow/memory/MEMORY.md`（H3 受管）
- 任何 hook 文件（INV-H5-3）

## §9 H0 自检（H0.1-H0.6 + H0.meta）

| 条款 | 内容 | 本 ADR 状态 |
|------|------|-------------|
| H0.1 施工隔离 | scope 显式列出 | ✅ §8 受管资产表 + frontmatter applies_scope |
| H0.2 节流限速 | ADR ≤300 行 | ✅ 终稿 wc -l 验（estimated 200-220） |
| H0.3 执检分离 | 起草人 ≠ 签字人 | ✅ WP-05 reviewer subagent 独立 |
| H0.4 自指禁止 | 不重现要修的症状 | ✅ INV-H5-3 + §7 反例表是 ADR-H4 INV-H4-3 第 2/3 条的本 H 翻版，物理避免 |
| H0.5 跨 H 协调 | 共改文件冲突表 | ✅ §6 H4/H5 边界表；review-contract.yaml 仅本 H 改动 |
| H0.6 证据机械化 | DoD 证据机器可生成 | ✅ §4 跳 Gate 表 + §5 规则均给 grep/yaml field 校验路径 |
| H0.meta | 不引未来 H | ✅ grep `H[6-9]` = 0（H9 已存在不算未来；下方 grep 验证） |

H0.meta 验证命令（排除 code block，避免命令字符串自指 false positive）：
```bash
awk '/^```/{f=!f; next} !f' docs/decisions/ADR-H5-gate-quantization.md | grep -cE "\bH[6-8]\b"
# 应为 0（H6/H7/H8 是未来 H；排除 code block 后命令字符串自身不算引用）
```

## §10 dogfood 规划

H5 自身走一次 Gate 即 PLAN-H5 WP-04：
- 起草本 ADR-H5 + PLAN-H5 时，本身要满足 INV-H5-1（行数）+ INV-H5-3（无机制关键词）
- WP-04 dogfood-output-*.md 记录"H5 起草过程触发了哪些 line_caps 边界"
- WP-05 reviewer signoff 验证"H5 自己是否被 H5 的规则约束住"——典型 ADR-038 D11.2 实例

## §11 与现行 vNext 共存

- review-contract.yaml 修改前必须 `git diff` 验证：4 active binding 未被破坏
- 修改后跑 `verify-gate.py` 一次手动测试（PLAN-H5 WP-03 DoD）
- 如发现 verify-gate.py 因新字段崩溃 → 回退 yaml + ADR-H5 重新设计字段位置（H 系列 plan §3.3.4 中等回退）
