# PLAN-H3: Memory Scope 分段实施计划

**状态**：Draft（待 reviewer 复核）
**日期**：2026-04-28
**关联**：ADR-H3 / ADR-H0 §3 元规约 / ADR-H9 §6.5 边界

## 1. 工程范围

ADR-H3 §1-§3 决策的工程展开：5 个 WP，串行（WP-01 → WP-05）。本 PLAN 不引入并行 WP（H3 总估时 3 天，单 session 串行更稳）。

**入口资产清单**（来自 ADR-H3 §3.6 受管资产 + Gate 0 实地盘点）：

| 资产类 | 文件路径 | 状态 |
|--------|----------|------|
| ADR | `docs/decisions/ADR-H3-memory-scope.md` | 已新增（前置 commit） |
| PLAN | 本文件 | 起草中 |
| user-level memory 主索引 | `~/.claude/projects/-Users-nature------Towow/memory/MEMORY.md` | 待重组（276 → ≤200） |
| user-level memory backup | `~/.claude/projects/-Users-nature------Towow/memory/_backup/MEMORY-pre-H3-{ts}.md` | 待新增 |
| user-level memory index | `~/.claude/projects/-Users-nature------Towow/memory/feedback_index.md` | 待新增（feedback_*.md 目录索引） |
| symptoms log | `.towow/log/harness-self-symptoms.md` | 待 append（如有） |
| reviewer 落点 | `docs/decisions/tasks/PLAN-H3/reviewer-verdict-{ts}.md` | 待新增 |

**不动**：ownership.yaml / SKILL.md / hook / inbox/proposals/state schema / 任何业务代码 / 224 个 topic-specific .md 文件（仅 MEMORY.md 主索引重组，其余文件 grep 引用）。

---

## 2. WP 拆解

### WP-01：MEMORY.md backup（H 系列灰度 §3.3.3 强制前置）

**目标**：MEMORY.md 重组前先备份到 `_backup/MEMORY-pre-H3-{ts}.md`，7 天观察期内任何反弹可一键回滚。

**操作**：
```bash
TS=$(date +%Y%m%dT%H%M)
mkdir -p ~/.claude/projects/-Users-nature------Towow/memory/_backup
cp ~/.claude/projects/-Users-nature------Towow/memory/MEMORY.md \
   ~/.claude/projects/-Users-nature------Towow/memory/_backup/MEMORY-pre-H3-${TS}.md
```

**DoD**：
- [ ] `_backup/MEMORY-pre-H3-*.md` 文件存在
- [ ] backup 行数 = 当前 MEMORY.md 行数（diff 验证一字未改）
- [ ] backup 文件 mtime ≥ 重组开始时刻

**估时**：5 min

**verify**：
```bash
ls -la ~/.claude/projects/-Users-nature------Towow/memory/_backup/MEMORY-pre-H3-*.md
diff ~/.claude/projects/-Users-nature------Towow/memory/MEMORY.md \
     ~/.claude/projects/-Users-nature------Towow/memory/_backup/MEMORY-pre-H3-*.md  # 此时应为空 diff
```

---

### WP-02：MEMORY.md 段长盘点 + 重组分组

**目标**：grep 现状段头 + 段长 + 计算"超 50 行"段数，输出重组分组清单。

**操作**：
1. 列所有 `## ` 段头 + 起始行号
2. 计算每段行数：相邻段头行号差
3. 标 `OVER_50` / `OK`
4. 按 ADR-H3 §3.2 重组规则把每个 `OVER_50` 段标"下沉到 X.md" / "拆分为 highlights + index"

**DoD**：
- [ ] 现状盘点文件落 `docs/decisions/tasks/PLAN-H3/wp02-current-segments.md`（grep 输出 + 段长统计）
- [ ] 重组分组清单覆盖所有 `OVER_50` 段，每段标"动作"（下沉 / 拆分 / highlights+index / 不动）
- [ ] 估算重组后行数 ≤ 200（meeting INV-H3-1）

**估时**：30 min

**verify**：
```bash
test -f docs/decisions/tasks/PLAN-H3/wp02-current-segments.md
grep -c "OVER_50" docs/decisions/tasks/PLAN-H3/wp02-current-segments.md  # 期望 ≥ 1
grep -c "动作:" docs/decisions/tasks/PLAN-H3/wp02-current-segments.md
```

---

### WP-03：5 条旧 memory highlights 挑选 + feedback_index.md 起草

**目标**：从现有"硬性要求"段（~60 项）中挑出**最高频引用**的 5 条作为主索引 highlights，其余下沉到新 `feedback_index.md`（每条 1 行 pointer + 1 行描述）。

**挑选规则**（ADR-H0.6 证据机械化）：
- 近 30 天 `git log --since=2026-03-29 -p` grep 命中频次最高的 5 条
- 命中频次相同时，优先 Nature 显式升级过的（含 "第 N 次升级" / "Nature 拍" 字样）
- 5 条 highlights 必须涵盖至少 3 个不同主题（不能 5 条全是 git 类）

**feedback_index.md 起草**：
```
# feedback_index.md — 完整教训目录索引

> 主索引 MEMORY.md 仅留 5 条 highlights；本文件是完整 ~60 项的目录指针。
> 每条 1 行 pointer + 1 行 hook，详细见各 topic-specific .md。

## 多 session / git race
- [并行 git race—commit 后必核 git show --stat](feedback_parallel_session_git_race_post_commit_verify.md) — race 升级版

## 部署与上线
- [生产 SSH 要白名单](feedback_prod_ssh_needs_allowlist.md) — verbal 不能穿透 sandbox
...
```

**DoD**：
- [ ] 5 条 highlights 挑选过程（grep 命令 + 命中数）落 `docs/decisions/tasks/PLAN-H3/wp03-highlights-selection.md`
- [ ] 5 条覆盖至少 3 个不同主题
- [ ] `feedback_index.md` 新增（user-level，路径 `~/.claude/projects/-Users-nature------Towow/memory/feedback_index.md`）
- [ ] feedback_index.md 行数 ≤ 100（防膨胀）；包含至少 30 条 pointer（覆盖现状大部分 feedback）

**估时**：1 h

**verify**：
```bash
test -f ~/.claude/projects/-Users-nature------Towow/memory/feedback_index.md
wc -l ~/.claude/projects/-Users-nature------Towow/memory/feedback_index.md  # ≤ 100
grep -cE "^- \[" ~/.claude/projects/-Users-nature------Towow/memory/feedback_index.md  # ≥ 30 pointers
test -f docs/decisions/tasks/PLAN-H3/wp03-highlights-selection.md
```

---

### WP-04：MEMORY.md 主索引重组实施

**目标**：按 WP-02 分组 + WP-03 highlights，实际重写 MEMORY.md，落到 ≤200 行 + 单段 ≤50 行。

**操作流程**：
1. 读 backup（防原文丢失）
2. 按 ADR-H3 §3.2 顶部固定（≤30 行）：身份说明 + 近期重要真相源 pointer（最多 8 条）
3. 硬性要求段：5 条 highlights + 1 行 pointer 到 feedback_index.md
4. 项目状态段：每段 ≤30 行；超 30 行下沉到对应 `project_<name>_state.md`
5. 生产环境 / Discovery / Crystallization 等技术清单段：每段 ≤30 行
6. 删除现状所有"Pending Reminder"中**已触发条件满足**的条目
7. 末尾 grep `^## ` 计数 + 行数验证

**DoD**：
- [ ] MEMORY.md 行数 ≤ 200（INV-H3-1）
- [ ] 单个 `## ` 段行数 ≤ 50（INV-H3-2，逐段 awk 验证）
- [ ] MEMORY.md 不含"待协调员决定" / "TBD" / "进行中 WP" 字样（INV-H3-3 + H0.4 自指禁止；元层定义命中除外）
- [ ] 顶部"近期重要真相源" pointer ≤ 8 条
- [ ] "硬性要求"段 = 5 条 highlights + 1 行 feedback_index.md pointer
- [ ] backup 仍存在（一键回滚保证）

**估时**：1 h

**verify**：
```bash
M=~/.claude/projects/-Users-nature------Towow/memory/MEMORY.md
wc -l "$M"  # ≤ 200
awk '/^## /{if(prev){print NR-prev_line, prev}; prev=$0; prev_line=NR} END{print NR-prev_line+1, prev}' "$M" | sort -rn | head -5
# 期望最长段 ≤ 50
grep -cE "TBD|后续讨论|待协调员决定|进行中 WP" "$M"
# 期望 0（INV-H3-3）
```

---

### WP-05：非起草 reviewer 复核（H0.3 执检分离）

**目标**：spawn 一个非起草 reviewer subagent（read-only frontmatter 物理隔离），复核 ADR-H3 + PLAN-H3 + WP-01..04 实施物。

**reviewer brief**（必含）：
- ADR-H3 / PLAN-H3 / ADR-H0 6+1 元规约 + INV-H3-1/2/3 验收清单
- 严格只读：不得 Edit/Write/commit；仅 grep/wc/awk/test
- 输出 PASS/FAIL + P0/P1/P2 finding 列表

**reviewer agent picks**：`pr-review-toolkit:code-reviewer`（外部插件 reviewer，prompt-level read-only directive 兜底；H2 已用，工作良好）

**DoD**：
- [ ] reviewer 复核完成 + 输出落 `docs/decisions/tasks/PLAN-H3/reviewer-verdict-{ts}.md`
- [ ] reviewer 裁决 PASS（如 FAIL 则按 P0/P1 修后再走一轮）
- [ ] H0.3 执检分离证据：reviewer agent 不是 ADR-H3/PLAN-H3 起草者

**估时**：30 min（含 reviewer 异步等待）

**verify**：
```bash
ls docs/decisions/tasks/PLAN-H3/reviewer-verdict-*.md 2>/dev/null | head -1
grep -E "verdict: (PASS|FAIL)" docs/decisions/tasks/PLAN-H3/reviewer-verdict-*.md
```

---

## 3. WP 顺序 + 总估时

```
WP-01 backup → WP-02 盘点 → WP-03 highlights+index → WP-04 重组 → WP-05 reviewer
   5 min       30 min        1 h                       1 h          30 min
```

**串行 + 单 session**。预计总耗时 ~3 h（含 reviewer 异步等待）。如某 WP 超期 50% 触发"H 系列自指症状"记录（H 系列 plan §3.5 节奏控制）。

---

## 4. 跨 H 协调（H0.5）

| 触点 | 冲突类型 | H3 处置 |
|------|---------|---------|
| MEMORY.md schema 结构 | 后续子计划同改风险 | H3 收口后 schema 定锚，后续子计划在新结构下写入条目（不重新分段） |
| `~/.claude/projects/.../memory/` 整目录 | user-level shared resource | 任何 H 子计划改 user-level memory 结构需先核 H3 是否收口 |
| ADR-042 D6 心跳契约 | memory vs inbox 边界声明 | H3 §3.5 已显式声明：memory ≠ 心跳通道；不动 ADR-042 D6 文本 |
| ADR-H9 §6.5 inbox/proposals 边界 | 三态完整图 | H3 §3.4 在 ADR-H9 基础上扩展为三态完整图；不动 ADR-H9 文本 |

---

## 5. ADR-H0 元规约自检

- **H0.1 施工隔离**：本 PLAN 操作路径全在 ADR-H3 §3.6 列出范围
- **H0.2 节流限速**：本 PLAN 目标 ≤ 500 行
- **H0.3 执检分离**：WP-05 reviewer 必为非起草 read-only subagent
- **H0.4 自指禁止**：H3 修"memory 噪声"，本 PLAN grep `TBD|后续讨论|待协调员决定` 仅元层定义命中（参 ADR-H0 §6 例 4）
- **H0.5 跨 H 协调**：见 §4
- **H0.6 证据机械化**：每个 WP 都给出 grep / wc / awk / test 命令

---

## 6. 反对意见

无新反对（ADR-H3 §4 已答辩 3 类反对，本 PLAN 不引入新决策点）。

---

## 7. 受影响外部相关

- `~/.claude/projects/-Users-nature------Towow/memory/MEMORY.md` 是 CC user-level memory 主入口，重组期间任何 session 启动会读到部分迁移状态——WP-01 backup 是回滚保证；WP-02 → WP-04 在同一 session 内连续完成（≤2 h 窗口），最小化跨 session 半态读取概率。
- 224 个 topic-specific `.md` 文件不动（仅 grep 引用），feedback_index.md 是新增 pointer 索引。
