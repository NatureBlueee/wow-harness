#!/bin/bash
# beads-auto-link.sh
#
# 用法：./scripts/beads-auto-link.sh <EPIC_ID> <TASK_DIR>
#
# 功能：批量创建 beads 任务并自动关联 TASK 文档
#
# 示例：
#   ./scripts/beads-auto-link.sh E-014 docs/E-014-私聊聊天记录功能/task
#
# E014 复盘：15 个 TASK × 4 次操作 = 60 次手动命令 → 使用此脚本减少到 1 次

set -e

EPIC_ID="$1"
TASK_DIR="$2"

if [ -z "$EPIC_ID" ] || [ -z "$TASK_DIR" ]; then
  echo "用法: $0 <EPIC_ID> <TASK_DIR>"
  echo ""
  echo "示例:"
  echo "  $0 E-014 docs/E-014-私聊聊天记录功能/task"
  exit 1
fi

if [ ! -d "$TASK_DIR" ]; then
  echo "错误: TASK_DIR 不存在: $TASK_DIR"
  exit 1
fi

echo "🔗 开始批量创建 beads 任务并关联..."
echo "   EPIC_ID: $EPIC_ID"
echo "   TASK_DIR: $TASK_DIR"
echo ""

count=0
for task_file in "$TASK_DIR"/TASK-*.md; do
  if [ ! -f "$task_file" ]; then
    echo "⚠️  未找到 TASK 文件"
    continue
  fi

  task_id=$(basename "$task_file" .md)
  title=$(grep '^# ' "$task_file" | head -1 | sed 's/^# //')

  echo "📝 创建任务: $task_id"
  echo "   标题: $title"

  # 创建 beads 任务并自动设置 external_ref
  bd create "$task_id: $title" \
    --external-ref "$task_file" \
    --labels "$EPIC_ID"

  # 在 TASK 文档中添加 Beads ID
  beads_id=$(bd list --format json | jq -r ".[] | select(.title | startswith(\"$task_id\")) | .id" | head -1)

  if [ -n "$beads_id" ]; then
    # 检查是否已有 Beads 任务ID 注释
    if ! grep -q "Beads 任务ID" "$task_file"; then
      echo "" >> "$task_file"
      echo "> Beads 任务ID：\`$beads_id\`" >> "$task_file"
      echo "   ✅ 已关联 Beads ID: $beads_id"
    else
      echo "   ℹ️  TASK 文档已有 Beads ID，跳过"
    fi
  fi

  echo ""
  count=$((count + 1))
done

echo "✅ 完成！共处理 $count 个 TASK"
echo ""
echo "📋 验证命令："
echo "   bd show <BEADS_ID> | grep external_ref    # beads → TASK"
echo "   grep 'Beads 任务ID' $TASK_DIR/*.md | wc -l  # TASK → beads"
