---
name: sn-query-classification
description: Runs the full LLM-based query classification pipeline on an Excel file with a "query" column. Produces ability class, subject/domain, and intent/action/constraint columns. Use when the user provides an xlsx with a query column and wants to classify queries (能力/学科领域/意图动作限制条件), or when they mention "query分类", "学科领域分类", "意图分类", "run_all_classifications".
---

# LLM Query 分类流水线

对包含 **query** 列的 Excel 文件，顺序执行能力分类、学科+领域分类、意图/动作/限制条件分类，输出合并到同一张表。本 skill 为自包含包：只需本目录 + 配置 Azure OpenAI 环境变量即可运行。

## 何时使用

- 用户提供一个含 **query** 列的 xlsx，希望对 query 做「一系列分类」
- 用户提到「query 分类」「学科领域」「意图分类」「能力分类」并给出 xlsx 路径
- 需要一次性得到：能力类别、学科、领域、主意图、隐含意图、动作、限制条件 等列

## 输入要求

- 输入文件：**Excel（.xlsx）**，且必须包含列 **`query`**
- 其他列会原样保留，并在右侧追加分类结果列

## 使用前准备

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **配置 Azure OpenAI（必填）**
   - 复制 `.env.example` 为 `.env`，填入 `AZURE_OPENAI_API_KEY`、`AZURE_OPENAI_ENDPOINT` 等；或运行前 export 环境变量。
   - 环境变量说明见 `.env.example`。

## 运行方式

在**本 skill 所在目录**下执行：

```bash
python scripts/run_all_classifications.py --input /path/to/含有query列的.xlsx --output /path/to/分类结果.xlsx
```

可选参数：`--workers 5`（并行条数，默认 3）

## 输出列说明

| 分类模块 | 输出列 |
|----------|--------|
| 能力分类 | 能力类别、能力类别置信度、能力类别判断理由 |
| 学科/领域 | 学科、领域 |
| 意图分类 | 主意图名称/置信度/判断理由，隐含意图1-N、动作1-N、限制条件1-N（多列展开），query字数 |

详细流程与输出列见 [reference/flow.md](reference/flow.md)。

## 依赖与配置

- 分类逻辑在 **scripts/** 下：`run_all_classifications.py`（入口）、`ability_classification.py`、`domain_classification.py`、`query_classification.py`。请勿修改脚本逻辑，仅通过环境变量或参数配置。
- 三个模块内部使用 **Azure OpenAI**；运行前需保证已填写有效 key/endpoint。

## 流程简述

1. 读取 Excel，校验存在 `query` 列。
2. 对每条 query 顺序执行：**能力分类 → 学科+领域分类 → 意图分类**。
3. 将三类结果与原有列合并，写出到指定输出 xlsx。

详细流程与模块职责见 [reference/flow.md](reference/flow.md)。
