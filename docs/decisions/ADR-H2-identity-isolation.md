# ADR-H2: harness 身份物理隔离（资产 frontmatter owner 字段）

**状态**: Proposed
**日期**: 2026-04-28
**起草者**: Nature（AI 助手协助）
**前置**: ADR-H0 元规约 / ADR-042 §5 ownership.yaml schema / ADR-H9 邮箱（H 系列拓扑 D 上游）
**编号说明**: 独立 H 编号（不占主仓 ADR-XXX），H 系列 plan §3.3 表 line "ADR-042 D9 补丁" 是字面歧义——ADR-042 D9 已被"AGENTS.md 渐进加载"占用；本 ADR 实际补的是**新增 D10**，plan 字面"D9 补丁"按本 ADR 校准为"D10 新增"

---

## 1. 决策本质

**一句话**：资产侧 frontmatter `owner:` 字段是 schema-level 副真相源；与 ownership.yaml（D3 主真相源）互校，冲突时取最严；让"这个资产归谁"从资产文件本身可读，不再需要查 yaml 反推。

**不变量 INV-H2-1**：任何被 multi-window 协作 owns 的资产文件（SKILL.md / agent.md / 关键 hook.py）必须在 frontmatter 含 `window_owner: <window-id>` 字段；缺字段 = 视为 unowned shared（任何 window 不得写）。注：v1.1 修订前措辞为 `owner: <window-id>`，因与历史人名语义冲突改用 `window_owner`，详见 §3.1 修订记录。

**不变量 INV-H2-2**：资产 frontmatter `window_owner` 与 ownership.yaml `windows[].owned_folders` 一致性由 lint 工具校验；不一致时取**最严**（以严限松：yaml 列了而 frontmatter 缺 → 加；frontmatter 标了而 yaml 没列 → yaml 补登记）。

**不变量 INV-H2-3**：ownership.yaml 是**纯 schema 数据文件**，不混入协调员日志注释；日志走独立 append-only `docs/handoffs/ownership.changelog.md`，按 ISO8601 时间戳倒序追加。

---

## 2. 动机（为什么 D3 yaml 单点真相源不够）

### 2.1 D3 现状
ADR-042 D3 建立"协调员唯一写入 ownership.yaml + AI 自识身份查 yaml"的模型。9 个月运行下来，三个症状反复出现（H 系列 plan §2.2 #8-10、#30-31）：

1. **ownership.yaml 膨胀**：当前 979 行 = ~700 schema + ~130 协调员日志注释 + ~150 windows 实例。日志注释 prepend-style（最新在顶），导致 schema diff 噪声极大，git blame 失真。

2. **资产侧零标记**：SKILL.md / hook / agent.md 文件本身不知道"我归谁"。AI 编辑 `scripts/hooks/inbox-write-ledger.py` 时，必须先 `grep` ownership.yaml 反查 owner——这是**间接寻址**，compact 后 AI 失忆时容易跳过查询直接编辑（schema-level 物理隔离失效）。

3. **跨 session add→commit race**：D2 commit 姿势标准化只到 commit 层，但 staged area 在 add 和 commit 之间会被并行 session reset/重 stage（feedback memory `parallel_session_git_race_post_commit_verify` 实证）。即便有 D3 yaml，资产侧无 owner 字段意味着 race 时无法在 add 时就拒绝（只能 commit 后审计 `git show --stat`）。

### 2.2 schema-level 物理隔离的论据
ADR-038 D11 + OpenDev arXiv 2603.05344：
- prompt 约束 ~70% 遵从率
- schema 约束 100% 遵从率（物理无法绕过）

D3 yaml 是**单点 schema**——AI 必须主动查询才生效，等同于 prompt-level 约束（"你应该先查 yaml"）。资产侧 frontmatter owner 字段是**资产内嵌 schema**——AI 打开文件就看到，等同 100% 遵从（CC 读文件 = 必读 frontmatter）。

INV-H2-1 把 D3 单点真相源升级为"yaml 主 + 资产副"双真相源，schema 层叠加：要绕过 INV-H2-1 必须同时改两处，hint 比改一处明显得多。

---

## 3. 设计

### 3.1 frontmatter `window_owner` 字段 schema

> **字段名修订记录（v1.1, 2026-04-28）**：原草稿用 `owner` 字段名；WP-03 落地时发现 9 个候选 SKILL.md 已存 `owner: nature` 字段（人名 product owner 语义），与本 ADR 期望的 window 归属语义直接冲突。修订为 `window_owner` 避开历史字段碰撞，同时保留现有 `owner: nature` 字段不动（语义解耦：`owner` = product owner 人名 / `window_owner` = window-id schema 归属）。symptoms §4.7 + ADR-H0 修订建议 #9 已登记此 spec gap。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `window_owner` | string \| `shared` \| `unowned` | 是（受管资产） | window-id（如 `window-0-coordinator`）/ `shared`（多 window 共写需协调员仲裁）/ `unowned`（任何 window 不得写） |
| `window_owner_since` | ISO8601 | 否 | 首次写入时间；用于 changelog 反查 |
| `window_owner_adr` | string | 否 | 关联 ADR 路径；如 owner 决策有专门 ADR |

**字段位置**：所有受管资产（详见 §3.2）的 frontmatter 顶层；与现有 `name` / `description` / `tools` / `owner`（如有）等同级。

**与现有 `owner: nature` 字段关系**：解耦共存。`owner` 沿用既有人名语义（指 Nature 是 product owner），不动；`window_owner` 是新增字段，专管 schema-level window 归属。lint 工具（H6）按 `window_owner` 校验，不读 `owner`。

**示例**：
```yaml
---
name: lead
description: 通爻开发流程统领
owner: nature                                  # 既有字段，product owner = 人名（不动）
window_owner: shared                           # H2 新增，schema-level window 归属
window_owner_since: 2026-04-28T17:00+08:00
window_owner_adr: docs/decisions/ADR-H2-identity-isolation.md
---
```

### 3.2 受管资产清单（H2 落地范围）

INV-H2-1 不要求**所有** SKILL.md / agent.md / hook.py 都标 owner——只要求受 multi-window 协作影响的资产。MVP 范围：

| 资产类 | 路径 pattern | 受管标准 | DoD 数量 |
|--------|-------------|----------|----------|
| skill | `.claude/skills/*/SKILL.md` | lead skill 加载 + 跨 window 共写 | ≥ 3 |
| hook | `scripts/hooks/*.py` + `.claude/plugins/*/hooks/*.py` | settings.json 注册 + 跨 window 触发 | ≥ 3 |
| agent | `.claude/agents/*.md` + `.claude/plugins/*/agents/*.md` | TeamCreate 用 + multi-window spawn | 按需（H2 不强制 3 个） |

后续 H 系列其他段（H4 prompt 治理、H6 状态健康度）需要时增量扩列。

### 3.3 ownership.yaml 日志剥离

**现状**：1-136 行 + 散落的 `# 协调员日志` 注释（共 ~130 行）混在 yaml 里。

**改造**：
- 保留 yaml 顶部 `version` / `schema` / `last_updated` / `last_updated_by_session` 5 行 frontmatter
- 删除所有 `# YYYY-MM-DDTHH:MM 协调员` 注释段（搬到 changelog）
- 新建 `docs/handoffs/ownership.changelog.md`（append-only，最新在顶；与 yaml 同 commit 同步）
- yaml 顶部加一行 pointer：`# 协调员动作历史见 docs/handoffs/ownership.changelog.md`

**预期效果**：yaml 行数 979 → ≤ 800（剥日志后 schema 主体保持，但去掉日志后可读性飞升；后续 windows 增长仍受 D5 限）。

### 3.4 ADR-042 §3 新增 D10

D10 文本（≤100 行 H0.2 budget）落 ADR-042 §3 末尾，不改 D1-D9 任一字。D10 内容：
- 引用 INV-H2-1 / INV-H2-2 / INV-H2-3
- 与 D3 关系（主副真相源 + 互校规则）
- 与 D2 关系（commit 姿势 + frontmatter owner 双闸）
- 与 D5 planning-time 隔离关系（planned_windows 也按受管资产标 owner）
- 例外申请条款（参考 review-agent-isolation.md §"例外申请"格式）

### 3.5 lint 工具（不在本 H 落地，登记 followup）

INV-H2-2 一致性校验需 lint 工具（扫描资产 frontmatter `window_owner` ↔ ownership.yaml `owned_folders`）。本 H2 范围不交付 lint，登记 followup `guard-h2-lint-tooling`，由 H6（状态健康度）段处置。当前阶段一致性靠协调员手工核对 + reviewer Gate 抽样。

---

## 4. 反对意见与取舍

**反对 1**：frontmatter owner 字段会污染资产文件，影响 lead skill 加载。

答：现有 SKILL.md frontmatter 已有 `name` / `description` / `tools` 等 5+ 字段，加 1 个 `owner` 字段不影响 CC 解析（CC 只识别已知字段，未知字段忽略）。lead skill 也只读 `name` / `description`，不会因 owner 字段而失效。

**反对 2**：双真相源会发生 drift，单点 yaml 反而干净。

答：drift 风险确实存在（INV-H2-2 互校规则就是为解决它），但单点 yaml 的"间接寻址"症状已造成实际 race（feedback memory 反复升级三次）。双真相源 + lint 是工程上权衡 drift 风险换取 schema-level 物理隔离的标准做法（参考 K8s 的 etcd ↔ object metadata 双真相源）。

**反对 3**：`owner: shared` 字段语义模糊，谁仲裁？

答：shared = 任何 window 写入前必须经协调员 ping 仲裁，仲裁结果落 changelog；不是"任何人随便写"。语义和 ADR-042 D8 交付形态分层一致。

**反对 4**：H2 是不是又一个机制堆叠？ADR-041 v1.0 警告过。

答：H2 不是行为偏好治理（那是 H4 prompt 范围）；H2 是物理隔离 schema 落地——schema-level 100% 遵从是 ADR-038 D11 已论证的硬门槛，不在 ADR-041 v1.0 警告的"机制堆叠"范畴。H 系列 plan §3.3.1 边界判定表已显式区分。

---

## 5. 与其他 ADR / H 段的关系

| 关系方 | 关系类型 | 说明 |
|--------|----------|------|
| ADR-042 §3 D1-D9 | 不冲突，新增 D10 | INV-H2-1/2/3 嵌入 D10；D1-D9 一字不改 |
| ADR-042 §5 schema | 互校副真相源 | yaml `owned_folders` ↔ 资产 `window_owner` 双向校验 |
| ADR-038 D11 | 同源精神 | schema-level >> prompt-level，H2 是 D11 在 ownership 域的具体应用 |
| ADR-H0 元规约 | 自检 | H2 起草需走 H0.4 自指禁止 grep（已通过：本文件 grep "TBD\|后续讨论\|待协调员决定" 仅命中元层定义）+ H0.2 ≤300 行（本 ADR 目标行数）+ H0.5 跨 H 协调（已 grep gate 0 撞车） |
| ADR-H9 inbox | 渠道复用 | H2 reviewer Gate 走 inbox 通信不靠人手 ping（H 系列 plan §3.5 总体执行守则） |
| H4 prompt 治理 | 不重叠 | H4 治"语气/推卸"等 prompt-level 偏好；H2 治"资产归属"schema-level 物理 |
| H6 状态健康度 | 后置依赖 | H2 落地后 H6 再做 lint 工具 + 状态文件清单（避免 lint 早出但资产无 owner 字段可校） |

---

## 6. 实施清单（PLAN-H2 落地）

详见 PLAN-H2-identity-isolation.md。骨架：
- WP-01: owner frontmatter schema 文档定义（本 ADR §3.1 已含，PLAN 补 lint TODO）
- WP-02: ownership.yaml 日志剥离 → ownership.changelog.md
- WP-03: ≥3 skill + ≥3 hook 标 owner（最小集挑选标准 + 实施）
- WP-04: ADR-042 §3 D10 补丁 ≤100 行
- WP-05: 非起草 reviewer 复核（H0.3 执检分离）

---

## 7. 验收（DoD）

- [ ] 至少 3 个 skill frontmatter 含 `owner` 字段（H 系列 plan §3.3 H2 行硬规）
- [ ] 至少 3 个 hook frontmatter 含 `owner` 字段（H 系列 plan §3.3 H2 行硬规）
- [ ] ADR-042 §3 D10 补丁 ≤ 100 行（H 系列 plan §3.3 H2 行硬规）
- [ ] ownership.yaml 主体行数比 H2 前减少（剥日志后 ≤ 800 行；当前 979）
- [ ] ownership.changelog.md 创建并迁入历史日志（按时间戳倒序）
- [ ] 本 ADR ≤ 300 行（H0.2 budget）
- [ ] H0.4 自指禁止 grep：`grep -nE '(TBD|后续讨论|待协调员决定)' docs/decisions/ADR-H2-identity-isolation.md docs/decisions/PLAN-H2-identity-isolation.md` 仅元层定义命中（参 ADR-H0 §6 例 4）
- [ ] 非起草 reviewer Gate 复核 PASS（H0.3 执检分离）

---

## 8. 不做什么（吸收 ADR-041 v0.1→v0.3 教训 + ADR-H9 边界教训）

- ❌ 不做 lint 自动校验工具（登记 followup `guard-h2-lint-tooling` → H6 段处置）
- ❌ 不做 PreToolUse hook 拦截"无 owner frontmatter 资产被写"（hook IO 已在 H 系列 plan §3.1 H7 撤销后无新 hook 框架；强制拦截留待 H6 状态文件健康度）
- ❌ 不做 owner 字段历史回溯（`git log --diff-filter` 重写 owner_since 不写，只对 H2 之后新加字段写 owner_since）
- ❌ 不做"全部" SKILL.md / hook.py 标 owner（MVP 只覆盖受 multi-window 协作影响的资产；§3.2 范围）
- ❌ 不做 owner 字段值的 enum 约束（free-form string；INV-H2-2 互校时按 ownership.yaml 已知 window_id 反查；非已知值 reviewer Gate 时手工抓）

---

## 9. 变更记录

- 2026-04-28 初稿（Proposed）
- 后续：实施完成后翻 Accepted（参 ADR-H9 模式：附录 A 验收记录 + 状态翻 Accepted 同 commit）
