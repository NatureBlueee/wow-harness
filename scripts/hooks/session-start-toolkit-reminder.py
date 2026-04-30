#!/usr/bin/env python3
"""SessionStart hook — periodically remind user about manual harness toolkit entries.

[来源: 用户反馈 2026-04-07 — "这些东西要自动提醒我，比如说每三个小时...
       要不然的话我会忘掉我这个东西的存在的"
       — v5 之后大部分 hooks 是 transparent 的，但 5 个 user-facing 入口
         需要主动操作，平时藏得太深需要定期告知]

Why this exists:
- v5 之后的 13 个 hooks 大部分是 transparent (auto-trigger，用户不需要管)
- 但有 5 个入口需要用户主动跑：
  1. 看 .towow/proposals/ 里 trace-analyzer 的提议
  2. 重建 magic doc（source 改了之后）
  3. 跑全量 freshness check
  4. 调 TOWOW_RECITATION_EVERY 频率
  5. 看累计 metrics
- CC 没有 OS-level cron，最佳触发点是 SessionStart hook + 时间间隔检查
- 用户开发节奏：可能 2-3 小时换一次 session 或者持续跑一整天，
  靠记忆容易遗忘 → 每 ~3 小时主动提醒一次

Behavior:
- SessionStart 时检查 .towow/metrics/last-toolkit-reminder.txt
- 文件不存在 OR (now - last_ts) > 3 hours → 注入提醒片段，写新时间戳
- 否则静默 exit 0
- 永远 exit 0 (advisory, never block)

Configurable:
- TOWOW_TOOLKIT_REMINDER_INTERVAL_SEC (default: 10800 = 3h)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAST_REMINDER_FILE = REPO_ROOT / ".towow" / "metrics" / "last-toolkit-reminder.txt"

DEFAULT_INTERVAL_SEC = 3 * 60 * 60  # 3 hours
INTERVAL_SEC = int(os.environ.get("TOWOW_TOOLKIT_REMINDER_INTERVAL_SEC", DEFAULT_INTERVAL_SEC))

REMINDER_FRAGMENT = """
## 🛠️ Harness Toolkit Reminder (每 ~3 小时主动告知)

下面 5 个入口在 v5 hooks 之外，需要主动跑（v5 hooks 自身是 transparent 的，用户不用管）。
如果你（main agent）发现下面任一项有未读/未处理内容，请主动告知用户：

### 1. trace-analyzer 提议（SessionEnd 自动跑，但 propose 不自动落地）
```
ls -lt .towow/proposals/ | head -5
```
如果有 confidence ≥ 0.8 的 finding，建议建 issue (`docs/issues/...`) 跟踪。

### 2. 重建 magic doc（source 改了之后）
```
python3 scripts/checks/regenerate_magic_docs.py all          # 重建
python3 scripts/checks/regenerate_magic_docs.py all --check  # 只检查漂移
```

### 3. 全量文档漂移检测
```
python3 scripts/checks/check_doc_freshness.py
```

### 4. 调 D9 mid-task recitation 频率（默认 50 tool calls）
```
export TOWOW_RECITATION_EVERY=30   # 更频繁
export TOWOW_RECITATION_EVERY=100  # 更稀疏
```

### 5. 累计 metrics（v5 hooks 的实际效果数据）
```
cat .towow/metrics/tool-call-counter.txt        # 总 tool 调用数
wc -l .towow/metrics/guard-events.jsonl         # guard 触发次数
wc -l .towow/metrics/stop-events.jsonl          # stop check 次数
wc -l .towow/metrics/tool-failures.jsonl        # tool 失败次数
wc -l .towow/metrics/initializer-events.jsonl   # WP init 次数
ls .towow/proposals/                            # trace-analyzer 提议数
```

[来源: ADR-038 §12 + 用户反馈 2026-04-07]
"""


def _read_last_ts() -> float:
    if not LAST_REMINDER_FILE.exists():
        return 0.0
    try:
        return float(LAST_REMINDER_FILE.read_text(encoding="utf-8").strip() or "0")
    except (ValueError, OSError):
        return 0.0


def _write_last_ts(value: float) -> None:
    """Atomic write via tmp+rename to survive concurrent sessions."""
    try:
        LAST_REMINDER_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = LAST_REMINDER_FILE.with_suffix(".tmp")
        tmp.write_text(str(value), encoding="utf-8")
        os.rename(str(tmp), str(LAST_REMINDER_FILE))
    except OSError:
        pass


def main() -> int:
    now = time.time()
    last = _read_last_ts()
    if (now - last) < INTERVAL_SEC:
        return 0  # too soon, silent
    print(REMINDER_FRAGMENT)
    _write_last_ts(now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
