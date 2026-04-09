---
name: guardian-fixer
description: 守夜人 issue 自动修复管道。8 Gate 全流程——规划、独立审查、开发、测试、闭环、PR。用于修复 docs/issues/guard-*.md 中 status:open 的 issue。
status: active
tier: execution
owner: nature
last_audited: 2026-03-24
triggers:
  - 修复 guardian issue
  - 执行 guard issue
  - 自动修复管道
outputs:
  - 独立 branch 上的 PR
  - 完整 Gate artifacts (PLAN/REVIEW/TASK/LOG/TEST/CLOSURE)
truth_policy:
  - issue 文档是唯一执行队列
  - 不从口头描述、memory、聊天记录直接开做
  - 代码真相以 repo 当前状态为准，不以 issue 描述为准
---

# 守夜人 Issue 自动修复

## 我是谁

我把 `docs/issues/guard-*.md`（status: open）变成可合并的 PR。我不发现 issue（那是巡逻的事），我只修复。

## 核心约束

1. **8 Gate 全走，一个都不能少。** 简单 issue 不是跳步的理由。
2. **审查是独立的。** Gate 2/4/7 必须 spawn 独立 subagent（opus），不是自己审自己。
3. **验证是诚实的。** 跑不了的测试标 BLOCKED，不标 PASS。"collect 通过" ≠ "测试通过"。
4. **写了代码必须运行。** 每个 WP 完成后必须有运行时证据（命令 + 输出），不是"看起来对"。

## 执行流程

### Step 0: 选 issue

```bash
# 找到优先级最高的可执行 issue
grep -rl 'status: open' docs/issues/guard-*.md | while read f; do
  sev=$(grep '^severity:' "$f" | sed 's/severity: *//')
  exec_st=$(grep '^execution_status:' "$f" | sed 's/execution_status: *//')
  # 跳过已有 execution_status 的（除了 pending）
  if [ -z "$exec_st" ] || [ "$exec_st" = "pending" ]; then
    echo "$sev|$f"
  fi
done | sort
```

选第一个（P0 > P1 > P2）。如果需要检查 zone 冲突，查 DESIGN 文档 Section 3.6 的 CODE_ZONES。

### Step 1: 建 worktree

```bash
ISSUE_SLUG="guard-YYYYMMDD-HHMM-slug"  # 从 issue 文件名提取
git worktree add /tmp/{{PROJECT_NAME}}-$ISSUE_SLUG -b codex/$ISSUE_SLUG main
mkdir -p /tmp/{{PROJECT_NAME}}-$ISSUE_SLUG/docs/decisions/tasks/GUARD-YYYYMMDD-HHMM
```

以下所有操作在 worktree 目录内进行。

### Step 2: Gate 1 — 规划

**输入**: issue 文档
**产物**: `PLAN.md`

PLAN.md 必须包含：

```markdown
# PLAN: guard-YYYYMMDD-HHMM — 标题

**Issue**: issue 文档路径
**Severity**: P0/P1/P2
**Component**: 主要代码文件

## 问题分析
（根因，不是症状）

## 变更清单
| # | 文件 | 变更 | 类型 |

## 契约 vs 实现分析
- 契约变更？消费方？

## 同类检查
（grep 验证是否有其他地方有同样的问题）

## 测试策略
（修改前/修改后的验证方法）

## Scope 判定
- ≤3 文件 + 无契约变更 → 可执行
- 否则 → needs_plan，停止
```

**Scope 硬上限**：
- 超过 3 个代码文件 → 标 `needs_plan`，停止
- API/schema/event 契约变更 → 标 `needs_plan`，停止
- 需要数据库 migration → 标 `needs_plan`，停止

### Step 3: Gate 2 — 独立审查 PLAN

**用 Agent tool spawn 独立审查者（opus 模型）。不是自己审自己。**

```
Agent tool:
  model: opus
  prompt: |
    你是独立代码审查者。你没有参与这段代码的编写。

    审查 PLAN 文档：[路径]
    对照 issue 文档：[路径]
    读相关代码文件。

    审查维度（全部覆盖）：
    1. 覆盖性：变更清单完整吗？
    2. 独立性：每个改动可独立验证吗？
    3. 执行模拟：逐步走，开发者会卡住吗？
    4. 自包含性：有执行所需全部信息吗？
    5. 元数据准确性：severity/component/scope 正确吗？
    6. 修复完整性：修复完整吗？有没有引入新问题？

    输出写入：[PLAN-REVIEW.md 路径]
    YAML frontmatter 必须有 verdict: PASS 或 FAIL。
```

**如果 FAIL**：修改 PLAN，重新提交审查（最多 2 轮）。2 轮不通过 → 标 `blocked`，停止。

### Step 4: Gate 3 — 任务拆解

**产物**: `TASK.md`

```markdown
# TASK: guard-YYYYMMDD-HHMM

## WP-N: 标题
**文件**: 路径
**改什么**: 具体描述
**验收标准**: 可机械验证的条件

## 验收测试
| # | 方法 | 预期结果 |
```

### Step 5: Gate 4 — 独立审查 TASK

同 Gate 2，spawn 独立审查者审查 TASK.md。

### Step 6: Gate 5 — 开发

**操作顺序**：

1. **先开 LOG.md**（实时写，不是事后补）
2. 逐个 WP 执行：
   a. 写代码
   b. **运行代码**（关键！不是"看起来对"就 commit）
   c. 记录运行命令和输出到 LOG.md
   d. 验证 TASK.md 中的验收标准
3. 更新 issue 文档状态（pre-commit hook 要求）
4. Commit（不 push）

**Worktree 里 Read/Edit 工具可能被 guard hook 阻塞**（pre-existing findings）。用 Bash 操作 worktree 文件：
- 读文件：`cat` / `tail`
- 写文件：`cat > file << 'EOF'` 或 `cat >> file << 'EOF'`
- 小修改：`sed -i ''`

**LOG.md 格式**：

```markdown
# LOG: guard-YYYYMMDD-HHMM

## WP-N: 标题
- 做了什么
- 运行命令 + 输出（证据）
- 偏差说明（如果有）

## 验收检查
| # | 方法 | 结果 |
```

### Step 7: Gate 6 — 测试

**运行所有能跑的测试**：

```bash
# 从 worktree 运行，用主仓库的 venv
VENV=<PROJECT_VENV>/bin/pytest

cd /tmp/{{PROJECT_NAME}}-$ISSUE_SLUG
$VENV -q backend/tests/unit/           # 无 Docker
$VENV -q backend/tests/field/          # 无 Docker
$VENV -q backend/tests/test_phase0_surface.py  # 无 Docker
$VENV -q backend/tests/product/        # 需要 Docker
$VENV -q backend/tests/matching/      # 无 Docker
```

**产物**: `TEST.md`

```markdown
# TEST: guard-YYYYMMDD-HHMM

## 测试执行结果

### 可运行测试
| 测试集 | 数量 | 结果 | 命令 |

### 需要 Docker 的测试
| 测试集 | 状态 | 原因 |

### 诚实声明
- 新代码有没有被测试覆盖？
- 是"旧测试通过"还是"新代码验证通过"？
- 有没有把 BLOCKED 标成 PASSED？
```

**诚实规则**：
- "collect 通过" ≠ "测试通过"
- "旧测试通过" ≠ "新代码验证通过"
- Docker 不可用 → 标 BLOCKED，不标 PASS
- 不虚构测试数量

### Step 8: Gate 7 — 最终审查

Spawn 独立审查者（opus）审查代码 diff + 测试结果。

```
Agent tool:
  model: opus
  prompt: |
    你是独立代码审查者（最终审查）。

    审查 git diff + TEST.md + LOG.md。
    检查代码是否与 PLAN 一致。
    检查有没有引入新问题。
    检查 TEST.md 是否诚实。

    输出写入：[FINAL-REVIEW.md 路径]
    verdict: PASS 或 FAIL。
```

### Step 9: Gate 7.5 — Closure

**产物**: `CLOSURE.md`

```markdown
# CLOSURE

## Issue 闭环状态
- status: fixed ✓/✗
- prevention_status: closed ✓/✗
- mechanism_layer: guard|test|type|convention ✓/✗

## 文档同步清单

### 必须更新
- [ ] issue 文档 status/prevention_status

### 可能需要更新（写进 PR 描述）
- [ ] CLAUDE.md 路由表（如果改了 API）
- [ ] 其他 issue 文档（如果修复也解决了其他问题）

### 不需要更新
- （列出检查过但不需要改的）
```

**禁止修改的文件**：
- CLAUDE.md（行为指令部分）
- AGENTS.md
- `.claude/skills/*/SKILL.md`
- `scripts/hooks/guard-feedback.py`
- `scripts/context_router.py`

### Step 10: Gate 8 — Push + PR

```bash
cd /tmp/{{PROJECT_NAME}}-$ISSUE_SLUG
git push -u origin codex/$ISSUE_SLUG
gh pr create --title "fix(...): guard-YYYYMMDD-HHMM 标题" --body "..."
```

PR 描述必须包含：
- Issue 路径
- 变更摘要
- 8 Gate 结果表
- 验证结果（诚实标注 PASS/BLOCKED）
- Artifacts 列表

## 异常处理

| 场景 | 操作 |
|------|------|
| Scope 超 3 文件 | Gate 1 标 `needs_plan`，停止 |
| 审查 2 轮不通过 | 标 `blocked`，停止 |
| 测试失败且无法修 | TEST.md 记录失败原因，标 `blocked`，停止 |
| 碰禁止修改的文件 | 停止 |
| Rebase 冲突 | 标 `needs_coordination`，停止 |

**所有异常路径都停止。不要强行继续。**

## 反模式清单

以下行为是明确禁止的（PLAN-064 教训）：

| 反模式 | 正确做法 |
|--------|---------|
| 写完代码不运行就 commit | 每个 WP 必须有运行时证据 |
| LOG.md 从 git log 生成 | LOG.md 在写代码时实时写 |
| 把 "199 tests PASS" 当验证 | 区分旧测试/新测试，标注新代码覆盖率 |
| 4 分钟完成一个 WP | 如果太快，说明没有运行验证 |
| 自己审自己 | Gate 2/4/7 必须 spawn 独立 subagent |
| Docker 不可用就跳过 | 标 BLOCKED，不标 PASS |

## Gate 检查清单

执行前自检——**如果正在写代码但 PLAN.md 不存在，立刻停下来。**

```
□ PLAN.md 存在？           → Gate 2 可以开始
□ PLAN-REVIEW.md verdict: PASS？ → Gate 3 可以开始
□ TASK.md 存在？           → Gate 4 可以开始
□ TASK-REVIEW.md verdict: PASS？ → Gate 5 可以开始
□ LOG.md 存在？            → Gate 6 可以开始
□ TEST.md 存在？           → Gate 7 可以开始
□ FINAL-REVIEW.md verdict: PASS？ → Gate 7.5 可以开始
□ CLOSURE.md 存在？        → Gate 8 可以开始
```
