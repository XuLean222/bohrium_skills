#!/usr/bin/env python3
"""
AI小导师反馈归因与写入脚本
Claude 调用此脚本完成：写入飞书多维表格
优先级和问题层面均由 Claude 归因后传入
"""

import json
import sys
import subprocess
from typing import List, Dict, Any


def write_to_bitable(records: List[Dict[str, Any]], base_token: str, table_id: str, dry_run: bool = False):
    """批量写入飞书多维表格"""
    if dry_run:
        print("DRY RUN: 将写入以下记录：", file=sys.stderr)
        print(json.dumps(records, ensure_ascii=False, indent=2), file=sys.stderr)
        return

    fields = ["url", "问题描述", "问题层面", "优先级", "创建时间", "备注"]

    rows = []
    for record in records:
        row = [
            record.get("url", ""),
            record.get("问题描述", ""),
            record.get("问题层面", []),
            record.get("优先级", "P2"),
            record.get("创建时间", ""),
            record.get("备注", "")
        ]
        rows.append(row)

    batch_size = 200
    total_batches = (len(rows) + batch_size - 1) // batch_size

    for i in range(0, len(rows), batch_size):
        batch_rows = rows[i:i+batch_size]
        batch_payload = {
            "fields": fields,
            "rows": batch_rows
        }

        print(f">> 写入第 {i//batch_size + 1}/{total_batches} 批（{len(batch_rows)} 行）...", file=sys.stderr)

        cmd = [
            "lark-cli", "base", "+record-batch-create",
            "--base-token", base_token,
            "--table-id", table_id,
            "--json", json.dumps(batch_payload, ensure_ascii=False)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f">> 批次 {i//batch_size + 1} 写入成功", file=sys.stderr)
        except subprocess.CalledProcessError as e:
            print(f"错误：写入第 {i//batch_size + 1} 批失败：{e.stderr}", file=sys.stderr)
            sys.exit(1)


def main():
    """
    主函数

    输入格式（stdin JSON）：
    {
      "base_token": "xxx",
      "table_id": "xxx",
      "dry_run": false,
      "records": [
        {
          "url": "https://...",
          "categories": ["产品层面", "研发层面"],
          "priority": "P0",
          "description": "问题描述",
          "create_time": "2026-04-19 10:00:00",
          "raw_data": {...}
        }
      ]
    }
    """

    input_data = json.load(sys.stdin)

    base_token = input_data["base_token"]
    table_id = input_data["table_id"]
    dry_run = input_data.get("dry_run", False)
    records_input = input_data["records"]

    records_to_write = []
    for rec in records_input:
        record = {
            "url": rec["url"],
            "问题描述": rec.get("description", ""),
            "问题层面": rec.get("categories", []),
            "优先级": rec.get("priority", "P2"),
            "创建时间": rec.get("create_time", ""),
            "备注": json.dumps(rec.get("raw_data", {}), ensure_ascii=False)
        }
        records_to_write.append(record)

    write_to_bitable(records_to_write, base_token, table_id, dry_run)

    print(f"完成！共处理 {len(records_to_write)} 条记录", file=sys.stderr)

if __name__ == "__main__":
    main()
