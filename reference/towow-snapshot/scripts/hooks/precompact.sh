#!/bin/bash
# PreCompact hook: 注入必须在 context compaction 中保留的关键信息
# [来源: ADR-038 D2.3 + D9 (v4 Objective Recitation), CC PreCompact hook — exit 0 追加为 compact 指令]

# 读取当前活跃的 PLAN/TASK/Issue 状态
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

cat <<'PRESERVE'
## 必须保留的关键信息

### 当前工作上下文
- 保留当前正在进行的 PLAN/TASK/Issue 的完整状态和进度
- 保留 Sprint Contract（如果有）的全部验收标准
- 保留当前 WP 的 scope 和验收条件

### 不可降级规则 (ADR-030 核心)
- Guard > Memory: 能机械化检测的必须写 guard
- 一个事实一个定义: 同一信息不得在多处重复定义
- 验证看最后一公里: 验证必须到达用户可观测的终点

### 行为约束
- 所有 commit message 必须中英双语
- 所有 subagent 必须使用 claude-opus-4-6
- 不得跳过 Gate 2/4/6/8 审查
- Issue 先于代码: 改代码前必须先创建 issue 文档
PRESERVE

# ── v4 D9: Objective Recitation ──
# [来源: Manus/IMPACT — recite objectives at end of context after ~50 tool calls]
# [来源: Cursor — 丢失 reasoning traces 导致 30% 性能下降]
# 在 compact 后的新上下文末尾追加原始目标，防止注意力漂移。
# KV cache 友好——只追加到末尾，不重排前文。
PROGRESS_FILE="$REPO_ROOT/.towow/progress/current.json"
if [ -f "$PROGRESS_FILE" ]; then
    echo ""
    echo "## Objective Recitation (v4 D9)"
    echo ""
    echo "**原始目标**（不可漂移，由 D8 Initializer Agent 写入后 read-only）："
    python3 -c "
import json, sys
try:
    data = json.load(open('$PROGRESS_FILE'))
    print(f\"  {data.get('objective', '<未设置>')}\")
    print()
    pending = [f for f in data.get('features', []) if f.get('status') != 'passing']
    if pending:
        print('**未完成 features**：')
        for f in pending:
            print(f\"  - [{f.get('status', '?')}] {f.get('id', '?')}: {f.get('subject', '')}\")
    else:
        print('**所有 features 已 passing**，可以进入 Stop 流程。')
except Exception as e:
    print(f'  <progress.json 解析失败: {e}>')
" 2>&1
fi

exit 0
