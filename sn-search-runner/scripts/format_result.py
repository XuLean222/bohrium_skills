#!/usr/bin/env python3
"""
Format SN search results to make papers field structured and readable.

Supports both old format (papers as pipe-delimited string) and
new format (papers as list of dicts). For new format, just reorders fields.
"""
import json
import sys
from pathlib import Path


def parse_papers_string(papers_str):
    """将旧版 papers 原始字符串解析为结构化列表（向后兼容）。"""
    if not papers_str:
        return []

    papers_str = papers_str.strip('"')
    paper_entries = papers_str.split(" | ")

    papers_list = []
    known_keys = [
        "Title", "Author", "Journal", "Abstract", "doi",
        "PublicationDate", "citation_id",
        "snippet", "url", "key_points",
        "site", "data_source", "date",
    ]

    for entry in paper_entries:
        paper = {}
        for i, key in enumerate(known_keys):
            pattern = key + ": "
            idx = entry.find(pattern)
            if idx == -1:
                continue
            value_start = idx + len(pattern)
            next_pos = len(entry)
            for next_key in known_keys[i + 1:]:
                nidx = entry.find(", " + next_key + ": ", value_start)
                if nidx != -1 and nidx < next_pos:
                    next_pos = nidx
                    break
            paper[key] = entry[value_start:next_pos].strip()
        if paper:
            papers_list.append(paper)

    return papers_list


def format_result(input_file, output_file=None):
    """格式化搜索结果 JSON 文件。"""
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 只有当 papers 是字符串时才解析，已经是 list 则跳过
    papers = data.get("papers", "")
    if isinstance(papers, str) and papers:
        data["papers"] = parse_papers_string(papers)

    formatted_data = {
        "session_id": data.get("session_id", ""),
        "share_url": data.get("share_url", ""),
        "keywords": data.get("keywords", []),
        "sub_query": data.get("sub_query", []),
        "summary": data.get("summary", ""),
        "papers": data.get("papers", []),
        "evidence_search": data.get("evidence_search", []),
        "summary_first_token": data.get("summary_first_token", 0)
    }

    if output_file is None:
        output_file = input_file

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(formatted_data, f, ensure_ascii=False, indent=2)

    print(f"Formatted result saved to {output_file}")
    print(f"Total references: {len(formatted_data['papers'])}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        format_result("result.json")
    elif len(sys.argv) == 2:
        format_result(sys.argv[1])
    elif len(sys.argv) == 3:
        format_result(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python format_result.py [input_file] [output_file]")
        sys.exit(1)
