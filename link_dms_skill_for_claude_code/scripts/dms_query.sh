#!/usr/bin/env bash
# 根据 DMS 实例展示名（InstanceAlias）、库名（SchemaName）解析 ID 并执行 SQL 或创建导出工单。
# 依赖：aliyun CLI、jq、已 aliyun configure 的凭证。
# 用法：./dms_query.sh --help

set -euo pipefail

REGION="${REGION:-cn-zhangjiakou}"
ENDPOINT="${ENDPOINT:-dms-enterprise.cn-zhangjiakou.aliyuncs.com}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ALIYUN="${SCRIPT_DIR}/../tools/aliyun"

if [[ -n "${ALIYUN_CLI:-}" ]]; then
  ALIYUN="$ALIYUN_CLI"
elif [[ -x "$REPO_ALIYUN" ]]; then
  ALIYUN="$REPO_ALIYUN"
elif command -v aliyun &>/dev/null; then
  ALIYUN="$(command -v aliyun)"
else
  echo "未找到 aliyun：请设置 ALIYUN_CLI 或安装 CLI，或使用仓库内 tools/aliyun" >&2
  exit 1
fi

command -v jq &>/dev/null || { echo "请先安装 jq（如 brew install jq）" >&2; exit 1; }

INSTANCE_NAME=""
DATABASE_NAME=""
SQL_TEXT=""
SQL_FILE=""
LOGIC="false"
MODE="query"
DRY_RUN=0
AFFECT_ROWS="${AFFECT_ROWS:-100000}"
CLASSIFY="${CLASSIFY:-业务导出}"
ORDER_COMMENT="${ORDER_COMMENT:-DMS CLI 导出工单}"
SCENARIO_ID=""
LIST_SCENARIOS=0
SCENARIOS_JSON="$SCRIPT_DIR/dms_scenarios.json"

usage() {
  cat <<'EOF'
用法:
  dms_query.sh --instance <DMS实例别名或SearchKey> --database <库名SchemaName> --sql '<SQL>'
  dms_query.sh --instance ... --database ... --sql-file /path/to/query.sql
  dms_query.sh --scenario <序号>              # 使用预置场景（见 dms_scenarios.json / Skill scenarios.md）
  dms_query.sh --list-scenarios               # 打印全部预置场景

选项:
  --instance, -i   DMS 控制台中的实例名/别名（InstanceAlias），或 ListInstances 的 SearchKey
  --database, -d   库名（SchemaName）
  --sql, -s        要执行的 SQL（查询建议只用 SELECT；DML/DDL 受实例安全规则约束）
  --sql-file, -f   从文件读取 SQL（优先级高于 --sql）
  --scenario, -S   预置场景序号（1–14，与 sql语句.xlsx 序号一致）；自动绑定实例名、库名与 sql/scenario-XX.sql
  --list-scenarios 列出预置场景后退出
  --logic          逻辑库时传入；默认按物理库（Logic=false）
  --export         创建「SQL 结果集导出」工单（需控制台审批后再 ExecuteDataExport）
  --dry-run        只解析并打印 InstanceId、DatabaseId，不执行
  --affect-rows    与 --export 连用，PluginParam.AffectRows（默认 100000）
  --classify       与 --export 连用，PluginParam.Classify
  --comment        与 --export 连用，工单 Comment

环境变量:
  REGION, ENDPOINT      默认张家口
  ALIYUN_CLI            指定 aliyun 可执行文件路径
  TID                   若设置，所有请求追加 --Tid
  EXPORT_IGNORE_ROWS    设为 true 时 PluginParam.IgnoreAffectRows=true（需配合 EXPORT_IGNORE_REASON）
  EXPORT_IGNORE_REASON  跳过行数校验原因

示例:
  ./scripts/dms_query.sh -i "生产MySQL" -d account_center -s "SELECT 1"
  ./scripts/dms_query.sh -i "生产MySQL" -d account_center -f ./my_query.sql --dry-run
  ./scripts/dms_query.sh -i "生产MySQL" -d account_center -s "SELECT * FROM t LIMIT 10" --export
  ./scripts/dms_query.sh --list-scenarios
  ./scripts/dms_query.sh --scenario 11 --dry-run
  ./scripts/dms_query.sh --scenario 9 --export
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance|-i) INSTANCE_NAME="${2:-}"; shift 2 ;;
    --database|-d) DATABASE_NAME="${2:-}"; shift 2 ;;
    --sql|-s) SQL_TEXT="${2:-}"; shift 2 ;;
    --sql-file|-f) SQL_FILE="${2:-}"; shift 2 ;;
    --scenario|-S) SCENARIO_ID="${2:-}"; shift 2 ;;
    --list-scenarios) LIST_SCENARIOS=1; shift ;;
    --logic) LOGIC="true"; shift ;;
    --export) MODE="export"; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --affect-rows) AFFECT_ROWS="${2:-}"; shift 2 ;;
    --classify) CLASSIFY="${2:-}"; shift 2 ;;
    --comment) ORDER_COMMENT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "未知参数: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$LIST_SCENARIOS" -eq 1 ]]; then
  [[ -f "$SCENARIOS_JSON" ]] || { echo "缺少 $SCENARIOS_JSON，请运行 python3 scripts/sync_scenarios_from_xlsx.py" >&2; exit 1; }
  echo "序号 | 使用场景 | 实例 | 库 | sql 文件"
  echo "--- | --- | --- | --- | ---"
  jq -r '.[] | "\(.id) | \(.title) | \(.instance) | \(.database) | \(.sql_file)"' "$SCENARIOS_JSON"
  exit 0
fi

if [[ -n "$SCENARIO_ID" ]]; then
  [[ -f "$SCENARIOS_JSON" ]] || { echo "缺少 $SCENARIOS_JSON" >&2; exit 1; }
  if [[ -n "$INSTANCE_NAME" || -n "$DATABASE_NAME" || -n "$SQL_TEXT" || -n "$SQL_FILE" ]]; then
    echo "使用 --scenario 时不要同时使用 -i / -d / -s / -f" >&2
    exit 1
  fi
  ROW="$(jq -c --arg id "$SCENARIO_ID" '.[] | select((.id | tonumber) == ($id | tonumber))' "$SCENARIOS_JSON" | head -n1)"
  [[ -n "$ROW" ]] || { echo "未找到场景序号: $SCENARIO_ID（执行 --list-scenarios 查看）" >&2; exit 1; }
  INSTANCE_NAME="$(echo "$ROW" | jq -r '.instance')"
  DATABASE_NAME="$(echo "$ROW" | jq -r '.database')"
  REL_SQL="$(echo "$ROW" | jq -r '.sql_file')"
  SQL_FILE="$SCRIPT_DIR/$REL_SQL"
  [[ -f "$SQL_FILE" ]] || { echo "缺少 SQL 文件: $SQL_FILE" >&2; exit 1; }
  SQL_TEXT="$(cat "$SQL_FILE")"
  echo ">> 场景 $(echo "$ROW" | jq -r '.id'): $(echo "$ROW" | jq -r '.title')" >&2
  echo ">> SQL 文件: $SQL_FILE" >&2
  NOTES="$(echo "$ROW" | jq -r '.notes')"
  if [[ -n "$NOTES" && "$NOTES" != "null" ]]; then
    echo ">> 备注（来自 Excel）：" >&2
    echo "$NOTES" | sed 's/^/   /' >&2
  fi
fi

if [[ -n "$SQL_FILE" ]]; then
  [[ -f "$SQL_FILE" ]] || { echo "文件不存在: $SQL_FILE" >&2; exit 1; }
  SQL_TEXT="$(cat "$SQL_FILE")"
fi

if [[ -z "$INSTANCE_NAME" || -z "$DATABASE_NAME" ]]; then
  echo "必须提供 --instance 与 --database，或提供 --scenario" >&2
  usage >&2
  exit 1
fi

if [[ "$MODE" == "query" && -z "$SQL_TEXT" ]]; then
  echo "查询模式必须提供 --sql 或 --sql-file" >&2
  exit 1
fi

if [[ "$MODE" == "export" && -z "$SQL_TEXT" ]]; then
  echo "导出工单模式必须提供 --sql 或 --sql-file（作为 ExeSQL）" >&2
  exit 1
fi

# Bash 3.2 + set -u：空数组 "${arr[@]}" 会报 unbound，故按 TID 分支调用，勿用可选数组展开。
aliyun_dms() {
  if [[ -n "${TID:-}" ]]; then
    "$ALIYUN" dms-enterprise "$@" --region "$REGION" --endpoint "$ENDPOINT" --Tid "$TID"
  else
    "$ALIYUN" dms-enterprise "$@" --region "$REGION" --endpoint "$ENDPOINT"
  fi
}

normalize_instances_json() {
  jq '(.InstanceList.Instance // null)
    | if . == null then []
      elif type == "array" then .
      else [.]
      end'
}

normalize_databases_json() {
  jq '(.DatabaseList.Database // null)
    | if . == null then []
      elif type == "array" then .
      else [.]
      end'
}

echo ">> ListInstances SearchKey=$INSTANCE_NAME ..." >&2
INST_JSON="$(aliyun_dms ListInstances --SearchKey "$INSTANCE_NAME" --PageSize 100)"

INSTANCE_ID="$(echo "$INST_JSON" | normalize_instances_json | jq -r --arg want "$INSTANCE_NAME" '
  if length == 0 then "ERROR_NO_INSTANCE"
  elif length == 1 then (.[0].InstanceId | tostring)
  else
    (map(select(.InstanceAlias == $want))) as $ex |
    if ($ex | length) == 1 then ($ex[0].InstanceId | tostring)
    elif ($ex | length) > 1 then "ERROR_MULTI"
    else
      if ($want | test("rm-")) then
        (map(select((.Host // "") | contains($want)))) as $h |
        if ($h | length) == 1 then ($h[0].InstanceId | tostring)
        else "ERROR_AMBIGUOUS" end
      else "ERROR_AMBIGUOUS" end
    end
  end
')"

case "$INSTANCE_ID" in
  ERROR_NO_INSTANCE)
    echo "未找到匹配实例，请检查 --instance 或扩大 SearchKey。" >&2
    echo "$INST_JSON" | jq '.' >&2 || echo "$INST_JSON" >&2
    exit 1
    ;;
  ERROR_AMBIGUOUS|ERROR_MULTI)
    echo "匹配到多个实例，请使用更精确的实例别名，或从下列结果中确认 InstanceId：" >&2
    echo "$INST_JSON" | normalize_instances_json | jq -r '.[] | "\(.InstanceId)\t\(.InstanceAlias // "-")\t\(.Host // "-")"' >&2
    exit 1
    ;;
esac

echo ">> 解析得到 InstanceId=$INSTANCE_ID" >&2

echo ">> ListDatabases InstanceId=$INSTANCE_ID SearchKey=$DATABASE_NAME ..." >&2
DB_JSON="$(aliyun_dms ListDatabases --InstanceId "$INSTANCE_ID" --SearchKey "$DATABASE_NAME" --PageSize 100)"

DB_ID="$(echo "$DB_JSON" | normalize_databases_json | jq -r --arg db "$DATABASE_NAME" '
  if length == 0 then "ERROR_NO_DB"
  else
    (map(select(.SchemaName == $db))) as $m |
    if ($m | length) == 0 then "ERROR_NO_DB"
    elif ($m | length) > 1 then "ERROR_MULTI_DB"
    else ($m[0].DatabaseId | tostring)
    end
  end
')"

case "$DB_ID" in
  ERROR_NO_DB)
    echo "未找到库名 SchemaName=$DATABASE_NAME，请检查 --database。" >&2
    echo "$DB_JSON" | jq '.DatabaseList' >&2 || echo "$DB_JSON" >&2
    exit 1
    ;;
  ERROR_MULTI_DB)
    echo "同实例下存在多条同名库记录，请人工核对 JSON：" >&2
    echo "$DB_JSON" | jq '.' >&2
    exit 1
    ;;
esac

echo ">> 解析得到 DatabaseId(DbId)=$DB_ID" >&2

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '{"InstanceId":"%s","DatabaseId":"%s","Logic":%s}\n' "$INSTANCE_ID" "$DB_ID" "$LOGIC"
  exit 0
fi

if [[ "$MODE" == "query" ]]; then
  echo ">> ExecuteScript ..." >&2
  aliyun_dms ExecuteScript \
    --DbId "$DB_ID" \
    --Logic "$LOGIC" \
    --Script "$SQL_TEXT"
  exit 0
fi

# export: CreateDataExportOrder
IGNORE_ROWS="${EXPORT_IGNORE_ROWS:-false}"
IGNORE_REASON="${EXPORT_IGNORE_REASON:-}"

PLUGIN="$(jq -n \
  --arg iid "$INSTANCE_ID" \
  --arg dbid "$DB_ID" \
  --argjson ar "$(jq -n --arg x "$AFFECT_ROWS" '($x | tonumber)')" \
  --arg cl "$CLASSIFY" \
  --arg logic "$LOGIC" \
  --arg ign "$IGNORE_ROWS" \
  --arg ignr "$IGNORE_REASON" \
  --arg sql "$SQL_TEXT" \
  '{
    AffectRows: $ar,
    Classify: $cl,
    InstanceId: ($iid | tonumber),
    DbId: ($dbid | tonumber),
    Logic: ($logic == "true"),
    IgnoreAffectRows: ($ign == "true"),
    ExeSQL: $sql
  }
  | if .IgnoreAffectRows and ($ignr | length > 0) then . + {IgnoreAffectRowsReason: $ignr} else . end')"

echo ">> CreateDataExportOrder ..." >&2
CREATE_OUT="$(aliyun_dms CreateDataExportOrder \
  --Comment "$ORDER_COMMENT" \
  --PluginParam "$PLUGIN")"
echo "$CREATE_OUT"

ORDER_ID="$(echo "$CREATE_OUT" | jq -r '
  def firstid:
    if type == "array" then .[0] elif type == "number" or type == "string" then . else empty end;
  (.CreateOrderResult.CreateOrderResult // null) | firstid // empty
  | if . == null or . == "" then empty else tostring end
')"

if [[ -z "$ORDER_ID" || "$ORDER_ID" == "null" ]]; then
  ORDER_ID="$(echo "$CREATE_OUT" | jq -r '(.CreateOrderResult // []) | if type == "array" then .[0] | tostring else empty end')"
fi

echo "" >&2
echo "================================================================================" >&2
if [[ -n "$ORDER_ID" && "$ORDER_ID" != "null" ]]; then
  echo "【工单 ID】$ORDER_ID" >&2
  echo "" >&2
  echo "请将上述工单 ID 提交给「本 DMS 实例 / 目标库」的负责人（如库 Owner、DBA）在 DMS 控制台完成审批。" >&2
  echo "上下文：实例展示名/SearchKey=$INSTANCE_NAME ，库 SchemaName=$DATABASE_NAME ，DMS InstanceId=$INSTANCE_ID ，DbId=$DB_ID" >&2
  echo "" >&2
  echo "审批通过后，在 Cursor 对话中明确告知 Skill/Agent，例如：" >&2
  echo "  「工单 $ORDER_ID 已在 DMS 审批通过，请继续执行导出（ExecuteDataExport）并获取下载链接。」" >&2
else
  echo "【未能从返回 JSON 自动解析工单 ID】请从上方原始输出中查找 CreateOrderResult，或到 DMS 控制台「我的工单」核对。" >&2
fi
echo "================================================================================" >&2
echo "" >&2
echo "审批通过后在本机执行（将 ORDER_ID 替换为实际工单号）：" >&2
echo "  $ALIYUN dms-enterprise ExecuteDataExport --region $REGION --endpoint $ENDPOINT --OrderId ORDER_ID \\" >&2
echo "       --ActionDetail '{\"mode\":\"FAST\",\"encoding\":\"UTF8\",\"fileType\":\"CSV\",\"transaction\":false}'" >&2
echo "  $ALIYUN dms-enterprise GetDataExportDownloadURL --region $REGION --endpoint $ENDPOINT --OrderId ORDER_ID" >&2
