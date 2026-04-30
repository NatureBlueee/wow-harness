#!/bin/bash
# beads-sync-proj.sh
#
# 用法：./scripts/beads-sync-proj.sh <PROJ_FILE>
#
# 功能：从 beads 批量同步状态到 PROJ 文档
#
# 示例：
#   ./scripts/beads-sync-proj.sh docs/E-014-私聊聊天记录功能/proj/PROJ-E-014-v1.md
#
# 注意：此脚本会更新 PROJ 文档中的任务状态，建议在执行前备份

set -e

PROJ_FILE="$1"

if [ -z "$PROJ_FILE" ]; then
  echo "用法: $0 <PROJ_FILE>"
  echo ""
  echo "示例:"
  echo "  $0 docs/E-014-私聊聊天记录功能/proj/PROJ-E-014-v1.md"
  exit 1
fi

if [ ! -f "$PROJ_FILE" ]; then
  echo "错误: PROJ 文件不存在: $PROJ_FILE"
  exit 1
fi

# 备份原文件
backup_file="${PROJ_FILE}.backup.$(date +%Y%m%d%H%M%S)"
cp "$PROJ_FILE" "$backup_file"
echo "📦 已备份原文件到: $backup_file"
echo ""

echo "🔄 开始从 beads 同步状态到 PROJ 文档..."
echo "   PROJ_FILE: $PROJ_FILE"
echo ""

# 获取所有 beads 任务（JSON 格式）
beads_json=$(bd list --format json)

# 统计
updated=0
not_found=0

# 遍历每个 beads 任务，更新 PROJ 文档中的状态
echo "$beads_json" | jq -r '.[] | @json' | while read -r task_json; do
  title=$(echo "$task_json" | jq -r '.title')
  status=$(echo "$task_json" | jq -r '.status')
  id=$(echo "$task_json" | jq -r '.id')

  # 提取 TASK ID（例如 TASK-E014-BE-001）
  task_id=$(echo "$title" | grep -oE 'TASK-[A-Z0-9-]+' || true)

  if [ -z "$task_id" ]; then
    continue
  fi

  echo "📝 $task_id"
  echo "   Beads ID: $id"
  echo "   状态: $status"

  # 检查 PROJ 文档中是否包含此任务
  if grep -q "$task_id" "$PROJ_FILE"; then
    # 更新状态（使用 sed 进行替换）
    # 匹配模式：| TASK-ID | 旧状态 | -> | TASK-ID | 新状态 |
    case "$status" in
      "open")
        new_status="待开始"
        ;;
      "in_progress")
        new_status="进行中"
        ;;
      "done")
        new_status="已完成"
        ;;
      *)
        new_status="$status"
        ;;
    esac

    # 使用 macOS 兼容的 sed 命令
    if [[ "$OSTYPE" == "darwin"* ]]; then
      sed -i.bak "s/| $task_id | [^|]* |/| $task_id | $new_status |/" "$PROJ_FILE"
      rm -f "${PROJ_FILE}.bak"
    else
      sed -i "s/| $task_id | [^|]* |/| $task_id | $new_status |/" "$PROJ_FILE"
    fi

    echo "   ✅ 已更新状态: $new_status"
    updated=$((updated + 1))
  else
    echo "   ⚠️  PROJ 文档中未找到此任务"
    not_found=$((not_found + 1))
  fi

  echo ""
done

echo "✅ 同步完成！"
echo ""
echo "📊 统计："
echo "   已更新: $updated 个"
echo "   未找到: $not_found 个"
echo ""
echo "🔍 查看更新后的 PROJ 文档："
echo "   cat $PROJ_FILE"
