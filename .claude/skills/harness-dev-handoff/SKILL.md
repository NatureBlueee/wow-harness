---
name: harness-dev-handoff
description: {{PROJECT_NAME}}开发接手入口。用于新 AI 接手 {{PROJECT_NAME}} 开发、梳理最新上下文、开始生产排障、继续上一轮工作或确认当前主线时使用。
status: active
tier: entry
owner: nature
last_audited: 2026-04-06
triggers:
  - 新 session 接手 {{PROJECT_NAME}}
  - 继续上一轮开发
  - 进入生产排障
outputs:
  - 当前主线
  - 最新风险
  - 下一步建议
  - source drift
truth_policy:
  - repo 真相源优先于 skill 文本
  - skill 负责导航，不复制现有知识
  - 遇到冲突必须显式指出采用来源
---

# {{PROJECT_NAME}} 开发接手入口

## 目标

这个 skill 不负责复述 {{PROJECT_NAME}} 的全部历史，也不负责重新总结理念。

它只负责一件事：**让新接手 {{PROJECT_NAME}} 开发的 AI，在一次入场中找到最新、可执行、可验证的上下文入口。**

默认场景：
- 接手 {{PROJECT_NAME}} 生产开发
- 梳理当前主线
- 开始生产排障
- 继续上一轮工作
- 进入 MCP / protocol / matching / run 链路的真实代码

## 启动协议

每次新 AI 接手 {{PROJECT_NAME}} 时，按这个顺序执行：

1. 先运行：
   ```bash
   python3 .claude/skills/harness-dev-handoff/scripts/collect_handoff_context.py
   ```
2. 先读 repo 真相源，再读派生资料。
   - 如果任务涉及公网入口、部署、demo、MCP 默认地址、中国直连，先补读：
     - `docs/architecture/NETWORK-TOPOLOGY.md`
     - `ops/nginx/*.conf`
     - `scripts/deploy.sh`
     - `scripts/deploy-demo.sh`
     - `scripts/deploy-edge.sh`
3. 根据脚本输出，补读最近的 issue / decision / review。
4. 再读 Cloud memory 中最新的项目记忆。
5. 再抽查最近 1-3 个 transcript，只看有效用户意图，不看命令噪声。
6. 最后形成当前接手摘要。

## Truth Policy

我不是新的权威副本。我只负责把新 agent 引到当前仍然活着的真相源上。

## 真相源优先级

遇到信息冲突时，按这个优先级判断：

1. `CLAUDE.md`
2. `MEMORY.md`
3. `docs/INDEX.md`
4. 最近的 `docs/issues/*.md`、`docs/decisions/*.md`、`docs/reviews/**/*.md`
5. Cloud 项目目录下的 `memory/`
6. transcript `.jsonl`

规则：
- 不要把 skill 自己当成新的权威副本。
- skill 负责导航，不负责复制现有知识。
- 如果发现 source drift，必须显式指出冲突点和你最终采用的来源。

## 治理机制入口（ADR-030）

{{PROJECT_NAME}} 有一套上下文工程系统（不是 prompt），通过 PostToolUse hook 在编辑文件时自动注入相关思维框架：

- **路由表**：`scripts/context_router.py` — 文件路径 → 上下文片段映射
- **片段库**：`scripts/context-fragments/` — 精炼的领域规则（每个 10-25 行）
- **Guard 路由**：`scripts/guard_router.py` — 文件路径 → guard 脚本映射
- **Hook 入口**：`scripts/guard-feedback.py` — PostToolUse 目标
- **设计文档**：`docs/decisions/ADR-030-guard-signal-protocol-and-governance-reload.md`

如果 PostToolUse hook 正常工作，接手者编辑文件时会自动收到该领域的上下文。如果没收到，检查 `.claude/settings.json` 中的 hook 配置。

## 公网入口 / 部署接手补充

涉及公网入口或生产部署时，先确认这些边界仍成立：

- 对外品牌 / 全球默认 / MCP 默认入口看 `<NETWORK_REDACTED>`
- 中国公开入口看 `<NETWORK_REDACTED>`
- 原始 IP 只允许留在 preview、bridge、ops、部署脚本，不进入用户默认入口
- edge 路由真相源在 `ops/nginx/*.conf`，不是线上手改的 `/etc/nginx/conf.d/*`
- demo 发布分 `prod` / `preview` 两条通道，不能把 preview 产物当 prod 发

## 必读代码入口

完成文档入场后，优先进入这些路径：

- `backend/server.py`
- `backend/product/protocol/`
- `backend/product/matching/`
- `backend/product/bridge/`
- `backend/product/catalyst/`
- `backend/product/openagents/`

这些路径对应当前生产主链：

`clarification-session -> discover -> invitation -> run -> prompt/respond -> result`

## transcript 噪声过滤

默认忽略这些内容：

- `local-command-caveat`
- `/clear`、`/model` 等命令操作
- `local-command-stdout`
- 纯模型切换信息
- 非业务性的命令回显
- 纯 Team assignment / shutdown 元信息（除非任务本身在审计 Agent Team 工作流）

你要优先提取的是：

- 最近几次有效用户意图
- 用户最近想推进的主线
- 用户最近指出的线上问题
- 用户最近改变的方向或约束

## 输出契约

完成接手后，先输出 4 个块，再展开细节：

1. 当前主线
2. 最新风险
3. 下一步建议
4. 缺失真相源 / source drift

默认要求：
- 不直接复述旧知识
- 先找最新来源
- 先给当前状态，再展开细节
- 发现 source drift 时必须显式指出

## 工具

脚本入口：

```bash
python3 .claude/skills/harness-dev-handoff/scripts/collect_handoff_context.py
```

可选参数：

```bash
python3 .claude/skills/harness-dev-handoff/scripts/collect_handoff_context.py \
  --cloud-root ~/.claude/projects/-Users-nature------{{PROJECT_NAME}} \
  --recent-sessions 3 \
  --recent-messages 3
```

脚本只负责收集入口，不替代你做判断。
