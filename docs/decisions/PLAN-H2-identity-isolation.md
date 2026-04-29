---
plan_id: PLAN-H2
title: harness 身份物理隔离工程实施
status: Proposed
adr: docs/decisions/ADR-H2-identity-isolation.md
started: 2026-04-28
last_updated: 2026-04-28
owner: Nature（AI 助手协助）
prereq:
  - docs/decisions/ADR-H0-meta-charter.md
  - docs/decisions/ADR-H2-identity-isolation.md
  - docs/decisions/ADR-042-parallel-dev-state-management.md
  - docs/decisions/ADR-H9-mailbox.md
budget:
  total_lines: 500
  adr_lines: 300
  d10_patch_lines: 100
---

# PLAN-H2: harness 身份物理隔离工程实施

> 本 PLAN 与 ADR-H2 配套，按 H 系列 plan §3.0 三层文档边界：本文件只写 WP 拆解 + DoD 验证清单，不写决策本质（决策本质见 ADR-H2 §1-§5）。

---

## 1. 工程范围

ADR-H2 §6 实施清单的工程展开：5 个 WP，串行（WP-01 → WP-05）。本 PLAN 不引入并行 WP（H2 总估时 3 天，单 session 串行更稳）。

**入口资产清单**（来自 ADR-H2 §3.2 受管资产 + Gate 0 实地盘点）：

| 资产类 | 文件路径 | H2 MVP 是否纳入 | 选取理由 |
|--------|----------|----------------|----------|
| skill | `.claude/skills/lead/SKILL.md` | ✓ | 所有 multi-window session 起步必加载，H 系列起草核心入口 |
| skill | `.claude/skills/arch/SKILL.md` | ✓ | 架构讨论 skill，多 window 共读共写（v1.1：原 nature-designer 无 SKILL.md，仅 `output/` 子目录，候选改 arch） |
| skill | `.claude/skills/toolkit/SKILL.md` | ✓ | pull surface，所有 window 按需调；vNext substrate 入口 |
| hook | `scripts/hooks/inbox-write-ledger.py` | ✓ | H9 邮箱 PostToolUse writer，multi-window 触发的 ledger 路径 |
| hook | `scripts/hooks/inbox-inject-on-start.py` | ✓ | H9 邮箱 SessionStart inject，multi-window 启动时刻共触 |
| hook | `scripts/hooks/owner-guard.py` | ✓ | ADR-042 D4 实施（身份隔离逻辑本身），元层自指最强示范 |

非 MVP 资产（其余 28 skill + 7 hook + 全部 agent）按 H2 后增量补，本 H2 不强制。

---

## 2. WP 拆解

### WP-01：owner frontmatter schema 文档定义

**目标**：把 ADR-H2 §3.1 schema 表格落到一个机器可解析的 frontmatter spec 文件，供后续 lint 工具（H6 段）读取。

**交付物**：
- 新增 `docs/handoffs/owner-frontmatter-schema.md`（schema 定义 + 字段语义 + 示例）
- 引用：ADR-H2 §3.1 + INV-H2-1/2/3

**DoD**：
- [ ] schema 文件存在 + 含 3 个字段 (`owner` / `owner_since` / `owner_adr`) 表格
- [ ] 含至少 1 个 minimal 示例 + 1 个 shared 示例 + 1 个 unowned 示例
- [ ] 引用 ADR-H2 §3.1 + ADR-042 §5
- [ ] 行数 ≤ 80（防止 schema 文档自身膨胀）

**估时**：30 min

**verify 命令**：
```bash
test -f docs/handoffs/owner-frontmatter-schema.md && wc -l docs/handoffs/owner-frontmatter-schema.md
grep -c "^| \`owner" docs/handoffs/owner-frontmatter-schema.md  # 期望 ≥3 字段行
```

---

### WP-02：ownership.yaml 日志剥离 → ownership.changelog.md

**目标**：把 ownership.yaml 里 ~130 行协调员日志注释剥离到独立 append-only changelog，yaml 主体只剩纯 schema。

**交付物**：
- 新增 `docs/handoffs/ownership.changelog.md`（按时间戳倒序）
- 修改 `docs/handoffs/ownership.yaml`：
  - 删除所有 `# YYYY-MM-DDTHH:MM 协调员` 注释段（约 line 6-136）
  - 顶部加 1 行 pointer：`# 协调员动作历史见 docs/handoffs/ownership.changelog.md`
  - 保留 `version` / `schema` / `adr` / `last_updated` / `last_updated_by_session` 5 行 frontmatter
  - 保留所有 `windows:` / `planned_windows:` / `conflict_history:` / `compact_recovery_protocol:` schema 段一字不动

**操作流程**：
1. `git show HEAD:docs/handoffs/ownership.yaml` 备份当前完整版本到临时文件
2. `awk '/^# 2026-/,/^[a-z]/' temp.yaml` 提取所有日志注释段
3. 反序写入 `docs/handoffs/ownership.changelog.md`（最新在顶）
4. 用 `sed`/手工 Edit 从 yaml 中删除日志段
5. 顶部加 pointer 行
6. 跑 yaml lint：`python3 -c "import yaml; yaml.safe_load(open('docs/handoffs/ownership.yaml'))"`

**DoD**：
- [ ] `ownership.changelog.md` 存在 + 含至少 3 段历史日志（迁移完整性证据）
- [ ] `ownership.yaml` 行数 ≤ 860（当前 979；剥离 ~125 行日志后 schema 主体 ~855 是 18 windows 实例的不可压结构基线）
- [ ] yaml 仍可被 `yaml.safe_load` 成功解析（schema 完整性）
- [ ] yaml 顶部含 changelog pointer 行
- [ ] 所有 windows 实例条目无丢失（diff 前后 `windows:` 段对比）

**估时**：1 h

**verify 命令**：
```bash
test -f docs/handoffs/ownership.changelog.md
wc -l docs/handoffs/ownership.yaml  # 期望 ≤ 800
python3 -c "import yaml; d=yaml.safe_load(open('docs/handoffs/ownership.yaml')); print(len(d.get('windows',[])))"
grep -c "^# 协调员动作历史见" docs/handoffs/ownership.yaml  # 期望 1
```

---

### WP-03：≥3 skill + ≥3 hook 落 `window_owner` 字段

**目标**：按 §1 入口资产清单，给 6 个 MVP 资产文件 frontmatter 加 `window_owner` 字段（v1.1 修订；原措辞 `owner` 与历史人名语义冲突，详见 ADR-H2 §3.1 修订记录）。

**交付物**：6 个文件 frontmatter 编辑

**`window_owner` 值映射**（按现有 ownership.yaml 实际登记 / 协调员判定）：

| 文件 | `window_owner` 值 | `window_owner_since` | 备注 |
|------|----------|-------------|------|
| `.claude/skills/lead/SKILL.md` | `shared` | 2026-04-28T17:00+08:00 | lead skill 多 window 共加载，shared 语义最准；保留现有 `owner: nature` 不动 |
| `.claude/skills/arch/SKILL.md` | `shared` | 2026-04-28T17:00+08:00 | 架构讨论多 window 共读共写；保留现有 `owner: nature` 不动 |
| `.claude/skills/toolkit/SKILL.md` | `shared` | 2026-04-28T17:00+08:00 | pull surface 全 window 按需；保留现有 `owner: nature` 不动 |
| `scripts/hooks/inbox-write-ledger.py` | `window-0-coordinator` | 2026-04-28T17:00+08:00 | H9 邮箱 hook 由协调员维护；其他 window 不写 |
| `scripts/hooks/inbox-inject-on-start.py` | `window-0-coordinator` | 2026-04-28T17:00+08:00 | 同上 |
| `scripts/hooks/owner-guard.py` | `window-0-coordinator` | 2026-04-28T17:00+08:00 | ADR-042 D4 实施 hook，由协调员维护；元层自指 |

**SKILL.md frontmatter 加字段**：在 `name`/`description`/`tools`/`owner`（如有，不动）同级追加 `window_owner` / `window_owner_since`。

**hook .py 加字段**：Python 文件 frontmatter 走"模块 docstring 顶部 YAML block"约定（同 ADR-058 helper 已用模式）：
```python
"""
---
name: inbox-write-ledger
window_owner: window-0-coordinator
window_owner_since: 2026-04-28T17:00+08:00
window_owner_adr: docs/decisions/ADR-H2-identity-isolation.md
---

inbox-write-ledger.py — PostToolUse Write hook ...
"""
```

**DoD**：
- [ ] 6 个文件全部含 `window_owner` 字段（`grep -c "^window_owner:" <files>` 总数 = 6）
- [ ] 6 个文件全部含 `window_owner_since` 字段
- [ ] hook .py 文件加完字段后仍 `python3 -c "import ast; ast.parse(open('<file>').read())"` PASS（语法不破）
- [ ] SKILL.md 加完字段后 `python3 -c "import yaml; ..."` 解析 frontmatter 仍 PASS
- [ ] `lead` skill 加载时不报错（不能因新字段把 lead 加载链炸断）
- [ ] 现有 `owner: nature` 字段（如有）保留未动（diff 验证）

**估时**：1 h

**verify 命令**：
```bash
for f in .claude/skills/lead/SKILL.md .claude/skills/arch/SKILL.md .claude/skills/toolkit/SKILL.md scripts/hooks/inbox-write-ledger.py scripts/hooks/inbox-inject-on-start.py scripts/hooks/owner-guard.py; do
  test -f "$f" && grep -q "^window_owner:" "$f" && echo "PASS $f" || echo "FAIL $f"
done
# 期望 6/6 PASS
python3 -c "import ast; ast.parse(open('scripts/hooks/owner-guard.py').read())"  # 不能破语法
```

---

### WP-04：ADR-042 §3 D10 补丁

**目标**：在 ADR-042 §3 末尾（line 143 D9 段之后、line 151 §4 之前）插入 D10 段，引用 INV-H2-1/2/3 并交代与 D1-D9 关系。

**交付物**：`docs/decisions/ADR-042-parallel-dev-state-management.md` 新增 D10 段（≤100 行 H0.2 budget）

**D10 段骨架**（≤100 行）：
1. 标题 `### D10. 资产 frontmatter owner 字段（schema-level 副真相源）`（1 行）
2. 1 段引用 ADR-H2 §1 决策本质（3 行）
3. INV-H2-1/2/3 列出（10 行）
4. 与 D3 关系（主副真相源 + 互校规则）（10 行）
5. 与 D2 关系（commit 姿势 + frontmatter 双闸）（5 行）
6. 与 D5 关系（planned_windows 也按受管资产标 owner）（5 行）
7. 例外申请条款（参考 review-agent-isolation.md §"例外申请"格式）（10 行）
8. 受管资产清单 pointer 到 ADR-H2 §3.2（5 行）
9. 落地范围 pointer 到 PLAN-H2（5 行）

**DoD**：
- [ ] ADR-042 §3 末尾新增 D10 段
- [ ] D10 段行数 ≤ 100（H 系列 plan §3.3 H2 行硬规）
- [ ] D1-D9 一字不改（diff verify only line 143-150 之后插入，line 1-142 不变）
- [ ] D10 段含 INV-H2-1 / INV-H2-2 / INV-H2-3 至少 3 处引用
- [ ] D10 段含 ADR-H2 路径 + PLAN-H2 路径 pointer
- [ ] ADR-042 总行数 ≤ 363（当前 263 + D10 100 上限）

**估时**：30 min

**verify 命令**：
```bash
grep -n "^### D10" docs/decisions/ADR-042-parallel-dev-state-management.md | head -1
# 期望 line 在 §4 反对意见之前
awk '/^### D10/,/^## 4\./' docs/decisions/ADR-042-parallel-dev-state-management.md | wc -l
# 期望 ≤ 100
git diff docs/decisions/ADR-042-parallel-dev-state-management.md | grep "^-" | grep -v "^---" | wc -l
# 期望 = 0（D1-D9 一字不改，纯插入）
```

---

### WP-05：非起草 reviewer 复核（H0.3 执检分离）

**目标**：spawn 一个非起草 reviewer subagent（read-only frontmatter 物理隔离），复核 ADR-H2 + PLAN-H2 + WP-01..04 实施物。

**reviewer brief**（必含）：
- 复核 ADR-H2 §1 INV-H2-1/2/3 一致性
- 复核 ADR-042 D10 与 D1-D9 不冲突
- 复核 6 个 MVP 资产 frontmatter `owner` 字段语法 + 值合理性
- 复核 ownership.yaml 日志剥离完整性（diff 前后 windows 数量不丢）
- 复核 H0 元规约自检（H0.1 scope / H0.2 行数 / H0.3 执检分离 / H0.4 自指 / H0.5 跨 H 协调 / H0.6 证据机械化）
- 复核结论形式：PASS / PASS_WITH_NOTES / BLOCK，每条 finding 标 P0/P1/P2

**reviewer agent picks**：`towow-review-toolkit:reviewer`（plugin 内 frontmatter 物理隔离 reviewer，schema-level 100% 遵从）

**DoD**：
- [ ] reviewer 复核完成 + 输出落 `docs/decisions/tasks/PLAN-H2/reviewer-verdict-<ts>.md`（或 inbox 邮箱）
- [ ] 总裁决 = PASS 或 PASS_WITH_NOTES（P0 = 0）
- [ ] 若 PASS_WITH_NOTES：所有 P1 由协调员 inline 修；P2 登记 followup（不阻断）
- [ ] H0.3 执检分离证据：reviewer agent 不是 ADR-H2/PLAN-H2 起草者（验证 reviewer agent 是 plugin 内 read-only subagent，非协调员本体）

**估时**：1 h

**verify 命令**：
```bash
ls docs/decisions/tasks/PLAN-H2/reviewer-verdict-*.md 2>/dev/null | head -1
# 期望存在
```

---

## 3. WP 执行顺序与依赖

```
WP-01 schema 文档 → WP-02 yaml 剥离 → WP-03 6 资产 owner → WP-04 D10 补丁 → WP-05 reviewer
   (前置: ADR-H2)        (无前置)        (依赖 WP-01 schema) (依赖 WP-03 实证) (依赖 WP-01..04)
```

**串行 + 单 session**。预计总耗时 ~4 h（含 reviewer 异步等待）。如某 WP 超期 50% 触发"hanis 自指症状"记录（H 系列 plan §3.5 节奏控制）。

---

## 4. 不在本 PLAN 范围（明确划界，防膨胀）

- ❌ owner frontmatter lint 自动校验工具（→ H6 状态健康度段）
- ❌ PreToolUse hook 拦截"无 owner 资产被写"（→ H6）
- ❌ 28 个非 MVP skill / 7 个非 MVP hook 标 owner（→ H 系列后续段按需增量）
- ❌ agent.md 标 owner（H2 不强制 ≥3 个 agent，按需）
- ❌ owner 字段历史回溯重写（owner_since 只对 H2 之后字段写）
- ❌ owner 值 enum 约束（free-form，靠 reviewer Gate 抓）

---

## 5. 失败回滚（参 H 系列 plan §3.3.4）

| 档位 | 触发 | 处置 |
|------|------|------|
| 轻 broken | WP-03 某资产加 owner 字段后 lead skill 加载报错 | inline 修；不 revert；记 `.towow/log/harness-self-symptoms.md` |
| 中 broken | WP-02 ownership.yaml 剥离后 vNext smoke 失败 / 协调员查 yaml 报错 | hotfix 内修复 1h 内；超时升级 |
| 重 broken | WP-04 ADR-042 D10 补丁与 D3/D5 实质冲突 | `git revert <H2-commit>`；下游 H3 worktree 重 rebase；Nature 单签 |
| 最坏 | 连续 2 个 WP 重 broken | H2 暂停 1 周；Nature 评估拆 H 或调拓扑 |

---

## 6. 自指自检（H0.4 必填）

- 本 PLAN 修问题症状关键词（"间接寻址"/"单点真相源膨胀"）→ 本 PLAN 自身**不**用间接寻址（所有受管资产清单在本文件 §1 直接列出，不让读者再去查 ownership.yaml）
- 本 PLAN 是否引用未来产物（H3-H8）？仅在 §4 不在范围列 H6 lint 工具作为后置依赖（合规：lint 是后置依赖不是前置依赖）
- 本 PLAN 是否含"待协调员决定"等推卸字眼？grep 验证：`grep -nE '(TBD|后续讨论|待协调员决定)' docs/decisions/PLAN-H2-identity-isolation.md` 仅元层定义命中（参 ADR-H0 §6 例 4）

---

## 7. 收尾约定（参 ADR-H9 模式）

WP-05 reviewer PASS 后：
1. 翻 ADR-H2 status：Proposed → Accepted（line 3）
2. 翻本 PLAN frontmatter status：Proposed → Accepted
3. §11 WP 表（如本 PLAN 后续展开会用，目前 §2 已是 WP 详表）所有 row 翻 ✓ DONE
4. 收尾 commit 走"原子 -o pathspec"模式（H 系列 plan §3.3 commit 姿势）
5. 同 commit 写 `.towow/log/harness-self-symptoms.md` 一行 PASS 记录（如演练发现新 spec 误读则附带 spec 澄清）

---

## 8. 进度追踪

- [ ] WP-01 schema 文档
- [ ] WP-02 yaml 日志剥离
- [ ] WP-03 6 资产 owner 字段
- [ ] WP-04 ADR-042 D10 补丁
- [ ] WP-05 reviewer 复核
