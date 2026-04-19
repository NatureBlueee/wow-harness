# Claude Code + Cursor CLI：全局 hooks 与项目级 hooks

## 目标

- **任意工作区**只要检出过 wow-harness（存在 `.wow-harness/MANIFEST.yaml`），即可在 **不提交** `~/.cursor` 到该仓库的前提下，让 **Cursor CLI** 与 **Claude Code** 走同一套生命周期脚本。
- **项目已自带** `.cursor/hooks.json` 或 `.claude/settings.json` 里的 `hooks` 时，全局层 **自动让位**，避免同一事件跑两遍。

## 安装

在 wow-harness 仓库根目录执行：

```bash
python3 scripts/install/wow_global_hooks.py install
```

该命令会：

1. 将 `scripts/install/wow_agent_dispatch.py` 复制到 `~/.wow-agent-hooks/wow_agent_dispatch.py`。
2. 写入 `~/.cursor/hooks.json`（若已有则先备份为 `*.bak.<timestamp>`）。
3. 合并写入 `~/.claude/settings.json` 的 `hooks` 字段（保留其它键如 `mcpServers`）。
4. 若存在 `scripts/install/templates/wow-harness-autodispatch.js`，则安装到 `~/.config/opencode/plugins/wow-harness-autodispatch.js`。

## 卸载与状态

```bash
python3 scripts/install/wow_global_hooks.py status
python3 scripts/install/wow_global_hooks.py uninstall
```

卸载会备份后移除全局 Cursor hooks 文件、清空 Claude 的 `hooks` 键、删除 OpenCode 插件文件（若曾安装）。

## 分发器行为摘要

`wow_agent_dispatch.py` 从 `CURSOR_PROJECT_DIR` / `CLAUDE_PROJECT_DIR` 或当前目录向上查找 `.wow-harness/MANIFEST.yaml`，解析出项目根后，在子进程中执行该项目内的 `scripts/hooks/*.py` 等。调试日志（尽力而为）写在 `~/.wow-agent-hooks/logs/dispatch.jsonl`。

**Cursor stdin 归一**：全局入口在把 JSON 交给子脚本前会补全缺失的顶层 `cwd`（优先已有 `cwd`，否则 `tool_input.working_directory`，再否则 `workspace_roots[0]`），并把 `conversation_id` 复制为 `session_id`，以便与 Claude 侧脚本对路径与会话字段的假设一致。

**项目内 hooks + 全局 hooks**：仅当本进程是安装在 `~/.wow-agent-hooks/wow_agent_dispatch.py` 的**全局**入口且仓库内已存在 `.cursor/hooks.json` 时才会 noop 让位。若 `hooks.json` 里调用的是**仓库自带的** `scripts/install/wow_agent_dispatch.py`（例如 phase2 安装后的项目），则必须照常执行桥接，否则会误 noop、整链失效。

## 与 `issue-adapter.yaml` 的关系

若项目内 `.wow-harness/issue-adapter.yaml` 中 `enabled: false`，则 `scripts/guard-feedback.py` 对 **PostToolUse** 路径为纯 no-op（不注入 fragment、不跑 guard）。全局分发器仍会调用 `guard-feedback.py`，但脚本会立即退出；其它 hook 不受影响。设为 `enabled: true` 则启用完整 context 路由与 guard 检查。

## 参考

- 安装器源码：`scripts/install/wow_global_hooks.py`、`scripts/install/wow_agent_dispatch.py`
- 脚手架安装仍使用 `scripts/install/phase2_auto.py`（按项目复制 bundle，与全局 hooks 互补）
