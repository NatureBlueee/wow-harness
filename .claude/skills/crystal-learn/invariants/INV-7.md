# INV-7 无主接缝 (Seam Without Owner)

**分类**: 已确认 invariant
**Target skills**: `task-arch`, `plan-lock`, `lead`

## 模式定义

两个或多个 WP / 模块 / agent 之间存在共享接口（数据结构、配置、文件、事件、状态），但**没有任何一方被指定为接缝的 owner**。结果是：每一方都认为"另一边会处理"，接缝本身处于无人区，任何边界问题都是"不是我负责的"。

这是并行执行中最危险的失败模式——它不会让 CI 变红，不会让测试失败，它让某个接缝**静默地保持错误状态**，直到集成或生产时才爆发，而那时所有 WP 都已 commit 并 closed。

命名为"无主接缝"是为了让这个状态**可被指认**。未命名的情况下，它以"大家都假设别人会处理"的样子存在，每一步都看起来合理。命名之后，它变成一个 Gate 门禁问题。

## 典型形状

- WP-A 定义一个事件 schema，WP-B 消费这个事件——但没人被指定维护 schema 演进，A 改了格式，B 几周后才发现。
- 两个并行 track 共同写入同一个 `settings.json`，都使用"读取-修改-写入"模式——没有指定谁先谁后，也没有指定冲突处理方。
- PLAN 拆了 5 个 WP，其中 WP-3 和 WP-4 都需要"认证中间件"，但 PLAN 没说谁建、谁改、谁在 Gate 8 验收这个中间件。
- 两个 agent 都引用了 MANIFEST.yaml 的某个字段，但该字段的 owner 是"上游 ADR"——ADR 不是 skill，无法在运行时响应问题。

## 检测信号

- `parallel_contract` 里有 write_set 重叠但没有 `seam_owner` 字段
- 两个 WP 的 TASK.md 都提到同一个文件/接口，措辞不同
- 审查时问"这个接缝谁负责"得到"应该是另一边吧"的回答
- 集成阶段出现的 bug 对应的代码没有任何一个 WP 的 commit 历史

## 缓解动作

**注入到 `task-arch`**：

1. 拆 WP 时，**每个跨 WP 的共享接口必须显式填 seam_owner 字段**。不是建议，是硬字段。
2. 一个 seam 只能有一个 owner，不能"共同负责"。共同负责 = 无人负责。
3. seam_owner 负责：(a) 接缝的初始定义 (b) 接缝的演进决策 (c) Gate 8 时对接缝的端到端验收。

**注入到 `plan-lock`**：

4. plan-lock 的冻结清单包括"所有 seam 的 owner 已分配"。任何一条未分配 → plan-lock 拒绝冻结。

**注入到 `lead`**：

5. Gate 5 → Gate 6 转移时，lead 必须扫描 parallel_contract.write_set 交集；有交集但无 seam_owner → BLOCKED，不允许进 Gate 6。

## seam without owner

这一条短语必须在本文件可被 grep 到，作为 WP-06 AC 6 对 INV-7 自证存在的硬检查：**seam without owner** / **无主接缝** 就是 INV-7 的英中两面。
