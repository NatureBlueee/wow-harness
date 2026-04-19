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

**Cursor**：可在 **设置 → Hooks** 或 **Hooks** 输出通道看子进程日志；若需要每条 hook 在 stderr 再打一行短标记，可在环境里设 ``WOW_HARNESS_STDERR_TRACE=1``。

**静默**：若不想写该文件，设 ``WOW_HARNESS_QUIET=1``。
"""
    print(banner.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
