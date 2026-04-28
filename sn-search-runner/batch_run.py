#!/usr/bin/env python3
import csv
import json
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from sn_search import SNSearch
from const import SN_TOKEN, LARK_APP_TOKEN, LARK_TABLE_ID, DIFY_API_KEY
from lark_bitable import ensure_table, insert_record, build_record_fields
from agent_workflow import AgentWorkflow

def main():
    csv_file = "examples/queries.csv"
    output_dir = "results"
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    Path(output_dir).mkdir(exist_ok=True)

    # 初始化飞书多维表格
    print("初始化飞书多维表格...")
    table_id = ensure_table(LARK_APP_TOKEN)
    print(f"表格 ID: {table_id}\n")

    sn = SNSearch("prod", "adk_science_navigator", SN_TOKEN, "", "", "")

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        queries = list(reader)

    total = len(queries)
    print(f"开始批量搜索，共 {total} 条查询\n")

    for idx, row in enumerate(queries, 1):
        query = row['query']
        discipline = row.get('discipline', 'All')
        journal_type = row.get('journal_type', 'both')

        print(f"[{idx}/{total}] {query[:60]}...")

        try:
            result = sn.ai_search_result(query, "reason", discipline, journal_type)

            # 保存 JSON 文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_query = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in query)[:50]
            filename = f"{output_dir}/{idx:03d}_{safe_query}_{timestamp}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            # 写入飞书多维表格
            try:
                # 调用 AI 评分
                agent = AgentWorkflow(
                    query=query,
                    keywords=result.get("keywords", []),
                    summary=result.get("summary", ""),
                    papers=json.dumps(result.get("papers", []), ensure_ascii=False),
                    scene="adk_science_navigator",
                    ttft=result.get("summary_first_token", 0),
                    sub_query=result.get("sub_query", []),
                    evidence_search=result.get("evidence_search", [])
                )
                ai_analysis = agent.get_ai_result()
                score_json = agent.get_score(ai_analysis)
                score_reasons_json = agent.extract_score_reasons(ai_analysis)

                # 构建记录字段
                fields = build_record_fields(
                    query=query,
                    answer_result=result,
                    ai_analysis=ai_analysis,
                    score_json=score_json,
                    score_reasons_json=score_reasons_json,
                    model="reason",
                    scene="adk_science_navigator",
                    env="prod",
                    task_id=task_id
                )

                # 写入表格
                insert_record(LARK_APP_TOKEN, table_id, fields)
                print(f"✓ 已保存到文件和多维表格\n")

            except Exception as e:
                print(f"✓ 已保存到文件，但写入多维表格失败: {e}\n")

            time.sleep(2)

        except Exception as e:
            print(f"✗ 错误: {e}\n")
            continue

    print(f"\n✓ 完成！结果保存在 {output_dir}/ 目录和飞书多维表格")

if __name__ == "__main__":
    main()
