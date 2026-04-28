---
paths:
  - "{{PROJECT_NAME}}/**"
  - "src/**"
  - "lib/**"
---

# {{PROJECT_NAME}} Repository Structure (Template)

> 这份 rule 是仓库结构的"认知地图"，让 agent 在第一次接触仓库时快速理解目录布局，避免盲目 Glob 扫描。

## 如何使用

1. 替换 `{{PROJECT_NAME}}`、`{{DOMAIN}}` 为你项目的真实名称
2. 下表是骨架示例，填入你项目的实际目录
3. 每条注释回答 "这个目录放什么 / 什么不应该放在这里"

## 目录布局

```
{{PROJECT_NAME}}/
├── AGENTS.md             # Codex 可读的项目规则和分流边界
├── .claude/              # Claude Code 配置 (settings.json + rules/ + skills/ + agents/)
├── .wow-harness/         # wow-harness runtime 数据 (metrics/proposals/guard/tasks)
├── scripts/
│   ├── hooks/            # PreToolUse/PostToolUse 等 hook 实做 (stdlib only)
│   ├── checks/           # 结构化 check 脚本 (INV-* guard, fragment integrity, etc.)
│   ├── ci/               # CI 专用扫描器
│   └── lib/              # 共享 Python lib (sanitize_patterns, claim_patterns, ...)
├── src/ or {{PROJECT_NAME}}/      # 业务代码入口
├── tests/                         # 测试
├── docs/
│   ├── decisions/        # ADR / PLAN / TECH 决策文档
│   ├── issues/           # Guardian issue (ADR-030 closure semantics)
│   └── architecture/     # 架构图与核心概念
└── CLAUDE.md             # Claude Code 根入口, 声明不可妥协约束 + path-scoped rules 触发表
```

## 禁止事项

- `scripts/hooks/` 内禁止 `import requests` / 非 stdlib 依赖（hook 必须 runtime 零依赖）
- `.wow-harness/` 子目录的 runtime content 不能进 git（`.gitignore` 负向模式保留 `.gitkeep` sentinel）
- 不允许在多个地方硬编码 "physical_files=N"——唯一源是 `scripts/ci/count-components.sh`
