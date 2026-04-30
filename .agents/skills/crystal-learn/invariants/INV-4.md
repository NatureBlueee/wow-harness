# INV-4 真相源分裂 (Truth Source Split)

**分类**: 已确认 invariant
**Target skills**: `harness-ops`, `lead`, `harness-eng-test`

## 模式定义

同一个事实被写在**两个及以上的地方**，没有标注谁是权威。一开始两处一致；一次修改后，只改了其中一处；从那一刻起，两个副本开始独立演化，agent 读到哪一份取决于运气。

真相源分裂是所有"奇怪的 bug"的温床——不同的 agent 在不同的时间读到不同的事实，行为就会自相矛盾。

## 典型形状

- ADR 说 "X 的上限是 100"，配置文件里写 "50"，代码里 hardcode "200"
- MEMORY.md 说"部署在 region A"，README 说 "region B"，实际部署在 region C
- 同一个字段的定义在 OpenAPI 文档、Pydantic 模型、前端 TypeScript 类型、数据库 schema 四处各自为政
- ADR-030 里的列表和 `ADR-030 Section 12` 里的列表条目数不一致

## 检测信号

- grep 某个数字/名字/路径，出现 3+ 处相同字面值
- 文档说"以 X 为准"但 X 本身也有多个副本
- 审查时发现 agent 引用了某条规则，但规则的另一处副本已被修改且未同步

## 缓解动作

**注入到 `harness-ops`**：

1. 每条跨文件出现的事实必须在一个**唯一位置**声明为权威（single source of truth），其他位置要么引用权威，要么删除。
2. 定期运行"同词检测"——对关键术语做 grep，统计出现次数，数量突然变化触发审查。
3. ADR/PLAN 进入 plan-lock 前必须核对 §X 引用的所有数据点与权威源一致。

**注入到 `lead`**：

4. 每个 Gate 转移时，涉及"这个事实还写在哪"的判断必须显式提问——不是"应该有人想过"，而是现在由我问一遍。

**注入到 `harness-eng-test`**：

5. 测试 fixture 里的常量必须来自权威源（从配置/代码 import），不得 hardcode 字面值。

## 自修复方向硬规则

**修 INV-4 漂移时，第一个动作必须是 grep 最上游 ADR/PLAN 找 ground truth**，然后把所有下游副本对齐到上游。禁止挑熟悉的一侧去平——那会让下游的错版本变成新权威，使漂移方向反转而非消除。
