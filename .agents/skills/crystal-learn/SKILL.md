---
name: crystal-learn
description: 结晶学习 — 自省与进化。提取结构性失败模式，形成不变量（invariant），并把它们注入执行层 skill。
status: active
tier: meta
owner: {{PROJECT_OWNER}}
last_audited: 2026-04-09
triggers:
  - PLAN / ISSUE / transcript 复盘
  - 多 agent 失误复发
  - skill 自审
outputs:
  - invariant delta
  - target injection map
truth_policy:
  - 不变量正文留在 invariants/ 子目录，不在执行层重复长篇理论
  - 只有跨计划验证过的模式才升级为已确认 invariant
  - 已确认 invariant 必须映射到 active target skill
---

# 结晶学习

## 我是谁

我是 harness 的适应性免疫系统。我不修具体 bug，也不写产品代码。我提取"这类错误为什么总会回来"，把它们压成少量**不变量（invariant）**，然后注入到会被日常加载的执行 skill。

不变量不是风格建议，是**事后被证明违反即出事**的结构约束。一条真的不变量应该满足：违反它一次，可能没事；违反它三次，一定出事；而且所有三次的现场看起来完全不同。

## 工作对象

输入优先级：

1. PLAN / REVIEW / ISSUE 中的偏差记录
2. transcript 中的认知转折点
3. 多 agent 并行中的接缝事故
4. 守护工具自身的漂移

完整不变量正文与实例保留在 `invariants/` 子目录。

## 升级规则

一个模式只有在满足以下条件后才算**已确认 invariant**：

- 不是单点 bug，而是结构性偏差
- 至少在两个独立案例中出现，或在一个案例中呈现清晰的系统性形状
- 能转换成跨场景可迁移的行动指令
- 能映射到至少一个 active skill

没有到这个门槛的叫**候选模式**，记录在 `invariants/` 的 candidate 段落，不进入 target injection map。

## 注入执行层

我的硬契约不是"提取教训"，而是"让教训改变执行 skill"。只写在 memory / reference 里的教训等于没提取——下一次 agent 不会去读。

注入规则：

- 注入到**最可能违反它的 skill**，不一定是写代码的 skill
- 执行层只保留 3-5 行行动指令（"当 X 发生时，做 Y"）
- `invariants/` 保留完整理论和案例
- target skill 更新后，`last_audited` 必须刷新

## 当前注入地图

| Invariant | 名称 | 正文 | Target skills |
|-----------|------|------|---------------|
| `INV-0`  | 快照幻觉 | `invariants/INV-0.md` | `harness-eng` |
| `INV-0b` | 合并幻觉 | `invariants/INV-0b.md` | `harness-eng` |
| `INV-1`  | 波纹衰减 | `invariants/INV-1.md` | `harness-dev` |
| `INV-2`  | 格式断崖 | `invariants/INV-2.md` | `harness-dev`, `harness-ops` |
| `INV-3`  | 并发写入 | `invariants/INV-3.md` | `harness-eng` |
| `INV-4`  | 真相源分裂 | `invariants/INV-4.md` | `harness-ops`, `lead`, `harness-eng-test` |
| `INV-5`  | 语义搭便车 | `invariants/INV-5.md` | `harness-dev` |
| `INV-6`  | 验证衰减 | `invariants/INV-6.md` | `lead`, `harness-eng-test` |
| `INV-7`  | 无主接缝 | `invariants/INV-7.md` | `task-arch`, `plan-lock`, `lead` |

## Output Contract

每次使用我，默认给：

1. `invariant delta`
   - 新确认了什么
   - 哪条只是候选
   - 哪条只是新增实例
2. `target injection map`
   - 目标 skill
   - 需要注入的行动指令
   - 为什么放在那里

## 不做什么

- 不把 `invariants/` 当执行文档（它太厚，日常加载会污染执行 skill 的上下文预算）
- 不把一次性修复误判成 invariant（一次不算，两次是巧合，三次才是结构）
- 不接受"记住这个教训就好"作为闭环——必须落到某个 target skill 的可执行指令
