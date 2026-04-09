# Stop Hook: Completion Proposal + Independent Review (ADR-044 §3.4 L3+L4)

你**不是** Evaluator。你是被评估的一方。你的工作是：
1. 写出你做了什么（proposal）
2. 请一个独立 agent 来评你

**禁止自己给自己打分。** 自评有结构性利益冲突（Anthropic: "Agents consistently overpraise their own work"）。

## Step 1: 写 Completion Proposal

将以下 JSON 写入 `.towow/state/completion-proposal.json`：

```json
{
  "session_id": "<当前 session 标识>",
  "timestamp": "<ISO 8601>",
  "summary": "<1-3 句话描述本 session 做了什么>",
  "files_changed": ["<从 git diff 或 risk-snapshot 获取>"],
  "evidence": {
    "tests_run": "<运行了哪些测试，结果如何>",
    "verification_commands": ["<实际执行的验证命令>"],
    "commits": ["<本 session 的 commit hash + message>"]
  },
  "known_limitations": ["<诚实列出已知的未完成项或风险>"],
  "task_reference": "<TASK.md 路径或用户原始指令摘要>"
}
```

**要求**：
- `files_changed` 必须从 `git diff` 或 risk-snapshot 的 `files_touched` 取，**不得凭记忆列举**
- `evidence` 中的测试结果必须是实际运行输出，不是"应该通过"
- `known_limitations` 必须诚实 — 这是给 reviewer 的线索，不是给自己开脱

## Step 2: Spawn 独立 Reviewer

写完 proposal 后，**必须** spawn 一个独立审查 agent：

```
Agent({
  subagent_type: "review-readonly",
  description: "Completion review",
  prompt: `你是独立的 Completion Reviewer（ADR-044 L4）。
你的任务是验证 agent 的 completion proposal 是否与实际代码变更一致。

读取 .towow/state/completion-proposal.json，然后：

1. **Proposal vs Reality**：git diff 的实际变更是否与 proposal.files_changed 一致？有遗漏吗？
2. **Evidence 可信度**：proposal.evidence 中声称的测试/验证，结果是否真实？
3. **半成品检查**：变更文件中有没有 TODO/FIXME/HACK？有没有 dead code？
4. **契约一致性**：如果改了 API/config/路由，所有引用处是否同步更新？
5. **已知限制诚实度**：proposal.known_limitations 是否遗漏了明显风险？

评分（每维 1-5，任何维 < 3 = FAIL）：
- Completeness: proposal 是否覆盖所有实际变更
- Honesty: evidence 和 limitations 是否真实
- Quality: 代码变更本身的质量
- Consistency: 跨文件/跨层的一致性

输出格式：
## Verdict: PASS / FAIL
## Scores: Completeness X/5, Honesty X/5, Quality X/5, Consistency X/5
## Findings: [具体发现列表]
## Recommendation: [如果 FAIL，具体要修什么]`
})
```

## Step 3: 根据 Reviewer 裁决行动

- **Reviewer 说 PASS** → 你可以 Stop
- **Reviewer 说 FAIL** → 按 Recommendation 修复，修复后再尝试 Stop
- **Reviewer spawn 失败**（超时/权限等）→ 降级为 PreCompletionChecklist 自检（下方），但必须在输出中声明 "独立审查未执行，以下为自检降级"

## 降级 Fallback: PreCompletionChecklist（仅当 reviewer 不可用时）

如果因环境限制无法 spawn reviewer，执行以下自检：

1. **Git 状态**: 所有新文件是否已 `git add`？是否有未保存的变更？
2. **测试**: 如果有代码变更，相关测试是否通过？
3. **文档一致性**: 代码变更是否需要更新文档？
4. **无半成品**: 是否有 TODO/FIXME/HACK 被遗留？
5. **契约一致性**: API 类型、路由路径、配置 key 是否在所有引用处一致？

**但必须标注**：这是自检降级，不是独立审查。
