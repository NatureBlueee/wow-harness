# INV-3 并发写入 (Concurrent Write)

**分类**: 已确认 invariant
**Target skill**: `harness-eng`

## 模式定义

多个并行 WP（或多个并行 agent）对同一个文件/资源/共享状态写入，没有显式的写入 owner 或锁，结果是最后一个写入者覆盖前面所有人的工作——前面的工作**没有报错**，只是消失了。

这是"静默数据丢失"的典型形态。CI 绿、测试过、git 历史干净，但某个 WP 的成果不见了。

## 典型形状

- 两个并行 agent 都往 MEMORY.md 追加内容，后写的覆盖了先写的整个文件（不是 append，是重写）
- 并行 WP 各自更新 `settings.json`，后一个用完整的文件 Write 而不是 Edit，吞掉前一个的字段
- 两个 track 都 regenerate 了同一个 auto-generated 文件，后 regenerate 的版本缺少前一个 track 的输入

## 检测信号

- `git log --follow <file>` 显示同一文件在短时间内被多次完整重写
- 某个 WP 的 LOG 说"已写入字段 X"，但最终文件里没有 X
- 并行 track 的 parallel_contract 里 write_set 有重叠但未指定 seam_owner

## 缓解动作

**注入到 `harness-eng`**：

1. `parallel_contract.write_set` 必须不相交。相交的文件必须提升成 seam，并指定 seam_owner 做单点写入。
2. 共享状态文件（MEMORY.md / settings.json / MANIFEST.yaml）的并发写入一律通过 seam_owner 串行化，不允许并行 track 直接触碰。
3. 禁止 agent 用 `Write` 工具覆盖文件去做"追加"——追加必须用 `Edit` 或 `cat >>`，保证读后写。

## 与 INV-7 的关系

INV-3 是无主接缝（INV-7）在"文件写入"维度的具体后果。INV-7 在计划阶段拦，INV-3 在执行阶段兜底。两层都失守才会出事。
