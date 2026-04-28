#!/usr/bin/env python3
"""从 scripts/sql语句.xlsx 生成 sql/*.sql 与 dms_scenarios.json。仅依赖标准库。"""
from __future__ import annotations

import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def col_letter_to_idx(ref: str) -> int:
    letters = "".join(c for c in ref if c.isalpha())
    n = 0
    for c in letters:
        n = n * 26 + (ord(c.upper()) - ord("A") + 1)
    return n - 1


def load_shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out = []
    for si in root.findall(".//m:si", NS):
        out.append("".join(si.itertext()))
    return out


def parse_rows(z: zipfile.ZipFile, ss: list[str]) -> dict[int, dict[int, str]]:
    root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows: dict[int, dict[int, str]] = {}
    for row in root.findall(".//m:row", NS):
        ridx = int(row.get("r", 0))
        rowd: dict[int, str] = {}
        for c in row.findall("m:c", NS):
            ref = c.get("r", "")
            col = col_letter_to_idx(ref)
            t = c.get("t")
            v = c.find("m:v", NS)
            if v is None:
                val = ""
            else:
                val = v.text or ""
                if t == "s" and val.isdigit():
                    val = ss[int(val)]
            rowd[col] = val
        rows[ridx] = rowd
    return rows


def main() -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xlsx = os.path.join(script_dir, "sql语句.xlsx")
    if not os.path.isfile(xlsx):
        print(f"未找到: {xlsx}", file=sys.stderr)
        return 1

    sql_dir = os.path.join(script_dir, "sql")
    os.makedirs(sql_dir, exist_ok=True)

    with zipfile.ZipFile(xlsx) as z:
        ss = load_shared_strings(z)
        rows = parse_rows(z, ss)

    scenarios: list[dict] = []
    for ridx in sorted(rows.keys()):
        if ridx == 1:
            continue
        rd = rows[ridx]
        seq = (rd.get(0) or "").strip()
        if not seq or not seq.isdigit():
            continue
        title = (rd.get(1) or "").strip()
        instance = (rd.get(2) or "").strip()
        database = (rd.get(3) or "").strip()
        sql = (rd.get(4) or "").strip()
        notes = (rd.get(5) or "").strip()
        if sql.endswith(";)"):
            sql = sql[:-1]
        fn = f"scenario-{int(seq):02d}.sql"
        rel = f"sql/{fn}"
        path = os.path.join(sql_dir, fn)
        with open(path, "w", encoding="utf-8") as f:
            f.write(sql)
            if not sql.endswith("\n"):
                f.write("\n")
        scenarios.append(
            {
                "id": seq,
                "title": title,
                "instance": instance,
                "database": database,
                "sql_file": rel,
                "notes": notes,
            }
        )

    out_json = os.path.join(script_dir, "dms_scenarios.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(scenarios, f, ensure_ascii=False, indent=2)

    skill_md = os.path.normpath(
        os.path.join(script_dir, "..", ".cursor", "skills", "dms-sql-query-export", "scenarios.md")
    )
    if os.path.isdir(os.path.dirname(skill_md)):
        lines = [
            "# 预置场景索引",
            "",
            "> 供 Agent 读取：用户提到 **场景序号（1–14）** 或下表中 **使用场景** 标题时，映射到 "
            "`scripts/sql/scenario-XX.sql` 与 `dms_query.sh --scenario <序号>`。",
            "",
            "同步方式：在 `scripts/` 下执行 `python3 sync_scenarios_from_xlsx.py`（依赖同目录 `sql语句.xlsx`）。",
            "",
            "| 序号 | 使用场景 | DMS 实例名 | 库名 | sql 文件 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for s in scenarios:
            title = s["title"].replace("|", "\\|")
            lines.append(
                f"| {s['id']} | {title} | {s['instance']} | {s['database']} | `{s['sql_file']}` |"
            )
        lines += [
            "",
            "## 调用方式",
            "",
            "```bash",
            "./scripts/dms_query.sh --list-scenarios",
            "./scripts/dms_query.sh --scenario <序号>",
            "./scripts/dms_query.sh --scenario <序号> --export",
            "```",
            "",
        ]
        with open(skill_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"已更新 Skill 表: {skill_md}")

    print(f"已写入 {len(scenarios)} 条场景 -> {sql_dir}/ 与 {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
