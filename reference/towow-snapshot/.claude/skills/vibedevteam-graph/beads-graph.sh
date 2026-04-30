#!/bin/bash
# beads-graph.sh
#
# 用法：./scripts/beads-graph.sh <EPIC_ID> --output <OUTPUT_FILE>
#
# 功能：生成任务依赖可视化图（使用 Graphviz DOT 格式）
#
# 示例：
#   ./scripts/beads-graph.sh E-014 --output docs/E-014-私聊聊天记录功能/dependencies.svg
#
# 依赖：需要安装 Graphviz (brew install graphviz)

set -e

EPIC_ID="$1"
OUTPUT_FILE=""

# 解析参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    *)
      EPIC_ID="$1"
      shift
      ;;
  esac
done

if [ -z "$EPIC_ID" ]; then
  echo "用法: $0 <EPIC_ID> --output <OUTPUT_FILE>"
  echo ""
  echo "示例:"
  echo "  $0 E-014 --output docs/E-014-私聊聊天记录功能/dependencies.svg"
  exit 1
fi

if [ -z "$OUTPUT_FILE" ]; then
  OUTPUT_FILE="docs/${EPIC_ID}-dependencies.svg"
  echo "⚠️  未指定输出文件，使用默认: $OUTPUT_FILE"
fi

# 检查是否安装了 dot 命令
if ! command -v dot &> /dev/null; then
  echo "❌ 错误: 未安装 Graphviz"
  echo ""
  echo "请安装 Graphviz："
  echo "  macOS:   brew install graphviz"
  echo "  Ubuntu:  sudo apt-get install graphviz"
  echo "  CentOS:  sudo yum install graphviz"
  exit 1
fi

echo "📊 开始生成任务依赖图..."
echo "   EPIC_ID: $EPIC_ID"
echo "   OUTPUT: $OUTPUT_FILE"
echo ""

# 创建临时 DOT 文件
temp_dot=$(mktemp)

# 写入 DOT 文件头部
cat > "$temp_dot" << 'EOF'
digraph TaskDependencies {
  rankdir=LR;
  node [shape=box, style=rounded, fontname="Arial"];
  edge [fontname="Arial", fontsize=10];

  // 定义节点样式
  node [fontcolor="#333333"];

  // 已完成的任务
  node [fillcolor="#d4edda", style="rounded,filled"];

  // 进行中的任务
  node [fillcolor="#fff3cd", style="rounded,filled"];

  // 待开始的任务
  node [fillcolor="#f8d7da", style="rounded,filled"];
EOF

# 获取 beads 任务列表
beads_json=$(bd list --labels "$EPIC_ID" --format json)

# 添加节点和边
echo "" >> "$temp_dot"
echo "  // 任务节点" >> "$temp_dot"

# 记录任务状态映射
declare -A task_status
declare -A task_title

# 解析 beads 数据
echo "$beads_json" | jq -r '.[] | @json' | while read -r task_json; do
  id=$(echo "$task_json" | jq -r '.id')
  title=$(echo "$task_json" | jq -r '.title')
  status=$(echo "$task_json" | jq -r '.status')
  deps=$(echo "$task_json" | jq -r '.dependencies[]? // empty' | tr '\n' ',' | sed 's/,$//')

  # 提取简短标题（去除 TASK ID 前缀）
  short_title=$(echo "$title" | sed 's/^TASK-[A-Z0-9-]*: //' | cut -c1-20)

  # 根据状态选择颜色
  case "$status" in
    "done")
      fillcolor="#d4edda"
      fontcolor="#155724"
      ;;
    "in_progress")
      fillcolor="#fff3cd"
      fontcolor="#856404"
      ;;
    *)
      fillcolor="#f8d7da"
      fontcolor="#721c24"
      ;;
  esac

  # 添加节点
  echo "  \"$id\" [label=\"$short_title\", fillcolor=\"$fillcolor\", fontcolor=\"$fontcolor\"];" >> "$temp_dot"

  # 添加依赖边
  if [ -n "$deps" ]; then
    IFS=',' read -ra DEP_ARRAY <<< "$deps"
    for dep in "${DEP_ARRAY[@]}"; do
      echo "  \"$dep\" -> \"$id\";" >> "$temp_dot"
    done
  fi
done

# 写入 DOT 文件尾部
echo "}" >> "$temp_dot"

# 生成图片
echo "🎨 正在生成图片..."
dot -Tsvg "$temp_dot" -o "$OUTPUT_FILE"

# 清理临时文件
rm -f "$temp_dot"

echo "✅ 完成！"
echo ""
echo "📊 依赖图已生成: $OUTPUT_FILE"
echo ""
echo "💡 查看图片："
if [[ "$OSTYPE" == "darwin"* ]]; then
  echo "   open $OUTPUT_FILE"
else
  echo "   xdg-open $OUTPUT_FILE  # Linux"
  echo "   start $OUTPUT_FILE     # Windows"
fi
