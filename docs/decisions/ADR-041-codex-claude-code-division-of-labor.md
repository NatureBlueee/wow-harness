# ADR-041: Codex × Claude Code 分流策略（v1.0 极简版）

**状态**: accepted (v1.0 — 2026-04-07，砍掉 v0.1/v0.2/v0.3 过度工程化设计)
**日期**: 2026-04-07

## 0. 历史与重写理由

v0.1 → v0.3 在 Gate 2 三轮审查中被红队推着持续加机制，从"分流偏好"膨胀成"18 个架构变更 + 10 红线 + 12 白线 + 威胁模型 + cumulative drift hook + marker chokepoint + hash 锁"。Nature 看完后判断**过度工程化**：原始诉求只是「让 Claude 自己判断啥时候用 Codex + 配几个自动化省 token」，不是建一个微型操作系统。

v1.0 是干净重写。v0.1/v0.2/v0.3 全部 superseded，**不**作为参考实现。失败模式记录：审查驱动复杂度通胀——红队每轮按"最大威胁假设"提 finding，作者每轮加机制应对，三轮后 ADR 与原始诉求脱节。教训沉淀到 `feedback_review_driven_complexity_inflation.md`。

## 1. 问题

- Claude Code (Opus 4.6) 月度 token 消耗远超预算
- ChatGPT Pro 的 Codex 额度富余，且 2026-03 上线 Automations（schedule + trigger）
- `codex-dev` subagent 已存在但几乎不被调用——main agent 默认把活留给自己
- 一些重复性任务（文档漂移、夜间测试、飞书 bug 预翻译）原本由 Claude 在 session 里跑或干脆没人跑

## 2. 决策

四件事，没有别的：

### D1: CLAUDE.md 加「老板心态」硬规则（§零）

`CLAUDE.md` 的 §一（不可妥协约束）之前插入新的 §零，约 30 行，明确：

> 你是技术主管，你有 Codex 这个员工。每接到任务先问"能不能 Codex 干"。默认假设 Codex 能干。

列出 5 类容易忽略分流的典型场景：
- 批量字符串替换 / i18n 提取
- CSS / Tailwind 类名批量调整
- 纯技术重构（命名、dead code、补 TS 类型、性能 memo）
- 批量补测试用例（已有框架下）
- 文档批量更新 / shell 脚本生成

这是**默认偏好**，不是硬阻塞。误判由人/Claude 在下次任务里学着调整，不靠 hook 强制。

### D2: codex-dev 红线（3 条，不是 10 条）

`.claude/agents/codex-dev.md` 顶部加红线段，**只列 3 条**：

1. **前端 React 组件结构 / 交互逻辑 / 新页面或新 feature 的实现** — Codex 前端小错多
2. **跨模块数据流穿透**（前端 → API → DB） — Codex 类型对齐 ≠ 数据流通的元失败模式
3. **审美决策 / `nature-designer` 流程** — CLAUDE.md §一 1.2

红线之外的任务，main agent 决定要不要分流，不强制。

### D3: 5 个 ChatGPT Pro Automation（异步通道）

由 Nature 在 ChatGPT Pro 端手动配置，**全部以 PR 为唯一交付形态**，不直接 commit main：

| Automation | 触发 | 频率 | 产出 |
|---|---|---|---|
| `doc-drift-scan` | schedule | 每 2h | 检测 magic docs / `check_doc_freshness.py` 漂移，有则提 PR |
| `magic-doc-regenerate` | schedule | 每 6h | 跑 `regenerate_magic_docs.py all`，drift 则提 PR |
| `nightly-test-baseline` | schedule | 每日 02:00 | 跑全量 unit/integration 对比 baseline，新 failure 提 PR + 飞书通知 |
| `daily-release-brief` | schedule | 每日 18:00 | git log + PR merged 汇总，写 `.wow-harness/codex-reports/brief-{date}.md` |

GitHub main branch protection 必须开启（禁直接 push main、禁 force push）。这是 Automation 安全边界的兜底。

### D4: AGENTS.md 派生 + 双配置同步

Codex 不读 `CLAUDE.md`。在仓根的 `AGENTS.md` 加一段从 `CLAUDE.md` 抽取的 Codex 必知子集（路径、commit 双语、python3、浅色主题、3 条红线）。手动维护即可，不写自动同步脚本——一周复盘时顺便对一遍。

## 3. 不做的事（明确砍掉）

为了避免 v1.x 又被审查放大，明确**不做**：

- ❌ `codex-router.py` 决策树 hook（让 Claude 判断就行）
- ❌ PostToolUse / PreToolUse 任何 router 相关 hook
- ❌ marker 文件 / chokepoint / hash 锁
- ❌ Gate 审查 pre-pass（Codex 在审查中的角色是 0）
- ❌ 威胁模型四元论证 / cumulative drift / signed bias 算法
- ❌ `.wow-harness/router-misroutes.jsonl` / `.wow-harness/router-tobe-reviewed.jsonl` / `.wow-harness/router-health.jsonl`
- ❌ `task_signal` 字段 / `executor` frontmatter 强制 / `task-arch` skill 改造
- ❌ PLAN-083 / 9 WP 拆分

如果未来发现"老板心态规则不够，Claude 还是不分流"，**先调规则文字，不加机制**。机制化必须先在每周复盘里证明"调规则解决不了"。

## 4. 实施清单（4 个文件，不是 18 个）

| # | 文件 | 改动 |
|---|---|---|
| C1 | `CLAUDE.md` | 在 §一 之前插入 §零「老板心态」硬段 |
| C2 | `.claude/agents/codex-dev.md` | 顶部加 3 条红线 |
| C3 | `AGENTS.md` | 加「Codex 必知子集」一节（红线 + commit 双语 + python3 + 浅色主题） |
| C4 | ChatGPT Pro 控制台 | Nature 手动配置 5 个 Automation（D3 表）+ 验证 main branch protection 已开 |

C1/C2/C3 由本 ADR 同 commit 一起做。C4 由 Nature 手动完成，做完在 `MEMORY.md` 记一笔。

## 5. 复盘节奏

**每周一次**（不是月度）。每周末 Nature 看一次：

1. 这周 codex-dev 被调用了几次？（人脑估算，不需要 metrics 文件）
2. 有没有发生"应该分流但没分流"的明显案例？
3. 5 个 Automation 是否都在跑？产出是否被消费？
4. 老板心态规则要不要改字？

如果连续 2 周分流明显不足，再考虑加机制；不要先建机制再找用途。

## 6. 验收

不设可量化指标。验收靠 Nature 的主观感受：

- 月度 Claude token 消耗有没有"明显感觉降低"
- codex-dev 有没有"明显感觉被用起来"
- 5 个 Automation 是否真的在 PR 队列里看到产出

当出现"感觉跟 v1.0 之前没区别"时，回头审视：是规则文字不够强？还是 Automation 没配？不是"加机制"。

## 7. 关联

- ADR-038 D11 — 审查 agent 工具隔离，与本 ADR 正交（本 ADR 不动审查门，Codex 不参与审查）
- <EXTERNAL_PIPELINE_REDACTED> — Automation 下游消费方示例（已脱敏移除）
- `CLAUDE.md §四 4.3` — subagent 模型约束。codex-dev 是**执行类**而非判断类 subagent，不受 4.3 opus 约束（这一句加到 4.3 末尾的例外子句里，由 C1 顺手做）
- `memory/feedback_codex_quality_issues.md` / `feedback_codex_error_patterns_crystal_learn.md` — Codex 已知失败模式，沉淀在 memory 而不是 hook

## 8. 失败模式记录（v0.1 → v0.3 教训）

为什么前 3 版会膨胀：

1. **审查门 PEHK 规则在小决策上反向放大**：「任一 reviewer P0 → BLOCK」逼出"每轮按红队最大威胁假设加机制"的循环
2. **没人喊停**：作者在 Gate 流程里默认遵循 reviewer，没意识到原始诉求只需要 100 行 ADR
3. **威胁模型不显式**：v0.3 才补 §2.0 威胁模型，但已经是在过度工程之上的防御
4. **Skill 状态机鼓励完整性**：lead skill 的 Gate 0→8 完整流程对"30 分钟级别的偏好调整"是过度的——快速通道（CLAUDE.md §零行为约束 2.2）的 5 条触发条件应该被本 ADR 命中

教训沉淀到 `feedback_review_driven_complexity_inflation.md`，将来类似规模的 ADR 直接走快速通道，不开 Gate 2 三角审查。
