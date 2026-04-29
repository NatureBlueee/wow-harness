# ADR-H8: 已知 issue + 文档合规

**状态**：v1.0 起草中（2026-04-28）
**Owner**：H 系列 / hanis-main
**前置**：ADR-H0 (元规约) + ADR-H5 (Gate 量纲化) + ADR-H6 (state file health) 已签署
**后续**：作为拓扑 D 最后一站，本 ADR 关闭后 H 系列收尾

## §H0 自检

按 ADR-H0 §H0.6 执检分离要求：

- 起草人：当前 session（H6 reviewer 签字后立即起草）
- ≤300 行：本 ADR 实测 < 300（见 §11 verification）
- 不引用未来 H 产物：本文档仅引用已签署 H 序列（H0/H1/H2/H3/H4/H5/H6/H9）；已退役 H 在 §1.1 表中以 footnote 形式说明，不作为依赖
- 不写"待协调员决定" / "TBD" / "后续讨论"

## §1 背景与触发

### 1.1 H 系列拓扑 D 进度

| H | 主题 | ADR | PLAN | reviewer | 状态 |
|---|------|-----|------|----------|------|
| H0 | 元规约 | ✓ | — | Nature 单签 | 已签 |
| H9 | 邮箱机制 | ✓ | ✓ | reviewer | 已签 |
| H2 | 身份隔离 | ✓ | ✓ | reviewer | 已签 |
| H3 | memory scope | ✓ | ✓ | reviewer | 已签 |
| H4 | prompt 治理 | ✓ | ✓ | reviewer | 已签 |
| H1 | 学习层复活 | ✓ | ✓ | reviewer | 已签 |
| H5 | Gate 量纲化 | ✓ | ✓ | reviewer | 已签 |
| H6 | state 健康度 | ✓ | ✓ | reviewer | 本 ADR 起草前刚签 |
| **H8** | **本 ADR** | **起草中** | 起草中 | 待 | 进行中 |

原拓扑 v0.3 中的"hook IO 收口"H 已按 v0.5 决议退役不再独立交付，相关 IO 治理已收归 ADR-058 §D1（hook output schema）。

### 1.2 H8 触发动机

H 系列实施期间，以下三类问题在主仓堆积：

1. **ADR 索引完全没建立**：74 个 ADR 文件，但无 `docs/decisions/ADR-INDEX.md`。新人 / future AI 找 ADR 必须 ls + grep，没有按主题/状态的导航
2. **CHANGELOG 长间隙**：0.4.4 (2026-04-08) → 0.4.5 (2026-04-28) 之间 20 天 / 672 commit / 15+ 个 PLAN，但 0.4.5 changelog 只覆盖 PLAN-101 / PLAN-104。中间漏掉的 PLAN-H1~H6/H9/PLAN-103 K6/PLAN-096 admin/PLAN-093 MCP 等多条上线记录
3. **open issue 量爆炸**：383 issue 文件中 93 条 status=open，4 月新建的 235 条。其中相当一部分实际已经 fixed 或 superseded，只是没 flip 状态

### 1.3 与 H 系列其他 H 的边界

- 本 H 不重新设计 issue 工作流（ADR-030 已定）
- 本 H 不重新设计 ADR 编号规则（ADR-038 D8 已定）
- 本 H 不接管 changelog 真相源职责（CHANGELOG.md + mcp-server/CHANGELOG.md 已定）
- 本 H **只做盘点 / 索引 / 补全 / 闭环**——不创造新治理机制

按 ADR-041 v1.0 哲学："调字不加机制"，H8 是治理空白的填充，不是新治理框架。

## §2 决策本质

### 2.1 H8 = 文档合规闸 + 已知 issue 关闭闸

H8 在 H 系列收尾位置，对 H 系列累积的"账面浮动"做一次性结算：

- **账面浮动**：ADR/PLAN/issue/CHANGELOG 的状态与代码实际状态不同步（feedback_verification_honesty.md 的 N+1 次实例）
- **结算手段**：盘点 + 索引 + 补全 + 关闭，全部 in-tree 文档动作；不动 hook、不动 yaml 治理字段、不动 SKILL.md prompt

### 2.2 ADR-038 D11.2 适用性

H8 交付物**不属于 schema-level**（不进 review-contract.yaml）也**不属于 prompt-level**（不进 SKILL.md）。它属于 **artifact-level**（直接交付文档制品）。这是 H 系列里第一个 artifact-level H：

| H | level | 主交付 |
|---|-------|--------|
| H4 prompt 治理 | prompt-level (SKILL.md) | 黑话/推卸 prompt 段 |
| H5/H6 schema 化 | schema-level (review-contract.yaml) | line_caps / inflation / state_inventory / state_health_indicators |
| H1 学习层 | mechanism-level (skill 触发节奏) | crystal-learn 触发 |
| H2 身份隔离 | schema-level (frontmatter + ownership.yaml) | owner 字段 + worktree 隔离 |
| H3 memory scope | artifact-level (memory dir 重组) | MEMORY.md 段化 + topic file |
| **H8** | **artifact-level (in-tree docs)** | **ADR-INDEX + CHANGELOG 补 + issue 闭** |

H8 与 H3 是 H 系列两个 artifact-level H；其余都是 schema/prompt/mechanism level。

## §3 INV（不变量）

### INV-H8-1 ADR 索引完整性

`docs/decisions/ADR-INDEX.md` 必须存在；每个 `docs/decisions/ADR-*.md` 文件必须在索引中有 1 行。

**红线**：新增 ADR 必须同时更新索引，没有"先合并 ADR 再补索引"的豁免。

**检测**：
```bash
diff <(ls docs/decisions/ADR-*.md | sed 's|docs/decisions/||;s|\.md$||' | grep -v '^ADR-INDEX$' | sort) \
     <(awk -F'[][]' '/^- \[ADR-/{print $2}' docs/decisions/ADR-INDEX.md | sort)
# 期望: 输出空（双向集合相等；ADR-INDEX 自身因匹配 ADR-*.md glob 但不应在自己的索引列表里，需排除以免自指）
```

### INV-H8-2 CHANGELOG 间隙上限

CHANGELOG.md 相邻两版本号之间的实际历史时间间隙 ≤ 14 天，或必须包含同时间段的"intermediate" 占位记录解释为何无版本号。

**红线**：禁止跳过 ≥ 3 个 minor patch 数字（如 0.4.4 → 0.4.7 中跳过 0.4.5/0.4.6 不被允许）。

**检测**（人工 + 半自动）：
```bash
grep -E "^## \[" CHANGELOG.md | head -20
# 人工读：每两条之间日期差 ≤ 14 天
```

### INV-H8-3 open issue 数量上限

`docs/issues/*.md` 中 `status: open` 的文件 ≤ 80 条；超过 80 必须触发批量 triage / close。

**红线**：H8 关闭时 open issue 总数 ≤ 80（当前实测 93，需关闭 ≥ 13 条）。

**检测**：
```bash
grep -lE "^status: open" docs/issues/*.md 2>/dev/null | wc -l
# 期望: ≤ 80
```

## §4 H8 受管资产

| 资产 | 路径 | 本 H 动作 |
|------|------|-----------|
| ADR 索引 | `docs/decisions/ADR-INDEX.md` | 新建（不存在） |
| CHANGELOG | `CHANGELOG.md` | 补 0.4.4 → 0.4.5 间隙的 intermediate notes |
| H 系列上线条目 | CHANGELOG.md 0.4.5 段 | 增加 H 系列 backfill 段落 |
| open issue | `docs/issues/*.md` | 批量审查 + flip ≥ 13 条到 fixed/superseded |
| 合规清单 | `docs/decisions/tasks/PLAN-H8/WP-03/compliance-checklist.md` | 新建，列 5+ 条 H8 闭关后必须满足的合规规则 |

## §5 ADR-042 D3/D4/D9 复用（不重新发明）

按 ADR-H6 §6 抗 compact 接口签字模式，H8 也复用 ADR-042 同一组接口：

- **D3 Session-Owner**：H8 实施期间 session owner = h8-window，跨 compact 仍能复读
- **D4 owner-guard**：批量 issue flip 不会被 owner-guard 误拦（owner 一致）
- **D9 AGENTS.md 梯度加载**：lead skill H8 段按 stage 懒加载，不全量灌

签字 = 不为 D3/D4/D9 重新发明替代品。

## §6 与 H5/H6 schema 关系

H8 不动 review-contract.yaml（artifact-level，非 schema-level），但 H8 完工后 review-contract.yaml 可加 line_caps 项保护 ADR-INDEX.md（如 ≤500 行）。本 ADR 留作 H 系列收尾建议，不在 H8 内强制。

## §7 不做什么（防膨胀红线）

H8 **绝对不做**以下 4 类（防 ADR-041 v0.1→v0.3 膨胀重演）：

1. ❌ 自动化 ADR 索引生成 hook（artifact-level 治理，pre-commit 跑 grep 即可手工维护）
2. ❌ CHANGELOG bot / changelog auto-generation 工具（人工写为佳，AI 协助但不接管）
3. ❌ issue 状态自动机（ADR-030 已定，不重新设计）
4. ❌ 合规度 metrics dashboard（按 ADR-041 v1.0 红线 + 每周人脑回顾）

## §8 H8 阶段拆解（详见 PLAN-H8）

| 阶段 | 主题 | DoD 关键 |
|------|------|----------|
| H8-WP-01 | 盘点 | issue 总数 / open 数 / 主题分布 / ADR 数 / CHANGELOG 缺口列出 |
| H8-WP-02 | 起草 ADR-H8 + PLAN-H8 | 本 ADR ≤300 + PLAN-H8 ≤500 + INV ≥3 |
| H8-WP-03 | 实施 | ADR-INDEX 新建 + CHANGELOG 补 ≥3 条 + 关闭 ≥13 issue + 合规清单 ≥5 |
| H8-WP-04 | dogfood | self-check + INV-H8-1/2/3 当场实测 |
| H8-WP-05 | reviewer signoff | 独立 subagent 14 维度审 PASS |

## §9 H 系列收尾（H8 闭合后）

H8 闭合后，H 系列拓扑 D 全部完成。建议收尾动作（**非 H8 scope，留给 hanis-main 维护者**）：

1. 在 `.towow/log/hanis-self-symptoms.md` 做一次完整复盘（H 系列实施期间累积的自指症状）
2. 把 H 系列累积的 P3 informational 一并整理（INV-H1-3 / INV-H5-3 / INV-H6-3 修正建议）
3. 整体 hanis-main → main merge 之前的 vNext smoke 重跑

## §10 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 批量 issue flip 误关 | 错把仍 open 的 issue 标 fixed | 每条 flip 必须附 1 行 justification + 引用 commit/PR |
| ADR-INDEX.md 漂移 | 新 ADR 加进来时索引漏掉 | INV-H8-1 检测命令进 review-contract.yaml line_caps（H 系列收尾任务） |
| CHANGELOG backfill 内容错误 | 把没 ship 的 PLAN 标 ship | 每条 backfill 引用至少 1 个 ship commit hash |

## §11 verification

```bash
# 行数限
wc -l docs/decisions/ADR-H8-issue-and-doc-compliance.md
# 期望: ≤300

# H 引用范围（不引未来 H）
awk '/^```/{f=!f; next} !f' docs/decisions/ADR-H8-issue-and-doc-compliance.md | grep -cE "H(7|10|11|12)"
# 期望: 0（H7 已退役，10-12 不存在）

# INV 数量
grep -c "^### INV-H8-" docs/decisions/ADR-H8-issue-and-doc-compliance.md
# 期望: ≥3

# 自检段落
grep -c "^## §H0 自检" docs/decisions/ADR-H8-issue-and-doc-compliance.md
# 期望: 1

# 不做什么段
grep -c "^## §7 不做什么" docs/decisions/ADR-H8-issue-and-doc-compliance.md
# 期望: 1
```

## §12 交付时间

- 起草：2026-04-28 20:10+08:00（本文件）
- 实施目标：2026-04-28 当晚（夜间 standing delegation 全自动模式）
- 交付预算：1 个 session 内完成 5 WP + reviewer signoff
