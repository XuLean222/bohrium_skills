#!/usr/bin/env python3
"""
飞书多维表格操作模块 — 通过 lark-cli api 命令行调用飞书 Bitable API
"""
import json
import logging
import subprocess

logger = logging.getLogger(__name__)

# ============ 配置区 ============
LARK_APP_TOKEN = ""       # 多维表格 app_token，参考 README 获取
LARK_TABLE_ID = ""        # 数据表 table_id，已有表则填入，留空则自动创建
TABLE_NAME = "SN搜索评测结果"  # 自动创建时的表名
# ================================

# 评分字段列表（与 agent_workflow.py 中 get_score 的 target_fields 对齐）
SCORE_FIELDS = [
    "忠实度评分", "回答相关性评分", "上下文相关性评分", "上下文精确率评分",
    "首次响应时间评分", "文献时效性评分", "Top6文献时效性评分",
    "文献质量评分", "Top6文献质量评分", "回答完整性",
    "思考过程 / Query 改写准确性", "证据检索来源相关性",
    "输出格式自适应能力", "限制条件识别能力", "回答逻辑性",
]

# 理由维度名列表（score_reasons_json 的 key，即 SCORE_FIELDS 去掉"评分"后缀）
REASON_DIMENSIONS = [f.replace("评分", "").strip() for f in SCORE_FIELDS]

# 理由字段列表：每个维度拆成 满分理由 + 扣分理由
REASON_FIELDS = []
for dim in REASON_DIMENSIONS:
    REASON_FIELDS.append(f"{dim}满分理由")
    REASON_FIELDS.append(f"{dim}扣分理由")

# 评分+理由交错排列：每个维度依次为 评分(数字)、满分理由(文本)、扣分理由(文本)
_SCORE_REASON_FIELDS = []
for score_field, dim in zip(SCORE_FIELDS, REASON_DIMENSIONS):
    _SCORE_REASON_FIELDS.append({"field_name": score_field, "type": 2})        # 评分
    _SCORE_REASON_FIELDS.append({"field_name": f"{dim}满分理由", "type": 1})   # 满分理由
    _SCORE_REASON_FIELDS.append({"field_name": f"{dim}扣分理由", "type": 1})   # 扣分理由

# 创建表时的字段定义
TABLE_FIELDS = [
    {"field_name": "query", "type": 1},              # 文本
    {"field_name": "session_id", "type": 1},          # 文本
    {"field_name": "share_url", "type": 15},          # 链接
    {"field_name": "keywords", "type": 1},            # 文本 (JSON)
    {"field_name": "sub_query", "type": 1},           # 文本 (JSON)
    {"field_name": "summary", "type": 1},             # 文本
    {"field_name": "papers", "type": 1},              # 文本 (JSON)
    {"field_name": "papers_count", "type": 2},        # 数字
    {"field_name": "evidence_search", "type": 1},     # 文本 (JSON)
    {"field_name": "summary_first_token", "type": 2}, # 数字
    {"field_name": "ai_analysis", "type": 1},         # 文本
    {"field_name": "model", "type": 1},               # 文本
    {"field_name": "scene", "type": 1},               # 文本
    {"field_name": "env", "type": 1},                 # 文本
    {"field_name": "task", "type": 1},                 # 文本 (task_时间戳)
    {"field_name": "创建时间", "type": 1001},          # 飞书自动创建时间
] + _SCORE_REASON_FIELDS


def _run_lark_cli(method, path, data=None, params=None):
    """通过 subprocess 调用 lark-cli api，返回解析后的 JSON 结果"""
    cmd = ["lark-cli", "api", method, path]
    if data is not None:
        cmd += ["--data", json.dumps(data, ensure_ascii=False)]
    if params is not None:
        cmd += ["--params", json.dumps(params, ensure_ascii=False)]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        logger.error(f"lark-cli failed: {result.stderr}")
        raise RuntimeError(f"lark-cli exited with code {result.returncode}: {result.stderr}")

    resp = json.loads(result.stdout)

    # lark-cli 错误时返回 {"ok": false, "error": {...}}
    if "ok" in resp and not resp["ok"]:
        error = resp.get("error", {})
        raise RuntimeError(f"Lark CLI error: {error.get('message', resp)}")

    # Lark API 成功时返回 {"code": 0, "data": {...}, "msg": "success"}
    if resp.get("code", 0) != 0:
        raise RuntimeError(f"Lark API error: code={resp.get('code')}, msg={resp.get('msg')}")

    return resp.get("data", {})


def ensure_table(app_token):
    """确保数据表存在且字段完整。如果 LARK_TABLE_ID 已配置则使用它；
    否则按表名查找，找不到则创建。最后补齐缺失字段。返回 table_id。"""
    table_id = None

    if LARK_TABLE_ID:
        logger.info(f"使用已配置的 table_id: {LARK_TABLE_ID}")
        table_id = LARK_TABLE_ID
    else:
        # 列出已有数据表
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables"
        data = _run_lark_cli("GET", path)
        items = data.get("items", [])

        # 按名称查找
        for item in items:
            if item.get("name") == TABLE_NAME:
                table_id = item["table_id"]
                logger.info(f"找到已有数据表 '{TABLE_NAME}': {table_id}")
                break

        if not table_id:
            # 创建新表
            logger.info(f"未找到数据表 '{TABLE_NAME}'，开始创建...")
            create_data = {
                "table": {
                    "name": TABLE_NAME,
                    "default_view_name": "默认视图",
                    "fields": TABLE_FIELDS,
                }
            }
            result = _run_lark_cli("POST", path, data=create_data)
            table_id = result.get("table_id", "")
            logger.info(f"数据表创建成功: {table_id}")
            return table_id  # 新建表已包含所有字段，无需补齐

    # 补齐已有表中缺失的字段
    fields_path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
    existing = _run_lark_cli("GET", fields_path)
    existing_names = {item["field_name"] for item in existing.get("items", [])}

    for field_def in TABLE_FIELDS:
        if field_def["field_name"] not in existing_names:
            logger.info(f"创建缺失字段: {field_def['field_name']}")
            _run_lark_cli("POST", fields_path, data=field_def)

    return table_id


def insert_record(app_token, table_id, record_fields):
    """向数据表插入一条记录"""
    path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    data = {"fields": record_fields}
    result = _run_lark_cli("POST", path, data=data)
    record_id = result.get("record", {}).get("record_id", "")
    logger.info(f"记录插入成功: {record_id}")
    return record_id


def build_record_fields(query, answer_result, ai_analysis, score_json, score_reasons_json, model, scene, env, task_id=""):
    """将各数据源展平为飞书多维表格的 fields dict"""
    papers = answer_result.get("papers", [])
    keywords = answer_result.get("keywords", [])
    sub_query = answer_result.get("sub_query", [])
    evidence_search = answer_result.get("evidence_search", [])

    fields = {
        "query": query,
        "session_id": answer_result.get("session_id", ""),
        "share_url": {"text": answer_result.get("share_url", ""), "link": answer_result.get("share_url", "")},
        "keywords": json.dumps(keywords, ensure_ascii=False) if keywords else "无",
        "sub_query": json.dumps(sub_query, ensure_ascii=False) if sub_query else "无",
        "summary": answer_result.get("summary", "") or "无",
        "papers": json.dumps(papers, ensure_ascii=False) if papers else "无",
        "papers_count": len(papers),
        "evidence_search": json.dumps(evidence_search, ensure_ascii=False) if evidence_search else "无",
        "summary_first_token": answer_result.get("summary_first_token", 0),
        "ai_analysis": (ai_analysis if isinstance(ai_analysis, str) else json.dumps(ai_analysis, ensure_ascii=False)) or "无",
        "model": model,
        "scene": scene,
        "env": env,
        "task": task_id,
    }

    # 展开评分字段 — 无论 score_json 是否有值，都写入（缺失的写 0）
    if score_json and isinstance(score_json, dict):
        for field_name in SCORE_FIELDS:
            fields[field_name] = score_json.get(field_name, 0)
    else:
        for field_name in SCORE_FIELDS:
            fields[field_name] = 0

    # 展开理由字段 — 每个维度拆成 满分理由 + 扣分理由
    for dim in REASON_DIMENSIONS:
        reasons = score_reasons_json.get(dim, {}) if score_reasons_json and isinstance(score_reasons_json, dict) else {}
        fields[f"{dim}满分理由"] = reasons.get("满分理由", "")
        fields[f"{dim}扣分理由"] = reasons.get("扣分理由", "")

    return fields
