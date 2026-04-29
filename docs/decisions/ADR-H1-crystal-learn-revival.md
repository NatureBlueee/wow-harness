---
adr: ADR-H1
title: crystal-learn 学习层复活——触发节奏物理化（不加机制）
status: Accepted
version: 1.0
date: 2026-04-28
owner: nature
window_owner: shared
window_owner_since: 2026-04-28T18:30+08:00
parent_plan: 39-h-h-h-h-hanis-refactored-toucan
inherits_philosophy:
  - ADR-041-v1.0-codex-routing  # 调字不加机制
  - ADR-H4-prompt-governance    # H4 INV-H4-3 哲学硬继承
related_skills:
  - ~/.claude/skills/towow-crystal-learn/SKILL.md  # 学习层（已就位，89 行成熟契约）
  - .claude/skills/lead/SKILL.md                   # 接收侧（line 142 已布线）
problems_addressed:
  - "#1 自我进化健康度停摆 11 天（最后 round verdict 2026-04-17）"
  - "#2 crystal-learn skill 周期触发停了 4 周"
  - "#7 crystal-learn 没退役（认知修正，问题降级）"
---

# ADR-H1：crystal-learn 学习层复活——触发节奏物理化（不加机制）

## §1 上下文

### 1.1 stop-the-bleed 现状（来自 H 系列 plan §2.1 Phase 1 调研）

- crystal-learn skill 文件 `~/.claude/skills/towow-crystal-learn/SKILL.md` **存在且成熟**（89 行；status=active；tier=meta；INV-0..INV-7 全部映射到 active target skills）
- crystal-learn 接收侧 `.claude/skills/lead/SKILL.md` line 142 **已布线**（`## 来自 crystal-learn 的门禁` 段含 INV-4 真相源分裂 + INV-6 验证衰减 + Gate 8 PASS 宣告规则）
- crystal-learn skill commit 历史最近一次产出 `c80f2b48`（2026-04-25 billing INV-5/6 sync）；之前 `8925d8f1`（4 skill 沉淀）→ `479a6b70`（INV-1/6 instances）→ 4-5 个月静默期
- harness-self-symptoms.md 累计 **9 条** symptom（§4.1-§4.9），其中 §4.7/§4.8 同根复发（"起草不实证"），§4.9 是新型号（cross-plan-class race）；处置段已生成 ADR-H0 修订建议第 8/9/10 条**未消化**

### 1.2 root cause（4 周停摆）

不是基础设施缺失，是**触发节奏断了**。crystal-learn 现有触发依赖：

- (A) Nature 主动启动（人脑提醒）
- (B) Gate 收尾时手工触发（依赖 reviewer / coordinator 在 Gate 8 闭环时记得调用）

H 系列实施 11 天累积，Nature 已超载；reviewer / coordinator 角色在 H4 之前未稳定到位。两条触发轴都失效。

### 1.3 不是什么

- 不是 crystal-learn skill 本身契约问题（output contract = invariant delta + target injection map 已明确）
- 不是接收侧布线问题（lead/SKILL.md line 142 段已存在）
- 不是缺机制（写 cron / 加 hook 是 #20 推卸 + ADR-041 v1.0 红线 + H4 INV-H4-3 反例）

## §2 决策本质

把"何时触发 crystal-learn"从隐式人脑依赖转为显式 prompt-level checklist，**写进 lead/SKILL.md**（CLAUDE.md 隐式默认加载，70% adherence baseline）。继承 ADR-041 v1.0 "调字不加机制" + H4 INV-H4-3 "禁 hook/metrics/review-contract"。

具体：

1. 触发条件 ≤5 条，全部物理化为 lead/SKILL.md 段（≤30 行，同 H4 INV-H4-1）
2. 落地路径用现有"## 来自 crystal-learn 的门禁"段（不新建文件）
3. 受管资产 scope 严格列出（H0.1 施工隔离）

## §3 不变量（INV-H1）

### INV-H1-1 触发条件 ≤5 条

> Why：防 ADR-041 v0.1→v0.3 膨胀剧本重演；H4 INV-H4-1 同结构（≤10 条 / H1 更紧因为是触发表非分类清单）。
> 验证：`awk` 计触发条件计数 ≤5。

### INV-H1-2 落地路径必须落到现有接收段

> Why：每新建文件 = 一个新真相源分裂点（INV-4），且违反 ADR-041 v1.0 "调字"原则。
> 验证：`grep -n "## 来自 crystal-learn 的门禁" lead/SKILL.md` 命中 1 次；H1 注入段嵌入此段下方。

### INV-H1-3 不写 cron / hook / 任何运行时机制

> Why：硬继承 H4 INV-H4-3 + ADR-041 v1.0 红线；任何 cron/hook 都是把"AI 自管理"机制化的失败模式（70% prompt baseline 已够用）。
> 验证：`grep -iE "cron|hook|schedule|metrics|setInterval|crontab" lead/SKILL.md` 在本次新增段命中 0。

## §4 触发节奏（5 条物理化触发条件）

按消费侧（AI 自识 → 主动调用 crystal-learn skill）：

| # | 触发条件 | 触发动作 | Why |
|---|----------|---------|-----|
| 1 | 主仓发现新型 symptom（与 self-symptoms.md 既有 §4.x 不同根） | 立即调用 crystal-learn，输入 = 新 symptom + 历史相关 symptom | 新 symptom 是结晶学习的天然原料；不及时消化会累积变成 §4.7/§4.8 同根复发 |
| 2 | 跨 PLAN 出现同类违规 ≥3 次（grep self-symptoms.md 同根模式数） | 调用 crystal-learn，输入 = 全部同根案例 | crystal-learn 升级规则要求 ≥2 案例；3 次触发"已是结构性偏差" |
| 3 | reviewer 给出 P0/P1 notes 涉及"教训未学" | 调用 crystal-learn 消化，输入 = reviewer notes + 关联 ADR/PLAN | 防 H4 §过度 review 第 3 条（PASS_WITH_NOTES 含 P0 仍 BLOCK）变成"修个表面 commit 完事"，不真升级 invariant |
| 4 | Gate 8 闭环前若 self-symptoms.md 自上次 crystal-learn 后新增 ≥3 条 | 调用 crystal-learn，输入 = 新增的 ≥3 条 | Gate 8 是天然消化 checkpoint；不能 PASS 一个 H 子计划但 symptoms 越积越多 |
| 5 | 任何 ADR-H0 修订建议累积 ≥3 条未消化 | 调用 crystal-learn，输入 = 未消化建议清单 | 修订建议是 invariant 候选；累积不消化 = 4 周停摆症状复发 |

**消费侧而非生产侧**：触发条件检查时机由"AI 自识"承担（lead/SKILL.md prompt-level 指令），不接受"等 Nature 提醒"。

## §5 落地路径模板

crystal-learn 输出 → 注入接收侧 SKILL.md：

```
crystal-learn output:
  invariant_delta:
    - confirmed: INV-X 描述（≥2 案例 + 跨场景）
    - candidate: INV-Y 描述（仅 1 案例 + 系统性形状）
    - new_instance: 已确认 INV 的新案例
  target_injection_map:
    - target: <skill 路径>
    - directive: <≤3-5 行行动指令>
    - rationale: <为什么放这里>
        ↓
注入动作:
  1. 已确认 invariant → 加到对应 SKILL.md "## 来自 crystal-learn 的门禁" 段
  2. 候选 invariant → 暂存 ADR-H0 修订建议表（待 ≥2 案例升级）
  3. 新案例 → reference/invariant-instances.md（不动 active SKILL.md）
  4. 注入后 target SKILL.md frontmatter `last_audited` 必须刷新
```

**模板硬规则**（写进 lead/SKILL.md 注入段）：
- 不新建独立 ADR/PLAN 文件来"装" invariant（INV-4 真相源分裂红线）
- 不在 active 执行层 SKILL.md 写完整理论（仅 ≤5 行行动指令）
- 完整理论留 reference 文档（INV-2 格式断崖反例）

## §6 受管资产 scope（H0.1 施工隔离）

| # | 路径 | 改动类型 | 行数预算 |
|---|------|---------|---------|
| 1 | `.claude/skills/lead/SKILL.md` | 在 line 142 "## 来自 crystal-learn 的门禁" 段下方追加 "## 触发节奏（H1）" 子段 | ≤30 行 |
| 2 | `docs/decisions/ADR-H1-crystal-learn-revival.md` | 新建本 ADR | ≤300 行 |
| 3 | `docs/decisions/PLAN-H1-crystal-learn-revival.md` | 新建 PLAN | ≤500 行 |
| 4 | `docs/decisions/tasks/PLAN-H1/WP-04/dogfood-output-20260428-{ts}.md` | dogfood 一次产出（§4.9 输入 → INV delta + injection map） | ≤80 行 |
| 5 | `docs/decisions/tasks/PLAN-H1/WP-05/reviewer-verdict-20260428-{ts}.md` | reviewer 报告 | ≤200 行 |
| 6 | `.towow/log/harness-self-symptoms.md` | append 新 §4.x 若 H1 实施期触发自指 | append-only |

**scope 外严格不动**：crystal-learn skill 文件本身（89 行成熟契约）、其它 SKILL.md（dev/eng/eng-test/bridge/ops/task-arch/plan-lock 接收段）。任何这些资产的修订必须先经 crystal-learn 输出 → 进 ADR-H0 修订表 → 收尾整体 commit；H1 阶段不动。

## §7 失败模式（FM）— 起草内防御

### FM1：触发条件 5 条膨胀到 N 条

复活成功后第一周容易膨胀（"再加一条"）。防御：INV-H1-1 硬数字 ≤5；超过必须先砍一条。

### FM2：lead/SKILL.md 200 行超 truncate

H4 已用掉 ~22 行段（line 158-180）；H1 再加 ≤30 行 → ~210 行风险。MEMORY.md scope policy（INV-H3-1）阈值 200。**预防措施**：H1 注入段写 ≤25 行（留 5 行 buffer）；正文最长不超过 27 行；段内全部用单行短句不用表格。

### FM3：触发后未真做（"prompt 70% adherence" 上限）

按 ADR-038 D11.2 schema-level vs prompt-level 数据，prompt 约束 ~70% adherence。意味着即使 lead/SKILL.md 写了触发条件，也有 30% 概率 AI 不调用 crystal-learn。**接受这个上限**（改 schema 化 = 写 hook = 违反 INV-H1-3）。**唯一升级条件**：连续 2 周观察期内有 ≥3 次触发条件命中但未调用记录在 self-symptoms.md → 升级讨论（不一定升级到 hook，可能调字辞）。

## §8 与 H4 关系（边界）

| 维度 | H4（已 closed）| H1（本 ADR）|
|------|---------------|-------------|
| 治理对象 | 行为偏好（黑话/推卸/过度 review/其它） | 元学习触发节奏 |
| 主要资产 | lead/SKILL.md "## 行为治理（H4 三类清单）" | lead/SKILL.md "## 触发节奏（H1）" 子段 |
| 哲学 | 调字不加机制 | 调字不加机制（同 H4） |
| INV 数 | ≥10 条三类清单 | ≤5 条触发条件 |
| 长度预算 | ≤30 行 | ≤25 行（FM2 buffer） |
| 调用 crystal-learn? | 否（H4 直接物理化静态规则） | 是（H1 是 crystal-learn 的"触发协议"，本身不重写规则） |

H4 是"把 6 条 memory feedback 物化"，H1 是"把元学习何时跑物化"。H4 静态、H1 元层。两者正交，互不动对方文件。

## §9 不做什么

- ❌ 不写 cron job 触发 crystal-learn（INV-H1-3 红线）
- ❌ 不加 PostToolUse hook 检测"应触发"（INV-H1-3 红线）
- ❌ 不建 dashboard 看 invariant 增长（同 ADR-041 反例 #3）
- ❌ 不复活的"复活"是给 crystal-learn 加新功能；H1 只触发现有契约
- ❌ 不在 crystal-learn skill 自己加治理段（学习层 ≠ 执行层；学习层只输出 invariant delta + injection map）
- ❌ 不更新 crystal-learn target injection map 表（那是 crystal-learn 自己的工作产物，由 invariant 升级触发）

## §10 H0 元规约 6+1 自检

- **H0.1 施工隔离**：本 ADR scope 严格在 §6 列表内；不动 crystal-learn skill / 其它 SKILL.md 接收段 / hook / cron / metrics
- **H0.2 节流**：本 ADR ≤300 行（验证：本文件 `wc -l`）；PLAN-H1 ≤500 行；H1 注入段 ≤25 行
- **H0.3 执检分离**：起草人 ≠ reviewer；WP-05 spawn read-only subagent 收尾
- **H0.4 自指禁止**：本 ADR 不写"待协调员决定 / TBD / 后续讨论"（H4 §推卸第 2 条）；不写 hook / metrics（H4 §3.6 FM2 + 本 ADR INV-H1-3）；起草前完整盘点（避 §4.7/§4.8 同根复发）
- **H0.5 跨 H 协调**：见 PLAN-H1 §4 跨 H 登记表（H4 line 158-180 已用，H1 紧接其后；不重叠）
- **H0.6 证据机械化**：所有 INV / DoD 给 grep / wc / awk 命令（PLAN-H1 §3 验证矩阵 + §7 verify bundle）
- **H0.meta**：grep `\bH[2-8]\b` 仅协调登记表 + §8 H4 边界 + 自检命中（无前置依赖引用）

## §11 dogfood 规划

WP-04 用 self-symptoms.md §4.9（cross-plan-class race，新型号）作为首次触发输入：

- 触发条件命中 = §4 表第 1 条（主仓发现新型 symptom）
- 输入：§4.9 完整描述 + 处置段（ADR-H0 修订建议第 10 条）
- 期望输出：
  - `invariant_delta.candidate` = "跨 plan-class race"（仅 1 案例，候选不已确认）
  - `target_injection_map.target` = ADR-H0 修订建议表 + lead/SKILL.md "## 来自 crystal-learn 的门禁" 段
  - `target_injection_map.directive` = ≤5 行（"施工前 git status 核 merge state；H0.5 协调表扩展为跨 plan-class"）
  - `target_injection_map.rationale` = 防 §4.9 同模式跨业务 PLAN 复发

DoD 落地物 = WP-04 输出文档（path 在 §6 #4），证明 crystal-learn 触发协议可消费。
