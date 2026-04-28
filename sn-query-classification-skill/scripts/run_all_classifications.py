#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
顺序调用能力分类、领域分类、意图分类三个模块，将结果合并到同一张 Excel。

用法:
    python run_all_classifications.py [--input INPUT.xlsx] [--output OUTPUT.xlsx]
    或在脚本内修改 INPUT_FILE / OUTPUT_FILE 后直接运行。
"""

import argparse
import os
import sys

# 保证从 code 目录或项目根目录运行都能正确导入
_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
if _CODE_DIR not in sys.path:
    sys.path.insert(0, _CODE_DIR)

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from ability_classification import classify_single_query
from domain_classification import analyze_subject_and_domain
from query_classification import analyze_four_category_intent


def _empty_intent_four():
    """意图分类为空/异常时的四维结构，供 expand_dimension 使用。"""
    empty_dim = {"result": "无", "confidence": "0.0", "reason": ""}
    return {
        "主意图": {"result": "", "confidence": "0.0", "reason": ""},
        "隐含意图": empty_dim.copy(),
        "动作": empty_dim.copy(),
        "限制条件": empty_dim.copy(),
    }


def run_one_query(query: str) -> dict:
    """
    对单条 query 顺序执行：能力分类 -> 领域分类 -> 意图分类。
    返回包含三类结果及意图四维的字典；意图部分含 intent_four，用于与 query_classification 一致的多列展开。
    """
    empty = str(query).strip() == "" or (isinstance(query, float) and pd.isna(query))
    if empty:
        return {
            "能力类别": "无法识别",
            "能力类别置信度": "0.0",
            "能力类别判断理由": "标题为空；无有效查询内容",
            "学科": "",
            "领域": "",
            "主意图名称": "",
            "主意图置信度": "",
            "主意图判断理由": "",
            "intent_four": _empty_intent_four(),
        }

    q = str(query).strip()
    out = {}

    # 1. 能力分类
    try:
        cat, conf, feat = classify_single_query(q)
        out["能力类别"] = cat or "无法识别"
        out["能力类别置信度"] = conf or "0.0"
        out["能力类别判断理由"] = feat or ""
    except Exception as e:
        out["能力类别"] = "ERROR"
        out["能力类别置信度"] = "0.0"
        out["能力类别判断理由"] = str(e)[:200]

    # 2. 学科 + 领域分类
    try:
        subject, field = analyze_subject_and_domain(q)
        out["学科"] = subject or "未知"
        out["领域"] = field or "未知"
    except Exception as e:
        out["学科"] = "未知"
        out["领域"] = "未知"

    # 3. 意图分类（四维），保留原始结构供多列展开
    try:
        intent_result = analyze_four_category_intent(q, retry_on_error=True)
        out["主意图名称"] = intent_result.get("主意图", {}).get("result", "") or "无"
        out["主意图置信度"] = intent_result.get("主意图", {}).get("confidence", "") or "0.0"
        out["主意图判断理由"] = intent_result.get("主意图", {}).get("reason", "") or ""
        out["intent_four"] = intent_result
    except Exception as e:
        out["主意图名称"] = "ERROR"
        out["主意图置信度"] = "0.0"
        out["主意图判断理由"] = str(e)[:200]
        out["intent_four"] = _empty_intent_four()

    return out


def _split_by_comma(s: str) -> list:
    """将逗号分隔的字符串拆分为列表，与 query_classification 一致。"""
    if not s or s == "无" or s == "ERROR" or s == "未识别":
        return []
    return [item.strip() for item in str(s).split(",") if item.strip()]


def _expand_dimension(results: list, dimension: str, max_count: int = None) -> dict:
    """
    将某个维度的多个值展开为多列（与 query_classification 相同格式）。
    返回: {列名: 列数据列表}，如 隐含意图1名称、隐含意图1置信度、隐含意图1判断理由、隐含意图2名称...
    """
    if max_count is None:
        max_count = 0
        for r in results:
            values = _split_by_comma(r[dimension]["result"])
            max_count = max(max_count, len(values))
        max_count = max(max_count, 1)

    columns = {}
    for i in range(max_count):
        idx = i + 1
        columns[f"{dimension}{idx}名称"] = []
        columns[f"{dimension}{idx}置信度"] = []
        columns[f"{dimension}{idx}判断理由"] = []

    for r in results:
        values = _split_by_comma(r[dimension]["result"])
        confidence = r[dimension].get("confidence", "") or "0.0"
        reason = r[dimension].get("reason", "") or ""
        for i in range(max_count):
            idx = i + 1
            if i < len(values):
                columns[f"{dimension}{idx}名称"].append(values[i])
                columns[f"{dimension}{idx}置信度"].append(confidence)
                columns[f"{dimension}{idx}判断理由"].append(reason)
            else:
                columns[f"{dimension}{idx}名称"].append("")
                columns[f"{dimension}{idx}置信度"].append("")
                columns[f"{dimension}{idx}判断理由"].append("")

    return columns


def run_all_classifications(
    input_excel: str,
    output_excel: str,
    max_workers: int = 3,
) -> None:
    """
    读取含 query 列的 Excel，对每行顺序执行三类分类，结果合并后写入 output_excel。
    """
    df = pd.read_excel(input_excel)
    if "query" not in df.columns:
        raise ValueError("输入文件必须包含 'query' 列")

    queries = df["query"].tolist()
    n = len(queries)

    print(f"共 {n} 条 query，顺序执行：能力分类 -> 领域分类 -> 意图分类")
    print(f"并行处理 {max_workers} 条（每条内部为顺序调用三个分类）\n")

    results = [None] * n
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {executor.submit(run_one_query, q): i for i, q in enumerate(queries)}
        for future in tqdm(as_completed(future_to_idx), total=n, desc="分类进度"):
            i = future_to_idx[future]
            try:
                results[i] = future.result()
            except Exception as e:
                results[i] = run_one_query("")  # 用空 query 的占位结果
                results[i]["能力类别判断理由"] = f"处理异常: {str(e)[:150]}"

    # 合并到 DataFrame（与 query_classification 一致的列结构）
    # 能力 + 学科 + 领域 + 主意图（固定列）
    for col in [
        "能力类别", "能力类别置信度", "能力类别判断理由",
        "学科", "领域",
        "主意图名称", "主意图置信度", "主意图判断理由",
    ]:
        df[col] = [r[col] for r in results]

    # 隐含意图、动作、限制条件：多列展开（隐含意图1名称、隐含意图1置信度、隐含意图1判断理由、隐含意图2...）
    intent_results = [r["intent_four"] for r in results]
    for dimension in ("隐含意图", "动作", "限制条件"):
        dim_cols = _expand_dimension(intent_results, dimension)
        for col_name, col_data in dim_cols.items():
            df[col_name] = col_data

    df["query字数"] = df["query"].apply(lambda x: len(str(x)) if pd.notna(x) else 0)

    os.makedirs(os.path.dirname(os.path.abspath(output_excel)) or ".", exist_ok=True)
    df.to_excel(output_excel, index=False)
    print(f"\n结果已保存: {output_excel}")
    print("\n能力类别统计:")
    print(df["能力类别"].value_counts().to_string())


def main():
    parser = argparse.ArgumentParser(description="顺序调用能力/领域/意图三类分类并合并结果")
    parser.add_argument("--input", "-i", required=True, help="输入 Excel（须含 query 列）")
    parser.add_argument("--output", "-o", required=True, help="输出 Excel")
    parser.add_argument("--workers", "-w", type=int, default=3, help="并行处理的 query 数，默认 3")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"错误: 输入文件不存在: {args.input}")
        sys.exit(1)

    run_all_classifications(args.input, args.output, max_workers=args.workers)


if __name__ == "__main__":
    main()
