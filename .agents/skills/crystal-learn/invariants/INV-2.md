# INV-2 格式断崖 (Format Cliff)

**分类**: 已确认 invariant
**Target skills**: `harness-dev`, `harness-ops`

## 模式定义

Agent 在拼接/转换数据时，假设上游输出是"结构化的"（dict / JSON / YAML），但上游实际输出是"近似结构化的字符串"——大多数时候能用 `json.loads()` 解析成功，某些 edge case 时解析失败。成功路径运行了 99 次，失败的第 100 次产生一个看起来与任何代码无关的崩溃。

命名"断崖"是因为：99% 的输入落在平地上，1% 的输入落下悬崖，中间没有坡。

## 典型形状

- LLM 输出"JSON"，但偶尔包含未转义的内部引号
- 日志行被当作 TSV 解析，但某个字段里偶尔出现制表符
- 配置文件被当作 YAML 解析，但某次手动编辑引入了一个 tab 缩进
- CSV 中偶尔有字段包含换行或逗号

## 检测信号

- 错误日志里出现极低频率的 `JSONDecodeError` / `YAMLParseError` 但没人修
- "大多数时候没问题"成为某个路径的维护状态
- 有 try/except 吞掉解析错误然后走降级分支——降级分支从未被测试

## 缓解动作

**注入到 `harness-dev`**：

1. 任何"解析字符串→结构"的边界必须有**显式的 schema 验证**（pydantic / jsonschema / 自写的 assert），而不是 `json.loads()` 就过。
2. 解析失败不得静默降级。降级路径必须有明确的触发条件和可观测信号。
3. LLM 输出 parsing 走 strict mode（失败 → 重试或显错），不做"尽力而为"。

**注入到 `harness-ops`**：

4. 日志/配置/数据文件的 schema 一旦定义，变更前必须过 INV-4 门禁——格式演进是真相源分裂的常见温床。
