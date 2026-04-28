---
name: bug-pipeline
description: Bug 反馈 → 自动修复 → PR 的端到端流水线。用户在任何渠道扔一句话 bug，自动走 triage + guardian-fixer 8 Gate 修复流程，最后开 PR 到 GitHub。依赖 Codex harness（headless `Codex -p`）。
status: active
tier: infrastructure
triggers:
  - bug 自动修复
  - 反馈 pipeline
  - 自动 PR
outputs:
  - GitHub PR（带双语标题 + reporter attribution + 8 Gate artifact）
truth_policy:
  - 运行时事实以日志和状态文件为准
  - 架构见本文件，细节见 runtime/ 子目录
---

# Bug → PR 全自动流水线

## 一句话

**用户在消息渠道发一条 bug，本地常驻进程捡起来，调 `Codex -p` 跑 triage + guardian-fixer 8 Gate 修复流程，最后自动开 PR 到 GitHub。**

---

## 这个东西解决的问题

早期产品有一堆 bug，但开发者看不到 / 用户懒得写 / 开发者懒得修的三重循环。

这个 skill 把链路全部压缩到 15 分钟：

| 环节 | 传统做法 | 本 skill |
|---|---|---|
| 用户反馈 | 提 Issue / 写邮件 / 填表 | 消息渠道一句话 |
| 分诊 | 产品经理人工判断优先级 | `bug-triage` skill 自动判断 |
| 修复 | 开发者进入 sprint 排期 | `guardian-fixer` skill 8 Gate 闭环 |
| PR | 人工写描述 + 补测试 | `gh pr create` 自动带完整 artifact |
| 成本 | $$$ 人天 | **0 API 成本**（走 Codex 订阅） |

---

## 架构一眼图

```
┌──────────────────────┐
│ 消息渠道（适配器）     │
│ 飞书 / Slack / 邮件   │
└────────┬─────────────┘
         │ 事件到达
         ▼
┌──────────────────────┐      ┌──────────────────────┐
│ bug_daemon            │      │  队列目录             │
│ (常驻进程 #1)         │─────▶│  <ts>-<source>-*.json │
│ 监听消息渠道          │      │                      │
└──────────────────────┘      └───────────┬──────────┘
                                          │ poll
                                          ▼
                              ┌──────────────────────┐
                              │ bug_worker            │
                              │ (常驻进程 #2)         │
                              │ batch + route         │
                              └───────────┬──────────┘
                                          │
                    ┌─────────────────────┼──────────────────┐
                    ▼                     ▼                  ▼
         ┌──────────────────┐  ┌────────────────┐  ┌──────────────────┐
         │ Codex -p         │  │ git worktree   │  │ Codex -p         │
         │ --skill           │  │ (隔离分支)      │  │ --skill           │
         │   bug-triage      │  │                │  │   guardian-fixer  │
         └──────────────────┘  └────────────────┘  └──────────────────┘
                  │                                          │
                  ▼                                          ▼
           docs/issues/*.md                              gh pr create
```

三个关键隔离：
1. **daemon 和 worker 进程隔离** — daemon 挂了不影响已排队的 bug 继续修
2. **worker spawn 子进程跑 `Codex -p`** — 用订阅不烧 API tokens
3. **每个 bundle 一个 git worktree** — 多 bug 并行互不踩

---

## 消息渠道适配器（结构性槽位）

> 这套 pipeline 的核心是平台无关的。消息源通过**适配器**接入。
>
> 安装时只需实现一个适配器：从你的消息渠道接收事件，写成标准 JSON 到队列目录。

### 适配器接口契约

适配器必须产出以下格式的 JSON 文件到队列目录：

```json
{
  "record_id": "唯一标识",
  "received_at": "ISO 8601 时间",
  "source": "feishu|slack|email|github-issue",
  "fields": {
    "症状": "用户原话",
    "复现步骤": "用户提供的复现步骤（可选）",
    "场景": "受影响的产品区域（可选）",
    "严重程度": "用户自评（可选）",
    "reporter": {
      "name": "报告者名",
      "user_id": "平台内 ID"
    }
  },
  "attachments": []
}
```

### 已有适配器

| 平台 | 适配器 | 运行方式 |
|---|---|---|
| 飞书 | `runtime/adapters/feishu_daemon.py` | macOS LaunchAgent / Linux systemd |
| Slack | `runtime/adapters/slack_daemon.py` | 同上（需 Slack App + Socket Mode） |
| GitHub Issues | `runtime/adapters/github_issue_daemon.py` | webhook / poll |

**写你自己的适配器**：实现 `poll()` → 写 JSON 到 `~/.wow-harness/queue/` 即可。参考任一已有适配器。

---

## 安装

### 0. 前置条件

- Python 3.9+
- `Codex` CLI 已登录（`Codex -p "hello"` 能跑通）
- `gh` CLI 已登录（用于自动开 PR）
- 你的仓库里已有 `.Codex/skills/guardian-fixer/SKILL.md`

### 1. 一键装

```bash
cd <你的项目根目录>
bash .Codex/skills/bug-pipeline/install.sh
```

### 2. 配置消息源

填写适配器的环境变量。install.sh 会告诉你具体需要什么。

### 3. 验证

在消息渠道发一条假 bug，然后 `tail -f` 日志。看到 `PR url: https://github.com/...` 就说明链路活了。

---

## 设计决策

1. **为什么 LaunchAgent/systemd 不是 cron**：需要持续监听消息渠道的事件流
2. **为什么 `Codex -p` 不是直接调 API**：Codex 订阅 flat rate，API 一次修复 $3+
3. **为什么每个 bundle 一个 git worktree**：修复需要 dirty working dir，不能污染主工作区
4. **为什么 triage 和 fixer 分两个 skill**：triage 快（2 min）、fixer 慢（6-10 min），隔离 budget 和 timeout
5. **为什么 state file 是权威不是 exit code**：`Codex -p` headless 的 exit code 不稳定

---

## 与 harness 的关系

| 依赖 | 是什么 |
|---|---|
| `Codex` CLI | Codex 命令行，headless 模式 |
| Codex 订阅 | flat rate，不按 API 计费 |
| `bug-triage` skill | 翻译用户语言 → 结构化 issue 草稿 |
| `guardian-fixer` skill | 8 Gate 修复闭环 |

`guardian-fixer` 是与仓库工程规范深度耦合的重 skill，本 pipeline 不打包它——你的仓库有自己的实现。
