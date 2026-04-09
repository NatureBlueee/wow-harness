# ADR-030: Guard Signal Protocol and Governance Reload

**Status**: Proposed
**Date**: 2026-03-22
**Revised**: 2026-03-22 (v6 — Part B governance reload 完整设计：上下文路由 + 上下文片段 + guard-feedback.py 双重机制)
**Origin**: PLAN-057 后续讨论 — 如何让 coherence guard 的思维范式永久存活

---

## 1. 问题

### 1.1 直接诱因：19 个审计发现

2026-03-21 的全局系统审计（`docs/reviews/global-system-audit-2026-03-21.md`）揭示了 19 个跨系统的问题，涵盖 P0（安全/正确性）到 P2（质量/规范）：

| 编号 | 级别 | 问题 | 类型 |
|------|------|------|------|
| 4.1 | P0 | 真相源导航断裂（MEMORY.md/INDEX.md 死链） | 真相漂移 |
| 4.2 | P0 | MCP 默认公网 HTTP 传输 bearer token | 承诺 vs 现实 |
| 4.3 | P0 | run_events 读模型截断导致长 run 状态不正确 | 共享结构过载 |
| 4.4 | P0 | /protocol/runs/{id}/prompt 双重 O(history) 扫描 | 共享结构过载 |
| 4.5 | P0 | 事件写入按 run 序列化（扩展瓶颈） | 共享结构过载 |
| 4.6 | P1 | BYOK base_url 从受控中继退化为任意 SSRF 面 | 承诺 vs 现实 |
| 4.7 | P1 | SecondMe 回调仍允许公网 HTTP origin | 承诺 vs 现实 |
| 4.8 | P1 | Node MCP 未收敛到 PLAN-051 auth surface | 多实现漂移 |
| 4.9 | P1 | smart-home-butler 承诺真实协议，跑 demo fallback | 承诺 vs 现实 |
| 4.10 | P1 | 网站暴露 startup-hub 路由解析为 null | 承诺 vs 现实 |
| 4.11 | P1 | Bridge admin stdout_chunk 信任模型弱于主事件路径 | 边界模糊 |
| 4.12 | P1 | Bridge 回归门禁文档说关了，实际标准调用失败 | 承诺 vs 现实 |
| 4.13 | P1 | Discovery 仍为全表扫描 + N+1 过滤 | 共享结构过载 |
| 4.14 | P1 | AgentWork Inbox 消费旧契约 | 多实现漂移 |
| 4.15 | P2 | MCP 本地配置文件为明文非原子密钥存储 | 真相漂移 |
| 4.16 | P2 | bridge_listen.py 在一条完成路径上伪装成功 | 承诺 vs 现实 |
| 4.17 | P2 | ENGINEERING_REFERENCE.md 过期但仍被当基线用 | 元层漂移 |
| 4.18 | P2 | 版本/部署/生成产物的真相碎片化 | 真相漂移 |
| 4.19 | P2 | 公开 Agent API 暴露稳定的 owner-identity 映射 | 边界模糊 |

### 1.2 病因分析：不是 19 个独立 bug

这 19 个 finding 聚成 5 个共同病因（审计 Section 7 的根因分析）：

1. **代码演化快，真相收敛慢**（7.1）— 代码改了但文档/测试/消费方没同步。多层真相源（代码、CLAUDE.md、MEMORY.md、INDEX.md、plans、.claude memory、部署现实）没有显式治理。
2. **目标态文档跑在实现前面**（7.2）— plan/ADR 写的是"已完成"语气，代码还在过渡态。场景文档说"真实协议"，跑的是 demo fallback。
3. **共享数据结构承担太多角色**（7.3）— `run_events` 同时是审计日志、重放历史、进度来源、轮次来源。一旦过载，每个消费方都从一个不完整的存储中推断语义。
4. **多实现产品缺乏主动一致性治理**（7.4）— Python MCP 和 Node MCP 不会"自动"保持一致。auth、config、版本号各自漂移。
5. **元层漂移是第一等风险**（7.5）— 过期的 skill/指南文档不只是"文档不准"——它会主动把未来的 AI 开发引向错误方向。

审计的核心结论：

> **Towow 的本地实现能力已经超过了系统级协调能力。核心问题不再是"能不能实现复杂功能"，而是"能不能维护一个关于'已经实现了什么'的一致的、可信的解释"。**

### 1.3 标和本

用户要求："既要能够解决我们目前遇到的几十个问题，又要是一套美的方式防止以后出现类似的问题，而且其本身也是可维护的。本质和实现我都要，标和本我都要治。"

- **治标**：PLAN-057 逐条修复 19 个 finding（已完成，19 WP + 672 测试）
- **治本**：本 ADR（ADR-030）建立机制，让这 5 类病因不再反复发作

### 1.4 为什么这些 bug 会反复出现

每一类病因的复发机制都相同：**AI 在改代码的那个瞬间，缺乏"这段代码在系统中的完整位置感"。**

- 改了 Python MCP auth 但不知道 Node MCP 是消费方 → 病因 4（多实现漂移）
- 改了 run_events 的读取逻辑但不知道 6 个消费方 → 病因 3（共享结构过载）
- 改了 scene 文档承诺但不知道运行时还是 fallback → 病因 2（承诺 vs 现实）
- 改了 CLAUDE.md 的版本号但不知道 pyproject.toml 也要改 → 病因 1（真相漂移）
- 改了 skill 文档但不知道旧版还在其他地方被引用 → 病因 5（元层漂移）

**共同根因**：AI 做决策时，相关的上下文不在它的窗口里。

这不是 prompt 问题（"告诉 AI 要注意消费方"），不是记忆问题（"让 AI 记住 Python/Node 是一对"），不是流程问题（"要求 AI 先查消费方再改代码"）。

这是**上下文工程问题**：在合适的时候，把合适的上下文投影到 AI 的工作窗口中。

### 1.5 核心问题的精确定义

> **如何让每一次代码变更都在完整的上下文下发生——AI 知道这个改动涉及哪些消费方、哪些约定、哪些承诺、哪些已知教训——从而在源头防止这 5 类病因反复出现？**

具体而言：
- 改 `mcp-server/towow_mcp/server.py` 时，AI 窗口里有 `mcp-server-node/` 的对应文件路径和 parity 约定
- 改 `backend/product/bridge/` 时，AI 窗口里有 Bridge 宪法 5 条规则
- 改 issue doc 标 Fixed 时，AI 窗口里有 "Fixed 三层"定义
- 改 scene 文档承诺时，AI 窗口里有该 scene 的实际 runtime fidelity 分级
- 改 `CLAUDE.md` 版本号时，AI 窗口里有所有版本号来源的清单
- 改契约（URL/schema/env var）时，AI 窗口里有消费方列表

这些上下文不靠 AI 自己想起来，不靠 skill 碰巧被加载，不靠人提醒。由代码确定性地路由和注入。

### 1.6 这本质是什么

> **这是上下文工程——在合适的时候给出合适的上下文，而不是 prompt。**

Prompt 是静态的、全量的、前置的指令。上下文工程是动态的、精准的、按需的知识投影。

区别：
- Prompt 把所有规则塞给 AI，希望它记住 → 注意力稀释，规模不可扩展
- 上下文工程检测 AI 正在做什么，投影此刻相关的知识 → 精准，可扩展，由代码控制

LLM 的工作方式是：上下文窗口里有什么，它就用什么来推理。上下文工程利用这个特性——把正确的输入放进窗口，让 transformer 自然产出正确的输出。不是"告诉 AI 应该怎么想"，而是"让 AI 的输入中包含它需要的知识"。

### 1.7 PLAN-057 的思维范式贡献（仍然重要）

PLAN-057 除了修复 19 个 finding，还沉淀了一套思维范式：

- "Fixed"有三层（runtime / prevention / mechanism），不是症状消失就算完
- Guard > Memory：如果一件事靠记忆维护，它一定会出错
- 一个事实只允许一个定义，其余自动派生或自动报警
- 验证看最后一公里，不是"服务启动了"就算过

这些思维范式是上下文工程要投影的**内容**之一。当 AI 改 issue doc 时，"Fixed 三层"框架应该出现在它的窗口里。当 AI 新增一个版本号时，"一个事实只允许一个定义"应该出现在它的窗口里。

**核心矛盾依然存在**：思维方式不能被机械执行（你不能写代码检测"AI 有没有想清楚"），但如果不机械化地把相关思维框架放进 AI 的窗口，它一定会蒸发。上下文工程是解决这个矛盾的机制。

## 2. 关键洞察

### 2.1 思维范式不是被"记住"的，是被"要求输出"的

你不能机械检测"有没有正确思考"，但你可以：

1. 定义"正确思考的产物长什么样"（Convention）
2. 写代码检查产物格式（Guard）
3. 检测到违反时，强制把 AI 拉回正确思维轨道（Signal → Governance Reload）

例：

| 思维规则 | 约定（机器可检查的输出） | Guard |
|---|---|---|
| Fixed 不等于症状消失 | issue.md frontmatter 必须包含 `prevention_status` 字段 | `check_issue_closure.py` |
| 改代码前要规划 | 代码变更必须伴随 issue/plan artifact | `check_artifact_link.py` |
| 一个事实只允许一个定义 | Python/Node MCP 工具名和行为必须一致 | `check_mcp_parity.py` |
| Guard > Memory | issue 标 Fixed 时必须指向 guard 或标 `not_applicable` | `check_issue_closure.py` |

Guard 不只是语法检查——**它是思维规则的可执行编码**。当 guard 拒绝接受缺少 `prevention_status` 的 issue doc 时，它在教每一个新会话：你必须思考 prevention。

### 2.2 这是上下文工程，不是 Prompt

19 个审计 finding 的共同根因：**AI 做决策时，相关上下文不在它的窗口里。**

- 改了 Python MCP 但不知道 Node MCP 是消费方（窗口里没有 parity 约定）
- 改了 run_events 读取逻辑但不知道 6 个消费方（窗口里没有消费方列表）
- 改了 scene 文档承诺但不知道运行时是 fallback（窗口里没有 fidelity 分级）

传统的解决方式是 prompt："把所有规则写进 CLAUDE.md / skill，让 AI 记住"。

问题：
- 规则太多 → 注意力稀释
- 静态全量 → 改 bridge 和改前端需要的知识完全不同，但 prompt 不区分
- Advisory → AI 读完可以不照做
- 上下文压缩 → 长会话后早期 prompt 被挤掉

**上下文工程是不同的路径**：检测 AI 正在做什么 → 用代码确定性地投影此刻相关的知识到窗口 → LLM 自然用它来推理。

这不是"告诉 AI 应该怎么想"（prompt），而是"让 AI 的输入中包含它需要的知识"（context engineering）。路由是代码控制的确定性操作，AI 不参与"要不要加载"的决策。

### 2.3 两部分的成熟度

| 部分 | 内容 | 成熟度 | 行业对标 |
|------|------|--------|---------|
| **Part A: Enforcement** | Convention + Guard + Signal + Blocking Gates | 设计完整，可用现成工具（pre-commit framework, GitHub Actions） | 任何大公司的 CI/CD |
| **Part B: Governance Reload** | 上下文路由 + 上下文片段 + 动态投影 | **本 ADR 的核心贡献**，设计见 Section 3.4.1 | AI 开发时代的新问题，无行业先例 |

Part A 治标（阻止错误产出进入代码库），Part B 治本（让 AI 在源头就用正确的知识做决策）。

## 3. 决策

### 3.1 架构总览

```
                  Towow Mechanism Stack
                  ═══════════════════

  ┌─────────────────────────────────────────────────┐
  │  Layer 1: Convention                            │
  │  定义"正确的产物长什么样"                        │
  │  载体: CLAUDE.md + docs/ + issue/plan 格式约定   │
  │  覆盖: 通用                                     │
  ├─────────────────────────────────────────────────┤
  │  Layer 2: Guard                                 │
  │  检查约定是否被遵守                              │
  │  载体: scripts/checks/*.py                      │
  │  覆盖: 通用（纯 Python，任何环境可跑）            │
  ├─────────────────────────────────────────────────┤
  │  Layer 3: Signal                                │
  │  把 guard 结果写入文件系统                        │
  │  载体: .towow/guard/session-{pid}.json          │
  │  覆盖: 通用（JSON 文件，任何工具/人可读）          │
  ├─────────────────────────────────────────────────┤
  │  Layer 4: Trigger                               │
  │  什么时候跑 guard                                │
  │  载体: git hooks + deploy.sh (通用)              │
  │         + Claude Code hooks (Claude-specific)    │
  ├─────────────────────────────────────────────────┤
  │  Layer 5: Governance Reload（上下文工程）         │
  │  在 AI 编辑代码时，动态投影相关思维框架到窗口      │
  │  两个机制：                                      │
  │    主动投影: 文件路径→上下文片段（每次编辑都做）   │
  │    被动重载: guard 报红→required_skills/reads     │
  │  载体: context-router.py + context-fragments/    │
  │  覆盖: Claude Code (native), Codex (adapter)    │
  ├─────────────────────────────────────────────────┤
  │  Layer 6: Blocking Gates                        │
  │  不允许带病通过                                  │
  │  载体: pre-commit + deploy.sh + remote CI       │
  │  覆盖: 通用（git hooks + shell + GitHub Actions）│
  └─────────────────────────────────────────────────┘
```

#### 3.1.1 Enforcement Plane vs Feedback Plane

Mechanism Stack 中的 6 层分属两个截然不同的平面：

```
  ╔══════════════════════════════════════════════════╗
  ║  FEEDBACK PLANE（反馈面）                        ║
  ║  目的: 让 AI/开发者在编辑时立刻知道问题            ║
  ║  特征: 不阻断操作，stderr 输出，advisory          ║
  ║  组件: PostToolUse hook, PreToolUse hook,        ║
  ║        session signal files, governance reload   ║
  ║  覆盖: Claude Code (native), Codex (via signal)  ║
  ╠══════════════════════════════════════════════════╣
  ║  ENFORCEMENT PLANE（强制面）                     ║
  ║  目的: 硬性阻止坏代码进入 repo/生产               ║
  ║  特征: exit ≠ 0 → 操作失败，不可绕过              ║
  ║  组件: pre-commit hook, deploy.sh,               ║
  ║        remote CI (GitHub Actions coherence)      ║
  ║  覆盖: 通用（任何 git client、任何 CI 平台）       ║
  ╚══════════════════════════════════════════════════╝
```

**关键裁决**：

1. **反馈面和强制面不能混淆**。PostToolUse 的 `exit 2` 是反馈（AI 收到信息但可以选择继续），不是阻断。真正的阻断只发生在 pre-commit、deploy、remote CI。
2. **反馈面的价值是速度**：AI 编辑文件后 1-2 秒内收到 signal，不需要等到 commit 时才发现问题。
3. **强制面的价值是不可绕过**：local pre-commit 可以被 `--no-verify` 跳过，deploy.sh 可以被绕过，但 remote CI 不能。Remote gate 是最终防线。
4. **两者互补而非替代**：反馈面减少到达强制面时的问题数量；强制面保证漏网的问题不能落地。

### 3.2 Guard Signal Protocol

Guard 运行后，每个进程写自己的 session 文件到 `.towow/guard/`：

```
.towow/guard/
  session-{pid}.json      # 每个进程独立写，不互相覆盖
  .session-notified-{pid} # SessionStart 通知标记（见 3.5）
```

单个 session 文件格式：

```json
{
  "timestamp": "2026-03-22T10:15:00Z",
  "pid": 12345,
  "stage": "post-edit | pre-commit | deploy",
  "trigger": "guard-feedback.py | pre-commit | deploy.sh",
  "findings": [
    {
      "severity": "P0 | P1 | P2",
      "blocking": true,
      "category": "closure_semantics | contract_drift | bridge_boundary | doc_integrity | version_drift | artifact_linkage | governance_bootstrap",
      "problem_class": "policy | contract | implementation",
      "message": "Issue 022 marked Fixed but prevention_status is open",
      "file": "docs/issues/022-bridge-node-missing-execution-files-2026-03-21.md",
      "line": 5,
      "required_skills": ["lead", "towow-ops"],
      "required_reads": [
        "docs/issues/022-bridge-node-missing-execution-files-2026-03-21.md"
      ]
    }
  ],
  "summary": {
    "p0": 0,
    "p1": 1,
    "p2": 0,
    "has_blocking": true,
    "required_skills": ["lead", "towow-ops"]
  }
}
```

**`severity` 与 `blocking` 是独立维度**：

| 概念 | 回答 | 值域 |
|------|------|------|
| `severity` | 问题有多严重 | P0 (安全/数据丢失), P1 (功能断裂), P2 (质量/规范) |
| `blocking` | 是否阻止 commit/deploy | true / false — 由 guard 按治理要求声明 |

一个 P2 的 closure 违规可能不那么"严重"，但它违反治理规则，所以 `blocking: true`。分离这两个维度是让 closure 体系真正可执行的关键。

**`category` 与 `problem_class` 是正交维度**：

| 字段 | 回答 | 用于 | 值域 |
|------|------|------|------|
| `category` | 发现了什么类型的问题 | skill 路由（见 3.4） | closure_semantics, contract_drift, bridge_boundary, doc_integrity, version_drift, artifact_linkage, governance_bootstrap |
| `problem_class` | 问题在哪个架构层 | 修复者决定修复策略 | policy, contract, implementation |

`required_skills` 从 `category` 派生，不从 `problem_class` 派生。`problem_class` 是给修复者的元信息——对应 R1 "先分层再动手"。

**多 session 读取**：

任何需要了解仓库 guard 状态的代码，通过 union 所有 session 文件获取：

```python
SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2}

def read_all_findings(guard_dir: Path, max_age_seconds: int = 3600) -> list[Finding]:
    raw = []
    now = time.time()
    for path in guard_dir.glob("session-*.json"):
        age = now - path.stat().st_mtime
        if age > max_age_seconds:
            path.unlink(missing_ok=True)  # 过期自动清理
            continue
        data = json.loads(path.read_text())
        raw.extend(data["findings"])
    return merge_findings(raw)

def merge_findings(findings: list[Finding]) -> list[Finding]:
    """Deterministic merge: same (file, category) → keep worst signal."""
    by_key: dict[tuple, dict] = {}
    for f in findings:
        key = (f["file"], f["category"])
        if key not in by_key:
            by_key[key] = dict(f)
        else:
            existing = by_key[key]
            # severity: keep worst (P0 > P1 > P2)
            if SEVERITY_RANK[f["severity"]] < SEVERITY_RANK[existing["severity"]]:
                existing["severity"] = f["severity"]
                existing["message"] = f["message"]
            # blocking: OR — if any session says blocking, it's blocking
            existing["blocking"] = existing["blocking"] or f["blocking"]
            # required_skills: union
            existing["required_skills"] = list(
                set(existing["required_skills"]) | set(f["required_skills"])
            )
    return list(by_key.values())
```

**合并规则（保守原则——取最严）**：

| 字段 | 合并策略 | 理由 |
|------|---------|------|
| `severity` | `max`（P0 > P1 > P2） | 两个 session 对同一问题评估不同，取最严防漏 |
| `blocking` | `OR` | 任一 session 认为应阻断 → 阻断 |
| `required_skills` | `union` | 所有相关 skill 都应被加载 |
| `message` | 取 severity 最高的 | 最严发现的描述最有信息量 |

**设计原则**：

- **每个 writer 只写自己的 scope，reader union 全部**：消除竞态，不需要锁或 merge-on-write
- **signal 不是日志**：session 文件只保留该 session 最新一次 guard 结果，超过 1 小时自动过期
- **required_skills 是建议**：AI 读到后应加载对应 skill，但 guard 本身不依赖 skill 是否被加载

### 3.3 Guard Router

文件路径到 guard 的映射，定义在 `scripts/guard_router.py`：

```python
GUARD_MAP = {
    # 业务代码
    "bridge_agent/":        ["check_bridge_deps"],
    "mcp-server/":          ["check_mcp_parity"],
    "mcp-server-node/":     ["check_mcp_parity"],
    "backend/":             ["check_versions"],
    "website/":             ["check_doc_links"],

    # 文档
    "docs/issues/":         ["check_issue_closure", "check_doc_links"],
    "docs/decisions/":      ["check_doc_links"],
    "docs/":                ["check_doc_links"],

    # 治理层（guard 保护 guard 自身）
    "CLAUDE.md":            ["check_doc_links"],
    ".claude/skills/":      ["check_doc_links"],
    ".claude/settings.json": ["check_hook_installed"],
    ".githooks/":           ["check_hook_installed"],
    "scripts/checks/":      ["check_versions"],
    "scripts/coherence.py": ["check_versions"],
    "scripts/guard_router.py": ["check_versions"],
    "scripts/context-router.py": ["check_fragment_integrity"],
    "scripts/context-fragments/": ["check_fragment_integrity"],
}

# 未映射路径的 fallback — 至少跑基础 guard
DEFAULT_GUARDS = ["check_doc_links"]
```

Guard 命名沿用 PLAN-057 已建立的规范（`check_versions` 而非 `check_version_drift`）。

**`check_fragment_integrity.py`** — guard 保护上下文片段自身不漂移（元层漂移的反漂移机制也需要被保护）：

```python
def run(repo_root: Path) -> list[Finding]:
    findings = []
    # 1. CONTEXT_MAP 引用的片段必须存在
    for name in all_referenced_fragments(repo_root):
        path = repo_root / "scripts" / "context-fragments" / f"{name}.md"
        if not path.exists():
            findings.append(Finding(severity="P1", category="governance_bootstrap",
                blocking=True, message=f"CONTEXT_MAP references fragment '{name}' but file missing"))

    # 2. 片段文件存在但未被任何路由引用 → stale warning
    for path in (repo_root / "scripts" / "context-fragments").glob("*.md"):
        name = path.stem
        if name not in all_referenced_fragments(repo_root):
            findings.append(Finding(severity="P2", category="doc_integrity",
                blocking=False, message=f"Fragment '{name}' exists but not referenced in CONTEXT_MAP"))

    return findings
```

新增 guard 只需：写 `scripts/checks/check_xxx.py`，在 `GUARD_MAP` 注册路由。

### 3.4 Category → Skill 映射

```python
CATEGORY_TO_SKILLS = {
    "closure_semantics":    ["lead", "towow-ops"],
    "contract_drift":       ["towow-dev", "towow-eng-test"],
    "bridge_boundary":      ["towow-bridge", "towow-ops"],
    "policy_freeze":        ["lead", "arch", "plan-lock"],
    "doc_integrity":        ["towow-ops"],
    "version_drift":        ["towow-ops"],
    "artifact_linkage":     ["lead"],
    "governance_bootstrap": ["towow-ops"],
}
```

当 guard 发现问题时，`required_skills` 由 `CATEGORY_TO_SKILLS[finding.category]` 生成。AI 收到信号后加载这些 skill 获取完整的思维框架，而不是盲目修。

### 3.4.1 Governance Reload 完整设计（Part B — 上下文工程）

> **这是 ADR-030 区别于标准 CI/CD 的核心贡献。**
>
> Enforcement plane（Part A）检查"产出对不对"——这是任何大公司都有的标准 CI。
> Governance Reload（Part B）解决"AI 做决策时窗口里有没有正确的知识"——这是 AI 开发时代的新问题。

#### 核心原理：上下文工程，不是 Prompt

```
Prompt 思路:    写一套静态规则 → 希望 AI 记住 → 检查有没有遵守
                问题: 规则太多注意力稀释, 新会话可能没加载, AI 可以读完不照做

上下文工程:     检测 AI 正在做什么 → 投影此刻相关的知识到窗口 → LLM 自然用它推理
                原理: Transformer 的工作方式就是用上下文中的信息来推理
                保障: 路由是代码（确定性），投影是脚本（自动），AI 不参与"要不要加载"的决策
```

#### 两个机制

Governance Reload 由两个独立的机制组成，通过同一条管道（PostToolUse → stderr → exit 2）送达，但使用不同的输出标记以区分语义：

```
AI 编辑文件
  │
  ├─→ 机制 A: 上下文路由（主动，每次编辑都做）
  │     输入: 被编辑的文件路径
  │     逻辑: context-router.py 匹配路由表
  │     输出: 相关的上下文片段（精炼的思维框架，10-25 行）
  │     目的: 让 AI 在做决策时，窗口里有此刻需要的知识
  │     举例: 改 bridge → 注入 Bridge 宪法 5 条规则
  │
  └─→ 机制 B: Guard 检查 + Signal（被动，有问题才报）
        输入: 被编辑的文件路径 + diff
        逻辑: guard-router → 相关 check_*.py
        输出: findings + required_skills + required_reads
        目的: 发现具体违规，指向需要补读的 skill/文档
        举例: issue 标 Fixed 但 prevention_status 缺失 → 报 P1 + 指向 lead skill
```

机制 A 是**主动的**——不管有没有问题都注入。改 bridge 代码时，Bridge 宪法出现在窗口里，AI 自然不会违反它。
机制 B 是**被动的**——只在发现问题时才报。这是 Section 3.2 已有的 signal 协议。

**两者的关系**：机制 A 减少错误产生（AI 在正确的上下文下做决策），机制 B 兜住漏网的（有些错误即使有上下文也会犯，guard 拦住）。

#### 上下文路由表（`scripts/context-router.py`）

```python
# 文件路径模式 → 上下文片段文件列表
CONTEXT_MAP: dict[str, list[str]] = {
    # Bridge
    "bridge_agent/":                    ["bridge-constitution"],
    "backend/product/bridge/":          ["bridge-constitution"],

    # MCP 双端
    "mcp-server/":                      ["mcp-parity"],
    "mcp-server-node/":                 ["mcp-parity"],

    # 协议 API（多消费方契约）
    "backend/product/routes/protocol.py": ["protocol-consumers", "contract-consumers"],
    "backend/product/protocol/":        ["protocol-consumers"],

    # API 路由层（契约定义点）
    "backend/product/routes/":          ["contract-consumers"],

    # run_events（6 个消费方的共享结构）
    "backend/product/db/crud_events.py": ["run-events-consumers"],

    # 认证（消费方安全约定 + SecondMe OAuth）
    "backend/product/auth/":            ["auth-consumers"],

    # DB 层（共享数据结构约定）
    "backend/product/db/":              ["db-shared-structures"],

    # 分布式协商核心
    "backend/product/catalyst/":        ["catalyst-distributed"],

    # Issue / 修复
    "docs/issues/":                     ["fixed-three-layers", "closure-checklist"],

    # 场景
    "scenes/":                          ["scene-fidelity", "two-language"],
    "website/app/[scene]/":             ["scene-fidelity", "two-language"],
    "website/components/scene/":        ["scene-fidelity", "two-language"],

    # 真相源文件
    "CLAUDE.md":                        ["truth-source-hierarchy"],
    "MEMORY.md":                        ["truth-source-hierarchy"],
    "docs/INDEX.md":                    ["truth-source-hierarchy"],

    # 版本号
    "mcp-server/pyproject.toml":        ["version-sources"],
    "mcp-server-node/package.json":     ["version-sources"],

    # 前端通用
    "website/":                         ["two-language"],

    # 文档
    "docs/decisions/":                  ["artifact-linkage"],
}

def match(file_path: str) -> list[str]:
    """返回匹配的上下文片段名列表。最长前缀优先。"""
    matched = []
    for pattern, fragments in sorted(CONTEXT_MAP.items(), key=lambda x: -len(x[0])):
        if file_path.startswith(pattern) or file_path.endswith(pattern):
            matched.extend(fragments)
    return list(dict.fromkeys(matched))  # 去重保序

# Fallback: 未匹配任何路由的文件，注入通用片段
FALLBACK_FRAGMENTS = ["general-dev-principles"]
```

路由表是确定性代码。新增一个领域 = 写一个片段文件 + 在路由表里加一条规则。

#### 上下文片段库（`scripts/context-fragments/`）

每个片段是一个精炼的 Markdown 文件，设计原则：
- **短**：10-25 行，一屏看完，不稀释 AI 注意力
- **自足**：不需要跳转到其他文档就能理解
- **面向当前操作**：不是"这个领域的全部知识"，而是"你正在改这个文件，这几件事必须知道"
- **可维护**：每个片段对应一个领域，独立更新

示例片段 — `scripts/context-fragments/bridge-constitution.md`：
```markdown
## Bridge 宪法（ADR-026）

你正在编辑 Bridge 相关代码。以下 5 条规则约束所有 bridge 改动：

1. **Worker 不拥有业务解释权，只上报执行事实。** 如果代码需要理解输出内容的含义，它写错了地方。
2. **同一个语义只允许有一个定义。** 文件名模式、artifact 类型、event 含义，只能在一个地方定义。
3. **跑通了就发结果，没跑通就报 failed。** 不做 partial_success 抢救、不生成 placeholder。
4. **生产不能是第一个集成环境。** 本地必须能用 fake CLI + 真实 HTTP backend 跑完整链。
5. **新增观测维度或 event 类型，只改 server，不改 worker。**

三层职责：`towow-run` 定义成功产物契约 → `worker` 执行和上报事实 → `server` 解释事实并生成产品语义。
```

示例片段 — `scripts/context-fragments/mcp-parity.md`：
```markdown
## MCP 双端一致性约定

你正在编辑 MCP 相关代码。Python 和 Node 两端必须保持一致：

- **工具数量**：两端都是 54 个 @mcp.tool() / registerTool()
- **工具名称**：必须完全相同（towow_xxx）
- **行为语义**：相同输入必须产生相同输出结构
- **版本号**：pyproject.toml 和 package.json 版本必须一致

对应文件映射：
- Python: `mcp-server/towow_mcp/server.py` ↔ Node: `mcp-server-node/src/index.ts`
- Python: `mcp-server/towow_mcp/client.py` ↔ Node: `mcp-server-node/src/client.ts`
- Python: `mcp-server/towow_mcp/config.py` ↔ Node: `mcp-server-node/src/config.ts`

改了一端后，检查另一端是否需要同步。Guard: `check_mcp_parity.py`
```

示例片段 — `scripts/context-fragments/fixed-three-layers.md`：
```markdown
## Fixed 三层定义

你正在编辑 issue 文档。"Fixed" 不等于"症状消失"：

| 层级 | 含义 | 标准 | 标记 |
|------|------|------|------|
| Level 1 | 症状消失 | 生产不报错了 | Runtime Fixed |
| Level 2 | 复发路径关闭 | 有机制防止同类问题再次发生 | **Fixed**（最低标准） |
| Level 3 | 机制消灭 | 有 guard 自动检测 | Fixed + Guarded |

issue doc frontmatter 必须包含：
- `prevention_status: open | closed | not_applicable`
- `mechanism_layer: runtime | prevention | guard`

如果标 Fixed 但 prevention_status 是 open → 不合格。Guard: `check_issue_closure.py`
```

片段清单（初始集，覆盖 19 个审计 finding 的 5 个病因 + 高频变更区域）：

| 片段文件 | 覆盖的病因 | 内容概要 |
|----------|-----------|----------|
| `bridge-constitution.md` | 边界模糊 | ADR-026 五条规则 + 三层职责 |
| `mcp-parity.md` | 多实现漂移 | 双端映射 + 同步约定 |
| `fixed-three-layers.md` | 真相漂移 | Fixed 定义 + frontmatter 要求 |
| `closure-checklist.md` | 真相漂移 | prevention_status 检查清单 |
| `protocol-consumers.md` | 多实现漂移 | /protocol/ API 的消费方列表 |
| `run-events-consumers.md` | 共享结构过载 | run_events 的 6 个消费方 + 角色 |
| `scene-fidelity.md` | 承诺 vs 现实 | scene 分级（real/demo/shell）|
| `two-language.md` | 承诺 vs 现实 | 协议语言 vs 用户语言 |
| `truth-source-hierarchy.md` | 元层漂移 | 真相源优先级 |
| `version-sources.md` | 真相漂移 | 所有版本号来源清单 |
| `artifact-linkage.md` | 真相漂移 | 代码变更必须伴随 artifact |
| `contract-consumers.md` | 多实现漂移 | 契约 vs 实现 + 消费方追踪 |
| `general-dev-principles.md` | 通用 | Guard > Memory + 一个事实一个定义 |
| `auth-consumers.md` | 多实现漂移 | SecondMe OAuth 消费方 + session 安全约定 |
| `db-shared-structures.md` | 共享结构过载 | DB 表的多消费方声明 + 迁移约定 |
| `catalyst-distributed.md` | 边界模糊 | 分布式协商约定 + 端侧 vs 平台侧职责 |

**扩展原则**：这是初始集，不是完整集。当某个代码区域反复出现同类错误时，应为其创建上下文片段并加入路由表。判断标准：如果 AI 在编辑该区域时"应该知道但反复不知道"某条规则，就需要一个片段。

#### `guard-feedback.py` — PostToolUse 枢纽脚本

`guard-feedback.py` 是 Governance Reload 的实际执行入口。它同时承担上下文路由和 guard 检查两个职责：

```python
#!/usr/bin/env python3
"""PostToolUse hook target — 上下文路由 + 增量 guard"""
import sys
import os

from context_router import match, load_fragment, FALLBACK_FRAGMENTS
from guard_router import GUARD_MAP, run_guards
from signal_writer import write_session_signal

def main():
    file_path = os.environ.get("TOOL_FILE_PATH", "")
    if not file_path:
        return

    # 相对于 repo root
    repo_root = os.environ.get("REPO_ROOT", ".")
    rel_path = os.path.relpath(file_path, repo_root)

    output_parts = []

    # ── 机制 A: 上下文路由（主动，每次都做）──
    # 输出标记: "## Context" — AI 应将其作为背景知识用于后续推理
    fragments = match(rel_path) or FALLBACK_FRAGMENTS
    context_parts = []
    for name in fragments:
        content = load_fragment(name)
        if content:
            context_parts.append(content)
    if context_parts:
        output_parts.append("## Context\n\n" + "\n\n".join(context_parts))

    # ── 机制 B: Guard 检查（被动，有问题才报）──
    # 输出标记: "## Guard Findings" — AI 应视为需要立即处理的问题
    findings = run_guards(rel_path)
    if findings:
        output_parts.append(format_findings(findings))
        write_session_signal(findings)

    # 有内容就输出到 stderr + exit 2
    if output_parts:
        print("\n---\n".join(output_parts), file=sys.stderr)
        sys.exit(2)

def format_findings(findings):
    lines = ["## Guard Findings\n"]
    for f in findings:
        lines.append(f"- **{f['severity']}** [{f['category']}]: {f['message']}")
        if f.get("required_skills"):
            lines.append(f"  → 建议加载: {', '.join(f['required_skills'])}")
        if f.get("required_reads"):
            lines.append(f"  → 建议参考: {', '.join(f['required_reads'])}")
    return "\n".join(lines)

if __name__ == "__main__":
    main()
```

#### Claude Code Hook 配置

```json
// .claude/settings.json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "python3 scripts/guard-feedback.py"
      }
    ]
  }
}
```

Claude Code 在 AI 每次调用 Edit 或 Write 工具后自动执行 `guard-feedback.py`。脚本输出到 stderr + exit 2，内容被 Claude Code 注入 AI 的对话上下文。AI 的下一步推理，窗口里已经有了相关的思维框架。

#### Codex Adapter

Codex 没有原生 PostToolUse hook。实现同等效果的路径（按优先级）：

1. **Codex task wrapper**：在 Codex task 启动脚本中注入 `guard-feedback.py` 调用
2. **Filesystem watcher**：监听工作目录文件变更，变更后调用 `guard-feedback.py`，输出写入 `.towow/guard/session-*.json`，Codex 读取
3. **Pre-task 注入**：在 Codex task description 中包含"先运行 `python3 scripts/guard-feedback.py --file {file}`"的指令

无论哪条路径，核心脚本相同（`scripts/guard-feedback.py`），差异只在触发方式。

**诚实声明**：以上三条路径均为候选，尚未验证 Codex 实际支持哪一条。Phase 2 开始时必须先做 Codex 能力调研（支持哪些 hook/plugin/watcher 机制），确定可行路径后再实现。如果 Codex 当前不支持任何主动推送机制，则在 Phase 2 完成标准中标注"待 Codex 支持后交付"，并持续跟踪 Codex 新功能。**不接受**静默降级为"Codex 被动可读"。

#### 与 Enforcement Plane 的关系

```
Governance Reload（Layer 5）              Enforcement（Layer 6）
────────────────────────────              ──────────────────────
时机: 编辑时（即时，1-2 秒）                时机: 提交/合并/部署时
目的: 让 AI 在正确的上下文下做决策           目的: 阻止错误产出进入代码库
方式: 投影相关知识到 AI 窗口                方式: 检查产物格式 + exit ≠ 0
效果: 从源头减少错误产生                    效果: 兜底拦住漏网的
依赖: Claude Code hooks / Codex adapter   依赖: git hooks / GitHub Actions（通用）
```

两层独立运作，互补而非替代：
- Governance Reload 只要有效运作，到达 Enforcement 时的问题数量大幅减少
- 即使 Governance Reload 完全失效（hook 没装、Codex 没 adapter），Enforcement 仍然拦住所有 blocking 问题

#### 可维护性

新增一个领域的治理：
1. 写一个上下文片段文件 `scripts/context-fragments/xxx.md`（10-25 行）
2. 在 `CONTEXT_MAP` 里加一条路由规则
3. （可选）写一个 `scripts/checks/check_xxx.py` guard
4. （可选）在 `CATEGORY_TO_SKILLS` 里加一条映射

删除一个过时的治理：
1. 删除片段文件
2. 从 `CONTEXT_MAP` 移除路由
3. 下次 guard 跑不到就自然失效

这满足用户要求 #1（显式强调——机制入口在每次 Edit 后自动触发）和"其本身也是可维护的"。

### 3.5 触发点

| 触发点 | 机制 | Guard 范围 | 平面 | 阻断判定 | 覆盖 |
|--------|------|-----------|------|---------|------|
| **Session-start** | Claude Code `PreToolUse` hook (first `Read` only) | 不跑新 guard，只读现有 session 文件 | Feedback | Advisory（stderr 输出） | Claude Code |
| **Post-edit** | Claude Code `PostToolUse` hook | 增量（改动文件相关 guard） | Feedback | Advisory（stderr + exit 2） | Claude Code |
| **Pre-commit** | `.githooks/pre-commit` | `--staged-only` + `check_artifact_link` (presence) | Enforcement | **Hard — 拦 `blocking: true`** | 通用 |
| **Commit-msg** | `.githooks/commit-msg` | `check_bugfix_binding`（message + staged files） | Enforcement | **Hard — 拦 bugfix 无 issue doc** | 通用 |
| **Deploy** | `deploy.sh` | 全量 | Enforcement | **Hard — 拦 P0** | 通用 |
| **Remote CI** | GitHub Actions `coherence.yml` (required check) | 全量 + bugfix binding | Enforcement | **Hard — PR 不过不能 merge** | 通用（不可绕过） |

**阻断逻辑**：

```python
def should_block(findings: list[Finding], stage: str) -> bool:
    if stage == "deploy":
        # 设计决策：deploy 只拦 P0（安全/数据完整性），不拦治理违规。
        # 理由：治理违规（blocking=true 但 severity=P1）已被 pre-commit 和
        # remote CI 拦住；deploy 是最后防线，只关注"部署了会出事"的问题。
        # 治理问题在 commit/merge 阶段已经关闭，不需要 deploy 重复检查。
        return any(f["severity"] == "P0" for f in findings)
    if stage in ("pre-commit", "commit-msg", "remote-ci"):
        return any(f["blocking"] for f in findings)    # ← 看 blocking 字段
    return False  # post-edit 和 session-start 是 feedback plane，不阻断
```

**Post-edit 信号闭环**：

```
AI 编辑文件
  → PostToolUse hook 触发 guard-feedback.py
  → guard-feedback.py 通过 guard router 跑相关 guard
  → 写 .towow/guard/session-{pid}.json
  → 如果有 finding：stderr 输出摘要 + exit 2
  → AI 收到 stderr 反馈
  → 反馈中包含 required_skills
  → AI 加载对应 skill，获取完整思维上下文
  → 带着正确思维框架去修问题
```

**Session-start 早期感知**：

```
新 session 打开
  → AI 首次使用 Read 工具
  → PreToolUse hook 触发 guard-feedback.py --check-only --once
  → 读 .towow/guard/ 下所有 session 文件（不跑新 guard）
  → 如果有 blocking finding：stderr 输出摘要
  → 写 .towow/guard/.session-notified-{pid} 标记，同一 session 不重复通知
  → AI 知道 repo 当前有 blocking 问题，优先处理
```

Session-start 触发是 advisory，不是硬阻断。其价值是减少浪费（避免在已有 blocker 时做无效规划），不是防止错误（那是 pre-commit/deploy 的事）。

### 3.6 Closure Semantics

#### Issue 文档格式（Convention）

`docs/issues/*.md` 必须使用 YAML frontmatter：

```markdown
---
title: Bridge node missing execution files
date: 2026-03-21
status: Fixed
prevention_status: closed
guard_status: exists
problem_class: contract
guard_ref: check_bridge_deps
---

## 问题描述
...
```

字段定义：

| 字段 | 必填 | 值域 | 含义 |
|------|------|------|------|
| `title` | 是 | 自由文本 | 问题标题 |
| `date` | 是 | YYYY-MM-DD | 发现日期 |
| `status` | 是 | Open, Runtime-Fixed, Fixed, Fixed+Guarded | 当前状态 |
| `prevention_status` | 是 | open, closed, not_applicable | 预防机制是否存在 |
| `guard_status` | 是 | missing, exists, not_applicable | 自动化检测是否存在 |
| `problem_class` | 是 | policy, contract, implementation | 问题所在的架构层 |
| `guard_ref` | 条件 | guard 脚本名 | `guard_status=exists` 时必填 |
| `scope` | 推荐 | 代码目录列表 | 受影响的代码路径（用于 artifact linkage scope binding，见 3.9） |

#### Status 语义（新增到 CLAUDE.md）

```
- Runtime-Fixed: 现网症状已消除，生产验证通过。
  复发路径尚未关闭。
- Fixed: 预防机制已存在于 repo 中
  (runbook step / guard / automation)。
  同一失败模式不能通过同一路径再次发生。
- Fixed+Guarded: 自动化检测已存在于
  scripts/checks/。未来回归会被 coherence runner 捕获。
```

#### Guard 解析

`check_issue_closure.py` 使用 YAML frontmatter 解析，不做 prose scraping：

```python
def parse_issue_frontmatter(path: Path) -> dict | None:
    text = path.read_text()
    if not text.startswith("---"):
        return None  # 缺少 frontmatter → 直接报 finding
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return yaml.safe_load(parts[1])
```

### 3.7 Multi-session Coordination

4-5 个并行上下文窗口的协调通过 per-session 文件实现：

```
              .towow/guard/
    ┌──────────────────────────────────┐
    │  session-1234.json  (Session A)  │
    │  session-5678.json  (Session B)  │
    │  session-9012.json  (Session C)  │
    └──────────────────────────────────┘
                    │
          ┌─────────┼─────────┐
          │ reads   │ reads   │ reads
          │ all     │ all     │ all
          ▼         ▼         ▼
      Session A  Session B  Session C
```

**为什么不用单个 `latest.json`**：

Session A 发现 P1 → 写入 latest.json → Session B 运行 guard 无发现 → 覆写 latest.json → Session A 的 P1 消失 → 假绿。

Per-session 文件消除竞态：每个进程只写自己的文件，不碰别人的。读的时候 union 所有文件。文件系统是天然的无锁共享层。

过期清理（> 1 小时）防止死 session 残留累积。

### 3.8 Bootstrap Protocol

Git 不会自动执行 repo 中的 hook 文件。`.githooks/pre-commit` 和 `.githooks/commit-msg` checked into repo 不等于它们会被执行。

**`check_hook_installed.py`** — 用 guard 保障 guard 基础设施本身：

```python
def run(repo_root: Path) -> list[Finding]:
    result = subprocess.run(
        ["git", "config", "core.hooksPath"],
        capture_output=True, text=True, cwd=repo_root
    )
    hooks_path = result.stdout.strip()
    if hooks_path == ".githooks":
        return []

    legacy_hook = repo_root / ".git" / "hooks" / "pre-commit"
    if legacy_hook.is_symlink() and ".githooks" in str(legacy_hook.resolve()):
        return []

    return [Finding(
        severity="P0",
        category="governance_bootstrap",
        blocking=True,
        message="Pre-commit hook not active. Run: git config core.hooksPath .githooks",
        required_skills=["towow-ops"],
    )]
```

**自举链**：

```
Claude Code 启动
  → 加载 .claude/settings.json（Claude Code 自动行为，不需手动）
  → PostToolUse hook 配置指向 guard-feedback.py
  → AI 首次编辑文件 → guard-feedback.py 跑
  → check_hook_installed 发现 git hook 未安装 → P0 blocking
  → AI 收到 stderr 反馈 → 执行 git config core.hooksPath .githooks
  → 此后所有 commit 经过 pre-commit hook
```

**非 Claude Code 环境**：手动 git commit 时如果 hook 未安装，deploy.sh 全量 coherence 会拦住。hook 未安装的代码可以 commit，但无法部署。

### 3.9 Artifact Linkage

**问题**：`check_issue_closure.py` 只在 issue 文件被 staged 时检查合规性。如果开发者只改代码不碰 issue doc，guard 根本不触发。

Artifact linkage 分两个阶段实现，当前阶段和增强阶段解决不同层次的问题：

#### Phase 3: Presence Gate（当前）

强制代码变更伴随**某个** issue/plan artifact。打破"纯代码提交零文档"的模式。

**`check_artifact_link.py`**：

```python
CODE_DIRS = {"backend/", "bridge_agent/", "mcp-server/", "mcp-server-node/", "website/"}
ARTIFACT_PREFIXES = {"docs/issues/", "docs/decisions/PLAN-", "docs/decisions/ADR-"}

def run(staged_files: list[str]) -> list[Finding]:
    code_files = [f for f in staged_files if any(f.startswith(d) for d in CODE_DIRS)]
    if not code_files:
        return []

    # 豁免：纯测试变更
    if all("test" in f.lower() for f in code_files):
        return []

    has_artifact = any(any(f.startswith(p) for p in ARTIFACT_PREFIXES) for f in staged_files)
    if not has_artifact:
        return [Finding(
            severity="P1",
            category="artifact_linkage",
            blocking=True,
            message="Code changes staged without an associated issue/plan document.",
            required_skills=["lead"],
        )]
    return []
```

**诚实的局限**：presence gate 只检查"有没有 artifact 陪跑"，不检查"是不是正确的 artifact"。开发者可以 stage 一个不相关的旧 issue doc 来满足门禁。这是 Phase 3 的已知 tradeoff：它消除了最常见的失败模式（纯代码提交），但不能防止刻意绕过。

#### Phase 4+: Scope Binding（增强）

Issue/plan frontmatter 的 `scope` 字段声明受影响的代码路径。Guard 验证 staged 代码路径与 artifact 声明的 scope 匹配。

Issue frontmatter 示例：

```yaml
---
title: Bridge node missing execution files
date: 2026-03-21
status: Fixed
prevention_status: closed
guard_status: exists
problem_class: contract
guard_ref: check_bridge_deps
scope:
  - bridge_agent/
  - backend/product/bridge/
---
```

增强后的 `check_artifact_link.py`：

```python
def run_with_scope(staged_files: list[str]) -> list[Finding]:
    # ... presence check (same as Phase 3) ...

    # Scope binding: artifact 的 scope 必须覆盖 staged 代码路径
    artifact_files = [f for f in staged_files if any(f.startswith(p) for p in ARTIFACT_PREFIXES)]
    declared_scopes = set()
    for af in artifact_files:
        fm = parse_frontmatter(Path(af))
        if fm and "scope" in fm:
            declared_scopes.update(fm["scope"])

    unlinked = [f for f in code_files if not any(f.startswith(s) for s in declared_scopes)]
    if unlinked:
        return [Finding(
            severity="P1",
            category="artifact_linkage",
            blocking=True,
            message=f"Code files {unlinked[:3]} not covered by any staged artifact's scope.",
            required_skills=["lead"],
        )]
    return []
```

**Phase 4+ 不在本 ADR 的初始实现范围内**，但 `scope` 字段现在就定义到 frontmatter 规范中（见 3.6），为增强预留接口。Phase 3 的 presence gate 是可接受的起步。

#### Closure 链路（Phase 3 → Phase 4 渐进）

两种 artifact 走不同的 closure 路径——不能假装 PLAN/ADR 会触发 closure 检查：

```
Phase 3 — presence gate:
  代码变更 → check_artifact_link 要求伴随某个 artifact（pre-commit）

  路径 A（issue doc staged）:
    → check_issue_closure 检查 YAML frontmatter
    → 必须包含 prevention_status + guard_status
    → 违反 → blocking: true → pre-commit 拦住
    → ✅ 完整 closure 链路

  路径 B（PLAN/ADR staged）:
    → presence gate 通过
    → ⚠️ 无 closure 检查 — PLAN/ADR 没有 prevention_status 字段
    → 对功能开发足够，对 bugfix 不够

Phase 4 — bugfix binding + scope binding:
  commit-msg hook:
    → commit message 含 fix/bugfix/hotfix/incident
    → 必须走路径 A（强制 issue doc）
    → ✅ bugfix closure 链路关闭

  scope binding:
    → artifact frontmatter 的 scope 必须覆盖 staged 代码路径
    → 不相关的 artifact 不再被接受
```

Phase 3 路径 B 的缺口是已知的过渡状态。Phase 4 通过 `commit-msg` hook 和 scope binding 关闭。

这是 lead 流程 Gate 1（规划 → 产物: PLAN 文档）的机械化。

### 3.10 Tool Scope and Non-Claude Fallback

本 ADR 的覆盖范围对不同层有不同承诺：

| 层 | 覆盖范围 | 非 Claude 环境行为 |
|----|---------|-------------------|
| Convention (L1) | 通用 | CLAUDE.md、issue frontmatter 格式对任何开发者/工具可见 |
| Guard (L2) | 通用 | 纯 Python 脚本，`python3 scripts/coherence.py` 任何环境可跑 |
| Signal (L3) | 通用 | JSON 文件，人或任何工具可读可解析 |
| Trigger - hard (L4) | 通用 | `pre-commit` + `deploy.sh` 只依赖 git + shell |
| Trigger - advisory (L4) | Claude Code native, Codex adapter-based | Claude Code: PostToolUse/PreToolUse; Codex: adapter/watcher 主动推送 |
| Governance Reload (L5) | Claude Code native, Codex adapter-based; both active | 两者都必须有即时本地反馈，触发方式不同但效果相同 |
| Blocking Gates (L6) | 通用 | git hooks + shell |

**各环境覆盖矩阵**：

| 环境 | Feedback Plane | Enforcement Local | Enforcement Remote |
|------|---------------|-------------------|-------------------|
| **Claude Code** | native hooks（PostToolUse/PreToolUse）→ 即时 advisory | pre-commit + commit-msg | required status check |
| **Codex** | adapter/watcher 主动推送（调用同一套 `scripts/`）→ 即时 advisory | pre-commit + commit-msg | required status check |
| **手动开发** | `python3 scripts/coherence.py`（手动运行） | pre-commit + commit-msg | required status check |
| **CI/CD** | N/A | N/A | `coherence.py --json --exit-on-blocking` |

**Codex adapter 策略**：

Codex 当前没有原生 PostToolUse 等 hook 机制。本 ADR 对 Codex 的承诺（不可降级为"被动可读"）：
- **Enforcement plane 完全覆盖**：pre-commit + commit-msg + remote CI 与 Claude Code 完全相同
- **Feedback plane 主动推送**：通过 adapter/watcher/wrapper 机制，在代码变更后主动调用 `scripts/guard-feedback.py` 并将结果推送给 Codex。用户原话："脚本检测到东西之后，是可以提醒系统 ai 的"，"我们一定要接受"。具体实现路径：
  - 如果 Codex 支持 hook/plugin → 直接接入 `guard-feedback.py`
  - 如果 Codex 支持 filesystem watcher → `.towow/guard/session-*.json` 变更触发读取
  - 如果 Codex 支持 task wrapper → 在 task 启动脚本中注入 guard 调用
  - 无论哪条路径，最终效果必须是"编辑后信号主动到达 Codex"，不是"Codex 碰巧去读"
- **共用脚本**：所有环境调用同一套 `scripts/` 脚本，差异只在触发方式

**设计原则**：enforcement 通用（任何环境都拦住坏代码），feedback 主动到达（不是被动等读取），信号协议工具无关（为未来适配留接口）。

### 3.11 Remote Gate（最终防线）

Local pre-commit 可以被 `--no-verify` 绕过。Deploy.sh 只在部署时触发。Remote gate 是唯一不可被本地操作绕过的硬保证。

**关键约束**：GitHub Actions workflow on `push` 是**事后报警**——push 已经落地了。要做到"不可绕过"，workflow 必须是 merge 的**前置条件**，不是事后审计。

**GitHub 仓库配置（Enforcement 基础设施）**：

| 设置 | 值 | 理由 |
|------|-----|------|
| `main` branch protection | 启用 | 所有 enforcement 的前提 |
| Require pull request before merging | 是 | 禁止 direct push to main |
| Required status checks | `coherence-gate` | PR 不过 check 不能 merge |
| Require branches to be up to date | 是 | 防止 merge 时状态过期 |

**`.github/workflows/coherence.yml`**：

```yaml
name: Coherence Gate
on:
  pull_request:
    branches: [main]

jobs:
  coherence-gate:    # ← 这个 job name 是 required status check 的 ID
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Run coherence checks
        run: python3 scripts/coherence.py --json --exit-on-blocking
      - name: Check artifact linkage
        run: |
          # 解析 PR 所有 commit messages，验证 bugfix 绑定
          git log --format='%s' origin/main..HEAD | python3 scripts/checks/check_bugfix_binding_ci.py
      - name: Verify hook infrastructure
        run: |
          test -f .githooks/pre-commit || (echo "::error::pre-commit hook missing from repo" && exit 1)
          test -f .githooks/commit-msg || (echo "::error::commit-msg hook missing from repo" && exit 1)
```

**为什么触发是 `pull_request` 而不是 `push`**：

- `on: push` → push 已经落地，workflow 失败只是报警
- `on: pull_request` + required status check → workflow 是 merge 的前置条件，不通过就不能 merge
- 这才是真正的"不可绕过"

**三层防线总结**：

```
编辑时 → Feedback Plane → AI 立即知道问题（PostToolUse）
提交时 → Enforcement Local → pre-commit + commit-msg 拦住 blocking findings
合并时 → Enforcement Remote → GitHub Actions required check 阻止 merge
部署时 → Enforcement Deploy → deploy.sh 拦住 P0
```

本地 hook 未安装 + `--no-verify` 跳过的情况下，代码可以 commit + push 到 feature branch，但 **PR 到 main 时会被 required status check 拦住**。不合规代码无法进入主线。

### 3.12 Bugfix/Incident 必须绑定 Issue

**问题（F13）**：Artifact linkage（3.9）的 Phase 3 presence gate 接受 PLAN/ADR 作为 artifact。但 PLAN 和 ADR 不触发 `check_issue_closure` — 它们没有 `prevention_status`、`guard_status` 等 closure 字段。功能开发伴随 PLAN 是合理的，但 bugfix/incident 修复**必须**绑定到 `docs/issues/` 下的 issue doc，否则 closure 链路断裂。

**裁决**：

| 变更类型 | 要求的 artifact | Closure 链路 |
|---------|----------------|-------------|
| 功能开发 | PLAN 或 ADR（`docs/decisions/PLAN-*`, `docs/decisions/ADR-*`） | presence gate 足够 — PLAN 有自己的 Gate 体系 |
| Bugfix / Incident | Issue doc（`docs/issues/*.md`） | 必须走 closure：frontmatter 含 `prevention_status` + `guard_status` |
| Refactor / Chore | PLAN 或 ADR | presence gate 足够 |

`check_artifact_link.py`（pre-commit 阶段）不区分变更类型——它只要求"有 artifact 伴随"。Bugfix 区分通过 **`commit-msg` hook** 实现，因为 pre-commit 阶段没有 commit message。

**触发时机选择**：

| 阶段 | 有 commit message? | 有 staged files? | 可以阻止 commit? |
|------|-------------------|-------------------|------------------|
| `pre-commit` | 没有 | 有 | 是 |
| `commit-msg` | **有** | **有**（`git diff --cached` 仍然有效） | **是** |
| remote CI | 有（解析 commit range） | 有（diff） | 是（阻止 merge） |

`commit-msg` 是唯一能在本地同时拿到 message + staged files 的时机。

**`.githooks/commit-msg`**（本地 enforcement）：

```bash
#!/bin/sh
python3 scripts/checks/check_bugfix_binding.py "$1"
```

**`scripts/checks/check_bugfix_binding.py`**（本地 + CI 共用逻辑）：

```python
import re, subprocess, sys
from pathlib import Path

FIX_PATTERNS = re.compile(r"\b(fix|bugfix|hotfix|incident)\b", re.IGNORECASE)

def check_local(commit_msg_file: str) -> list[Finding]:
    """commit-msg hook 调用：读 commit message 文件 + git diff --cached。"""
    msg = Path(commit_msg_file).read_text()
    if not FIX_PATTERNS.search(msg):
        return []

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True
    )
    staged = result.stdout.strip().splitlines()
    return _check(staged)

def check_ci(commit_messages: list[str], changed_files: list[str]) -> list[Finding]:
    """Remote CI 调用：解析 PR commit range。"""
    has_fix = any(FIX_PATTERNS.search(msg) for msg in commit_messages)
    if not has_fix:
        return []
    return _check(changed_files)

def _check(files: list[str]) -> list[Finding]:
    has_issue = any(f.startswith("docs/issues/") for f in files)
    if has_issue:
        return []
    return [Finding(
        severity="P1",
        category="artifact_linkage",
        blocking=True,
        message="Bugfix/incident commit must include a docs/issues/ document with closure frontmatter.",
        required_skills=["lead", "towow-ops"],
    )]
```

**三阶段验证**：

```
pre-commit:  presence gate — 任何 artifact（issue/PLAN/ADR）
commit-msg:  bugfix binding — message 含 fix → 必须有 issue doc
remote CI:   re-validate — 解析 PR 所有 commit messages + changed files
```

**当前阶段（Phase 3）的诚实局限**：Phase 3 只实现 presence gate（pre-commit）。`commit-msg` hook 和 bugfix binding 是 Phase 4 交付物。Phase 3 期间，bugfix 可以只带一个 PLAN 就通过——这是已知的过渡状态。

## 4. PLAN-057 思维范式的五条规则

从讨论中提炼，以后每次处理问题都该默认这样想：

### R1: 先分层，再动手

这是 policy、contract、还是 implementation？不同层不能混着修。
- **Guard 编码**：`check_issue_closure.py` 要求 issue frontmatter 声明 `problem_class`

### R2: 修复分两半

runtime fix（让现网恢复）和 mechanism fix（让它不再静默复发）必须分别证明。
- **Guard 编码**：issue 标 Fixed 但 `prevention_status: open` → P1, `blocking: true`

### R3: 一个事实只允许一个定义

其余要么自动派生，要么自动报警。
- **Guard 编码**：`check_mcp_parity.py`（两端工具名+行为一致）、`check_versions.py`（版本号一致）

### R4: 没有 guard 的 closure 都不稳

只靠人记得、只靠 issue 文档写"以后注意"，都不算闭环。
- **Guard 编码**：issue 标 Fixed 但 `guard_status: missing` 且 `problem_class != implementation` → P2, `blocking: true`

### R5: 验证看最后一公里

不是"服务启动了"就算过，要看用户价值链最后一步。
- **Guard 编码**：deploy.sh 路由验证（已有）

## 5. 需要新增 / 修改的组件

### 5.1 新增

| 组件 | 路径 | 职责 |
|------|------|------|
| Guard Router | `scripts/guard_router.py` | 文件路径 → guard 映射 + signal 生成 + union reader |
| Guard Feedback | `scripts/guard-feedback.py` | PostToolUse/PreToolUse hook 目标，调用 guard router |
| Issue Closure Check | `scripts/checks/check_issue_closure.py` | YAML frontmatter 解析 + closure 语义验证 |
| Artifact Link Check | `scripts/checks/check_artifact_link.py` | 代码变更 → 必须伴随 issue/plan artifact |
| Hook Install Check | `scripts/checks/check_hook_installed.py` | 验证 pre-commit hook 已激活 |
| Bridge Deps Check | `scripts/checks/check_bridge_deps.py` | 验证 bridge 外部依赖声明 |
| Pre-commit Hook | `.githooks/pre-commit` | checked into repo，调用 coherence.py --staged-only |
| Commit-msg Hook | `.githooks/commit-msg` | checked into repo，调用 check_bugfix_binding.py |
| Bugfix Binding Check | `scripts/checks/check_bugfix_binding.py` | commit message 含 fix → 必须有 issue doc |
| Bugfix Binding CI | `scripts/checks/check_bugfix_binding_ci.py` | 解析 PR commit range 的 CI 入口 |
| Remote Gate | `.github/workflows/coherence.yml` | GitHub Actions coherence 门禁（最终防线） |
| Context Router | `scripts/context-router.py` | 文件路径 → 上下文片段路由表（`CONTEXT_MAP`） |
| Context Fragments | `scripts/context-fragments/` (16 files) | 精炼的领域思维框架片段 |
| Fragment Integrity Check | `scripts/checks/check_fragment_integrity.py` | 验证片段引用完整性（CONTEXT_MAP vs 实际文件） |
| Guard Signal Dir | `.towow/guard/` | 目录结构（gitignored） |

### 5.2 修改

| 组件 | 修改内容 |
|------|---------|
| `scripts/coherence.py` | 新增 `--staged-only` 模式 + `--json` 输出模式 + `--exit-on-blocking` 模式 |
| `scripts/checks/__init__.py` | Finding 加 `blocking` + `category` + `problem_class` + `required_skills` 字段 |
| `.claude/settings.json` | 新增 PostToolUse + PreToolUse hook 配置 |
| `CLAUDE.md` | 新增 Closure Semantics 定义 + session-start 检查指令 |
| `.gitignore` | 新增 `.towow/guard/` |

### 5.3 迁移

| 对象 | 内容 |
|------|------|
| `docs/issues/*.md` | 现有 issue 文档添加 YAML frontmatter（一次性） |

### 5.4 不做

| 不做的事 | 原因 |
|---------|------|
| 持久化 guard daemon / 文件系统 watcher | PostToolUse + pre-commit + remote CI 已覆盖所有进入 repo 的变更 |
| AI 自动加载 skill 的代码 | Skill 加载是 AI 工具行为；signal 中的 `required_skills` 由 AI 自行消费 |
| Guard Report 历史 / inbox.jsonl | 单开发者阶段不需要历史审计；session 文件只保留最新 + 自动过期 |
| 非 Claude/Codex 工具的 governance reload 适配器 | Codex adapter 在 Phase 2 交付（见 3.10）；其他未知工具留给未来有需求时做 |

## 6. 实现优先级

### Phase 1: 硬保障层（最高优先）

1. `scripts/coherence.py` 加 `--staged-only` + `--json` 模式
2. `scripts/checks/__init__.py` Finding 扩展字段（`blocking`, `category`, `problem_class`, `required_skills`）
3. `.githooks/pre-commit`（checked into repo）
4. `scripts/checks/check_hook_installed.py`（bootstrap guard）
5. CLAUDE.md 加 closure semantics 定义
6. `.gitignore` 加 `.towow/guard/`

**完成标准**：Hook-installed 环境下，commit 经过 coherence 门禁（`blocking: true` 拦住）。所有环境下，deploy.sh 提供最终硬门禁。Hook 缺失会被 PostToolUse 检测到（Claude Code）或 remote CI 拦住（push 阶段）。

### Phase 2: 反馈层 + 上下文投影（Part B 核心）

7. `scripts/guard_router.py`（路径 → guard 映射 + per-session signal 写入 + union reader）
8. `scripts/guard-feedback.py`（PostToolUse/PreToolUse 目标，含 `--check-only --once` 模式）
9. `.claude/settings.json` PostToolUse + PreToolUse hook 配置
10. `scripts/context-router.py`（文件路径 → 上下文片段路由表 `CONTEXT_MAP`）
11. `scripts/context-fragments/`（全部 16 个上下文片段文件）
12. `scripts/checks/check_fragment_integrity.py`（片段引用完整性 guard）
13. Codex adapter（至少一条已验证的主动推送路径）

**完成标准**：
- **机制 B（被动 guard）**：AI 编辑文件后 1-2 秒内收到 guard 反馈 + skill 加载建议；新 session 首次 Read 时收到 repo 当前 blocking 状态。
- **机制 A（主动投影）**：AI 编辑 `bridge_agent/` 下的文件后，stderr 输出包含 `## Context` 标记和 Bridge 宪法片段内容（可通过 `guard-feedback.py --dry-run bridge_agent/agent.py` 验证）。
- **Codex**：至少一条 adapter 路径经过验证，能在 Codex 编辑文件后将 guard-feedback.py 输出主动送达 Codex。

### Phase 2.5: Remote Gate（最终防线）

14. `.github/workflows/coherence.yml`（GitHub Actions coherence 门禁）
15. `scripts/coherence.py` 加 `--exit-on-blocking` 模式

**完成标准**：`main` 设为 protected branch，禁止 direct push，`coherence-gate` 设为 required status check。PR 到 main 时 GitHub Actions 跑全量 coherence + bugfix binding，blocking findings 导致 check 失败、PR 不能 merge。本地 `--no-verify` 跳过 hook 的代码推到远程后仍会在 merge 阶段被拦住。

### Phase 3: 思维范式 guard

16. `scripts/checks/check_issue_closure.py`（YAML frontmatter 解析 + closure 语义）
17. `scripts/checks/check_artifact_link.py`（代码变更 → artifact 伴随）
18. `scripts/checks/check_bridge_deps.py`
19. `docs/issues/*.md` 现有 issue 迁移到 YAML frontmatter

**完成标准**：思维规则 R1-R5 中 R2（修复分两半）和 R4（没有 guard 的 closure 不稳）有可执行 guard。代码变更必须伴随 issue/plan artifact。

### Phase 4: Skill 注入 + Scope Binding（与 Phase 3 并行/后续）

20. `.githooks/commit-msg` hook（checked into repo，调用 `check_bugfix_binding.py`）
21. `scripts/checks/check_bugfix_binding.py`（本地：message + staged files）
22. `scripts/checks/check_bugfix_binding_ci.py`（CI：解析 PR commit range）
23. `check_artifact_link.py` 增强为 scope binding（验证 artifact `scope` 覆盖代码路径）
24. `lead` skill 加 closure protocol（Gate 7.5）
25. `towow-dev` skill 加 "runtime fix ≠ closure" 硬规则
26. `towow-bridge` skill 加 deployment boundary 声明要求
27. 现有 issue/plan doc 补全 `scope` 字段

**完成标准**：Bugfix/incident commit 被 commit-msg hook 强制绑定 issue doc。Artifact linkage 从 presence gate 升级为 scope binding。signal 的 `required_skills` 字段指向的 skill 都已包含相应思维框架。

## 7. 与现有系统的关系

- **PLAN-057**：本 ADR 是 PLAN-057 的自然延伸。PLAN-057 建立了 guard 脚本，本 ADR 建立了 guard 到 AI 思维的回传链路。Guard 命名沿用 PLAN-057 规范。
- **ADR-026 Bridge 宪法**：`check_bridge_deps.py` 是 Bridge 宪法第 4 条（"生产不能是第一个集成环境"）的机械化。
- **Lead Skill**：Lead 的 8-Gate 流程不变，本 ADR 在 Gate 7 和 Gate 8 之间插入 closure 验证。`check_artifact_link.py` 是 Gate 1 的机械化。
- **deploy.sh**：已有的 coherence 门禁不变，本 ADR 扩展 signal 输出格式和 per-session 写入。
- **GitHub Actions**：新增 `coherence.yml` workflow 作为 remote gate。与 pre-commit 共用同一套 guard 脚本，但运行时机不同（push/PR vs commit）。Remote gate 是最终防线——local hook 可以被绕过，remote CI 不能。

## 8. 设计原则

1. **规则在 repo，触发器在工具侧**：所有 guard 逻辑在 `scripts/`，Claude Code / Codex / CI 只是调用者。换框架不丢规则。
2. **Convention 先于 Guard**：先定义"正确的产物长什么样"（YAML frontmatter、artifact 伴随），再写代码检查。没有 convention 的 guard 是盲目的。
3. **Guard 保障 guard**：治理基础设施（hook、guard 脚本、settings）本身被 guard 路由覆盖。`check_hook_installed` 保证 pre-commit 在。
4. **Severity ≠ Blocking**：问题的严重程度和是否阻止 commit 是独立维度。治理要求的违反可以是低 severity 但 blocking。
5. **Per-session, union-on-read**：每个进程写自己的 signal 文件，读的时候合并所有文件。消除竞态，不需要锁。
6. **增量优先**：PostToolUse 和 pre-commit 都只跑改动文件相关的 guard（通过 guard_router），不跑全量。全量留给 deploy。
7. **硬阻断通用，思维重载 Claude-first**：任何环境都能拦住坏代码（git hooks + shell + remote CI），治理重载当前针对最活跃的开发环境优化，信号协议本身工具无关。
8. **Enforcement vs Feedback 不混淆**：PostToolUse `exit 2` 是反馈（AI 收到信息），不是阻断。真正的阻断只发生在 pre-commit、deploy.sh、remote CI。
9. **三层纵深防御**：编辑时反馈（快）→ 提交时本地拦截（强）→ 推送时远程拦截（不可绕过）。每一层削减问题密度，最终防线保证零泄漏。

## 9. 成功标准

这套机制成功的标志是：

1. **Governance reload（机制 B — 被动重载）**：新开一个 Claude Code 会话，不加载任何 skill，改了一行代码触发了 closure 问题 → AI 通过 PostToolUse hook 收到反馈，反馈中包含 `required_skills: ["lead"]`，AI 加载 lead skill 后用正确的 closure 语义处理问题。

2. **Context projection（机制 A — 主动投影）**：新开一个 Claude Code 会话，编辑 `bridge_agent/agent.py` → PostToolUse 输出包含 `## Context` + Bridge 宪法 5 条规则 → AI 后续编辑不违反这 5 条规则。**可验证方式**：`python3 scripts/guard-feedback.py --dry-run bridge_agent/agent.py` 输出包含 Bridge 宪法内容；`--dry-run mcp-server/towow_mcp/server.py` 输出包含 MCP 双端一致性约定。

3. **Artifact linkage (Phase 3)**：开发者修了一个 bug，只 staged 代码文件 → pre-commit 运行 `check_artifact_link`，发现没有伴随 issue/plan doc → `blocking: true` → commit 被拦住 → 开发者被迫创建/更新 issue doc（含 YAML frontmatter）。注：Phase 3 是 presence gate，要求伴随某个 artifact 但不验证语义关联。Phase 4+ 通过 `scope` 字段升级为 scope binding。

4. **Closure enforcement**：开发者创建了 issue doc 但没填 `prevention_status` → pre-commit 运行 `check_issue_closure` → `blocking: true` → commit 被拦住 → 开发者被迫思考 prevention。

5. **Multi-session consistency**：4 个并行窗口同时开发 → Session A 发现 `(file.py, closure, P1, blocking=true)` → 写入 `session-{pid_a}.json` → Session B 对同一文件发现 `(file.py, closure, P2, blocking=false)` → 写入 `session-{pid_b}.json` → 任何 reader 合并时取 `max(severity)=P1, blocking=OR=true` → 不会假绿。Session B 的 clean run 不会覆盖 Session A 的发现。

6. **Bootstrap**：clone repo 后第一次用 Claude Code 编辑文件 → PostToolUse 跑 `check_hook_installed` → 发现 pre-commit hook 未安装 → P0 blocking → AI 自动执行 `git config core.hooksPath .githooks`。

7. **Remote gate**：开发者用 `git commit --no-verify` 跳过 pre-commit + commit-msg → 本地 commit 成功 → `git push` → 创建 PR → GitHub Actions 跑 `coherence-gate` job → blocking findings 导致 required check 失败 → **PR 不能 merge** → 不合规代码无法进入 main。

8. **Bugfix binding（Phase 4）**：开发者 commit message 含 "fix" → `commit-msg` hook 调用 `check_bugfix_binding.py` → 检测到 message 匹配 + `git diff --cached` 无 `docs/issues/*.md` → `blocking: true` → commit 被拦住 → 开发者被迫创建 issue doc 并填写 closure frontmatter。

**一句话**：不靠记忆，不靠加载，不靠提醒。编辑时 feedback plane 立即回传 signal，commit 时 pre-commit + commit-msg 拦住 blocking findings，merge 时 required status check 拦住漏网之鱼。纵深防御，零泄漏。

## 10. Review Log

| # | Finding | Severity | 修复 | Section |
|---|---------|----------|------|---------|
| F1 | `latest.json` 多写者竞态，假绿 | P1 | Per-session files + union-on-read | 3.2, 3.7 |
| F2 | Closure severity 拦不住 commit | P1 | `blocking` 字段独立于 `severity` | 3.2, 3.5 |
| F3 | `.githooks/pre-commit` 不自动生效 | P1 | Bootstrap guard `check_hook_installed` | 3.8 |
| F4 | Guard router 不覆盖治理层文件 | P2 | 补全 GUARD_MAP + DEFAULT_GUARDS | 3.3 |
| F5 | `category` / `problem_class` 混用 | P1 | 正交维度分离，`CATEGORY_TO_SKILLS` | 3.2, 3.4 |
| F6 | Issue doc 字段无机器可读格式 | P1 | YAML frontmatter 规范 | 3.6 |
| F7 | 新 session 无治理状态注入 | P2 | PreToolUse `--check-only --once` | 3.5 |
| F8 | Guard 命名与 PLAN-057 不一致 | P2 | 沿用 PLAN-057 命名 | 3.3 |
| F9 | 代码变更无 issue/plan 硬链接 | P1 | `check_artifact_link.py` | 3.9 |
| F10 | 非 Claude 环境 governance reload 缺失 | P2 | 分层声明覆盖范围 | 3.1, 3.10 |
| F11 | Per-session union 无确定性合并规则 | P1 | `merge_findings()`: max(severity), OR(blocking), union(skills) | 3.2 |
| F12 | Artifact linkage 接受不相关文档 | P1 | 分层设计: Phase 3 presence gate + Phase 4+ scope binding | 3.6, 3.9 |
| F13 | PLAN/ADR 不触发 closure 检查，bugfix 可绕过 closure 链路 | P1 | 区分功能开发 vs bugfix：bugfix 必须绑定 issue doc（Phase 4+ bugfix binding） | 3.12 |
| F14 | Phase 1 完成标准假设 hook 已安装，与"不依赖记忆"目标矛盾 | P2 | 诚实分层：Hook 环境有 commit 门禁，所有环境有 deploy + remote CI 门禁 | 6 Phase 1 |
| F15 | GitHub Actions on push 是事后报警，不是真门禁 | P1 | Protected branch + PR-only + required status check + `on: pull_request` | 3.11 |
| F16 | Bugfix binding 依赖 commit message，但 pre-commit 阶段没有 message | P1 | 用 `commit-msg` hook（本地）+ CI commit range 解析（远程） | 3.12 |
| F17 | Phase 3 closure chain 误称 PLAN/ADR 会触发 closure 检查 | P2 | 拆成两条路径：issue doc → closure 检查 / PLAN+ADR → 仅 presence | 3.9 |
| **v7 独立审查 findings（Part B 聚焦）** |||||
| B1 | 机制 A（主动投影）效果度量缺失，成功标准只覆盖机制 B | P1 | 新增成功标准 #2（Context projection），含 `--dry-run` 验证方式 | 9 |
| B2 | 上下文片段自身过期/失准无检测（元层漂移的反漂移也会漂移） | P1 | `check_fragment_integrity.py` + GUARD_MAP 路由 `scripts/context-fragments/` | 3.3 |
| B3 | CONTEXT_MAP 覆盖空白（auth/、db/、catalyst/ 等高频区域无路由） | P2 | 扩展路由表 + 3 个新片段（auth-consumers, db-shared-structures, catalyst-distributed）+ 声明扩展原则 | 3.4.1 |
| B4 | Codex adapter 是承诺不是设计，三条候选路径均未验证 | P1 | Phase 2 完成标准加入 Codex adapter 验证；Codex Adapter 段加诚实声明 | 3.4.1, 6 Phase 2 |
| B5 | 机制 A + B 混合输出到同一 exit 2，AI 无法区分背景知识 vs 错误报告 | P2 | 输出分段标记：`## Context`（机制 A）vs `## Guard Findings`（机制 B） | 3.4.1 |
| B6 | Part B 核心交付物（context-router.py + 16 片段）无 Phase 归属 | P1 | 全部纳入 Phase 2 组件列表（#10~#13）+ Phase 2 完成标准增加机制 A 验证 | 6 Phase 2 |
| A2 | deploy 阻断逻辑只看 P0，pre-commit 看 blocking，不一致 | P2 | 补充设计决策注释：deploy 只拦安全问题，治理违规在 commit/merge 已关闭 | 3.5 |

## 11. 战略讨论记录（2026-03-22）

本次审查经历 17 个 findings、5 轮迭代，从逐条修复上升到对整个机制栈的战略性讨论。最终收敛为 4 条核心裁决。

### 最终目标（用户拍板）

> **Towow 的任何代码变更，都必须同时落在两张网里：**
> - **本地反馈网**：改完立刻有 guard 信号回传
> - **远程阻断网**：没过 gate 就进不了主线/生产

不是"让 AI 记住 PLAN-057"，而是"让任何 Towow 开发都被同一套本地反馈 + 远程阻断机制包住"。

### 4 条核心裁决

#### 裁决 1: Enforcement Plane vs Feedback Plane（明确分层）

PostToolUse `exit 2` 是反馈，不是阻断。

**裁决**：反馈面和强制面必须作为两个独立的架构概念维护。反馈面的价值是速度（编辑后 1-2 秒），强制面的价值是不可绕过性。见 Section 3.1.1。

#### 裁决 2: Remote Gate 是最终硬保证

Local hook 可以被 `--no-verify` 绕过。GitHub Actions workflow on `push` 是事后报警。

**裁决**：Protected branch + PR-only + required status check 三者组合才是真正不可绕过的硬门禁。PR 不过 coherence-gate check 不能 merge。见 Section 3.11。

#### 裁决 3: Bugfix/Incident 强制绑定 Issue Doc

PLAN/ADR 不触发 closure 检查。功能开发伴随 PLAN 合理，但 bugfix 必须走 issue doc → closure 链路。

**裁决**：`commit-msg` hook 在本地（有 message + staged files），remote CI 在远程（解析 PR commit range），双重验证 bugfix commit 必须伴随 issue doc。Phase 3 presence gate 是已知的过渡。见 Section 3.12。

#### 裁决 4: Phase 3 是过渡，最终目标是 scope/ref binding

Phase 3 presence gate 只检查"有没有 artifact 伴随"，不检查"是不是正确的 artifact"。

**裁决**：Phase 3 诚实标注为过渡。Phase 4 同时交付三个增强：bugfix binding（commit-msg hook）、scope binding（artifact scope 覆盖代码路径）、skill injection（signal 指向的 skill 包含思维框架）。

### 纵深防御总结

```
  编辑时 ─── Feedback Plane ──── AI 立即知道问题
              │                    Claude Code: PostToolUse/PreToolUse hooks（native）
              │                    Codex: adapter/watcher 主动推送
              ▼
  提交时 ─── Enforcement Local ── 两道 hook 拦住 blocking findings
              │                    .githooks/pre-commit:  presence gate + closure check
              │                    .githooks/commit-msg:  bugfix → 必须有 issue doc
              │                    （可被 --no-verify 绕过）
              ▼
  合并时 ─── Enforcement Remote ── required status check 阻止 merge
              │                    coherence.yml: 全量 coherence + bugfix binding
              │                    Protected branch: 禁止 direct push
              │                    （不可绕过）
              ▼
  部署时 ─── Enforcement Deploy ── deploy.sh 拦住 P0
                                    （全量 coherence）
```

**各环境覆盖**：

| 环境 | Feedback | Local Enforcement | Remote Enforcement |
|------|----------|-------------------|-------------------|
| Claude Code | native hooks（即时） | pre-commit + commit-msg | required check |
| Codex | adapter/watcher（主动推送） | pre-commit + commit-msg | required check |
| 手动开发 | CLI（手动） | pre-commit + commit-msg | required check |

所有路径最终都经过 remote gate（required status check on PR）。这是"不依赖记忆"的终极实现。

## 12. 偏移警告与原始要求锚点

### 偏移教训（必须永久保留）

本 ADR 经历 17 个 findings 的 5 轮迭代。每一轮 reviewer 都在问实现层的问题："多 session 竞态怎么办？hook 怎么安装？commit message 怎么拿到？protected branch 怎么配？"

这些 findings 都是对的。但它们全部指向 **enforcement plane**——标准 CI/CD，任何工程团队都有的东西。17 个 findings 没有一个在问 **governance reload**——"AI 的思维怎么才能真正被校正？"

结果：ADR 的灵魂（governance reload）在每一轮迭代中被稀释，最终 1022 行文档里 95% 在讲标准 CI，核心创新只有 10 行 stderr 描述。

**根因**：reviewer 的 findings 太有道理，导致作者逐个修复实现层问题时忘了核心目标。这本身就是 ADR-030 要解决的那个问题的又一次发作——思维方向被上下文噪声带偏。

**给未来编辑者的规则**：
- 修改本 ADR 时，先问：这个改动是在加强 governance reload，还是在加强 enforcement/CI？
- 如果连续 3 个以上改动都在 enforcement 层，停下来检查 governance reload 有没有被忽略
- Enforcement plane 应该用现成工具（pre-commit framework, GitHub Actions），不需要从头设计

### 用户原始要求（不可降级）

以下是用户在本 ADR 讨论开始前和讨论中明确提出的要求。完整来源见原始 transcript（252bfcc6, line 11218~11220）。任何迭代都不能静默降级：

#### 第一组：机制的存在性和触发方式

1. **机制本身要被显式强调**——不是藏在某个 ADR 附录里，不是"知道的人知道"。用户原话："无论是通过 skill、claude.md 还是固定的读一个东西"。这意味着机制入口必须在 AI 每次启动时被强制加载，不能靠"碰巧读到"。
2. **适用于所有 Towow 开发**——不限工具、不限人、不限场景。
3. **不依赖任何事**——比"不依赖记忆"更强。用户原话："不依赖任何事，只要是代码有改动就会有机制保障"。不依赖 AI、上下文、人主动提及或记忆。
4. **任何代码变更都自动触发**——不需要手动调用，不需要额外动作。

#### 第二组：覆盖的完整性

5. **全量有效，不是部分功能有效**——用户原话："哪怕我忘了，而且是全量有效，不是部分功能"。不是"恰好 cover 了当前已知的问题"，而是"保证 cover 所有代码变更"。
6. **必须包含思维范式级别**——不只是 CI、不只是格式检查。用户原话："而且也有思维范式级别的"。这是 ADR-030 区别于标准 CI/CD 的根本要求。

#### 第三组：具体的硬约束

7. **Claude Code 本地要即时信号回传**——PostToolUse/PreToolUse hooks，编辑后 1-2 秒内有 advisory 信号。
8. **Codex 本地也要即时信号回传**——不是"被动可读"，而是"改完代码直接有信号回传"。如果 Codex 没有原生 hook，用 adapter/watcher/wrapper 实现，调用同一套 repo 脚本。用户原话："脚本检测到东西之后，是可以提醒系统 ai 的"，"我们一定要接受"。
9. **Remote gate 是最终硬保证**——protected branch + required check，不是事后报警。用户原话："一定要到 remote gate"。
10. **Bugfix/incident 强制绑定 issue doc + 全部机械化**——不能用 PLAN/ADR 代替，且整体执行必须全部机械化，不留人工判断环节。用户原话："必须全部机械化"。

#### 要求间的层次关系

```
存在性（1~4）：机制必须存在、显式、自动、全场景
     ↓
完整性（5~6）：覆盖全量 + 思维范式，不只是 lint
     ↓
硬约束（7~10）：具体的实现底线，不可降级为"建议"
```

**第 6 条（思维范式级别）是整个 ADR 的灵魂。** 如果没有第 6 条，ADR-030 就是一个标准 CI/CD 系统。第 6 条要求的是 governance reload——检测到 AI 思维偏离后，用正确的思维框架重新校正 AI 的行为。这是传统代码开发和 AI Agent 代码开发的根本区别。

### 两部分的成熟度诚实声明

本 ADR 包含两个架构层面，成熟度截然不同：

**Part A: Enforcement Plane（成熟——可直接实现）**
- pre-commit + commit-msg + GitHub Actions + protected branch
- YAML frontmatter 格式检查 + artifact linkage
- 这是标准 CI/CD，可以用现成工具实现，不需要从头设计
- 当前文档的 Section 3.2~3.12 主要在讲这部分

**Part B: Governance Reload / 上下文工程（v6 已设计——见 Section 3.4.1）**
- 两个机制：主动上下文投影（每次编辑都注入相关思维框架）+ 被动 guard 重载（有问题时指向 skill/文档）
- 完整设计包括：上下文路由表、16 个上下文片段、`guard-feedback.py` 枢纽脚本、Codex adapter 路径
- 这是 ADR-030 区别于标准 CI/CD 的独特贡献
- **闭环保证**：上下文投影由代码确定性控制（路由表），不依赖 AI 自觉；enforcement plane（Part A）作为兜底，拦住即使有上下文也犯的错误

传统代码开发和 AI Agent 代码开发的核心区别：
- 传统开发检查**代码是否正确**（编译、测试、lint）
- AI 开发需要检查**AI 是否在用正确的方式思考**（governance reload）
- 后者是 ADR-030 的独特问题空间
