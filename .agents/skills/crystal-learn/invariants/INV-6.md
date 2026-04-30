# INV-6 验证衰减 (Verification Decay)

**分类**: 已确认 invariant
**Target skills**: `lead`, `harness-eng-test`

## 模式定义

验证从"最难验证的层"（端到端用户价值）不断降级到"最容易验证的层"（函数单测、类型检查、CI 绿）。每次降级都有一个看似合理的理由（"E2E 不稳定"、"这个依赖不可用"、"先跑 unit 再说"），但降级不会自己回升——几周后，只有最容易的层还在跑，而那一层跟用户价值几乎没有关系。

关键反差：**"CI 全绿"与"功能真的能用"之间的距离在悄悄变大**。

## 典型形状

- E2E 测试 flaky 被 mark skip → 单元测试通过 = 发布 → 两周后生产出现 E2E 本来会发现的 bug
- 新功能只有 happy path 的单元测试，failure path 和集成完全不测
- "测试覆盖率 85%"很高，但覆盖的是 getter/setter，核心业务逻辑零覆盖
- 所有测试都 mock 了数据库，从未在真实数据库上跑过 migration

## 检测信号

- `@pytest.mark.skip` 数量单调递增
- PR 描述里的测试章节写"依赖已 mock / 简化"
- 修完一个生产 bug 时发现该路径完全没有测试
- golden journey 测试的最后一次运行日期在一个月之前

## 缓解动作

**注入到 `lead`**：

1. 任何 PLAN 必须包含 **golden journeys**——从用户价值链的最后一步倒推回来的端到端验证路径。只走单元测试的 PLAN 不允许进入 Gate 4。
2. Gate 8 验收必须跑至少一条 golden journey 并在 LOG 里留证据。

**注入到 `harness-eng-test`**：

3. 测试金字塔的每一层都要有**本层 owner**，owner 确保本层不被持续 skip。
4. 跳过测试（skip / xfail）必须带 TODO + 回收期限；到期未处理，测试回归 failing 状态（不是 skip），强制有人处理。
5. "Mock 了关键依赖" 的测试不记入有效验证——它只是类型检查，不是行为检查。
