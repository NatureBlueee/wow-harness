# Claude Code + Cursor CLI + Codex：全局 hooks 与项目级 hooks

## 目标

- **任意工作区**只要检出过 wow-harness（存在 `.wow-harness/MANIFEST.yaml`），即可在 **不提交** `~/.cursor` 到该仓库的前提下，让 **Cursor CLI** 与 **Claude Code** 走同一套生命周期脚本。
- **项目已自带** `.cursor/hooks.json` 或 `.claude/settings.json` 里的 `hooks` 时，全局层 **自动让位**，避免同一事件跑两遍。
- **Codex** 通过仓根 `AGENTS.md` 获取同一套项目约束。当前不为 Codex 增加 router hook；这是 ADR-041 的显式边界。

## 安装

在 wow-harness 仓库根目录执行：

```bash
python3 scripts/install/wow_global_hooks.py install
```

该命令会：

1. 将 `scripts/install/wow_agent_dispatch.py` 复制到 `~/.wow-agent-hooks/wow_agent_dispatch.py`。
2. 将 `scripts/install/va-agent-wrap.sh` 复制到 `~/.wow-agent-hooks/va-agent-wrap.sh`（可执行），供下面第 5 步的 shell 包装调用。
3. 写入 `~/.cursor/hooks.json`（若已有则先备份为 `*.bak.<timestamp>`）。
4. 合并写入 `~/.claude/settings.json` 的 `hooks` 字段（保留其它键如 `mcpServers`）。
5. 若存在 `scripts/install/templates/wow-harness-autodispatch.js`，则安装到 `~/.config/opencode/plugins/wow-harness-autodispatch.js`。
6. 在 **`~/.bashrc` 与 `~/.zshrc`（若存在）** 末尾追加一段受管 shim：当 `~/.wow-agent-hooks/va-agent-wrap.sh` 可执行且当前 shell 里还没有名为 `agent` 的**函数**时，定义 `agent()`，把调用转发给该包装脚本。安装时会尽量删除旧的「仅 VoiceAgent」`_voiceagent_*` 块，避免重复包装。

## 卸载与状态

```bash
python3 scripts/install/wow_global_hooks.py status
python3 scripts/install/wow_global_hooks.py uninstall
```

卸载会备份后移除全局 Cursor hooks 文件、清空 Claude 的 `hooks` 键、删除 OpenCode 插件文件（若曾安装）、删除 `~/.wow-agent-hooks/va-agent-wrap.sh`，并从 `~/.bashrc` / `~/.zshrc` 中移除受管 universal shim（以及残留的 VoiceAgent-only `_voiceagent_*` 块）。

## 分发器行为摘要

`wow_agent_dispatch.py` 从 `CURSOR_PROJECT_DIR` / `CLAUDE_PROJECT_DIR` 或当前目录向上查找 `.wow-harness/MANIFEST.yaml`，解析出项目根后，在子进程中执行该项目内的 `scripts/hooks/*.py` 等。调试日志（尽力而为）写在 `~/.wow-agent-hooks/logs/dispatch.jsonl`。

**Cursor stdin 归一**：全局入口在把 JSON 交给子脚本前会补全缺失的顶层 `cwd`（优先已有 `cwd`，否则 `tool_input.working_directory`，再否则 `workspace_roots[0]`），并把 `conversation_id` 复制为 `session_id`，以便与 Claude 侧脚本对路径与会话字段的假设一致。

**项目内 hooks + 全局 hooks**：仅当本进程是安装在 `~/.wow-agent-hooks/wow_agent_dispatch.py` 的**全局**入口且仓库内已存在 `.cursor/hooks.json` 时才会 noop 让位。若 `hooks.json` 里调用的是**仓库自带的** `scripts/install/wow_agent_dispatch.py`（例如 phase2 安装后的项目），则必须照常执行桥接，否则会误 noop、整链失效。

**可见性**：每次经分发器**实际执行**仓库内脚本时，会在 `.wow-harness/state/harness-visible.jsonl` 追加一行 JSON（`runtime`、`hook`、时间）；新会话的 `session-start-harness-banner` 会在上下文里说明该文件与 `WOW_HARNESS_STDERR_TRACE` / `WOW_HARNESS_QUIET` 环境变量。

**CLI `agent` 与 SessionStart**：`sessionStart` 的 `additional_context` 进入**模型上下文**，不会画在终端 ASCII 框里。

**重要（已在本机用 `agent -p` + 分离重定向验证）**：Cursor **`agent` CLI 不会把 hook 子进程的 stderr 接到你的 TTY**；因此 `before-submit-harness-ping` / `session-start-harness-banner` 里写的 `stderr` **在纯 `agent` 交互界面里不可见**。要看治理链是否在跑，请用 **`.wow-harness/state/harness-visible.jsonl`**（`tail -f`），或在终端里通过 **`agent` 包装** 启动：`wow_global_hooks.py install` 会把 **`va-agent-wrap.sh`** 装到 `~/.wow-agent-hooks/`，并在 shell 里注册 `agent()`（仅当尚未存在同名**函数**时），从而对**任意 Git 仓库**生效——若仓库根存在 **`.wow-harness/MANIFEST.yaml`**，则在 `exec` 真实 `agent` 前向 stderr 打印横幅；若仓库另有可执行的 **`scripts/va-agent`**（例如 VoiceAgent），则**优先**走该脚本以便定制文案。找不到 Cursor CLI 时，可设置环境变量 **`WOW_AGENT_BIN`** 指向 `agent` 可执行文件。

**全局 hooks 更新**：修改 `wow_global_hooks.py` 后必须重新执行 `python3 scripts/install/wow_global_hooks.py install`，否则 `~/.cursor/hooks.json` 仍是旧条目（会缺 `beforeSubmitPrompt` / `session-start-harness-banner`）。

## 与 `issue-adapter.yaml` 的关系

若项目内 `.wow-harness/issue-adapter.yaml` 中 `enabled: false`，则 `scripts/guard-feedback.py` 对 **PostToolUse** 路径为纯 no-op（不注入 fragment、不跑 guard）。全局分发器仍会调用 `guard-feedback.py`，但脚本会立即退出；其它 hook 不受影响。设为 `enabled: true` 则启用完整 context 路由与 guard 检查。

## Codex 路径

Codex 侧集成是指令级而非 hook 级：

1. 安装器会复制仓根 `AGENTS.md` 到目标项目。
2. `AGENTS.md` 只包含 Codex 必须知道的项目约束、适合分流的任务和红线。
3. Claude 侧通过 `.claude/agents/codex-dev.md` 把 Codex 作为执行类 agent 目标使用。
4. Codex 不参与 Gate 2/4/6/8 的独立审查；它只负责实现。

如果未来要给 Codex 增加真实生命周期 hook，必须先写新的 ADR supersede ADR-041，不能直接把 router 逻辑塞进现有分发器。

## 参考

- 安装器源码：`scripts/install/wow_global_hooks.py`、`scripts/install/wow_agent_dispatch.py`
- 脚手架安装仍使用 `scripts/install/phase2_auto.py`（按项目复制 bundle，与全局 hooks 互补）
