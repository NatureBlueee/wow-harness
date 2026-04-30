# INV-0 快照幻觉 (Snapshot Hallucination)

**分类**: 已确认 invariant
**Target skill**: `harness-eng`

## 模式定义

Agent 在做并行编排或计划时，使用"某个时间点拍下的代码快照"作为决策依据——但执行发生在快照之后，仓库已漂移，快照中提到的文件/函数/签名可能已不存在。

决策发生在 T0，执行发生在 T1，两者之间的代码变更被 agent 当成不存在。

## 典型形状

- "我看到 `module/foo.py` 里有 `Handler.process()`，WP-03 改这个函数即可"——实际 `process` 已改名为 `handle_request`。
- "刚才 grep 过 5 个调用方"——实际 grep 是半小时前的结果，其间有两个新增调用方。
- 多个 WP 引用同一份"现状分析文档"，但文档本身从未被更新。

## 检测信号

- 计划文档里的文件名/函数名在当前仓库 grep 不到
- 同一次会话中多次引用"刚才看过的状态"而没有重新 Read
- task-arch 阶段产生的 WP 清单与 Gate 7 实际执行时的文件状态不符

## 缓解动作

**注入到 `harness-eng`**：

1. 任何跨 WP 的代码引用必须在**执行时刻**重新 Read，不能依赖 plan 阶段的 grep 结果。
2. 计划文档的"现状快照"段落必须标注 `snapshot_at: <commit sha>`；当前 HEAD 与该 sha 不同时，agent 必须重跑快照。
3. 多 WP 并行时，第二个 WP 开始前必须 `git status` 对齐。

## 实例池

（案例留空，由后续 PLAN 复盘填充。模式本身已在上游 harness 的多个并行实验中独立出现至少三次，满足升级门槛。）
