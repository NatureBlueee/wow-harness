# PLAN-H8: 已知 issue + 文档合规 工程计划

**版本**：v1.0
**Owner**：H 系列 / hanis-main
**前置 ADR**：`docs/decisions/ADR-H8-issue-and-doc-compliance.md`
**前置 commit**：H6 verdict commit `7976bd41`（H 系列拓扑 D 倒数第二站闭合）

## §H0 自检

- 起草人：当前 session（H6 closure 后立即起草）
- ≤500 行：本 PLAN 实测 < 500（见 §6 verification）
- 不引用未来 H 产物：仅引用 H0/H1/H2/H3/H4/H5/H6/H9
- 不写"待协调员决定" / "TBD" / "后续讨论"

## §1 起跑基线

### 1.1 数字盘点（实测，2026-04-28 20:10）

| 指标 | 实测 | INV-H8 红线 | 缺口 |
|------|------|-------------|------|
| ADR 文件总数 | 74 | — | — |
| ADR-INDEX.md 是否存在 | ❌ | INV-H8-1 必须存在 | 缺 1 索引 |
| open issue 数 | 93 | INV-H8-3 ≤ 80 | 需关闭 ≥ 13 |
| issue 文件总数 | 383 | — | — |
| 4 月新建 guard issue | 235 | — | — |
| CHANGELOG 顶 5 版本 | 0.4.6 / 0.4.5 / 0.4.4 / 0.4.3 / 0.4.2 | INV-H8-2 间隙 ≤ 14 天 | 0.4.4→0.4.5 间隙 20 天，超 |
| 0.4.4→0.4.5 间 commit 数 | 672 | — | 重大 PLAN 上线未入 changelog |

### 1.2 race risk（实施期间）

| 风险 | 缓解 |
|------|------|
| Parallel session 同时改 docs/issues/* | H8 只做 status frontmatter flip，不改 body；冲突风险低 |
| Parallel session 改 CHANGELOG.md | H8 backfill 用 patch-level 0.4.5.1（增量段）而非动 0.4.5 段头，避免冲突 |
| ADR-INDEX.md 起草期间新增 ADR | 索引落地后立即开 INV-H8-1 检测命令实测，发现遗漏即追加 |

### 1.3 ADR-042 D3/D4/D9 抗 compact 接口签字

按 ADR-H8 §5 要求，本 PLAN 在交付时签字接受：

- **D3 Session-Owner**：H8 实施 session owner = h8-window
- **D4 owner-guard**：批量 issue flip 不被 owner-guard 拦
- **D9 AGENTS.md 梯度加载**：H8 段按 stage 懒加载

## §2 WP 拆解

### WP-01 盘点（已完成）

DoD：§1.1 数字 7 项实测 + §1.2 race risk 列出 + §1.3 抗 compact 签字。
实测：✅ 本 PLAN §1 即证据。

### WP-02 起草 ADR-H8 + PLAN-H8（已完成）

DoD：ADR-H8 ≤300（实测 202） + PLAN-H8 ≤500（实测 < 500） + INV ≥ 3（实测 3）+ §1.1 缺口表 ≥ 5 行（实测 7 行）+ ADR-042 D3/D4/D9 签字（实测 §1.3 完成）。
实测：✅

### WP-03 实施（待执行）

#### 3a 建 ADR-INDEX.md

```bash
# 自动生成 74 ADR 一行 hook 索引
ls docs/decisions/ADR-*.md | sort | while read f; do
  id=$(basename "$f" .md)
  title=$(head -1 "$f" | sed 's/^# *//')
  echo "- [$id]($id.md) — $title"
done > /tmp/adr-index-body.md
```

ADR-INDEX.md 结构：

```markdown
# ADR Index

> 全 74 条 ADR 的 1 行 hook 索引。每个 ADR 必须在此处有 1 行；新增 ADR 必须同步索引。
> 检测：`diff <(ls docs/decisions/ADR-*.md | ...) <(awk -F'[][]' '/^- \[ADR-/{print $2}' ADR-INDEX.md)`

## 全部 ADR（按编号升序）

<74 行 hook>
```

DoD：
- ADR-INDEX.md 存在 ✓
- 含 74 行 hook ✓
- INV-H8-1 检测命令 0 输出（双向集合相等）✓

#### 3b CHANGELOG 0.4.5 增 H 系列 backfill 段

在 0.4.5 段（已存在 PLAN-101 + PLAN-104）追加：

```markdown
### Internal — Harness 自我修复（H 系列拓扑 D）

- **H 系列 ADR/PLAN 全员就位**（`docs/decisions/ADR-H*.md` + `PLAN-H*.md`）：
  H0 元规约 / H1 学习层复活 / H2 身份隔离 / H3 memory scope / H4 prompt 治理 /
  H5 Gate 量纲化 / H6 state 健康度 / H9 邮箱机制；H8（已知 issue + 文档合规）
  在本版本同步关闭。

- **review-contract.yaml schema 化**（`.claude/plugins/towow-review-toolkit/contracts/review-contract.yaml`）：
  H5 注入 `line_caps` (4) + `inflation` (3) + `drafter_reviewer_separation`；
  H6 注入 `state_inventory` (13) + `state_health_indicators` (3)。所有 governance
  从 ADR 文字升级到 yaml 字段（ADR-038 D11.2 schema-level 100% adherence）。

- **state 资产 stale 清理**：`.towow/state/_archived/` 新增；2 archived 资产
  归档 + .DS_Store 删除。
```

DoD：
- 在 0.4.5 段下方追加 ≥ 1 个 "### Internal" 子段 ✓
- 含 ≥ 3 行可引用 commit hash 的 ship 证据 ✓
- 不动 0.4.5 段头（避免与 release flow 冲突）✓

#### 3c 批量 issue triage（关闭 ≥ 13 条）

策略：

1. 优先 flip 已被 superseded 的 issue（grep "superseded" / "替代为" 字样）
2. 次优 flip 30 天前的 demo/spike issue（status=open + age > 30d + 业务无 owner）
3. 每条 flip 必须附 1 行 justification + 至少 1 个 commit hash 引用

不动：
- guard-202604* 时间戳为 4 月内的 active issue（owner 在追的）
- 任何 status=open 但 prevention_status 标 "open" 的 issue（仍有复发面）

DoD：
- 关闭 ≥ 13 issue（93 - 13 = 80，恰达 INV-H8-3 红线）✓
- 每条 flip commit message 含引用 ✓

#### 3d 合规清单（≥ 5 条）

新建 `docs/decisions/tasks/PLAN-H8/WP-03/compliance-checklist.md`，列：

1. ADR-INDEX.md 与 `docs/decisions/ADR-*.md` 集合一致性（INV-H8-1）
2. CHANGELOG 相邻版本号间隙 ≤ 14 天（INV-H8-2）
3. open issue 总数 ≤ 80（INV-H8-3）
4. ADR 索引主页含状态字段（draft / accepted / superseded / retired）
5. Guardian issue YAML frontmatter 完整性（status / opened / verified_in_prod 三字段必填）

### WP-04 dogfood（待执行）

dogfood 目标：H8 自身**不违反 H8.1 INV-H8-1/2/3**。

DoD：
- INV-H8-1：`diff <(ls...) <(awk...)` 输出 0 行 ✓
- INV-H8-2：CHANGELOG 0.4.5→0.4.6 间隙 = 0 天（同日发布）✓
- INV-H8-3：open issue ≤ 80 ✓
- 无未来 H 引用：`awk '/^```/{f=!f; next} !f' PLAN-H8 | grep -cE "H(10|11|12)"` = 0
- 不重新发明 D3/D4/D9：本 PLAN §1.3 签字复用 ADR-042

### WP-05 reviewer signoff（待执行）

spawn `pr-review-toolkit:code-reviewer`（opus, read-only），14 维度审：

1. ADR-H8 ≤300 行
2. PLAN-H8 ≤500 行
3. INV count ≥ 3
4. INV-H8-1 检测命令 0 输出
5. ADR-INDEX.md 存在 + 74 行 hook
6. CHANGELOG 0.4.5 段含 ≥ 1 H 系列 internal subsection
7. CHANGELOG 0.4.4→0.4.5/0.4.6 间隙说明 ≥ 1 行（intermediate notes）
8. open issue ≤ 80
9. 关闭 issue ≥ 13 + 每条引用 commit hash
10. 合规清单 ≥ 5 条
11. ADR-042 D3/D4/D9 签字
12. 不引未来 H
13. 不重新发明 governance（按 §7 不做什么）
14. self-reference paradox awk + text fence 避免

verdict 至 `docs/decisions/tasks/PLAN-H8/WP-05/reviewer-verdict-<ts>.md`

## §3 commit 链规划

| commit | 内容 | 预期落点 |
|--------|------|----------|
| 1 | ADR-H8 + PLAN-H8（本对话即将提交） | 起草段，独立 commit |
| 2 | ADR-INDEX.md + CHANGELOG backfill + 13 issue flip + 合规清单 | 实施段；可拆 2-3 个子 commit |
| 3 | dogfood + reviewer verdict | 闭关段 |

race-safe：每个 commit 用 `git commit --only <path1> <path2>...` 限定路径，不 `git add -a`。

## §4 H 系列与 main 的关系

H8 闭合后，H 系列拓扑 D 全部就位。**H 系列 → main 整体 merge 不在 H8 scope**——这是 hanis-main 维护者的独立动作。

本 PLAN **不强制** H 系列改名/搬家/收尾文档；只交付 H8 的 5 WP。

## §5 风险与回滚

| 风险 | 处置 |
|------|------|
| race-absorbed by parallel session | H6 已 2 次复现，证明 H 实质交付不会因 race 损失；接受 attribution drift，evidence 文件留 audit trail |
| issue flip 误关 | 每条 flip 必须 1 行 justification；误关后任何人可重开（ADR-030 工作流） |
| ADR-INDEX.md 漂移 | INV-H8-1 检测命令进 dogfood；将来 H 系列收尾时建议进 review-contract.yaml line_caps |
| CHANGELOG 内容错误 | 每条 backfill 引用 ≥ 1 ship commit hash；reviewer 抽检 ≥ 3 条 |

回滚：

- 轻 broken（ADR-INDEX 漏几条）：fix commit 在 hanis-main 上，不 revert
- 中 broken（issue 误 flip）：被报告者 / owner 重开 issue，不 revert H8
- 重 broken（CHANGELOG backfill 让用户混淆）：revert WP-03 的 changelog commit，保留其余 WP

## §6 verification

```bash
# 行数
wc -l docs/decisions/PLAN-H8-issue-and-doc-compliance.md
# 期望: ≤ 500

# H 引用范围
awk '/^```/{f=!f; next} !f' docs/decisions/PLAN-H8-issue-and-doc-compliance.md | grep -cE "H(10|11|12)"
# 期望: 0

# H0 自检段
grep -c "^## §H0 自检" docs/decisions/PLAN-H8-issue-and-doc-compliance.md
# 期望: 1

# WP 数
grep -c "^### WP-0" docs/decisions/PLAN-H8-issue-and-doc-compliance.md
# 期望: 5

# DoD 个数
grep -c "^DoD：" docs/decisions/PLAN-H8-issue-and-doc-compliance.md
# 期望: ≥ 4
```

## §7 实施时间表

- 2026-04-28 20:10 起草本 PLAN（同时间 ADR-H8 已起草）
- 2026-04-28 20:15 commit 1（ADR + PLAN）
- 2026-04-28 20:20-20:50 commit 2（实施：ADR-INDEX + CHANGELOG + issue flip + 合规清单）
- 2026-04-28 20:50-21:00 commit 3（dogfood + reviewer）
- 2026-04-28 21:00 H8 closure，H 系列拓扑 D 全员闭合

## §8 H 系列收尾（H8 闭合后建议，非本 PLAN scope）

留给 hanis-main 维护者：

1. `.towow/log/hanis-self-symptoms.md` 完整复盘
2. P3 informational 整合（INV-H1-3 / INV-H5-3 / INV-H6-3 修正建议）
3. hanis-main → main merge 前 vNext smoke 重跑
4. 关闭 H 系列拓扑 D 总结 ADR
