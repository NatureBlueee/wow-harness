#!/usr/bin/env python3
"""SessionStart — 显式告知本会话 wow-harness 已接入，并指向 hook 活动日志。

stdout 的文本会进入 Claude Code 会话上下文；经 ``wow_agent_dispatch`` 的
Cursor 桥接会包装为 ``additional_context``。

永远 exit 0（advisory）。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VISIBLE = REPO_ROOT / ".wow-harness" / "state" / "harness-visible.jsonl"


def main() -> int:
    try:
        rel = str(VISIBLE.relative_to(REPO_ROOT))
    except ValueError:
        rel = str(VISIBLE)
    banner = f"""## wow-harness 本会话已激活

本仓库已接入 **wow-harness**：下列阶段会自动跑脚本（无需你手动启动分发器）。

| 阶段 | 内容（摘要） |
|------|----------------|
| **SessionStart** | 风险快照、Magic doc 漂移、工具包周期提醒、**本说明** |
| **PreToolUse** | sanitize（Read/Shell）、deploy-guard（Bash）、python→python3、调用计数、Task 审查门禁 |
| **PostToolUse（Write/Edit）** | guard-feedback、loop-detection、risk-tracker |
| **SessionEnd / Stop** | 反思、trace、deploy 进度、stop 评估 |

### 每次实际跑 hook 时记了什么？

经 ``wow_agent_dispatch`` **真正进入仓库脚本**时，会在下面文件 **追加一行 JSON**（时间、``runtime`` 为 ``cursor`` 或 ``claude``、``hook`` 为子命令名），用来对照「刚才到底触发了哪条链」：

`{rel}`

**本地查看**：`tail -f {rel}`

**Cursor 终端 `agent`**：官方文档里 Agent hooks 主要对应 **Cmd+K / Agent Chat** 路径；`sessionStart` 注入的内容进**模型上下文**，**不会**画在你看到的 ASCII 欢迎框里。要在终端里更明显，请看 **stderr**（本脚本结束时会打一行）并依赖 **`beforeSubmitPrompt`** 钩子（`before-submit-harness-ping.py`，每条用户消息一次）。

**Cursor 编辑器**：可在 **设置 → Hooks** 或 **Hooks** 输出通道看子进程 **stderr**；需要每条经分发器的 hook 再打 stderr 时，设 ``WOW_HARNESS_STDERR_TRACE=1``。

**静默**：若不想写该文件，设 ``WOW_HARNESS_QUIET=1``。
"""
    print(banner.strip())
    try:
        print(
            "[wow-harness] SessionStart：上文「本会话已激活」已写入模型上下文；"
            "终端里若看不到表格属正常。活动日志: "
            f"tail -f {rel}",
            file=sys.stderr,
        )
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
