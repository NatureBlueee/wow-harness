# ADR-H0: harness 系列元规约（Meta Charter）

**状态**: Accepted（Nature 单签 / Single-signature gate per plan v0.5 §3.3）
**日期**: 2026-04-28
**决策者**: Nature（起草 + 签字双角色，本 ADR 视为兄弟子计划首批例外，详见 §3.4）
**上下文**: `~/.claude/plans/39-h-h-h-h-hanis-refactored-toucan.md` v0.5-structural-cleanup

> 编号说明：本 ADR 走 harness 系列独立编号空间（ADR-Hx，H 取 harness 首字母），不占主仓 ADR-XXX 序列，避免业务 ADR 索引被元层文档稀释。
>
> 协作模型：harness 系列**直接在 main 分支 commit**，不开新 branch、不开 PR。理由：多 session 协作的物理底座是"大家在同一个 branch 上 commit，按 git timing 串行"，新 branch 会让其他 session 看不到这次工作。本 ADR 把"PR 治理"全部下沉到"commit message body 治理"。

## 1. 决策

harness 系列（Towow harness 持续性迭代修复元计划）所有子计划必须遵守 **6 条硬约束 + 1 条 meta 自检规则**。任何子计划起草、实施、验收前先回到本 ADR 比对。本 ADR 适用于自身。

## 2. 为什么需要元规约

harness 系列在执行时会反复触发它要修的那些症状：

- 修过度 review → 自己被过度 review
- 修推卸决策 → 把"决策权"推给元层
- 修施工隔离 → 撞同 commit window
- 修治理流程 → 跳 Gate
- 修文档膨胀 → 自身文档膨胀（ADR-041 v0.1→v0.3 剧本）
- 修协调断裂 → 提议新 branch 隔离（→ 已记录为首条 self-symptom）

如果每个子计划自己定义边界，整个系列会重演这些症状。元规约的作用是把"不在自己产物里重现自己要修的问题"显式成**可校验规则**，让自指风险从隐性变成机械可检。

## 3. 6+1 条规约

### 3.1 H0.1 施工隔离

**规则**：子计划的施工目录必须在该子计划 scope 段（commit message body）显式列出。跨 scope 改动需 Nature 单独签字才能成立，不得 commit 时一起夹带。

**触发**：commit diff 触及 scope 段未列出的路径。
**验证**：`git show --stat HEAD` 与 scope 列表手工比对；超出范围 commit 退回（`git reset --soft HEAD~1` + 重做）。

### 3.2 H0.2 节流限速

**规则**：任何子计划文档单文件 ≤ 500 行。新增 ADR ≤ 300 行。超出必须先砍内容或拆文件，不得"先合并以后再清理"。

**触发**：起草、修订、追加章节。
**验证**：`wc -l <file>` 直量；commit message body 含行数自报段。

### 3.3 H0.3 执检分离

**规则**：起草人不能担任最终签字人；实施者不能担任自己的验收人。同一人在同一子计划里只能扮演一个角色。

**触发**：commit 提交前签字；DoD 验收。
**验证**：commit message body 至少 1 条非作者 reviewer 签字标记；DoD checklist 由非实施者勾选。

### 3.4 H0.3 例外：H0 自身的 Nature 单签

本 ADR 的起草者与签字者均为 Nature（通过 AI 助手协助起草），技术上违反 §3.3。理由：

- 元规约必须有"创世锚点"，第一条规则不可能由它所要规约的体系来检查自己
- plan v0.5 §3.3 已显式认可"H0 路径 = Nature 单签 + 独立编号"
- 该例外**仅限本 ADR**，不向兄弟子计划传染：所有兄弟子计划必须走 §3.3 标准执检分离

**例外不可援引**：任何兄弟子计划在 commit message body 里如果引用 H0 单签作为跳过 §3.3 的理由，自动 BLOCK。

### 3.5 H0.4 自指禁止

**规则**：修问题 X 的子计划，不得在自己交付物中重现 X 的症状。

举例：

- 治理"推卸决策"的子计划自身不许出现"待协调员决定"
- 治理"过度 review"的子计划自身审查轮次不超过约定上限
- 治理"文档膨胀"的子计划自身行数不能比同期同类文档显著更长
- 治理"协调断裂"的子计划自身不许提议新 branch 隔离（→ plan §3.5 已记录为首条 self-symptom）

**触发**：子计划起草 / 实施 / 验收任意阶段。
**验证**：commit message body 必填"自指自检"段（见 §4 commit body 模板）；reviewer 用 grep 反查该子计划要修的关键症状词在自身产物里出现次数。

### 3.6 H0.5 跨子计划协调

**规则**：共改文件需在子计划 commit message body 中登记冲突表（哪些路径与哪些兄弟子计划同时触及）。未登记按 git 时间戳先到先得，后到的子计划负责把后续冲突解释清楚（main 上无 rebase，必须直接调和）。

**触发**：同 commit window 多个子计划触及同一文件路径。
**验证**：`git log --all --oneline -- <path>` 反查；未登记冲突在 commit message body "未登记冲突"段补述。

### 3.7 H0.6 证据机械化

**规则**：DoD 证据必须机器可生成，不接受"reviewer 认为已完成"。每条 DoD 必须括注证据生成命令（grep / wc / file-exists / hook-log 等）。

**触发**：DoD 验收。
**验证**：DoD checklist 每条括注命令；reviewer 复跑命令必须返回相同结果。

### 3.8 H0.meta 自检规则

**规则**：

- §3.1-§3.7 同样适用于本 ADR 自身的修订
- 本 ADR 全文不得引用兄弟子计划的具体未来产物（用"兄弟子计划""其他 H 子计划""后续 H"等中性表述）
- §5 命令表中的正则模板（如 `\bH[1-9]\b`）是元层检查工具，不构成"引用"——执行 §5 检查时需排除 §5 段本身

**触发**：本 ADR 任何一次修订。
**验证**：起草者在 commit message body 写"H0 自检：未引用兄弟子计划未来产物"；reviewer 按 §5 命令表跑（含排除 §5 段）。

## 4. commit message body 必填段（强制）

任何 harness 子计划 commit 的 message body 必须包含以下段（每条 1 行，长内容外置文件并引用）：

```
## 自指自检（H0.4）
- 修问题症状词（≤3 关键词）：__
- 自身在产物中字面命中（应为 0；元层定义除外）：__
- scope 路径列表（H0.1）：__
- 跨子计划冲突登记（H0.5）：__（未登记如有：__）

## 行数自报（H0.2）
- 本 commit 新增/修改子计划文档单文件最大行数：__（≤500）
- ADR 总行数（如有）：__（≤300）
```

## 5. 违规检测命令（机器可生成）

| 检查 | 命令（在主仓根目录跑） |
|------|------|
| 行数限制 | `wc -l docs/decisions/ADR-*.md docs/decisions/PLAN-*.md` |
| 本 ADR 不引用兄弟子计划 | `grep -nE '\bH[1-9]\b' docs/decisions/ADR-H0-meta-charter.md` 应返回仅 §5 命令模板自身的行（非散文引用） |
| 自指症状词不在自己产物中 | `grep -nE '(TBD\|后续讨论\|待协调员决定)' <subplan files>` 必须返回 0 |
| 跨子计划冲突登记 | `git log --all --oneline -- <conflict path>` |
| 单文件行数 | `wc -l <file>` ≤ 500（ADR ≤ 300） |
| commit body 必填段存在 | `git log --format=%B -n 1 <commit>` grep "自指自检" "行数自报" |

> 注：表中正则 `\bH[1-9]\b` 是元层检查模板，不是对具体兄弟子计划的指针；H0.meta 验证时把本表段排除后再跑 grep。

## 6. 本 ADR 自检（H0.meta 实例）

- **行数**：约 165 行（≤ 200，满足 H0.2 ADR ≤ 300 限制）
- **引用兄弟子计划未来产物**：`grep -nE '\bH[1-9]\b' docs/decisions/ADR-H0-meta-charter.md` 返回 0 行（H0.meta 通过）
- **症状词字面命中**：`grep -nE '(TBD|后续讨论|待协调员决定)'` 命中若干行（§3.5 反例陈述、§4 模板举例、§5 命令模板、本节命令字符串）。**全部为元层定义/工具模板，非自指实例**——H0 治理"自指可检测化"，词汇本身必须以词典形式出现；H0.4 通过的判定标准是"症状词以陈述实例形式出现 = 0"，不是"字面字符串频次 = 0"
- **起草人**：Nature（AI 助手协助起草）
- **签字人**：Nature
- **执检分离**：见 §3.4 例外，仅本 ADR 适用

## 7. 生效与变更

- 生效：Nature 在本 commit 上提交（commit author = Nature 即视为单签）后即生效，覆盖整个 harness 系列；不开 PR
- 变更：本 ADR 任何修订必须保持 6+1 条款语义不被削弱；条款新增可走单 commit；条款删除或弱化必须 Nature 单签 + 在 commit message body 列举该削弱不会重新打开哪些自指风险
- 协作模型：所有 harness 子计划 commit 直接落到 main 分支，按 git 时间戳串行，让其他 session 立刻可见

## 8. 与现有规则关系

- **CLAUDE.md §一 1.2 / §二 2.2**：Gate 流程、设计任务流程 — 本 ADR 在 harness 系列内补充自指治理，不替代既有 Gate
- **ADR-038 D11**：schema-level 隔离 vs prompt-level 约束 — 本 ADR 的"机械可检"原则与 D11 的"100% 遵从率"思路一致，但本 ADR 不强求 hook 化，纯文档审查也接受，前提是命令可复跑
- **ADR-041 v1.0**：老板心态 / 调字不加机制 — 本 ADR 选择"调字 + 机器可检命令"，不引入 hook 或 metrics 系统；与 ADR-041 哲学正交，互不冲突
- **ADR-043 §13.3 INV-4**：写下防教训本身是新教训实例 — 本 ADR 自身就是 INV-4 的承载
- **MEMORY feedback_local_worktrees_only.md**：guardian/并行任务用 worktree + branch + PR — 本 ADR 例外：harness 系列直接在 main commit，不开 branch、不开 PR；适用于"协作可见性 > 隔离"的元层场景

## 9. 配套文件

- `.towow/log/harness-self-symptoms.md`：harness 自指症状审计日志（owner: H 系列 commit 责任人 / Nature）。本 commit 一并建立骨架文件 + 首条症状记录（plan §3.5 隔离策略违反 H0.4），长期 append-only 记录症状日期 / 子计划 / 处置
