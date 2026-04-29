# PLAN-H4: Prompt 治理工程实施（lead/SKILL.md 三类清单落地）

**状态**：Draft（待 ADR-H4 reviewer 签字后转 Active；H 系列拓扑 D 第 5 个 PLAN）
**日期**：2026-04-28
**估时**：3 天（继承 H 系列 plan §3.3 行）
**关联**：ADR-H4-prompt-governance.md（决策真相源）/ ADR-H0 元规约 / ADR-041 v1.0 / `.claude/skills/lead/SKILL.md`

## 1. Context

本 PLAN 是 ADR-H4 决策的工程实施真相源（详细 WP / DoD / 验证命令）。ADR-H4 §3 已锁三类清单 + lead/SKILL.md 插入位置 + 哲学边界 + 失败模式；本 PLAN 把它们拆为可执行 WP。

> **三层文档边界**（H 系列 plan §3.0）：本 PLAN 写 WP 拆解 + DoD 机械化命令；不写决策辩证（在 ADR-H4 §1-§4）；不写实施 LOG（在 `docs/decisions/tasks/PLAN-H4/WP-NN/LOG.md`）。

## 2. WP 拆解（5 WP 模式）

### WP-01: 现状盘点（precondition，避 §4.8 第 3 次复发）

**目标**：施工前完成 4 项核（路径存在 + 行数 + frontmatter 字段 + 前置 ADR 已覆盖），杜绝起草未实证症状。

**动作**：
1. `wc -l .claude/skills/lead/SKILL.md`（确认当前 169 行 + 加 ≤30 行预算 ≤200 行）
2. `grep -nE "^## |^### " .claude/skills/lead/SKILL.md`（确认 "Gate 7 开发日志硬性要求" 段在 line 152、"联动规则（skill 调度表）" 段在 line 158 — ADR-H4 §3.2 锚点）
3. `ls .claude/skills/lead/SKILL.md ~/.claude/projects/-Users-nature------Towow/memory/feedback_no_jargon_with_nature.md ~/.claude/projects/-Users-nature------Towow/memory/feedback_stop_asking_confirmation.md ~/.claude/projects/-Users-nature------Towow/memory/feedback_review_driven_complexity_inflation.md`（确认 6 个 pointer 真相源全存在）
4. `grep -n "行为治理\|H4 三类\|黑话\|推卸\|过度 review" .claude/skills/lead/SKILL.md`（确认目标段位现尚无重叠规则；如有重叠 → WP-02 设计为 enhancement 而非 new section）

**DoD**（机械化）：
- 4 项核命令全跑通 + 输出落 `docs/decisions/tasks/PLAN-H4/WP-01/baseline-evidence.md`
- 任一项偏离 ADR-H4 §3.2/§3.5 假设 → 必须先回 ADR-H4 修订（避免 ADR/PLAN 漂移）

**预估**：0.3d（半上午）

### WP-02: lead/SKILL.md 段起草（≤30 行 + 10 条 + 全 pointer）

**目标**：把 ADR-H4 §3.1 三类清单 10 条物化为 lead/SKILL.md 内 ≤30 行 markdown 段。

**动作**：
1. backup `cp .claude/skills/lead/SKILL.md .claude/skills/lead/SKILL.md.pre-h4-bak`（不入 git，仅本地保命）
2. 起草 `## 行为治理（H4 三类清单）` 段草稿到 `docs/decisions/tasks/PLAN-H4/WP-02/draft-section.md`（独立文件先验段长 + 内容审）
3. 段结构（严格 ≤30 行）：
   ```
   ## 行为治理（H4 三类清单）              # 1 行
                                          # 1 行空
   > 由 ADR-H4 物理化 6 条 memory ...     # 2 行 blockquote
                                          # 1 行空
   ### 黑话                                # 1 行
   - jargon 检测 → ...（pointer）         # 1 行
   - task-arch 复写 → ...（pointer）      # 1 行
                                          # 1 行空
   ### 推卸                                # 1 行
   - 反问 → ...（pointer）                # 1 行
   - 待协调员决定 → ...（pointer）        # 1 行
                                          # 1 行空
   ### 过度 review                         # 1 行
   - inflation → ...（pointer）           # 1 行
   - 同维度反复 → ...（pointer）          # 1 行
   - 无证 PASS → ...（pointer）           # 1 行
                                          # 1 行空
   ### 其他                                # 1 行
   - 完工虚报 → ...（pointer）            # 1 行
   - 起草未实证 → ...（pointer）          # 1 行
   - 结论范围越界 → ...（pointer）        # 1 行
   ```
   合计 ≤25 行（裕量 5 行给 pointer 长度）

**DoD**（机械化）：
- `wc -l docs/decisions/tasks/PLAN-H4/WP-02/draft-section.md` ≤ 30
- `grep -c "feedback_.*\.md\|harness-self-symptoms.md" draft-section.md` ≥ 10（每条挂 pointer，INV-H4-2）
- `grep -c "^- " draft-section.md` ≥ 10（INV-H4-1 厚度）
- 段内零 hook / metrics / review-contract / spawn 关键词（INV-H4-3 哲学边界）：`grep -iE "hook|metrics|review-contract|spawn" draft-section.md` 必须为零

**预估**：0.5d（半天起草 + reviewer self-check）

### WP-03: Demo 改写示范（"前 vs 后" 对照）

**目标**：取 1 条历史违规实例（推卸 / 黑话 / 过度 review 任选），写"H4 前 → H4 后"对照，让未来 reviewer / Nature 验收时能秒判 H4 是否生效。

**动作**：
1. 从 `.towow/log/harness-self-symptoms.md` §4.1-§4.9 中挑 1 条最具代表性的违规实例（建议 §4.1 plan §3.5 隔离策略违反 H0.4 自指禁止 — "推卸（待协调员决定）"代表）
2. 写到 `docs/decisions/tasks/PLAN-H4/WP-03/demo-rewrite-{ts}.md`：
   - **H4 前（违规）**：原文摘录（≤10 行 quote）
   - **触发的 checklist 条**：哪条 H4 规则本应触发
   - **H4 后（合规重写）**：改写示范（≤10 行）
   - **判定逻辑**：grep 哪个关键词命中 / 应改为哪个表达
3. demo 改写本身**不修改原文件**（避 §4.x 第 N 次复发：改 .towow/log 等于篡改 dogfood 数据流）—— 仅作示范

**DoD**（机械化）：
- `wc -l docs/decisions/tasks/PLAN-H4/WP-03/demo-rewrite-*.md` ≤ 60（前+后+判定 ≤60 行总）
- demo 文件 grep `^### H4 前\|^### H4 后` 各 ≥1 段
- demo 引用的 self-symptoms 行号能 verify（`grep -n "$快照" .towow/log/harness-self-symptoms.md` 命中）

**预估**：0.5d

### WP-04: lead/SKILL.md race-safe 嵌入

**目标**：把 WP-02 草稿落到 `.claude/skills/lead/SKILL.md`，行数 + 段位 + 内容三验证 PASS。

**动作**：
1. 嵌入前再核 `git status` 不在 merge state（如在 → defer 到 merge conclude，记 self-symptoms §4.x — §4.9 同模式可能复发）
2. `Edit` 工具在 lead/SKILL.md line 157（"## 联动规则（skill 调度表）" 之前）插入 WP-02 段
3. 嵌入后立即 `wc -l .claude/skills/lead/SKILL.md` 验 ≤200 行（FM1 防御）
4. `grep -nE "^## |^### " .claude/skills/lead/SKILL.md` 验段顺序：Gate 7 段（line ≤157）→ 行为治理段（line 158-185 区段）→ 联动规则段（line ≥186）
5. race-safe commit：`git commit --only .claude/skills/lead/SKILL.md docs/decisions/ADR-H4-prompt-governance.md docs/decisions/PLAN-H4-prompt-governance.md docs/decisions/tasks/PLAN-H4/`（用 --only 隔离别 session 的 staged）
6. commit 后 `git show --stat HEAD` 后核：只含本 H4 scope 文件，不带别 plan 串味儿

**DoD**（机械化）：
- `wc -l .claude/skills/lead/SKILL.md` ≤ 200（绝对硬规，FM1 防御）
- `grep -c "## 行为治理（H4 三类清单）" .claude/skills/lead/SKILL.md` = 1
- `grep -c "^- .*feedback_.*\.md\|^- .*harness-self-symptoms.md" .claude/skills/lead/SKILL.md` ≥ 10（嵌入后 INV-H4-1/2 仍成立）
- `git show --stat HEAD` 文件清单严格匹配 §3.5 受管资产 scope（不多不少）

**预估**：0.4d

### WP-05: Reviewer 签字（H0.3 执检分离）

**目标**：spawn `pr-review-toolkit:code-reviewer` 或 `feature-dev:code-reviewer` subagent（read-only directive 兜底，schema-level frontmatter 隔离），签字判定 INV-H4-1/2/3 + ADR-H0 6+1 全 PASS。

**动作**：
1. `Agent(subagent_type="pr-review-toolkit:code-reviewer", run_in_background=true)` spawn reviewer，prompt 含：
   - read-only directive（"do not Edit/Write/Bash; verify only by Read/Grep/Glob"）
   - 验证目标 commit 区间（H4 ADR + PLAN + lead SKILL.md + tasks/PLAN-H4/ 全部）
   - 14 维度核查清单（INV-H4-1/2/3 + ADR-H0 6+1 + ADR-H4 §3.6 FM 1/2/3 防御 + dogfood §4.x 是否新增）
2. reviewer 输出落 `docs/decisions/tasks/PLAN-H4/reviewer-verdict-{ts}.md`
3. verdict 三态：
   - **PASS**：所有 INV + 6+1 全过 → H4 closure
   - **PASS-WITH-NOTES**：≤ P1 不阻塞 → 同 session 内修补 → 二次 verdict（继承 H3 §4.8 处置经验）
   - **BLOCK**：任 P0 → 必须修补再过

**DoD**（机械化）：
- verdict 文件存在 + 含 `verdict: PASS|PASS-WITH-NOTES|BLOCK` frontmatter
- `grep -c "^## Findings\|^### P0\|^### P1" reviewer-verdict-*.md` ≥ 2 段（即使 PASS 也要列空 P0）
- reviewer ≠ 起草 session（reviewer self-attest 段）
- reviewer 自身 grep `\bH[1568]\b` 仅边界引用 + 自检命中（H0.meta 不引用未来产物）

**预估**：0.3d

## 3. 验证矩阵（汇总 DoD）

| 维度 | 验证命令 | 通过门槛 |
|------|---------|---------|
| INV-H4-1 厚度 | `grep -c "^- " .claude/skills/lead/SKILL.md` 在 H4 段范围 | ≥10 |
| INV-H4-2 pointer | `grep -c "feedback_.*\.md\|harness-self-symptoms.md" lead/SKILL.md` 在 H4 段 | ≥10 |
| INV-H4-3 哲学边界 | `grep -iE "hook\|metrics\|review-contract\|spawn" lead/SKILL.md` 在 H4 段 | =0 |
| FM1 lead 行数 | `wc -l .claude/skills/lead/SKILL.md` | ≤200 |
| FM2 inflation 防御 | reviewer verdict P0/P1 列表 | ≤1 P1（且 pointer 关）|
| FM3 跨 SKILL 漂移 | `grep -l "## 行为治理（H4" .claude/skills/*/SKILL.md` | 仅 lead/SKILL.md 命中 |
| H0.1 scope | `git show --stat HEAD` 文件清单 | 严格 ⊆ ADR-H4 §3.5 |
| H0.2 节流 | `wc -l ADR-H4` / `wc -l PLAN-H4` | ≤300 / ≤500 |
| H0.3 执检分离 | reviewer self-attest 段 | "我非起草人" |
| H0.4 自指禁止 | `grep -E "TBD\|后续讨论\|待协调员决定" ADR-H4 PLAN-H4` | 仅元层定义命中 |
| H0.5 跨子计划 | H 系列 plan §3.4 冲突表 | H4 行已登记 |
| H0.6 证据机械化 | 本 §3 表 | 每行有命令 |
| H0.meta 不引未来 | `grep "\bH[1568]\b" ADR-H4 PLAN-H4` | 仅边界 + 自检命中 |
| Dogfood §4.x | `git diff .towow/log/harness-self-symptoms.md` | 同 session 内自指必登记 |

## 4. 失败回滚策略（继承 ADR-H4 §3.6 + plan §3.3.4）

| 等级 | 触发 | 处置 |
|------|------|------|
| 轻 | WP-04 嵌入后 lead 行数 195-200（接近边界，未越线） | 段内删冗余条目至 ≤25 行；INV-H4-1 仍 ≥10 |
| 中 | WP-04 嵌入后 lead 行数 >200（FM1 触发） | revert lead/SKILL.md 嵌入；H4 段必须先按 INV-H3-2 双层口径分拆为子文件，再二次嵌入 |
| 重 | reviewer 给 P0 BLOCK，且根因是 ADR-H4 决策缺陷而非工程错误 | revert 全部 H4 commit；ADR-H4 修订 v1.1（同 H3 P1-1 处置模式）；不阻塞 H 系列推进 — H4 进入 followup 待 v1.1 后重启 |
| 最坏 | reviewer 给 P0 + 跨 H 副作用（破坏 H2/H3 已落地段） | 按 H 系列 plan §3.3.4 第 4 档 — 暂停 H 系列 1 周，Nature 评估 |

## 5. ADR-H0 元规约自检（PLAN 维度）

- **H0.1 施工隔离**：本 PLAN scope 见 ADR-H4 §3.5，6 类路径全在 `docs/`、`.claude/skills/lead/`、`.towow/log/`
- **H0.2 节流限速**：本 PLAN 目标 ≤500 行（终稿见 wc -l）
- **H0.3 执检分离**：起草 = 本 session（H4 owning）；reviewer = WP-05 spawn 的 read-only subagent
- **H0.4 自指禁止**：本 PLAN grep `TBD|后续讨论|待协调员决定` 仅元层定义命中（参 §2 WP-02 段结构示意，本身就是规则定义）
- **H0.5 跨子计划协调**：lead/SKILL.md 共改冲突已记入 H 系列 plan §3.4（H2 × H4 串行；H2 已 merged 不冲突 / H4 不动 ownership.yaml）
- **H0.6 证据机械化**：每个 WP DoD 段全机械化（详 §3 矩阵）
- **H0.meta**：本 PLAN grep `\bH[1568]\b` 仅 §1 关联 + §3 ADR-H0 / ADR-H3 / ADR-H4 / H 系列 plan 引用 + §5 自检本身命中（无未来产物引用）

## 6. 跨 H 协调登记（H 系列 plan §3.4 增量）

| 文件 | H 触及 | 类型 | 仲裁 | 验证 |
|------|--------|------|------|------|
| `.claude/skills/lead/SKILL.md` | H4 独占 | 新增段（line 157 后插入）| H2/H3 已 merged 且不动 lead/SKILL.md，H4 独占无冲突 | `git log --oneline -- .claude/skills/lead/SKILL.md` 验 H 系列内仅 H4 commit |
| `docs/decisions/ADR-H4-prompt-governance.md` | H4 独占 | 新增 ADR | 编号唯一 | `ls docs/decisions/ADR-H4-*.md` |
| `docs/decisions/PLAN-H4-prompt-governance.md` | H4 独占 | 新增 PLAN | 编号唯一 | `ls docs/decisions/PLAN-H4-*.md` |
| `docs/decisions/tasks/PLAN-H4/` | H4 独占 | 新增目录 | 编号唯一 | `ls docs/decisions/tasks/PLAN-H4/` |
| `.towow/log/harness-self-symptoms.md` | H4 append | append 段（如自指）| 全 H 共享 append-only | `git log -- .towow/log/harness-self-symptoms.md` |

## 7. 进度追踪

- [x] WP-01: 现状盘点（已在 H4 起草前完成 — 即避 §4.8 第 3 次复发的"前置 grep" 动作；wc/grep 4 项核命令已跑，结果纳入 ADR-H4 §3.5）
- [ ] WP-02: 起草草稿段 → `tasks/PLAN-H4/WP-02/draft-section.md`
- [ ] WP-03: demo 改写 → `tasks/PLAN-H4/WP-03/demo-rewrite-{ts}.md`
- [ ] WP-04: lead/SKILL.md 嵌入 + race-safe commit
- [ ] WP-05: reviewer 签字 + verdict 落 `tasks/PLAN-H4/reviewer-verdict-*.md`

## 8. Verify 命令汇总（reviewer 直接 copy-paste）

```bash
# H0.2 行数核
wc -l docs/decisions/ADR-H4-prompt-governance.md docs/decisions/PLAN-H4-prompt-governance.md .claude/skills/lead/SKILL.md

# INV-H4-1 厚度（H4 段范围内 ≥10 条 - 段范围用 awk 切 "^## 行为治理" 到 "^## 联动规则" 之间）
awk '/^## 行为治理（H4 三类清单）/,/^## 联动规则/' .claude/skills/lead/SKILL.md | grep -c "^- "

# INV-H4-2 pointer（每条挂 feedback_*.md 或 harness-self-symptoms.md）
awk '/^## 行为治理（H4 三类清单）/,/^## 联动规则/' .claude/skills/lead/SKILL.md | grep -c "feedback_.*\.md\|harness-self-symptoms.md"

# INV-H4-3 哲学边界（段内零 hook/metrics/review-contract）
awk '/^## 行为治理（H4 三类清单）/,/^## 联动规则/' .claude/skills/lead/SKILL.md | grep -iE "hook|metrics|review-contract|spawn" || echo "PASS: 段内零机制化关键词"

# H0.4 自指扫描（仅元层定义命中）
grep -nE "TBD|后续讨论|待协调员决定" docs/decisions/ADR-H4-prompt-governance.md docs/decisions/PLAN-H4-prompt-governance.md

# H0.meta 未来 H 引用（仅边界 + 自检命中）
grep -nE "\bH[1568]\b" docs/decisions/ADR-H4-prompt-governance.md docs/decisions/PLAN-H4-prompt-governance.md

# FM1 lead 行数（≤200 硬规）
wc -l .claude/skills/lead/SKILL.md

# FM3 跨 SKILL 漂移（仅 lead/SKILL.md 应有 H4 段）
grep -l "## 行为治理（H4 三类清单）" .claude/skills/*/SKILL.md
```

## 9. 与现行 vNext 共存（plan §3.3.3）

| 检查 | 期望 | 缘由 |
|------|------|------|
| K 系列 sandbox smoke 不破 | PASS | H4 仅改 lead/SKILL.md prompt 段，不动 hook / yaml / 业务代码 |
| 业务集成示例 Gate 不破 | PASS | 同上 |
| coaching session 行为 | 70% 遵从率基线（继承 ADR-038 D11.2）| H4 不立硬约束，行为偏好 30% session 仍可能违规 — 不算回归 |
| MCP `towow-mcp` 不破 | PASS | H4 不动 mcp-server / backend |
