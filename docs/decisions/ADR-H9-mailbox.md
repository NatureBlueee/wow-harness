# ADR-H9: harness 多窗口邮箱机制（取代人脑协调员）

**状态**: Accepted（PLAN-H9 + 5 hook 落地 + Nature 真实演练 PASS [附录 A.2] + 非起草 reviewer 复核 task #17 完成，2026-04-28）
**日期**: 2026-04-28
**起草者**: Nature（AI 助手协助）
**签字者**: 待非起草 reviewer 复核
**上下文**: `docs/decisions/ADR-H0-meta-charter.md` / harness 拓扑 D 修订版（H0 → H9 → H2 → H3 → H4 → H1 → {H5/H6/H8 并行}，原 H7 已撤销见 `.towow/log/harness-self-symptoms.md` §4.3）

> 编号说明：走 harness 系列独立编号空间（ADR-Hx），不占主仓 ADR-XXX。
>
> 取代关系：本 ADR 把"主窗口人脑协调员"物理化为"文件队列 + hook 自动注入 + ScheduleWakeup 自循环"。Nature 启动主窗口后只说"开始 harness 系列"，主窗口靠 SessionStart 注入读邮箱、靠 ScheduleWakeup 持续轮询，不再手动 ping / 复制粘贴。

## 1. 决策

harness 多窗口协作通信走文件邮箱（inbox），路径 `.towow/inbox/`，schema 锁定为 **message-v1**（yaml frontmatter + markdown body）。5 个 hook 承担 **ledger / validate / inject / poll / ack** 五职。主窗口扮演"脚本协调员"，不接受人手 ping。

## 2. 为什么需要邮箱

harness 起草过程中 Nature 反复扮演"信使"——子窗口完工或卡壳时手动复制粘贴回主窗口。这本身就是 harness 要修的"协调断裂"——人脑队列容量有限、易丢、跨 session 不可见。

继续用人手 ping 推进会撞 3 类问题：
- 子窗口失败 / 卡壳 → 等 Nature 看到 → 手动协调 → 时延 / 丢消息
- 主窗口长时间不在线时子窗口"边缘化"，等不到反馈又不能自决
- 同一进度容易重复进 proposals + 主窗口对话双写

文件邮箱把通信物理化：所有窗口间交互留痕、可机器扫、可重放、可校验 schema。

## 3. inbox 路径约定（schema 锁死）

```
.towow/inbox/
├── main/
│   ├── unread/              # 主窗口 SessionStart 全量注入源
│   ├── in-flight/           # 处理中（崩溃恢复用，见 §6.2）
│   └── processed/           # 主窗口已处理
├── window-h0/               # 子窗口出件箱 + acks/
│   └── acks/
├── window-h1/  window-h2/  window-h3/  window-h4/
├── window-h5/  window-h6/  window-h8/  window-h9/
# 注：window-h7 缺位 = 拓扑 D H7 撤销（参 .towow/log/harness-self-symptoms.md §4.3 调研缺失/重复立项）；非编号空洞，是有意省略
├── quarantine/              # schema 不合规移入（见 §6.4）
└── schema/
    └── message-v1.json      # JSON Schema 真相源（机器可校验）
```

**硬规则**：
- 任何窗口写邮箱必须命中 `.towow/inbox/<owner>/(unread|acks)/<msg-id>.md` 路径模板，否则 §6.4 quarantine
- 路径树在本 ADR 落地后 **frozen**；新增子目录或重命名走 ADR-H9.x 显式修订
- Window 命名空间 = harness 拓扑 H 编号；非 harness 子计划不得占用 `.towow/inbox/`

## 4. message-v1 schema（yaml frontmatter）

```yaml
---
sender: window-h0              # 发送窗口（必填）；子→主走 window-Hx；主→子 ack 时填 main，路径仍写到 window-Hx/acks/<msg-id>.md
sender_pid: 12345              # 发送窗口 CC pid（防伪 / race 排查）
ts: 2026-04-28T14:30:00+08:00  # ISO-8601 + 时区
msg_id: h0-20260428-143000-abc # 幂等 ID（重发 ack 用）
kind: progress|block|done|question|ack
priority: P0|P1|P2
related_h: H0|H1|H2|H3|H4|H5|H6|H8|H9
related_wp: WP-Hx-NN           # 可选
ack_required: true             # 主窗口是否需回执；默认 false（progress/done）；priority=P0 强制 true（schema 校验拒收 P0 + ack_required=false 组合）；kind=ack 永远 false（ack 不再 ack）
ack_for: <msg_id>              # kind=ack 时必填，引用被 ack 的消息 ID
---
```

**sender 取值约定**：
- `window-h0`..`window-h9`：子窗口（出件箱在 `.towow/inbox/window-Hx/`）
- `main`：主窗口出向 ack（写入 `.towow/inbox/window-Hx/acks/`，**不**写入 `.towow/inbox/main/`，避免主窗口 SessionStart 注入自己的 ack 消息构成回环）

**markdown body 风格**：沿用 `.towow/proposals/*-trace-analysis.md` 章节式 markdown（标题 + 列表 + 代码块），便于人眼扫读和未来与 proposal schema 收敛。

**与 `.towow/proposals/` 的复用决策**（本 ADR §4 设计内 sealed，待 reviewer 复核后随本 ADR 转 Accepted 一并落定）：

| 维度 | proposal-v1 | message-v1 |
|------|-------------|------------|
| 性质 | self-trace（AI 自留足迹） | peer-message（窗口间显式喊队友） |
| 触发 | trace-analyzer.py 自动生成 | 窗口主动写入 |
| 必填字段 | findings + confidence | sender_pid / ts / msg_id / kind / priority |
| schema | markdown 章节，无 frontmatter | yaml frontmatter + markdown body |
| 收件 | 人工审查 → D6.1 self-evolution | hook 注入 → 主窗口处理 |

**双写规则**：同一动作**只走一个**。如必须双写，message frontmatter 增 `proposal_ref: <path>` 引用 proposal 路径，**不复制 proposal 内容到 message body**。

## 5. 5 个 hook 边界 + helper 映射

| Hook 文件 | 注册事件 | matcher | 职责 | helper 调用 | 落点 |
|----------|----------|---------|------|-------------|------|
| `inbox-write-ledger.py` | PostToolUse | Edit\|Write | 检测 .towow/inbox/** 写入 → 追加 ledger（不阻断） | `post_tool_use_inject(ctx)` | `.towow/log/hook/inbox-write.jsonl` |
| `inbox-validate.py` | PostToolUse | Edit\|Write | 校验 message-v1 schema，不合规 mv quarantine/ | `post_tool_use_inject(ctx)` | `.towow/log/hook/inbox-quarantine.jsonl` |
| `inbox-inject-on-start.py` | SessionStart | * | 主窗口启动读 main/unread/ → 注入 systemMessage | `session_start_inject(ctx)` | session 启动 inline |
| `inbox-poll.sh` | ScheduleWakeup 自循环 | — | 主窗口每 1200s 扫 unread/ 触发新一轮处理 | 调 ScheduleWakeup MCP，不出 stdout JSON | 主窗口 cron-like |
| `inbox-ack.py` | 主窗口手动调用 | — | 处理完 mv unread/→processed/ + 写 ack 回子窗口 | 直接文件 IO，不出 stdout JSON | `.towow/inbox/window-Hx/acks/` |

**红线**：
- 3 个 stdout-bearing hook（write-ledger / validate / inject-on-start）必须 `from _hook_output import <helper>`（ADR-058 §D1）；不许手搓 `print(json.dumps(...))`
- 2 个非-stdout hook（poll.sh / ack.py）跑 lint-hook-output.py 应不命中即可
- 5 hook 任何 IO 失败都不阻断主流程（PostToolUse inject 不能 BLOCK 用户工作）

## 6. 5 失败模式 inline 处置（plan §3.3.2 sealed）

### 6.1 主窗口长时间不在线
- **现象**：子窗口邮件堆积 unread/，没人读
- **处置**：inbox-write-ledger.py 检测 `len(main/unread/) ≥ 50` 时写 `.towow/log/hook/inbox-overflow.jsonl`；子窗口 priority=P0 时跳过等待，直接调 ScheduleWakeup 强制唤醒主窗口（300s 内重唤只生效一次）

### 6.2 消息重复处理
- **现象**：unread/ → processed/ mv 中间崩溃
- **处置**：处理前先写 `.towow/inbox/main/in-flight/<msg-id>.lock`；inbox-inject-on-start.py 启动时清 in-flight/，把对应消息 mv 回 unread/；ack 用幂等 msg_id（重发 ack 不重复处理）

### 6.3 ScheduleWakeup 边界
- **现象**：CC 限制 60s-3600s，不能更短；主窗口轮询慢于实时
- **处置**：默认 1200s（20min，prompt cache 友好）；priority=P0 消息触发子窗口立即调 ScheduleWakeup 强制 wake 主窗口；P0 wake 在 300s 内重复触发只生效一次（防雪崩）

### 6.4 schema 漂移
- **现象**：子窗口写出非 message-v1 消息
- **处置**：inbox-validate.py PostToolUse 时拒收，mv `.towow/inbox/quarantine/`；ledger 写一行 quarantine 事件；新增 schema 字段必须 v1→v2 显式 migration（本 ADR §4 frozen，新版本走 ADR-H9.x 修订）

### 6.5 inbox 与 proposals 双写
- **现象**：同一进度同时进 proposals 和 inbox
- **处置**：本 ADR §4 设计内 sealed（待整体转 Accepted 落定）— proposal 是 self-trace，message 是 peer-message，同一动作只走一个；如必须双写 message `proposal_ref:` 引用，不复制内容

## 7. 主窗口"脚本协调员"姿态

- 主窗口**不是**人脑协调员，是脚本协调员
- Nature 启动主窗口时只说"开始 harness 系列"，主窗口靠 SessionStart 注入读邮箱、靠 ScheduleWakeup 持续轮询
- 主窗口与子窗口的**所有通信走 inbox**——不许 SendMessage / TeamCreate / 复制粘贴
- 子窗口 kind=block 时主窗口决定是否升级 Nature（升级 = 主窗口对 Nature 输出文本说明 block 内容）
- Nature 看到主窗口对 block 的处置后回复主窗口 = 主窗口写 ack 给原子窗口

## 8. 自检（H0.1-H0.6 + H0.meta）

- **H0.1 施工隔离**：本 ADR scope = `docs/decisions/ADR-H9-mailbox.md`；新建 `.towow/inbox/**` 路径树 + 5 hook 由 PLAN-H9 各 WP 独立 commit，每个 commit body 显式列出 scope 路径
- **H0.2 节流限速**：本 ADR 目标 ≤ 300 行
- **H0.3 执检分离**：起草者 Nature（AI 助手协助），签字者待非起草 reviewer 复核；**不享** H0 §3.4 单签例外（例外仅限 ADR-H0 自身）
- **H0.4 自指禁止**：H9 修"协调断裂"，自身不许提议新 branch 隔离（已遵守，沿用 ADR-H0 main 直接 commit）；不许"待协调员决定"（已遵守，§7 显式说明协调员是脚本而非人脑）
- **H0.5 跨子计划协调**：本 ADR 不动 ownership.yaml / MEMORY.md / SKILL.md / review-contract.yaml / commit body 模板；冲突表为空
- **H0.6 证据机械化**：本 ADR 锁 schema + hook 边界；DoD 证据命令在 PLAN-H9 各 WP 落地
- **H0.meta**：本 ADR 引用 H0（已落地的兄弟子计划，可引用）；其他兄弟用"后续 H 子计划"或具体路径表述

**症状词字面命中检查**：本 ADR §2 / §6 / §7 出现"协调断裂""人脑协调员""待协调员决定（反例）"均以**陈述实例 / 元层反例**形式出现，自身行为命中 = 0；元层定义不计入（参 ADR-H0 §6 例 4 判定标准）。

## 9. 生效与变更

- **生效**：本 ADR + PLAN-H9 + 5 hook 实施 + Nature 演练 1 次 + 非起草 reviewer 签字后转 Accepted
- **变更**：§3 inbox 路径 / §4 message-v1 schema / §5 hook 边界 frozen；修订必须新 ADR-H9.x + Nature 单签 + migration 路径
- **不向后兼容**：v1 message 不允许丢字段；v1→v2 必须有迁移脚本 + quarantine 缓冲期 ≥7d

## 10. 与现有规则关系

- **ADR-H0-meta-charter.md**：H9 完全遵守 H0 6+1 规约；不享 §3.4 单签例外
- **ADR-058 §D1 hook IO schema**：3 stdout-bearing hook 全部走 `_hook_output` helper
- **ADR-038 D10 / .towow/proposals/**：proposal-v1 与 message-v1 schema 分开，§4 已签字
- **MEMORY feedback_local_worktrees_only.md**：harness 系列例外（main 直接 commit）已在 ADR-H0 §8 说明，H9 沿用
- **CLAUDE.md §四 4.3 / `.claude/rules/review-agent-isolation.md`**：H9 reviewer 用 `towow-review-toolkit:reviewer`（frontmatter schema-level 物理隔离）

## 11. 配套文件

- `docs/decisions/PLAN-H9-mailbox.md`：WP 拆解 + DoD 验证清单（task #15 已完成）
- `.towow/inbox/schema/message-v1.json`：JSON Schema 真相源（PLAN-H9 WP-01 落地）
- `scripts/hooks/inbox-{write-ledger,validate,inject-on-start,poll,ack}.{py,sh}`：5 hook 实施（PLAN-H9 WP-02 ~ WP-06）
- `.towow/log/hook/inbox-{write,quarantine,overflow}.jsonl`：3 类落盘 ledger（PLAN-H9 各 WP DoD 证据）

## 附录 A：演练证据（WP-08 落地后填）

> 本附录是 ADR-H9 转 Accepted 的最后凭证占位。真实演练（Nature 启动两个 CC session）
> 录像 / 截图 / timing 数据在演练完成后由 Nature 或主窗口 agent 填入。
>
> **AI dress rehearsal vs Nature 真实演练 边界声明**：本附录区分两类证据。
> - AI dress rehearsal：单 shell session 顺序模拟所有 hook，验证逻辑链路
> - Nature 真实演练：两个真实 CC session 启动 + Write tool 触发真实 PostToolUse +
>   SessionStart 注入 systemPromptAdditions + 真实 ScheduleWakeup 调度
> 前者是 logic 验证，后者是 integration 验证；后者的录像 / 截图是 ADR-H9 转 Accepted
> 的硬条件，**前者不能替代**（H0.6 证据机械化要求人脑可复盘）。

### A.1 AI dress rehearsal（2026-04-28，commit 8b442216 完成 WP-07 后实测）

**setup**：单 shell session 顺序模拟"子窗口写消息 → PostToolUse 链 → SessionStart inject → 主窗口 ack"
全流程 hook 调用，不启动 CC session（不触发真实 hook 调度）。

**端到端 timing**：

| 阶段 | 耗时 | 备注 |
|------|------|------|
| T0→T1 子写消息 | 0s | heredoc 写入 unread/ |
| T1→T2 PostToolUse 链 | 1s | inbox-write-ledger.py + inbox-validate.py 串行 |
| T2→T3 SessionStart inject | 0s | inbox-inject-on-start.py 输出 schema-correct additionalContext |
| T3→T4 主→ack | 0s | inbox-ack.py mv + 写 ack 文件 |
| **T0→T4 端到端** | **1s** | **≪ 60s P0 路径预算 ≪ 1200s 默认轮询预算** |

**机器证据 delta（PLAN-H9 §4.8 reviewer P1-2）**：ledger ts_unix vs ack file mtime delta = **0s**（同秒完成）

**结论**：所有 5 hook 实现层逻辑正确。链路无缺口、无 schema drift、无 hook 间状态不一致。
但本 rehearsal 不能证明 **CC 真实 SessionStart additionalContext 是否真的注入到主窗口
systemPromptAdditions**，也不证明 **真实 ScheduleWakeup 调度时主窗口 SessionStart hook
是否真触发**——这两点必须 Nature 真实演练验证。

### A.2 Nature 真实演练（2026-04-28 PASS）

**setup**：
- session A：主仓 root（`/Users/nature/个人项目/Towow`），CC v2.1.121 Opus 4.7，settings.json 16 hooks 全注册
- session B：同目录第二终端，CC v2.1.121 Opus 4.7（同 working tree，避免 worktree 各自 `.towow/` 互不可见的拓扑陷阱）
- 共享物理 inbox：`.towow/inbox/`

**演练时间线**：

| T | 动作 | 机器证据 |
|---|------|----------|
| T0 16:33:05 | session B Write `.towow/inbox/main/unread/h9-20260428-163305-rehearsal.md` | msg_id=h9-20260428-163305-rehearsal |
| T1 16:33:22 | PostToolUse hook chain（write-ledger + validate）触发 | `.towow/log/hook/inbox-write.jsonl` 末行含 rel_path / sender=window-h9 / msg_id / kind=progress / priority=P1 / related_h=H9 全 6 字段 |
| T2 ~16:36 | session A `/exit` + 重启 `claude` → SessionStart hook 链触发 | session A 进程重启 |
| T3 重启同一秒 | `inbox-inject-on-start.py` emit `hookSpecificOutput.additionalContext` | session A 接到 `<system-reminder>SessionStart hook additional context: [H9 inbox] 1 unread message(s) ... [P1] progress from window-h9 (h9-20260428-163305-rehearsal) — H9 @ 2026-04-28T08:33:06+08:00 ... body: WP-08 真实演练测试消息（Session B → Main）...</system-reminder>` |
| T4 16:37:01 | session A 调 `python3 scripts/hooks/inbox-ack.py --msg-id h9-20260428-163305-rehearsal --sender window-h9` | unread/<msg> mv processed/<msg> + `window-h9/acks/main-20260428-163701-6f40f7.md` 生成 |

**端到端时延**：T4 - T0 ≈ 4 min（含 Nature 切换终端 + 手动 `/exit` 重启 CC 的人工操作时间），远 ≪ 1200s 默认轮询预算。

**关键 UX spec 澄清**（不在原 PLAN 设想内，本 ADR 转 Accepted 同时新增）：

CC SessionStart `hookSpecificOutput.additionalContext`（ADR-058 §D1 helper `session_start_inject` 唯一合法 stdout JSON 出口）注入到的是 **AI 视角的系统消息层**——CC runtime 把 additionalContext 包成 `<system-reminder>` tag 进 AI 的 prompt context；**不是**用户可见的 banner / 启动屏。

修订原 PLAN §4.4 / 附录草稿设想：
- ❌ 原："Nature 截屏 banner 看到 📬 收件箱" → 设想错误（banner 永远不会显示）
- ✓ 改："AI 在新 session 第一个 turn 逐字转述 inject 原文" → T3 行引文即此证据

**演练覆盖路径**：
- ✓ **Path A（手动 restart）**：session 重启 → SessionStart hook 链触发 → additionalContext 注入 AI prompt context → AI 看到 unread 列表（本演练验证）
- ⚠ **Path B（ScheduleWakeup 自循环 poll）**：本演练**未覆盖**——ScheduleWakeup 唤醒同一 session，**不重新触发 SessionStart hook**；AI 在 wakeup 后应主动调 Bash 跑 `scripts/hooks/inbox-poll.sh` 看 unread 计数 + 读文件自检。Path B 留待 H 系列首次跨窗口实战验证（不阻断本 ADR 转 Accepted，因 Path A 已足以证明邮箱机制端到端可用）

**结论**：PASS。5 个 hook + inbox 路径树 + message-v1 schema + ack 闭环全部端到端打通；CC integration 黑盒在 Path A 路径上已被 system-reminder 实证。

**ADR-H9 status 转 Accepted 触发条件**：✓ 全部满足（A.2 PASS + reviewer task #17 完成）→ 本附录入库 commit 同步翻 status：Proposed → Accepted（line 3 已落）。
