# Hanis（H 系列）协议详细规则

**触发**: 改 `.towow/inbox/**` / `.towow/state/**` / `docs/decisions/ADR-H*.md` / `docs/decisions/PLAN-H*.md` / `.worktrees/hanis-*/**` / `.towow/log/hanis-self-symptoms.md` 时自动加载
**适用范围**: 所有针对 hanis（H 系列）治理底座的修改
**强制等级**: 不可降级（hard rule）；与 ADR-041 v1.0「调字不加机制」边界详 §H4 vs H5

## H0 元规约 6+1（必读）

> H0 仅依赖手工 `git diff` / `wc -l` / `grep` / Nature 签字 / PR 评论。**不得引用任何 H1-H9 未来产物**。

| § | 规则 | 触发 | 验证 |
|---|---|---|---|
| **H0.1 施工隔离** | H 子 PLAN 的施工目录必须在 scope 显式列出，跨 scope 改动需 Nature 签字 | PR diff 触及非自身 scope | `git diff --name-only` 与 scope 列表手工比对 |
| **H0.2 节流限速** | 每个 H 文档 ≤500 行；新增 ADR ≤300 行 | 起草 / 修订 / 追加章节 | `wc -l` 直量；PR 模板含行数自报 |
| **H0.3 执检分离** | 起草人不能担任最终签字人；实施者不能验收自己 | PR merge 前；DoD 验收 | PR 至少 1 条非作者签字 |
| **H0.4 自指禁止** | 修问题 X 的 H 不得在自己交付物中重现 X 的症状 | 任意 H 起草 / 实施 | PR 必填"自指自检"段，reviewer grep 反查 |
| **H0.5 跨 H 协调** | 共改文件需登记冲突表；未登记按 git 时间戳先到先得，后到方负责 rebase | 同 commit window 多 H 触及同文件 | `git log --all --oneline -- <path>` 反查 |
| **H0.6 证据机械化** | DoD 证据必须机器可生成（grep / 行数 / 文件存在 / hook log），不接受"reviewer 认为已完成" | 每个 DoD 勾选 | DoD checklist 每条括注证据生成命令 |
| **H0.meta** | H0 自身修订也适用 H0.1-H0.6；H0 不引用任何 H1-H9 未来产物 | H0 文档每次变更 | 起草者写"H0 自检：未引用 H1-H9 未来产物" |

## 9 站速查表

| 站 | ADR | PLAN | 核心 INV | 抗 compact 接口 |
|---|-----|------|---------|----------------|
| H0 | `ADR-H0-meta-charter.md` | （单文档，Nature 单签 charter） | 6+1 元规约 | — |
| H9 | `ADR-H9-mailbox.md` | `PLAN-H9-mailbox.md` | inbox schema-v1 / 5 hook | `.towow/inbox/main/unread/` SessionStart 注入 |
| H2 | `ADR-H2-identity-isolation.md` | `PLAN-H2-identity-isolation.md` | ownership.yaml owner 字段必填 | ADR-042 D9 |
| H3 | `ADR-H3-memory-scope.md` | `PLAN-H3-memory-scope.md` | INV-H3-1/2/3（≤200 / ≤50 / 跨session 走 inbox） | MEMORY.md 主索引 ≤200 |
| H4 | `ADR-H4-prompt-governance.md` | `PLAN-H4-prompt-governance.md` | 黑话/推卸/过度 review checklist | — |
| H1 | `ADR-H1-crystal-learn-revival.md` | `PLAN-H1-crystal-learn-revival.md` | crystal-learn 周期触发 | — |
| H5 | `ADR-H5-gate-quantization.md` | `PLAN-H5-gate-quantization.md` | review-contract.yaml + 跳 Gate 决策表 | — |
| H6 | `ADR-H6-state-file-health.md` | `PLAN-H6-state-file-health.md` | state 清单 + 健康指标 ≥3 | ADR-042 D9 |
| H8 | `ADR-H8-issue-and-doc-compliance.md` | `PLAN-H8-issue-and-doc-compliance.md` | INV-H8-1/2/3 | ADR-INDEX 自指过滤 |

## H4 vs H5 哲学边界（与 ADR-041 v1.0 张力）

ADR-041 v1.0 故意"调字不加机制"。H 系列在补机制（H7 hook IO / H9 邮箱 / H6 状态文件）。两哲学边界：

| 问题类型 | 走 prompt（ADR-041 v1.0） | 走 schema/hook（H 系列） | 判定理由 |
|---|---|---|---|
| 行为偏好（黑话 / 推卸 / 过度自我表扬） | ✅ lead skill prompt 段 | ❌ 不写 hook | 70% 遵从率够用；hook 解决不了"语气" |
| 物理隔离（写权限 / 身份 / 跨 session） | ❌ prompt 不算数 | ✅ frontmatter / hook / 文件结构 | ADR-038 D11：schema-level 100% |
| 节奏限速（review 轮次 / 文档行数） | ✅ 红线 + 每周人脑回顾 | ⚠ 仅当反复违反才升级 hook | 先调字 3 周 → 仍违反再上 hook |
| 通信协议（窗口间消息 / proposal 格式） | ❌ prompt 不能保证 schema | ✅ 文件 + hook 验 schema | 没 schema 验，邮箱第二天就乱 |

**反例（H 系列绝不做）**：
- ❌ 写 hook 检测 AI 用没用黑话 → 黑话治理走 lead skill prompt
- ❌ 建 metrics 系统记录 review 轮次 → 节奏靠红线 + 每周人脑回顾
- ❌ 做 dashboard 看 H 系列进度 → 主窗口邮箱 inbox 已经够用
- ❌ 加 SKILL.md 教 AI 怎么自己识别推卸行为 → 元能力堆叠是推卸的另一个症状

## H9 邮箱机制使用规则

**inbox 路径约定**（schema 锁死，不许后续动）：
```
.towow/inbox/
├── main/{unread,processed,in-flight}/    # 主窗口收件箱
├── window-h0/, window-h7/, window-h9/, ...   # 子窗口出件箱
└── schema/message-v1.json                # 消息 schema
```

**消息文件 frontmatter 必填**：`sender / sender_pid / ts / kind(progress|block|done|question) / priority(P0|P1|P2) / related_h / ack_required`

**5 hooks**（已上线）：`inbox-write-ledger.py` / `inbox-validate.py` / `inbox-inject-on-start.py` / `inbox-poll.sh` / `inbox-ack.py`

**与 `.towow/proposals/` 边界**（H9 ADR §X 锁死）：
- proposal = "我的足迹"（self-trace）
- inbox = "我喊队友"（peer-message）
- 同一动作只走一个；都要走时 inbox 引用 proposal ID（不复制内容）

**主窗口姿态**：脚本协调员，不是人手。所有窗口间通信走 inbox，不许 SendMessage / TeamCreate / 复制粘贴。

## ADR-INDEX.md 自指过滤

**INV-H8-1 检测命令**：
```bash
diff <(ls docs/decisions/ADR-*.md | xargs -n1 basename | sed 's/\.md$//' | grep -v '^ADR-INDEX' | sort) \
     <(awk '/^- \[ADR-/{gsub(/^- \[/, ""); gsub(/\].*/, ""); print}' docs/decisions/ADR-INDEX.md | sort)
```

**关键**：`grep -v '^ADR-INDEX'` 必须保留——ADR-INDEX 自身在 `ADR-*.md` glob 内，但不在自身 hook 列表（自指悖论闭环）。

## 跨 H 冲突仲裁

| 冲突点 | H | 仲裁原则 |
|---|---|---|
| `*/SKILL.md` frontmatter | H2 × H4 | 串行：H2 先 schema，H4 后 prompt |
| `ownership.yaml` | H2 × H6 | 串行：H2 先升级 schema，H6 后基于新 schema |
| `MEMORY.md` | H3 × H4 | 串行：H3 先重组分段，H4 后写入 |
| `ADR-042.md` D9 段 | H2 × H6 | 串行：H2 加身份段，H6 加抗 compact 段 |
| `.towow/log/hook/` 路径 | H7 × 下游全部 | 串行：H7 先定，下游引用 |
| `.towow/inbox/**` | H9 × 下游全部 | 串行：H9 先定 schema，下游窗口才能发 |

未登记冲突：git 时间戳先到先得，后到方 rebase。

## DoD 证据生成命令速查

| Check | 命令 | 期望 |
|---|---|---|
| ADR ≤300 行 | `wc -l docs/decisions/ADR-H*.md` | 全部 ≤300 |
| PLAN ≤500 行 | `wc -l docs/decisions/PLAN-H*.md` | 全部 ≤500 |
| ADR-INDEX 完整 | INV-H8-1 命令 | exit 0 |
| CHANGELOG ≤14d | `awk '/^## \[/{...}' CHANGELOG.md` | 相邻日期差 ≤14d |
| open issue ≤80 | `find docs/issues -name "*.md" \| xargs grep -l "^status: open" \| wc -l` | ≤80 |
| 9 H ADR 索引 | `for h in H0 H9 H2 H3 H4 H1 H5 H6 H8; do grep -qE "^\- \[ADR-${h}\b" docs/decisions/ADR-INDEX.md \|\| echo "MISSING \| ADR-${h}"; done` | 0 MISSING |

## 自指症状审计流

`.towow/log/hanis-self-symptoms.md` 是 H 系列实施期 + 后续维护期"修问题反而引入问题"的落地审计流。每次触发：
- 日期 / 涉及 H / 症状描述 / 处置 / 是否需要回滚

**长期成功信号**：症状趋势递减（H 系列收尾时分析）；递增 = H 系列失败信号。

## 失败回滚 4 档

| 档位 | 现象 | 处置 |
|---|---|---|
| 轻 | 个别 hook fail，不影响产线 | 在 hanis-main 上 fix commit；记 self-symptoms |
| 中 | vNext smoke fail 但能修 | hotfix worktree from hanis-main，1 天内 fix；超时升级 |
| 重 | 产线撞挂 | `git revert <Hx-merge-commit>`；下游 H 必须 rebase；Nature 单签 |
| 最坏 | 连续 2 H 重 broken 回滚 | H 系列暂停 1 周，Nature 评估拓扑或拆 H |

## 与现行产线共存灰度（已收尾期间维护参考）

H 系列已 9/9 全闭，但维护期改动仍受灰度规则约束：
- 改 hook → 跑现行 vNext smoke（K 系列 sandbox + boattosea Gate）
- inbox 新路径不冲突 vNext，但 PostToolUse Write hook 只在 inbox 路径加
- ownership.yaml / MEMORY.md 重组前必须 backup
- state 文件健康指标 = 只读盘点，不删活的 state

## 与其他规则的关系

- **ADR-038 D11**: schema-level 隔离 100% > prompt-level 70%（H2/H9 frontmatter 设计依据）
- **ADR-041 v1.0**: 调字不加机制（H4 prompt 治理 vs H 系列其他机制层的边界依据）
- **ADR-042 D3/D4/D9**: anti-compact 接口（H2/H6 抗 compact 接口签字依据）
- **`feedback_record_preexisting_failures`**: pre-existing 失败 / guard 漂移登记不阻塞，但必须记录

## 例外申请

H 系列 9 站已收尾。新议题原则上**不加 H10+**，走业务 PLAN-XXX 自然消化。

例外申请条件（罕见）：
1. 该议题不能由任何业务 PLAN 承载（必须是 hanis 元层）
2. Nature 单签
3. 沿 9 站现有 ADR/PLAN 修订路径走，不开新 H 编号
