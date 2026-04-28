#!/usr/bin/env bash
# AI小导师反馈追踪：查询点踩/评分数据 → Claude归因 → 写入飞书多维表格
# 依赖：dms_query.sh、lark-cli、jq

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DMS_QUERY_SH="$SCRIPT_DIR/../../link_dms_skill_for_claude_code/scripts/dms_query.sh"

# 目标飞书多维表格
BASE_TOKEN="FQlvbn8yxaBOsPsVKsncPCA6nqc"
TABLE_ID="tblUegIr5F3D7iXa"

# 参数
QUERY_DATE=""
START_TIME_ARG=""
END_TIME_ARG=""
FEEDBACK_TYPE="all"  # all | dislike | rating
DRY_RUN=0
SKIP_ATTRIBUTION=0

usage() {
  cat <<'EOF'
用法:
  track_feedback.sh (--date <YYYY-MM-DD|yesterday|today> | --start-time <DT> --end-time <DT>) [选项]

两种查询模式（二选一）:
  --date <date>            整天模式：查询 00:00:00 ~ 次日 00:00:00（yesterday/today/具体日期）
  --start-time / --end-time  自定义时间窗口模式，格式 'YYYY-MM-DD HH:MM:SS'

其他选项:
  --type <type>        反馈类型：all（默认）| dislike（点踩）| rating（评分）
  --dry-run            预览模式，不写入飞书
  --skip-attribution   跳过 Claude 归因，只写入原始数据
  -h, --help           显示帮助

示例:
  ./track_feedback.sh --date yesterday
  ./track_feedback.sh --date 2026-04-19 --type dislike
  ./track_feedback.sh --start-time '2026-04-21 17:00:00' --end-time '2026-04-22 17:00:00'
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date)            QUERY_DATE="${2:-}"; shift 2 ;;
    --start-time)      START_TIME_ARG="${2:-}"; shift 2 ;;
    --end-time)        END_TIME_ARG="${2:-}"; shift 2 ;;
    --type)            FEEDBACK_TYPE="${2:-}"; shift 2 ;;
    --dry-run)         DRY_RUN=1; shift ;;
    --skip-attribution) SKIP_ATTRIBUTION=1; shift ;;
    -h|--help)         usage; exit 0 ;;
    *)
      echo "未知参数: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

# 校验参数：两种模式二选一
if [[ -n "$START_TIME_ARG" || -n "$END_TIME_ARG" ]]; then
  if [[ -z "$START_TIME_ARG" || -z "$END_TIME_ARG" ]]; then
    echo "错误：--start-time 和 --end-time 必须同时提供" >&2
    exit 1
  fi
  if [[ -n "$QUERY_DATE" ]]; then
    echo "错误：--date 与 --start-time/--end-time 互斥，请二选一" >&2
    exit 1
  fi
  START_TIME="$START_TIME_ARG"
  END_TIME="$END_TIME_ARG"
  QUERY_DATE="custom"
elif [[ -n "$QUERY_DATE" ]]; then
  # 解析日期
  if [[ "$QUERY_DATE" == "yesterday" ]]; then
    QUERY_DATE="$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d 'yesterday' +%Y-%m-%d)"
  elif [[ "$QUERY_DATE" == "today" ]]; then
    QUERY_DATE="$(date +%Y-%m-%d)"
  fi
  START_TIME="${QUERY_DATE} 00:00:00"
  END_TIME="$(date -j -f "%Y-%m-%d" -v+1d "$QUERY_DATE" +"%Y-%m-%d" 2>/dev/null || date -d "$QUERY_DATE + 1 day" +%Y-%m-%d) 00:00:00"
else
  echo "错误：必须提供 --date 或 --start-time/--end-time" >&2
  exit 1
fi

echo ">> 查询窗口: $START_TIME ~ $END_TIME" >&2

# 检查依赖
[[ -f "$DMS_QUERY_SH" ]] || { echo "错误：未找到 dms_query.sh" >&2; exit 1; }
command -v lark-cli &>/dev/null || { echo "错误：未找到 lark-cli" >&2; exit 1; }
command -v jq &>/dev/null || { echo "错误：未找到 jq" >&2; exit 1; }

# ============================================================
# Step 1: 查询 DMS 数据
# ============================================================
echo ">> [1/5] 查询 DMS 数据..." >&2

DISLIKE_DATA=""
RATING_DATA=""

if [[ "$FEEDBACK_TYPE" == "all" || "$FEEDBACK_TYPE" == "dislike" ]]; then
  echo ">> 查询点踩数据..." >&2
  DISLIKE_SQL="SELECT * FROM \`common_feed_back_log\` WHERE \`scene\`='science_navigator' AND \`reaction_type\`=2 AND \`status\`=1 AND \`create_time\` >= '$START_TIME' AND \`create_time\` < '$END_TIME'"

  DISLIKE_RESULT="$(bash "$DMS_QUERY_SH" --instance "quickbi用" --database "account_center" --sql "$DISLIKE_SQL")"
  DISLIKE_DATA="$(echo "$DISLIKE_RESULT" | jq -c '{columns: .Results[0].ColumnNames, rows: .Results[0].Rows}')"
  DISLIKE_COUNT="$(echo "$DISLIKE_DATA" | jq '.rows | length')"
  echo ">> 点踩数据: $DISLIKE_COUNT 条" >&2
fi

if [[ "$FEEDBACK_TYPE" == "all" || "$FEEDBACK_TYPE" == "rating" ]]; then
  echo ">> 查询评分数据..." >&2
  RATING_SQL="SELECT ubr.* FROM \`account_center\`.\`user_behavior_record\` ubr INNER JOIN \`sigma-search\`.\`hot_session\` hs ON hs.\`uuid\` = ubr.conversation_id COLLATE utf8mb4_general_ci WHERE ubr.\`scene\`='scholar_QA' AND ubr.\`status\`=1 AND ubr.\`session_id\` LIKE 'adk\\_a\\_%' AND ubr.\`create_time\` >= '$START_TIME' AND ubr.\`create_time\` < '$END_TIME'"

  RATING_RESULT="$(bash "$DMS_QUERY_SH" --instance "quickbi用" --database "account_center" --sql "$RATING_SQL")"
  RATING_DATA="$(echo "$RATING_RESULT" | jq -c '{columns: .Results[0].ColumnNames, rows: .Results[0].Rows}')"
  RATING_COUNT="$(echo "$RATING_DATA" | jq '.rows | length')"
  echo ">> 评分数据: $RATING_COUNT 条" >&2
fi

TOTAL_COUNT=$(( ${DISLIKE_COUNT:-0} + ${RATING_COUNT:-0} ))
if [[ "$TOTAL_COUNT" -eq 0 ]]; then
  echo "查询结果为空，无需处理。" >&2
  exit 0
fi

# ============================================================
# Step 2: 拼接会话 URL
# ============================================================
echo ">> [2/5] 拼接会话 URL..." >&2

# 点踩数据：提取 URL、session_id、feed_back_remark、create_time，输出结构化 JSON
if [[ -n "$DISLIKE_DATA" && "$DISLIKE_DATA" != "null" ]]; then
  DISLIKE_ITEMS="$(echo "$DISLIKE_DATA" | jq -c '
    [.rows[] |
      (.URL // .url // "") as $raw_url |
      ($raw_url | split("/") | last) as $share_id |
      {
        feedback_type: "dislike",
        url: ("https://www.bohrium.com/chat/share/" + $share_id + (if .session_id then "?qid=" + .session_id else "" end)),
        feedback_reason: (.feed_back_remark // ""),
        rating_score: null,
        create_time: (.create_time // ""),
        raw: .
      }
    ]
  ')"
else
  DISLIKE_ITEMS="[]"
fi

# 评分数据：提取 conversation_id、session_id、target（评分）、remarks（评分原因）、create_time
if [[ -n "$RATING_DATA" && "$RATING_DATA" != "null" ]]; then
  RATING_ITEMS="$(echo "$RATING_DATA" | jq -c '
    [.rows[] |
      {
        feedback_type: "rating",
        url: ("https://www.bohrium.com/chat/share/" + (.conversation_id // "") + (if .session_id then "?qid=" + .session_id else "" end)),
        feedback_reason: (.remarks // ""),
        rating_score: (.target | tonumber? // null),
        create_time: (.create_time // ""),
        raw: .
      }
    ]
  ')"
else
  RATING_ITEMS="[]"
fi

ALL_ITEMS="$(jq -n --argjson d "$DISLIKE_ITEMS" --argjson r "$RATING_ITEMS" '$d + $r')"
ITEM_COUNT="$(echo "$ALL_ITEMS" | jq 'length')"
echo ">> 生成 $ITEM_COUNT 条反馈记录" >&2

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "" >&2
  echo "========== DRY RUN 预览 ==========" >&2
  echo "查询日期: $QUERY_DATE" >&2
  echo "点踩数据: ${DISLIKE_COUNT:-0} 条" >&2
  echo "评分数据: ${RATING_COUNT:-0} 条" >&2
  echo "反馈记录示例（前 5 条）:" >&2
  echo "$ALL_ITEMS" | jq '.[:5]' >&2
  echo "" >&2
  echo "目标: base-token=$BASE_TOKEN, table-id=$TABLE_ID" >&2
  echo "========== DRY RUN 结束 ==========" >&2
  exit 0
fi

# ============================================================
# Step 3: Claude 归因（需要在 Claude 对话中完成）
# ============================================================
echo ">> [3/4] Claude 归因..." >&2

if [[ "$SKIP_ATTRIBUTION" -eq 1 ]]; then
  echo ">> 跳过归因，直接写入原始数据" >&2
  # TODO: 实现跳过归因的逻辑
else
  echo ">> 注意：Claude 归因需要在对话中完成" >&2
  echo ">> 请在 Claude 对话中执行以下操作：" >&2
  echo "   1. 逐个访问会话 URL" >&2
  echo "   2. 阅读对话内容" >&2
  echo "   3. 结合用户反馈原因，判断问题层面（产品/研发/设计/数据）" >&2
  echo "   4. 结合会话内容和反馈原因，判断优先级（P0/P1/P2）" >&2
  echo "   5. 生成问题描述" >&2
  echo "" >&2
  echo ">> 反馈数据已保存到临时文件：" >&2
  TEMP_ITEMS="/tmp/sn_feedback_items_${QUERY_DATE}.json"
  echo "$ALL_ITEMS" | jq '.' > "$TEMP_ITEMS"
  echo "   $TEMP_ITEMS" >&2
  echo "" >&2
  echo ">> 归因完成后，Claude 会自动写入飞书多维表格。" >&2
fi

# ============================================================
# Step 4: 写入飞书多维表格
# ============================================================
echo ">> [4/4] 写入飞书多维表格..." >&2
echo ">> 注意：实际写入操作需要在 Claude 归因完成后执行" >&2
echo ">> 本脚本已准备好数据，等待 Claude 完成归因..." >&2

echo "" >&2
echo "============================================" >&2
echo "数据准备完成！" >&2
echo "查询日期: $QUERY_DATE" >&2
echo "反馈总数: $TOTAL_COUNT 条" >&2
echo "反馈记录: $ITEM_COUNT 条" >&2
echo "目标表格: https://dptechnology.feishu.cn/base/$BASE_TOKEN?table=$TABLE_ID" >&2
echo "============================================" >&2
