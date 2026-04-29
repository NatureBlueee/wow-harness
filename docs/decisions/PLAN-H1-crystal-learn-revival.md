---
plan: PLAN-H1
adr: ADR-H1
title: crystal-learn 学习层复活——4 WP 工程拆解
status: in_progress
version: 1.0
date: 2026-04-28
owner: nature
window_owner: shared
window_owner_since: 2026-04-28T18:30+08:00
parent_plan: 39-h-h-h-h-hanis-refactored-toucan
estimated_effort: 2 天
---

# PLAN-H1：crystal-learn 学习层复活——4 WP 工程拆解

## §1 受管资产 + 现状基线

### 1.1 完整受管资产清单（H0.1 施工隔离）

| # | 路径 | 现状 | H1 改动 | DoD 行数 |
|---|------|------|---------|----------|
| 1 | `~/.claude/skills/towow-crystal-learn/SKILL.md` | 89 行 active 契约成熟 | **不动**（scope 外） | — |
| 2 | `.claude/skills/lead/SKILL.md` | 192 行（H4 后），line 142 "## 来自 crystal-learn 的门禁"段已布线 | line 192 后追加 "## 触发节奏（H1）" 子段 | ≤25 行（INV-H1-1 + FM2 buffer） |
| 3 | `docs/decisions/ADR-H1-crystal-learn-revival.md` | （本起草同 commit 创建） | 188/300 行 | ≤300 |
| 4 | `docs/decisions/PLAN-H1-crystal-learn-revival.md` | 本文件 | 起草中 | ≤500 |
| 5 | `docs/decisions/tasks/PLAN-H1/WP-04/dogfood-output-20260428-{ts}.md` | 待 WP-04 创建 | 创建 | ≤80 |
| 6 | `docs/decisions/tasks/PLAN-H1/WP-05/reviewer-verdict-20260428-{ts}.md` | 待 WP-05 创建 | 创建 | ≤200 |
| 7 | `.towow/log/harness-self-symptoms.md` | 145 行（含 §4.1-§4.9） | 若 H1 实施期触发自指 → append 新 §4.x | append-only |

### 1.2 现状基线（实证已做，避 §4.7/§4.8 同根复发）

| 实证项 | 命令 | 结果 | 时间 |
|--------|------|------|------|
| crystal-learn skill 存在 | `wc -l ~/.claude/skills/towow-crystal-learn/SKILL.md` | 89 | 2026-04-28 18:25 |
| crystal-learn 历史 | `git log --oneline --grep="crystal-learn" -10` | c80f2b48 → 8925d8f1 → 479a6b70 → 4-5 月静默 | 2026-04-28 18:20 |
| lead 接收侧 | `grep -n "## 来自 crystal-learn 的门禁" lead/SKILL.md` | line 142 命中 1 | 2026-04-28 18:20 |
| lead 当前长度 | `wc -l lead/SKILL.md` | 192（H4 后） | 2026-04-28 18:35 |
| self-symptoms 库存 | `awk '/^### 4\./{count++}END{print count}' harness-self-symptoms.md` | 9（§4.1-§4.9） | 2026-04-28 18:25 |
| §4.9 是新型号（dogfood 输入） | `grep -n "cross-plan-class race" harness-self-symptoms.md` | 1 处（§4.9 标题） | 2026-04-28 18:25 |
| git 状态 | `git status -b` + `test -f .git/MERGE_HEAD` | main，无 merge state（避 §4.9 同模式复发） | 2026-04-28 18:35 |

## §2 4 WP 工程拆解

### WP-01：现状盘点（已在起草前完成）

**结果**：完成。1.2 表中 7 项实证全部记录。

> **ADR-H1 起草前必做的"4 项核"**（feedback ADR/PLAN 引用受管资产前必先 wc/grep/ls）：
> 1. 路径核：crystal-learn skill 文件存在 ✓
> 2. 行数核：89 行 + lead 192 行 + symptoms 145 行 ✓
> 3. 字段核：crystal-learn frontmatter status=active / triggers / outputs / target injection map ✓
> 4. 前置 ADR 核：ADR-041 v1.0 + ADR-H4 + ADR-038 D11.2 + ADR-H0 6+1 全已读 ✓

### WP-02：起草 ADR-H1 + PLAN-H1（已完成 ADR，PLAN 起草中）

**结果**：
- ADR-H1 = 188/300 行，§1-§11 完整，零"待协调员决定 / TBD / 后续讨论"
- PLAN-H1 = 本文件起草中，目标 ≤500 行

### WP-03：嵌入 lead/SKILL.md "## 触发节奏（H1）" 子段

**输入**：ADR-H1 §4 触发节奏表（5 条）+ §5 落地路径模板。

**动作**：在 lead/SKILL.md line ≥182（"## 联动规则"段之前；"## 行为治理（H4 三类清单）"段之后）插入新子段 "## 触发节奏（H1）"。

**子段结构（≤25 行硬限）**：
1. 引言（1 行）：指针到 ADR-H1
2. 5 条触发条件（5 行短句，每条 1 行）
3. 落地路径模板缩略（3 行）
4. 红线（3 行短句：不写 cron / 不写 hook / 不新建 active SKILL.md）
5. 升级条件（2 行）

**Edit pattern**（同 H4 嵌入手法）：
```python
old_string = "## 联动规则（skill 调度表）"
new_string = "## 触发节奏（H1）\n\n... 25 行内容 ...\n\n## 联动规则（skill 调度表）"
```

**DoD**：
- `wc -l .claude/skills/lead/SKILL.md` ≤ 220（192 + ≤25 + buffer）
- `grep -c "## 触发节奏（H1）"` = 1
- `grep -iE "cron|hook|schedule|metrics" <new-segment>` = 0（INV-H1-3 段内）

### WP-04：dogfood 一次成功触发

**输入选择**：harness-self-symptoms.md §4.9（cross-plan-class race，新型号）。
- 触发条件命中 = ADR-H1 §4 表第 1 条（主仓发现新型 symptom）
- 历史相关 symptom：§4.4（同 session 内 H × H race）= 同根但不同子类
- 新案例数：1（§4.9 自身）

**期望产出**（写到 `docs/decisions/tasks/PLAN-H1/WP-04/dogfood-output-20260428-{ts}.md`）：

```yaml
# crystal-learn output (per skill output contract)
invariant_delta:
  candidate:
    - id: INV-cross-plan-class-race  # 候选，仅 1 案例
      description: "施工前必须 git status 核 merge state；H 子计划与业务 PLAN 跨 class race 不被 H0.5 协调表覆盖"
      evidence: "§4.9 / 1 案例 / 系统性形状（merge state collision 是 git 操作语义级冲突）"
  new_instance: []
  confirmed: []  # 无新升级
target_injection_map:
  - target: docs/decisions/ADR-H0-meta-charter.md  # 修订建议第 10 条候选
    directive: "H0.5 协调表扩展为'跨 plan-class' 协调（H × 业务 PLAN race 也登记）；或加 H0.7 子规则'施工前 git status 核 merge state'"
    rationale: "§4.9 新型号 symptom 暴露 H0.5 表只覆盖 H 子 PLAN 之间是规则盲区；不立即修订 ADR-H0（H 系列收尾时整体复盘），先入修订建议表"
  - target: .claude/skills/lead/SKILL.md "## 来自 crystal-learn 的门禁" 段
    directive: "起草 ADR/PLAN 进入 commit 阶段前 → `git status` 核 merge state；处于 merge state 时 git restore --staged 不擅自 conclude 别 session merge"
    rationale: "lead 是入口 skill；prompt-level 70% adherence 足够（INV-H1-3 红线，不机制化）；与现有 INV-4 真相源分裂 + INV-6 验证衰减 对齐"
status: candidate-not-yet-confirmed  # crystal-learn 升级规则要求 ≥2 案例才升级 confirmed
next_check: "下次出现 cross-plan-class race（任何 H × 业务 PLAN 或业务 PLAN × 业务 PLAN）即升级 confirmed + 注入 lead/SKILL.md"
```

**DoD**：
- 文件 `dogfood-output-20260428-{ts}.md` 存在 + 非空 + ≤80 行
- `grep -c "invariant_delta\|target_injection_map"` ≥ 2
- `grep "candidate-not-yet-confirmed\|confirmed"` 命中（status 字段非空）
- 不实际修改 ADR-H0（仅产出注入建议；ADR-H0 实际修订留 H 系列收尾）
- 不实际写入 lead/SKILL.md（INV-H1-2 落地路径段已在 WP-03 写好；候选不该立刻进入执行层）

### WP-05：reviewer signoff

**spawn**：read-only subagent（按 .claude/rules/review-agent-isolation.md），prompt-level 兜底加 read-only directive。

**14 维度验证矩阵**（reviewer 必须逐项 grep/wc 实证）：

| # | 维度 | 验证命令 | 期望 |
|---|------|---------|------|
| 1 | ADR-H1 ≤300 行 | `wc -l ADR-H1` | ≤300 |
| 2 | PLAN-H1 ≤500 行 | `wc -l PLAN-H1` | ≤500 |
| 3 | lead 注入段 ≤25 行 | `awk '/## 触发节奏（H1）/,/## 联动规则/' lead/SKILL.md \| wc -l` | ≤27（含起止 2 行）|
| 4 | INV-H1-1（≤5 触发条件） | `awk '/## 触发节奏（H1）/,/## 联动规则/' lead/SKILL.md \| grep -c "^[0-9]\.\| - "` | ≤5 |
| 5 | INV-H1-2（落地路径在现有接收段） | `grep -B5 "## 触发节奏（H1）" lead/SKILL.md \| grep "## 来自 crystal-learn 的门禁"` | 命中 1 |
| 6 | INV-H1-3（注入段零机制化） | `awk '/## 触发节奏（H1）/,/## 联动规则/' lead/SKILL.md \| grep -iE "cron\|hook\|schedule\|metrics\|setInterval\|crontab"` | 0（注入段内）|
| 7 | dogfood 落地物存在 | `ls docs/decisions/tasks/PLAN-H1/WP-04/dogfood-output-*.md` | 1 文件 |
| 8 | dogfood 内容非空 | `wc -l <dogfood-file>` | 30-80 |
| 9 | dogfood 含 invariant_delta + injection map | `grep -c "invariant_delta\|target_injection_map" <dogfood-file>` | ≥ 2 |
| 10 | H0.4 自指（无"待 / TBD / 后续讨论"实质命中） | `grep -nE "待协调员决定\|TBD\|后续讨论" ADR-H1 PLAN-H1` | 仅元层引用 |
| 11 | H0.meta（不引用未来产物） | `grep -nE "\bH[2-8]\b" ADR-H1` | 仅 §8 H4 边界 + §10 自检 |
| 12 | H0.6 证据机械化（每 INV/DoD 给命令） | 人审 §3 表 | 每行有 grep/wc/awk |
| 13 | crystal-learn skill 文件未被改动 | `git diff --stat HEAD~3..HEAD ~/.claude/skills/towow-crystal-learn/SKILL.md` | 空 / 0 lines changed |
| 14 | 4 项 grep 实证（前置 ADR / hook / cron / pointer） | reviewer copy verify bundle § 7 | 全 PASS |

**verdict 模板**（同 H4 reviewer-verdict-*.md）：
- 14 维度逐项 PASS / BLOCK / PASS_WITH_NOTES
- P0/P1 notes 必须 BLOCK（H4 §过度 review 第 3 条）
- P2/P3 advisory 不 BLOCK，记入 followup
- 文件路径 `docs/decisions/tasks/PLAN-H1/WP-05/reviewer-verdict-20260428-{ts}.md`

## §3 验证矩阵（机械化）

> 14 维度全部机械化。每行 reviewer 只需 copy-paste 命令验证，不接受"reviewer 认为已完成"（H0.6）。

参考 §2 WP-05 表。

## §4 跨 H 协调登记

| 共改资产 | 与谁冲突 | 仲裁 | 检测 |
|---------|---------|------|------|
| `lead/SKILL.md` | H4（行为治理段 line 158-180） | 串行：H4 已 merged，H1 紧接其后追加 | `git log lead/SKILL.md` 验时间序 |
| `.towow/log/harness-self-symptoms.md` | H 系列全部子计划 | append-only，时间戳前后即可 | `git log harness-self-symptoms.md` |
| `~/.claude/skills/towow-crystal-learn/SKILL.md` | 无（H1 scope 外） | 不动 | `git diff --stat` 空 |
| ADR-H0 修订建议 | H 系列全部子计划已积 8/9/10 条 | H1 仅追加候选第 10 条 candidate（不 confirm）；待 H 系列收尾整体批量合并 | dogfood 输出 status=candidate |

## §5 H0 元规约 6+1 自检（PLAN 自身）

- **H0.1 施工隔离**：PLAN scope 严格在 §1.1 表 7 项；本 PLAN 起草不动其它资产
- **H0.2 节流**：PLAN 当前预算 ≤500 行（实际 wc 待 commit 时核）
- **H0.3 执检分离**：起草人 ≠ reviewer；WP-05 spawn read-only subagent
- **H0.4 自指禁止**：grep "待协调员决定 / TBD / 后续讨论" 全文仅 §2 WP-05 表第 10 维度元层引用 + §6 dogfood verify bundle 元层引用 + §10 自检命中
- **H0.5 跨 H 协调**：见 §4 表
- **H0.6 证据机械化**：§2 WP-05 表 14 行每行 grep/wc/awk 命令
- **H0.meta**：grep `\bH[2-8]\b` 仅 §4 协调表行 + §1 H4 line 158-180 引用 + §5 自检命中

## §6 dogfood 验证（DoD 内嵌）

H1 的"DoD = 至少 1 次成功触发并产出落地物"通过 WP-04 内嵌实现：

- 触发条件命中（§4 表第 1 条 + 第 5 条 复合命中：新型 symptom + ADR-H0 修订建议累积 ≥3）
- 输入 = §4.9 + 处置段第 10 条
- 输出 = `dogfood-output-*.md`（≤80 行）
- 输出含 crystal-learn output contract 必填字段（invariant_delta / target_injection_map）
- 输出 status = candidate（严格按 crystal-learn 升级规则 ≥2 案例才 confirmed）
- 不实际修改 ADR-H0（候选不立即升级；不立即 commit 注入到 lead/SKILL.md）

dogfood 落地物本身就是"复活成功"的证据：能产出 well-formed crystal-learn output → 触发协议可消费。

## §7 reviewer copy-paste verify bundle

**前置实证**：
```bash
cd /Users/nature/个人项目/Towow
wc -l docs/decisions/ADR-H1-crystal-learn-revival.md         # 期望 ≤300
wc -l docs/decisions/PLAN-H1-crystal-learn-revival.md        # 期望 ≤500
wc -l .claude/skills/lead/SKILL.md                            # 期望 ≤220
```

**INV-H1 三条**：
```bash
# INV-H1-1: 触发条件 ≤5 条
awk '/## 触发节奏（H1）/,/## 联动规则/' .claude/skills/lead/SKILL.md \
  | grep -cE "^[0-9]+\.|^- "                                  # 期望 ≤5

# INV-H1-2: 落地路径必须引用现有接收段（不要求物理紧邻；接收段在 line 142，触发节奏段在 line 181）
grep -c "## 来自 crystal-learn 的门禁" .claude/skills/lead/SKILL.md  # 期望 ≥1（接收段存在）
awk '/## 触发节奏（H1）/,/## 联动规则/' .claude/skills/lead/SKILL.md \
  | grep -c "来自 crystal-learn 的门禁"                              # 期望 ≥1（触发节奏段引用接收段）

# INV-H1-3: 注入段零机制化关键词
awk '/## 触发节奏（H1）/,/## 联动规则/' .claude/skills/lead/SKILL.md \
  | grep -iE "cron|hook|schedule|metrics|setInterval|crontab" # 期望 0 行
```

**dogfood 落地物**：
```bash
ls docs/decisions/tasks/PLAN-H1/WP-04/dogfood-output-*.md     # 期望 1 文件
wc -l docs/decisions/tasks/PLAN-H1/WP-04/dogfood-output-*.md  # 期望 30-80
grep -cE "invariant_delta|target_injection_map" \
  docs/decisions/tasks/PLAN-H1/WP-04/dogfood-output-*.md      # 期望 ≥2
grep -E "candidate-not-yet-confirmed|^status:" \
  docs/decisions/tasks/PLAN-H1/WP-04/dogfood-output-*.md      # 期望 1 行
```

**自指检测**：
```bash
# H0.4 实质命中（非元层引用）
grep -nE "待协调员决定|TBD|后续讨论" \
  docs/decisions/ADR-H1-crystal-learn-revival.md \
  docs/decisions/PLAN-H1-crystal-learn-revival.md             # 全部应为元层引用

# H0.meta 不引用未来 H[2-8]
grep -nE "\bH[2-8]\b" docs/decisions/ADR-H1-crystal-learn-revival.md
# 期望仅 §8 H4 边界 + §10 自检 + 协调表
```

**crystal-learn skill 文件未动**：
```bash
git diff --stat HEAD~5..HEAD ~/.claude/skills/towow-crystal-learn/SKILL.md
# 期望空（H1 scope 外不动）
```

## §8 commit 计划（race-safe pattern，§4.9 教训）

```bash
# 1. commit 前再核 merge state（§4.9 防御）
test -f .git/MERGE_HEAD && echo "MERGE in progress, abort" && exit 1

# 2. 先 add ADR + PLAN，pathspec 隔离
git add docs/decisions/ADR-H1-crystal-learn-revival.md \
        docs/decisions/PLAN-H1-crystal-learn-revival.md

# 3. commit only with strict pathspec (§4.4 race-safe)
git commit --only \
  docs/decisions/ADR-H1-crystal-learn-revival.md \
  docs/decisions/PLAN-H1-crystal-learn-revival.md \
  -m "PLAN-H1 起草: ADR-H1 v1.0 (188/300) + PLAN-H1 v1.0 (~430/500)"

# 4. post-verify
git show --stat HEAD  # 验文件清单严格 = 2 文件
```

WP-03 / WP-04 / WP-05 各自独立 commit，相同 race-safe pattern。

## §9 进度追踪

- [x] WP-01 现状盘点（7 项实证）
- [x] WP-02 起草 ADR-H1 + PLAN-H1（本文件）
- [ ] WP-03 嵌入 lead/SKILL.md "## 触发节奏（H1）" 子段
- [ ] WP-04 dogfood 一次（§4.9 输入 → INV delta + injection map）
- [ ] WP-05 reviewer signoff（read-only subagent + 14 维度）
