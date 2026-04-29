# ADR-H3: Memory Scope 分段 + 三态边界（memory / inbox / proposals）

**状态**：Accepted（v1.1，reviewer PASS-WITH-NOTES 后随 v1.1 patch 转 Accepted；H 系列拓扑 D 第 4 个 ADR）
**日期**：2026-04-28（v1.0 起草）/ 2026-04-28（v1.1 reviewer P1-1 + P2-2 修订）
**关联**：ADR-H0 元规约 / ADR-H2 身份隔离 / ADR-H9 inbox 邮箱 / ADR-042 §3 D3/D6/D10 / ~/.claude/projects/-Users-nature------Towow/memory/MEMORY.md
**修订记录**：v1.1 把 INV-H3-2 文本由"单个 `## ` 段 ≤50 行"修订为双层限速"## 父段 ≤80 行 / ### 子段 ≤50 行"，原因见 §4 反对 4（reviewer-verdict-20260428-1741.md P1-1 / P2-2）。

## 1. 决策本质

把跨 session 的"信息持久化"分成 **三个明确状态**，把 MEMORY.md 主索引从"30+ 主题混编、276 行（已超 200 truncate）"重组为"按 scope 分段、≤200 行硬规、单段 ≤50 行"。

> **memory** = user-level 长期 recall index（项目状态快照 + 硬性要求清单）
> **inbox** = cross-session 短期消息（WP 完工 ping / block 升级，已由 H9 落地）
> **proposals** = single-session self-trace（每 session 自留足迹，已存在）

三者**生命周期递减**（memory > proposals > inbox）+ **信息凝固度递减**（memory > proposals > inbox）+ **协作半径递减**（memory cross-window > inbox peer-window > proposals self-window）。

## 2. 不变量（INV-H3）

- **INV-H3-1（主索引硬规）**：`MEMORY.md` 主索引文件总行数 **≤ 200**（CC 用户级 memory 加载的 truncate 阈值；line 200+ 物理上不被加载到 prompt context）
- **INV-H3-2（单段双层限速，v1.1）**：`MEMORY.md` 内 **`## ` 父段总行数 ≤ 80**（含所有 `### ` 子段累计）+ **单个 `### ` 子段 ≤ 50 行**（含 metadata 与子项）。两层独立约束（父段 ≤80 与子段 ≤50 必须同时满足；不取最严，也不二选一）。超 80 父段 = 必须把整段下沉到 topic-specific .md，主索引仅留 1 行 pointer；超 50 子段 = 必须把该子段拆出去，父段保留其余子段。**v1.0 旧文本"`## ` 段 ≤50 行"是单层限速，v1.1 修订原因**：父段含多个 `### ` 子段时，单层口径会因为"按 ## 切" vs "按 ### 切"产生度量分歧（reviewer-verdict-20260428-1741.md P1-1）；现状"关键索引"段 73 行属指针索引大目录形态，硬拆反碎片化（§4 反对 4）。
- **INV-H3-3（三态边界）**：跨 session 短期通信 **走 inbox 不走 memory**；single-session 自我足迹 **走 proposals 不走 memory**；MEMORY.md **不得新增**"待办 / ping / 进行中 WP" 语义条目（这些是 inbox/proposals 的语义）

## 3. 设计

### 3.1 三态边界判定表

| 内容形态 | 走哪 | 生命周期 | 协作半径 |
|---------|------|---------|---------|
| 项目状态快照（"K3 已上线 / 计费已闭环"） | memory | 跨 session 长期，保留至项目终止/重大变更 | cross-window 共读 |
| 硬性要求 / 教训沉淀（"不要反复确认"） | memory | 跨 session 长期，保留至 Nature 显式撤销 | cross-window 共读 |
| 真相源 pointer（"K-Series Roadmap 在 docs/roadmaps/...") | memory | 跨 session 长期，保留至该真相源失效 | cross-window 共读 |
| WP-N 完工 ping / block 升级 | **inbox**（走 H9） | 短期，主窗口 ack 后归档 | peer-window 单次定向 |
| Single-session 决策足迹（"我决定用 X 方案"） | **proposals** | session 内 + 收敛期归档 | self-window 自留 |
| "待协调员决定" / "TBD" / "下次再说" | **❌ 哪都不走** | H0.4 自指禁止 | 推卸语义直接禁 |

**判定流程**：写新内容前先问"这是项目终止前都该被任何 session recall 的吗？" → Y = memory；"这是要 ping 主窗口/某个 peer 窗口的吗？" → Y = inbox；"这是我这个 session 的自我足迹吗？" → Y = proposals。

### 3.2 MEMORY.md 主索引重组（≤200 行 / 单段 ≤50 行）

**当前问题**：276 行（line 200+ truncate）+ "硬性要求"段 ~60 项混编 + 项目状态段长短不一。

**重组规则**：
1. **顶部固定**（≤30 行）：身份说明 + 近期重要真相源 pointer（最多 8 条，每条 1-2 行）
2. **硬性要求**：拆分为 topic-specific .md（按主题），主索引段仅留 ≤30 行高频 highlights + 指针到完整清单 `feedback_index.md`（新增）
3. **项目状态段**：每段 ≤30 行；超 30 行下沉到 `project_<name>_state.md`，主索引仅留 1 行 pointer + 1 行最新状态
4. **生产环境 / Discovery / Crystallization** 等技术清单段：每段 ≤30 行，详细数据下沉
5. **Pending Reminder**：禁止累积；每条触发条件满足后立即删除（不留尾巴）

### 3.3 5 条旧 memory 迁移（最低 DoD）

至少迁移 5 条：把 MEMORY.md 现有"硬性要求"段（~60 项）中最高频引用的 5 条 highlights 留主索引，其余下沉为 `feedback_index.md` 单文件目录索引（每条 1 行 pointer）。具体哪 5 条 highlight 由 PLAN-H3 §2 WP-03 起草时按"近 30 天 grep 频次"挑。

### 3.4 与 ADR-H9 §6.5 的关系

ADR-H9 §6.5 已签 **inbox vs proposals** 边界（peer-message vs self-trace）。本 ADR 补全 **memory vs inbox vs proposals** 三态完整图。三 ADR 关系：

```
长期 ─────────── 短期
memory  >  proposals  >  inbox
cross    self-session    peer-window
window     trace          message
recall   ← H3 INV-H3-3 →  ← ADR-H9 §6.5 →
```

### 3.5 与 ADR-042 D3/D6/D10 关系

- **D3 session-owner 真相源**：本 ADR 是 D3 在 user-level memory 文件层的子约束（MEMORY.md 是 user-level；不入 ownership.yaml；本 ADR 决定其 scope 分段策略）
- **D6 心跳契约**：H9 inbox 已物理化"心跳"（peer-window 显式消息）；本 ADR 进一步拒绝把 memory 当心跳通道用（INV-H3-3）
- **D10 资产副真相源**：本 ADR **不**给 MEMORY.md 加 `window_owner` frontmatter——MEMORY.md 是 user-level shared resource，scope 分段在文件**内部**（按 `## ` 段），不在 frontmatter

### 3.6 受管资产 scope（H0.1 施工隔离）

本 ADR 施工范围严格限于：

| 路径 | 动作 |
|------|------|
| `docs/decisions/ADR-H3-memory-scope.md` | 新增（本文件） |
| `docs/decisions/PLAN-H3-memory-scope.md` | 新增（PLAN 起草） |
| `~/.claude/projects/-Users-nature------Towow/memory/MEMORY.md` | 重组（user-level，**不进主仓 commit**） |
| `~/.claude/projects/-Users-nature------Towow/memory/_backup/MEMORY-pre-H3-{ts}.md` | 备份（H 系列灰度 §3.3.3） |
| `~/.claude/projects/-Users-nature------Towow/memory/feedback_index.md` | 新增索引文件（user-level） |
| `.towow/log/harness-self-symptoms.md` | append §4.x（如有） |
| `docs/decisions/tasks/PLAN-H3/reviewer-verdict-*.md` | reviewer 落点 |

**不动**：ownership.yaml / SKILL.md / hook / inbox/proposals/state schema / 任何业务代码。

### 3.7 backup 与回滚

按 H 系列灰度策略 §3.3.3：MEMORY.md 重组前先 `cp` 到 `_backup/MEMORY-pre-H3-{ts}.md`；7 天观察期内任何 vNext 报警可一键 `cp` 回滚。重组期间不删任何 topic-specific .md 文件（225 个 memory 文件保留），仅改 MEMORY.md 主索引指向。

## 4. 反对意见与取舍

**反对 1**：把"硬性要求"拆到 `feedback_index.md` = 多一跳读取；session 启动时 lazy-load 不上 = AI 漏教训。

**取舍**：CC 已经物理 truncate 了 line 200+，"漏读"早已发生（仅是隐藏的）。重组后主索引留 5 条 highlights 是经验上"高频引用 = 高 ROI"；其余教训 grep 即可触发，不影响。如未来发现某条新增 highlight 必要，按 INV-H3-2 限速调换（不增长）。

**反对 2**：单段 ≤50 行硬规会导致项目状态段反复挪到 .md 文件，徒增碎片。

**取舍**：碎片本就是分布式信息组织的代价。MEMORY.md 是**索引**不是**正文**——索引只该列指针。当前"项目状态段"长是历史包袱，不是该有的形态。

**反对 3**：H3 不给 MEMORY.md 加 `window_owner` 与 ADR-H2 D10 形成不一致。

**取舍**：MEMORY.md 是 user-level shared resource，没有"哪个 window 拥有"语义；它是**所有 window 共读 + 所有 window 经协调员仲裁后写**——更接近 ADR-H2 §3.1 中 `window_owner: shared` 的语义，但因为它在 `~/.claude/projects/` 下、不在主仓，frontmatter 字段没意义（lint 工具够不到）。本 ADR 用文件**内**分段替代 frontmatter，是同一精神在不同物理介质上的投影。

**反对 4（v1.1 新增）**：把 INV-H3-2 改成"## ≤80 / ### ≤50"双层限速 = 给"超长指针索引段"开后门，违背 v1.0 严格"≤50"初衷。

**取舍**：v1.0 单层限速文本对"父段含多个 ### 子段"形态有度量分歧（按 ## 切 73 行违例 vs 按 ### 切 14 行合规）；reviewer-verdict-20260428-1741.md P1-1 明确指认。"关键索引"段当前 73 行是**指针索引大目录**形态（每行单 hook + topic-file 链接，无信息冗余），硬拆为 `topics_index.md` 反让用户多走一跳——违 INV-H3-1 初衷（主索引高密度 recall）。双层 ## ≤80 限速仍守住"父段不会无限膨胀"硬底（4 个 80 行段已 320 行 ≫ 200，CC truncate 自然兜底），且让"父段是指针 / 子段是教训"的现状形态合规。INV-H3-1（≤200 总行）+ INV-H3-3（三态边界）这两条**核心承诺不变**；v1.1 仅在 INV-H3-2 这一条度量口径上澄清。

## 5. ADR-H0 元规约自检

- **H0.1 施工隔离**：scope 列表见 §3.6（7 类路径，全在主仓内 `docs/decisions/`、`docs/decisions/tasks/`、`.towow/log/`，加上 user-level memory 重组路径）
- **H0.2 节流限速**：本 ADR 目标 ≤ 300 行（截至本行约 ~150 行；实际终稿见末尾 wc -l）；PLAN-H3 ≤ 500 行
- **H0.3 执检分离**：起草 = 本 session；reviewer 必为非起草 read-only subagent（PLAN-H3 WP 末位安排）
- **H0.4 自指禁止**：H3 修"memory 噪声 / 跨 session 信息漂移"，本 ADR grep `TBD|后续讨论|待协调员决定` 仅元层定义命中（参 ADR-H0 §6 例 4）
- **H0.5 跨子计划协调**：MEMORY.md 共改冲突已记入 H 系列 plan §3.4 冲突表；本 ADR 重组的是主索引**结构**（分段规则 + 单段限速 + 主索引 ≤200 行硬规），后续任何子计划在 H3 收口前不得对 MEMORY.md schema 结构再动手；H3 收口后的 schema 是后续子计划的工作面前提
- **H0.6 证据机械化**：所有 INV / DoD 都给出 grep / wc / test 命令（见 PLAN-H3 §2 verify 命令段）
- **H0.meta**：本 ADR 自身不引用 H1/H4/H5/H6/H8 未来产物（grep `\bH[14-8]\b` 仅本检查行命中）

## 6. 关系

- **ADR-H0 §3 元规约**：本 ADR 完全遵守 H0.1-H0.6 + H0.meta（自检见 §5）
- **ADR-H2 §3.1 schema-level 隔离 + D10 资产副真相源**：H3 选择**不**走 frontmatter 路径，原因 §4 反对 3 已答辩
- **ADR-H9 §6.5 inbox vs proposals 边界**：H3 §3.4 在此基础上扩展为三态完整图
- **ADR-042 §3 D3/D6/D10**：H3 是 D3 + D6 在 user-level memory 介质上的具体化（§3.5）
- **PLAN-H3-memory-scope.md**：本 ADR 工程实施真相源
- **CC user-level memory 加载文档**：MEMORY.md 物理 200 行 truncate 行为（reference）

## 7. 落地范围 + DoD

- 详细 WP 拆解 + DoD：见 PLAN-H3 §2
- H 系列 plan §3.3 H3 行：3 天估时；DoD 关键 = 每段 ≤50 行 + 5 条旧 memory 迁移 + 0 个"待定"
- 末位 reviewer 签字：H0.3 执检分离强制
