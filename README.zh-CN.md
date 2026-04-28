中文 | [English](README.md)

# wow-harness

> "你怎么做到让 AI 自己开发，人几乎不用管？"

这就是答案。

wow-harness 是 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 的治理层，同时提供 Codex 指令和 Cursor / Claude / OpenCode 的全局 hook 分发。它让 AI agent 变得足够可靠——你定方向，AI 交付，工作真的能落地。靠的不是提示词里多写几句"请认真做"，而是机械化的审查门禁、完成验证和工具隔离。

## 问题

Claude Code 能力很强。但不加约束时，它有结构性偏见：

- **假装完成** — "测试全过了"（其实没跑）
- **跳过审查** — "这个改动很简单"（并不简单）
- **任务漂移** — 修一个 bug，顺手重构三个文件
- **自我评价偏差** — 问自己"做得好不好？"，回答"好"

你花在监督上的时间，比省下的开发时间还多。更难受的是，它做对的 80% 让你放松警惕，剩下 20% 的静默遗漏更难发现。

## 核心洞察

```
CLAUDE.md 指令遵从率:     ~20%
PreToolUse hook 执行率:   100%
```

指令改变不了 AI 的行为。机械约束可以。

告诉审查 agent "不要修改文件"，遵从率约 70%。把 Edit/Write 从它的工具清单里删掉，遵从率 100%——它物理上调不了不存在的工具。

wow-harness 把这个原则应用到所有该管的地方：重要的事不靠说，靠 hook。

## 装了之后有什么变化

| 没有 wow-harness | 有 wow-harness |
|---|---|
| "跑测试了吗？" → "跑了"（没跑） | 机械化门禁检查 `progress.json` — 伪造不了证据 |
| 纯聊天时弹出完成检查清单 | Stop hook 解析 session transcript — 只在有未提交的编辑时才触发 |
| 审查 agent "顺手"改了它审查的代码 | 审查 agent 物理上无法调用 Edit/Write（schema 级隔离） |
| "这个 PR 简单，跳过审查吧" | Gate 2/4/6/8 机械化强制独立审查 — 没有例外 |
| 并行 AI session 互相污染 | 每个 session 通过独立 transcript 文件隔离作用域 |
| Agent 漂移去修不相关的东西 | 上下文路由只对正在编辑的文件注入领域规则 |

## 怎么工作的

### Hook：在动作发生的那一刻介入

18 个 hook command 覆盖 7 个生命周期阶段。不是事后审查，是实时拦截：

```
SessionStart  →  加载上下文、重置风险状态、展示可用工具
PreToolUse    →  拦截危险部署、门控审查 agent、净化读取内容
PostToolUse   →  编辑时路由上下文、检测循环、追踪风险
Stop          →  验证是否存在完成候选品（transcript × git diff）
SessionEnd    →  反思、分析轨迹、持久化进度
```

### 8 关状态机

每个重要变更都要过关。偶数关要求独立审查——不是同一个 agent 自己检查自己的工作：

```
G0 问题  →  G1 设计  →  G2 审查*
  →  G3 方案  →  G4 审查+锁定*
  →  G5 任务拆分  →  G6 审查*
  →  G7 执行+日志  →  G8 终审*

* = 独立审查者（独立上下文、只读工具）
```

### 自动化检查

15 个验证器在文件变更时运行：API 类型一致性、文档新鲜度、安全模式、片段完整性、hook 注册等。在漂移累积之前就抓住它。

### Skill

16 个专业化行为——从架构设计（`arch`）到失败模式提取（`crystal-learn`）到结构化 bug 分诊（`bug-triage`）。Skill 安装的是判断框架，不是规则清单，所以 agent 能应对 skill 没明确覆盖的情况。

每个 skill 都有 `{{PLACEHOLDER}}` 结构化槽位，安装时会填入你项目的上下文。

### Codex 执行通道

Codex 被集成为有边界的执行通道，不是新的审查权威。`AGENTS.md` 承载 Codex 可读的项目规则，`.claude/agents/codex-dev.md` 让 Claude 可以把批量重构、补测试、文档、shell 脚本、CI 检查这类机械实现工作分流出去。ADR-041 明确不新增 Codex router hook；默认靠人/Claude 判断，再轻量分流。

## 安装

```bash
git clone https://github.com/NatureBlueee/wow-harness.git
cd wow-harness
python3 scripts/install/phase2_auto.py /path/to/your/project --tier drop-in
```

### 三个层级

| 层级 | 信任度 | 效果 |
|------|--------|------|
| **drop-in** | 最低 | 原样安装 hook + skill。先试试看。 |
| **adapt** | 中等 | 读你的 README + 文档，把 skill 适配到你的项目。 |
| **mine** | 完全 | 读你的工作 transcript，深度适配到你的模式。 |

### 安装了什么

```
your-project/
├── AGENTS.md             # Codex 可读的项目规则和分流边界
├── .claude/
│   ├── settings.json    # Hook 注册（追加模式，不覆盖已有配置）
│   ├── agents/          # codex-dev 等分流目标
│   ├── skills/          # 16 个 agent 行为定义
│   └── rules/           # 路径作用域上下文规则（按文件路径自动加载）
├── scripts/
│   ├── hooks/           # 生命周期 hook 脚本
│   └── checks/          # 15 个自动化验证器
└── CLAUDE.md            # 治理指南（自动生成，你可以自由编辑）
```

安装器是幂等的——跑两次，结果一样。

### Cursor CLI + Claude + OpenCode 全局 hooks（可选）

若要在**任意仓库**通过用户级 Cursor / Claude 配置和可选 OpenCode 插件复用同一套 hook（而不必每个仓库都提交 `.cursor/`），可安装分发器：

```bash
python3 scripts/install/wow_global_hooks.py install
```

说明见 [docs/dual-cli-global-hooks.md](docs/dual-cli-global-hooks.md)。

### OpenCode 实验性 PoC

本仓库现在带有一套 OpenCode 兼容性验证 PoC：

- 项目插件：`.opencode/plugins/wow-harness-runtime.js`
- 只读审查 agent：`.opencode/agents/wow-reviewer.md`
- 项目配置：`opencode.json`
- 说明文档：[docs/opencode-poc.md](docs/opencode-poc.md)

当前 PoC 的范围刻意收窄：session 启动准备、`.env` 读取净化、编辑后的风险快照、compact 延续提醒、停止时的完成提案，以及只读 reviewer 隔离。它证明 wow-harness 可以接到另一个 agent runtime 上；还不声称已经和 Claude Code 侧完整等价。

## 设计原则

1. **Hook 优于指令** — 重要的事不靠说，靠执行。
2. **Schema 级隔离** — 审查 agent 的工具清单里没有写工具。不是"请不要"——是"不能"。
3. **安全方向 fail-open** — hook 读不到数据时注入*更多*检查，不是更少。失败模式永远是"过于谨慎"，绝不是"静默跳过"。
4. **Session 隔离** — 完成检测用每个 session 独立的 transcript 解析。并行 session 之间零共享可变状态。
5. **结构化槽位** — 项目特定内容变成 `{{PLACEHOLDER}}` + 元指令（放什么、为什么重要、怎么发现它），不是你忘记填的空白字段。

## 环境要求

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- Codex CLI 可选；存在时读取仓根 `AGENTS.md` 指令。
- Python 3.9+
- Git

## 来历

从 [Towow](https://towow.net)（通爻，一个 Agent 协作协议项目）6 个月的生产使用中提取出来的。治理层不断证明它独立于项目也有价值——每个 AI 辅助开发的项目都需要它，不只是我们的。

这里的每一条 hook、每一个 gate、每一种隔离模式，都是因为 AI agent 找到了创造性的方法来绕过上一条规则，所以才被加上的。不是设计出来的，是被逼出来的。

## License

MIT
