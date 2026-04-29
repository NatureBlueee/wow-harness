---
plan_id: PLAN-H9
title: harness 多窗口邮箱机制工程化（inbox 路径 + 5 hook + Nature 演练）
status: Accepted (5 hook 落地 + Nature 真实演练 PASS 2026-04-28 [ADR-H9 附录 A.2] + reviewer task #17 完成)
drafted: 2026-04-28
drafter: Nature（AI 助手协助）
signer: 待非起草 reviewer 复核（task #17）— 不享 H0 §3.4 单签例外
related_adrs:
  - ADR-H9-mailbox.md（本 PLAN 决策真相源）
  - ADR-H0-meta-charter.md（6+1 元规约 + commit body 治理）
  - ADR-058 §D1（hook IO schema 红线 + 16 helper API）
  - ADR-038 D10（.towow/proposals/ self-trace 来源）
related_issues: []
line_budget: ≤500 行（H0.2）；预算 ~400 行
verification_chokepoint: lint-hook-output.py（pre-commit）+ schema/message-v1.json（jsonschema validate）+ Nature 演练录像
---

# PLAN-H9 — harness 多窗口邮箱机制工程化

## 0. 本 PLAN 在 H 系列拓扑中的位置

- 拓扑序：`H0 → H9 → H2 → H3 → H4 → H1 → {H5/H6/H8 并行}`（H7 已撤销见 `.towow/log/harness-self-symptoms.md` §4.3）
- 上游：ADR-H0 6+1 元规约（已落地 commit `2c162d04`）+ ADR-H9 决策（本 PLAN 同期 commit `be03f44b`）
- 下游：H2 / H3 / H4 / H1 / H5 / H6 / H8 都依赖 H9 邮箱作为多窗口通信底座
- 出口条件：本 PLAN 8 WP 全部 PASS + Nature 演练录像/截图附 ADR-H9 末尾 + 非起草 reviewer 签字 → ADR-H9 status 转 Accepted

## 1. 目标

把"主窗口人脑协调员"物理化为"文件队列 + hook 自动注入 + ScheduleWakeup 自循环"。Nature 启动主窗口后只说"开始 harness 系列"，后续多窗口通信全部走 `.towow/inbox/`，不再手动 ping / 复制粘贴。

## 2. 范围

**In scope**：
- `.towow/inbox/` 路径树初始化 + JSON Schema 真相源
- 5 个 hook 实施（write-ledger / validate / inject-on-start / poll / ack）
- `.claude/settings.json` PostToolUse + SessionStart 注册
- pre-commit lint chokepoint 校验（lint-hook-output.py = 0 violation）
- Nature 演练 1 次（端到端 ≤ 60s + 录像/截图）

**Out of scope**：
- 现有 hook（guard-feedback / loop-detection / risk-tracker / session-start-magic-docs / session-start-reset-risk）的改造——H9 是追加，不改既有
- proposal-v1 schema 迁移——ADR-H9 §4 已签字"schema 分歧不复用"，本 PLAN 不动 trace-analyzer.py
- 多窗口物理隔离——交给 ADR-042 worktree 模式，H9 只管通信

## 3. WP 拆解表（8 WP）

| WP | 主题 | 产物 | DoD 关键证据命令 | 估时 | depends_on |
|----|------|------|------------------|------|------------|
| WP-01 | schema 真相源 | `.towow/inbox/schema/message-v1.json` + 路径树 | `python3 -c "import jsonschema, json; jsonschema.Draft202012Validator.check_schema(json.load(open('.towow/inbox/schema/message-v1.json')))"` 退出码 0 | 0.3d | — |
| WP-02 | write-ledger | `scripts/hooks/inbox-write-ledger.py` | `python3 scripts/checks/lint-hook-output.py scripts/hooks/inbox-write-ledger.py` 0 violation；写测试 inbox 文件后 `.towow/log/hook/inbox-write.jsonl` 新增 1 行 | 0.5d | WP-01 |
| WP-03 | validate | `scripts/hooks/inbox-validate.py` | lint 0；写非 schema-v1 文件后该文件被 mv 到 `.towow/inbox/quarantine/` + ledger 1 行 | 0.5d | WP-01 |
| WP-04 | inject-on-start | `scripts/hooks/inbox-inject-on-start.py` | lint 0；启动一个 CC session（main/unread/ 有 1 文件）后 systemMessage 中能 grep 到该消息 msg_id | 0.5d | WP-01 |
| WP-05 | poll 自循环 | `scripts/hooks/inbox-poll.sh` + ScheduleWakeup 调用 | lint 0（虽 shell 不出 stdout JSON 也确认无手搓 print）；模拟 1200s wakeup 后再次注入 | 0.5d | WP-04 |
| WP-06 | ack 回执 | `scripts/hooks/inbox-ack.py` | lint 0；调用后 main/unread/<msg> 消失、main/processed/<msg> 出现、对应 window-Hx/acks/<msg-id>.md 出现 | 0.4d | WP-01 |
| WP-07 | settings 注册 + 全 lint | `.claude/settings.json` PostToolUse + SessionStart 增段 | `python3 -c "import json; d=json.load(open('.claude/settings.json')); print(any('inbox-write-ledger' in str(d['hooks'])))"` True；`python3 scripts/checks/lint-hook-output.py scripts/hooks/inbox-*.py` 0 violation | 0.3d | WP-02..06 |
| WP-08 | Nature 演练 | 录像/截图 + ADR-H9 末尾附录 + symptoms.md §4.4 通过记录（无症状则也写一行 PASS） | 录像可见：子窗口写消息 → ≤60s 主窗口 SessionStart 注入 → 主窗口 ack → 子窗口下次启动看到 ack | 0.5d | WP-07 |

**总估时**：3.5d 串行 + 0.5d Gate / reviewer = ~4d（plan §3.3 估时 3d，多 0.5d 用于 schema 真相源 + 全 lint，可接受）

## 4. WP 详细

### 4.1 WP-01 schema 真相源 + 路径树初始化

**产物**：
- `.towow/inbox/schema/message-v1.json`（JSON Schema Draft 2020-12）
- `.towow/inbox/{main/{unread,in-flight,processed},quarantine,window-h0,window-h1,window-h2,window-h3,window-h4,window-h5,window-h6,window-h8,window-h9}/`（含每个 window-Hx 下的 acks/）
- `.towow/inbox/.gitkeep` 让 git track 空目录

**JSON Schema 字段**：见 ADR-H9 §4；message-v1.json 必须 1:1 反映 ADR-H9 §4 frontmatter 字段，所有必填字段 `required` 列出，`kind` / `priority` / `related_h` 用 enum 锁死。

**DoD**：
- `python3 -c "import jsonschema, json; jsonschema.Draft202012Validator.check_schema(json.load(open('.towow/inbox/schema/message-v1.json')))"` 退出码 0
- `find .towow/inbox/ -type d | wc -l` ≥ 14
- `git status` 显示路径树进入 git track（通过 .gitkeep）

### 4.2 WP-02 inbox-write-ledger.py

**触发**：PostToolUse Edit|Write，matcher 路径含 `.towow/inbox/`

**职责**：检测 inbox 写入 → 追加 jsonl ledger（`.towow/log/hook/inbox-write.jsonl`）→ 不阻断主流程

**实施关键**：
- 不绕开 `_hook_output`：要么 `from _hook_output import post_tool_use_inject` 用 helper，要么完全沉默 early return（PostToolUse 空 stdout = no-op；模型对照 `scripts/hooks/risk-tracker.py`）。绝对禁止手搓 `print(json.dumps(...))` 等三种 banned form（ADR-058 §D1）
- ledger 字段：ts / ts_unix / rel_path / tool / size_bytes / sender / msg_id / kind / priority / related_h（落地实现比初版 spec 多 4 字段，可观测性更全）
- 检测 `len(.towow/inbox/main/unread/) ≥ INBOX_OVERFLOW_THRESHOLD`（默认 50，env 可覆盖）时同步写 `.towow/log/hook/inbox-overflow.jsonl`（§6.1 失败模式 1）
- 顶层 `try/except BaseException → sys.exit(0)` 兜底：非零 exit = CC 解读 deny → 锁仓，业务 hook 必须吞掉所有异常

**DoD**（落地实证 ✓ 2026-04-28 commit-anchor 见 §11）：
- `LINT_HOOK_OUTPUT_INCLUDE_ALL=1 python3 scripts/checks/lint-hook-output.py scripts/hooks/inbox-write-ledger.py` 0 violation ✓
- 模拟 Write `.towow/inbox/window-h9/h9-20260428-160000-smoke01.md` 后，`.towow/log/hook/inbox-write.jsonl` 末行 `msg_id == "h9-20260428-160000-smoke01"` ✓
- 模拟 4 文件 + 阈值=3，`.towow/log/hook/inbox-overflow.jsonl` 一行 `unread_count=4 / threshold=3` ✓
- 性能：out-of-scope 路径 p50=32ms（含 python startup），< 50ms ADR-058 §D1 budget ✓

### 4.3 WP-03 inbox-validate.py

**触发**：PostToolUse Edit|Write，matcher 同 WP-02

**职责**：用 message-v1.json schema 校验 frontmatter；不合规 mv 到 quarantine/

**实施关键**：
- `import jsonschema, yaml` 解析 frontmatter
- 不合规：原文件 mv 到 `.towow/inbox/quarantine/<orig-name>-<ts>.md`，写 `.towow/log/hook/inbox-quarantine.jsonl` 一行
- 合规：不动文件，inject_context 空
- ack 类型消息（kind=ack）必须有 ack_for 字段，否则 quarantine

**DoD**：
- lint 0 violation
- 写非 schema-v1 文件 → 文件移到 quarantine + ledger 1 行
- 写合规文件 → 文件保留原位 + 无 quarantine 事件

### 4.4 WP-04 inbox-inject-on-start.py

**触发**：SessionStart matcher=*

**职责**：主窗口启动时读 `.towow/inbox/main/unread/`，把所有未读消息以 systemMessage 注入；同时清理 `in-flight/` 中的崩溃残留（§6.2 失败模式 2）

**实施关键**：
- `from _hook_output import session_start_inject`
- 检测 cwd 是否是主仓 root（`scripts/hooks/find-towow-root.sh`）；不是则 inject 空
- 注入格式：分章节列出每条 unread msg（msg_id / sender / ts / kind / priority / 正文摘要 ≤200 字）
- in-flight/ 残留 mv 回 unread/（msg_id 幂等，重新注入不重复处理）
- 注入文本总长度 ≤ 4096 字（CC SystemMessage 友好上限）；超额则注入"unread overflow，请人工 archive"

**DoD**：
- lint 0 violation
- 启动 CC session（main/unread/ 1 测试文件）后，session systemMessage 中 grep msg_id 命中
- in-flight/ 1 残留 → 启动后 mv 回 unread/

### 4.5 WP-05 inbox-poll.sh（agent/shell 切分版）

**触发**：主 agent 在 ScheduleWakeup 触发后用 Bash tool 主动调用本脚本

**职责**：纯状态检查 + 推荐间隔输出（KV 文本）。不直接调 ScheduleWakeup——见下方 spec letter 修订 disclosure。

**Spec letter 修订（落地阶段发现的工程不可行性，2026-04-28 落地 commit-anchor 见 §11）**：

PLAN-H9 §4.5 草稿原文写"shell 脚本 ... 内部调用 ScheduleWakeup MCP"。落地阶段发现 ScheduleWakeup 是 **CC agent loop 内部 tool API**，shell 进程没有合法 RPC 入口直接调用——必须由主 agent（CC 主窗口）在 agent loop 里调用。本脚本因此切分为两层：

- **[shell 层] inbox-poll.sh**：状态检查 + 推荐间隔 → stdout KV 文本
- **[agent 层] 主 agent**：读 stdout 后自行决定下次 ScheduleWakeup 时机

切分边界已落 ADR-H0 修订建议（`note=` 行直接写在脚本输出里供未来 grep）。

**实施关键**：
- shell 脚本（KV 文本输出，不出 stdout JSON）
- `set -euo pipefail`；GNU/BSD `stat` 兼容性（`stat -c %Y` Linux vs `stat -f %m` macOS）
- 默认间隔常量：`INBOX_POLL_NORMAL_WAKE=1200s`（20min cache 友好），`INBOX_POLL_P0_WAKE=300s`（CC ScheduleWakeup 最短允许下限）
- 输出字段：`unread_count`、`p0_exists`、`oldest_unread_age_seconds`、`recommended_wake_seconds`、`note`

**DoD**（落地实证 ✓ 2026-04-28 commit-anchor 见 §11）：
- shell 脚本不出 stdout JSON 的物理校验（reviewer P1-1 修法：lint-hook-output.py AST 是 Python-only，对 .sh 必然 vacuously 0 命中 = misleading；改为显式 grep）：`grep -nE '^[^#]*(print\(json\.dumps|echo.*permissionDecision|echo.*systemMessage)' scripts/hooks/inbox-poll.sh` 必须 0 命中（active-code only；comment 内的 banned form 词法引用是 disclosure，不是活路径）✓
- Smoke 1（empty unread）→ `unread_count=0 / p0_exists=false / recommended_wake_seconds=1200` ✓
- Smoke 2（P1 only）→ `unread_count=1 / p0_exists=false / oldest_unread_age_seconds>0 / recommended_wake_seconds=1200` ✓
- Smoke 3（P0 present）→ `p0_exists=true / recommended_wake_seconds=300` ✓
- 主 agent 演练：ScheduleWakeup → Bash 调脚本 → 读 stdout → 决定下次 wake → 留待 WP-08 端到端演练验证

### 4.6 WP-06 inbox-ack.py

**触发**：主窗口手动调用（处理完一条 unread 消息后）；CLI 工具，**不是** CC hook

**职责**：mv unread/<msg> → processed/<msg> + 在原 sender 的 acks/ 目录写 ack 文件

**实施关键**：
- 命令行参数：`python3 scripts/hooks/inbox-ack.py --msg-id <id> --sender <window-Hx>`
- 写 ack 时生成新 msg_id（格式 `main-<YYYYMMDD>-<HHMMSS>-<sha256[:6]>`；同秒重 ack 同 orig 撞名→被 Step 2 反扫捕获不双写）
- 幂等：反扫 `<sender>/acks/` 找 frontmatter `kind=ack && ack_for==<orig>`，命中→直接 noop
- mv 阶段：unread 不在则跳过（已 processed 或丢失）；processed 已存在同名→删 unread 副本（msg_id 幂等保证内容一致）
- 主消息 related_h fallback：unread/→processed/→默认 H9
- ack 不出 stdout JSON；error 走 stderr（参数错误提示用，不是 hook decision）
- 顶层 try/except BaseException → exit 0

**DoD**（落地实证 ✓ 2026-04-28 commit-anchor 见 §11）：
- lint 0 violation：`LINT_HOOK_OUTPUT_INCLUDE_ALL=1 python3 scripts/checks/lint-hook-output.py scripts/hooks/inbox-ack.py` exit=0 ✓
- AST 物理校验 banned form hits=0 ✓
- 行数 202 ≤ 300 ✓
- Smoke 1（basic）→ unread mv processed + window-h9/acks/main-*.md 生成 + frontmatter schema-v1 jsonschema validate PASS（含 `kind=ack → ack_for required + ack_required=false` allOf 子句）✓
- Smoke 2（idempotency）→ 同 msg-id 重 ack 仍只 1 份 ack 文件 ✓
- Smoke 3（invalid sender）→ stderr 人类可读错误 + exit 0 ✓
- Smoke 4（second message）→ 不同 msg-id 新 ack 文件正确生成（共 2 份）✓

### 4.7 WP-07 settings 注册 + 全 lint

**产物**：`.claude/settings.json` PostToolUse + SessionStart 段追加 inbox-write-ledger.py / inbox-validate.py / inbox-inject-on-start.py 三条注册（poll.sh / ack.py 不走 CC hook 注册）

**实施关键**：
- 现有 PostToolUse Edit|Write 段已有 3 hook（guard-feedback / loop-detection / risk-tracker）；H9 追加 2 个，total 5 个
- 现有 SessionStart 段已有 2 hook（reset-risk / magic-docs）；H9 追加 1 个，total 3 个
- 顺序：H9 hook 排在最后（不影响现有 hook 时延）

**DoD**（落地实证 ✓ 2026-04-28 commit-anchor 见 §11）：
- PostToolUse 段 H9 hook 注册 ≥ 2：`python3 -c "import json; d=json.load(open('.claude/settings.json')); print(sum('inbox-' in str(h) for h in d['hooks']['PostToolUse'][0]['hooks']))"` = 2（inbox-write-ledger + inbox-validate）✓
- SessionStart 段 H9 hook 注册 ≥ 1：`python3 -c "import json; d=json.load(open('.claude/settings.json')); print(sum('inbox-inject' in str(h) for h in d['hooks']['SessionStart'][0]['hooks']))"` = 1（inbox-inject-on-start）✓
- JSON syntax valid：`python3 -c "import json; json.load(open('.claude/settings.json'))"` exit=0 ✓
- 4 个 H9 Python hook 各自 lint exit=0：`LINT_HOOK_OUTPUT_INCLUDE_ALL=1 python3 scripts/checks/lint-hook-output.py scripts/hooks/inbox-{write-ledger,validate,inject-on-start,ack}.py` 全 0 ✓
- inbox-poll.sh active-code banned form grep exit=1（无匹配）✓
- 端到端 hook chain integration smoke：合规消息写入 unread/ → write-ledger 写 jsonl 1 行（含 sender/msg_id/kind/priority/related_h 5 字段）+ validate 不动消息 + inject-on-start 输出 schema-correct `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}` ✓
- 现有 hook 未被打乱（guard-feedback / loop-detection / risk-tracker / reset-risk / magic-docs 仍按原顺序）✓

### 4.8 WP-08 Nature 演练 + 录像

**目标**：端到端验证 H9 邮箱机制可用 → ADR-H9 转 Accepted 的最后凭证

**演练脚本**：
1. 启动主窗口（CC session A），不说"开始 harness 系列"以外的指令
2. 启动子窗口（CC session B in `.worktrees/hanis-Hx-test/`），写测试消息到 `.towow/inbox/window-Hx/unread/test-XXX.md`（按 message-v1 schema）
3. 等待主窗口 ScheduleWakeup 触发（≤ 1200s）或子窗口 P0 强制 wake（≤ 60s）
4. 主窗口 SessionStart 注入测试消息内容
5. 主窗口调 inbox-ack.py 写 ack
6. 子窗口下次启动 SessionStart 看到 ack

**DoD**：
- 录像 / 截图序列附 ADR-H9 末尾"附录 A"段
- 端到端时间机器证据（reviewer P1-2 修法：录像 timer 是人眼读，不算 H0.6 机器可生成）：`.towow/log/hook/inbox-write.jsonl` 子→主消息行 + `.towow/inbox/main/processed/<msg-id>.md` 文件 mtime 对比，delta ≤ 60s（P0 路径）或 ≤ 1200s（默认轮询）；命令：`python3 -c "import json,os,sys; sub=json.loads(open('.towow/log/hook/inbox-write.jsonl').readlines()[-2]); main_mtime=os.path.getmtime('.towow/inbox/main/processed/'+sub['msg_id']+'.md'); print(main_mtime - sub['ts_unix'])"` ≤ 60 / 1200
- `.towow/log/harness-self-symptoms.md` 追加一行 WP-08 PASS 记录（如有症状则记录新症状）
- ADR-H9 status: Proposed → Accepted（带签字 reviewer）

## 5. Verification Matrix（DoD 汇总）

| 维度 | 命令 | 期望 | WP |
|------|------|------|-----|
| schema 合法 | `python3 -c "import jsonschema, json; jsonschema.Draft202012Validator.check_schema(json.load(open('.towow/inbox/schema/message-v1.json')))"` | 退出码 0 | WP-01 |
| 5 hook lint | `python3 scripts/checks/lint-hook-output.py scripts/hooks/inbox-*.py scripts/hooks/inbox-*.sh` | 0 violation | WP-02..07 |
| 行数限制 | `wc -l docs/decisions/ADR-H9-mailbox.md docs/decisions/PLAN-H9-mailbox.md scripts/hooks/inbox-*.py` | ADR ≤300 / PLAN ≤500 / 单 hook ≤500 | 全 WP |
| 端到端时延 P0 | 演练录像 timer | ≤ 60s | WP-08 |
| 端到端时延默认 | 演练录像 timer | ≤ 1200s | WP-08 |
| ledger 落盘 | `wc -l .towow/log/hook/inbox-write.jsonl` 写入测试后 | ≥ 1 | WP-02 |
| quarantine 工作 | 写非 schema-v1 文件后 `ls .towow/inbox/quarantine/` | ≥ 1 文件 | WP-03 |
| ack 幂等 | 重复调用 inbox-ack.py 同 msg_id | 退出码 0 + acks/ 目录文件数不增 | WP-06 |
| settings 注册 | `grep inbox- .claude/settings.json` | 命中 ≥ 3 行 | WP-07 |
| H0.2 ADR 行数 | `wc -l docs/decisions/ADR-H9-mailbox.md` | ≤ 300 | 收尾自检 |
| H0.2 PLAN 行数 | `wc -l docs/decisions/PLAN-H9-mailbox.md` | ≤ 500 | 收尾自检 |
| H0.4 自指 | `grep -nE '(TBD\|后续讨论\|待协调员决定)' docs/decisions/ADR-H9-mailbox.md docs/decisions/PLAN-H9-mailbox.md` | 仅元层定义命中（参 ADR-H0 §6 例 4） | 收尾自检 |

## 6. 跨子计划冲突登记（H0.5）

| 文件 | 与谁冲突 | 处置 |
|------|---------|------|
| `.claude/settings.json` PostToolUse 段 | 后续 H 子计划如需注册新 PostToolUse hook | 顺序追加，H9 排前；后续 H 起草前先 grep 当前 settings.json 状态 |
| `.claude/settings.json` SessionStart 段 | 后续 H 子计划如需注册新 SessionStart hook | 同上 |
| `scripts/hooks/_hook_output.py` | 不动 | H9 仅消费 helper API，不动真相源；如需扩展 helper 走 ADR-058 修订路径 |
| `scripts/checks/lint-hook-output.py` | 不动 | H9 仅消费 lint，不动；新 hook 文件名 `inbox-*` 自动被 lint 扫到 |
| `.towow/inbox/` 路径树 | H9 独占 | 后续 H 子计划如需写邮箱必须按 message-v1 schema |
| `.towow/log/hook/inbox-*.jsonl` | H9 独占落点 | 后续 H 子计划不得写同名 ledger |

**未登记冲突处置**：git 时间戳先到先得；后到方在 commit body "未登记冲突"段补述（H0.5）。

## 7. 自检（H0.1-H0.6 + H0.meta）

- **H0.1 施工隔离**：本 PLAN scope = `docs/decisions/PLAN-H9-mailbox.md`；各 WP 实施 scope 详见 §3 表格 / §4 各 WP 产物列；每 WP commit body 必须显式列出 scope 路径
- **H0.2 节流限速**：本 PLAN 目标 ≤ 500 行（实际行数 wc -l 自报）；ADR-H9 ≤ 300 已落地
- **H0.3 执检分离**：起草人 Nature（AI 助手协助），签字人待非起草 reviewer 复核（task #17 spawn `towow-review-toolkit:reviewer`）；H9 不享 H0 §3.4 单签例外
- **H0.4 自指禁止**：H9 修"协调断裂"，本 PLAN 自身不许提议新 branch 隔离（已遵守，沿用 ADR-H0 main 直接 commit）；不许"待协调员决定"（已遵守，§4.7 主窗口由 inbox 注入而非人手协调）
- **H0.5 跨子计划协调**：见 §6 冲突表
- **H0.6 证据机械化**：每 WP DoD 都括注证据生成命令（§3 表格 + §5 verification matrix）；reviewer 复跑命令必须返回相同结果
- **H0.meta**：本 PLAN 引用 H0（已落地）+ H9 自身 + ADR-H9 / PLAN-H9 配套；其他兄弟用"后续 H 子计划"中性表述（§6 / §7）

**症状词字面命中检查**：本 PLAN §4.4 / §6 / §7 出现"协调断裂""人脑协调员""待协调员决定（反例）"以**陈述实例 / 元层反例**形式出现，自身行为命中 = 0；元层定义不计入。

## 8. 生效与变更

- **生效**：本 PLAN 所有 8 WP PASS + Nature 演练录像 + 非起草 reviewer 签字 → ADR-H9 status 转 Accepted
- **变更**：WP 拆解可在每 WP 实施时 inline 微调（不影响 ADR-H9 schema），微调记入对应 WP commit body；新增 WP / 删除 WP 必须本 PLAN 修订 + Nature 单签
- **回滚**：参 plan §3.3.4 失败回滚策略 4 档；H9 任一 WP broken 触发"重 broken"时 `git revert` 该 WP commit + 写 symptoms.md 新症状

## 9. RACE-DISCLOSURE — 本 PLAN 入库 race 真实时序

> **登记于**: 2026-04-28 14:56 CST（首次披露），后续随本 commit 落入 git history
> **失败模式**: parallel session git race（同日同一 PLAN-102 协调员 session 第三次复发；前两次见 memory `feedback_parallel_session_git_race_post_commit_verify` + `docs/decisions/tasks/PLAN-101-WP-08/RACE-DISCLOSURE.md`）
> **代码影响**: 零（PLAN-H9-mailbox.md 240 行全部正确落 main）
> **真相源影响**: commit message 错配，git log/blame 后续追溯需配合本节解读

### 9.1 时间线

| 时刻 | session A（H9 起草，本 dev session） | session B（PLAN-102 协调员 session） |
|---|---|---|
| 14:54:50 | `git add docs/decisions/PLAN-H9-mailbox.md` staged | (在做 Gate 6 review 3 文件 + PLAN-101 WP-04/08 5 文件) |
| 14:55:??（数十秒内） | (准备 commit) | `git add` Gate 6 + WP-08 共 8 文件 staged，叠在 A 的 1 文件之上 |
| 14:56:08 | `git commit -- docs/decisions/PLAN-H9-mailbox.md` 试图执行 | 同时 `git commit` (no pathspec) 执行 → **B 的 commit 先到达，把全部 9 文件一锅端** |
| 14:56:08 | A 收到 ref-lock mismatch | B 完成 commit `fcdb83c1`，message 后续被改为"docs(mixed)"承认 race |

### 9.2 实际 commit 内容（git show --stat fcdb83c1）

```
commit fcdb83c1 (docs(mixed): Gate 6 task review 3 报告 + PLAN-101 WP-04/WP-08 平行 session hitchhike)
 docs/decisions/PLAN-H9-mailbox.md                  | 240 +++++++++++   ← H9（本 PLAN）
 docs/decisions/tasks/PLAN-101-WP-08/LOG.md         | 135 +++++-        ← PLAN-101 WP-08
 .../freeze-account/gate6-reviews/01-arch-review.md | 177 ++++++++      ← PLAN-102 Gate 6
 .../gate6-reviews/02-consistency-review.md         | 290 +++++++++++++ ← PLAN-102 Gate 6
 .../gate6-reviews/03-security-redteam-review.md    | 148 +++++++       ← PLAN-102 Gate 6
 scenes/业务场景示例-admin/demo-app/src/App.tsx     |   2 +             ← PLAN-101 WP-08
 .../demo-app/src/layouts/AdminLayout.tsx           |   1 +             ← PLAN-101 WP-08
 .../demo-app/src/lib/admin-client.ts               |  91 ++++          ← PLAN-101 WP-08
 .../demo-app/src/pages/OnboardingScenesPage.tsx    | 458 +++++++++++++ ← PLAN-101 WP-08
 9 files changed, 1535 insertions(+), 7 deletions(-)
```

3 个独立 session（H9 / PLAN-101 WP-08 / PLAN-102 Gate 6）的工作混在同一 commit 下，message 是协调员 session 的"docs(mixed)"。

### 9.3 为什么 `git commit -- <pathspec>` 没救

`git commit -- file` 只在执行该命令的 git 进程内部生效——它告诉**自己的 commit** 只包含这些 pathspec。但 race window 在 `git add` 完成到 `git commit` 启动之间：别的 session 此时调用 `git commit`（不带 pathspec）会把 index 里**所有 staged 的内容**一锅端，包括我已 staged 但还没来得及 commit 的 PLAN-H9-mailbox.md。

memory `feedback_parallel_session_git_race_post_commit_verify` 已记录该升级路径。今天是同款问题第三次发生（前两次：上午 PLAN-102 Batch C+D `ca37b2c5/301a4780` amend pair；下午 PLAN-101 WP-08 `b6d53e48`）。

### 9.4 实际影响评估

| 维度 | 影响 | 备注 |
|---|---|---|
| 代码完整性 | ✅ 0 | PLAN-H9-mailbox.md 240 行正确落 main，本 §9 追加后行数升至 ~290（仍 ≤500 行 H0.2 限） |
| ADR-H0 §4 commit body 必填段 | ❌ 错配 | fcdb83c1 message 不含"自指自检"/"行数自报"段（被协调员 session 的 race-survivor message 覆盖） |
| H0.1 施工隔离 | ⚠ 名义违反 | fcdb83c1 scope 跨 H9 + PLAN-101 + PLAN-102，但 race 不可控；该 commit message 已自报混合 scope 真相 |
| git history 可追溯性 | ⚠ 降级 | git blame PLAN-H9-mailbox.md 会指向 fcdb83c1 而非独立 H9 commit；本 §9 + symptoms.md §4.4 形成双向引用兜底 |
| 下游 H9 实施（WP-01..08） | ✅ 不影响 | 本 PLAN 已在 main HEAD 链上，WP-01 schema 真相源等可正常起跑 |

### 9.5 不做 reset / amend 的理由

1. **fcdb83c1 不是 H9 独有**——含 PLAN-101 + PLAN-102 共 8 文件别 session 真实工作，reset 会破坏别人的工作（与 PLAN-101 WP-08 RACE-DISCLOSURE §"不做 reset / amend 的理由" §1 同源）
2. **本 §9 + `.towow/log/harness-self-symptoms.md` §4.4** 已经形成双向 disclosure，git blame 落到 fcdb83c1 的人会被引导到本节
3. **commit message 真相源升级**：fcdb83c1 在 race 后已被改为"docs(mixed)"承认 race，git log 上读者第一眼就看到 race 标签，不再误以为 H9 没起草

### 9.6 ADR-H0 §4 必填段补落（在本 §9 入库 commit 中）

由于 fcdb83c1 message 错配，ADR-H0 §4 commit body 模板的"自指自检"+"行数自报"段无法在 fcdb83c1 中补齐（该 commit 不归 H9 owner 控制）。本 §9 入库 commit `01c2efca` 已显式包含（reviewer P1-6 修法：补落实证 hash，便于事后 audit 跑 `git log --format=%B 01c2efca` 复核）：

- **修问题症状词**：协调断裂 / 同 commit 冲突 / race
- **自身在产物中字面命中（应为 0；元层定义除外）**：0（本 §9 + symptoms §4.4 出现"协调断裂""race""同 commit 冲突"均为元层声明实例：disclosure 描述 + 反例陈述 + 处置规则；自身行为命中 = 0）
- **scope 路径列表（H0.1）**：`docs/decisions/PLAN-H9-mailbox.md`（追加 §9）+ `.towow/log/harness-self-symptoms.md`（追加 §4.4）—— 双文件 disclosure 互引用，scope-coupled 例外
- **跨子计划冲突登记（H0.5）**：本 commit 与 fcdb83c1 race 冲突已在 §9.1 / §9.2 / §9.3 显式登记
- **本 commit 新增/修改子计划文档单文件最大行数**：PLAN-H9-mailbox.md 324 行（≤500，行数自报段 ✓）
- **ADR 总行数（如有）**：本 commit 不动 ADR

### 9.7 后续动作

1. **本节落入 PLAN-H9-mailbox.md**: 单独 commit，与 symptoms.md §4.4 同 commit 入库（H0.1 例外：disclosure 双向引用 scope-coupled）
2. **三段式 git stash 协议落地**: 本 commit 起 H 系列后续全部走 `git stash --keep-index → git add <path> → git commit -- <path> → git stash pop`，彻底关闭 race window（symptoms.md §4.4 处置 #3）
3. **ADR-H0 修订建议清单**:
   - "H 文件入库于非 H commit"边界 case 处置规则（symptoms.md §4.4 处置 #5）
   - 三段式 git stash 协议作为 H 系列 commit 治理硬规（symptoms.md §4.4 处置 #4）
4. **memory 升级**: `feedback_parallel_session_git_race_post_commit_verify` 应增加"2026-04-28 同日三次复发 + 三段式 stash 协议"标注（待 Nature 复盘时整理）

### 9.8 引用

- 本 §9 入库 commit: `01c2efca` (docs(harness-H9 H0): RACE-DISCLOSURE — 双向引用 commit，pathspec lock + 原子 -o 协议关闭 race window)
- 本次 race commit: `fcdb83c1` (docs(mixed) message, 含 H9 + PLAN-101 WP-08 + PLAN-102 Gate 6 共 9 文件)
- 同日前次 race: `b6d53e48` (PLAN-101 WP-08 hitchhike, 见 `docs/decisions/tasks/PLAN-101-WP-08/RACE-DISCLOSURE.md`)
- 同日首次 race: `ca37b2c5` / `301a4780` amend pair（PLAN-102 Batch C+D，见 memory `feedback_parallel_session_git_race_post_commit_verify`）
- 防护教训: memory `feedback_parallel_session_git_race_post_commit_verify`, `feedback_local_worktrees_only`
- 双向引用: `.towow/log/harness-self-symptoms.md` §4.4 PLAN-H9-mailbox.md 入库 race
- reviewer 复核: feature-dev:code-reviewer (claude-opus-4-7, 2026-04-28) PASS_WITH_NOTES → 修 P0-1 + P1-1/3/4/5/6 + P2-3 → 本 commit 收口

## 10. reviewer 复核 followup（未修 P2 登记）

reviewer feature-dev:code-reviewer (claude-opus-4-7, 2026-04-28) 第一轮 PASS_WITH_NOTES：1 P0 + 6 P1 + 3 P2，已修 P0-1 + 5 P1 + 1 P2（详见 §9.6 / §9.8 reviewer 复核段）。剩余 P2 不阻断本 PLAN 转 Accepted，登记此处供 H 系列收尾整理：

| ID | 严重度 | 内容 | 处置 |
|----|--------|------|------|
| P2-1 | 讨论项 | ADR-H9 §6.1 P0 wake "300s 内重唤只生效一次"防雪崩 — 300s 是经验值还是有依据？ | 不阻断；CC ScheduleWakeup 限制 60s-3600s 已在 §6.3 说明，300s ≈ 5min 是中位经验值；H9 演练（WP-08）有数据后再决定是否调整或补依据段 |
| P2-2 | 讨论项 | PLAN-H9 §3 总估时 3.5d + 0.5d Gate = 4d 与 plan §3.3 估时 3d 多 0.5d；§0 line_budget 段未同步预算调整说明 | 不阻断；§3 段内已说明合理性（schema 真相源 + 全 lint 多出的 0.5d）；plan 文件 §4.1 / §4.2 / §4.3 约定整体复盘时再 align，本 PLAN 不动 plan |
| reviewer 二审 | 可选 | reviewer 第一轮已条件 PASS（"修 P0 后建议 PASS"），P0 + 5 P1 + 1 P2 已修 | 不强制二审；如 H 系列收尾时发现修法误差，再 spawn |

**signer** 状态升级：
- ADR-H9 / PLAN-H9 起草: Nature（AI 助手协助）
- ADR-H9 / PLAN-H9 reviewer 第一轮: feature-dev:code-reviewer (claude-opus-4-7, 2026-04-28) PASS_WITH_NOTES
- ADR-H9 / PLAN-H9 起草人收口（修 P0+多 P1+1 P2）: 本 commit
- 转 Accepted 触发条件：WP-08 Nature 演练录像 + WP-01..07 全 PASS（保持 PLAN-H9 §0 / §8 既定生效条件）

## 11. 实施进度追踪（commit-anchor 表）

| WP | 状态 | 落地 commit | 关键证据 |
|----|------|-------------|----------|
| WP-01 | ✓ DONE | 8bdc662e (2026-04-28) | 25 dirs + 22 .gitkeep + message-v1 JSON Schema 真相源 + 7 round-trip 用例 PASS |
| WP-02 | ✓ DONE | 202dff63 (2026-04-28) | inbox-write-ledger.py 183 行 / lint 0 violation / 3 smoke PASS / p50=32ms |
| WP-03 | ✓ DONE | 39cc402b (2026-04-28) | inbox-validate.py 211 行 / lint 0 / 4 smoke PASS（合规保留 / 缺必填 quarantine / P0+false quarantine / ack 缺 ack_for quarantine）/ in-scope p50=105ms（schema 校验开销）/ out p50=30ms |
| WP-04 | ✓ DONE | 1eb1f764 (2026-04-28) | inbox-inject-on-start.py 212 行 / lint 0 / 3 smoke PASS（空 unread 沉默 / 1 unread → SessionStart additionalContext JSON 含 msg_id / in-flight 残留 mv 回 unread）/ 4096 字节降级提示 |
| WP-05 | ✓ DONE | 37a15972 (2026-04-28) | inbox-poll.sh 78 行 / lint active-code 0 / 3 smoke PASS（empty=1200s / P1=1200s+age>0 / P0=300s）/ spec letter 修订：shell 不能调 CC 内部 ScheduleWakeup tool API，落地切分 shell 输出 KV state + agent 决定调度 |
| WP-06 | ✓ DONE | 38262642 (2026-04-28) | inbox-ack.py 202 行 / lint INCLUDE_ALL exit=0 / AST banned form 0 / 4 smoke PASS（basic mv+ack+schema validate / idempotency 不双写 / invalid sender stderr / 二次 ack 不同 msg-id 正确生成）|
| WP-07 | ✓ DONE | 8b442216 (2026-04-28) | .claude/settings.json PostToolUse +2 hook（inbox-write-ledger + inbox-validate）+ SessionStart +1 hook（inbox-inject-on-start）；JSON valid + 4 lint exit=0 + poll.sh banned form 0；端到端 chain integration smoke：write-ledger 写 jsonl + validate 保留合规 + inject-on-start 输出正确 schema additionalContext |
| WP-08 | ✓ DONE | 本 commit (2026-04-28) | Nature 真实演练 PASS（ADR-H9 附录 A.2）：session B Write h9-20260428-163305-rehearsal → PostToolUse 链落 ledger（6 字段）→ session A `/exit` + 重启 → SessionStart hook 链触发 → `inbox-inject-on-start.py` emit additionalContext → session A 接 `<system-reminder>` 转述原文（CC integration 黑盒 Path A 实证）→ ack mv processed + window-h9/acks/main-20260428-163701-6f40f7.md。端到端 ≈ 4min（人工切换主导，远 ≪ 1200s 预算）。UX spec 澄清：additionalContext 是 AI 系统消息层（不是 banner），修订原 PLAN §4.4 截屏 banner 设想。Path B（ScheduleWakeup poll）留待 H 系列首次跨窗口实战 |
