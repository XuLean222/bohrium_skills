#!/usr/bin/env python3
"""
Run a single SN search query and save formatted results.
"""
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from agent_workflow import AgentWorkflow
try:
    from opik_client import OpikClient
except ImportError:
    OpikClient = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s [%(threadName)s]: %(message)s')


def sanitize_filename(query):
    """Convert query to safe filename."""
    safe = "".join(c if c.isalnum() or c in (' ', '-', '_', '，', '。') else '_' for c in query)
    safe = safe.strip().replace(' ', '_')[:50]
    return safe


def run_single_search(token, query, discipline="All", journal_type="both", output_dir=".", task_id=None):
    """Run a single search and save formatted result.

    Args:
        discipline: "All" | "NS" | "ET" | "LS" | "PSS"
                    (全部 / 自然科学 / 工程技术 / 生命科学 / 哲学与社会科学)
        journal_type: "both" | "foreign" | "chinese" | "chinese_tech"
                      (全部期刊 / 国际期刊 / 中国期刊 / 科协期刊集群)
    """
    try:
        from sn_search import SNSearch
    except ImportError:
        logging.error("Cannot import SNSearch. Make sure sn_search.py is in the current directory or PYTHONPATH.")
        sys.exit(1)

    # 生成 task_id（批量调用时从外部传入同一个）
    if not task_id:
        task_id = f"task_{int(time.time())}"

    # Fixed parameters
    model = "reason"
    scene = "adk_science_navigator"
    env = "uat"
    user_id, org_id, watchtower_token = "", "", ""
    opik_client = OpikClient(env) if OpikClient else None

    sn_search = SNSearch(env, scene, token, user_id, org_id, watchtower_token)

    logging.info(f"Running search: {query} (discipline={discipline}, journal_type={journal_type})")
    answer_result = sn_search.ai_search_result(query, model, discipline, journal_type)
    summary_first_token = answer_result["summary_first_token"]
    keywords = answer_result["keywords"]
    summary = answer_result["summary"]
    papers = answer_result["papers"]
    sub_query = answer_result["sub_query"]
    evidence_search = answer_result["evidence_search"]
    llm_span = ""
    if scene == "adk_science_navigator" and opik_client:
        session_id = answer_result["session_id"]
        traces = opik_client.search_traces(filter_string=f'thread_id = "{session_id}"')
        if traces:
            trace = traces[0]
            trace_id = trace.id
            llm_span = opik_client.get_llm_span_io(trace_id)
    logging.info("AI搜索结束，开始AI评分")
    papers_str = json.dumps(papers, ensure_ascii=False) if isinstance(papers, list) else papers
    _ai = AgentWorkflow(query, keywords, summary, papers_str, scene, summary_first_token, sub_query,
                        evidence_search, llm_span)
    ai_analysis = _ai.get_ai_result()
    score_json = _ai.get_score(ai_analysis)
    score_reasons_json = _ai.extract_score_reasons(ai_analysis)
    logging.info("AI评分结束")

    # 写入飞书多维表格
    from lark_bitable import ensure_table, insert_record, build_record_fields, LARK_APP_TOKEN
    if LARK_APP_TOKEN:
        try:
            table_id = ensure_table(LARK_APP_TOKEN)
            record = build_record_fields(
                query, answer_result, ai_analysis, score_json, score_reasons_json,
                model, scene, env, task_id
            )
            insert_record(LARK_APP_TOKEN, table_id, record)
            logging.info("已写入飞书多维表格")
        except Exception as e:
            logging.error(f"写入飞书多维表格失败: {e}")
    else:
        logging.warning("未配置 LARK_APP_TOKEN，跳过写入飞书多维表格")



def _load_queries_from_file(file_path):
    """从 csv/json/xlsx 文件加载 query 列表，自动去重。

    返回 list[dict]，每个 dict 包含 query, discipline, journal_type。
    """
    file_path = str(file_path)
    seen = set()
    queries = []

    if file_path.endswith(".csv"):
        import csv
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                q = row.get("query", "").strip()
                if q and q not in seen:
                    seen.add(q)
                    queries.append({
                        "query": q,
                        "discipline": row.get("discipline", "All").strip() or "All",
                        "journal_type": row.get("journal_type", "both").strip() or "both",
                    })

    elif file_path.endswith(".json"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            q = item.get("query", "").strip()
            if q and q not in seen:
                seen.add(q)
                queries.append({
                    "query": q,
                    "discipline": item.get("discipline", "All").strip() or "All",
                    "journal_type": item.get("journal_type", "both").strip() or "both",
                })

    elif file_path.endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
        header = [cell.value for cell in ws[1]]
        if "query" not in header:
            raise ValueError(f"xlsx 文件中未找到 'query' 列，当前列: {header}")
        q_col = header.index("query")
        d_col = header.index("discipline") if "discipline" in header else None
        j_col = header.index("journal_type") if "journal_type" in header else None

        for row in ws.iter_rows(min_row=2, values_only=True):
            q = str(row[q_col]).strip() if row[q_col] else ""
            if q and q not in seen:
                seen.add(q)
                queries.append({
                    "query": q,
                    "discipline": str(row[d_col]).strip() if d_col is not None and row[d_col] else "All",
                    "journal_type": str(row[j_col]).strip() if j_col is not None and row[j_col] else "both",
                })
    else:
        raise ValueError(f"不支持的文件格式: {file_path}，请使用 .csv / .json / .xlsx")

    return queries


def run_batch(token, file_path, workers=5):
    """从文件批量运行搜索（支持 csv/json/xlsx），多线程并发，自动去重"""

    queries = _load_queries_from_file(file_path)
    logging.info(f"从 {file_path} 读取到 {len(queries)} 条去重后的 query")

    task_id = f"task_{int(time.time())}"
    logging.info(f"批次 task_id: {task_id}, 并发线程数: {workers}")

    # 先确保表和字段存在（主线程做一次，避免并发创建字段冲突）
    from lark_bitable import ensure_table, LARK_APP_TOKEN
    if LARK_APP_TOKEN:
        ensure_table(LARK_APP_TOKEN)

    success = 0
    fail = 0

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="worker") as pool:
        futures = {
            pool.submit(
                run_single_search, token, item["query"],
                item["discipline"], item["journal_type"], ".", task_id
            ): item["query"]
            for item in queries
        }
        for future in as_completed(futures):
            query = futures[future]
            try:
                future.result()
                success += 1
                logging.info(f"进度: {success + fail}/{len(queries)} (成功 {success}, 失败 {fail})")
            except Exception as e:
                fail += 1
                logging.error(f"query '{query}' 执行失败: {e}")

    logging.info(f"批量执行完成: 成功 {success}, 失败 {fail}, 共 {len(queries)}")


# ============ 配置区 ============
TOKEN = "your-token-here"
_SCRIPT_DIR = Path(__file__).resolve().parent
QUERY_FILE = str(_SCRIPT_DIR.parent / "examples" / "queries.csv")  # 支持 .csv / .json / .xlsx
WORKERS = 3          # 并发线程数
# ================================


def main():
    if len(sys.argv) >= 2:
        # 命令行模式：python run_search.py "查询内容" [discipline] [journal_type]
        query = sys.argv[1]
        discipline = sys.argv[2] if len(sys.argv) > 2 else "All"
        journal_type = sys.argv[3] if len(sys.argv) > 3 else "both"
        run_single_search(TOKEN, query, discipline, journal_type)
    else:
        # 无参数：从配置的文件批量运行
        run_batch(TOKEN, QUERY_FILE, workers=WORKERS)


if __name__ == "__main__":
    main()
