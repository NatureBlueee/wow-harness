# ADR-H4: Prompt 治理（行为偏好三类清单：黑话 / 推卸 / 过度 review）

**状态**：Draft（待 reviewer 复核后转 Accepted；H 系列拓扑 D 第 5 个 ADR）
**日期**：2026-04-28
**关联**：ADR-H0 元规约 / ADR-H2 身份隔离 / ADR-H9 inbox 邮箱 / ADR-H3 memory scope / ADR-041 Codex 分流 v1.0 / ADR-038 D11 schema-level 隔离 / `.claude/skills/lead/SKILL.md`

## 1. 决策本质

把跨 session 反复出现的"行为偏好类违规"（黑话 / 推卸决策 / 过度 review）从**散落在 6 条 memory feedback** 升级为 **lead SKILL.md 内一段 ≤30 行 checklist**，让 lead skill 加载时直接推入 prompt context；触发 70% 遵从率（ADR-038 D11.2 prompt-level 兜底基线，schema 隔离不适用——这是行为偏好，不是工具调用边界）。

> **H4 = 把已经存在但散落的教训聚拢成 lead skill 上的清单**，不是发明新规则。
> ADR-041 v1.0 已签"老板心态 + 红线 + 每周复盘"哲学——本 ADR 是其在"语言/对话表达"侧的具体化。

## 2. 不变量（INV-H4）

- **INV-H4-1（清单最小厚度）**：`.claude/skills/lead/SKILL.md` 内必须存在一段 `## 行为治理（H4 三类清单）` 或同义标题，含 **≥10 条** checklist 项（每条 1 行：触发场景 → 应有行为 → memory pointer）
- **INV-H4-2（pointer 强制）**：每条 checklist 必须挂 `feedback_*.md` 真相源 pointer；不允许新建无 pointer 的"凭空规则"（避免 ADR-041 v0.1 → v0.3 inflation 重演）
- **INV-H4-3（哲学边界硬规）**：H4 **不**写任何 hook、**不**加 metrics、**不**动 `review-contract.yaml`、**不**改 PreToolUse / PostToolUse / SessionStart hook 链路（schema-level 治理是 H2/H7/H6 段范畴；H4 严格留在 prompt-level）

## 3. 设计

### 3.1 三类清单（H4 最小集合）

按现有 6 条 memory feedback 教训映射到 3 个语义类：

| 类别 | 触发场景 | 应有行为 | memory pointer |
|------|---------|---------|---------------|
| **黑话** | 跟 Nature 对话中即将冒出 idle / commit / SendMessage / pytest / PASS / verify / spawn 等术语 | 改用人话（"等一下" / "保存进度" / "跟队友说一声" / "跑测试" / "通过" / "验证" / "派人去做"）；保留协议术语仅在 ADR/PR 内部 | `feedback_no_jargon_with_nature.md` |
| **黑话（task-arch）** | 起草 task-arch 文档时倾向把每个 seam 契约逐字复写 | 每 seam 只 3 行角色 + PLAN 引用 | `feedback_task_arch_verbose_rewrite.md` |
| **推卸（反问）** | 收到不熟悉的需求时第一反应是反问"你确认要 X 吗？" | 拿不准就派 teammate 或先做现状 grep；不要把决策权抛回 Nature | `feedback_stop_asking_confirmation.md` / `feedback_answer_not_ask.md` / `feedback_delegate_to_teammate_on_uncertain.md` |
| **推卸（待协调员决定）** | 起草 ADR/PLAN 时倾向写"待协调员决定 / TBD / 后续讨论" | 直接给当下最佳判断；H0.4 自指禁止已物理化此规则 | `feedback_stop_asking_confirmation.md`（升级版） |
| **过度 review（review-driven inflation）** | reviewer 给 P1/P2 时第一反应是大重构 / 加新机制 / 写 hook 拦截 | 先调规则文字（ADR-041 哲学）；机制化必须先在每周复盘里证明"调规则解决不了" | `feedback_review_driven_complexity_inflation.md` |
| **过度 review（同维度反复）** | 同一 PR 第 N 轮 review 时给同一维度建议 | 多轮同维度 = 边际递减；换正交方法论 | `feedback_review_methodology_orthogonal.md` |
| **过度 review（无证宣告 PASS）** | reviewer 给 PASS 但子项 P0 未闭 | 任何 PASS_WITH_NOTES 含 P0 仍为 BLOCK；修复后必须重评估 | `lead/SKILL.md` 现有段（已存）|
| **完工虚报** | 实现完成即宣告 done，未跑 E2E / 未截图 | E2E + Playwright + 真实后端是 Gate 7→8 必经 | `feedback_e2e_before_push.md` |
| **起草未实证（H 系列 dogfood）** | 起草 ADR/PLAN 引用受管资产时未先 wc / grep / ls 实证 | 起草前必做 4 项核：路径存在 + 行数 + frontmatter 字段 + 前置 ADR 已覆盖 | `.towow/log/harness-self-symptoms.md` §4.7 / §4.8 |
| **结论范围越界** | 单点测试 PASS 即宣告全量 PASS / 平台级声明 | 测试 ≤ docstring ≤ LOG ≤ commit；平台级前核 vendor docs | `feedback_assertion_scope_discipline.md` |

合计 **10 条**，正好达成 INV-H4-1 最小厚度。新增条目按 INV-H4-2 必须挂 pointer。

### 3.2 lead SKILL.md 集成位置

在 lead/SKILL.md 现有"### Gate 7 开发日志硬性要求"段**之后** + "## 联动规则（skill 调度表）"段**之前**插入新段：

```markdown
## 行为治理（H4 三类清单）

> 本段由 ADR-H4 物理化 6 条 memory feedback 教训。lead skill 加载时直接推入 prompt context（70% 遵从率基线，schema 隔离不适用）。
> 任何 checklist 项升级或新增按 INV-H4-2 挂 memory pointer，禁止凭空规则。

### 黑话
- ...

### 推卸
- ...

### 过度 review
- ...
```

### 3.3 与 ADR-041 v1.0 的关系（重要）

ADR-041 v1.0 §3 已签"先调规则不加机制"哲学；本 ADR **完全继承**该哲学：

| 维度 | ADR-041 v1.0 | ADR-H4 |
|------|--------------|--------|
| 治理对象 | Codex 分流决策（"是否派 Codex"） | 表达行为（"怎么说话"） |
| 物理介质 | CLAUDE.md §零 + ADR-041 §3 红线 | lead/SKILL.md `## 行为治理`段 |
| 机制化禁令 | hook / router / metrics 全砍 | 同砍（INV-H4-3）|
| 升级路径 | 每周复盘人脑回顾 | 同（H4 不另立机制） |

H4 是 ADR-041 在不同行为侧（决策 vs 表达）的孪生子，**不重复也不冲突**。

### 3.4 与 H5 边界（plan §3.3.1）

| 维度 | H4 (本 ADR) | H5 (未来) |
|------|-------------|-----------|
| 范围 | lead / arch / towow-dev SKILL.md prompt 段 | review-contract.yaml + Gate 清单 + .claude/skills/towow-review/ |
| 介质 | 纯 markdown 文字 | yaml + 文档 |
| 触发 | skill 加载时 prompt context | Gate 流转时 contract spawn reviewer |
| 治理对象 | 表达行为 | 节奏控制（review 轮次 / inflation 规则） |

二者**不交叉**：H4 不动 review-contract，H5 不动 SKILL.md prompt 段。如某条规则跨界（既要 prompt 又要 yaml），按 plan §3.3.1 串行：先 H4 prompt，再 H5 yaml backport。

### 3.5 受管资产 scope（H0.1 施工隔离）

| 路径 | 动作 |
|------|------|
| `docs/decisions/ADR-H4-prompt-governance.md` | 新增（本文件） |
| `docs/decisions/PLAN-H4-prompt-governance.md` | 新增（PLAN 起草） |
| `.claude/skills/lead/SKILL.md` | 追加 `## 行为治理` 段（≤30 行）|
| `docs/decisions/tasks/PLAN-H4/demo-rewrite-{ts}.md` | 1 个 demo 改写示范（PLAN-H4 §2 WP-04）|
| `docs/decisions/tasks/PLAN-H4/reviewer-verdict-*.md` | reviewer 落点 |
| `.towow/log/harness-self-symptoms.md` | append §4.x（如有自指）|

**不动**：ownership.yaml / hook / review-contract.yaml / arch SKILL.md（暂不改 — PLAN-H4 WP-01 盘点确认现状再定）/ towow-dev SKILL.md / 任何业务代码。

### 3.6 失败模式（必须 inline，不留撞坑）

**FM1**：lead SKILL.md 加上"## 行为治理"段后膨胀超 200 行 → 触发与 INV-H3-1 同类的物理 truncate 风险。
**对策**：H4 段 ≤30 行硬规（INV-H4-1 上限附加值）；超限按 INV-H3-2 双层口径分拆。

**FM2**：H4 写入后被 reviewer 当作 inflation 攻击面 → 重演 ADR-041 v0.1→v0.3 失败模式。
**对策**：每条 checklist 强制挂 memory pointer（INV-H4-2）；reviewer 反对必须指认"哪条规则没 pointer"，否则属同维度反复 review（H4 §3.1 第 6 条命中）。

**FM3**：跨 SKILL.md 复制粘贴（lead → arch → towow-dev）导致同规则三个副本漂移。
**对策**：H4 仅在 lead/SKILL.md 落地；其他 skill 引用时用 pointer 不复制（lead skill 是 entry tier，所有 session 必加载，不需要在 arch/towow-dev 重复）。

## 4. 反对意见与取舍

**反对 1**：lead SKILL.md 已经 169 行 + 加 30 行 = 199 行，逼近 200 行 truncate 阈值（INV-H3-1 同类）。

**取舍**：lead SKILL.md 不是 user-level memory（在 `.claude/skills/lead/`，不受 200 行 truncate 限制；CC skill 加载是按完整文件读，无 line-cutoff）。reviewer 若担心 prompt context token 占用，按 ADR-041 §3 "先调规则不加机制" — 不引入 hook 切片；如未来某段冗余，按 INV-H4-2 删冗余条目（每条必须挂 pointer = 必然有真相源备份）。

**反对 2**：行为偏好治理本质是"语气问题"，靠 prompt 70% 遵从率 = 30% session 仍然违规；该升级到 hook 拦截。

**取舍**：ADR-038 D11 已明确："prompt 解决不了语气问题，schema 也解决不了"。70% 是行为偏好上限；剩 30% 靠 Nature 每周复盘人脑回顾（继承 ADR-041 路径）。任何 hook 拦截"黑话"都会撞 false-positive 海啸（"commit"二字在工程上下文必然出现，hook 无法区分"对 Nature 说 commit"vs"在 ADR 里写 commit"）。

**反对 3**：H4 只做 lead SKILL.md = 漏覆盖 arch / towow-dev 等其他 skill 加载时的违规。

**取舍**：lead 是 entry tier，CLAUDE.md 隐式默认加载；其他 skill 是按需加载。70% 遵从率基线建立在"必读 skill"的位置；arch/towow-dev session 已经有 lead 加载，规则会跨级生效。如未来发现 arch session 的违规率显著高于 lead session，按 ADR-041 路径："先调规则文字" — 在 lead `## 行为治理`段加 1 条"在 arch 子任务中同样适用"，不复制清单。

## 5. ADR-H0 元规约自检

- **H0.1 施工隔离**：scope 列表见 §3.5（6 类路径，全在 `docs/decisions/`、`docs/decisions/tasks/`、`.claude/skills/lead/`、`.towow/log/`）
- **H0.2 节流限速**：本 ADR 目标 ≤ 300 行（终稿见 wc -l）；PLAN-H4 ≤ 500 行
- **H0.3 执检分离**：起草 = 本 session；reviewer 必为非起草 read-only subagent（PLAN-H4 末位 WP）
- **H0.4 自指禁止**：H4 修"黑话/推卸/过度 review"，本 ADR grep `TBD|后续讨论|待协调员决定` 仅元层定义命中（参 ADR-H0 §6 例 4 + §3.1 #4 推卸类条目本身就是定义）
- **H0.5 跨子计划协调**：lead/SKILL.md 共改冲突已记入 H 系列 plan §3.4 冲突表（H2 × H4 串行；H2 已 merged，H4 后续在新 schema 上加段不冲突）
- **H0.6 证据机械化**：所有 INV / DoD 给 grep / wc / `find` 命令（详 PLAN-H4 §2 verify 命令段）
- **H0.meta**：本 ADR 自身不引用 H1/H5/H6/H8 未来产物（grep `\bH[1568]\b` 仅本检查行 + §3.4 H5 边界段命中）

## 6. 关系

- **ADR-H0 §3 元规约**：本 ADR 完全遵守 H0.1-H0.6 + H0.meta（自检见 §5）
- **ADR-H3 INV-H3-2 v1.1 双层限速**：lead SKILL.md 不是 MEMORY.md，不受 200 行 truncate 限制；本 ADR §4 反对 1 已答辩
- **ADR-038 D11.2 prompt-level 兜底基线**：H4 完全在 prompt-level 工作，70% 遵从率是 D11.2 给定上限
- **ADR-041 v1.0 §3 不做的事**：H4 完全继承 §3 哲学，不写 hook / router / metrics（INV-H4-3）
- **PLAN-H4-prompt-governance.md**：本 ADR 工程实施真相源
- **lead/SKILL.md 现有段**：H4 新段插入位置详 §3.2

## 7. 落地范围 + DoD

- 详细 WP 拆解 + DoD：见 PLAN-H4 §2
- H 系列 plan §3.3 H4 行：3 天估时；DoD 关键 = checklist ≥ 10 + 自指悖论显式段 + 自身 grep "TBD\|后续讨论" = 0 + 1 个 demo 改写
- 末位 reviewer 签字：H0.3 执检分离强制
