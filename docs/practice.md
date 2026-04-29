# wow-harness 在 Towow 的实践

> **本地展示**：双击打开 [`docs/practice.html`](./practice.html)（浅色主题，纯 HTML+CSS，不依赖任何渲染引擎）。
> 下面是同一份内容的 GitHub 在线版本（Mermaid 渲染）。

98 天 / 2058 commits / 76 万行 / 2100+ 测试 — 一个人 + AI 全自主交付。
两张图是 harness 当前真实在跑的样子。

---

## 图 1 · 你说一句话，AI 自己干完 8 关

```mermaid
flowchart LR
    U[你说<br/>我要做 X]:::user --> G0
    G0[Gate 0<br/>lead 锁问题]:::work --> G1
    G1[Gate 1<br/>arch 出架构]:::work --> G2
    G2[Gate 2<br/>独立审查 AI<br/>无 Edit/Write]:::review --> G34
    G34[Gate 3-4<br/>plan-lock 冻结<br/>独立审查]:::review --> G56
    G56[Gate 5-6<br/>task-arch 拆 WP<br/>独立审查]:::review --> G7
    G7[Gate 7<br/>harness-dev 写代码<br/>边写边记日志]:::work --> G8
    G8[Gate 8<br/>终审 + E2E]:::review --> PR
    PR[accept PR]:::user

    classDef user fill:#fff4d6,stroke:#d97706,color:#000
    classDef work fill:#dceefb,stroke:#1d4ed8,color:#000
    classDef review fill:#fde2ea,stroke:#be123c,color:#000
```

- 黄色 = 你的输入 / 你的决策
- 蓝色 = AI 执行（lead / arch / dev）
- 红色 = 独立审查 AI — 不共享之前对话从头看；tools 列表里物理移除 Edit / Write，**不是嘱咐它「只看不改」，是它根本调不出这两个工具**

---

## 图 2 · 三层 harness — 每层在解决什么问题

```mermaid
flowchart TB
    subgraph V3[v3 · 自治层 · 解决 harness 自己跑出 bug 时谁来修 harness]
        H0[改 harness 时<br/>不许重现自己要修的症状<br/>H0 元规约]
        H9[多窗口并行<br/>不靠人手当中转<br/>H9 文件邮箱]
        H1[同样的坑<br/>不踩第二次<br/>H1 crystal-learn]
        Hx[编号撞/记忆涨爆<br/>状态漂移/文档脱节<br/>H2-H8 硬指标]
    end
    subgraph V2[v2 · 阶段化层 · 解决 AI 不知道当前在哪个阶段，工具权限一直全开]
        Mode[阶段切换<br/>自动收/放权<br/>mode-toolkit]
        Review[审查标准写在契约里<br/>不在提示词里漂<br/>review-toolkit]
    end
    subgraph V1[v1 · 物理拦截层 · 解决 AI 写规则但不听规则 CLAUDE.md 遵从率仅 20%]
        Hooks[想做错事<br/>就在动作那一刻挡下<br/>18 hooks]
        Skills[把 AI 拆成<br/>各司其职的角色<br/>16 skills]
        Checks[不靠 AI 记规则<br/>靠脚本自动验<br/>15 checks]
    end
    V1 ==当 v1 还不够==> V2 ==当 v1+v2 自己跑出问题==> V3

    classDef v1 fill:#dceefb,stroke:#1d4ed8,color:#000
    classDef v2 fill:#fff4d6,stroke:#d97706,color:#000
    classDef v3 fill:#d6f0d8,stroke:#15803d,color:#000
    class Hooks,Skills,Checks v1
    class Mode,Review v2
    class H0,H9,H1,Hx v3
```

每层都在答一个问题：「上一层不够用的时候补什么」。
- **v1 解决** AI 写规则但不听规则（CLAUDE.md 遵从率仅 ~20%）→ 用 hook 物理拦截
- **v2 解决** AI 工具权限一直全开 → 用阶段机自动收/放权
- **v3 解决** harness 自己跑出 bug → 9 站自治协议（修问题不在自己交付物里重现该问题等）

**v3 一直闭合不再开新站，本身就是稳态信号。**

---

## 想直接看实现的话

| 你想看 | 打开这个 |
|---|---|
| 审查 AI 物理上改不了代码 | [`.claude/plugins/towow-review-toolkit/agents/reviewer.md`](../.claude/plugins/towow-review-toolkit/agents/reviewer.md) — 看顶上 `tools:` 列表 |
| ADR 编号撞了 git 直接拒绝提交 | [`.githooks/pre-commit`](../.githooks/pre-commit)（22 行 shell）+ [`scripts/checks/check_adr_plan_numbering.py`](../scripts/checks/check_adr_plan_numbering.py) |
| AI 之间怎么传消息（H9 邮箱） | [`.towow/inbox/schema/message-v1.json`](../.towow/inbox/schema/message-v1.json) + 5 个 inbox hook |
| 16 个 skill 怎么分工 | [`.claude/skills/`](../.claude/skills/) |
| 所有 hook IO schema | [`scripts/hooks/_hook_output.py`](../scripts/hooks/_hook_output.py) — 16 个 helper API（ADR-058） |
