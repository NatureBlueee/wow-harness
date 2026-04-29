# ADR-045: Codex 原生生命周期 hooks 与非 Claude 运行时体感对齐

**状态**: accepted
**日期**: 2026-04-29
**Supersedes**: ADR-041 §3 里“Codex 不加 PostToolUse / PreToolUse hook”的边界，仅限本 ADR 定义的 advisory lifecycle hooks。ADR-041 的“Codex 不参与 Gate 审查、不做 router、不建强制分流状态机”继续有效。

## 1. 问题

Nature 反馈：在 Codex、OpenCode、Cursor CLI 里使用 wow-harness，体感没有 Claude Code 好。

根因不是模型单点能力，而是 runtime 原语差异：

1. Claude Code 原生有生命周期 hooks，能在 `SessionStart` / `PreToolUse` / `PostToolUse` / `Stop` 把上下文和阻断信号直接送回会话。
2. Codex 官方已经支持 project-level `.codex/hooks.json`、`config.toml` feature flag，以及 `SessionStart`、`PreToolUse`、`PermissionRequest`、`PostToolUse`、`Stop` 事件；ADR-041 写下“不要加 Codex hook”时，这个能力还不是本仓库已验证前提。
3. Cursor CLI 官方读取 `AGENTS.md` / `CLAUDE.md`，并支持 `<project>/.cursor/cli.json` 权限；但 CLI 终端可见性不等同于 Claude Code UI，所以必须用项目 hooks + 可见日志补偿。
4. OpenCode 官方支持 project plugin、`tool.execute.before/after`、`permission` 规则和 agent-level permission；本仓库应该显式声明权限，而不是依赖默认 permissive 行为。

官方参考：

- OpenAI Codex hooks: https://developers.openai.com/codex/hooks
- OpenAI Codex AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- Cursor CLI rules / permissions: https://docs.cursor.com/en/cli/using, https://docs.cursor.com/cli/reference/permissions
- OpenCode plugins / tools / permissions: https://opencode.ai/docs/plugins/, https://opencode.ai/docs/tools/, https://opencode.ai/docs/permissions

## 2. 决策

### D1: Codex 增加官方原生生命周期 hooks

新增：

- `.codex/config.toml`：启用 `codex_hooks` feature flag。
- `.codex/hooks.json`：声明项目级 hooks。
- `scripts/codex/wow_codex_hook.py`：把现有 wow-harness 脚本翻译为 Codex hook JSON。

hook 覆盖范围：

| Codex event | wow-harness 行为 |
|---|---|
| `SessionStart` | 注入 harness 激活说明、Magic Doc 漂移、工具提醒，重置风险快照 |
| `PreToolUse` / `Bash` | 调 `sanitize-on-read.py` 与 `deploy-guard.py`，必要时 deny |
| `PermissionRequest` / `Bash` | 对升级审批再跑 `deploy-guard.py`，必要时 deny |
| `PostToolUse` / `apply_patch|Edit|Write` | 解析 patch 路径，逐文件跑 `guard-feedback.py`、`loop-detection.py`、`risk-tracker.py` |
| `Stop` | 跑 `python3 scripts/codex/wow_codex_check.py --strict`，发现 blocking findings 时让 Codex 继续修 |

### D2: Codex 仍不是 router 或 reviewer

这些 hooks 只是“把现有脚本的即时反馈送回 Codex”。它们不得做：

- Codex 分流决策树；
- Gate 2/4/6/8 独立审查；
- 自动评价自己是否通过审查；
- marker/hash/chokepoint 式的强制状态机。

因此本 ADR 不推翻 ADR-041 的核心哲学，只修正“Codex 完全无生命周期反馈”的过时前提。

### D3: Cursor CLI 用官方权限面收紧最危险动作

`.cursor/cli.json` 保持常用工具可用，但加入 deny 规则：

- 禁 `rm` / `dd` / `mkfs` / `shred` 这类破坏性 shell command base；
- 禁读写 `.env*`、`*.pem`、`*.key`。

更细的部署风险仍由 `pre-deploy-guard` 负责，因为 Cursor CLI 的 `Shell(commandBase)` 权限粒度按命令首 token 工作，不能可靠表达“只禁止某些 ssh/scp 目标”。

### D4: OpenCode 用官方 permission 显式化安全边界

`opencode.json` 增加 top-level `permission`：

- `read` / `edit` 默认可用，但 deny `.env*`、`*.pem`、`*.key`；
- `bash` 默认 ask，放行常用只读 git/rg 与本仓库验证命令；
- deny `git reset --hard`、`git checkout --`、`git clean -fd`、`git push --force`、`rm *`。

项目插件继续负责 post-edit feedback，`wow-reviewer` 继续只读。

### D5: 安装脚手架复制 Codex 层

`phase2_auto.py` 的 bundle 复制范围加入 `.codex/`，这样目标项目安装 wow-harness 后也能获得 Codex project hooks。Codex 仍需信任项目 `.codex/` layer；未启用时显式 fallback 是：

```bash
python3 scripts/codex/wow_codex_check.py --strict
```

## 3. 验收

必须通过：

```bash
PYTHONPYCACHEPREFIX=/tmp/wow-harness-pycache python3 -m compileall -q scripts
node --check .opencode/plugins/wow-harness-runtime.js
node --check scripts/install/templates/wow-harness-autodispatch.js
python3 scripts/install/wow_runtime_doctor.py
python3 scripts/codex/wow_codex_check.py --strict
bash scripts/ci/count-components.sh
python3 scripts/ci/scan_verify_artifacts.py --claims
python3 scripts/ci/detect_rebaseline_triggers.py
```

并至少 smoke：

- `scripts/codex/wow_codex_hook.py session-start`
- `scripts/codex/wow_codex_hook.py pre-deploy-guard`
- `scripts/codex/wow_codex_hook.py post-write-bundle`
- `scripts/codex/wow_codex_hook.py stop-check`

## 4. 不做什么

- 不给 Codex 新增 review authority。
- 不让 Codex 替代独立 reviewer。
- 不把 Cursor/OpenCode/Codex 做成同一个伪 Claude Code；只用各自官方扩展点接入同一套 repo 脚本。
- 不用全局强制配置覆盖用户个人偏好；项目层提供默认，用户层可继续自行选择。
